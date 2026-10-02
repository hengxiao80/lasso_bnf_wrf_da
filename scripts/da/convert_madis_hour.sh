#!/bin/bash
# Convert one hourly public-MADIS file to a DART obs_seq file trimmed to the domain's lat/lon box
# (pilot step 9).
#
# Usage: convert_madis_hour.sh <family> <YYYYMMDD_HH00> [out_root]
#
# <family>: metar | acars | rawin | marine (the converter names; rawin reads madis/raob/).
# Input:  ${CASE_DIR}/obs/madis/<dir>/<YYYYMMDD_HH00>.gz
# Output: <out_root>/<family>/obs_seq.<family>.<YYYYMMDD_HH00>  (ASCII, in the box only)
#         <out_root>/<family>/counts.<family>.<YYYYMMDD_HH00>   (obs per type, in the box)
#         <out_root>/logs/<family>.<YYYYMMDD_HH00>.log          (converter + obs_sequence_tool)
# out_root defaults to ${CASE_DIR}/obs/obs_seq_madis.
#
# The converters read a fixed-name input (<family>_input.nc) and append to a fixed-name output
# (obs_seq.<family>) if it exists, so every run gets its own fresh work directory, removed on
# success. The box is the domain's mass-point lat/lon extent (geo_em XLAT_M/XLONG_M, rounded),
# as in the first conversion test (obs/obs_seq_test); the exact trim to the Lambert domain and
# its boundary zone is wrf_dart_obs_preprocess's job (step 10). Converter options are the
# compiled constants (patches/README.md); rawin reads &convert_madis_rawin_nml (patched).
# A missing input (radiosonde files exist only for launch hours) is reported and skipped.
# Needs the scripts/env_wrf.sh modules (netCDF libraries).
set -eu

family=$1 stamp=$2
CASE_DIR=${CASE_DIR:-/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da/cases/20250520}
out_root=${3:-${CASE_DIR}/obs/obs_seq_madis}
MADIS_WORK=${MADIS_WORK:-/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/software/DART/observations/obs_converters/MADIS/work}

# Domain lat/lon box (degrees north / east, 0-360).
MIN_LAT=30.36 MAX_LAT=39.37 MIN_LON=262.52 MAX_LON=278.38

case ${family} in
   metar|acars|marine) madis_dir=${family} ;;
   rawin) madis_dir=raob ;;
   *) echo "convert_madis_hour.sh: unknown family '${family}'" >&2; exit 1 ;;
esac

in_file=${CASE_DIR}/obs/madis/${madis_dir}/${stamp}.gz
if [ ! -f "${in_file}" ]; then
   echo "convert_madis_hour.sh: no ${madis_dir} file for ${stamp}, skipped"
   exit 0
fi

out_dir=${out_root}/${family}
log=${out_root}/logs/${family}.${stamp}.log
work=${out_root}/work/${family}.${stamp}
mkdir -p "${out_dir}" "${out_root}/logs"
rm -rf "${work}"
mkdir -p "${work}"
cd "${work}"

zcat "${in_file}" > ${family}_input.nc

cat > input.nml << EOF
&utilities_nml
   termlevel = 1,
   logfilename = 'dart_log.out',
   nmlfilename = 'dart_log.nml',
   write_nml = 'file',
/
&obs_kind_nml
/
&location_nml
/
&obs_sequence_nml
   write_binary_obs_sequence = .false.
/
&convert_madis_rawin_nml
   do_significant_level_temps = .true.
   do_significant_level_winds = .true.
   wind_use_vert_pressure     = .true.
   LH_err                     = .false.
   include_specific_humidity  = .true.
   include_relative_humidity  = .false.
   include_dewpoint           = .false.
   use_input_qc               = .true.
/
&obs_sequence_tool_nml
   filename_seq       = 'obs_seq.${family}'
   filename_out       = 'obs_seq.box'
   gregorian_cal      = .true.
   min_lat            = ${MIN_LAT}
   max_lat            = ${MAX_LAT}
   min_lon            = ${MIN_LON}
   max_lon            = ${MAX_LON}
/
EOF

{
   echo "=== convert_madis_${family} ${in_file}"
   "${MADIS_WORK}/convert_madis_${family}" < /dev/null
   echo "=== obs_sequence_tool (box ${MIN_LAT}-${MAX_LAT} N, ${MIN_LON}-${MAX_LON} E)"
   "${MADIS_WORK}/obs_sequence_tool" < /dev/null
} > "${log}" 2>&1 || true

if [ ! -s obs_seq.${family} ]; then
   # A converter writes no file when no report passes (possible for marine); not an error.
   if grep -q 'Finished ...' "${log}"; then
      echo "convert_madis_hour.sh: ${family} ${stamp}: no observations written"
      cd "${out_root}"; rm -rf "${work}"; exit 0
   fi
   echo "convert_madis_hour.sh: convert_madis_${family} failed for ${stamp}, see ${log}" >&2; exit 1
fi
if grep -q 'All input files are empty or all obs excluded' "${log}"; then
   # Nothing in the box (e.g. off-hour radiosonde files with soundings elsewhere): no output file.
   : > "${out_dir}/counts.${family}.${stamp}"
   echo "convert_madis_hour.sh: ${family} ${stamp}: 0 obs in the box"
   cd "${out_root}"; rm -rf "${work}"; exit 0
fi
if ! grep -q 'obs_sequence_tool Finished successfully' "${log}"; then
   echo "convert_madis_hour.sh: obs_sequence_tool failed for ${family} ${stamp}, see ${log}" >&2; exit 1
fi

# Per-type counts of the output (the second table obs_sequence_tool prints).
awk '/Starting to process output sequence file/{o=1} o && / obs$/{print $1, $2}' "${log}" \
   > "${out_dir}/counts.${family}.${stamp}"
if [ -f obs_seq.box ]; then
   mv obs_seq.box "${out_dir}/obs_seq.${family}.${stamp}"
fi
cd "${out_root}"
rm -rf "${work}"
echo "convert_madis_hour.sh: ${family} ${stamp}: $(awk '{n += $2} END {print n + 0}' "${out_dir}/counts.${family}.${stamp}") obs in the box"
