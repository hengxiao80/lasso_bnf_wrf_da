# Hand-off: "fulltest: obs_diag"

Written 2026-11-13 at the end of session "fulltest: D1 analysis". It overlaps with `2026-11-13_fulltest_d2_analysis.md` (its directions 3 and 4: innovation statistics, rank histograms): `obs_diag` would be a tool for that analysis. The two can be one session or two; agree with the user which.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da`. Read `CLAUDE.md`, then `notes/fulltest_workflow.md` (the 50-member setup and where each file lives), `notes/fulltest_d1_analysis.md` (D1 against run 5, and our own observation-space statistics) and `notes/obs_error_diagnostics.md` (what `innovation_stats.py` computes).

## Goal

Set up DART's `obs_diag` for the first 6 h of the production run `_conv_refl_f2` (`cases/20250520/da_theta_m0_n50/`): the 24 analyses 05-20 00:15 to 06:00 (D1's 4, D2's 20; D2 is done). The aim is observation-space statistics our own scripts don't give: time series in 15-min bins, vertical profiles (ACARS by pressure, radar by height), regions, and rank histograms with 50 members. Set it up so it can be rerun on D3 and D4.

## Where things stand

- **`obs_diag` has never been run in this project** (checked 2026-11-13). It was built on 2026-10-01 with the other DART programs (`r8 = r4`), at `../software/DART/models/wrf/work/obs_diag` (the `threed_sphere` version), next to `obs_seq_to_netcdf`. No script calls it and no experiment's `config/` has an `&obs_diag_nml`. Earlier plans named it and deferred it: `da_5member_pilot_steps.md` Sec. 3, `da_workflow_layout.md`, `wrf_dart_tutorial_adaptation.md`.
- **What we use instead**, both reading `obs_seq.final` in Python: `check_filter_gate.py obs_report`, which `check_cycle.py` runs every cycle (per type: prior and posterior rms and bias, spread, total spread, QC counts), and `scripts/da/innovation_stats.py` (consistency ratio, implied error, Desroziers' estimate, pooled over cycles). Both pool each type over all levels and the whole domain; neither makes rank histograms.
- **D3 is running** (2026-11-13: cycles to 08:15 complete). It writes the cycles from 06:15 on into the same `output_conv_refl_f2/`, so select D2's files by name.

## What was checked for this hand-off (2026-11-13)

- **Documentation**: `../software/DART/assimilation_code/programs/obs_diag/threed_sphere/obs_diag.rst` (namelist, output variables, rank histograms, trusted obs). Output: one file, `obs_diag_output.nc`.
- **Namelists**: `obs_diag.f90` reads `&obs_diag_nml` itself; the modules it uses read their own. D2's filter `input.nml` (e.g. `output_conv_refl_f2/202505200600/filter/input.nml`) has `&obs_sequence_nml`, `&obs_kind_nml`, `&location_nml`, `&obs_def_radar_mod_nml`, `&utilities_nml` and the rest of filter's blocks, but no `&obs_diag_nml`. Starting from a copy of it plus an `&obs_diag_nml` block is the obvious route; whether `obs_diag` needs anything else is unknown until it runs.
- **The default `&obs_diag_nml`** in `models/wrf/work/input.nml` is for a global case: four regions (hemispheres, tropics, North America), 12-h bins, `create_rank_histogram = .true.`, `outliers_in_histogram = .true.` (the `.rst` gives `.false.` as the default).
- **Vertical coordinates in our `obs_seq.final`** (01:00): radar reflectivity and clear air in height (code 3, metres; e.g. a clear-air obs at 4000 m), ACARS in pressure (code 2, Pa), METAR and mesonet at the surface (code −1). So `plevel_edges` bins ACARS, `hlevel_edges` bins the radar types, and the surface types have one level.
- **Rank histograms**: `Rank_Histogram` in `obs_diag.f90` adds Gaussian noise with the observation-error variance to each member before ranking (fixed seed), as usual.
- **The inputs**: ASCII `obs_seq.final` with 105 copies (observation; prior and posterior mean and spread; 50 prior and 50 posterior members), 98,688 obs at 01:00; 178 MB at D1's times, 182–213 MB in D2 (202 MB at 06:00). `obs_diag` takes a list (`obs_sequence_list`), so the 24 paths can be listed explicitly.
- **Mesonet obs times**: 00:15–01:45 carry float32-rounded times (up to 64 s off, all inside the window), exact times from 02:00 on (`fulltest_steps.md` A7). This matters only for observations near a time-bin edge.
- **Plotting**: DART has only MATLAB scripts (`../software/DART/diagnostics/matlab/`). The plots would be Python, ours. (NCAR's pyDARTdiags package reads `obs_seq` files in Python; not checked or installed.)
- **Not known**: `obs_diag`'s run time and memory on these files. Measure on one file first.

## Decisions for the user

1. **Where the derived files and figures go.** Not in `run_conv_refl_f2/` or `output_conv_refl_f2/` (the run continues from them). One option: `cases/20250520/da_theta_m0_n50/diag_conv_refl_f2/obs_diag/` for the list, `input.nml`, `obs_diag_output.nc` and the log, with the namelist template tracked in `config/` (then add it to `.gitignore`'s allowlist).
2. **Binning**: 15-min bins centred on the analysis times (00:15 to 06:00, `bin_separation` and `bin_width` 15 min), pressure edges for ACARS, height edges for the radar types, and the whole domain as the region (sub-regions later, if wanted).
3. **Where it runs**: the login node (detached if long, `~/.claude/rules/cirrus-detached-loops.md`) or a 1-node Slurm job (go-ahead first), depending on the measured time and memory.
4. **Whether to run it on D1 and run 5 too** (00:15–01:00), for rank histograms of 50 against 5 members (6 bins).

## Suggested steps

1. Read `obs_diag.rst`: the namelist, the output variables (`rmse`, `bias`, `spread`, `totalspread`, the counts `Nposs`, `Nused`, …), which DART QC values count as used, how outliers enter the statistics and the histograms, trusted observations.
2. A script in `scripts/da/` (e.g. `run_obs_diag.sh <output dir> <first time> <last time> <diag dir>`) that writes the file list and `input.nml` (from the run's filter `input.nml` plus the `&obs_diag_nml` template) and runs `obs_diag` in the diagnostics directory.
3. **Test on D1's four cycles** (00:15–01:00), the first under `/usr/bin/time -v` (wall time, peak memory). Check the setup against what we already have: per type and time, `obs_diag`'s prior rms, bias, spread and counts against `check_cycle.log` (`obs_report`) and `innovation_stats.py`. Differences should be explained by the QC selection; the counts per bin should equal each cycle's counts, which also checks the bin edges.
4. Run it on the 24 cycles 00:15–06:00.
5. Python plots of `obs_diag_output.nc`: time series per type, ACARS profiles, radar by height, rank histograms (surface, ACARS, radar). A few test images to the user before a full set (`~/.claude/rules/working-style.md`).
6. Results into a note (where: agree with the user; `fulltest_steps.md` D2 or a new note like `fulltest_d1_analysis.md`).

`obs_seq_to_netcdf` (built, same directory) writes each observation with its location into netCDF; it would serve maps of the innovations, such as the clear-air misfit of `fulltest_d1_analysis.md` Sec. 4.

## Working rules

- **Never write into `da_theta_m0_n50/run_conv_refl_f2/` or `output_conv_refl_f2/`**: the run continues from them. Derived files go elsewhere.
- No quantitative guesses: derive from a measured run, show the basis, or say "unknown" and measure first (memory `no-unfounded-estimates`).
- Status lines before tool calls are full sentences (what, on what, why). No LaTeX in chat (derivations go into a note). Notes per `~/.claude/rules/typora-markdown.md`.
- The user's go-ahead before every `sbatch`; commits only after the user has reviewed; push only when asked.
- Login nodes: 32 GB per user; long work detached (`~/.claude/rules/cirrus-detached-loops.md`). `command ls` (the `ls` alias adds `-F`); `.venv/bin/python`.

## Starting the session

Name it `fulltest: obs_diag`, and name this file in the first prompt (`notes/handoffs/2026-11-13_fulltest_obs_diag.md`).
