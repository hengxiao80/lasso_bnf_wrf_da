#!/bin/bash
# One cycle at <t> (pilot step 12): [filter at t, if t > FIRST_CYCLE] + advance t -> t + 15 min.
# Runs inside the cycling allocation (driver.sh calls it once per cycle).
#
# Usage: cycle_job.sh <experiment.sh> <YYYYMMDDHHMM>
#
# Stages and their markers in output/<t>/ (a rerun skips what is marked done):
#   filter.done          prep_filter.sh, filter (FILTER_NODES x FILTER_TASKS_PER_NODE ranks),
#                        post_filter.sh save. Before this marker the restart files are untouched,
#                        so the whole stage is simply rerun.
#   memNNN/update.done   post_filter.sh member: analysis into the restart file, boundary refit
#   memNNN/advance.done  advance_member.sh: the 15-min segment, all members concurrently
#   status = complete    check_cycle.py passed (output/<t>/check_cycle.log)
# A member failure stops the cycle; a member is never replaced by a copy of another.
set -eu

exp_sh=$1 t=$2
source "${exp_sh}"
source "$(dirname "$(readlink -f "$0")")/cycle_lib.sh"
PY=${PROJECT_DIR}/.venv/bin/python
DA=${PROJECT_DIR}/scripts/da
out=${OUTPUT_DIR}/${t}
mkdir -p "${out}"

if grep -qx complete "${out}/status" 2> /dev/null; then
   log "cycle ${t}: already complete"; exit 0
fi
echo running > "${out}/status"
SECONDS=0

# --- analysis -----------------------------------------------------------------------------
if [ "${t}" != "${FIRST_CYCLE}" ]; then
   if [ ! -f "${out}/filter.done" ]; then
      "${DA}/prep_filter.sh" "${exp_sh}" "${t}"
      log "cycle ${t}: filter on $((FILTER_NODES * FILTER_TASKS_PER_NODE)) ranks"
      t0=${SECONDS}
      (cd "${RUN_DIR}/filter" && srun -N "${FILTER_NODES}" -n $((FILTER_NODES * FILTER_TASKS_PER_NODE)) \
         --ntasks-per-node="${FILTER_TASKS_PER_NODE}" -c 1 --exact "${DART_WORK}/filter" > filter.log 2>&1) \
         || die "filter failed at ${t}, see ${RUN_DIR}/filter/filter.log"
      grep -q 'Finished \.\.\. at' "${RUN_DIR}/filter/filter.log" \
         || die "filter did not finish at ${t}, see ${RUN_DIR}/filter/filter.log"
      log "cycle ${t}: filter done in $((SECONDS - t0)) s"
      "${DA}/post_filter.sh" "${exp_sh}" "${t}" save
      touch "${out}/filter.done"
   fi
   "${DA}/post_filter.sh" "${exp_sh}" "${t}" members
   log "cycle ${t}: members updated"
fi

# --- advance --------------------------------------------------------------------------------
pids=()
for m in $(members); do
   [ ! -f "${out}/mem${m}/advance.done" ] || continue
   "${DA}/advance_member.sh" "${exp_sh}" "${t}" "${m}" &
   pids+=($!)
done
[ ${#pids[@]} -eq 0 ] || wait_all "${pids[@]}" || die "advance failed at ${t}"
log "cycle ${t}: members advanced"

# --- checks ---------------------------------------------------------------------------------
"${PY}" "${DA}/check_cycle.py" "${out}" --nmem "${NUM_ENS}" > "${out}/check_cycle.log" 2>&1 \
   || { cat "${out}/check_cycle.log"; die "check_cycle.py failed at ${t}"; }
echo complete > "${out}/status"
log "cycle ${t}: complete in ${SECONDS} s"
