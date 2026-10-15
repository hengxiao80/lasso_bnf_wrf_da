#!/bin/bash
# Build one cycle's obs_seq.out from the hourly converted MADIS files (pilot step 10).
#
# Usage: [OBS_NAME=_x] [MESONET=a_calmkeep] [MRMS=hrrrdas] make_cycle_obs.sh <YYYYMMDDHHMM> [out_root]
#
# <YYYYMMDDHHMM> is the analysis time t. Output in <out_root>/<YYYYMMDDHHMM>/ (default
# ${OBS_DIR} = ${EXP_DIR}/obs${OBS_NAME}): obs_seq.out, counts.window (per type after the time slice, per family) and
# counts.out (per type after screening), plus the logs of every program run.
#
# 1. Time slice. For each family, obs_sequence_tool merges the hourly files of the hours around t
#    (${CASE_DIR}/obs/obs_seq_madis/<family>/obs_seq.<family>.YYYYMMDD_HH00, from
#    convert_madis_hour.sh) and keeps (t - 450 s, t + 450 s], the window filter uses with
#    assimilation_period_seconds = 900 (obs_model_mod: start = t - 450 s + 1 s, end = t + 450 s,
#    both inclusive), so each report goes to exactly one cycle. A family with nothing in the
#    window gets no file.
#    Mesonet (MESONET != none, experiment.sh): make_cycle_mesonet.sh builds the cycle's
#    obs_seq.land_sfc (its selection already applies the same window) and it joins the others.
#    The set's contents are recorded in <out_root>/obs_settings.txt; a set built with other
#    settings, or one without that file (obs/ of step 13), is not written into.
# 2. Screening. wrf_dart_obs_preprocess with ${CONFIG_DIR}/input.nml.obs_preprocess reads the
#    per-family slices as its "extra" files and trims to the domain minus the boundary zone,
#    checks surface elevation against the model terrain, applies the pressure/height top and
#    inflates errors near the boundary. It needs wrfinput_d01 for the grid and terrain; the hourly
#    mean wrfinput is used (static fields only).
# 3. MRMS reflectivity (MRMS != none, experiment.sh): mrms_to_obs_seq.py writes <t>/obs_seq.mrms,
#    the obs of filter's second (radar) pass (two-pass cycle, obs_expansion.md Sec. 8.4). It is
#    not merged into obs_seq.out and does not go through wrf_dart_obs_preprocess (which has no
#    radar family); the converter applies the same boundary trim and error inflation itself and
#    checks that the MRMS time is in the window. The MRMS files come from download_mrms.sh
#    (login node). counts.mrms: per type.
#    Also <t>/obs_seq.joint: obs_seq.out and obs_seq.mrms merged by obs_sequence_tool (time order,
#    no duplicate-location test; the copy/QC names differ and are declared synonymous), the input of
#    a one-pass run (MRMS_FILTER = one_pass).
# Needs the scripts/env_wrf.sh modules (netCDF libraries).
set -eu

stamp=$1
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
source /gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da/cases/20250520/da_theta_m0/config/experiment.sh
out_root=${2:-${OBS_DIR}}
DART_WRF_WORK=${SOFTWARE_DIR}/DART/models/wrf/work
CONV_DIR=${CASE_DIR}/obs/obs_seq_madis
GRID_FILE=${MEAN_DIR}/wrfinput_d01_2025-05-20_00_00_00
HALF=450

# Analysis time in DART's Gregorian days/seconds (days since 1601-01-01).
t_epoch=$(date -u -d "${stamp:0:8} ${stamp:8:2}:${stamp:10:2}" +%s)
dart_time() {   # epoch seconds -> "days seconds"
   local s=$(( $1 + 11644473600 ))
   echo "$(( s / 86400 )) $(( s % 86400 ))"
}
read -r t_day t_sec <<< "$(dart_time ${t_epoch})"
read -r first_day first_sec <<< "$(dart_time $(( t_epoch - HALF + 1 )))"
read -r last_day last_sec <<< "$(dart_time $(( t_epoch + HALF )))"

obs_settings="mesonet=${MESONET}"
[ "${MRMS}" = none ] || obs_settings="${obs_settings} mrms=${MRMS}"   # sets without MRMS keep their line
case ${MRMS} in
   none|hrrrdas) ;;
   *) echo "make_cycle_obs.sh: unknown MRMS=${MRMS} (none, hrrrdas)" >&2; exit 1 ;;
