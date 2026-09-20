#!/bin/bash
# Module environment for building/running WRF/WPS at the pinned commit 06d4240a.
# Mirrors the module set used for the existing verified build at
# /gpfs/wolf2/arm/cli120/proj-shared/sey/bnf/wrf/code/wrf480 (modules2load),
# so our independent build matches its toolchain exactly.
module purge
module load intel/20.0.4
module load openmpi/4.0.4
module load netcdf-wrf/0.1
module load hdf5
module load jasper

export NETCDF=${OLCF_NETCDF_C_ROOT}
export PNETCDF=${OLCF_PARALLEL_NETCDF_ROOT}
export HDF5=${OLCF_HDF5_ROOT}
export JASPERLIB=${OLCF_JASPER_ROOT}/lib64
export JASPERINC=${OLCF_JASPER_ROOT}/include

export WRFIO_NCD_LARGE_FILE_SUPPORT=1
export NetCDF4=0
