#!/bin/bash
# make_mean_icbc.sh - hourly unperturbed ("mean") wrfinput files for the DA experiment.
#
# Usage (inside a Slurm allocation; see cases/<case>/da_*/slurm.make_mean_icbc):
#   make_mean_icbc.sh <experiment.sh> <first_hour> <last_hour>
# Hours are offsets from CASE_START (0 .. CASE_NHOURS).
#
# For each hour it runs real.exe for that single time level (start = end), which writes only
# wrfinput_d01, and stores it as ${MEAN_DIR}/wrfinput_d01_YYYY-MM-DD_HH_00_00. This replaces the
# tutorial's gen_retro_icbc.sh (GFS/WPS per cycle); our WPS output (hourly HRRR met_em) already
# exists. The 72-h wrfbdy_d01 from the theta_m0 real.exe run is linked in, not regenerated.
# Hours whose output already exists are skipped, so the script can be rerun after a failure.
# See notes/wrf_dart_tutorial_adaptation.md 2.3 and notes/da_workflow_layout.md step 1.

set -uo pipefail

if [[ $# -ne 3 ]]; then
   echo "usage: $0 <experiment.sh> <first_hour> <last_hour>"
   exit 2
fi
source "$1"
first_hour=$2
last_hour=$3

: "${SLURM_JOB_ID:?run this inside a Slurm allocation (it uses srun)}"
REAL_NTASKS=${REAL_NTASKS:-${SLURM_NTASKS}}

work=${MEAN_DIR}/work_real
mkdir -p "${MEAN_DIR}" "${work}" "${MEAN_DIR}/logs"

# boundary file: reuse the theta_m0 one (72 hourly records)
if [[ ! -e ${MEAN_DIR}/wrfbdy_d01 ]]; then
   ln -s "${MEAN_BDY_SOURCE}" "${MEAN_DIR}/wrfbdy_d01"
fi

# run directory: WRF run-time tables and real.exe (no namelist, no old outputs)
cd "${work}" || exit 1
for f in "${WRF_RUN_DIR}"/*; do
   name=$(basename "$f")
   [[ ${name} == namelist.input* ]] && continue
   [[ -e ${name} ]] || ln -s "$f" "${name}"
done

start_epoch=$(date -u -d "${CASE_START:0:4}-${CASE_START:4:2}-${CASE_START:6:2} ${CASE_START:8:2}:00:00" +%s)

nfail=0
for (( h=first_hour; h<=last_hour; h++ )); do

   t=$(date -u -d "@$(( start_epoch + h*3600 ))" +%Y%m%d%H)
   yyyy=${t:0:4}; mm=${t:4:2}; dd=${t:6:2}; hh=${t:8:2}
   out=${MEAN_DIR}/wrfinput_d01_${yyyy}-${mm}-${dd}_${hh}_00_00

   if [[ -s ${out} ]]; then
      echo "hour ${h} (${t}): ${out} exists, skipping"
      continue
   fi

   met=${WPS_OUT_DIR}/met_em.d01.${yyyy}-${mm}-${dd}_${hh}:00:00.nc
   if [[ ! -r ${met} ]]; then
      echo "hour ${h} (${t}): missing ${met}"
      (( nfail++ ))
      continue
   fi

   rm -f met_em.d01.* wrfinput_d01 wrfbdy_d01 rsl.out.* rsl.error.*
   ln -s "${met}" .

   # namelist for this single time level; drop the template's '!' header lines
   sed -e '/^!/d' -e "s/@YYYY@/${yyyy}/g" -e "s/@MM@/${mm}/g" \
       -e "s/@DD@/${dd}/g" -e "s/@HH@/${hh}/g" \
       "${CONFIG_DIR}/namelist.input.real" > namelist.input

   echo "hour ${h} (${t}): real.exe start $(date)"
   srun -n "${REAL_NTASKS}" --cpu_bind=cores ./real.exe
   status=$?

   mkdir -p "${MEAN_DIR}/logs/${t}"
   cp namelist.input rsl.out.0000 rsl.error.0000 "${MEAN_DIR}/logs/${t}/" 2>/dev/null

   if [[ ${status} -eq 0 && -s wrfinput_d01 ]] && \
      grep -q "SUCCESS COMPLETE REAL_EM INIT" rsl.out.0000; then
      mv wrfinput_d01 "${out}"
      echo "hour ${h} (${t}): done $(date)"
   else
      echo "hour ${h} (${t}): FAILED (srun status ${status}); see ${MEAN_DIR}/logs/${t}"
      (( nfail++ ))
   fi

done

rm -f met_em.d01.* rsl.out.* rsl.error.*
echo "make_mean_icbc.sh: hours ${first_hour}-${last_hour} finished, ${nfail} failure(s)"
exit $(( nfail > 0 ))
