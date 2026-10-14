#!/bin/bash
# Build one cycle's mesonet obs_seq from the hourly public-MADIS files (obs_expansion.md Sec. 7.2).
#
# Usage: make_cycle_mesonet.sh <YYYYMMDDHHMM> [option] [calm]
#
# option: a (default, RRFS v2), b1 (GSD method, HRRR/RRFS v1) or c (HRRRDAS); calm: keep (default,
# as RRFS v2) or drop. See select_mesonet_cycle.py and notes/mesonet_station_selection.md.
# Output in ${CASE_DIR}/obs/obs_seq_mesonet/<option>_calm<calm>/<YYYYMMDDHHMM>/:
#   obs_seq.land_sfc   LAND_SFC_* observations (ASCII), the land_sfc_extra input of
#                      wrf_dart_obs_preprocess in make_cycle_obs.sh
#   counts             obs per type in obs_seq.land_sfc
#   selected.csv, selection.log, mesonet_input.nc   from select_mesonet_cycle.py
#   convert.log        convert_madis_mesonet and obs_sequence_tool output
# The selection already applies the time window and the lat/lon box; the exact trim to the Lambert
# domain and its boundary zone is wrf_dart_obs_preprocess's job. Observation errors are the
# converter's compiled land_* functions: RAP/RRFS mesonet values since 2026-10-14 (T 3.0 K, wind 3.0 m/s,
# RH 0.07, altimeter 1.0 hPa; patches/dart_7bbd35a09_madis_mesonet_obs_errors.patch).
# Needs the scripts/env_wrf.sh modules (netCDF libraries).
set -eu

stamp=$1 option=${2:-a} calm=${3:-keep}
source /gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da/cases/20250520/da_theta_m0/config/experiment.sh
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PYTHON=$(dirname "$(dirname "${SCRIPT_DIR}")")/.venv/bin/python
MADIS_WORK=${SOFTWARE_DIR}/DART/observations/obs_converters/MADIS/work

out=${CASE_DIR}/obs/obs_seq_mesonet/${option}_calm${calm}/${stamp}
rm -rf "${out}"
mkdir -p "${out}"

"${PYTHON}" "${SCRIPT_DIR}/select_mesonet_cycle.py" "${stamp}" "${out}" --option "${option}" \
   --calm "${calm}" --grid-file "${GRID_FILE}" --case-dir "${CASE_DIR}" --software-dir "${SOFTWARE_DIR}" > /dev/null

# The converter reads mesonet_input.nc and appends to obs_seq.mesonet if it exists: fresh work dir.
work=${out}/work
mkdir -p "${work}"
cd "${work}"
ln -s ../mesonet_input.nc mesonet_input.nc
cat > input.nml << EOF
&utilities_nml
   termlevel = 1, logfilename = 'dart_log.out', nmlfilename = 'dart_log.nml', write_nml = 'file',
/
&obs_kind_nml
/
&location_nml
/
&obs_sequence_nml
   write_binary_obs_sequence = .false.
/
&obs_sequence_tool_nml
   filename_seq = 'obs_seq.mesonet', filename_out = 'obs_seq.junk', print_only = .true.,
   gregorian_cal = .true.,
/
EOF
{
   echo "=== convert_madis_mesonet"
   "${MADIS_WORK}/convert_madis_mesonet" < /dev/null
   echo "=== obs_sequence_tool (counts)"
   "${MADIS_WORK}/obs_sequence_tool" < /dev/null
} > "${out}/convert.log" 2>&1 || true

if [ ! -s obs_seq.mesonet ] || ! grep -q 'obs_sequence_tool Finished successfully' "${out}/convert.log"; then
   echo "make_cycle_mesonet.sh: conversion failed for ${stamp}, see ${out}/convert.log" >&2
   exit 1
fi
mv obs_seq.mesonet "${out}/obs_seq.land_sfc"
awk '/Starting to process input sequence file/{o=1} /Starting to process output/{o=0} o && / obs$/{print $1, $2}' \
   "${out}/convert.log" > "${out}/counts"
cd "${out}"
rm -rf "${work}"
echo "make_cycle_mesonet.sh: ${stamp} (${option}, calm ${calm}): $(awk '{n += $2} END {print n + 0}' counts) obs:" \
   "$(awk '{printf "%s %s  ", $1, $2}' counts)"
