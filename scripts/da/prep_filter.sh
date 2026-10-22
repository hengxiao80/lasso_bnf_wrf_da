#!/bin/bash
# Prepare filter for the analysis at <t> (pilot step 12). Runs inside the cycling allocation.
#
# Usage: prep_filter.sh <experiment.sh> <YYYYMMDDHHMM> [conv|mrms]
#
# conv (default): the first (or only) filter pass, in run/filter/, steps 1-3 below. In a one-pass MRMS
#    run (MRMS_FILTER = one_pass, cycle_lib.sh one_pass_mrms) the only pass: input.nml from
#    config/input.nml.filter_joint, obs_seq.out -> obs/<t>/obs_seq.joint, and the impact table
#    config/obs_impact_joint.txt linked in as obs_impact_joint.txt.
# mrms: the second pass of a two-pass run (observation set with MRMS, cycle_lib.sh two_pass), in
#    run/filter_mrms/, on the member files the first pass has just updated: no extraction; input.nml
#    from config/input.nml.filter_mrms, obs_seq.out -> obs/<t>/obs_seq.mrms, the impact table
#    config/obs_impact_mrms.txt (since 2026-10-21); inflation by
#    MRMS_INFLATION: pass1 = none (inf_flavor 0, as in the file); both = INF_FLAVOR, from the first
#    pass's postassim_priorinf_{mean,sd}.nc (output/<t>/filter/), inf_sd_lower_bound = INF_SD_LOWER_BOUND,
#    with inf_damping = INF_DAMPING if MRMS_PASS2_DAMPING = 1 (default), else the file's 1.0.
#
# 1. Prior DART-facing files: wrfrst_dart.py extract (with the DART_EXTRA fields of cycle_lib.sh) of
#    each member's run/memNNN/wrfrst_d01_<t> into run/memNNN/dart_d01.nc (filter updates it in
#    place), saved as output/<t>/memNNN/prior_d01.nc. One one-node srun step per member, concurrently.
# 2. run/filter/ from scratch: input.nml (config/input.nml.filter with tasks_per_node set to
#    FILTER_TASKS_PER_NODE, the prior inf_damping, inf_flavor and inf_sd_lower_bound to INF_DAMPING,
#    INF_FLAVOR and INF_SD_LOWER_BOUND),
#    input/output lists -> run/memNNN/dart_d01.nc, wrfinput_d01 -> GRID_FILE, the
#    sampling-error table, obs_seq.out -> obs/<t>/obs_seq.out.
# 3. Prior inflation: at the first analysis (t - 15 min = FIRST_CYCLE) fill_inflation_restart
#    (1.0, sd 0.6); afterwards the previous cycle's postassim_priorinf_{mean,sd}.nc (of its MRMS
#    pass if MRMS_INFLATION = both, else of its first pass). Not output_priorinf_*: that one holds
#    only the UPDATE variables (step 11 gate).
# The wrfrst files are not modified here, so this step can always be rerun.
set -eu

exp_sh=$1 t=$2 pass=${3:-conv}
source "${exp_sh}"
source "$(dirname "$(readlink -f "$0")")/cycle_lib.sh"
PY=${PROJECT_DIR}/.venv/bin/python
DA=${PROJECT_DIR}/scripts/da

out=${OUTPUT_DIR}/${t}
ft=$(file_time "${t}")
prev=$(add_minutes "${t}" -"${CYCLE_MINUTES}")

# directory, namelist, observations and (mrms) inflation of this pass
if [ "${pass}" = mrms ]; then
   two_pass || die "prep_filter mrms: ${OBS_DIR} has no MRMS"
   fdir=${RUN_DIR}/filter_mrms
   nml=${CONFIG_DIR}/input.nml.filter_mrms
   obs=${OBS_DIR}/${t}/obs_seq.mrms
   sdir=filter_mrms
elif [ "${pass}" = conv ] && one_pass_mrms; then
   fdir=${RUN_DIR}/filter
   nml=${CONFIG_DIR}/input.nml.filter_joint
   obs=${OBS_DIR}/${t}/obs_seq.joint
   sdir=filter
elif [ "${pass}" = conv ]; then
   fdir=${RUN_DIR}/filter
   nml=${CONFIG_DIR}/input.nml.filter
   obs=${OBS_DIR}/${t}/obs_seq.out
   sdir=filter
else
   die "prep_filter: unknown pass ${pass}"
fi
[ -s "${obs}" ] || die "no ${obs} (make_cycle_obs.sh ${t})"

# --- 1. prior DART-facing files (first pass only) ---------------------------------------
if [ "${pass}" = conv ]; then
   pids=()
   for m in $(members); do
      md=${RUN_DIR}/mem${m}
      [ -f "${md}/wrfrst_d01_${ft}" ] || die "no ${md}/wrfrst_d01_${ft}"
      mkdir -p "${out}/mem${m}"
      srun -N 1 -n 1 -c 8 --exact bash -c "set -e
         ${PY} ${DA}/wrfrst_dart.py extract ${md}/wrfrst_d01_${ft} ${md}/dart_d01.nc --extra ${DART_EXTRA}
         cp ${md}/dart_d01.nc ${out}/mem${m}/prior_d01.nc" &
      pids+=($!)
   done
   wait_all "${pids[@]}" || die "prior extraction failed"
