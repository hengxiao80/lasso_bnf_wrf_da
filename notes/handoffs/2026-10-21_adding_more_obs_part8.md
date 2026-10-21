# Hand-off: "Adding more obs part 8": run 4 and the inflation tests

Written 2026-10-21 at the end of session "Adding more obs part 7" (runs 1–3, the MRMS scaling test, the grid-file
fix). Everything from that session is committed (`2f08a18`, `fe23312`, and this hand-off); only the two Dowell PDFs
in `notes/` are untracked, as before. No jobs running.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup).
- Read `CLAUDE.md` first. New there since part 7: the grid-file gotcha (every DART state variable must be in
  filter's `wrfinput_d01`) and the rewritten exit-hang gotcha.
- Main working note: `notes/obs_expansion.md` **Sec. 9**: run plan, the timing table (step 13 baseline, runs 1–3),
  results of runs 1–3 and of the MRMS scaling test, and the decisions of 2026-10-21. MRMS design: Sec. 8.4 (two-pass),
  8.5 (one-pass).
- Namelist decisions: `notes/dart_namelist_discussion_log.md`, latest entries 2026-10-15 (MRMS inflation, pass-2
  damping, flavor 5 / `INF_SD_LOWER_BOUND`) and 2026-10-21 (search boxes, radar outlier check).
- Side investigation, possibly running in another session: `notes/handoffs/2026-10-21_filter_exit_hang.md` (filter
  and `wrf.exe` hang after finishing). **Check first what it found or changed** (its note `notes/filter_exit_hang.md`
  if written, `git log`), especially any change to `slurm.cycle`, `scripts/da/cycle_lib.sh` or
  `scripts/da/run_wrf_segment.sh`.
- Previous hand-off: `notes/handoffs/2026-10-20_adding_more_obs_part7.md`.

## Where things stand (2026-10-21)

- **Runs 1–3 passed** (1-hour, 5 members, cold start 00:00, analyses 00:15–01:00, filter 40 × 32):

  | run | `RUN_NAME` | observations | filter | job | wall |
  |---|---|---|---|---|---|
  | 1 | `_madis` | `obs_madis/` (MADIS, NCEP METAR errors) | one pass | 1054633 + 1054795 | 39 min after the resume |
  | 2 | `_meso_a` | `obs_meso_a_calmkeep/` (+ mesonet option a) | one pass | 1054801 | 44 min |
  | 3 | `_madis_mrms1p` | `obs_madis_mrms/` (+ MRMS) | `MRMS_FILTER=one_pass` | 1054809 | 73 min (27 min of a `wrf.exe` hang) |

  Run 3's radar: reflectivity QC-7 32 / 37 / 37 / 36 % per cycle; prior fit worsening (RMS 9.4 → 12.3 dBZ, bias
  +3.9 → +4.8), posterior steady ~7 dBZ; obs-space spread 3.1 → 7.3 dBZ; post-analysis |dpsfc/dt| (max of steps 2–4)
  308 / 500 / 632 / 732 hPa/3h, growing each cycle, back to 89–93 by minutes 5–15 as in runs 1–2.
- **MRMS scaling test** (job 1054799): radar pass ~0.2 ms/ob, ~1 min of filter; 283 × 144 search boxes 26 % faster
  with bit-identical analyses; 40 × 64 slower than 40 × 32.
- **Decided (user, 2026-10-21):** 283 × 144 boxes in `input.nml.filter_mrms` and `input.nml.filter_joint` (done;
  `input.nml.filter` keeps 71 × 36); `outlier_threshold = 3` for all types in runs 3–4; **run 4 uses
  `MRMS_INFLATION=both`**, details to decide (below); the impact table keeps conventional → `QTY_RADAR_REFLECTIVITY`
  at 0; no `--time` change for MRMS runs (2 h is ample).
