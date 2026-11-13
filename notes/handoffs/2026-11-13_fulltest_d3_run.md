# Hand-off: "fulltest: D3 run"

Written 2026-11-13 at the end of session "fulltest: D2 run". The other hand-off of that session, `2026-11-13_fulltest_d2_analysis.md` (a look at the first 6 h), went to its own session; check its outcome before submitting (step 1 below).

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da`. Read `CLAUDE.md`, then `notes/fulltest_workflow.md` (Sec. 2: the chain; Sec. 3: running, failures, resume) and `notes/fulltest_steps.md` Sec. 0 (scope, retention) and Part D (D1's and D2's results, the decisions due at the 6-h gate).

## Goal

Run D3, the 12-h gate of the production run `_conv_refl_f2` in `cases/20250520/da_theta_m0_n50/`: analyses 05-20 06:15 to 12:00 (24 cycles), continuing D2 (01:15 to 06:00, all `complete`). The state at 12Z starts the LES window (05-20 12Z to 05-21 05Z). The user's go-ahead before the submit.

## Where things stand (2026-11-13)

- **D2 passed** (`fulltest_steps.md` D2): all 20 cycles `complete`, every check passed, no retries, no CFL lines, no queue waits. It stopped once at 02:00 on mesonet obs stamped outside the window (float32 times under `r8 = r4`); `select_mesonet_cycle.py` fixed, 02:00 to 05-21 06:00 rebuilt, then resumed (A7, commit `a8ed260`; `CLAUDE.md` gotcha). Results committed in `0c0b9ad`.
- **D3's observations are ready and checked**: all 120 analyses (to 05-21 06:00) pass `scripts/da/check_cycle_obs.py`, including the test that every obs time in `obs_seq.out` and `obs_seq.joint` lies inside the window (A7). For 06:15–12:00: conventional obs after screening 5,014–9,759; radar reflectivity falling from 91,864 at 06:15 to 39,588 at 12:00 as event 1 ends; clear air 8,210–10,137; radiosondes at 12:00 (2,893 in the window, 959 after screening), "0 in window" at 11:00–11:45.
- **D3 dry run passed** (2026-11-13 17:42 UTC): observation files found, cycle 06:00 `complete`, settings equal to `output_conv_refl_f2/settings.txt`; it would submit one job, the 40-node filter job F(06:15) with a 30-min limit. Nothing queued.
- **Disk is not a concern for the 30-h run** (user, 2026-11-13). Unless the user decides on thinning, the chain keeps everything, as in D1 and D2: ~550 GB per analysis cycle (D2: 547–557 GB), so D3 adds ~13.2 TB and `output_conv_refl_f2/` goes from 13.4 to ~26.6 TB; `run_conv_refl_f2/` stays at 825 GB. The quota is unknown; OLCF's 50 TB doesn't apply to this area (user).
- **Expected from D2**: ~16 min per cycle (15.9–17.0, mean 16.3), so 24 cycles take ~6.5 h plus any queue waits (none in D1 or D2; unknown); ~12.5 node-hours per cycle, ~300 for D3.

## Before submitting

1. **The decisions due at the 6-h gate** (Part D; the user decides; the D2-analysis session may have material): thinning (with disk no concern, keep everything unless the user decides otherwise), a free ensemble, a spin-up variant, nodes per member. What bears on D3 itself:
   - A change to a setting that `settings.txt` records (`HYDROSTATIC_PH`, `INF_*`, the observation set, `MRMS_FILTER`) can't continue `_conv_refl_f2`: `run_preflight` refuses, and a change means a new run from 00Z. A spin-up variant or a free ensemble is a separate run, not a change to this one.
   - Resources (`MEMBER_NODES`, `NPROC_X`/`NPROC_Y`, `MEMBER_MAX`, filter nodes) are not recorded in `settings.txt`; changing nodes per member in `config/experiment.sh` before D3 is possible without a new run, but would be a production change: the user's go-ahead, ideally after a test.
   - Look in `notes/handoffs/`, `git log` and `notes/fulltest_steps.md` for what the D2-analysis session concluded.
2. **Dry run** again if anything changed since 2026-11-13 17:42 UTC: the command below with `--dry-run`.
3. `squeue -u $USER`: no jobs named `n50f_conv_refl_f2` or `n50w_conv_refl_f2`.

## Submit (user's go-ahead)

From the repo root, after `source scripts/env_wrf.sh`:

```
RUN_NAME=_conv_refl_f2 OBS_NAME=_meso_a_calmkeep_mrms \
  MRMS_FILTER=one_pass scripts/da/chain_submit.sh \
  cases/20250520/da_theta_m0_n50/config/experiment.sh \
  202505200615 202505201200