esac
if [ -f "${out_root}/obs_settings.txt" ]; then
   grep -qx "${obs_settings}" "${out_root}/obs_settings.txt" || {
      echo "make_cycle_obs.sh: ${out_root} holds $(cat "${out_root}/obs_settings.txt"), not ${obs_settings}" >&2; exit 1; }
elif [ -d "${out_root}" ] && [ -n "$(find "${out_root}" -mindepth 1 -maxdepth 1)" ]; then
   echo "make_cycle_obs.sh: ${out_root} has no obs_settings.txt (an older set); use another OBS_NAME" >&2; exit 1
else
   mkdir -p "${out_root}"
   echo "${obs_settings}" > "${out_root}/obs_settings.txt"
fi

out=${out_root}/${stamp}
rm -rf "${out}"
mkdir -p "${out}/slice" "${out}/prep"

# --- 1. time slice per family ------------------------------------------------------------
: > "${out}/counts.window"
for family in metar acars rawin marine; do
   cd "${out}/slice"
   rm -f input.nml obs_list dart_log.*
   # Hourly files of the previous, current and next hour (METAR/marine files start at HH-15 min).
   for dh in -1 0 1; do
      f=${CONV_DIR}/${family}/obs_seq.${family}.$(date -u -d "@$(( t_epoch + dh * 3600 ))" +%Y%m%d_%H00)
      [ -f "${f}" ] && echo "${f}" >> obs_list
   done
   [ -s obs_list ] || { echo "${family}: no hourly file" >> "${out}/counts.window"; continue; }
   cat > input.nml << EOF
&obs_sequence_tool_nml
   filename_seq_list = 'obs_list',
   filename_out      = '../prep/obs_seq.${family}',
   gregorian_cal     = .true.,
   first_obs_days    = ${first_day},
   first_obs_seconds = ${first_sec},
   last_obs_days     = ${last_day},
   last_obs_seconds  = ${last_sec},
/
&obs_sequence_nml
   write_binary_obs_sequence = .false.,
/
&utilities_nml
   termlevel = 1, logfilename = 'dart_log.out', nmlfilename = 'dart_log.nml', write_nml = 'file',
/
&obs_kind_nml
/
&location_nml
/
EOF
   log=${out}/slice.${family}.log
   "${DART_WRF_WORK}/obs_sequence_tool" < /dev/null > "${log}" 2>&1 || true
   if grep -q 'obs_sequence_tool Finished successfully' "${log}"; then
      awk -v fam=${family} '/Starting to process output sequence file/{o=1} o && / obs$/{print fam, $1, $2}' \
         "${log}" >> "${out}/counts.window"
   elif grep -q 'All input files are empty or all obs excluded' "${log}"; then
      echo "${family}: 0 in window" >> "${out}/counts.window"
   else
      echo "make_cycle_obs.sh: obs_sequence_tool failed for ${family} ${stamp}, see ${log}" >&2; exit 1
   fi
done

# Mesonet: one per-cycle file, already selected for the window.
if [ "${MESONET}" != none ]; then
   "${SCRIPT_DIR}/make_cycle_mesonet.sh" "${stamp}" "${MESONET%%_calm*}" "${MESONET##*_calm}" \
      > "${out}/mesonet.log" 2>&1 || {
      echo "make_cycle_obs.sh: make_cycle_mesonet.sh failed for ${stamp}, see ${out}/mesonet.log" >&2; exit 1; }
   meso=${CASE_DIR}/obs/obs_seq_mesonet/${MESONET}/${stamp}
   cp "${meso}/obs_seq.land_sfc" "${out}/prep/obs_seq.land_sfc"
   awk '{print "mesonet", $1, $2}' "${meso}/counts" >> "${out}/counts.window"
fi

# --- 2. screening ------------------------------------------------------------------------
cd "${out}/prep"
cp "${CONFIG_DIR}/input.nml.obs_preprocess" input.nml
ln -sf "${GRID_FILE}" wrfinput_d01
echo "${t_day} ${t_sec}" | "${DART_WRF_WORK}/wrf_dart_obs_preprocess" > "${out}/preprocess.log" 2>&1 || true
if ! grep -q 'Finished ...' "${out}/preprocess.log" || [ ! -s obs_seq.out ]; then
   echo "make_cycle_obs.sh: wrf_dart_obs_preprocess failed for ${stamp}, see ${out}/preprocess.log" >&2
   exit 1
