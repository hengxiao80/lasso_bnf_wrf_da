#!/bin/bash
# Cycle loop (pilot step 12), run inside one allocation (Q7: 40 nodes, slurm.cycle).
#
# Usage: driver.sh <experiment.sh> <first YYYYMMDDHHMM> <last YYYYMMDDHHMM>
#
# Runs cycle_job.sh for every cycle from <first> to <last>, CYCLE_MINUTES apart; the last cycle
# ends with the advance to <last> + 15 min. Resumable: complete cycles (output/<t>/status) are
# skipped and an interrupted cycle continues from its markers, so after a failure or a time-out
# the same job is simply resubmitted. Before starting, checks that every analysis time has its
# obs_seq.out and that the cycle before <first> is complete. Each cycle's log is output/<t>/cycle.log.
set -eu

exp_sh=$(readlink -f "$1") first=$2 last=$3
source "${exp_sh}"
source "$(dirname "$(readlink -f "$0")")/cycle_lib.sh"
DA=${PROJECT_DIR}/scripts/da

[ "${first}" -le "${last}" ] || die "first ${first} after last ${last}"
[ "${first}" -ge "${FIRST_CYCLE}" ] || die "first ${first} before FIRST_CYCLE ${FIRST_CYCLE}"
# The filter layout (experiment.sh) must fit the allocation, checked here rather than at the first analysis.
[ "${FILTER_NODES}" -le "${SLURM_NNODES:-${FILTER_NODES}}" ] \
   || die "FILTER_NODES=${FILTER_NODES} is more than the job's ${SLURM_NNODES} nodes"
[ $((FILTER_TASKS_PER_NODE * 1)) -ge 1 ] && [ "${FILTER_TASKS_PER_NODE}" -le 128 ] \
   || die "FILTER_TASKS_PER_NODE=${FILTER_TASKS_PER_NODE}: must be 1-128"
times=()
t=${first}
while [ "${t}" -le "${last}" ]; do
   times+=("${t}")
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
mkdir -p "${OUTPUT_DIR}"
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
else
   echo "${settings}" > "${OUTPUT_DIR}/settings.txt"
fi

log "driver: run '${RUN_NAME}' (${RUN_DIR}), ${#times[@]} cycles ${first} -> ${last}, ${NUM_ENS} members, filter ${FILTER_NODES}x${FILTER_TASKS_PER_NODE}, hydrostatic_ph=${HYDROSTATIC_PH}, inf_damping=${INF_DAMPING}, inf_flavor=${INF_FLAVOR}, inf_sd_lower_bound=${INF_SD_LOWER_BOUND}, obs ${OBS_DIR}"
for t in "${times[@]}"; do
   mkdir -p "${OUTPUT_DIR}/${t}"
   log "driver: cycle ${t}"
   if ! "${DA}/cycle_job.sh" "${exp_sh}" "${t}" >> "${OUTPUT_DIR}/${t}/cycle.log" 2>&1; then
      tail -n 30 "${OUTPUT_DIR}/${t}/cycle.log"
      die "cycle ${t} failed, see ${OUTPUT_DIR}/${t}/cycle.log"
   fi
   grep -E 'filter( \([a-z]*\))? done|filter exit guard|complete in' "${OUTPUT_DIR}/${t}/cycle.log" | tail -n 4
done
log "driver: done"
