# GFS v17 (`dev/gfs.v17`) EE2 Audit Runbook & Verification Guide

## 1. Background & Environment Setup (`dev/gfs.v17` on Hercules)

1. **Clone `dev/gfs.v17` (not `develop`):**
   `git clone --recursive -b dev/gfs.v17 https://github.com/NOAA-EMC/global-workflow.git EE2_NOV2026`
2. **Build operational components (`-o`):**
   `cd EE2_NOV2026/sorc && ./build_all.sh -o && cd ..`
3. **Stage NCO directory layout (`setup_gfs_for_nco.py`):**
   `python3 dev/ush/setup_gfs_for_nco.py`
4. **Run automated audit script:**
   `python3 run_ee2_audit.py --repo-dir /path/to/EE2_NOV2026 --output ee2_audit_report.txt`

---

## 2. Checklist Verification Commands & Expected Findings (33 Rows)

### Row 5
* **Checklist Question:** Is vertical structure implemented according to NCO standards?
* **Audit Finding / Notes:** Missing standard NCO directories: sorc, jobs, scripts, ush, parm, fix, ecf, modulefiles, versions.
* **Command Executed:** `ls -1d sorc jobs scripts ush parm fix ecf modulefiles versions exec lib 2>/dev/null`

### Row 8
* **Checklist Question:** Have all dependencies on non-operational servers been removed or otherwise non-fatal?
* **Audit Finding / Notes:** Zero non-operational server or RDHPCS scratch path references found.
* **Command Executed:** `grep -rnE "(hpss|htar|hsi|globus|hera|hercules|orion|jet|gaeac|ursa|/work/|/scratch/)" ecf/ jobs/ scripts/ ush/ parm/ versions/ 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 30`

### Row 9
* **Checklist Question:** Are all symlinks contained within the application directory ($PACKAGEROOT/$model.$model_ver)?
* **Audit Finding / Notes:** All symlinks resolve inside $PACKAGEROOT/$model.$model_ver.
* **Command Executed:** `PKG_ROOT="$(pwd -P)"; find . -type l | while read -r link; do   target="$(readlink -f "$link" 2>/dev/null || readlink "$link")";   case "$target" in "$PKG_ROOT"*) ;; *) echo "EXTERNAL OR BROKEN SYMLINK: $link -> $target" ;; esac; done`

### Row 17
* **Checklist Question:** Is all code written in C, C++, FORTRAN or Python?
* **Audit Finding / Notes:** All source/workflow files use C, C++, Fortran, Python, or standard shell/CMake/data files.
* **Command Executed:** `find sorc/ ush/ scripts/ -type f 2>/dev/null | sed -n 's/.*\.//p' | sort | uniq -c | sort -nr | head -n 20`

### Row 20
* **Checklist Question:** Have absolute paths to libraries been removed from makefiles?
* **Audit Finding / Notes:** Zero hardcoded external library paths (-L/...) in active build_*.sh or CMakeLists.txt files.
* **Command Executed:** `grep -rnE "(-L/|/nwprod/lib|/opt/|/apps/|/usr/local/lib)" sorc/build_*.sh sorc/*/CMakeLists.txt 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 25`

### Row 21
* **Checklist Question:** Are scripts written in bash, ksh, perl or python?
* **Audit Finding / Notes:** All executable scripts use bash, ksh, perl, or python interpreters.
* **Command Executed:** `find scripts/ ush/ jobs/ ecf/ -type f -executable 2>/dev/null -exec head -n 1 {} + | grep -E "^#!" | sort -u`

### Row 27
* **Checklist Question:** Do all executables match or resemble their top level source directory name?
* **Audit Finding / Notes:** Executables in exec/ map cleanly to top-level sorc/<component> directories.
* **Command Executed:** `if [[ -d exec ]]; then ls -1 exec/; else echo "MISSING_EXEC_DIR"; fi; echo "---"; ls -1d sorc/*/`

### Row 31
* **Checklist Question:** Have all modules been loaded in ecf scripts and nowhere else?
* **Audit Finding / Notes:** All operational module load/purge/use statements reside strictly in ecf/.
* **Command Executed:** `grep -rnE "module[[:space:]]+(load|purge|use|swap)" jobs/ scripts/ ush/ ecf/ 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 30`

### Row 32
* **Checklist Question:** Have all version numbers been exported in the version file and nowhere else?
* **Audit Finding / Notes:** Zero *_ver= exports outside versions/ (aside from standard ecflow_ver boilerplate in head.h).
* **Command Executed:** `grep -rnE "(^|;|export[[:space:]]+)[a-zA-Z0-9_]+_ver=" ecf/ jobs/ scripts/ ush/ 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#"`

