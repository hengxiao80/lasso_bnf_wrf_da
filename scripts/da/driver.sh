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

# Checks before starting (run_preflight, cycle_lib.sh; moved there on 2026-11-08): the observation files of
# every analysis time, the cycle before <first>, and one set of run settings (output/settings.txt).
run_preflight "${first}" "${last}"
# The filter layout (experiment.sh) must fit the allocation, checked here rather than at the first analysis.
[ "${FILTER_NODES}" -le "${SLURM_NNODES:-${FILTER_NODES}}" ] \
   || die "FILTER_NODES=${FILTER_NODES} is more than the job's ${SLURM_NNODES} nodes"
[ $((FILTER_TASKS_PER_NODE * 1)) -ge 1 ] && [ "${FILTER_TASKS_PER_NODE}" -le 128 ] \
   || die "FILTER_TASKS_PER_NODE=${FILTER_TASKS_PER_NODE}: must be 1-128"
times=()
t=${first}
while [ "${t}" -le "${last}" ]; do
   times+=("${t}")
   t=$(add_minutes "${t}" "${CYCLE_MINUTES}")
done

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
