#!/bin/bash
# Sequential chain: one variant at a time so their I/O does not interfere.
cd $(dirname $0)
prev=
id=$(cd G_io2_32x16 && sbatch --parsable ${prev:+--dependency=afterany:$prev} slurm.wrf); echo "G_io2_32x16 -> job $id"; prev=$id
id=$(cd H_io2_defaultUCX && sbatch --parsable ${prev:+--dependency=afterany:$prev} slurm.wrf); echo "H_io2_defaultUCX -> job $id"; prev=$id
id=$(cd I_quilt4x4_io2_defaultUCX && sbatch --parsable ${prev:+--dependency=afterany:$prev} slurm.wrf); echo "I_quilt4x4_io2_defaultUCX -> job $id"; prev=$id
id=$(cd J_16nodes_io2_16x16 && sbatch --parsable ${prev:+--dependency=afterany:$prev} slurm.wrf); echo "J_16nodes_io2_16x16 -> job $id"; prev=$id
