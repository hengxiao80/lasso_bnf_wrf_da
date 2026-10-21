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
# Observation sets: make_cycle_obs.sh writes ${OBS_DIR}/<t>/obs_seq.out, the cycles read it. obs/ is the
# step 13 set (MADIS families, METAR with DART's land errors, built 2026-10-02); a new set gets its own
# OBS_NAME, and make_cycle_obs.sh records its contents in ${OBS_DIR}/obs_settings.txt.
# Sets so far: obs_madis (MADIS families, NCEP METAR errors; reference for the mesonet/MRMS tests),
# obs_meso_a_calmkeep (+ mesonet a, calm kept).
# Since 2026-10-14 every run needs REFL_10CM in the restart files (it is in the state of all three filter
# namelists), i.e. restarts written by the patched wrf.exe, so new runs start from the 00Z cold start.
OBS_NAME=${OBS_NAME:-}
OBS_DIR=${EXP_DIR}/obs${OBS_NAME}            # <t>/obs_seq.out from make_cycle_obs.sh
# Mesonet (obs_expansion.md Sec. 7.2): none, or <option>_calm<calm> as in make_cycle_mesonet.sh
# (a_calmkeep, a_calmdrop, b1_calmkeep, ...). Used by make_cycle_obs.sh only.
MESONET=${MESONET:-none}
# MRMS reflectivity (obs_expansion.md Sec. 8): none, or hrrrdas (mrms_to_obs_seq.py with HRRRDAS's
# settings). Used by make_cycle_obs.sh, which writes <t>/obs_seq.mrms and records mrms=... in
# obs_settings.txt (and <t>/obs_seq.joint, the merge with obs_seq.out). A run on such a set takes it
# as MRMS_FILTER says.
MRMS=${MRMS:-none}
# How filter takes MRMS in a run whose observation set has it (no default; recorded in settings.txt):
#   two_pass: as HRRRDAS, filter with config/input.nml.filter (conventional obs), then with
#             config/input.nml.filter_mrms (MRMS) on the result; MRMS_INFLATION below.
#   one_pass: one filter with config/input.nml.filter_joint on <t>/obs_seq.joint (conventional + MRMS,
#             merged by make_cycle_obs.sh), per-type localization for the radar types and the impact
#             table config/obs_impact_joint.txt (same restrictions as the two passes); one inflation.
# Must be unset in runs without MRMS.
MRMS_FILTER=${MRMS_FILTER:-}
# Prior inflation in a two-pass run (no default; undecided, user 2026-10-14; obs_expansion.md Sec. 8.4):
#   pass1: adaptive prior inflation (INF_FLAVOR, INF_DAMPING) in the conventional pass only, carried
#          from cycle to cycle as in a one-pass run; the MRMS pass has no inflation (inf_flavor 0).
#   both:  the MRMS pass reads the conventional pass's updated inflation, inflates and updates it once
#          more; the next cycle starts from the MRMS pass's. The spread is then inflated twice per cycle.
#          Whether the MRMS pass damps it first: MRMS_PASS2_DAMPING below.
# Must be unset in other runs (one_pass, or no MRMS). Recorded in settings.txt.
MRMS_INFLATION=${MRMS_INFLATION:-}
# With MRMS_INFLATION=both only (user, 2026-10-15): 1 (default) = the MRMS pass damps the inflation it
# reads with INF_DAMPING too, as the first pass does, so the inflation is damped twice per cycle
# (effectively INF_DAMPING^2 per cycle); 0 = inf_damping 1.0 in the MRMS pass (damped once per cycle).
# Recorded in settings.txt for MRMS_INFLATION=both; ignored otherwise.
MRMS_PASS2_DAMPING=${MRMS_PASS2_DAMPING:-1}
BDY_DIR=${EXP_DIR}/bdy                       # pristine wrfbdy_d01_memNNN (step 6), never modified
DART_WORK=${SOFTWARE_DIR}/DART/models/wrf/work
SEC_TABLE=${SOFTWARE_DIR}/DART/assimilation_code/programs/gen_sampling_err_table/work/sampling_error_correction_table.nc
GRID_FILE=${MEAN_DIR}/wrfinput_d01_2025-05-20_00_00_00   # filter's wrfinput_d01 (grid and shapes)

# Resources inside the one 40-node allocation (Q7): each member's wrf.exe on 8 nodes,
# 16 x 8 ranks x 8 threads; filter on FILTER_NODES x FILTER_TASKS_PER_NODE ranks, one CPU each
# (prep_filter.sh sets &ensemble_manager_nml tasks_per_node). Filter on 40 x 32 since 2026-10-20 (user;
# step 13 used 8 x 16): conventional pass at 00:30 with the observation loop 97 s -> 10 s, analyses
# bit-identical to 8 x 16 (obs_expansion.md Sec. 9, scaling test job 1054411). Not recorded in
# settings.txt, since the analyses don't depend on it; overridable from sbatch's environment.
MEMBER_NODES=8
NPROC_X=16
NPROC_Y=8
FILTER_NODES=${FILTER_NODES:-40}
FILTER_TASKS_PER_NODE=${FILTER_TASKS_PER_NODE:-32}

# 1: wrfrst_dart.py insert --hydrostatic-ph (PH from the analyzed MU, THM, QVAPOR instead of
# DART's PH increment); 0 = DART's PH. Default 1 since 2026-10-03 (user, after step 13: it removes
# most of the post-analysis shock and changes nothing else). The first pilot (output/, DART's PH)
# can only be resumed with HYDROSTATIC_PH=0, which settings.txt enforces.
# driver.sh records it in output${RUN_NAME}/settings.txt and refuses to resume a run with another value.
HYDROSTATIC_PH=${HYDROSTATIC_PH:-1}

# Prior inflation damping per cycle (&filter_nml inf_damping, first column); prep_filter.sh writes it
# into the cycle's input.nml. 0.9 = config/input.nml.filter (tutorial value, e-folding ~2.4 h at
# 15-min cycles); 0.9956 gives the tutorial's ~57 h (0.9 per 6 h). Recorded in settings.txt as well.
INF_DAMPING=${INF_DAMPING:-0.9}
# Prior inflation flavor (&filter_nml inf_flavor, first column): 2 = config/input.nml.filter
# (adaptive, sd fixed at inf_sd_lower_bound); 5 = enhanced adaptive (Gharamti 2017), whose sd can
# grow by up to inf_sd_max_change per observation, but only if inf_sd_lower_bound < inf_sd_initial
# (both 0.6 by default, so it stays 0.6, as in step 13; see INF_SD_LOWER_BOUND). Written by
# prep_filter.sh, recorded in settings.txt.
INF_FLAVOR=${INF_FLAVOR:-2}
# Lower bound of the prior inflation sd (&filter_nml inf_sd_lower_bound, first column); prep_filter.sh
# writes it into each pass that inflates. 0.6 = the namelists' value = the initial sd
# (fill_inflation_restart, prior_inf_sd), so the sd never changes, with flavor 2 or 5 (step 13).
# Below 0.6 (> 0) the sd can evolve: with flavor 2 it can only shrink towards the bound; with
# flavor 5 it can also grow (an update that would raise it by more than inf_sd_max_change = 1.05 is
# skipped, per observation). Recorded in settings.txt when not 0.6.
INF_SD_LOWER_BOUND=${INF_SD_LOWER_BOUND:-0.6}
