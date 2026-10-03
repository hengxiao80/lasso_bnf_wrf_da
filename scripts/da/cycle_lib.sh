#!/bin/bash
# Helpers for the cycling scripts (pilot step 12); sourced after the experiment's experiment.sh.
# Cycle times are YYYYMMDDHHMM throughout.

# YYYYMMDDHHMM -> 2025-05-20_00:15:00 (WRF start time)
wrf_time() { date -u -d "${1:0:8} ${1:8:2}:${1:10:2}" +%Y-%m-%d_%H:%M:%S; }

# YYYYMMDDHHMM -> 2025-05-20_00_15_00 (nocolons file-name time)
file_time() { date -u -d "${1:0:8} ${1:8:2}:${1:10:2}" +%Y-%m-%d_%H_%M_%S; }

# <YYYYMMDDHHMM> <minutes> -> YYYYMMDDHHMM (minutes may be negative)
add_minutes() { date -u -d "${1:0:8} ${1:8:2}:${1:10:2} UTC ${2} minutes" +%Y%m%d%H%M; }

members() { seq -f %03g 1 "${NUM_ENS}"; }

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%S) $*"; }

die() { echo "$(date -u +%Y-%m-%dT%H:%M:%S) ERROR: $*" >&2; exit 1; }

# wait for background jobs given as pids; fail if any failed
wait_all() {
   local pid fail=0
   for pid in "$@"; do wait "${pid}" || fail=1; done
   return ${fail}
}
