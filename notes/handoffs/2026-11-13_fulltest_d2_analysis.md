# Hand-off: "fulltest: D2 analysis"

Written 2026-11-13 at the end of session "fulltest: D1 analysis". It combines three things into one hand-off: the D2-analysis hand-off that session "fulltest: D2 run" wrote earlier the same day under this file name (its content is kept here), the `obs_diag` hand-off of session "fulltest: D1 analysis" (`2026-11-13_fulltest_obs_diag.md`, removed in favour of this file), and what D1's analysis found that bears on D2. The D3 hand-off (`2026-11-13_fulltest_d3_run.md`) can run side by side: this one only reads the first 6 h of the run; that one writes D3's cycles after them.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da`. Read `CLAUDE.md`, then:

- `notes/fulltest_workflow.md`: the 50-member setup and where each file lives;
- `notes/fulltest_steps.md` Sec. 0 (scope: spin-up, control, retention) and Part D (D1's and D2's results, the decisions due at the 6-h gate);
- `notes/fulltest_d1_analysis.md`: D1 against run 5. Sec. 3.1 defines every statistic and the observation sets; Sec. 3.6 is the reflectivity split; Sec. 5 the open questions;
- `notes/obs_error_diagnostics.md`: the implied error and Desroziers' estimate, with the bias term (Eq. 2a, 2b);
- `notes/dart_sampling_error_correction.md`: the sampling-error correction, which matters for 5 against 50 members.

## Goal

A look at the DA diagnostics of the first 6 h of the production run `_conv_refl_f2` in `cases/20250520/da_theta_m0_n50/`: analyses 05-20 00:15 to 06:00, 24 cycles (D1's 4, D2's 20), as material for the decisions due at the 6-h gate. Part of it: setting up DART's `obs_diag` for these 24 cycles, reusable for D3 and D4. What to look at, and where results and figures go: agree with the user first.

## Where things stand (2026-11-13)

- **D2 ran 2026-11-12/13 and passed** (`fulltest_steps.md` D2): all 20 cycles `complete`, `check_cycle.py` passed for each, no retries, no CFL lines in the 1,000 segments, no queue waits; ~16 min per cycle, 252 node-hours. It stopped once, at 02:00, on mesonet obs stamped outside the window (float32 times under `r8 = r4`); fixed and rebuilt (A7, commit `a8ed260`), then resumed.
- **D3 is running** (at 22:30 UTC on 2026-11-13: cycles to 10:15 complete, 10:30 running; the gate ends at 12:00). It writes into the same `output_conv_refl_f2/`.
- **D1's analysis** (`fulltest_d1_analysis.md`) compared 00:15–01:00 with run 5 (5 members, same observations, errors and settings). Run 5 stops at 01:00, so from 01:15 on there is no DA run to compare with; the free run `cases/20250520/theta_m0/` is the control, and model fields against MRMS, GOES and HRRR are compared in `../bnf_wrf_eval` (its own sessions).
- **The weather in the 6 h**: event 1, domain MRMS coverage above 30 dBZ peaking at ~10 % around 03–04Z (`fulltest_steps.md` Sec. 0). Radar reflectivity obs per cycle 78,682–96,700 in D2, rising from 03:30 to 96,700 at 05:30; clear air 8,010–8,502; conventional obs after screening 5,703–9,240 (A7).

## The decisions due at the 6-h gate (the user decides)

From `fulltest_steps.md` Part D and Sec. 0:

- **Thinning for the 12-h and 30-h runs**, including which members' full states are kept for 05-20 12Z to 05-21 05Z (`fulltest_output_files.md` Sec. 1). As written, ~550 GB per analysis cycle (D2: 547–557 GB). For the 30-h run disk quota is not a concern (user, 2026-11-13), so the question is what is worth keeping, not space; the project's quota is unknown, and OLCF's 50 TB doesn't apply to this area (user).
- **A free ensemble** as control (Sec. 0, "Control"; possibly with Q5 option B, Sec. 2).
- **A spin-up variant**: Sec. 0 asks the 6-h gate whether the radar spread still lags. In run 3 the reflectivity prior spread in observation space was 3.1 → 7.3 dBZ against a prior RMS of 9.4 → 12.3 dBZ, with 32–37 % of the radar obs rejected as outliers. If it still lags, a free spin-up (from 05-19 18Z) or a short free advance would be a variant.
- **Nodes per member** (2 now; with 59 nodes free, 29 members ran at once in every array).

The analysis can supply the material for the spin-up question in particular (direction 2 below).

## What D1's analysis found that bears on D2

From `fulltest_d1_analysis.md`, written and corrected in session "fulltest: D1 analysis" (2026-11-12/13):

- **Definitions and selections** (Sec. 3.1). All statistics follow `obs_error_diagnostics.md` Sec. 1: innovation $d_b = y - H(x_b)$, analysis residual $d_a$, spread $s_b$, assigned error $\sigma_o$. Prior-only statistics (rms $d_b$, spread, implied error) over DART QC 0 or 7; statistics involving the analysis (rms $d_a$, Desroziers) over QC 0. The mesonet altimeter is evaluated only (QC 1) and is left out. `check_cycle.log`'s `obs_report` uses QC 0 and 1, so its numbers differ.
- **Comparing two runs needs the observations both assimilated.** The runs reject different outliers (the test depends on each run's spread); one observation assimilated by only one run changed a METAR T2 comparison from −7 % to −11 %, and an ACARS q "result" turned out to be such an artifact. Both runs read the same `obs_seq.joint`, so their `obs_seq.final` list the observations in the same order (checked), and the common set is taken observation by observation. For D2 alone this matters only for comparisons with another run (run 5 at 00:15–01:00, or later runs).
- **Gains** (Sec. 3.1, 3.5). The isolated-observation gain $k = s_b^2/(s_b^2 + \sigma_o^2)$ (one observation assimilated alone) against the realized gain $g$, the fraction of the innovation the whole analysis removed. Desroziers' estimate is exact only when $g$ equals the optimal gain $g_{\mathrm{opt}} = \sigma_b^2/\operatorname{mean}(d_b^2)$, which needs the true prior error and is unknown; the spread gives a lower bound on it when the ensemble is underdispersive.
- **Reflectivity** (Sec. 3.6). Its implied error (3.1 times the assigned 5.24 dBZ in D1) is mostly prior error the ensemble doesn't represent, not MRMS error: precipitation obs exist only where MRMS has at least 10 dBZ and the forward operator is floored at −10 dBZ, so missed or misplaced storms give large positive innovations (bias +8.8 dBZ); outliers were 30 % of the obs but 71 % of the summed $d_b^2$; at 54 % of the obs the observed value was above all 50 prior members. Per cycle over the 24 cycles, these numbers are the spin-up material.
- **The 50-member analyses draw much closer to the observations than run 5's** (Sec. 2, 3.2), as the sampling-error correction predicts (it keeps 12 % of a regression at sample correlation 0.5 with 5 members, 89 % with 50). Realized reflectivity gains were 1.6–1.9 times the isolated-observation gain in D1 (dense radar obs reinforce each other).
- **Scripts** (2026-11-13, from the session's scratchpad; they reproduce every number of the D1 note's Sec. 3.2–3.6): `scripts/da/obs_space_stats.py` (per cycle and pooled, one run or two side by side, the selections of Sec. 3.1, `--csv`) and `scripts/da/refl_innovation_split.py` (the Sec. 3.6 split per cycle and pooled). Both select the cycles with `--first`/`--last`. A parser of `check_cycle.log` (direction 1) doesn't exist yet.

## The run's files (read only)

Per analysis cycle `cases/20250520/da_theta_m0_n50/output_conv_refl_f2/<t>/` (layout as in D1; `fulltest_workflow.md` Sec. 1.2):

- `filter/`: `obs_seq.final` (ASCII, 105 copies: the observation, prior and posterior mean and spread, 50 prior and 50 posterior members; 178 MB at D1's times, 182–213 MB in D2), the `input`, `preassim`, `postassim` and `output` mean and sd, `preassim_member_*` and `postassim_member_*` (50 each), the inflation files, `input.nml`, `filter.log`.
- `memNNN/`: `prior_d01.nc` and `analysis_d01.nc` (DART state fields), `wrfout_d01_<t>` (the state WRF starts from, after `insert`), `wrfbdy_d01`, `insert.log`, WRF's rank-0 `rsl` files (`diag_print`'s domain-mean |dpsfc/dt| per step), `cfl_count.txt`.
- `check_cycle.log`, `cycle.log` (the filter job's steps and times).

A 15-min forecast exists only as the next cycle's `prior_d01.nc` (DART state fields). The 00:00 directory holds the cold start.

Things to know about the data:

- **Select the cycles by time**: D3 writes from 06:15 on into the same directory. The two new scripts take `--first`/`--last`; `innovation_stats.py` reads every cycle it finds, so give it a directory of links to the wanted `obs_seq.final` files (as D1's analysis did).
- **Mesonet obs times**: at 00:15–01:45 the mesonet obs carry their float32-rounded times (up to 64 s off, all inside the window); from 02:00 on their exact times (A7). Filter doesn't use times within a window; this matters only when binning by time.
- 02:00's `cycle.log` still has the `ERROR` line of the failed first attempt; its `filter/` and members hold the rerun's results.
- `innovation_stats.py` took 3.6 s and 1.2 GB per `obs_seq.final` on the login node (D1).

## `obs_diag` (checked 2026-11-13)

- **Never run in this project.** Built on 2026-10-01 with the other DART programs (`r8 = r4`): `../software/DART/models/wrf/work/obs_diag` (the `threed_sphere` version), next to `obs_seq_to_netcdf`. No script calls it; no experiment's `config/` has an `&obs_diag_nml`. Earlier plans named it and deferred it (`da_5member_pilot_steps.md` Sec. 3, `da_workflow_layout.md`, `wrf_dart_tutorial_adaptation.md`).
- **What it would add** to our Python statistics, which pool each type over all levels and the whole domain: time series in 15-min bins, vertical profiles (ACARS by pressure, radar by height), regions, and rank histograms with 50 members. One output file, `obs_diag_output.nc`.
- **Documentation**: `../software/DART/assimilation_code/programs/obs_diag/threed_sphere/obs_diag.rst` (namelist, output variables, rank histograms, trusted obs).
- **Namelists**: `obs_diag.f90` reads `&obs_diag_nml`; its modules read their own. D2's filter `input.nml` (e.g. `output_conv_refl_f2/202505200600/filter/input.nml`) has `&obs_sequence_nml`, `&obs_kind_nml`, `&location_nml`, `&obs_def_radar_mod_nml`, `&utilities_nml` and the rest of filter's blocks, but no `&obs_diag_nml`; a copy of it plus an `&obs_diag_nml` block is the obvious start. Whether `obs_diag` needs anything else is unknown until it runs.
- **The default `&obs_diag_nml`** in `models/wrf/work/input.nml` is for a global case: four regions (hemispheres, tropics, North America), 12-h bins, `create_rank_histogram = .true.`, `outliers_in_histogram = .true.` (the `.rst` gives `.false.` as the default).
- **Vertical coordinates in our `obs_seq.final`**: radar reflectivity and clear air in height (code 3, metres), ACARS in pressure (code 2, Pa), METAR and mesonet at the surface (code −1). So `plevel_edges` bins ACARS, `hlevel_edges` the radar types, and the surface types have one level.
- **Rank histograms**: `Rank_Histogram` in `obs_diag.f90` adds Gaussian noise with the observation-error variance to each member before ranking (fixed seed), as usual.
- **Inputs**: `obs_diag` takes a list (`obs_sequence_list`), so the 24 paths can be listed explicitly.
- **Plotting**: DART has only MATLAB scripts (`../software/DART/diagnostics/matlab/`), so the plots would be Python, ours. (NCAR's pyDARTdiags package reads `obs_seq` files in Python; not checked or installed.)
- **Not known**: run time and memory on these files. Measure on one file first.
- `obs_seq_to_netcdf` (built, same directory) writes each observation with its location into netCDF, for maps of the innovations (e.g. the clear-air misfit, `fulltest_d1_analysis.md` Sec. 4).

Suggested steps for it:

1. Read `obs_diag.rst`: the namelist, the output variables (`rmse`, `bias`, `spread`, `totalspread`, the counts `Nposs`, `Nused`, …), which DART QC values count as used, how outliers enter the statistics and the histograms, trusted observations.
2. A script in `scripts/da/` (e.g. `run_obs_diag.sh <output dir> <first time> <last time> <diag dir>`) that writes the file list and `input.nml` and runs `obs_diag` in the diagnostics directory.
3. Test on D1's four cycles (00:15–01:00), the first under `/usr/bin/time -v`. Check against what exists: per type and time, `obs_diag`'s prior rms, bias, spread and counts against `check_cycle.log` and `innovation_stats.py`; differences should be explained by the QC selection, and the counts per bin should equal each cycle's counts (which also checks the bin edges).
4. Run it on the 24 cycles 00:15–06:00.
5. Python plots of `obs_diag_output.nc`: time series per type, ACARS profiles, radar by height, rank histograms (surface, ACARS, radar). A few test images to the user before a full set (`~/.claude/rules/working-style.md`).

## Possible directions (none started; agree with the user first)

1. **Time series over the 24 cycles** from each cycle's `check_cycle.log`: per observation type the prior and posterior RMS and bias, spread and total spread, QC counts; the domain prior spread; the updated inflation (min / mean / max); the mean increments; forecast → analysis spread; the per-member |dpsfc/dt| (post-analysis shock). D1's analysis used a parser in its scratchpad that wasn't kept; one in `scripts/da/` would serve D3 and D4 too.
2. **Radar spread and outliers per cycle** (the spin-up question): from `check_cycle.log` (all points and echo columns) and, per cycle, the split of `fulltest_d1_analysis.md` Sec. 3.6 (`scripts/da/refl_innovation_split.py`): outlier share of the obs and of the summed $d_b^2$, the share above all members, the bias, prior spread against rms $d_b$, isolated-observation against realized gain.
3. **Innovation statistics**, per cycle and pooled: `scripts/da/obs_space_stats.py` (the selections of the D1 note's Sec. 3.1; `--csv` for time-series plots); `scripts/da/innovation_stats.py` pools only.
4. **`obs_diag`** (section above): profiles, time series, rank histograms.
5. **D1's open questions** (`fulltest_d1_analysis.md` Sec. 5): why the adaptive inflation is smaller than run 5's; the clear-air misfit, which grew each cycle in D1 (maps, `obs_seq_to_netcdf`); whether to keep the sampling-error correction at 50 members; a test of the correction's share (needs `sbatch`). Raised in session "fulltest: D1 analysis" but not in a note: an estimate of the prior error independent of the ensemble, from the covariance of innovations against the distance between observations (Hollingsworth–Lönnberg), for the dense mesonet and radar types.
6. **Timing summary for the chain** (`fulltest_steps.md` E2), if wanted: D2's numbers came from `sacct` and `cycle.log` (Part D, D2).

## Decisions for the user, before starting

1. What to look at first (directions above), and in which order.
2. Where derived files and figures go. Not in `run_conv_refl_f2/` or `output_conv_refl_f2/`. One option: `cases/20250520/da_theta_m0_n50/diag_conv_refl_f2/` (e.g. `obs_diag/` in it), with tracked templates in `config/` (then add them to `.gitignore`'s allowlist). Results in `fulltest_steps.md` D2 or a new note like `fulltest_d1_analysis.md`.
3. For `obs_diag`: the binning (15-min bins centred on the analysis times, pressure edges for ACARS, height edges for the radar types, the whole domain as the region), where it runs (login node, detached if long, or a 1-node Slurm job, after measuring one file), and whether to run it on D1 and run 5 too (rank histograms of 50 against 5 members).

## Working rules

- **Never write into `da_theta_m0_n50/run_conv_refl_f2/` or `output_conv_refl_f2/`**: the run continues from them. Derived files go elsewhere.
- No quantitative guesses: derive from a measured run, show the basis, or say "unknown" and measure first (memory `no-unfounded-estimates`).
- Status lines before tool calls are full sentences (what, on what, why). No LaTeX in chat (derivations go into a note). Notes per `~/.claude/rules/typora-markdown.md`.
- The user's go-ahead before every `sbatch`; commits only after the user has reviewed; push only when asked.
- Login nodes: 32 GB per user; open one netCDF file at a time; long work detached (`~/.claude/rules/cirrus-detached-loops.md`). `command ls` (the `ls` alias adds `-F`); `.venv/bin/python`.

## Starting the session

Name it `fulltest: D2 analysis`, and name this file in the first prompt (`notes/handoffs/2026-11-13_fulltest_d2_analysis.md`).
