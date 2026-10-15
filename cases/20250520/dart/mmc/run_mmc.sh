#!/bin/bash
#SBATCH -A cli120
#SBATCH -p batch_all
#SBATCH -N 1
#SBATCH -t 00:30:00
#SBATCH -J mmc
#SBATCH -o mmc_%j.log
cd "${SLURM_SUBMIT_DIR}"
source /gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da/scripts/env_wrf.sh
export OMP_NUM_THREADS=1
/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/software/DART/models/wrf/work/model_mod_check