- **Grid file (interim):** `GRID_FILE` = `mean/dart_wrfinput_d01_2025-05-20_00_00_00` (`scripts/da/make_grid_file.py`:
  the mean 00Z `wrfinput` plus `REFL_10CM`). **To do after run 4 (user):** `real.exe` writes `REFL_10CM` itself
  (runtime I/O `+:i:0:REFL_10CM`), rerun for 05-20 00Z only, check bit-identity, `GRID_FILE` back to the plain mean
  file, delete the interim script and file; steps in `obs_expansion.md` Sec. 9 (under run 1). Not during a run.
- **Exit hangs:** filter hung in 15 of 21 multi-node runs since 10-20, on 256-GB nodes too; the guard in `run_filter`
  handles it (costs ~30 s). **`wrf.exe` hung once** (run 3, member 005, 00:45 → 01:00): it printed "SUCCESS COMPLETE
  WRF", wrote complete outputs, and didn't exit. There is **no `wrf.exe` guard**. Proposed (not written, user to decide,
  unless the side investigation fixed the cause): in `run_wrf_segment.sh`, once SUCCESS is in `rsl.out.0000`, give the
  step 30 s, then, if no file in the run directory changed for 30 s, stop that member's `srun` (two SIGINTs; five
  `wrf.exe` steps run at once, so not by step name), log "wrf exit guard", leave a marker file; test on the login node
  with stand-ins, as for the filter guard.
- **Disk:** each 1-hour run takes ~0.4 TB (`output<RUN_NAME>/` ~330 GB, `run<RUN_NAME>/` ~77 GB); runs 1–3 ~1.2 TB,
  `output_hph/` 249 GB. The step 13 runs were trimmed after a user decision (`notes/da_5member_pilot_steps.md`,
  "Files kept"); ask before deleting anything.

## Goal

Run 4 (two-pass MRMS), then the inflation and damping tests the user asked about, one at a time, recording timing and
results in `obs_expansion.md` Sec. 9 as for runs 1–3.

| order | what | command (from `cases/20250520/da_theta_m0/`) | needs before |
|---|---|---|---|
| 1 | Decide the `wrf.exe` guard (and pick up any fix from the hang session) | – | user |
| 2 | **Run 4**, MRMS two passes, `MRMS_INFLATION=both` | `OBS_NAME=_madis_mrms MRMS_FILTER=two_pass MRMS_INFLATION=both RUN_NAME=_madis_mrms2p sbatch slurm.cycle 202505200000 202505200100` (+ `MRMS_PASS2_DAMPING=0` if chosen) | user's go-ahead and choice of details |
| 3 | Inflation / damping tests | to decide with the user (candidates below) | run 4 |
| 4 | `real.exe` `REFL_10CM` grid file (interim fix out) | Sec. 9, run 1's to-do | run 4 done, no run going |
| 5 | Run 5, everything (`obs_meso_a_calmkeep_mrms/` is built) | to decide | runs 1–4 |

**Run 4 details, as recommended at the end of part 7 (not yet decided by the user):** keep everything else as in
runs 1–3 so that run 4 differs from run 3 only in one vs two passes: `MRMS_PASS2_DAMPING=1` (the 10-15 default: pass 2
damps the inflation it reads from pass 1 again, effectively `INF_DAMPING`² per cycle, which partly offsets inflating
the spread twice per cycle; `0` = damped once, as in runs 1–3), `INF_DAMPING=0.9`, `INF_FLAVOR=2`,
`INF_SD_LOWER_BOUND=0.6`. Settings are recorded in `output<RUN_NAME>/settings.txt`, and `driver.sh` refuses to resume
a run with different ones.

**Candidate tests (the user named damping and inflation; none chosen yet).** All are per-run environment settings
(`config/experiment.sh`), no code changes. Each run needs its own `RUN_NAME`; propose names and confirm them:
- `INF_DAMPING=0.9956` (the tutorial's time scale for 15-min cycles; step 13's `_hph_d9956` is the only earlier test).
- `MRMS_PASS2_DAMPING=0` vs `1` under `both`.
- `INF_FLAVOR=5` with `INF_SD_LOWER_BOUND` < 0.6 (the sd can evolve; step 13's `_hph_f5` used flavor 5 with sd fixed
  at 0.6). No value chosen; DART's guide: smaller bounds make the inflation vary more slowly.
