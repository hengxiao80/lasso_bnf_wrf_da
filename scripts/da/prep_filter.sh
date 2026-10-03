#!/bin/bash
# Prepare filter for the analysis at <t> (pilot step 12). Runs inside the cycling allocation.
#
# Usage: prep_filter.sh <experiment.sh> <YYYYMMDDHHMM>
#
# 1. Prior DART-facing files: wrfrst_dart.py extract of each member's run/memNNN/wrfrst_d01_<t>
#    into run/memNNN/dart_d01.nc (filter updates it in place), saved as output/<t>/memNNN/prior_d01.nc.
#    One one-node srun step per member, concurrently.
# 2. run/filter/ from scratch: input.nml (config/input.nml.filter with tasks_per_node set to
#    FILTER_TASKS_PER_NODE, the prior inf_damping and inf_flavor to INF_DAMPING and INF_FLAVOR),
#    input/output lists -> run/memNNN/dart_d01.nc, wrfinput_d01 -> GRID_FILE, the
#    sampling-error table, obs_seq.out -> obs/<t>/obs_seq.out.
# 3. Prior inflation: at the first analysis (t - 15 min = FIRST_CYCLE) fill_inflation_restart
#    (1.0, sd 0.6); afterwards the previous cycle's postassim_priorinf_{mean,sd}.nc. Not
#    output_priorinf_*: that one holds only the UPDATE variables (step 11 gate).
# The wrfrst files are not modified here, so this step can always be rerun.
set -eu

exp_sh=$1 t=$2
source "${exp_sh}"
source "$(dirname "$(readlink -f "$0")")/cycle_lib.sh"
PY=${PROJECT_DIR}/.venv/bin/python
DA=${PROJECT_DIR}/scripts/da

out=${OUTPUT_DIR}/${t}
fdir=${RUN_DIR}/filter
ft=$(file_time "${t}")
obs=${OBS_DIR}/${t}/obs_seq.out
prev=$(add_minutes "${t}" -"${CYCLE_MINUTES}")
[ -s "${obs}" ] || die "no ${obs} (make_cycle_obs.sh ${t})"

# --- 1. prior DART-facing files ---------------------------------------------------------
pids=()
for m in $(members); do
   md=${RUN_DIR}/mem${m}
   [ -f "${md}/wrfrst_d01_${ft}" ] || die "no ${md}/wrfrst_d01_${ft}"
   mkdir -p "${out}/mem${m}"
   srun -N 1 -n 1 -c 8 --exact bash -c "set -e
      ${PY} ${DA}/wrfrst_dart.py extract ${md}/wrfrst_d01_${ft} ${md}/dart_d01.nc
      cp ${md}/dart_d01.nc ${out}/mem${m}/prior_d01.nc" &
   pids+=($!)
done
wait_all "${pids[@]}" || die "prior extraction failed"

# --- 2. filter directory ----------------------------------------------------------------
rm -rf "${fdir}"
mkdir -p "${fdir}"
cd "${fdir}"
sed "s/tasks_per_node = 16/tasks_per_node = ${FILTER_TASKS_PER_NODE}/" \
   "${CONFIG_DIR}/input.nml.filter" > input.nml
grep -q "tasks_per_node = ${FILTER_TASKS_PER_NODE}\$" input.nml || die "tasks_per_node not set"
sed -i "s/^\(   inf_damping *= *\)[0-9.]*,/\1${INF_DAMPING},/" input.nml
grep -q "^   inf_damping *= *${INF_DAMPING}," input.nml || die "inf_damping not set"
sed -i "s/^\(   inf_flavor *= *\)[0-9]*,/\1${INF_FLAVOR},/" input.nml
grep -q "^   inf_flavor *= *${INF_FLAVOR}," input.nml || die "inf_flavor not set"
ln -s "${GRID_FILE}" wrfinput_d01
ln -s "${SEC_TABLE}" sampling_error_correction_table.nc
ln -s "${obs}" obs_seq.out
for m in $(members); do echo "${RUN_DIR}/mem${m}/dart_d01.nc"; done > input_list_d01.txt
cp input_list_d01.txt output_list_d01.txt

# --- 3. prior inflation -----------------------------------------------------------------
if [ "${prev}" = "${FIRST_CYCLE}" ]; then
   ln -s "${RUN_DIR}/mem001/dart_d01.nc" dart_d01.nc   # template for fill_inflation_restart
   srun -N 1 -n 1 --exact "${DART_WORK}/fill_inflation_restart" > fill_inflation.log 2>&1 \
      || die "fill_inflation_restart failed, see ${fdir}/fill_inflation.log"
   rm dart_d01.nc
   src="fill_inflation_restart (first analysis)"
else
   for s in mean sd; do
      f=${OUTPUT_DIR}/${prev}/filter/postassim_priorinf_${s}.nc
      [ -f "${f}" ] || die "no ${f}"
      cp "${f}" "input_priorinf_${s}.nc"
   done
   src="${OUTPUT_DIR}/${prev}/filter/postassim_priorinf_{mean,sd}.nc"
fi
for s in mean sd; do [ -f "input_priorinf_${s}.nc" ] || die "no input_priorinf_${s}.nc"; done
mkdir -p "${out}/filter"
echo "${src}" > "${out}/filter/inflation_source.txt"
log "prep_filter ${t}: priors extracted, obs ${obs}, inflation from ${src}"
