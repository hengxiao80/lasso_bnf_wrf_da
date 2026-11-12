# Hand-off: "fulltest: D1 analysis"

Written 2026-11-12 at the end of session "fulltest: initial setup part 4". A second hand-off from the same session, `2026-11-12_fulltest_a7_observations.md`, covers the observations for D2; the two can run side by side (that one only adds observation files, this one only reads D1's output). Everything from that session is committed and pushed, with these two hand-offs.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da`. Read `CLAUDE.md`, then `notes/fulltest_workflow.md` (the 50-member setup and where each file lives) and `notes/fulltest_steps.md` D1 (the run's results and the first comparison with run 5).

## Where things stand

- **D1 ran 2026-11-09** and passed: the first gate of the production run `_conv_refl_f2` in `cases/20250520/da_theta_m0_n50/` (50 members, 00:00 cold start + analyses 00:15–01:00, 1 h 20 min, 61 node-hours). All five cycles `complete`, no retries, no CFL lines.
- **First comparison with run 5 `_conv_refl_f2`** (5 members, same observations and settings, `da_theta_m0_n5/output_conv_refl_f2/`), from both runs' `check_cycle.log` only (`fulltest_steps.md` D1, "D1 against run 5"): from 00:30 on D1's 15-min forecasts fit the surface temperature and moisture observations better (METAR T2 0.99 / 1.09 / 1.04 K against 1.06 / 1.34 / 1.14), the analysis fits reflectivity much closer (posterior RMS 5.0 against 6.7 dBZ at 01:00) with 10–26 % fewer radar outliers, the adaptive inflation stays smaller (U mean 1.053 against 1.098 at 01:00), the increments are larger (MU up to 60 %), and the first-minute pressure adjustment after each analysis is 7–18 % larger through 00:45. The runs also differ in their initial perturbations (50 of the 150 bank draws against 5 of 15), and four analyses can't separate that from the ensemble size.
- That comparison came from a parser of `check_cycle.log` in the old session's scratchpad (not kept unless the user decided otherwise): per analysis cycle it read the observation table (prior and posterior RMS/bias, spread, total, QC counts), the domain prior spread (`preassim_sd`), the updated inflation (min / mean / max), the mean increments, the forecast → analysis spread ("over the cycle") and the per-member |dpsfc/dt| lines, and printed the two runs side by side; the shock was summarised by the mean over members (a maximum over 50 is larger than over 5 by sampling alone).

## D1's files (read only)

Per analysis cycle `output_conv_refl_f2/<t>/`:
- `filter/`: `obs_seq.final` (ASCII, 178 MB, with all 50 prior and posterior member values per observation), the `input`, `preassim`, `postassim` and `output` mean and sd, `preassim_member_*` and `postassim_member_*` (50 each), the inflation files, `input.nml`, `filter.log`.
- `memNNN/`: `prior_d01.nc` and `analysis_d01.nc` (DART state fields), `wrfout_d01_<t>` (the state WRF starts from, after `insert`; full history fields), `wrfbdy_d01`, `insert.log`, WRF's rank-0 `rsl` files (`diag_print`'s domain-mean |dpsfc/dt| per step), `cfl_count.txt`.
- `check_cycle.log`, `cycle.log` (the filter job's steps and times).

Difference from run 5: run 5 kept each member's **end-of-segment** `wrfout` (t + 15 min, the forecast, with 65 extra fields), D1 the **start-of-segment** one (t, the analysis). D1's 15-min forecasts exist only as the next cycle's `prior_d01.nc` (DART state fields).

## Possible directions (none started; agree with the user first)

1. **Innovation statistics**, both runs: `.venv/bin/python scripts/da/innovation_stats.py <output dir>` (per type: consistency ratio, implied error, Desroziers' estimate; `notes/obs_error_diagnostics.md`). Does the larger ensemble change the error diagnosis? Its reader loads each `obs_seq.final` whole; memory for the 178-MB files is not known, so measure on one first (login node: 32 GB per user).
2. **Profiles and rank histograms**: DART's `obs_diag` and `obs_seq_to_netcdf` are built (`../software/DART/models/wrf/work/`); ACARS by pressure level; rank histograms of the surface and radar types, which 50 members make meaningful (run 5's 5 do not).
3. **Maps**: mean increments (MU, QVAPOR, `REFL_10CM`), spread and inflation λ (`postassim_priorinf_mean`, where it reaches 2–3), reflectivity analyses against the MRMS observations; and the clear-air reflectivity bias, which grows each cycle in both runs (observation − forecast −0.67, −0.98, −1.25 dBZ at 00:30–01:00, i.e. the forecast lies above the clear-air observations by more each cycle): where, and whether it is spurious echo.
4. **Ensemble size versus initial perturbations**: e.g. a 5-member run started from 5 of D1's 50 initial members (their boundary files exist) would separate the two; a test, with its own cost (run 5: 26 node-hours).
5. **The post-analysis adjustment**: only domain means per step exist (`diag_print`); a spatial view would need more frequent output in a test segment.
6. **Timing summary for the chain** (`fulltest_steps.md` E2).

Verification of model fields against MRMS, GOES and HRRR maps is done in `../bnf_wrf_eval` (its own sessions); here the look is at the DA diagnostics. Where results go (`fulltest_steps.md` D1, or a new note if they grow) and where derived files and figures go: to agree with the user.

## Working rules

- **Never write into `da_theta_m0_n50/run_conv_refl_f2/` or `output_conv_refl_f2/`**: D2 continues from them (the 01:15 restarts, the 01:00 inflation). Derived files go elsewhere.
- No quantitative guesses: derive from a measured run, show the basis, or say "unknown" and measure first (memory `no-unfounded-estimates`).
- Status lines before tool calls are full sentences (what, on what, why). No LaTeX in chat (derivations go into a note). Notes per `~/.claude/rules/typora-markdown.md`.
- The user's go-ahead before every `sbatch`; commits only after the user has reviewed; push only when asked.
- Login nodes: 32 GB per user; open one netCDF file at a time; long runs detached (`setsid nohup`). `command ls` (the `ls` alias adds `-F`); `.venv/bin/python`.

## Starting the session

Name it `fulltest: D1 analysis`, and name this file in the first prompt (`notes/handoffs/2026-11-12_fulltest_d1_analysis.md`).
