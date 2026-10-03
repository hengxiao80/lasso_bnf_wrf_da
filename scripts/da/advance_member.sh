#!/bin/bash
# Advance one member from <t> to <t> + CYCLE_MINUTES (pilot step 12). Runs inside the cycling
# allocation, beside the other members (srun -N MEMBER_NODES --exact).
#
# Usage: advance_member.sh <experiment.sh> <YYYYMMDDHHMM> <NNN>
#
# At FIRST_CYCLE: cold start from INIT_DIR/memNNN/wrfinput_d01 with the pristine bdy/wrfbdy_d01_memNNN
# (built from that same state, so no refit is needed). Afterwards: true restart from
# run/memNNN/wrfrst_d01_<t> (analysis inserted, post_filter.sh) with the refit run/memNNN/bdy/wrfbdy_d01.
# The segment runs in run/memNNN/wrf/ (run_wrf_segment.sh) and writes wrfout and wrfrst at <t> + 15 min.
# Then: wrfout_d01_* and the rank-0 rsl files, namelist.input and the count of CFL lines over all
# ranks go to output/<t>/memNNN/; the new wrfrst moves to run/memNNN/; output/<t>/memNNN/advance.done
# is written; and only then the member's wrfrst at <t> is deleted (Q10: latest wrfrst only).
set -eu

exp_sh=$1 t=$2 m=$3
source "${exp_sh}"
source "$(dirname "$(readlink -f "$0")")/cycle_lib.sh"
DA=${PROJECT_DIR}/scripts/da
md=${RUN_DIR}/mem${m}
mo=${OUTPUT_DIR}/${t}/mem${m}
ft=$(file_time "${t}")
next_ft=$(file_time "$(add_minutes "${t}" "${CYCLE_MINUTES}")")
mkdir -p "${mo}"

if [ "${t}" = "${FIRST_CYCLE}" ]; then
   restart=.false.
   input=${INIT_DIR}/mem${m}/wrfinput_d01
   bdy=${BDY_DIR}/wrfbdy_d01_mem${m}
else
   [ -f "${mo}/update.done" ] || die "member ${m}: no ${mo}/update.done"
   restart=.true.
   input=${md}/wrfrst_d01_${ft}
   bdy=${md}/bdy/wrfbdy_d01
fi
[ -f "${input}" ] || die "member ${m}: no ${input}"

rm -f "${md}"/wrf/wrfout_d01_* "${md}"/wrf/wrfrst_d01_*
SRUN_OPTS="-N ${MEMBER_NODES} --ntasks-per-node=$((NPROC_X * NPROC_Y / MEMBER_NODES)) -c ${OMP_NUM_THREADS} --exact" RESTART=${restart} \
   RESTART_INTERVAL=${CYCLE_MINUTES} "${DA}/run_wrf_segment.sh" "${exp_sh}" "${md}/wrf" \
   "$(wrf_time "${t}")" $((CYCLE_MINUTES * 60)) "${input}" "${bdy}" "${NPROC_X}" "${NPROC_Y}" \
   || die "member ${m}: wrf.exe failed at ${t}, see ${md}/wrf/rsl.error.*"
[ -f "${md}/wrf/wrfrst_d01_${next_ft}" ] || die "member ${m}: no wrfrst_d01_${next_ft}"

cd "${md}/wrf"
mv wrfout_d01_* "${mo}/"
cp rsl.out.0000 rsl.error.0000 namelist.input "${mo}/"
{ grep -il cfl rsl.error.* | wc -l; grep -ih cfl rsl.error.* | wc -l; } | paste -sd' ' \
   | awk '{print "ranks with cfl lines:", $1, " cfl lines:", $2}' > "${mo}/cfl_count.txt"
mv "wrfrst_d01_${next_ft}" "${md}/"
touch "${mo}/advance.done"
[ "${t}" = "${FIRST_CYCLE}" ] || rm -f "${md}/wrfrst_d01_${ft}"
log "advance ${t}: member ${m} done ($(cat "${mo}/cfl_count.txt"))"
