# 50-member full test: steps

The steps from the 5-member pilot to the first 50-member cycling runs over the LES window. Written 2026-11-06 in session "fulltest: initial setup" (hand-off `notes/handoffs/2026-11-06_fulltest_initial_setup.md`), after the scope was agreed with the user that day (Sec. 0). The steps (Sec. 1) are taken one at a time in this order, each with the user's go-ahead; a gate is a hard stop. Open items are in Sec. 2, decisions made along the way in Sec. 3.

Related notes: `fulltest_output_files.md` (what is kept per cycle, and sizes), `da_cycle_file_flow.md` (how the member files are made and changed in the current scripts), `da_5member_pilot_steps.md` (the pilot's steps and decisions Q1–Q18), `obs_expansion.md` Sec. 9 (runs 1–5).

## 0. Scope (user, 2026-11-06)

| topic | decision |
|---|---|
| start | 05-20 00Z cold start, 15-min cycles |
| gates | 1, 6, 12 and 30 h (to 05-21 06Z) |
| setup | `theta_m0`, `hybrid_opt = 0`, 1 + 4 |
| other settings | as run 5 `_conv_refl_f2` |
| inflation | flavor 2 |
| spin-up | none: the cycling from 00Z |
| ensemble | 50 members, 150 bank draws, option A |
| layout | member job array + filter job per cycle |
| retention | everything for the 1-h and 6-h gates |
| control | the existing `theta_m0` free run |

- **Window and gates.** The two 500-m runs to compare against (sey's `test1/20250520lassobnfwrfhrrr3/rund2`, forced by the free 2.5-km run, and `20250520lassobnfwrfhrrr4/rund2`, forced by hourly HRRR) cover 05-20 12Z to 05-21 05Z, so the cycling has to be settled by 12Z and run through 05Z. Domain-wide MRMS coverage above 30 dBZ (bnf_wrf_eval's `timeseries.png`): event 1 peaks at ~10 % around 05-20 03–04Z, quiet ~1.5–2 % from 10Z to 18Z, event 2 at 4–5 % from 18Z to 05-21 ~10Z. Starting at 00Z gives 12 h of cycling through event 1 before the LES window. The 1-h step lines up cycle for cycle with run 5. A later step continues the same run (`driver.sh` resumes from the last complete cycle) unless a setting changes; then a new `RUN_NAME` starts from 00Z.
- **Setup.** The full test stays in `theta_m0` (`use_theta_m = 0`), `hybrid_opt = 0`, with the 1 + 4 boundary zone. The moist-theta conversion (`use_theta_m = 1`, the target), the hybrid coordinate (`hybrid_opt = 2`, as in sey's 500-m runs) and the 1 + 9 boundary zone are a separate work package, done before the production DA runs, then plugged in and the runs repeated (Sec. 2). Theta- and coordinate-specific code is kept in a few clearly marked places, so the switch touches little else. Facts behind this: stock DART's `model_mod.f90` refuses `USE_THETA_M = 1`; it reads `HYBRID_OPT = 2` (C1H/C2H in the density), but `pert_wrf_bc` and `update_wrf_bc` couple with MU + MUB only (`module_couple_uv.f90:83`, `pert_wrf_bc.f90:479`), the `hybrid_opt = 0` form, and DART's tutorial and scripts require `hybrid_opt = 0` (DART Issue #807). Keeping 1 + 4 keeps the existing free run a valid control; Q18's plan to switch the 50-member DA to 1 + 9 moves into the work package.
- **Settings from run 5** (`output_conv_refl_f2/settings.txt`, `obs_expansion.md` Sec. 9): observation set `OBS_NAME=_meso_a_calmkeep_mrms` (MADIS METAR, ACARS, radiosondes, marine; mesonet option a with calm winds kept; MRMS reflectivity with HRRRDAS settings), `MRMS_FILTER=one_pass` (`input.nml.filter_joint`, `obs_impact_joint.txt`), `outlier_threshold = 3`, sampling-error correction on, localization 300 km / 0.5 scale height (conventional) and 18 km / 0.5 scale height (radar), the patched METAR and mesonet observation errors, `HYDROSTATIC_PH=1`.
- **Inflation.** Flavor 2 (adaptive prior inflation, sd fixed at 0.6, damping 0.9, bounds [1, 5]), the `experiment.sh` defaults. Flavor 5 gets its root-choice patch and a test later; RTPS stays an option (hand-off note).
- **Spin-up** as in the 5-member runs: cold start at 00Z from the mean state (`real.exe` from HRRR's 00Z analysis), first analysis at 00:15. The 6-h gate looks at whether the radar spread still lags: in run 3 the reflectivity prior spread in observation space was 3.1 → 7.3 dBZ against a prior RMS of 9.4 → 12.3 dBZ, and 32–37 % of the radar obs were rejected as outliers (run 5 at 01:00 the same). A free spin-up (from 05-19 18Z) or a short free advance would then be a variant.
- **Ensemble.** 150 WRFDA RANDOMCV draws (3 × 50; 135 more, ~4 node-hours, ~36 GB). Boundary option A of Q5: each member keeps one bank draw for its initial state and every boundary hour. Option B (distinct draws per hour) stays open as an experiment (Sec. 2). Tutorial amplitudes (Q3: 1.3 for U, V, THM, QVAPOR; 0.6 for MU) and centering (Q4) carry over.
- **Layout.** Per cycle, a Slurm job array of 50 member jobs (8 nodes each, short time limit) and a 40-node filter job with `--dependency=afterany` on the array, which checks the members, runs filter and submits the next cycle; an 8-node job starts as soon as 8 nodes are idle. Nodes per member and filter nodes are set after the measurements (Part C). `batch_all` (2026-11-06): 116 nodes of 128 cores (100 × 256 GB, 16 × 512 GB); priority by queue age only (fair-share and job-size weights 0), counted from when a job becomes eligible; no per-user job or node limits. A persistent 40-node core job that also runs members, with extra member jobs picking up the rest, is the fallback if the filter job's queue waits grow.
- **Retention.** `fulltest_output_files.md`: everything for the 1-h and 6-h gates, the thinning for the 12-h and 30-h runs decided at the 6-h gate. The older 5-member runs and `tests/` are kept. No known quota: OLCF's documentation gives 50 TB, a 90-day purge and no backups for standard Open project areas (`/gpfs/wolf/[projid]/proj-shared`), but `/gpfs/wolf2/arm/` is not documented (files untouched since 2026-06-25 are still there).
- **Control.** The existing free run `cases/20250520/theta_m0/` (05-19 00Z to 05-22 00Z, 1 + 4). It starts a day earlier than the DA, so at 05-20 00Z it is a 24-h forecast, not the DA's starting state; its namelist differs from the members' only in times, domain lists, I/O and `diag_print`. Whether a free ensemble is run is decided at the 6-h gate.

## 1. Steps

### Part A: inputs

**A1. Experiment directory. Done 2026-11-06** (user's layout). Building 50 members in the 5-member directory would have overwritten its `run/` (the initial members every 5-member run starts from), `perts/members/`, `perts/assignment.txt` and `bdy/`. Now, in `cases/20250520/`:
- `da_common_theta_m0/`: the inputs shared by the `theta_m0` experiments, moved there from the 5-member directory: `mean/` (87 GB), `perts/bank/` and `perts/work/` (24 GB), the five observation sets `obs*/` (0.4 GB). The draws' `fg` links in `perts/work/draw_NNN/` point to its `mean/`.
- `da_theta_m0_n5/`: the 5-member experiment, renamed from `da_theta_m0`, which is now a link to it. It links the common inputs back in under the old names (`mean`, `obs*`, `perts/bank`, `perts/work`; relative links) and keeps its `config/`, `perts/members/`, `perts/assignment.txt`, `run/`, `bdy/`, runs and tests. `EXP_DIR` in its `experiment.sh` names the new directory.
- `da_theta_m0_n50/`: the full test; so far only the same links, with `perts/` a directory of its own holding the `bank` and `work` links.

Checked after the move: file and link counts and bytes of every moved directory identical through the old paths and through `da_theta_m0_n50`; every path `experiment.sh` builds resolves, as do the paths recorded in a finished run (`obs_seq.out.path`, the filter directory's links). The 83 broken links in `da_theta_m0_n5/` all point to per-cycle files the workflow deletes (restart and boundary files in old run and test directories), none into the moved directories. Still to do for the full test (A2): its `config/`; `make_cycle_obs.sh`, `make_cycle_mesonet.sh` and `download_mrms.sh` source `da_theta_m0/config/experiment.sh` by absolute path, which still works through the link (they write into the common observation sets). New small files under `cases/` need adding to the `.gitignore` allowlist (`da_theta_m0_n50/config/` is covered by `cases/*/da_*/config/*`).

**A2. Five-member assumptions. Done 2026-11-06.** Grep of `scripts/da/`, the job scripts and the filter namelists. In the cycle scripts the ensemble size is a parameter (`NUM_ENS` → `members()` in `cycle_lib.sh`, `check_cycle.py --nmem`); the 5s are in the configs and in the defaults of the Python tools, which A5 and A6 override (`--nmem`, `--hours`). `prep_filter.sh` sets `tasks_per_node` from `FILTER_TASKS_PER_NODE`. The sampling-error correction table has rows for 3 to 200 members.
- `da_theta_m0_n50/config/`: copies of the 5-member files the one-pass full test uses. `experiment.sh`: `EXP_DIR`, `NUM_ENS=50` and comments changed; resources kept until Part C, `GRID_FILE` until A4. `input.nml.filter_joint`: `ens_size`, `num_output_state_members` and `num_output_obs_members` 50. `obs_impact_joint.txt`, `namelist.input.wrf`, `iofields_cycle.txt` unchanged (B1 changes the last two). Not copied: the two-pass files (`input.nml.filter`, `input.nml.filter_mrms`, `obs_impact_conv.txt`, `obs_impact_mrms.txt`), so a run without MRMS or with `MRMS_FILTER=two_pass` stops in `prep_filter.sh` for want of its namelist; `assignment.txt` (the git copy of `perts/assignment.txt`, made at A5).
- Shared configs (user): the three files that make the shared inputs, `namelist.input.real` (mean states), `namelist.input.3dvar` (bank) and `input.nml.obs_preprocess` (observation sets), moved with `git mv` to `da_common_theta_m0/config/`, with relative links in both experiments' `config/`. The scripts read them as `CONFIG_DIR/<file>` with `sed`, `cp` and `[ -f ]`, which follow links; their contents through `da_theta_m0`, `da_theta_m0_n5` and `da_theta_m0_n50` are identical to the committed files. A4's `iofields_real.txt` goes there too.
- Shared scripts: `innovation_stats.py` now takes a run's output directory as well as a bare run name (looked up in the 5-member experiment, as before); both forms give the same table for `output_hph`. Left as they are: `make_cycle_obs.sh`, `make_cycle_mesonet.sh` and `download_mrms.sh` source the 5-member `experiment.sh` through the `da_theta_m0` link and use only shared settings from it (the observation sets, `mean/`, `input.nml.obs_preprocess`, `GRID_FILE` for the terrain); `select_mesonet_cycle.py` (default terrain file through the link; `make_cycle_mesonet.sh` always passes `GRID_FILE`); `summarize_cycle_timing.py` (an example path in its docstring).
- Not copied: `slurm.cycle`. Its one 40-node allocation runs each member's segment as an 8-node step beside the others, so at 50 members only 5 segments could run at a time; B2 replaces it. The job scripts of A3, A4 and A6 are written at those steps.
- For later steps: `cycle_job.sh`, `prep_filter.sh` and `post_filter.sh` start one step per member inside the allocation (B2); `check_cycle.py` reads each member's prior and analysis one after another (its time at 50 members: C2); `obs_seq.final` is ASCII and will carry 50 members' prior and posterior values per observation (its size, and the time `read_obs_seq` takes in `check_cycle.py`: C3).

**A3. Bank.** Draws 16–150 into the shared bank: `slurm.pert_draw` as an array (one node, 16 ranks per draw, which a draw's reproducibility depends on; seeds `MMDDHH` and 10 × draw; ~1.7 min per draw), then `wrfda_bank_diff.py` and `check_wrfda_draw.py`.
- Job script `da_theta_m0_n50/slurm.pert_draw` (2026-11-06): one array task per draw runs `run_wrfda_draw.sh`, then `wrfda_bank_diff.py` and `check_wrfda_draw.py` for that draw (report in `work/draw_NNN/check_wrfda_draw.txt`), and logs the seeds of ranks 0 and 15; logs in `da_theta_m0_n50/logs/`. Seeds: WRFDA's second seed is `seed_array2 × seed_array1 + rank × 10⁷` (`da_random_seed.inc`), at most 1500 × 52000 + 15 × 10⁷ = 2.28 × 10⁸ < 2³¹ for draw 150; two (draw, rank) pairs give the same seed only if their draws are a multiple of 250 apart, so all 150 × 16 are distinct.
- **Reproducibility test passed** (job 1194357, 2026-11-06, 2 min 21 s): draw 1 rerun into `da_theta_m0_n50/tests/pert_draw_repro/` (deleted after the bank check, user) under the module setup of 2026-10-30 (`Core/A100`; the first MPI job under it). `wrfvar_output` byte-identical to the pilot's (job 1047356), `pert_bank_001.nc` identical in all variables (the `fg` attribute names the mean file by its new path), the check report identical; `da_wrfvar.exe` 1 min 36 s, 7.1 GB per rank, as in the pilot.
- **Done 2026-11-06.** Draws 16–150: array job 1194358 (`--array=16-150%30`), 19:32 to 19:44, all 135 tasks `COMPLETED` with complete logs; `da_wrfvar.exe` 1 min 35 s to 2 min 25 s per draw. Bank: 150 files `pert_bank_001…150.nc`, 36 GB. The `wrfvar_output` of all 150 draws (1.36 GB each, 190 GB) deleted after the bank check (user, 2026-11-06): only the bank files are read from here on, and a draw can be rerun bit for bit (the test above). `work/draw_NNN/` keeps the namelist, logs and, for draws 16–150, the check report (21 MB in all).
- **Bank check** (`scripts/da/check_bank.py`, new; output `da_common_theta_m0/perts/bank_check.txt`; 1 min 44 s on the login node with 4 processes). All checks passed:
  - seeds: 2400 distinct (`seed_array1`, `seed_array2`) pairs for 150 draws × 16 ranks, each as WRFDA's formula gives; largest `seed_array2` 2.28 × 10⁸;
  - the 135 new reports: the changed variables are U V PH T THM MU P PSFC QVAPOR, and T = THM in the output;
  - no non-finite values; RMS over the domain (unscaled) U 0.37–0.68 m/s, V 0.42–0.69 m/s, THM 0.80–0.96 K, QVAPOR 0.24–0.35 g/kg, MU 40–126 Pa, no draw outside 0.5–2 × the median; median of the new draws / median of draws 1–15: 0.99, 0.97, 0.99, 1.01, 0.92; the median RMS by level of the new draws follows that of the old within the draw-to-draw scatter;
  - correlation between draws over the horizontal field (U THM QVAPOR at levels 5, 30, 60, 90 and MU; 11,175 pairs): mean −0.004 to +0.007 for every field and level, the same for old–old, old–new and new–new pairs; sd 0.15–0.19 (QVAPOR), 0.23–0.27 (THM, MU), 0.30–0.44 (U).
  - U at level 90 (~14.6 km) has the largest sd (0.44, about 5 independent samples per field) and 74 pairs with |r| > 0.9 (max 0.983). Not repeated draws: the six most correlated of those pairs correlate −0.29 to +0.14 over the whole 3-D fields, and their median |r| over levels is 0.23–0.42 in U (ad hoc check). At that level the U perturbation is close to one domain-wide pattern, so the members' U perturbations there span only a few directions whatever the draws.

**A4. `GRID_FILE` clean-up** (user, 2026-11-06: before the members). `real.exe` writes `REFL_10CM` itself, so the plain mean 00Z `wrfinput` can be filter's `wrfinput_d01` again. Steps from `obs_expansion.md` Sec. 9, run 1: (1) `da_common_theta_m0/config/iofields_real.txt` with `+:i:0:REFL_10CM` (linked into both experiments' `config/`, as the other shared configs since A2), `iofields_filename` in `namelist.input.real` (there too), linked in by `make_mean_icbc.sh`; (2) keep the current file as `mean/wrfinput_d01_2025-05-20_00_00_00.pre_refl`, rerun `real.exe` for 05-20 00Z (`FIRST_HOUR=24 LAST_HOUR=24 sbatch slurm.make_mean_icbc`, ~3 min on 4 nodes); (3) check all 198 variables bit-identical to the old file, plus `REFL_10CM`; (4) `GRID_FILE` back to the plain mean 00Z `wrfinput` in both experiments' `experiment.sh` (`make_cycle_mesonet.sh` takes its terrain from the 5-member one's), delete `scripts/da/make_grid_file.py` and `mean/dart_wrfinput_d01_2025-05-20_00_00_00`, update `obs_expansion.md`, `da_cycle_file_flow.md` and the `CLAUDE.md` gotcha. Not during a run: every cycle's `prep_filter.sh` reads `GRID_FILE`.
- **Done 2026-11-06.** (1) `da_common_theta_m0/config/iofields_real.txt` (`+:i:0:REFL_10CM`), linked into both experiments' `config/`; `iofields_filename = 'iofields_real.txt'` in `namelist.input.real`; `make_mean_icbc.sh` copies the file the namelist names into its work directory and saves it with each hour's logs. Job script `da_theta_m0_n50/slurm.make_mean_icbc` (the pilot's, with the 50-member `experiment.sh`, the hours required, 30 min).
- (2) Old file and logs kept as `mean/wrfinput_d01_2025-05-20_00_00_00.pre_refl` (deleted after the checks, user) and `mean/logs/2025052000.pre_refl/` (kept); job 1194517 (4 nodes, 1 min 14 s; `real.exe` 74 s, the first under `Core/A100`): `SUCCESS COMPLETE REAL_EM INIT`, "Setting input stream 0 for refl_10cm".
- (3) New file against the old: all 198 variables bit-identical, dimensions and global attributes identical, `REFL_10CM` added (float32, `Time bottom_top south_north west_east`, zeros). Against the old `GRID_FILE` (`dart_wrfinput`): identical in all 199 variables, `REFL_10CM`'s attributes included. DART read test on the login node: `fill_inflation_restart` with run 5's 00:15 `input.nml`, member 1's `prior_d01.nc` and the new file as `wrfinput_d01` finished, and its `input_priorinf_{mean,sd}.nc` equal run 5's at 00:15 in all 43 variables (only the creation dates differ).
- (4) `GRID_FILE` is the mean 00Z `wrfinput` in both `experiment.sh` files; `scripts/da/make_grid_file.py` and `mean/dart_wrfinput_d01_2025-05-20_00_00_00` deleted (the `F/wrfinput_d01` links in the 5-member run directories now point nowhere; `prep_filter.sh` remakes them each cycle). `obs_expansion.md` Sec. 9 run 1, `da_cycle_file_flow.md` Sec. 1 and the `CLAUDE.md` gotcha updated.

**A5. Assignment and initial members.** `assign_perturbations.py --nmem 50` (50 distinct draws of the 150, fixed seed; scaled, centered), then `make_initial_members.py --nmem 50`. Checks as in pilot step 5: centering, spread by level, clipped QVAPOR, hydrostatic PH.

**A6. Member boundaries.** 31 hourly records, 05-20 00Z to 05-21 07Z (the last cycle also advances 15 min), option A. **Design point first:** a member's file holds ~0.15 GB per record (2 records: 0.30 GB; the 72-record mean file: 9.28 GB), so 31 records are ~4.5 GB. Every cycle, `refit_member_bdy.sh` copies the whole file to refit one record, WRF reads it, and `post_filter.sh` saves the refit copy in `output<RUN>/<t>/memNNN/`: ~220 GB written per cycle at 50 members, and ~220 GB more kept per cycle (`fulltest_output_files.md` Sec. 3 assumes 0.33 GB per member). Proposed: pristine boundary files split into one-record files per hour, and each cycle refits and saves only the record holding t. To test first: that WRF runs every segment of an hour from that hour's one-record file, including the one ending on the hour, where it may want the next record (then two records per file, the one holding t and the next). Then `build_member_bdy.py` (`slurm.member_bdy`), with the checks of pilot step 6.

**A7. Observations for the 120 analyses** (05-20 00:15 to 05-21 06:00), into `da_common_theta_m0/obs_meso_a_calmkeep_mrms/`: `download_mrms.sh` per analysis time (login node; ~28 MB per time), `make_cycle_mesonet.sh` (option a, calm winds kept), then `make_cycle_obs.sh` with `MESONET=a_calmkeep MRMS=hrrrdas`. MADIS is already converted for every hour of 05-20 and 05-21 (`cases/20250520/obs/obs_seq_madis/`).

### Part B: workflow changes

**B1. Output** (`fulltest_output_files.md` Sec. 1): `write_hist_at_0h_rst = .true.` in `namelist.input.wrf` (`history_interval` stays 15: the history alarm at the end of a segment makes Thompson compute `REFL_10CM` for the restart); keep the start-of-segment `wrfout` (the analysis; at the cold start the 00:00 one) and delete the end-of-segment one; drop `iofields_filename`, `ignore_iofields_warning` and the copy of `iofields_cycle.txt` (default history stream only); `num_output_state_members = 50`, `num_output_obs_members = 50`.

**B2. Job structure.** A member job (one array task per member and cycle: analysis into the restart file and boundary refit, the 15-min segment, extraction for the next filter) and a filter job (filter directory, filter, save, checks, submission of the next cycle, stop at the run's end time), chained with `--dependency=afterany`; resumable from the last complete cycle; each job type keeps its MPI settings (UCX, hcoll) and exit guard. First a small test job: whether `sbatch` works from a compute node.

**B3. Test of the chain** before the 1-h gate, in a form to be agreed (e.g. the 00:00 advance and the 00:15 analysis on a few members).

### Part C: measurements

**C1. WRF segment on 1, 2, 4 and 8 nodes** (one member's 15-min restart segment, from run 5's files). The first WRF job under `Core/A100` (`env_wrf.sh` since 2026-10-30): check its logs with that in mind.

**C2. The per-member Python steps** timed one by one (`extract`, `qnrain`, `insert`, refit), and with several per node. At 5 members they took ~100–150 s (update) and ~85 s (extraction) on one node each, longer than the 130-s WRF segment on 8 nodes.

**C3. Filter gate at 50 members:** time and memory on 40 and ~80 nodes (`tasks_per_node` matching the ranks per node). Run 5's filter used 1.9 GB per task on 40 × 32 and 63–94 s in the observation loop for ~95,000 observations at 5 members; the loop grows about in proportion to the ensemble size.

Then: nodes per member and filter nodes.

### Part D: gated runs

Each run is a production run: the user's go-ahead before it, even after a successful test.

**D1. 1 h** (00:00 cold start + 4 analyses), compared with run 5 `_conv_refl_f2`: spread, fits, inflation, post-analysis shock, cost. ~1.6 TB.

**D2. 6 h.** Decisions due: thinning for the 12-h and 30-h runs (including which members' full states are kept for 05-20 12Z to 05-21 05Z), a free ensemble, a spin-up variant (radar spread), nodes per member. ~8.8 TB.

**D3. 12 h**: the state at the start of the LES window.

**D4. 30 h**, to 05-21 06Z.

### Part E

**E1. A new workflow-layout note** from the actual full-test workflow, in place of `da_workflow_layout.md` (the 2026-09-25 plan, left as it is).

## 2. Open items

- **W in the state** (Q8): W is in the state as `NO_COPY_BACK`; in DART's serial EAKF it changes no other variable's update and costs ~17 % more state. Keep or drop for 50 members.
- **The separate work package**, before the production DA runs:
  - `use_theta_m = 1`: the moist/dry conversion (plan Step 1B1); DART's `model_mod` guard; `wrfrst_dart.py` (extract dry theta, rebuild THM, the moist equation of state for P); moist `T` in the member boundaries.
  - `hybrid_opt = 2`: hybrid coupling in `pert_wrf_bc` and `update_wrf_bc`; the hydrostatic PH increment and the P/AL recompute in our scripts; an audit of `model_mod`.
  - 1 + 9: `spec_zone = 1`, `relax_zone = 9` in `namelist.input.wrf` and the free control's namelist; `obs_boundary = 10` in `input.nml.obs_preprocess` and the same in `mrms_to_obs_seq.py` (`--obs-boundary`, best passed from one setting); `obsdistbdy` to review. A new free control with the same setup.
- **Q5 option B** (distinct bank draws per hour), possibly with a free ensemble.
- **Flavor-5 patch and RTPS**, later (user).

## 3. Decisions

- **2026-11-06 (user):** the scope in Sec. 0; the retention in `fulltest_output_files.md` Sec. 1; the `GRID_FILE` clean-up before the members (A4); 1 + 4 kept for the full test, 1 + 9 moved into the separate work package (Q18 had planned 1 + 9 for the 50-member DA); the directory layout of A1 (`da_common_theta_m0/`, `da_theta_m0_n5/` with the link `da_theta_m0`, `da_theta_m0_n50/`), with the shared inputs linked into each new experiment.
- **2026-11-06 (user, A2):** the configs that make the shared inputs (`namelist.input.real`, `namelist.input.3dvar`, `input.nml.obs_preprocess`) live in `da_common_theta_m0/config/`, linked into each experiment's `config/`, rather than as copies per experiment.
