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
times=()
t=${first}
while [ "${t}" -le "${last}" ]; do
   times+=("${t}")
   if [ "${t}" != "${FIRST_CYCLE}" ] && [ ! -s "${OBS_DIR}/${t}/obs_seq.out" ]; then
      die "no ${OBS_DIR}/${t}/obs_seq.out (make_cycle_obs.sh ${t})"
   fi
   t=$(add_minutes "${t}" "${CYCLE_MINUTES}")
done
if [ "${first}" != "${FIRST_CYCLE}" ]; then
   prev=$(add_minutes "${first}" -"${CYCLE_MINUTES}")
   grep -qx complete "${OUTPUT_DIR}/${prev}/status" 2> /dev/null || die "cycle ${prev} not complete"
fi

# One HYDROSTATIC_PH, INF_DAMPING, INF_FLAVOR and observation set per run: a resume with other values
# would mix them in one run. The observation set (OBS_NAME) is recorded only when it isn't the step 13 obs/,
# so the step 13 runs keep their settings line.
mkdir -p "${OUTPUT_DIR}"
settings="hydrostatic_ph=${HYDROSTATIC_PH} inf_damping=${INF_DAMPING} inf_flavor=${INF_FLAVOR}"
if [ -n "${OBS_NAME}" ]; then
   [ -s "${OBS_DIR}/obs_settings.txt" ] || die "no ${OBS_DIR}/obs_settings.txt (make_cycle_obs.sh)"
   settings="${settings} obs=obs${OBS_NAME} $(cat "${OBS_DIR}/obs_settings.txt")"
fi
if [ -f "${OUTPUT_DIR}/settings.txt" ]; then
   grep -qx "${settings}" "${OUTPUT_DIR}/settings.txt" \
      || die "${OUTPUT_DIR} was run with $(cat "${OUTPUT_DIR}/settings.txt"), not ${settings}"
else
   echo "${settings}" > "${OUTPUT_DIR}/settings.txt"
fi

log "driver: run '${RUN_NAME}' (${RUN_DIR}), ${#times[@]} cycles ${first} -> ${last}, ${NUM_ENS} members, hydrostatic_ph=${HYDROSTATIC_PH}, inf_damping=${INF_DAMPING}, inf_flavor=${INF_FLAVOR}, obs ${OBS_DIR}"
for t in "${times[@]}"; do
   mkdir -p "${OUTPUT_DIR}/${t}"
   log "driver: cycle ${t}"
   if ! "${DA}/cycle_job.sh" "${exp_sh}" "${t}" >> "${OUTPUT_DIR}/${t}/cycle.log" 2>&1; then
      tail -n 30 "${OUTPUT_DIR}/${t}/cycle.log"
      die "cycle ${t} failed, see ${OUTPUT_DIR}/${t}/cycle.log"
   fi
   grep -E 'filter done|complete in' "${OUTPUT_DIR}/${t}/cycle.log" | tail -n 2
done
log "driver: done"