- `MRMS_INFLATION=pass1` (no inflation in the MRMS pass) as the other two-pass variant.
- Later, not decided: a radar outlier threshold off (`-1`) or ~5. In a two-pass run that is `&quality_control_nml` in
  `input.nml.filter_mrms` only (a namelist edit); in one pass it needs `enable_special_outlier_code` and a patch to
  `quality_control_mod.f90`.
Things to compare between runs: radar QC-7 fraction and prior/posterior fits per cycle, prior spread of the
hydrometeors and `REFL_10CM`, the inflation fields (`check_cycle.log`), the post-analysis |dpsfc/dt| (steps 2–4 and
minutes 5–15), conventional fits.

## After each run

1. `slurm.cycle.<job>.out`: every cycle `complete`, `driver: done`; "filter exit guard" lines; nodes
   (`sacct -j <job> -X --format=NodeList`).
2. **Watch for a `wrf.exe` hang while it runs** (until a guard exists): a `wrf.exe` step running much longer than
   ~2.5 min. If `tail -1 run<RUN_NAME>/memNNN/wrf/rsl.out.0000` is "wrf: SUCCESS COMPLETE WRF" and the new `wrfrst`
   (13,261,878,800 bytes) is no longer changing, `scancel <job>.<step>` (step id from `sacct -j <job>`) lets the cycle
   go on normally. Done once on 2026-10-21 (step 1054809.51). Tell the user.
3. Per-cycle checks: `output<RUN_NAME>/<t>/check_cycle.log` (QC counts per type, increments, spread, inflation, NaNs,
   CFL, |dpsfc/dt|); two-pass runs have a block per pass.
4. Timing: `.venv/bin/python scripts/da/summarize_cycle_timing.py cases/20250520/da_theta_m0/output<RUN_NAME>`
   (columns `prep` and `srun` per pass since 2026-10-21; `*` = guard fired); add the rows to the run table in Sec. 9.
5. Radar QC per pass: `.venv/bin/python scripts/da/check_filter_gate.py obs <obs_seq.final>`.
6. Record results in Sec. 9 as they come; a discussion-log entry whenever `input.nml` settings, obs errors,
   localization or inflation come up.

## Open questions for the user

- The `wrf.exe` exit guard (above).
- Run 4's details (`MRMS_PASS2_DAMPING`; the rest as runs 1–3?).
- Which inflation / damping tests, in which order, with which `RUN_NAME`s.
- Disk: keep or trim the outputs of runs 1–3 (~1.2 TB).
- Later: radar outlier threshold variant; run 5's contents; job structure for the extension / 50 members (step 14).

## Working rules

- **Jobs:** the user's go-ahead before every `sbatch`; one step at a time; report each result. `sbatch --test-only`
  checks a script without queuing it.
- **Environment:** `source scripts/env_wrf.sh` before DART or WRF tools; Python is `.venv/bin/python`. In Claude Code's
  shell `find` is `bfs` (no relative `-newermt`), `ls` is aliased with `-F` (use `command ls`).
- **Don't change files a running job uses** (each cycle re-reads the scripts and configs), nor `GRID_FILE` during a run.
- **Notes:** results and decisions as they come (Sec. 9); discussion-log entries for namelist matters.
- **Locations:** never modify `sey/`; observation downloads under `cases/20250520/obs/`; external repos in
  `../software/`; hand-offs in `notes/handoffs/`.
- **Git:** work and commit directly on `main`, no worktrees; commit only when the user decides to, and only this
  session's own files (`git add <paths>`; the hang session commits on `main` too); commits end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Transcripts:** project hooks write each session to `notes/transcripts/` (ignored by git) before compaction and on
  `/clear`.

## Next step

Read what the hang session found or changed; ask the user about the `wrf.exe` guard and run 4's details; then, with
the go-ahead, submit run 4 and watch it.
