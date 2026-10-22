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

# MRMS runs (obs_expansion.md Sec. 8.4): the run's observation set has MRMS; MRMS_FILTER (experiment.sh)
# says how filter takes it: two_pass (conventional, then MRMS) or one_pass (both in one filter, obs_seq.joint).
has_mrms() { grep -q ' mrms=' "${OBS_DIR}/obs_settings.txt" 2> /dev/null; }
two_pass() { has_mrms && [ "${MRMS_FILTER}" = two_pass ]; }
one_pass_mrms() { has_mrms && [ "${MRMS_FILTER}" = one_pass ]; }

# Fields the DART-facing file carries besides wrfrst_dart.py's own (filter's hydrometeor and
# REFL_10CM state, QNRAIN for wrfrst_dart.py qnrain).
DART_EXTRA="QCLOUD QRAIN QSNOW QGRAUP REFL_10CM QNRAIN"

# recently_changed <seconds> <files...>: prints the first existing file modified within <seconds>
recently_changed() {
   local age=$1 f now
   shift
   now=$(date +%s)
   for f in "$@"; do
      if [ -e "${f}" ] && [ $((now - $(stat -c %Y "${f}"))) -lt "${age}" ]; then echo "${f}"; return; fi
   done
}

# run_filter <dir> <srun options...>: filter (DART_WORK/filter) as one srun step in <dir>, output in
# <dir>/filter.log; returns 0 if filter finished ("Finished ... at" in filter.log), 1 otherwise.
# hcoll off (OMPI_MCA_coll_hcoll_enable=0): with it, filter on 40 x 32 often hung after "Finished": one
# node-leader rank never finished closing hcoll's UCX connections in MPI_Finalize (hcoll_context_free ->
# hmca_bcol_ucx_p2p_disconnect) and all others waited in the last fence. hcoll off: no hang in 11 runs,
# analyses bit-identical, step as fast (notes/filter_exit_hang.md, 2026-10-21).
# Exit guard, kept as a safety net: once "Finished" is in the log, the step gets FILTER_EXIT_GRACE s
# (default 30; a normal exit takes ~1 s) to exit; if it hasn't, and no output file in <dir> or in
# output_list_d01.txt has changed for 30 s, the step is cancelled (scancel; srun killed 60 s later if
# still there) and the run counts as finished. Each firing is logged ("filter exit guard: ...") and
# leaves <dir>/filter_exit_guard.txt.
run_filter() {
   local dir=$1; shift
   local grace=${FILTER_EXIT_GRACE:-30} pid rc t_fin= t_cancel= step busy
   rm -f "${dir}/filter_exit_guard.txt"
   (cd "${dir}" && exec env OMPI_MCA_coll_hcoll_enable=0 srun "$@" "${DART_WORK}/filter" > filter.log 2>&1) &
   pid=$!
   while kill -0 "${pid}" 2> /dev/null; do
      if [ -z "${t_fin}" ]; then
         ! grep -q 'Finished \.\.\. at' "${dir}/filter.log" 2> /dev/null || t_fin=${SECONDS}
      elif [ -z "${t_cancel}" ] && [ $((SECONDS - t_fin)) -ge "${grace}" ]; then
         busy=$(recently_changed 30 "${dir}"/*.nc $(cat "${dir}/output_list_d01.txt" 2> /dev/null))
         if [ -z "${busy}" ]; then
            step=$(squeue -h -s -j "${SLURM_JOB_ID}" -o '%i %j' | awk '$2 == "filter" {print $1}' | head -n 1)
            log "filter exit guard: filter still running $((SECONDS - t_fin)) s after 'Finished' in ${dir}/filter.log; cancelling step ${step:-(not found, killing srun)}"
            echo "$(date -u +%Y-%m-%dT%H:%M:%S) step ${step:-?} cancelled $((SECONDS - t_fin)) s after Finished" \
               > "${dir}/filter_exit_guard.txt"
            if [ -n "${step}" ]; then
               scancel "${step}"
            else
               kill -INT "${pid}" 2> /dev/null; sleep 0.5; kill -INT "${pid}" 2> /dev/null || true
            fi
            t_cancel=${SECONDS}
         fi
      elif [ -n "${t_cancel}" ] && [ $((SECONDS - t_cancel)) -ge 60 ]; then
         kill -KILL "${pid}" 2> /dev/null || true
      fi
      sleep 2
   done
   rc=0
   wait "${pid}" || rc=$?
   grep -q 'Finished \.\.\. at' "${dir}/filter.log" || return 1
   [ "${rc}" -eq 0 ] || [ -n "${t_cancel}" ] || return 1
   return 0
}