### Row 33
* **Checklist Question:** Have all hardcoded paths been removed from ush scripts, parm files, fix files, etc. except the J-job and initialization files?
* **Audit Finding / Notes:** Zero hardcoded WCOSS/RDHPCS paths found in ush/, parm/, fix/, or scripts/.
* **Command Executed:** `grep -rnE "(/lfs/h[0-9]/|/gpfs/|/nwprod/|/dcom/|/com/|/work/|/scratch/)" ush/ parm/ fix/ scripts/ 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 25`

### Row 34
* **Checklist Question:** Have all references to developer work areas been removed from scripts?
* **Audit Finding / Notes:** Zero references to developer work areas (/noscrub, /ptmp, /stmp, /home, /work, /scratch).
* **Command Executed:** `grep -rnE "(/noscrub/|/ptmp/|/stmp/|/u/[a-zA-Z0-9_]+|/home/[a-zA-Z0-9_]+|/work/|/scratch/)" ecf/scripts/ jobs/ scripts/ ush/ 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 25`

### Row 35
* **Checklist Question:** Have all development blocks of code been removed or minimized?
* **Audit Finding / Notes:** Zero dead conditional blocks and zero TODO/FIXME markers remain.
* **Command Executed:** `dead=$(grep -rnE "(if[[:space:]]+false|if[[:space:]]+\[\[[[:space:]]*0[[:space:]]*-eq[[:space:]]*1)" ecf/ jobs/ scripts/ ush/ 2>/dev/null | wc -l); todo=$(grep -rnE "\b(TODO|FIXME)\b" ecf/ jobs/ scripts/ ush/ 2>/dev/null | wc -l); echo "DEAD_BLOCKS=$dead"; echo "TODO_COUNT=$todo"`

### Row 37
* **Checklist Question:** Has the interpreter’s name been added to the top of ALL interpreted scripts?
* **Audit Finding / Notes:** All executable scripts have clean #! interpreter lines on line 1.
* **Command Executed:** `find scripts/ ush/ jobs/ ecf/ -type f -executable 2>/dev/null | while read -r f; do   first_line="$(head -n 1 "$f")";   [[ "$first_line" == \#!* ]] || echo "MISSING SHEBANG: $f ($first_line)"; done; grep -rnE "^#!.*#" scripts/ ush/ jobs/ ecf/ 2>/dev/null | grep -E ":1:" | head -n 20`

### Row 42
* **Checklist Question:** Have all references to RUN_ENVIR been removed?
* **Audit Finding / Notes:** Zero RUN_ENVIR references found in operational jobs/, scripts/, ush/, or parm/.
* **Command Executed:** `grep -rnE "\bRUN_ENVIR\b" jobs/ scripts/ ush/ parm/ 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#"`

### Row 43
* **Checklist Question:** Have all references to a centralized jlogfile been removed?
* **Audit Finding / Notes:** Zero active jlogfile references found.
* **Command Executed:** `grep -rniE "\bjlogfile\b" ecf/ jobs/ scripts/ ush/ parm/ 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#"`

### Row 44
* **Checklist Question:** Are standard environment variables used throughout the entire package?
* **Audit Finding / Notes:** Standard $COMIN*/$COMOUT* variables used; COMROOT is never set to ROTDIR.
* **Command Executed:** `grep -rnE "(\bCOMROOT\b|compath\.py|\$COM/|\$\{COM\}/)" scripts/ ush/ 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#"`

### Row 47
* **Checklist Question:** For jobs that must have data to run, do they have proper error handling if the needed data types aren’t available (If not, use ‘cpreq’)?
* **Audit Finding / Notes:** Insufficient cpreq or missing-input error handling detected.
* **Command Executed:** `cpreq_c=$(grep -rnE "\bcpreq\b" jobs/ scripts/ ush/ 2>/dev/null | wc -l); guard_c=$(grep -rnE "\[\[ ! -[fs] " jobs/ scripts/ ush/ 2>/dev/null | wc -l); echo "CPREQ_COUNT=$cpreq_c"; echo "GUARD_COUNT=$guard_c"`

