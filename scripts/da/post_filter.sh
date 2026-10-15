#!/bin/bash
# After filter at <t> (pilot step 12). Runs inside the cycling allocation.
#
# Usage: post_filter.sh <experiment.sh> <YYYYMMDDHHMM> save [conv|mrms]
#        post_filter.sh <experiment.sh> <YYYYMMDDHHMM> members
#        post_filter.sh <experiment.sh> <YYYYMMDDHHMM> member <NNN>   (one member; members calls it)
#
# save: moves filter's outputs from run/filter/ to output/<t>/filter/: input.nml, filter.log,
#   dart_log.*, obs_seq.final, the stage files (input/preassim/postassim/output mean, sd, members)
#   and the inflation files. postassim_priorinf_{mean,sd}.nc is the next cycle's prior inflation.
#   save mrms: the same from run/filter_mrms/ to output/<t>/filter_mrms/ (two-pass runs); a pass
#   without inflation (MRMS_INFLATION = pass1) has no inflation files.
# members: for each member without output/<t>/memNNN/update.done, one one-node srun step running
#   member mode; all concurrently.
# member: for member NNN
#   1. save filter's in-place output run/memNNN/dart_d01.nc as output/<t>/memNNN/analysis_d01.nc
#      (its T is still the prior THM: T is not in the DART state);
#   1b. MRMS runs (one or two passes): wrfrst_dart.py qnrain sets QNRAIN where the analysis changed
#      QRAIN (Thompson's 1-mm rule), in run/memNNN/dart_d01.nc, before it is saved;
#   2. wrfrst_dart.py insert the UPDATE fields (U V PH THM MU QVAPOR QCLOUD; MRMS runs also
#      QRAIN QSNOW QGRAUP and QNRAIN) into run/memNNN/wrfrst_d01_<t>,
#      recomputing AL, ALT, P, P_HYD and T = THM; with HYDROSTATIC_PH=1 the PH increment is the
#      hydrostatic one, from the saved prior (--prior), so a rerun gives the same file;
#   3. extract the updated restart file again into run/memNNN/start_d01.nc: the state WRF starts
#      from, which update_wrf_bc reads (its T_B comes from T, which filter leaves at the prior THM;
#      with HYDROSTATIC_PH=1 also PH differs from filter's output);
#   4. refit_member_bdy.sh: fresh copy of bdy/wrfbdy_d01_memNNN, refit to that state in
#      run/memNNN/bdy/; the refit file and its log are saved in output/<t>/memNNN/;
#   5. touch output/<t>/memNNN/update.done.
# Step 2 changes the restart file, so the cycle never goes back to prep_filter once a member has
# started here (cycle_job.sh: filter.done).
set -eu

exp_sh=$1 t=$2 mode=$3
source "${exp_sh}"
source "$(dirname "$(readlink -f "$0")")/cycle_lib.sh"
PY=${PROJECT_DIR}/.venv/bin/python
DA=${PROJECT_DIR}/scripts/da
out=${OUTPUT_DIR}/${t}
fdir=${RUN_DIR}/filter
ft=$(file_time "${t}")

case ${mode} in
save)
   case ${4:-conv} in
      conv) sdir=filter ;;
      mrms) sdir=filter_mrms ;;
      *) die "post_filter.sh save: unknown pass $4" ;;
   esac
   fdir=${RUN_DIR}/${sdir}
   mkdir -p "${out}/${sdir}"
   cd "${fdir}"
   [ -f obs_seq.final ] || die "no ${fdir}/obs_seq.final"
   mv input.nml filter.log dart_log.out dart_log.nml obs_seq.final \
      input_{mean,sd}.nc {preassim,postassim}_{mean,sd}.nc {preassim,postassim}_member_*.nc \
      output_{mean,sd}.nc "${out}/${sdir}/"
   if [ -f input_priorinf_mean.nc ]; then
      mv input_priorinf_{mean,sd}.nc {preassim,postassim,output}_priorinf_{mean,sd}.nc "${out}/${sdir}/"
   fi
   [ ! -f fill_inflation.log ] || mv fill_inflation.log "${out}/${sdir}/"
   readlink obs_seq.out > "${out}/${sdir}/obs_seq.out.path"
   log "post_filter ${t}: filter outputs saved in ${out}/${sdir}"
   ;;
members)
   pids=()
   for m in $(members); do
      [ ! -f "${out}/mem${m}/update.done" ] || continue
      srun -N 1 -n 1 -c 8 --exact "$0" "${exp_sh}" "${t}" member "${m}" &
      pids+=($!)
   done
   [ ${#pids[@]} -eq 0 ] || wait_all "${pids[@]}" || die "member update failed at ${t}"
   ;;
member)
   m=$4
   md=${RUN_DIR}/mem${m}
   mo=${out}/mem${m}
   rst=${md}/wrfrst_d01_${ft}
   mkdir -p "${mo}"
   fields=(U V PH THM MU QVAPOR QCLOUD)
   : > "${mo}/insert.log"
   if has_mrms; then
      fields+=(QRAIN QSNOW QGRAUP QNRAIN)
      # QNRAIN from the analysed QRAIN (compared with the saved prior), so a rerun gives the same file
      ${PY} "${DA}/wrfrst_dart.py" qnrain "${md}/dart_d01.nc" --prior "${mo}/prior_d01.nc" \
         >> "${mo}/insert.log" 2>&1 || { cat "${mo}/insert.log" >&2; die "qnrain failed for member ${m}"; }
   fi
   cp "${md}/dart_d01.nc" "${mo}/analysis_d01.nc"
   opts=()
   [ "${HYDROSTATIC_PH}" != 1 ] || opts=(--hydrostatic-ph --prior "${mo}/prior_d01.nc")
   ${PY} "${DA}/wrfrst_dart.py" insert "${md}/dart_d01.nc" "${rst}" \
      --fields "${fields[@]}" "${opts[@]}" >> "${mo}/insert.log" 2>&1 \
      || { cat "${mo}/insert.log" >&2; die "insert failed for member ${m}"; }
   ${PY} "${DA}/wrfrst_dart.py" extract "${rst}" "${md}/start_d01.nc"
   "${DA}/refit_member_bdy.sh" "${md}/start_d01.nc" "${BDY_DIR}/wrfbdy_d01_mem${m}" "${md}/bdy"
   cp "${md}/bdy/wrfbdy_d01" "${mo}/wrfbdy_d01"
   cp "${md}/bdy/update_wrf_bc.log" "${mo}/"
   touch "${mo}/update.done"
   log "post_filter ${t}: member ${m} inserted (hydrostatic_ph=${HYDROSTATIC_PH}), boundary refit"
   ;;
*) die "post_filter.sh: unknown mode ${mode}" ;;
esac
