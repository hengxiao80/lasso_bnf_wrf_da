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

# filter_pass <experiment.sh> <YYYYMMDDHHMM> <conv|mrms>: one filter pass at t: prep_filter.sh, filter on
# FILTER_NODES x FILTER_TASKS_PER_NODE ranks (run_filter), post_filter.sh save; conv in run/filter, mrms (the
# second pass of a two-pass run) in run/filter_mrms. Used by cycle_job.sh (5-member runs) and filter_step.sh
# (50-member chain); moved here from cycle_job.sh on 2026-11-08, unchanged.
filter_pass() {
   local exp_sh=$1 t=$2 pass=$3 dir=${RUN_DIR}/filter t0=${SECONDS}
   [ "${pass}" = conv ] || dir=${RUN_DIR}/filter_mrms
   "${PROJECT_DIR}/scripts/da/prep_filter.sh" "${exp_sh}" "${t}" "${pass}"
   log "cycle ${t}: filter (${pass}) on $((FILTER_NODES * FILTER_TASKS_PER_NODE)) ranks"
   # run_filter: fails unless filter.log has "Finished ... at"; exit guard for a hang
   run_filter "${dir}" -N "${FILTER_NODES}" -n $((FILTER_NODES * FILTER_TASKS_PER_NODE)) \
      --ntasks-per-node="${FILTER_TASKS_PER_NODE}" -c 1 --exact \
      || die "filter (${pass}) failed or did not finish at ${t}, see ${dir}/filter.log"
   log "cycle ${t}: filter (${pass}) done in $((SECONDS - t0)) s"
   "${PROJECT_DIR}/scripts/da/post_filter.sh" "${exp_sh}" "${t}" save "${pass}"
}

# run_preflight <first> <last> [write]: the checks made before a run of cycles <first> to <last> starts or
# resumes (driver.sh, chain_submit.sh; moved here from driver.sh on 2026-11-08, unchanged): every analysis time
# has its observation files; the cycle before <first> is complete; one HYDROSTATIC_PH, INF_DAMPING, INF_FLAVOR,
# INF_SD_LOWER_BOUND, observation set and MRMS handling per run, recorded in output/settings.txt on the first
# call (write = 1, the default; 0 only compares, for dry runs) and compared on every later one.
run_preflight() {
   local first=$1 last=$2 write=${3:-1} t f prev settings
   [ "${first}" -le "${last}" ] || die "first ${first} after last ${last}"
   [ "${first}" -ge "${FIRST_CYCLE}" ] || die "first ${first} before FIRST_CYCLE ${FIRST_CYCLE}"
   t=${first}
   while [ "${t}" -le "${last}" ]; do
      if [ "${t}" != "${FIRST_CYCLE}" ] && [ ! -s "${OBS_DIR}/${t}/obs_seq.out" ]; then
         die "no ${OBS_DIR}/${t}/obs_seq.out (make_cycle_obs.sh ${t})"
      fi
      f=
      two_pass && f=obs_seq.mrms
      one_pass_mrms && f=obs_seq.joint
      if [ "${t}" != "${FIRST_CYCLE}" ] && [ -n "${f}" ] && [ ! -s "${OBS_DIR}/${t}/${f}" ]; then
         die "no ${OBS_DIR}/${t}/${f} (make_cycle_obs.sh ${t} with MRMS set)"
      fi
      t=$(add_minutes "${t}" "${CYCLE_MINUTES}")
   done
   if [ "${first}" != "${FIRST_CYCLE}" ]; then
      prev=$(add_minutes "${first}" -"${CYCLE_MINUTES}")
      grep -qx complete "${OUTPUT_DIR}/${prev}/status" 2> /dev/null || die "cycle ${prev} not complete"
   fi
   # One HYDROSTATIC_PH, INF_DAMPING, INF_FLAVOR, INF_SD_LOWER_BOUND and observation set per run: a resume
   # with other values would mix them in one run. The observation set (OBS_NAME) is recorded only when it
   # isn't the step 13 obs/, so the step 13 runs keep their settings line.
   settings="hydrostatic_ph=${HYDROSTATIC_PH} inf_damping=${INF_DAMPING} inf_flavor=${INF_FLAVOR}"
   # INF_SD_LOWER_BOUND: 0 < value <= 0.6 (the initial sd); recorded only when not 0.6, so older runs keep
   # their settings line.
   awk -v b="${INF_SD_LOWER_BOUND}" 'BEGIN { exit !(b ~ /^[0-9]*\.?[0-9]+$/ && b > 0 && b <= 0.6) }' \
      || die "INF_SD_LOWER_BOUND=${INF_SD_LOWER_BOUND}: must be > 0 and <= 0.6"
   [ "${INF_SD_LOWER_BOUND}" = 0.6 ] || settings="${settings} inf_sd_lower_bound=${INF_SD_LOWER_BOUND}"
   if [ -n "${OBS_NAME}" ]; then
      [ -s "${OBS_DIR}/obs_settings.txt" ] || die "no ${OBS_DIR}/obs_settings.txt (make_cycle_obs.sh)"
      settings="${settings} obs=obs${OBS_NAME} $(cat "${OBS_DIR}/obs_settings.txt")"
   fi
   # MRMS runs: MRMS_FILTER (two_pass | one_pass) has no default and must be given, and so has
   # MRMS_INFLATION (pass1 | both) for two_pass; neither may be set where it doesn't apply.
   if has_mrms; then
      case ${MRMS_FILTER} in
         two_pass|one_pass) settings="${settings} mrms_filter=${MRMS_FILTER}" ;;
         *) die "${OBS_DIR} has MRMS: set MRMS_FILTER=two_pass or one_pass" ;;
      esac
   elif [ -n "${MRMS_FILTER}" ]; then
      die "MRMS_FILTER=${MRMS_FILTER} set, but ${OBS_DIR} has no MRMS"
   fi
   if two_pass; then
      case ${MRMS_INFLATION} in
         pass1) settings="${settings} mrms_inflation=pass1" ;;
         both)
            case ${MRMS_PASS2_DAMPING} in 0|1) ;; *) die "MRMS_PASS2_DAMPING must be 0 or 1" ;; esac
            settings="${settings} mrms_inflation=both mrms_pass2_damping=${MRMS_PASS2_DAMPING}" ;;
         *) die "two-pass run: set MRMS_INFLATION=pass1 or both" ;;
      esac
   elif [ -n "${MRMS_INFLATION}" ]; then
      die "MRMS_INFLATION=${MRMS_INFLATION} set, but this is not a two-pass run"
   fi
   if [ -f "${OUTPUT_DIR}/settings.txt" ]; then
      grep -qx "${settings}" "${OUTPUT_DIR}/settings.txt" \
         || die "${OUTPUT_DIR} was run with $(cat "${OUTPUT_DIR}/settings.txt"), not ${settings}"
   elif [ "${write}" = 1 ]; then
      mkdir -p "${OUTPUT_DIR}"
      echo "${settings}" > "${OUTPUT_DIR}/settings.txt"
   fi
}
