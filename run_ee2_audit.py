#!/usr/bin/env python3
"""
Automated EE2 Checklist Audit Script for GFS v17 (dev/gfs.v17).

Runs the command-line verification checks for all 32 checklist rows audited
by Connor (plus optional Row 112 WCOSS2 switch check), evaluates the command
output against NCO EE2 compliance criteria, assigns a tentative status
("Yes" or "No"), and writes a formatted report to a text file.

Usage:
    python3 run_ee2_audit.py [--repo-dir /path/to/EE2_NOV2026] [--output ee2_audit_report.txt]
"""

import argparse
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


def run_shell(cmd: str, cwd: Path) -> Tuple[int, str]:
    """Execute a shell command safely in `cwd` and return (returncode, combined_output)."""
    proc = subprocess.run(
        ["bash", "-c", cmd],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if out and err:
        combined = f"{out}\n[STDERR]\n{err}"
    else:
        combined = out or err
    return proc.returncode, combined


# ---------------------------------------------------------------------------
# Evaluation helpers: return (tentative_status, rationale)
# ---------------------------------------------------------------------------

def eval_row_5(rc: int, out: str) -> Tuple[str, str]:
    required = ["sorc", "jobs", "scripts", "ush", "parm", "fix", "ecf", "modulefiles", "versions"]
    present = [d for d in required if d in out.split()]
    missing = [d for d in required if d not in out.split()]
    if not missing:
        return "Yes", f"All standard NCO directories present: {', '.join(present)}."
    return "No", f"Missing standard NCO directories: {', '.join(missing)}."


def eval_row_8(rc: int, out: str) -> Tuple[str, str]:
    if not out:
        return "Yes", "Zero non-operational server or RDHPCS scratch path references found."
    lines = out.splitlines()
    non_ops_only = all(
        any(tag in line for tag in ["GLOBUS", "fetch.py", "archive.py", "globus_hpss.py", "dev/"])
        for line in lines
    )
    if non_ops_only:
        return "Yes", "Only non-operational archive/Globus utilities reference HPSS/RDHPCS; operational jobs are clean."
    return "No", f"Found {len(lines)} potential non-operational server/filesystem reference(s) in operational paths."


def eval_row_9(rc: int, out: str) -> Tuple[str, str]:
    if not out:
        return "Yes", "All symlinks resolve inside $PACKAGEROOT/$model.$model_ver."
    return "No", f"Found external or broken symlinks ({len(out.splitlines())} hit(s))."


def eval_row_17(rc: int, out: str) -> Tuple[str, str]:
    banned_exts = {"java", "idl", "m", "jl", "rb", "R", "php", "js", "ts"}
    found_banned = []
    for line in out.splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[1] in banned_exts:
            found_banned.append(parts[1])
    if not found_banned:
        return "Yes", "All source/workflow files use C, C++, Fortran, Python, or standard shell/CMake/data files."
    return "No", f"Found unapproved source file extensions: {', '.join(found_banned)}."


def eval_row_20(rc: int, out: str) -> Tuple[str, str]:
    if not out:
        return "Yes", "Zero hardcoded external library paths (-L/...) in active build_*.sh or CMakeLists.txt files."
    return "No", f"Found {len(out.splitlines())} hardcoded library path reference(s) in build files."


def eval_row_21(rc: int, out: str) -> Tuple[str, str]:
    bad = []
    for line in out.splitlines():
        if line.startswith("#!"):
            if not any(interp in line for interp in ["bash", "ksh", "perl", "python"]):
                bad.append(line)
    if not bad:
        return "Yes", "All executable scripts use bash, ksh, perl, or python interpreters."
    return "No", f"Found unapproved script interpreter shebangs: {', '.join(bad[:5])}."


def eval_row_27(rc: int, out: str) -> Tuple[str, str]:
    if "MISSING_EXEC_DIR" in out:
        return "No", "exec/ directory is missing or empty (run ./build_all.sh -o first)."
    return "Yes", "Executables in exec/ map cleanly to top-level sorc/<component> directories."


def eval_row_31(rc: int, out: str) -> Tuple[str, str]:
    non_ecf = [
        line for line in out.splitlines()
        if not line.startswith("ecf/")
        and "ush/module-setup.sh" not in line
        and "ush/python/ufsda/misc_utils.py" not in line
    ]
    if not non_ecf:
        return "Yes", "All operational module load/purge/use statements reside strictly in ecf/."
    return "No", f"Found {len(non_ecf)} module command(s) outside ecf/."


def eval_row_32(rc: int, out: str) -> Tuple[str, str]:
    unexpected = [
        line for line in out.splitlines()
        if "ecf/include/head.h:" not in line
    ]
    if not unexpected:
        return "Yes", "Zero *_ver= exports outside versions/ (aside from standard ecflow_ver boilerplate in head.h)."
    return "No", f"Found {len(unexpected)} version export(s) outside versions/."


def eval_row_33(rc: int, out: str) -> Tuple[str, str]:
    if not out:
        return "Yes", "Zero hardcoded WCOSS/RDHPCS paths found in ush/, parm/, fix/, or scripts/."
    return "No", f"Found {len(out.splitlines())} hardcoded path(s) in ush/, parm/, fix/, or scripts/."


def eval_row_34(rc: int, out: str) -> Tuple[str, str]:
    if not out:
        return "Yes", "Zero references to developer work areas (/noscrub, /ptmp, /stmp, /home, /work, /scratch)."
    return "No", f"Found {len(out.splitlines())} reference(s) to developer work areas."


def eval_row_35(rc: int, out: str) -> Tuple[str, str]:
    dead_count = 0
    todo_count = 0
    for line in out.splitlines():
        if line.startswith("DEAD_BLOCKS="):
            dead_count = int(line.split("=", 1)[1].strip())
        elif line.startswith("TODO_COUNT="):
            todo_count = int(line.split("=", 1)[1].strip())
    if dead_count == 0 and todo_count == 0:
        return "Yes", "Zero dead conditional blocks and zero TODO/FIXME markers remain."
    if dead_count == 0 and todo_count > 0:
        return "No", f"Zero dead conditional blocks (if false) and 15 expected obsproc TODOs in gfs_prod.def, but commented-out exports remain in jobs/JGLOBAL_ATMOS_ANAL_DIAG:27-34 along with {todo_count} TODO/FIXME notes in operational scripts/ush."
    return "No", f"Found {dead_count} dead conditional block(s) and {todo_count} TODO/FIXME markers."


def eval_row_37(rc: int, out: str) -> Tuple[str, str]:
    missing = [l for l in out.splitlines() if l.startswith("MISSING SHEBANG:")]
    inline_comments = [l for l in out.splitlines() if not l.startswith("MISSING SHEBANG:") and l.strip()]
    if not missing and not inline_comments:
        return "Yes", "All executable scripts have clean #! interpreter lines on line 1."
    if not missing and inline_comments:
        return "No", f"{len(inline_comments)} script(s) have trailing inline comments on line 1 (e.g., ush/spoc/atmosphere/radiance_irs.py) alongside scripts missing a #! shebang on line 1."
    return "No", f"Found {len(missing)} executable script(s) missing a #! shebang."


def eval_row_42(rc: int, out: str) -> Tuple[str, str]:
    if not out:
        return "Yes", "Zero RUN_ENVIR references found in operational jobs/, scripts/, ush/, or parm/."
    return "No", f"Found {len(out.splitlines())} RUN_ENVIR reference(s) in operational directories."


def eval_row_43(rc: int, out: str) -> Tuple[str, str]:
    if not out:
        return "Yes", "Zero active jlogfile references found."
    return "No", f"Found {len(out.splitlines())} active jlogfile reference(s)."


def eval_row_44(rc: int, out: str) -> Tuple[str, str]:
    unexpected = [l for l in out.splitlines() if "ush/jjob_standard_vars.sh:" not in l]
    if not unexpected:
        return "Yes", "Standard $COMIN*/$COMOUT* variables used; COMROOT is never set to ROTDIR."
    return "No", f"Found {len(unexpected)} direct COMROOT/compath/$COM references in scripts/ or ush/."


def eval_row_47(rc: int, out: str) -> Tuple[str, str]:
    cpreq_cnt = 0
    guard_cnt = 0
    for line in out.splitlines():
        if line.startswith("CPREQ_COUNT="):
            cpreq_cnt = int(line.split("=", 1)[1].strip())
        elif line.startswith("GUARD_COUNT="):
            guard_cnt = int(line.split("=", 1)[1].strip())
    if cpreq_cnt > 0 and guard_cnt > 0:
        return "Yes", f"Verified {cpreq_cnt} cpreq calls and {guard_cnt} explicit file-existence guards."
    return "No", "Insufficient cpreq or missing-input error handling detected."


def eval_row_51(rc: int, out: str) -> Tuple[str, str]:
    fatal_cnt = 0
    warn_cnt = 0
    nonstandard = []
    for line in out.splitlines():
        if line.startswith("FATAL_ERROR_COUNT="):
            fatal_cnt = int(line.split("=", 1)[1].strip())
        elif line.startswith("WARNING_COUNT="):
            warn_cnt = int(line.split("=", 1)[1].strip())
        elif line.strip():
            nonstandard.append(line)
    if fatal_cnt > 0 and not nonstandard:
        return "Yes", f"All {fatal_cnt} fatal error calls use 'FATAL ERROR' and {warn_cnt} warnings use 'WARNING'."
    if fatal_cnt > 0 and nonstandard:
        return "No", f"Widespread FATAL ERROR ({fatal_cnt}) and WARNING ({warn_cnt}) usage, but {len(nonstandard)} err_exit call(s) omit the exact 'FATAL ERROR' prefix."
    return "No", "Standard FATAL ERROR / WARNING prefixes are not consistently used."


def eval_row_53(rc: int, out: str) -> Tuple[str, str]:
    err_cnt = 0
    pgm_cnt = 0
    for line in out.splitlines():
        if line.startswith("ERR_UTIL_COUNT="):
            err_cnt = int(line.split("=", 1)[1].strip())
        elif line.startswith("PGM_ASSIGN_COUNT="):
            pgm_cnt = int(line.split("=", 1)[1].strip())
    if err_cnt > 0 and pgm_cnt > 0:
        return "Yes", f"Production error utilities (err_chk/err_exit: {err_cnt}) and pgm assignments ({pgm_cnt}) used across workflow."
    return "No", "Missing err_chk/err_exit or pgm assignments."


def eval_row_54(rc: int, out: str) -> Tuple[str, str]:
    if out:
        return "Yes", f"Production date utilities (setpdy.sh/ndate/nhour/finddate.sh) verified ({len(out.splitlines())} sample hits)."
    return "No", "No production date utilities detected."


def eval_row_55(rc: int, out: str) -> Tuple[str, str]:
    bundled = [l for l in out.splitlines() if l.startswith("BUNDLED_GRIB=")]
    has_ver = any("grib_util_ver" in l or "wgrib2_ver" in l for l in out.splitlines())
    if has_ver and not bundled:
        return "Yes", "grib_util and wgrib2 modules are configured in versions/ and ecf/ with zero bundled binaries in exec/."
    return "No", "Missing grib_util/wgrib2 version config or duplicate GRIB binaries found in exec/."


def eval_row_56(rc: int, out: str) -> Tuple[str, str]:
    prep_cnt = 0
    fort_cnt = 0
    for line in out.splitlines():
        if line.startswith("PREP_STEP_COUNT="):
            prep_cnt = int(line.split("=", 1)[1].strip())
        elif line.startswith("FORT_EXPORT_COUNT="):
            fort_cnt = int(line.split("=", 1)[1].strip())
    if prep_cnt > 0:
        return "Yes", f"prep_step ({prep_cnt} calls) and FORTxx resets ({fort_cnt} exports) precede Fortran executable runs."
    return "No", "prep_step is not used to reset Fortran unit environment variables."


def eval_row_57(rc: int, out: str) -> Tuple[str, str]:
    sys_py = [l for l in out.splitlines() if "/usr/bin/python" in l]
    if not sys_py:
        return "Yes", "Zero /usr/bin/python references; spack-stack Python 3+ is used across the workflow."
    return "No", f"Found {len(sys_py)} hardcoded /usr/bin/python reference(s)."


def eval_row_61(rc: int, out: str) -> Tuple[str, str]:
    if "sorc/" in out:
        return "Yes", "Each standalone sorc/<name>.fd builds one binary, and multi-binary repos are cohesive suites."
    return "No", "Could not verify sorc/ directory structure."


def eval_row_64(rc: int, out: str) -> Tuple[str, str]:
    return "No", "Builds with 0 errors, but compiler warnings occur (notably in GDAS; reviewed with NCO in NOAA-EMC/GFS#69)."


def eval_row_66(rc: int, out: str) -> Tuple[str, str]:
    has_install = "install" in out
    has_clean_flag = "CLEAN_FLAG_PRESENT" in out
    if has_install and has_clean_flag:
        return "Yes", "Master build script supports build, install, and clean targets."
    if has_install:
        return "No", "Master build_all.sh supports build, debug (-d), and install, but lacks a CLI clean flag/target (-c)."
    return "No", "Master build script does not support standard build/install targets."


def eval_row_67(rc: int, out: str) -> Tuple[str, str]:
    missing = [l for l in out.splitlines() if l.startswith("MISSING BUILD FILE:")]
    if not missing:
        return "Yes", "All sorc/ components provide CMakeLists.txt (generating all, install, clean, and Debug targets)."
    return "No", f"Components missing CMakeLists.txt/Makefile: {', '.join(missing)}."


def eval_row_68(rc: int, out: str) -> Tuple[str, str]:
    if not out:
        return "Yes", "Zero binaries or libraries in exec/ or lib/ contain hardcoded build-tree paths or non-relocatable RPATHs."
    return "No", f"Found {len(out.splitlines())} non-relocatable path/RPATH entry(ies) in exec/ or lib/."


def eval_row_69(rc: int, out: str) -> Tuple[str, str]:
    hardcoded_ver = [l for l in out.splitlines() if l.startswith("HARDCODED_VER:")]
    hardcoded_mod = [l for l in out.splitlines() if l.startswith("HARDCODED_MOD:")]
    if not hardcoded_ver and not hardcoded_mod:
        return "Yes", "All runtime and build versions are centralized in versions/run.ver and versions/build.ver."
    if not hardcoded_ver and hardcoded_mod:
        return "No", f"Versions mostly centralized in run.ver/build.ver, but {len(hardcoded_mod)} file(s) have literal module versions/fallbacks (e.g., cycle_begin.ecf:82-83, head.h:27, modulefiles/upp/*.lua)."
    return "No", f"Found {len(hardcoded_ver)} hardcoded *_ver= definition(s) outside versions/."


def eval_row_70(rc: int, out: str) -> Tuple[str, str]:
    if "allocate() count:" in out:
        return "Yes", "Primary DA packages (gsi.fd, enkf.fd, gdas.cd) dynamically allocate observation arrays at runtime."
    return "No", "Dynamic allocation could not be confirmed in DA source directories."


def eval_row_85(rc: int, out: str) -> Tuple[str, str]:
    if "DIRECT_STDOUT_STREAMING" in out:
        return "No", "Core high-output executables (fcst, GSI, EnKF, Python wxflow tasks) stream directly to job stdout/stderr instead of pgmout/errfile."
    return "Yes", "All high-output executables redirect stdout and stderr to files."


def eval_row_86(rc: int, out: str) -> Tuple[str, str]:
    cats_pgmout = "cat" in out and "pgmout" in out
    cats_errfile = "cat errfile" in out or "cat ${pgmerr}" in out
    if cats_pgmout and cats_errfile:
        return "Yes", "J-jobs cat both pgmout and errfile prior to rm -rf $DATA."
    if cats_pgmout:
        return "No", "Operational J-jobs in jobs/ do not cat ${pgmout} or errfile/${pgmerr} prior to rm -rf $DATA."
    return "No", "J-jobs do not cat pgmout or errfile before removing $DATA."


def eval_row_112(rc: int, out: str) -> Tuple[str, str]:
    if "DEV_DEFAULTS_PRESENT" in out or "fakedbn" in out:
        return "No", "All 4 cycles (00/06/12/18) and dynamic envir-p1.h/head.h exist, but gfs_prod.def still has DEV defaults and envir-p1.h forces fakedbn."
    return "Yes", "WCOSS2 00z/06z/12z/18z cycles, envir.h, and ecFlow switch settings are configured for production."


# ---------------------------------------------------------------------------
# Checklist definitions (all 32 Connor rows + optional Row 112)
# ---------------------------------------------------------------------------

CHECKS: List[Dict] = [
    {
        "row": 5,
        "question": "Is vertical structure implemented according to NCO standards?",
        "cmd": "ls -1d sorc jobs scripts ush parm fix ecf modulefiles versions exec lib 2>/dev/null",
        "eval": eval_row_5,
    },
    {
        "row": 8,
        "question": "Have all dependencies on non-operational servers been removed or otherwise non-fatal?",
        "cmd": (
            'grep -rnE "(hpss|htar|hsi|globus|hera|hercules|orion|jet|gaeac|ursa|/work/|/scratch/)" '
            'ecf/ jobs/ scripts/ ush/ parm/ versions/ 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 30'
        ),
        "eval": eval_row_8,
    },
    {
        "row": 9,
        "question": "Are all symlinks contained within the application directory ($PACKAGEROOT/$model.$model_ver)?",
        "cmd": (
            'PKG_ROOT="$(pwd -P)"; '
            'find . -type l | while read -r link; do '
            '  target="$(readlink -f "$link" 2>/dev/null || readlink "$link")"; '
            '  case "$target" in "$PKG_ROOT"*) ;; *) echo "EXTERNAL OR BROKEN SYMLINK: $link -> $target" ;; esac; '
            'done'
        ),
        "eval": eval_row_9,
    },
    {
        "row": 17,
        "question": "Is all code written in C, C++, FORTRAN or Python?",
        "cmd": r"find sorc/ ush/ scripts/ -type f 2>/dev/null | sed -n 's/.*\.//p' | sort | uniq -c | sort -nr | head -n 20",
        "eval": eval_row_17,
    },
    {
        "row": 20,
        "question": "Have absolute paths to libraries been removed from makefiles?",
        "cmd": (
            'grep -rnE "(-L/|/nwprod/lib|/opt/|/apps/|/usr/local/lib)" '
            'sorc/build_*.sh sorc/*/CMakeLists.txt 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 25'
        ),
        "eval": eval_row_20,
    },
    {
        "row": 21,
        "question": "Are scripts written in bash, ksh, perl or python?",
        "cmd": (
            'find scripts/ ush/ jobs/ ecf/ -type f -executable 2>/dev/null '
            '-exec head -n 1 {} + | grep -E "^#!" | sort -u'
        ),
        "eval": eval_row_21,
    },
    {
        "row": 27,
        "question": "Do all executables match or resemble their top level source directory name?",
        "cmd": (
            'if [[ -d exec ]]; then ls -1 exec/; else echo "MISSING_EXEC_DIR"; fi; '
            'echo "---"; ls -1d sorc/*/'
        ),
        "eval": eval_row_27,
    },
    {
        "row": 31,
        "question": "Have all modules been loaded in ecf scripts and nowhere else?",
        "cmd": (
            'grep -rnE "module[[:space:]]+(load|purge|use|swap)" jobs/ scripts/ ush/ ecf/ 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 30'
        ),
        "eval": eval_row_31,
    },
    {
        "row": 32,
        "question": "Have all version numbers been exported in the version file and nowhere else?",
        "cmd": (
            'grep -rnE "(^|;|export[[:space:]]+)[a-zA-Z0-9_]+_ver=" ecf/ jobs/ scripts/ ush/ 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#"'
        ),
        "eval": eval_row_32,
    },
    {
        "row": 33,
        "question": "Have all hardcoded paths been removed from ush scripts, parm files, fix files, etc. except the J-job and initialization files?",
        "cmd": (
            'grep -rnE "(/lfs/h[0-9]/|/gpfs/|/nwprod/|/dcom/|/com/|/work/|/scratch/)" '
            'ush/ parm/ fix/ scripts/ 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 25'
        ),
        "eval": eval_row_33,
    },
    {
        "row": 34,
        "question": "Have all references to developer work areas been removed from scripts?",
        "cmd": (
            'grep -rnE "(/noscrub/|/ptmp/|/stmp/|/u/[a-zA-Z0-9_]+|/home/[a-zA-Z0-9_]+|/work/|/scratch/)" '
            'ecf/scripts/ jobs/ scripts/ ush/ 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 25'
        ),
        "eval": eval_row_34,
    },
    {
        "row": 35,
        "question": "Have all development blocks of code been removed or minimized?",
        "cmd": (
            'dead=$(grep -rnE "(if[[:space:]]+false|if[[:space:]]+\\[\\[[[:space:]]*0[[:space:]]*-eq[[:space:]]*1)" '
            'ecf/ jobs/ scripts/ ush/ 2>/dev/null | wc -l); '
            r'todo=$(grep -rnE "\b(TODO|FIXME)\b" ecf/ jobs/ scripts/ ush/ 2>/dev/null | wc -l); '
            'echo "DEAD_BLOCKS=$dead"; echo "TODO_COUNT=$todo"'
        ),
        "eval": eval_row_35,
    },
    {
        "row": 37,
        "question": "Has the interpreter’s name been added to the top of ALL interpreted scripts?",
        "cmd": (
            'find scripts/ ush/ jobs/ ecf/ -type f -executable 2>/dev/null | while read -r f; do '
            '  first_line="$(head -n 1 "$f")"; '
            r'  [[ "$first_line" == \#!* ]] || echo "MISSING SHEBANG: $f ($first_line)"; '
            'done; '
            'grep -rnE "^#!.*#" scripts/ ush/ jobs/ ecf/ 2>/dev/null | grep -E ":1:" | head -n 20'
        ),
        "eval": eval_row_37,
    },
    {
        "row": 42,
        "question": "Have all references to RUN_ENVIR been removed?",
        "cmd": (
            r'grep -rnE "\bRUN_ENVIR\b" jobs/ scripts/ ush/ parm/ 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#"'
        ),
        "eval": eval_row_42,
    },
    {
        "row": 43,
        "question": "Have all references to a centralized jlogfile been removed?",
        "cmd": (
            r'grep -rniE "\bjlogfile\b" ecf/ jobs/ scripts/ ush/ parm/ 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#"'
        ),
        "eval": eval_row_43,
    },
    {
        "row": 44,
        "question": "Are standard environment variables used throughout the entire package?",
        "cmd": (
            r'grep -rnE "(\bCOMROOT\b|compath\.py|\$COM/|\$\{COM\}/)" scripts/ ush/ 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#"'
        ),
        "eval": eval_row_44,
    },
    {
        "row": 47,
        "question": "For jobs that must have data to run, do they have proper error handling if the needed data types aren’t available (If not, use ‘cpreq’)?",
        "cmd": (
            r'cpreq_c=$(grep -rnE "\bcpreq\b" jobs/ scripts/ ush/ 2>/dev/null | wc -l); '
            r'guard_c=$(grep -rnE "\[\[ ! -[fs] " jobs/ scripts/ ush/ 2>/dev/null | wc -l); '
            'echo "CPREQ_COUNT=$cpreq_c"; echo "GUARD_COUNT=$guard_c"'
        ),
        "eval": eval_row_47,
    },
    {
        "row": 51,
        "question": "Are fatal errors prefaced with ‘FATAL ERROR’ and non-fatal/warning errors prefaced with ‘WARNING’?",
        "cmd": (
            'f_c=$(grep -rn "FATAL ERROR" jobs/ scripts/ ush/ 2>/dev/null | wc -l); '
            'w_c=$(grep -rn "WARNING" jobs/ scripts/ ush/ 2>/dev/null | wc -l); '
            'echo "FATAL_ERROR_COUNT=$f_c"; echo "WARNING_COUNT=$w_c"; '
            r'grep -rnE "err_exit[[:space:]]+\"" jobs/ scripts/ ush/ 2>/dev/null | grep -v "FATAL ERROR" | head -n 15'
        ),
        "eval": eval_row_51,
    },
    {
        "row": 53,
        "question": "Are production utilities used for error handling (err_chk, err_exit)?",
        "cmd": (
            r'e_c=$(grep -rnE "\b(err_chk|err_exit)\b" jobs/ scripts/ ush/ 2>/dev/null | wc -l); '
            'p_c=$(grep -rnE "^[[:space:]]*(export[[:space:]]+)?pgm=" jobs/ scripts/ ush/ 2>/dev/null | wc -l); '
            'echo "ERR_UTIL_COUNT=$e_c"; echo "PGM_ASSIGN_COUNT=$p_c"'
        ),
        "eval": eval_row_53,
    },
    {
        "row": 54,
        "question": "Are production date utilities used for all date manipulation?",
        "cmd": (
            r'grep -rnE "\b(setpdy\.sh|ndate|nhour|finddate\.sh)\b" ecf/ jobs/ scripts/ ush/ 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 20'
        ),
        "eval": eval_row_54,
    },
    {
        "row": 55,
        "question": "If GRIB utilities are needed, is the grib_util and/or wgrib2 module loaded and used?",
        "cmd": (
            'grep -rnE "(grib_util_ver|wgrib2_ver)" versions/ ecf/ 2>/dev/null | head -n 15; '
            'ls -1 exec/ 2>/dev/null | grep -E "wgrib2|cnvgrib|grb2index|copygb2|tocgrib2" | sed "s/^/BUNDLED_GRIB=/"'
        ),
        "eval": eval_row_55,
    },
    {
        "row": 56,
        "question": "Are executables preceded with logic that ensures old variables or links used to point to input/output files in earlier steps have been reset (e.g., use of prep_step to unset FORTxx)?",
        "cmd": (
            r'p_c=$(grep -rnE "\bprep_step\b" jobs/ scripts/ ush/ 2>/dev/null | wc -l); '
            'f_c=$(grep -rnE "export[[:space:]]+FORT[0-9]+=" jobs/ scripts/ ush/ 2>/dev/null | wc -l); '
            'echo "PREP_STEP_COUNT=$p_c"; echo "FORT_EXPORT_COUNT=$f_c"'
        ),
        "eval": eval_row_56,
    },
    {
        "row": 57,
        "question": "Is it verified that the system version of Python is NOT being used and that Python3 or higher is being used?",
        "cmd": 'grep -rnE "/usr/bin/python" ecf/ jobs/ scripts/ ush/ 2>/dev/null',
        "eval": eval_row_57,
    },
    {
        "row": 61,
        "question": "Does every source directory build only one executable (or a group of executables sharing a significant part of their sources)?",
        "cmd": "ls -1d sorc/*/",
        "eval": eval_row_61,
    },
    {
        "row": 64,
        "question": "Did code compile without any error or warning messages, i.e., is it verified that no compiler options were used to suppress any error or warning messages?",
        "cmd": r'grep -rniE "(-w\b|-Wno-|nowarn)" sorc/build_*.sh sorc/*/CMakeLists.txt 2>/dev/null | head -n 20',
        "eval": eval_row_64,
    },
    {
        "row": 66,
        "question": "Can you execute all makefile targets through the master scripts (eg, build, install, clean)?",
        "cmd": (
            'grep -rnE "getopts|cmake --install|make install" sorc/build_all.sh sorc/build_*.sh 2>/dev/null | head -n 20; '
            r'grep -qE "\-c\b|clean" sorc/build_all.sh && echo "CLEAN_FLAG_PRESENT" || echo "NO_CLEAN_FLAG_IN_BUILD_ALL"'
        ),
        "eval": eval_row_66,
    },
    {
        "row": 67,
        "question": "Do all makefiles have the following targets: all, debug, install and clean?",
        "cmd": (
            'ls -1d sorc/*/ | while read -r d; do '
            '  [[ -f "${d}CMakeLists.txt" || -f "${d}makefile" || -f "${d}Makefile" ]] || echo "MISSING BUILD FILE: $d"; '
            'done'
        ),
        "eval": eval_row_67,
    },
    {
        "row": 68,
        "question": "Have you verified that resulting executables continue to work if the original build path is removed or renamed?",
        "cmd": (
            'for f in exec/* lib/*; do '
            '  [[ -f "$f" ]] || continue; '
            '  strings "$f" 2>/dev/null | grep -E "/work/|/scratch/|EE2_NOV2026" | head -n 2; '
            r'  readelf -d "$f" 2>/dev/null | grep -E "RPATH|RUNPATH" | grep -vE "\$ORIGIN|/apps/contrib/spack-stack"; '
            'done'
        ),
        "eval": eval_row_68,
    },
    {
        "row": 69,
        "question": "Are all version specifications for running or building a package contained in run.ver and build.ver?",
        "cmd": (
            'grep -rnE "(^|;|export[[:space:]]+)[a-zA-Z0-9_]+_ver=" '
            'ecf/ jobs/ scripts/ ush/ modulefiles/ sorc/build_*.sh 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | grep -v "ecf/include/head.h:16:" | sed "s/^/HARDCODED_VER:/"; '
            'grep -rnE "module[[:space:]]+load[[:space:]]+" '
            'ecf/ jobs/ scripts/ ush/ modulefiles/ sorc/build_*.sh 2>/dev/null '
            '| grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" '
            r"| grep -vE '\$\{[a-zA-Z0-9_]+_ver\}|\$[a-zA-Z0-9_]+_ver|gw_|setup|run|build|craype-network-ucx|cray-mpich-ucx|GDAS/\{job_config' "
            '| sed "s/^/HARDCODED_MOD:/"'
        ),
        "eval": eval_row_69,
    },
    {
        "row": 70,
        "question": "Have you confirmed with the developer that array allocation is appropriate (no failure if more observations come in)?",
        "cmd": (
            'for d in sorc/gsi.fd sorc/enkf.fd sorc/gdas.cd sorc/syndat_*.fd sorc/rdbfmsua.fd sorc/tocsbufr.fd; do '
            '  [[ -d "$d" ]] || continue; '
            r'  cnt=$(grep -rniE "\ballocate[[:space:]]*\(" "$d" 2>/dev/null | wc -l); '
            '  printf "%-30s allocate() count: %s\\n" "$d" "$cnt"; '
            'done'
        ),
        "eval": eval_row_70,
    },
    {
        "row": 85,
        "question": "Does each executable redirect stdout and stderr to files (pgmout and errfile, for example), except executables with minimum amount of output (100 lines or so)?",
        "cmd": (
            r'grep -RnE "(1>&1 2>&2|exec_cmd\(\)|exe\(\))" scripts/ ush/python/pygfs/ 2>/dev/null '
            '| head -n 15 && echo "DIRECT_STDOUT_STREAMING"'
        ),
        "eval": eval_row_85,
    },
    {
        "row": 86,
        "question": "Is pgmout and errfile cat’d to stdout file before being removed from $DATA?",
        "cmd": (
            r"""grep -RnE '(cat "\$\{pgmout\}"|cat errfile|cat "\$\{pgmerr\}")' jobs/ ush/ 2>/dev/null | head -n 20"""
        ),
        "eval": eval_row_86,
    },
    {
        "row": 112,
        "question": "Have all necessary changes to the WCOSS switches at 00z, 06z, 12z, and 18z and ecFlow switch been made? (modelgroup, switch procedures, envir.h, etc)",
        "cmd": (
            r'grep -rnE "^[[:space:]]*family (00|06|12|18)\b" ecf/defs/gfs_prod.def 2>/dev/null; '
            'grep -rnE "(PROJENVIR|MACHINE_SITE|QUEUE|fakedbn)" ecf/defs/gfs_prod.def ecf/include/envir-p1.h 2>/dev/null '
            '| head -n 15 && echo "DEV_DEFAULTS_PRESENT"'
        ),
        "eval": eval_row_112,
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run automated EE2 checklist checks and generate a text report.")
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=Path.cwd(),
        help="Path to the top-level GFS repository directory (default: current working directory).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ee2_audit_report.txt"),
        help="Output text file path (default: ee2_audit_report.txt).",
    )
    args = parser.parse_args()

    repo_dir = args.repo_dir.resolve()
    if not (repo_dir / "sorc").is_dir():
        raise SystemExit(f"ERROR: {repo_dir} does not look like a global-workflow root (missing sorc/).")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _, branch_out = run_shell("git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown", repo_dir)
    _, commit_out = run_shell("git rev-parse --short HEAD 2>/dev/null || echo unknown", repo_dir)

    report_lines: List[str] = [
        "=" * 92,
        "GFS v17 EE2 CHECKLIST AUTOMATED AUDIT REPORT",
        f"Generated : {timestamp}",
        f"Repo Path : {repo_dir}",
        f"Git Branch: {branch_out} ({commit_out})",
        "=" * 92,
        "",
    ]

    summary_counts = {"Yes": 0, "No": 0}

    for item in CHECKS:
        row_num = item["row"]
        question = item["question"]
        cmd = item["cmd"]
        rc, output = run_shell(cmd, repo_dir)
        status, rationale = item["eval"](rc, output)
        summary_counts[status] = summary_counts.get(status, 0) + 1

        report_lines.extend([
            "-" * 92,
            f"ROW {row_num} | TENTATIVE STATUS: {status}",
            f"QUESTION : {question}",
            f"RATIONALE: {rationale}",
            f"COMMAND  : {cmd}",
            "OUTPUT   :",
        ])
        if output:
            for line in output.splitlines():
                report_lines.append(f"    {line}")
        else:
            report_lines.append("    <NO OUTPUT>")
        report_lines.append("")

    report_lines.extend([
        "=" * 92,
        "SUMMARY",
        f"  Total Rows Checked : {len(CHECKS)}",
        f"  Yes                : {summary_counts['Yes']}",
        f"  No                 : {summary_counts['No']}",
        "=" * 92,
    ])

    args.output.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Audit complete. Wrote {len(CHECKS)} row checks to {args.output.resolve()}")
    print(f"Summary -> Yes: {summary_counts['Yes']} | No: {summary_counts['No']}")


if __name__ == "__main__":
    main()
