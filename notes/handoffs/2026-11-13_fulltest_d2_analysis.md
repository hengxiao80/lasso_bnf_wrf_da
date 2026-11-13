# Hand-off: "fulltest: D2 analysis"

Written 2026-11-13 at the end of session "fulltest: D2 run". The other hand-off of that session, `2026-11-13_fulltest_d3_run.md` (the 12-h gate), can run side by side: this one only reads the first 6 h of the run, that one writes D3's cycles after them.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da`. Read `CLAUDE.md`, then `notes/fulltest_workflow.md` (the 50-member setup and where each file lives), `notes/fulltest_steps.md` Sec. 0 (scope: spin-up, control, retention) and Part D (D1's and D2's results, the decisions due at the 6-h gate), and `notes/fulltest_d1_analysis.md` (D1 against run 5: method, results, open questions).

## Goal

A look at the DA diagnostics of the first 6 h of the production run `_conv_refl_f2` in `cases/20250520/da_theta_m0_n50/`: analyses 05-20 00:15 to 06:00, 24 cycles (D1's 4, D2's 20), as material for the decisions due at the 6-h gate. What to look at, and where results and figures go: agree with the user first.

## Where things stand (2026-11-13)

- **D2 ran 2026-11-12/13 and passed** (`fulltest_steps.md` D2): all 20 cycles `complete`, `check_cycle.py` passed for each, no retries, no CFL lines in the 1,000 segments, no queue waits; ~16 min per cycle, 252 node-hours. It stopped once, at 02:00, on mesonet obs stamped outside the window (float32 times under `r8 = r4`); fixed and rebuilt (A7, commit `a8ed260`), then resumed.
- **D1's analysis** (`fulltest_d1_analysis.md`) compared 00:15–01:00 with run 5 (5 members, same observations and settings). Run 5 stops at 01:00, so from 01:15 on there is no DA run to compare with; the free run `cases/20250520/theta_m0/` is the control, and model fields against MRMS, GOES and HRRR are compared in `../bnf_wrf_eval` (its own sessions).
- **The weather in the 6 h**: event 1, domain MRMS coverage above 30 dBZ peaking at ~10 % around 03–04Z (Sec. 0). Radar reflectivity obs per cycle 78,682–96,700 in D2, rising from 03:30 to 96,700 at 05:30; clear air 8,010–8,502; conventional obs after screening 5,703–9,240 (A7).

## The decisions due at the 6-h gate (the user decides)

From `fulltest_steps.md` Part D and Sec. 0:

- **Thinning for the 12-h and 30-h runs**, including which members' full states are kept for 05-20 12Z to 05-21 05Z (`fulltest_output_files.md` Sec. 1). As written, ~550 GB per analysis cycle (D2: 547–557 GB). For the 30-h run disk quota is not a concern (user, 2026-11-13), so the question is what is worth keeping, not space; the project's quota is unknown, and OLCF's 50 TB doesn't apply to this area (user).
- **A free ensemble** as control (Sec. 0, "Control"; possibly with Q5 option B, Sec. 2).
- **A spin-up variant**: Sec. 0 asks the 6-h gate whether the radar spread still lags. In run 3 the reflectivity prior spread in observation space was 3.1 → 7.3 dBZ against a prior RMS of 9.4 → 12.3 dBZ, with 32–37 % of the radar obs rejected as outliers. If it still lags, a free spin-up (from 05-19 18Z) or a short free advance would be a variant.
- **Nodes per member** (2 now; with 59 nodes free, 29 members ran at once in every array).

The analysis can supply the material for the spin-up question in particular: reflectivity prior spread against prior RMS and the outlier fraction, cycle by cycle over the 24 cycles.

## The run's files (read only)

Per analysis cycle `cases/20250520/da_theta_m0_n50/output_conv_refl_f2/<t>/` (layout as in D1; `fulltest_workflow.md` Sec. 1.2):

- `filter/`: `obs_seq.final` (ASCII, 182–213 MB in D2, all 50 prior and posterior member values per observation), the `input`, `preassim`, `postassim` and `output` mean and sd, `preassim_member_*` and `postassim_member_*` (50 each), the inflation files, `input.nml`, `filter.log`.
- `memNNN/`: `prior_d01.nc` and `analysis_d01.nc` (DART state fields), `wrfout_d01_<t>` (the state WRF starts from, after `insert`), `wrfbdy_d01`, `insert.log`, WRF's rank-0 `rsl` files (`diag_print`'s domain-mean |dpsfc/dt| per step), `cfl_count.txt`.
- `check_cycle.log`, `cycle.log` (the filter job's steps and times).

A 15-min forecast exists only as the next cycle's `prior_d01.nc` (DART state fields). The 00:00 directory holds the cold start.

Things to know about the data:

- **Mesonet obs times**: at 00:15–01:45 the mesonet obs carry their float32-rounded times (up to 64 s off, all inside the window); from 02:00 on their exact times (A7). Filter doesn't use times within a window; this matters only when binning by time.
- 02:00's `cycle.log` still has the `ERROR` line of the failed first attempt; its `filter/` and members hold the rerun's results.
- D3 may be running while this session works: it writes the cycles from 06:15 on into the same `output_conv_refl_f2/`. Select the cycles by time (D1's analysis used a directory of links).

## Possible directions (none started; agree with the user first)

1. **Time series over the 24 cycles** from each cycle's `check_cycle.log`: per observation type the prior and posterior RMS and bias, spread and total spread, QC counts; the domain prior spread; the updated inflation (min / mean / max); the mean increments; forecast → analysis spread; the per-member |dpsfc/dt| (post-analysis shock). D1's analysis used a parser in its scratchpad that wasn't kept; one in `scripts/da/` would serve D3 and D4 too.
2. **Radar spread and outliers per cycle** (the spin-up question above), all points and echo columns (`check_cycle.py` prints both).
3. **Innovation statistics**, per cycle and pooled: `scripts/da/innovation_stats.py` (`obs_error_diagnostics.md` Sec. 7); 3.6 s and 1.2 GB per `obs_seq.final` on the login node (D1).
4. **D1's open questions** (`fulltest_d1_analysis.md` Sec. 5): rank histograms with 50 members (surface and radar types); why the adaptive inflation is smaller than run 5's; the clear-air misfit, which grew each cycle in D1 (maps); whether to keep the sampling-error correction at 50 members.
5. **Timing summary for the chain** (`fulltest_steps.md` E2), if wanted: D2's numbers came from `sacct` and `cycle.log` (Part D, D2).

## Working rules

- **Never write into `da_theta_m0_n50/run_conv_refl_f2/` or `output_conv_refl_f2/`**: the run continues from them. Derived files go elsewhere.
- No quantitative guesses: derive from a measured run, show the basis, or say "unknown" and measure first (memory `no-unfounded-estimates`).
- Status lines before tool calls are full sentences (what, on what, why). No LaTeX in chat (derivations go into a note). Notes per `~/.claude/rules/typora-markdown.md`.
- The user's go-ahead before every `sbatch`; commits only after the user has reviewed; push only when asked.
- Login nodes: 32 GB per user; open one netCDF file at a time; long work detached (`~/.claude/rules/cirrus-detached-loops.md`). `command ls` (the `ls` alias adds `-F`); `.venv/bin/python`.

## Starting the session

Name it `fulltest: D2 analysis`, and name this file in the first prompt (`notes/handoffs/2026-11-13_fulltest_d2_analysis.md`).