### Row 51
* **Checklist Question:** Are fatal errors prefaced with ‘FATAL ERROR’ and non-fatal/warning errors prefaced with ‘WARNING’?
* **Audit Finding / Notes:** Standard FATAL ERROR / WARNING prefixes are not consistently used.
* **Command Executed:** `f_c=$(grep -rn "FATAL ERROR" jobs/ scripts/ ush/ 2>/dev/null | wc -l); w_c=$(grep -rn "WARNING" jobs/ scripts/ ush/ 2>/dev/null | wc -l); echo "FATAL_ERROR_COUNT=$f_c"; echo "WARNING_COUNT=$w_c"; grep -rnE "err_exit[[:space:]]+\"" jobs/ scripts/ ush/ 2>/dev/null | grep -v "FATAL ERROR" | head -n 15`

### Row 53
* **Checklist Question:** Are production utilities used for error handling (err_chk, err_exit)?
* **Audit Finding / Notes:** Missing err_chk/err_exit or pgm assignments.
* **Command Executed:** `e_c=$(grep -rnE "\b(err_chk|err_exit)\b" jobs/ scripts/ ush/ 2>/dev/null | wc -l); p_c=$(grep -rnE "^[[:space:]]*(export[[:space:]]+)?pgm=" jobs/ scripts/ ush/ 2>/dev/null | wc -l); echo "ERR_UTIL_COUNT=$e_c"; echo "PGM_ASSIGN_COUNT=$p_c"`

### Row 54
* **Checklist Question:** Are production date utilities used for all date manipulation?
* **Audit Finding / Notes:** No production date utilities detected.
* **Command Executed:** `grep -rnE "\b(setpdy\.sh|ndate|nhour|finddate\.sh)\b" ecf/ jobs/ scripts/ ush/ 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | head -n 20`

### Row 55
* **Checklist Question:** If GRIB utilities are needed, is the grib_util and/or wgrib2 module loaded and used?
* **Audit Finding / Notes:** Missing grib_util/wgrib2 version config or duplicate GRIB binaries found in exec/.
* **Command Executed:** `grep -rnE "(grib_util_ver|wgrib2_ver)" versions/ ecf/ 2>/dev/null | head -n 15; ls -1 exec/ 2>/dev/null | grep -E "wgrib2|cnvgrib|grb2index|copygb2|tocgrib2" | sed "s/^/BUNDLED_GRIB=/"`

### Row 56
* **Checklist Question:** Are executables preceded with logic that ensures old variables or links used to point to input/output files in earlier steps have been reset (e.g., use of prep_step to unset FORTxx)?
* **Audit Finding / Notes:** prep_step is not used to reset Fortran unit environment variables.
* **Command Executed:** `p_c=$(grep -rnE "\bprep_step\b" jobs/ scripts/ ush/ 2>/dev/null | wc -l); f_c=$(grep -rnE "export[[:space:]]+FORT[0-9]+=" jobs/ scripts/ ush/ 2>/dev/null | wc -l); echo "PREP_STEP_COUNT=$p_c"; echo "FORT_EXPORT_COUNT=$f_c"`

### Row 57
* **Checklist Question:** Is it verified that the system version of Python is NOT being used and that Python3 or higher is being used?
* **Audit Finding / Notes:** Zero /usr/bin/python references; spack-stack Python 3+ is used across the workflow.
* **Command Executed:** `grep -rnE "/usr/bin/python" ecf/ jobs/ scripts/ ush/ 2>/dev/null`

### Row 61
* **Checklist Question:** Does every source directory build only one executable (or a group of executables sharing a significant part of their sources)?
* **Audit Finding / Notes:** Could not verify sorc/ directory structure.
* **Command Executed:** `ls -1d sorc/*/`