```

- It submits F(06:15). Each filter job then submits the next WRF array (`afterok`) and filter job (`afterany`); the last job is a 1-node F(12:15) that checks cycle 12:00 and submits nothing. At most 80 nodes in use at a time.
- Limits stay 30 min for a WRF task and a filter job (D2's longest: WRF task 368 s, filter job 7.0 min).

## While it runs

- The chain runs in Slurm and needs no session. Progress: `squeue -u $USER`; `output_conv_refl_f2/chain.log` (one line per submission); `output_conv_refl_f2/<t>/status`; `cycle.log` per filter job. A filter job F(t) finishes cycle t − 15 (marks it `complete` once its check passes) and starts cycle t, so two cycles show `running` while it works.
- Failures (`fulltest_workflow.md` Sec. 3): a failed WRF task gets one automatic retry per cycle; a failed filter, member update or check stops the chain. Find the cause before resuming (D2's stop was an observation bug, not the machine); resume with the same command (user's go-ahead). Stop by hand: `scancel` the jobs named `n50f_conv_refl_f2` and `n50w_conv_refl_f2`.
- **Notifier**: one background until-loop on `squeue` (ending when no `n50[fw]_conv_refl_f2` job is left), polling every 5 min. Learned in D2's session: if the session runs as a Claude Code background session (process `claude bg-spare` under `claude bg-pty-host`; `claude agents --json` shows `"kind": "background"`), `/exit` only detaches the view and the session's background commands keep running, so a "restarted" notifier is a second one. `/stop` ends the session, but its loops can survive as orphans (parent PID 1). Before starting a notifier, check with `pgrep -u $USER -af conv_refl_f2` (the check's own command line matches too), and stop stale ones.

## After D3

- **Checks as for D2** (Part D, D2), with the same sources:
  - all 24 cycles `complete`; "all checks passed" in each `check_cycle.log`; no `<t>/retries`; `ERROR` lines in `cycle.log`;
  - CFL: every `memNNN/cfl_count.txt` should read "ranks with cfl lines: 0  cfl lines: 0" (1,200 segments);
  - `sacct -u $USER -S <local start> -X -P -o JobID,JobName,State,Start,End,ElapsedRaw,NNodes --name=n50f_conv_refl_f2,n50w_conv_refl_f2` (times in local time, EST): job and task states, filter-job times, array spans (first task start to last task end), task times, members at once, node-hours (ElapsedRaw × NNodes);
  - queue waits: `Eligible` → `Start` per filter job and per array's first task (tasks 30–50 wait inside the array for nodes, as in D1 and D2);
  - from `cycle.log`: "filter (conv) done in N s", "filter step done in N s", and the check's "waited a -> b s";
  - disk: `du -s -B1` of `output_conv_refl_f2/`, `run_conv_refl_f2/` and each cycle.
- Results go into Part D under D3, for the user to review before a commit.
- **D4** (`202505201215 202505210600`, 72 cycles; at D2's pace ~19.6 h, ~900 node-hours, ~39.7 TB if everything is kept): its observations are ready and checked (A7).

## Working rules

- No quantitative guesses: derive from a measured run, show the basis, or say "unknown" (memory `no-unfounded-estimates`).
- Status lines before tool calls are full sentences (what, on what, why). No LaTeX in chat. Notes per `~/.claude/rules/typora-markdown.md`.
- The user's go-ahead before every `sbatch`, including `chain_submit.sh` without `--dry-run`; at most 80 nodes at a time; commits only after the user has reviewed; push only when asked.
- Never change `da_theta_m0_n50/run_conv_refl_f2/` or `output_conv_refl_f2/` by hand: the run continues from them.
- `command ls` (the `ls` alias adds `-F`); `.venv/bin/python`. The shell's `grep` is a function whose errors come from `ugrep`, which rejects some long bounded patterns (`{0,300}`); `command grep` is GNU grep 3.1.

## Starting the session

Name it `fulltest: D3 run`, and name this file in the first prompt (`notes/handoffs/2026-11-13_fulltest_d3_run.md`).
