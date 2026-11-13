#!/bin/bash
# Build the observations of a range of analysis times, one time after another, on a login node (A7,
# notes/fulltest_steps.md): per time t, download_mrms.sh t (unless MRMS=none), then make_cycle_obs.sh t.
#
# Usage: OBS_NAME=_x MESONET=<a_calmkeep|...|none> MRMS=<hrrrdas|none> make_obs_loop.sh <first> <last>
#
# <first>, <last>: analysis times YYYYMMDDHHMM, 15-min steps. All three settings must be given (make_cycle_obs.sh
# would otherwise take experiment.sh's), so the loop writes only the set meant. Stops at the first failure.
# Log: a header line (host, PID, range, settings), "=== <t> start HH:MM:SS" per time followed by the two
# scripts' output, and as the last line "LOOP DONE HH:MM:SS" or "LOOP FAILED at <t>"; check_cycle_obs.py
# --loop-log reads these. A7's two loops (then a7_loop.sh, in cases/20250520/obs/logs/) took 31-40 s per time
# with MRMS on cirrus-login1 (2026-11-12; 1.2 GB peak at 01:15). Run it detached, with the log on GPFS
# (~/.claude/rules/cirrus-detached-loops.md):
#   setsid nohup scripts/da/make_obs_loop.sh <first> <last> > cases/20250520/obs/logs/<name>.log 2>&1 < /dev/null &
set -u

[ $# -eq 2 ] || { echo "usage: OBS_NAME=_x MESONET=... MRMS=... make_obs_loop.sh <first> <last>" >&2; exit 1; }
for v in OBS_NAME MESONET MRMS; do
   [ -n "${!v+x}" ] || { echo "make_obs_loop.sh: set ${v}" >&2; exit 1; }
done
export OBS_NAME MESONET MRMS
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "${SCRIPT_DIR}/../.."
source scripts/env_wrf.sh > /dev/null 2>&1
first=$(date -u -d "${1:0:8} ${1:8:2}:${1:10:2}" +%s) || exit 1
last=$(date -u -d "${2:0:8} ${2:8:2}:${2:10:2}" +%s) || exit 1
[ "${first}" -le "${last}" ] || { echo "make_obs_loop.sh: first ${1} after last ${2}" >&2; exit 1; }

echo "obs loop on $(hostname), PID $$, ${1} -> ${2}, OBS_NAME=${OBS_NAME} MESONET=${MESONET} MRMS=${MRMS}"
for (( e = first; e <= last; e += 900 )); do
   t=$(date -u -d "@${e}" +%Y%m%d%H%M)
   echo "=== ${t} start $(date -u +%H:%M:%S)"
   if [ "${MRMS}" != none ]; then
      "${SCRIPT_DIR}/download_mrms.sh" "${t}" || { echo "LOOP FAILED at ${t}"; exit 1; }
   fi
   "${SCRIPT_DIR}/make_cycle_obs.sh" "${t}" || { echo "LOOP FAILED at ${t}"; exit 1; }
done
echo "LOOP DONE $(date -u +%H:%M:%S)"
