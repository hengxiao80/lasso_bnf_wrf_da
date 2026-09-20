#!/bin/bash
# Sequential chain: one variant at a time so their I/O does not interfere.
cd $(dirname $0)
prev=
id=$(cd A_base_io11 && sbatch --parsable ${prev:+--dependency=afterany:$prev} slurm.wrf); echo "A_base_io11 -> job $id"; prev=$id
id=$(cd B_decomp32x16 && sbatch --parsable ${prev:+--dependency=afterany:$prev} slurm.wrf); echo "B_decomp32x16 -> job $id"; prev=$id
id=$(cd C_16nodes_16x16 && sbatch --parsable ${prev:+--dependency=afterany:$prev} slurm.wrf); echo "C_16nodes_16x16 -> job $id"; prev=$id
id=$(cd D_quilt4x4_io11 && sbatch --parsable ${prev:+--dependency=afterany:$prev} slurm.wrf); echo "D_quilt4x4_io11 -> job $id"; prev=$id
id=$(cd E_quilt4x4_io2 && sbatch --parsable ${prev:+--dependency=afterany:$prev} slurm.wrf); echo "E_quilt4x4_io2 -> job $id"; prev=$id
id=$(cd F_sync_io2 && sbatch --parsable ${prev:+--dependency=afterany:$prev} slurm.wrf); echo "F_sync_io2 -> job $id"; prev=$id
