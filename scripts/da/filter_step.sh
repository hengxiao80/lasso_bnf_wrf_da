#!/bin/bash
# The filter job's work in a chained cycling run (50-member full test, notes/fulltest_steps.md B2); run by
# slurm.filter_step, which chain_submit.sh submits.
#
# Usage: filter_step.sh <experiment.sh> <t YYYYMMDDHHMM> <last YYYYMMDDHHMM>
#
# 1. Cycle p = t - CYCLE_MINUTES (its WRF array has ended): every member advanced (output/<p>/memNNN/advance.done)?
#    If not, one automatic retry per cycle (user, 2026-11-08), counted in output/<p>/retries: the first time,
#    chain_submit.sh submits the WRF tasks of the members missing and a new filter job F(t) after them, and this
#    job ends; the second time, the chain stops.
# 2. check_cycle.py on output/<p> in the background (it reads every member's prior and analysis; skipped if p is
#    already complete), so that it overlaps the extraction and filter below.
# 3. If t <= last: the analysis at t as cycle_job.sh does it (filter_pass, cycle_lib.sh; filter.done), then the
#    check's result (passed: output/<p>/status = complete; failed: stop, before any restart file at t is changed),
#    then post_filter.sh members (insert, boundary refit; update.done), then chain_submit.sh for the next step
#    (A(t), then F(t + 15)), with this job as A(t)'s afterok dependency.
#    If t > last (the run's last job): only the check's result; nothing more is submitted.
# A failure stops the chain (nothing further is submitted); chain_submit.sh with the run's arguments resumes it
# from the markers. CHAIN_DRY_RUN=1 (tests on the login node): chain_submit.sh is called with --dry-run.
set -eu

exp_sh=$(readlink -f "$1") t=$2 last=$3
source "${exp_sh}"
source "$(dirname "$(readlink -f "$0")")/cycle_lib.sh"
PY=${PROJECT_DIR}/.venv/bin/python
DA=${PROJECT_DIR}/scripts/da
p=$(add_minutes "${t}" -"${CYCLE_MINUTES}")
op=${OUTPUT_DIR}/${p}
dryopt=()
[ "${CHAIN_DRY_RUN:-0}" != 1 ] || dryopt=(--dry-run)
log "filter step ${t} (run '${RUN_NAME}', last ${last}, job ${SLURM_JOB_ID:-none} on ${SLURM_JOB_NUM_NODES:-?} nodes)"

# --- 1-2. the previous cycle ------------------------------------------------------------------------------------
cpid=
if ! grep -qx complete "${op}/status" 2> /dev/null; then
   missing=()
   for m in $(members); do [ -f "${op}/mem${m}/advance.done" ] || missing+=("${m}"); done
   if [ ${#missing[@]} -gt 0 ]; then
      n=$(cat "${op}/retries" 2> /dev/null || echo 0)
      [ "${n}" -lt 1 ] || die "cycle ${p}: ${#missing[@]} members not advanced after a retry: ${missing[*]}"
      echo $((n + 1)) > "${op}/retries"
      log "cycle ${p}: ${#missing[@]} members not advanced (${missing[*]}); automatic retry $((n + 1))"
      "${DA}/chain_submit.sh" "${exp_sh}" "${p}" "${last}" --after "${SLURM_JOB_ID}" "${dryopt[@]}"
      exit 0
   fi
   log "cycle ${p}: all ${NUM_ENS} members advanced; check_cycle.py in the background"
   "${PY}" "${DA}/check_cycle.py" "${op}" --nmem "${NUM_ENS}" > "${op}/check_cycle.log" 2>&1 &
   cpid=$!
fi

# finish_check: the check's result for cycle p
finish_check() {
   local t0=${SECONDS}
   [ -n "${cpid}" ] || return 0
   if wait "${cpid}"; then
      echo complete > "${op}/status"
      log "cycle ${p}: complete (check_cycle.py passed; waited ${t0} -> ${SECONDS} s into the step)"
   else
      tail -n 40 "${op}/check_cycle.log"
      die "check_cycle.py failed for cycle ${p}, see ${op}/check_cycle.log"
   fi
}

if [ "${t}" -gt "${last}" ]; then
   finish_check
   log "run '${RUN_NAME}': cycle ${last} was the last one; nothing more to submit"
   exit 0
fi

# --- 3. the analysis at t -----------------------------------------------------------------------------------------
out=${OUTPUT_DIR}/${t}
mkdir -p "${out}"
! grep -qx complete "${out}/status" 2> /dev/null || die "cycle ${t} is already complete"
echo running > "${out}/status"
SECONDS=0
if [ ! -f "${out}/filter.done" ]; then
   filter_pass "${exp_sh}" "${t}" conv
   if two_pass; then filter_pass "${exp_sh}" "${t}" mrms; fi
   touch "${out}/filter.done"
fi
finish_check
"${DA}/post_filter.sh" "${exp_sh}" "${t}" members
log "cycle ${t}: members updated"
"${DA}/chain_submit.sh" "${exp_sh}" "${t}" "${last}" --after "${SLURM_JOB_ID}" "${dryopt[@]}"
log "cycle ${t}: filter step done in ${SECONDS} s"
