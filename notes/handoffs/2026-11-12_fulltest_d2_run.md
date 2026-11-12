# Hand-off: "fulltest: D2 run"

Written 2026-11-12 at the end of session "fulltest: A7 observations" (which picked up `2026-11-12_fulltest_a7_observations.md`). The other hand-off of that day, `2026-11-12_fulltest_d1_analysis.md` (a look at D1's results), went to its own session; check its outcome before submitting (step 1 below).

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da`. Read `CLAUDE.md`, then `notes/fulltest_workflow.md` (Sec. 2: the chain; Sec. 3: running, failures, resume) and `notes/fulltest_steps.md` Part D (the run plan, D1's results, the decisions due at D2).

## Goal

Run D2, the 6-h gate of the production run `_conv_refl_f2` in `da_theta_m0_n50/`: analyses 05-20 01:15 to 06:00 (20 cycles), continuing D1 (00:00 to 01:00, all cycles `complete`). The user wants it submitted in this session, with their go-ahead before the submit.

## Where things stand (2026-11-12, 23:08 UTC)

- **D2's observations are ready and checked.** All 20 times are in `cases/20250520/da_common_theta_m0/obs_meso_a_calmkeep_mrms/<t>/` with `obs_seq.out`, `obs_seq.mrms`, `obs_seq.joint`. MRMS valid times are 18–24 s before t or 37–43 s after it. Joint totals are 94,909–111,481 obs (D1: 93,094–98,688). Conventional obs after screening: 5,703–9,240; radar reflectivity: 78,682–96,700 (rising after 03:30 with the echo coverage); clear air: 8,010–8,502. ACARS falls after 03Z (late evening to 1 am local time), METAR swings with the window's position relative to the hourly reports, as in D1. The only error-like log lines are the two boundary error-inflation messages and the radiosonde slice's "all obs excluded" (no radiosonde in any D2 window). `obs_settings.txt` unchanged.
- **D2 dry run passed** (2026-11-12 22:50 UTC): observation files found for all 20 times, cycle 01:00 `complete`, settings equal to `output_conv_refl_f2/settings.txt`; it would submit one job, the 40-node filter job F(01:15) with a 30-min limit. It wrote nothing.
- **The other 96 times** (05-20 06:15 to 05-21 06:00, needed by D3 and D4) are being built by a detached loop: `cases/20250520/obs/logs/a7_loop.sh` on `cirrus-login1`, PID 1986152, started 23:04:56 UTC, ~40 s per time, so it should end around 00:05–00:10 UTC on 11-13. Log: `cases/20250520/obs/logs/a7_rest.log` (D2's loop log: `a7_d2.log`). Not checked yet; it doesn't block D2. Checks below.
- Cost per time, measured at 01:15: MRMS download 11.6 s, `make_cycle_obs.sh` 28 s, 1.2 GB peak. Disk per time: MRMS ~31 MB, observation directory 23–48 MB.
- Not in git yet: this hand-off (for the user to review). A7's record in `notes/fulltest_steps.md` is not written yet.
- New rule for this machine: `~/.claude/rules/cirrus-detached-loops.md` (long login-node work runs detached with `setsid nohup`, script and log on GPFS, measure one item first).

## Before submitting

1. **D1 analysis outcome.** Look in `notes/handoffs/`, `git log` and `notes/fulltest_steps.md` for what the session "fulltest: D1 analysis" concluded. If it changes a setting that `settings.txt` records (e.g. the inflation flavor), D2 can't continue `_conv_refl_f2`: `run_preflight` refuses other settings, and a change means a new run. The user decides.
2. **Disk.** D2 adds ~11 TB: 20 analysis cycles × 550 GB, D1's measured size per analysis cycle. That takes `output_conv_refl_f2/` from 2.4 TB to ~13.4 TB, as Part D predicts; `run_conv_refl_f2/` stays at 825 GB. The project quota is unknown: `mmlsquota` fails on login nodes ("GPFS is down on this node"); OLCF's documentation gives 50 TB. Ask the user before submitting.
3. **Full-range dry run while nothing is queued.** `chain_submit.sh … 202505200115 202505210600 --dry-run` checks the observation files of all 116 times at once, i.e. also the 96 the loop is building (while the loop still runs, it stops at the first time not yet built). Once D2's jobs are queued, a dry run of this run stops at "jobs of run '_conv_refl_f2' already queued or running". Then D2's own dry run (`202505200115 202505200600`), if anything changed since 11-12.
4. `squeue -u $USER`: no jobs named `n50f_conv_refl_f2` or `n50w_conv_refl_f2`.

## Submit (user's go-ahead)

From the repo root, after `source scripts/env_wrf.sh`:

```
RUN_NAME=_conv_refl_f2 OBS_NAME=_meso_a_calmkeep_mrms \
  MRMS_FILTER=one_pass scripts/da/chain_submit.sh \
  cases/20250520/da_theta_m0_n50/config/experiment.sh \
  202505200115 202505200600
```

- It submits F(01:15), the filter job with the analysis at 01:15. Each filter job then submits the next WRF array (`afterok`) and filter job (`afterany`). The last job is a 1-node F(06:15) that checks cycle 06:00 and submits nothing. At most 80 nodes are in use at a time.
- Limits stay 30 min for a WRF task and a filter job (D1's longest: WRF task 6:11, filter job 6.7 min).
- Expected duration from D1: per cycle a WRF array of 10.6–11.6 min plus a filter job of 5.2–6.7 min, i.e. ~16–18 min per cycle. D1 had no queue waits, so 20 cycles take ~5.5–6 h plus whatever queue waits occur (unknown). D1 cost 61.1 node-hours for 5 cycles (12.2 per cycle; WRF 44.8, filter 16.3).

## While it runs

- The chain runs in Slurm and needs no session. Progress: `squeue -u $USER`; `output_conv_refl_f2/chain.log` (one line per submission); `output_conv_refl_f2/<t>/status` (`complete` once its check has passed); `cycle.log` per filter job in `output_conv_refl_f2/<t>/`.
- Failures (`fulltest_workflow.md` Sec. 3): a failed WRF task gets one automatic retry per cycle; a failed filter, member update or check stops the chain. Resume with the same command (user's go-ahead). Stop by hand: `scancel` the jobs named `n50f_conv_refl_f2` and `n50w_conv_refl_f2`.
- A notifier in the session (background until-loop on `squeue`, polling every few minutes) is optional; if the session is stopped (e.g. backgrounded and idle for about an hour), only the notifier is lost.

## After D2

- Checks as for D1 (Part D, D1 "Ran 2026-11-09"): all 20 cycles `complete`, "all checks passed" per cycle, retries, `ERROR` lines in `cycle.log`, CFL lines in the segments; times per cycle (WRF array, filter job, segments, members at once); disk (`du`); node-hours. Results go into Part D under D2.
- Decisions due at D2 (Part D): thinning for the 12-h and 30-h runs (including which members' full states are kept for 05-20 12Z to 05-21 05Z), a free ensemble, a spin-up variant (radar spread), nodes per member.
- D3 (`202505200615 202505201200`) needs the 96 times' observations, checked.

## Checking the 96-time loop

- The log's last line is `A7 LOOP DONE <time>` or `A7 LOOP FAILED at <t>`. If the process is gone without either line, it was killed (e.g. a reboot of the login node). After a failure or a kill: the failing time's logs in `obs_meso_a_calmkeep_mrms/<t>/`, or the download message in the log; then restart from that time, detached, as the rule says (`a7_loop.sh <t> 202505210600`; `make_cycle_obs.sh` clears `<t>/` first).
- Per time, as for D2: every file present; MRMS valid time inside (t − 450 s, t + 450 s]; counts compared type by type (they change with the weather and time of day); only the two boundary messages and the radiosonde "all obs excluded" in the logs.
- **Radiosondes:** each converted file carries one time stamp, 05-20 12:01:04, 05-20 18:59:12 and 05-21 00:00:00, so `counts.window` should show radiosonde obs at the 05-20 12:00, 19:00 and 05-21 00:00 cycles only (2,893, 221 and 2,584 in the hourly files before the time slice) and "0 in window" or "no hourly file" elsewhere. The 05-20 00Z file falls before the first window (00:15) and is never used.
- Then write A7's record in `notes/fulltest_steps.md` (both loops, the checks, the measured cost per time) for the user to review before a commit.

## Working rules

- No quantitative guesses: derive from a measured run, show the basis, or say "unknown" (memory `no-unfounded-estimates`).
- Status lines before tool calls are full sentences (what, on what, why). No LaTeX in chat. Notes per `~/.claude/rules/typora-markdown.md`.
- The user's go-ahead before every `sbatch`, including `chain_submit.sh` without `--dry-run`; at most 80 nodes at a time; commits only after the user has reviewed; push only when asked.
- Never change `da_theta_m0_n50/run_conv_refl_f2/` or `output_conv_refl_f2/` by hand: D2 continues from them.
- `command ls` (the `ls` alias adds `-F`); `.venv/bin/python`.

## Starting the session

Name it `fulltest: D2 run`, and name this file in the first prompt (`notes/handoffs/2026-11-12_fulltest_d2_run.md`).
