#!/bin/bash
# run_wrfda_draw.sh - one WRFDA RANDOMCV (CV3) draw for the perturbation bank.
#
# Usage (inside a Slurm allocation; see cases/<case>/da_*/slurm.pert_draw):
#   run_wrfda_draw.sh <experiment.sh> <draw_number>
#
# Runs da_wrfvar.exe in ${PERTS_DIR}/work/draw_NNN with
#   fg       = ${MEAN_DIR}/wrfinput_d01 at ${PERT_DATE} (unperturbed HRRR-based state)
#   be.dat   = ${WRFDA_DIR}/var/run/be.dat.cv3
#   namelist = ${CONFIG_DIR}/namelist.input.3dvar with the time and the seeds filled in:
#              seed_array1 = MMDDHH of PERT_DATE, seed_array2 = 10 * draw_number.
# Seeds: WRFDA seeds Fortran's random_seed (2 elements with ifort) with (seed_array1,
# seed_array2*seed_array1 + rank*1e7) (var/da/da_define_structures/da_random_seed.inc). The tutorial's
# seed_array1 = YYYYMMDDHH overflows that product in 32-bit integers, so we use MMDDHH (05-20 00Z -> 52000;
# 52000*150 + 15e7 < 2^31). Because the rank enters the seed, a draw is reproducible only with the same
# number of MPI ranks: keep 16 (slurm.pert_draw) for the whole bank.
# The output wrfvar_output (fg + random perturbation) stays in the work directory; the bank file
# (output - fg for U, V, THM, QVAPOR, MU, as in the tutorial) is made in a later step (wrfda_bank_diff.py).
# Replaces the per-draw part of the tutorial's gen_pert_bank.sh. See notes/da_5member_pilot_steps.md
# steps 3-4.

set -uo pipefail

if [[ $# -ne 2 ]]; then
   echo "usage: $0 <experiment.sh> <draw_number>"
   exit 2
fi
source "$1"
draw=$2

: "${SLURM_JOB_ID:?run this inside a Slurm allocation (it uses srun)}"
WRFDA_NTASKS=${WRFDA_NTASKS:-${SLURM_NTASKS}}

yyyy=${PERT_DATE:0:4}; mm=${PERT_DATE:4:2}; dd=${PERT_DATE:6:2}; hh=${PERT_DATE:8:2}
fg=${MEAN_DIR}/wrfinput_d01_${yyyy}-${mm}-${dd}_${hh}_00_00
seed1=$(( 10#${PERT_DATE:4:6} ))       # MMDDHH, see the header
seed2=$(( 10 * 10#${draw} ))
work=${PERTS_DIR}/work/draw_$(printf %03d "$((10#${draw}))")

for f in "${fg}" "${WRFDA_DIR}/var/build/da_wrfvar.exe" "${WRFDA_DIR}/var/run/be.dat.cv3" \
         "${CONFIG_DIR}/namelist.input.3dvar"; do
   [[ -r $f ]] || { echo "missing $f"; exit 1; }
done
if [[ -e ${work}/wrfvar_output ]]; then
   echo "${work}/wrfvar_output exists; remove the directory to rerun this draw"
   exit 1
fi

mkdir -p "${work}"
cd "${work}" || exit 1
rm -f rsl.* namelist.input namelist.output fg be.dat da_wrfvar.exe

ln -s "${WRFDA_DIR}/var/build/da_wrfvar.exe" da_wrfvar.exe
ln -s "${WRFDA_DIR}/var/run/be.dat.cv3" be.dat
ln -s "${fg}" fg
# WRF run-time tables (LANDUSE.TBL etc.), as the tutorial copies its whole WRF_RUN directory
for f in "${WRFDA_DIR}"/run/*.TBL; do
   [[ -e $(basename "$f") ]] || ln -s "$f" .
done

sed -e '/^!/d' -e "s/@YYYY@/${yyyy}/g" -e "s/@MM@/${mm}/g" -e "s/@DD@/${dd}/g" -e "s/@HH@/${hh}/g" \
    -e "s/@SEED1@/${seed1}/g" -e "s/@SEED2@/${seed2}/g" \
    "${CONFIG_DIR}/namelist.input.3dvar" > namelist.input

echo "draw ${draw}: fg=${fg} seed_array1=${seed1} seed_array2=${seed2} ntasks=${WRFDA_NTASKS}"
date
srun -n "${WRFDA_NTASKS}" ./da_wrfvar.exe > da_wrfvar.log 2>&1
status=$?
date

if [[ ${status} -ne 0 ]] || [[ ! -s wrfvar_output ]] || \
   ! grep -q "WRF-Var completed successfully" rsl.out.0000 2>/dev/null; then
   echo "draw ${draw}: FAILED (srun status ${status}); see ${work}/rsl.error.0000"
   exit 1
fi
rm -f wrfvar_output_randomcv.e*      # WRFDA's identical copy of wrfvar_output (1.4 GB)
echo "draw ${draw}: done, ${work}/wrfvar_output"
