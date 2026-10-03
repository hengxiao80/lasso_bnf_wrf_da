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

# --- cycling (pilot step 12) -------------------------------------------------------------
# Cycle times are YYYYMMDDHHMM. cycle(t) = [filter at t, if t > FIRST_CYCLE] + advance t -> t + 15 min
# (notes/da_5member_pilot_steps.md Sec. 1). FIRST_CYCLE is the cold start from run/memNNN/wrfinput_d01.
NUM_ENS=5
FIRST_CYCLE=202505200000
CYCLE_MINUTES=15
# RUN_NAME tells cycling runs of this experiment apart: run${RUN_NAME}/ and output${RUN_NAME}/.
# Step 13 pilots: "" (DART's PH, job 1047814), "_hph" (HYDROSTATIC_PH=1, 1047842), "_hph_d9956"
# (+ INF_DAMPING=0.9956, 1047843), "_hph_f5" (+ INF_FLAVOR=5, 1047844).
RUN_NAME=${RUN_NAME:-}
INIT_DIR=${EXP_DIR}/run                      # memNNN/wrfinput_d01: initial members (step 5), all runs
RUN_DIR=${EXP_DIR}/run${RUN_NAME}            # memNNN/ (latest wrfrst, DART-facing file), filter/
OUTPUT_DIR=${EXP_DIR}/output${RUN_NAME}      # <t>/: status, filter/, memNNN/ (Q10 retention)
OBS_DIR=${EXP_DIR}/obs                       # <t>/obs_seq.out from make_cycle_obs.sh
BDY_DIR=${EXP_DIR}/bdy                       # pristine wrfbdy_d01_memNNN (step 6), never modified
DART_WORK=${SOFTWARE_DIR}/DART/models/wrf/work
SEC_TABLE=${SOFTWARE_DIR}/DART/assimilation_code/programs/gen_sampling_err_table/work/sampling_error_correction_table.nc
GRID_FILE=${MEAN_DIR}/wrfinput_d01_2025-05-20_00_00_00   # filter's wrfinput_d01 (grid and shapes)

# Resources inside the one 40-node allocation (Q7): each member's wrf.exe on 8 nodes,
# 16 x 8 ranks x 8 threads; filter on FILTER_NODES x FILTER_TASKS_PER_NODE ranks (sets
# &ensemble_manager_nml tasks_per_node).
MEMBER_NODES=8
NPROC_X=16
NPROC_Y=8
FILTER_NODES=8
FILTER_TASKS_PER_NODE=16

# 1: wrfrst_dart.py insert --hydrostatic-ph (PH from the analyzed MU, THM, QVAPOR instead of
# DART's PH increment). Default 0 = DART's PH. Step 13 recommends 1 (removes most of the
# post-analysis shock, changes nothing else); the default is not switched yet.
# driver.sh records it in output${RUN_NAME}/settings.txt and refuses to resume a run with another value.
HYDROSTATIC_PH=${HYDROSTATIC_PH:-0}

# Prior inflation damping per cycle (&filter_nml inf_damping, first column); prep_filter.sh writes it
# into the cycle's input.nml. 0.9 = config/input.nml.filter (tutorial value, e-folding ~2.4 h at
# 15-min cycles); 0.9956 gives the tutorial's ~57 h (0.9 per 6 h). Recorded in settings.txt as well.
INF_DAMPING=${INF_DAMPING:-0.9}
# Prior inflation flavor (&filter_nml inf_flavor, first column): 2 = config/input.nml.filter
# (adaptive, sd fixed at inf_sd_lower_bound); 5 = enhanced adaptive (Gharamti 2017), whose sd can
# grow by up to inf_sd_max_change per observation, but only if inf_sd_lower_bound < inf_sd_initial
# (both 0.6 in input.nml.filter, so it stays 0.6; step 13). Written by prep_filter.sh, recorded in
# settings.txt.
INF_FLAVOR=${INF_FLAVOR:-2}