fi
mv obs_seq.out "${out}/obs_seq.out"
rm -f wrfinput_d01

# Per-type counts of the result.
cd "${out}/slice"
cat > input.nml << EOF
&obs_sequence_tool_nml
   filename_seq = '../obs_seq.out', filename_out = 'obs_seq.junk', print_only = .true.,
   gregorian_cal = .true.,
/
&obs_sequence_nml
/
&utilities_nml
   termlevel = 1, logfilename = 'dart_log.out', nmlfilename = 'dart_log.nml', write_nml = 'file',
/
&obs_kind_nml
/
&location_nml
/
EOF
"${DART_WRF_WORK}/obs_sequence_tool" < /dev/null > "${out}/counts.log" 2>&1
awk '/Starting to process input sequence file/{o=1} /Starting to process output/{o=0} o && / obs$/{print $1, $2}' \
   "${out}/counts.log" > "${out}/counts.out"

# --- 3. MRMS reflectivity (second filter pass) ------------------------------------------
if [ "${MRMS}" = hrrrdas ]; then
   "${PROJECT_DIR}/.venv/bin/python" "${SCRIPT_DIR}/mrms_to_obs_seq.py" "${CASE_DIR}/obs/mrms" "${stamp}" \
      "${CASE_DIR}/geog/geo_em.d01.nc" "${out}/obs_seq.mrms" > "${out}/mrms.log" 2>&1 || {
      echo "make_cycle_obs.sh: mrms_to_obs_seq.py failed for ${stamp}, see ${out}/mrms.log" >&2; exit 1; }
   awk '/^ *[0-9]+$/ && p == "kind" {n[$1]++} {p = $1}
        END {print "RADAR_REFLECTIVITY", n[1] + 0; print "RADAR_CLEARAIR_REFLECTIVITY", n[2] + 0}' \
      "${out}/obs_seq.mrms" > "${out}/counts.mrms"
   cd "${out}/slice"
   cat > input.nml << EOF
&obs_sequence_tool_nml
   filename_seq         = '../obs_seq.out', '../obs_seq.mrms',
   filename_out         = '../obs_seq.joint',
   gregorian_cal        = .true.,
   synonymous_copy_list = 'NCEP BUFR observation', 'MRMS observation',
   synonymous_qc_list   = 'NCEP QC index', 'Data QC',
/
&obs_sequence_nml
   write_binary_obs_sequence = .false.,
/
&utilities_nml
   termlevel = 1, logfilename = 'dart_log.out', nmlfilename = 'dart_log.nml', write_nml = 'file',
/
&obs_kind_nml
/
&location_nml
/
&obs_def_radar_mod_nml
/
EOF
   "${DART_WRF_WORK}/obs_sequence_tool" < /dev/null > "${out}/joint.log" 2>&1 || true
   grep -q 'obs_sequence_tool Finished successfully' "${out}/joint.log" || {
      echo "make_cycle_obs.sh: merging obs_seq.out and obs_seq.mrms failed for ${stamp}, see ${out}/joint.log" >&2; exit 1; }
   n_joint=$(awk '/num_obs:/{print $2; exit}' "${out}/obs_seq.joint")
   n_sum=$(( $(awk '{n += $2} END {print n + 0}' "${out}/counts.out") + $(awk '{n += $2} END {print n + 0}' "${out}/counts.mrms") ))
   [ "${n_joint}" -eq "${n_sum}" ] || {
      echo "make_cycle_obs.sh: obs_seq.joint has ${n_joint} obs, not ${n_sum}" >&2; exit 1; }
   echo "make_cycle_obs.sh: ${stamp}: MRMS $(awk '{n += $2} END {print n + 0}' "${out}/counts.mrms") obs ($(grep 'MRMS valid' "${out}/mrms.log" | sed 's/.*MRMS valid \([^,]*\),.*/\1/'))"
fi
echo "make_cycle_obs.sh: ${stamp}: window $(awk '$NF ~ /^[0-9]+$/ && NF == 3 {n += $3} END {print n + 0}' "${out}/counts.window"), screened $(awk '{n += $2} END {print n + 0}' "${out}/counts.out") obs"
