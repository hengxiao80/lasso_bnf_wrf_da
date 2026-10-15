#!/bin/bash
# Download the MRMS MergedReflectivityQC levels for one analysis time (obs_expansion.md Sec. 8.2).
#
# Usage: download_mrms.sh <YYYYMMDDHHMM> [out_root]
#
# HRRRDAS's file rule, as in mrms_to_obs_seq.py: all 33 levels at the analysis minute mm, else at
# mm - 1, else at mm - 2 (MRMS writes a set about every 2 min at irregular seconds, e.g. 00:14:38).
# Lists the public bucket noaa-mrms-pds (CONUS/MergedReflectivityQC_XX.XX/YYYYMMDD/) and downloads
# the first complete set into <out_root>/YYYYMMDD/ (default ${CASE_DIR}/obs/mrms). Files already
# there are not downloaded again. Run on a login node (compute nodes have no internet).
set -eu

stamp=$1
source /gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da/cases/20250520/da_theta_m0/config/experiment.sh
out_root=${2:-${CASE_DIR}/obs/mrms}
URL=https://noaa-mrms-pds.s3.amazonaws.com
LEVELS="00.50 00.75 01.00 01.25 01.50 01.75 02.00 02.25 02.50 02.75 03.00 03.50 04.00 04.50 05.00
        05.50 06.00 06.50 07.00 07.50 08.00 08.50 09.00 10.00 11.00 12.00 13.00 14.00 15.00 16.00
        17.00 18.00 19.00"

t_epoch=$(date -u -d "${stamp:0:8} ${stamp:8:2}:${stamp:10:2}" +%s)
for back in 0 1 2; do
   tm=$(date -u -d "@$(( t_epoch - back * 60 ))" +%Y%m%d-%H%M)
   day=${tm:0:8}
   keys=()
   for lev in ${LEVELS}; do
      prefix=CONUS/MergedReflectivityQC_${lev}/${day}/MRMS_MergedReflectivityQC_${lev}_${tm}
      key=$(curl -sf "${URL}/?list-type=2&prefix=${prefix}" | grep -o '<Key>[^<]*</Key>' \
            | sed 's/<\/*Key>//g' | head -n 1)
      [ -n "${key}" ] || break
      keys+=("${key}")
   done
   if [ ${#keys[@]} -eq 33 ]; then
      dir=${out_root}/${day}
      mkdir -p "${dir}"
      for key in "${keys[@]}"; do
         f=${dir}/$(basename "${key}")
         if [ ! -s "${f}" ]; then
            curl -sf -o "${f}.part" "${URL}/${key}" && [ -s "${f}.part" ] && mv "${f}.part" "${f}" \
               || { rm -f "${f}.part"; echo "download_mrms.sh: failed to download ${key}" >&2; exit 1; }
         fi
      done
      echo "download_mrms.sh: ${stamp}: 33 levels at $(basename "${keys[0]}" | sed 's/.*_\([0-9-]*\)\.grib2.*/\1/') in ${dir}"
      exit 0
   fi
done
echo "download_mrms.sh: no complete set of 33 levels within 2 min before ${stamp}" >&2
exit 1