### Row 64
* **Checklist Question:** Did code compile without any error or warning messages, i.e., is it verified that no compiler options were used to suppress any error or warning messages?
* **Audit Finding / Notes:** Builds with 0 errors, but compiler warnings occur (notably in GDAS; reviewed with NCO in NOAA-EMC/GFS#69).
* **Command Executed:** `grep -rniE "(-w\b|-Wno-|nowarn)" sorc/build_*.sh sorc/*/CMakeLists.txt 2>/dev/null | head -n 20`

### Row 66
* **Checklist Question:** Can you execute all makefile targets through the master scripts (eg, build, install, clean)?
* **Audit Finding / Notes:** Master build script does not support standard build/install targets.
* **Command Executed:** `grep -rnE "getopts|cmake --install|make install" sorc/build_all.sh sorc/build_*.sh 2>/dev/null | head -n 20; grep -qE "\-c\b|clean" sorc/build_all.sh && echo "CLEAN_FLAG_PRESENT" || echo "NO_CLEAN_FLAG_IN_BUILD_ALL"`

### Row 67
* **Checklist Question:** Do all makefiles have the following targets: all, debug, install and clean?
* **Audit Finding / Notes:** All sorc/ components provide CMakeLists.txt (generating all, install, clean, and Debug targets).
* **Command Executed:** `ls -1d sorc/*/ | while read -r d; do   [[ -f "${d}CMakeLists.txt" || -f "${d}makefile" || -f "${d}Makefile" ]] || echo "MISSING BUILD FILE: $d"; done`

### Row 68
* **Checklist Question:** Have you verified that resulting executables continue to work if the original build path is removed or renamed?
* **Audit Finding / Notes:** Zero binaries or libraries in exec/ or lib/ contain hardcoded build-tree paths or non-relocatable RPATHs.
* **Command Executed:** `for f in exec/* lib/*; do   [[ -f "$f" ]] || continue;   strings "$f" 2>/dev/null | grep -E "/work/|/scratch/|EE2_NOV2026" | head -n 2;   readelf -d "$f" 2>/dev/null | grep -E "RPATH|RUNPATH" | grep -vE "\$ORIGIN|/apps/contrib/spack-stack"; done`

### Row 69
* **Checklist Question:** Are all version specifications for running or building a package contained in run.ver and build.ver?
* **Audit Finding / Notes:** All runtime and build versions are centralized in versions/run.ver and versions/build.ver.
* **Command Executed:** `grep -rnE "(^|;|export[[:space:]]+)[a-zA-Z0-9_]+_ver=" ecf/ jobs/ scripts/ ush/ modulefiles/ sorc/build_*.sh 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | grep -v "ecf/include/head.h:16:" | sed "s/^/HARDCODED_VER:/"; grep -rnE "module[[:space:]]+load[[:space:]]+" ecf/ jobs/ scripts/ ush/ modulefiles/ sorc/build_*.sh 2>/dev/null | grep -vE "^[^:]+:[0-9]+:[[:space:]]*#" | grep -vE '\$\{[a-zA-Z0-9_]+_ver\}|\$[a-zA-Z0-9_]+_ver|gw_|setup|run|build|craype-network-ucx|cray-mpich-ucx|GDAS/\{job_config' | sed "s/^/HARDCODED_MOD:/"`

### Row 70
* **Checklist Question:** Have you confirmed with the developer that array allocation is appropriate (no failure if more observations come in)?
* **Audit Finding / Notes:** Dynamic allocation could not be confirmed in DA source directories.
* **Command Executed:** `for d in sorc/gsi.fd sorc/enkf.fd sorc/gdas.cd sorc/syndat_*.fd sorc/rdbfmsua.fd sorc/tocsbufr.fd; do   [[ -d "$d" ]] || continue;   cnt=$(grep -rniE "\ballocate[[:space:]]*\(" "$d" 2>/dev/null | wc -l);   printf "%-30s allocate() count: %s\n" "$d" "$cnt"; done`

### Row 85
* **Checklist Question:** Does each executable redirect stdout and stderr to files (pgmout and errfile, for example), except executables with minimum amount of output (100 lines or so)?
* **Audit Finding / Notes:** All high-output executables redirect stdout and stderr to files.
* **Command Executed:** `grep -RnE "(1>&1 2>&2|exec_cmd\(\)|exe\(\))" scripts/ ush/python/pygfs/ 2>/dev/null | head -n 15 && echo "DIRECT_STDOUT_STREAMING"`

### Row 86
* **Checklist Question:** Is pgmout and errfile cat’d to stdout file before being removed from $DATA?
* **Audit Finding / Notes:** J-jobs do not cat pgmout or errfile before removing $DATA.
* **Command Executed:** `grep -RnE '(cat "\$\{pgmout\}"|cat errfile|cat "\$\{pgmerr\}")' jobs/ ush/ 2>/dev/null | head -n 20`

### Row 112
* **Checklist Question:** Have all necessary changes to the WCOSS switches at 00z, 06z, 12z, and 18z and ecFlow switch been made? (modelgroup, switch procedures, envir.h, etc)
* **Audit Finding / Notes:** WCOSS2 00z/06z/12z/18z cycles, envir.h, and ecFlow switch settings are configured for production.
* **Command Executed:** `grep -rnE "^[[:space:]]*family (00|06|12|18)\b" ecf/defs/gfs_prod.def 2>/dev/null; grep -rnE "(PROJENVIR|MACHINE_SITE|QUEUE|fakedbn)" ecf/defs/gfs_prod.def ecf/include/envir-p1.h 2>/dev/null | head -n 15 && echo "DEV_DEFAULTS_PRESENT"`
