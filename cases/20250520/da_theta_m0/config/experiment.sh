#!/bin/bash
# Experiment settings for the case-20250520 WRF-DART cycling experiment (theta_m0 setup:
# hybrid_opt = 0, use_theta_m = 0). Sourced by the scripts in scripts/da/. This is the
# project's counterpart of the tutorial's param.sh; it grows as the workflow is built
# (see notes/da_workflow_layout.md). Paths are absolute so jobs can source it from anywhere.

# --- locations -------------------------------------------------------------------------
PROJECT_DIR=/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da
SOFTWARE_DIR=/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/software
CASE_DIR=${PROJECT_DIR}/cases/20250520
EXP_DIR=${CASE_DIR}/da_theta_m0
CONFIG_DIR=${EXP_DIR}/config

WPS_OUT_DIR=${CASE_DIR}/wps                  # met_em.d01.YYYY-MM-DD_HH:00:00.nc (73 hourly files)
WRF_RUN_DIR=${SOFTWARE_DIR}/WRF/run          # real.exe, wrf.exe and WRF run-time tables
MEAN_DIR=${EXP_DIR}/mean                     # unperturbed HRRR-based wrfinput per hour + wrfbdy

# Existing 72-h boundary file from the theta_m0 real.exe run (same namelist, 72 hourly
# records, 2025-05-19 00Z to 05-22 00Z). Reused rather than regenerated.
MEAN_BDY_SOURCE=${CASE_DIR}/theta_m0/real/wrfbdy_d01

# --- case times ------------------------------------------------------------------------
CASE_START=2025051900        # first met_em / boundary time (YYYYMMDDHH)
CASE_NHOURS=72               # hours covered by met_em and wrfbdy after CASE_START

# --- perturbation bank (WRFDA RANDOMCV, CV3) --------------------------------------------
WRFDA_DIR=${SOFTWARE_DIR}/WRFDA              # da_wrfvar.exe in var/build, be.dat.cv3 in var/run
PERTS_DIR=${EXP_DIR}/perts                   # work/draw_NNN (one WRFDA run per draw), bank/ later
PERT_DATE=2025052000                         # fg = mean wrfinput at this time (pilot start)
