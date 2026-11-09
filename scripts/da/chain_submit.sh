#!/bin/bash
# Start, resume or continue a cycling run as a chain of jobs (50-member full test, notes/fulltest_steps.md B2):
# per cycle a WRF array (slurm.wrf_member: one task per member, advance_member.sh, wrf.exe only) and a filter job
# (slurm.filter_step -> filter_step.sh), which calls this script again for the next step. Login node or job.
#
# Usage: chain_submit.sh <experiment.sh> <first YYYYMMDDHHMM> <last YYYYMMDDHHMM> [--after <jobid>] [--dry-run]
#   e.g. RUN_NAME=_b3 OBS_NAME=_meso_a_calmkeep_mrms MRMS_FILTER=one_pass \
#        scripts/da/chain_submit.sh cases/20250520/da_theta_m0_n50/config/experiment.sh 202505200000 202505200015
#
# Cycle t = the analysis at t (none at FIRST_CYCLE) + the advance t -> t + CYCLE_MINUTES, as for driver.sh; <last>
# is the last analysis, and its advance the run's last segment. Markers in output<RUN>/<t>/, as for cycle_job.sh:
# filter.done, memNNN/update.done, memNNN/advance.done, status (complete once check_cycle.py has passed; the
# filter job of the next cycle runs it).
# First the checks of run_preflight (cycle_lib.sh: observation files, the cycle before <first>, settings.txt), and
# that no job of this run (job names n50f<RUN_NAME>, n50w<RUN_NAME>) is queued or running, other than <jobid>.
# Then, for the first cycle t0 >= <first> that is not complete:
#   every member advanced (only the check is missing):              F(t0 + 15)
#   analysis done (or t0 = FIRST_CYCLE), some members not advanced: A(t0) for those, F(t0 + 15) afterany A(t0)
#   otherwise:                                                       F(t0)
# A(t): the WRF array of cycle t (--array=<members>%MEMBER_MAX, MEMBER_NODES nodes, WRF_TASK_TIME); Slurm output in
# output<RUN>/<t>/memNNN/. F(t): the filter job at t (FILTER_NODES nodes, FILTER_JOB_TIME), Slurm output and
# cycle.log in output<RUN>/<t>/; F(t) for t > <last> is the run's last job: 1 node, it checks cycle <last>, writes
# into output<RUN>/<last>/ and submits nothing.
# --after <jobid>: the first job submitted waits until <jobid> has ended successfully (afterok). The filter job
# passes its own ID, so the WRF tasks start only after it has ended (at most 80 nodes in use at a time).
# --dry-run: prints the sbatch commands instead of submitting them; writes nothing (no settings.txt, no
# directories, no chain.log).
# The run's settings (RUN_NAME, OBS_NAME, MRMS_FILTER, ...) are exported, so every job of the chain has them.
# Each submission is appended to output<RUN>/chain.log.
set -eu

exp_sh=$(readlink -f "$1") first=$2 last=$3
shift 3
after= dry=0
while [ $# -gt 0 ]; do
   case $1 in
      --after) after=$2; shift 2 ;;
      --dry-run) dry=1; shift ;;
      *) echo "chain_submit.sh: unknown option $1" >&2; exit 1 ;;
   esac
done
source "${exp_sh}"
source "$(dirname "$(readlink -f "$0")")/cycle_lib.sh"

# Every chained run is named: an empty RUN_NAME would put the run in run/ and output/ (and, where INIT_DIR is
# run/ as in the 5-member experiment, among the initial members).
[ -n "${RUN_NAME}" ] || die "RUN_NAME is empty: name the run (e.g. RUN_NAME=_d1)"
run_preflight "${first}" "${last}" $((1 - dry))
for v in MEMBER_MAX MEMBER_NODES WRF_TASK_TIME FILTER_JOB_TIME FILTER_NODES; do
   [ -n "${!v:-}" ] || die "${v} not set in ${exp_sh}"
done

name_f=n50f${RUN_NAME}
name_w=n50w${RUN_NAME}
others=$(squeue -h -u "${USER}" -o '%A %j' \
   | awk -v f="${name_f}" -v w="${name_w}" -v me="${after}" '($2 == f || $2 == w) && $1 != me {print $1}' \
   | sort -u | paste -sd' ')
[ -z "${others}" ] || die "jobs of run '${RUN_NAME}' already queued or running: ${others}"