fi

# --- 2. filter directory ----------------------------------------------------------------
rm -rf "${fdir}"
mkdir -p "${fdir}"
cd "${fdir}"
sed "s/tasks_per_node = 16/tasks_per_node = ${FILTER_TASKS_PER_NODE}/" "${nml}" > input.nml
grep -q "tasks_per_node = ${FILTER_TASKS_PER_NODE}\$" input.nml || die "tasks_per_node not set"
if [ "${pass}" = conv ]; then
   sed -i "s/^\(   inf_damping *= *\)[0-9.]*,/\1${INF_DAMPING},/" input.nml
   grep -q "^   inf_damping *= *${INF_DAMPING}," input.nml || die "inf_damping not set"
fi
if [ "${pass}" = conv ] || [ "${MRMS_INFLATION}" = both ]; then
   sed -i "s/^\(   inf_flavor *= *\)[0-9]*,/\1${INF_FLAVOR},/" input.nml
   grep -q "^   inf_flavor *= *${INF_FLAVOR}," input.nml || die "inf_flavor not set"
   sed -i "s/^\(   inf_sd_lower_bound *= *\)[0-9.]*,/\1${INF_SD_LOWER_BOUND},/" input.nml
   grep -q "^   inf_sd_lower_bound *= *${INF_SD_LOWER_BOUND}," input.nml || die "inf_sd_lower_bound not set"
fi
if [ "${pass}" = mrms ] && [ "${MRMS_INFLATION}" = both ]; then
   damp=1.0
   [ "${MRMS_PASS2_DAMPING}" != 1 ] || damp=${INF_DAMPING}
   sed -i "s/^\(   inf_damping *= *\)[0-9.]*,/\1${damp},/" input.nml
   grep -q "^   inf_damping *= *${damp}," input.nml || die "inf_damping not set"
fi
ln -s "${GRID_FILE}" wrfinput_d01
ln -s "${SEC_TABLE}" sampling_error_correction_table.nc
ln -s "${obs}" obs_seq.out
if grep -q "^ *adjust_obs_impact *= *\.true\." input.nml; then   # the table input.nml names, from config/
   imp=$(sed -n "s/^ *obs_impact_filename *= *'\([^']*\)'.*/\1/p" input.nml)
   [ -n "${imp}" ] && [ -f "${CONFIG_DIR}/${imp}" ] || die "impact table '${imp}' not in ${CONFIG_DIR}"
   cp "${CONFIG_DIR}/${imp}" "${imp}"
fi
for m in $(members); do echo "${RUN_DIR}/mem${m}/dart_d01.nc"; done > input_list_d01.txt
cp input_list_d01.txt output_list_d01.txt

# --- 3. prior inflation -----------------------------------------------------------------
mkdir -p "${out}/${sdir}"
if [ "${pass}" = mrms ]; then
   case ${MRMS_INFLATION} in
   pass1)
      grep -q "^   inf_flavor *= *0," input.nml || die "inf_flavor of the MRMS pass is not 0"
      echo "none (MRMS_INFLATION=pass1)" > "${out}/${sdir}/inflation_source.txt" ;;
   both)
      for s in mean sd; do
         f=${out}/filter/postassim_priorinf_${s}.nc
         [ -f "${f}" ] || die "no ${f}"
         cp "${f}" "input_priorinf_${s}.nc"
      done
      echo "${out}/filter/postassim_priorinf_{mean,sd}.nc (MRMS_INFLATION=both, inf_damping ${damp})" \
         > "${out}/${sdir}/inflation_source.txt" ;;
   *) die "MRMS_INFLATION='${MRMS_INFLATION}': must be pass1 or both" ;;
   esac
   log "prep_filter ${t} (mrms): obs ${obs}, inflation $(cat "${out}/${sdir}/inflation_source.txt")"
   exit 0
fi
if [ "${prev}" = "${FIRST_CYCLE}" ]; then
   ln -s "${RUN_DIR}/mem001/dart_d01.nc" dart_d01.nc   # template for fill_inflation_restart
   srun -N 1 -n 1 --exact "${DART_WORK}/fill_inflation_restart" > fill_inflation.log 2>&1 \
      || die "fill_inflation_restart failed, see ${fdir}/fill_inflation.log"
   rm dart_d01.nc
   src="fill_inflation_restart (first analysis)"
else
   pdir=filter
   [ "${MRMS_INFLATION}" != both ] || pdir=filter_mrms
   for s in mean sd; do
      f=${OUTPUT_DIR}/${prev}/${pdir}/postassim_priorinf_${s}.nc
      [ -f "${f}" ] || die "no ${f}"
      cp "${f}" "input_priorinf_${s}.nc"
   done
   src="${OUTPUT_DIR}/${prev}/${pdir}/postassim_priorinf_{mean,sd}.nc"
fi
for s in mean sd; do [ -f "input_priorinf_${s}.nc" ] || die "no input_priorinf_${s}.nc"; done
echo "${src}" > "${out}/filter/inflation_source.txt"
log "prep_filter ${t}: priors extracted, obs ${obs}, inflation from ${src}"
