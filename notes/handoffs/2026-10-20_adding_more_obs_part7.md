# Hand-off: "Adding more obs part 7: runs 1–4"

Written 2026-10-20 at the end of session "Adding more obs part 6" (run plan, filter scaling, filter exit hang).
Everything from that session is committed (last code commit `210152a`); only the two Dowell PDFs in `notes/` are
untracked, as before.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup).
- Read `CLAUDE.md` first. New there: the filter layout and run plan entry, and two gotchas (filter hang on the
  512-GB nodes; filter jobs need `slurm.cycle`'s job shape).
- Main working note: `notes/obs_expansion.md` **Sec. 9** (run plan table, timing baseline and the empty timing table
  to fill, DART speed-up levers, scaling tests, decisions of 2026-10-20). MRMS design: Sec. 8.4 (two-pass), 8.5
  (one-pass).
- Namelist decisions: `notes/dart_namelist_discussion_log.md`, latest entries 2026-10-15 (inflation, same state list
  in both passes) and 2026-10-20 (filter layout, exit hang).
- Pilot record: `notes/da_5member_pilot_steps.md` (step 13 = the 1-hour pilot these runs repeat; Q7 and step 14 for
  job structure, including the job-array discussion).
- Previous hand-off: `notes/handoffs/2026-10-15_adding_more_obs_part6.md`.

## Goal

Run the four 1-hour, 5-member runs of `obs_expansion.md` Sec. 9, plus the MRMS scaling test after run 1, one at a
time, and record timing and results. Each run: cold start 00:00, analyses 00:15–01:00, `slurm.cycle 202505200000
202505200100` from `cases/20250520/da_theta_m0/`, 40 nodes. Step 13 took ~32 min; with filter now on 40 × 32, expect
~25–30 min for runs without MRMS.

The user approved this plan on 2026-10-20 ("go ahead with steps 1, 2, 3 and runs 2 & 3") and then asked that nothing
be run until the code and documentation were done. **Still get the user's go-ahead before every `sbatch`.**
The `RUN_NAME`s below were proposed in Sec. 9 and not objected to; confirm them at the first submission.

| order | what | command (from `cases/20250520/da_theta_m0/`) | needs before |
|---|---|---|---|
| 1 | **Run 1**, MADIS reference | `OBS_NAME=_madis RUN_NAME=_madis sbatch slurm.cycle 202505200000 202505200100` | go-ahead |
| 2 | **MRMS scaling test** on run 1's 00:15 priors | `SCALE_CASE=mrms SCALE_SRC=output_madis sbatch --time=03:00:00 slurm.filter_scaling` | run 1 done |
| 3 | **Run 2**, + mesonet (a), calm winds kept | `OBS_NAME=_meso_a_calmkeep RUN_NAME=_meso_a sbatch slurm.cycle 202505200000 202505200100` | go-ahead |
| 4 | **Run 3**, + MRMS, one pass | `OBS_NAME=_madis_mrms MRMS_FILTER=one_pass RUN_NAME=_madis_mrms1p sbatch --time=<from test> slurm.cycle 202505200000 202505200100` | MRMS test (time limit) |
| 5 | **Run 4**, + MRMS, two passes | `OBS_NAME=_madis_mrms MRMS_FILTER=two_pass MRMS_INFLATION=<pass1\|both> RUN_NAME=_madis_mrms2p sbatch --time=<from test> slurm.cycle ...` | user's `MRMS_INFLATION` choice |
| 6 | Run 5, everything | to decide after runs 1–4 | |

Notes on the table:
- **Run 1 is the first real use of several new things:** the pass-1 namelist with QCLOUD updated and QRAIN, QSNOW,
  QGRAUP, `REFL_10CM` in the state (needs restarts from the patched `wrf.exe`, which a cold start gives); filter on
  40 × 32 inside the cycle; `run_filter` with the exit guard; the node exclusion in `slurm.cycle`.
- **MRMS scaling test:** the default configs are `40x16 40x16:283x144 40x32 40x32:283x144` (`:283x144` = `&location_nml`
  search boxes ×4). Since runs use 40 × 32, `SCALE_CONFIGS="40x32 40x32:283x144 40x64 40x64:283x144"` may be more
  useful; ask. It also prints the DART QC counts per type of the first config (outlier check, QC 7, on the radar types).
  Its radar ms per ob sets the time limit for runs 3–4: ~85,000–89,000 radar obs per cycle; at 8 × 16 a conventional ob
  cost ~28 ms, at 40 × 32 ~2.9 ms; the radar cost per ob (18-km cutoff) is unknown. If ×4 boxes help, decide whether to
  put them into `input.nml.filter_mrms` and `input.nml.filter_joint` before runs 3–4 (search only; results unchanged).
- **Run 2's set** is `obs_meso_a_calmkeep/`: the user first asked for calm winds dropped, then kept them.
- The test directory `tests/filter_scaling/<case>_<t>/` is deleted and recreated by each submission of
  `slurm.filter_scaling` for the same case and time; rename it first to keep earlier results (as done with
  `conv_202505200030_job1054411/`).

## After each run

1. `slurm.cycle.<job>.out`: every cycle `complete`, `driver: done`; look for **"filter exit guard"** lines (the guard
   fired: the hang happened even without 512-GB nodes) and note which nodes the job ran on (`sacct -j <job> -X
   --format=NodeList`).
2. Per-cycle checks: `output<RUN_NAME>/<t>/check_cycle.log` (QC counts, increments, spread, inflation, NaNs, CFL).
3. Timing: `.venv/bin/python scripts/da/summarize_cycle_timing.py cases/20250520/da_theta_m0/output<RUN_NAME>
   --slurm-out cases/20250520/da_theta_m0/slurm.cycle.<job>.out`; add the rows to the timing table at the end of the
   Sec. 9 timing block (the user asked to track how the filter cost changes from run to run; WRF should cost the same).
4. MRMS runs: filter wall time and MaxRSS per pass, the radar QC counts (`.venv/bin/python scripts/da/check_filter_gate.py
   obs <obs_seq.final>`), especially QC 7.
5. Record results and decisions in `obs_expansion.md` Sec. 9 as they come; a discussion-log entry whenever `input.nml`
   settings, observation errors, localization or inflation come up.

## Where things stand (2026-10-20)

- **Filter layout:** 40 nodes × 32 ranks (`experiment.sh` defaults `FILTER_NODES=40`, `FILTER_TASKS_PER_NODE=32`,
  overridable from sbatch's environment; not in `settings.txt`). Scaling test (job 1054411): analyses bit-identical
  for 8 × 16, 40 × 16, 40 × 32 (and to step 13); observation loop 97 → 18 → 10 s; 0.5 GB per rank at 40 × 32.
  `driver.sh` stops at the start if `FILTER_NODES` exceeds the job's nodes.
- **Filter exit hang:** in every multi-node filter run that included 512-GB nodes (cirrus57–64, 121–128) all ranks
  kept spinning after "Finished ... at" (outputs complete, analyses correct); on 256-GB nodes it always exited (step 13
  on cirrus77–116; job 1054413 on cirrus49–56). Cause not established (no library changes since step 13; `slurmd`
  restarted on all nodes 2026-10-14). `slurm.cycle` and `slurm.filter_scaling` now `--exclude` the 512-GB nodes;
  `run_filter` in `scripts/da/cycle_lib.sh` cancels a step still running `FILTER_EXIT_GRACE` (30 s) after "Finished"
  once no output file has changed for 30 s, and logs "filter exit guard" (also leaves `filter_exit_guard.txt`).
  Tested on the login node with stand-ins and in jobs 1054411 (fired 3×, correctly).
- **Job setup matters for speed:** a filter job shaped 128 × 1 per node without `OMP_*` was 27 % slower than
  `slurm.cycle`'s 16 × 8 with `OMP_*`, for the identical `srun` line. `slurm.filter_scaling` now copies `slurm.cycle`.
- **Observation sets** (all four cycles 00:15–01:00 built): `obs_madis/`, `obs_meso_a_calmkeep/`, `obs_madis_mrms/`,
  `obs_meso_a_calmkeep_mrms/`. The 10-01 `filter` was built with the radar and reanalysis-BUFR operators
  (`quickbuild_fp_precise.log`), so it knows the `RADAR_*` and `LAND_SFC_*` types. (`obs_kind_mod.f90` on disk was
  regenerated 10-14 by a converter build and lacks the radar types; it doesn't describe the `filter` binary. A
  `quickbuild.sh` in `models/wrf/work` would regenerate it with the WRF list.)
- **No new runs yet:** `run_madis/` etc. don't exist; the step 13 runs (`run*/`, `output*/`) can't be resumed with the
  new namelist (no `REFL_10CM` in their restarts).

## Open questions for the user

- `MRMS_INFLATION` for run 4 (`pass1` | `both`; with `both`, `MRMS_PASS2_DAMPING` default 1 damps twice per cycle).
  `INF_DAMPING` 0.9 vs 0.9956; flavor 5 with `INF_SD_LOWER_BOUND` < 0.6 (2026-10-15 discussion-log entry).
- Outlier check on radar obs (`outlier_threshold = 3` for all types): decide from the MRMS test's QC-7 counts.
- Impact table: conventional → `QTY_RADAR_REFLECTIVITY` 0 (as HRRRDAS) or 1.
- Search boxes ×4 for the radar namelists (from the MRMS scaling test).
- Run 5's contents.
- Later: job structure for the extension / 50 members (arrays, chained 1-hour allocations, or waves; step 14).

## Working rules

- **Jobs:** the user's go-ahead before every `sbatch`; one step at a time; report each result. `sbatch --test-only`
  checks a script without queuing a job.
- **Environment:** `source scripts/env_wrf.sh` before DART or WRF tools; Python is `.venv/bin/python`. In Claude Code's
  shell `find` is `bfs`, which rejects relative times such as `-newermt '-30 seconds'`.
- **Notes:** results and decisions as they come (Sec. 9); discussion-log entries for namelist matters.
- **Locations:** never modify `sey/`; observation downloads under `cases/20250520/obs/`; external repos in
  `../software/`; hand-offs in `notes/handoffs/`.
- **Git:** work and commit directly on `main`, no worktrees; commit only when the user decides to; commits end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Transcripts:** project hooks write each session to `notes/transcripts/` (ignored by git) before compaction and on
  `/clear`.

## Next step

Confirm the `RUN_NAME`s and get the go-ahead, then submit run 1 (table above) and watch it; then the MRMS scaling test.