export RUN_NAME OBS_NAME MESONET MRMS MRMS_FILTER MRMS_INFLATION MRMS_PASS2_DAMPING HYDROSTATIC_PH INF_DAMPING \
   INF_FLAVOR INF_SD_LOWER_BOUND FILTER_NODES FILTER_TASKS_PER_NODE

# the first cycle from <first> on that is not complete
t0=
t=${first}
while [ "${t}" -le "${last}" ]; do
   grep -qx complete "${OUTPUT_DIR}/${t}/status" 2> /dev/null || { t0=${t}; break; }
   t=$(add_minutes "${t}" "${CYCLE_MINUTES}")
done
if [ -z "${t0}" ]; then
   log "chain_submit: run '${RUN_NAME}' is complete through ${last}; nothing to submit"
   exit 0
fi
next=$(add_minutes "${t0}" "${CYCLE_MINUTES}")
out=${OUTPUT_DIR}/${t0}
missing=() notupd=()
for m in $(members); do
   [ -f "${out}/mem${m}/advance.done" ] || missing+=("${m}")
   [ -f "${out}/mem${m}/update.done" ] || notupd+=("${m}")
done
if [ ${#missing[@]} -eq 0 ]; then
   step=check
elif [ "${t0}" = "${FIRST_CYCLE}" ] || { [ -f "${out}/filter.done" ] && [ ${#notupd[@]} -eq 0 ]; }; then
   step=advance
else
   step=analysis
fi

# submit <label> <sbatch options and script...>: prints the new job's ID (dry run: DRY_<label>, and the command
# to stderr)
submit() {
   local label=$1
   shift
   if [ "${dry}" = 1 ]; then
      echo "dry-run: sbatch $*" >&2
      echo "DRY_${label}"
   else
      sbatch --parsable "$@"
   fi
}
# submit_f <t> <dependency or empty>: the filter job at t
submit_f() {
   local t=$1 dep=$2 nodes=${FILTER_NODES} tlog=$1 opts=()
   if [ "${t}" -gt "${last}" ]; then
      nodes=1
      tlog=$(add_minutes "${t}" -"${CYCLE_MINUTES}")
   fi
   [ "${dry}" = 1 ] || mkdir -p "${OUTPUT_DIR}/${tlog}"
   [ -z "${dep}" ] || opts=(--dependency="${dep}")
   submit F -J "${name_f}" -N "${nodes}" -t "${FILTER_JOB_TIME}" "${opts[@]}" \
      -o "${OUTPUT_DIR}/${tlog}/slurm.filter_step.%j.out" "${EXP_DIR}/slurm.filter_step" "${t}" "${last}"
}
# submit_a <t> <dependency or empty> <members...>: the WRF array of cycle t for those members
submit_a() {
   local t=$1 dep=$2 list m opts=()
   shift 2
   list=$(printf '%s\n' "$@" | sed 's/^0*//' | paste -sd,)
   if [ "${dry}" = 1 ]; then :; else for m in "$@"; do mkdir -p "${OUTPUT_DIR}/${t}/mem${m}"; done; fi
   [ -z "${dep}" ] || opts=(--dependency="${dep}")
   submit A -J "${name_w}" --array="${list}%${MEMBER_MAX}" -N "${MEMBER_NODES}" -t "${WRF_TASK_TIME}" "${opts[@]}" \
      -o "${OUTPUT_DIR}/${t}/mem%3a/slurm.wrf_member.%A_%a.out" "${EXP_DIR}/slurm.wrf_member" "${t}"
}

dep0=
[ -z "${after}" ] || dep0=afterok:${after}
case ${step} in
check)
   jf=$(submit_f "${next}" "${dep0}")
   msg="F(${next}) ${jf}" ;;
advance)
   ja=$(submit_a "${t0}" "${dep0}" "${missing[@]}")
   jf=$(submit_f "${next}" "afterany:${ja}")
   msg="A(${t0}) ${ja} for ${#missing[@]} members, F(${next}) ${jf}" ;;
analysis)
   jf=$(submit_f "${t0}" "${dep0}")
   msg="F(${t0}) ${jf}" ;;
esac
line="$(date -u +%Y-%m-%dT%H:%M:%S) ${step} at ${t0}: ${msg}$([ -z "${after}" ] || echo ", after ${after}") (run '${RUN_NAME}', ${first} -> ${last})"
if [ "${dry}" = 1 ]; then
   echo "dry-run: ${line}"
else
   echo "${line}" >> "${OUTPUT_DIR}/chain.log"
   echo "${line}"
fi
