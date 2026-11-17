# GFS v17 EE2 Checklist Automated Audit (ee2_audit_report)

Automated command-line verification script and runbook for auditing the NOAA-EMC global-workflow (dev/gfs.v17) repository against NCO End-to-End (EE2) implementation checklist standards.

## Repository Contents

* run_ee2_audit.py - Zero-dependency Python 3 audit script that executes verification commands across 33 EE2 checklist items (Rows 5, 8, 9, 17, 20, 21, 27, 31, 32, 33, 34, 35, 37, 42, 43, 44, 47, 51, 53, 54, 55, 56, 57, 61, 64, 66, 67, 68, 69, 70, 85, 86, and 112), evaluates command outputs against NCO EE2 rules, assigns a tentative status (Yes, Yes-ish, or No), and writes a formatted report (ee2_audit_report.txt).
* .gitignore - Excludes generated audit output (ee2_audit_report*.txt) and Python cache files.

## Prerequisites & Target Repository Setup

1. Clone dev/gfs.v17 (not develop):
       git clone --recursive -b dev/gfs.v17 https://github.com/NOAA-EMC/global-workflow.git EE2_NOV2026
       cd EE2_NOV2026

2. Build operational components (-o):
       cd sorc && ./build_all.sh -o && cd ..

3. Stage the NCO operational directory layout:
       python3 dev/ush/setup_gfs_for_nco.py

## Usage

    python3 run_ee2_audit.py --repo-dir /path/to/EE2_NOV2026 --output ee2_audit_report.txt

* --repo-dir : Path to the top-level global-workflow directory (default: current working directory)
* --output   : Path to write the formatted plain-text audit report (default: ee2_audit_report.txt)
