#!/bin/bash
# Sequential chain: one variant at a time so their I/O does not interfere.
cd $(dirname $0)
prev=
id=$(cd K_io2_classic_16nodes && sbatch --parsable ${prev:+--dependency=afterany:$prev} slurm.wrf); echo "K_io2_classic_16nodes -> job $id"; prev=$id
