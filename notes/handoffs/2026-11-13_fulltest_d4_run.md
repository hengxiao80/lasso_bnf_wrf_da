# Hand-off: "fulltest: D4 run"

Written 2026-11-13 at the end of session "fulltest: D3 run". Session "fulltest: D2 analysis" (hand-off `2026-11-13_fulltest_d2_analysis.md`) was running at the same time and had uncommitted files in the tree (`patches/README.md`, `software_lock.json`, `scripts/da/*obs_diag*`, `patches/dart_7bbd35a09_obs_diag_rank_hist_units.patch`, `config/input.nml.obs_diag`); leave them to it, and commit only your own files.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da`. Read `CLAUDE.md`, then `notes/fulltest_workflow.md` (Sec. 2: the chain; Sec. 3: running, failures, resume) and `notes/fulltest_steps.md` Sec. 0 (scope, retention) and Part D (D1's to D3's results).

## Goal

Run D4, the last gate of the production run `_conv_refl_f2` in `cases/20250520/da_theta_m0_n50/`: analyses 05-20 12:15 to 05-21 06:00 (72 cycles), continuing D3 (06:15 to 12:00, all `complete`). D4 covers the LES window (05-20 12Z to 05-21 05Z) and event 2 (domain MRMS coverage above 30 dBZ at 4–5 % from 18Z to 05-21 ~10Z, Sec. 0). 05-21 06:00 is the last analysis time with observations (A7), so D4 ends the 30-h run. The user's go-ahead before the submit.

## Where things stand (2026-11-13)

- **D3 passed** (`fulltest_steps.md` D3): all 24 cycles `complete`, every check passed, no retries, no `ERROR` lines, no CFL lines in the 1,200 segments, no queue waits. Chain 17:49:26 → 00:18:48 UTC (6 h 29 min), 294.4 node-hours.
- **The 6-h-gate decisions** (user, 2026-11-13, before D3): no thinning yet (the chain keeps everything), 2 nodes per member. A free ensemble or a spin-up variant would be a separate run, not a change to this one. The D2-analysis session was to supply material for these; check its outcome (`notes/handoffs/`, `git log`, Part D).
- **D4's observations are ready and checked** (A7): all 120 analyses pass `scripts/da/check_cycle_obs.py`, including the test that every obs time in `obs_seq.out` and `obs_seq.joint` lies inside the window. In D4: reflectivity ~17,000 at 17:00–17:45, ~45,000 at 05-21 00:30–01:30, 20,791 at 06:00; radiosondes in the window at 19:00 (221; 131 after screening; temperature, humidity and one altimeter, no wind) and at 05-21 00:00 (2,584; 842), "0 in window" at 12:15–13:45, 18:00–18:45, 19:15–20:45 and 23:00 to 05-21 01:45 except 00:00. A7's ranges for 06:15 to 05-21 06:00: conventional obs after screening 5,014–10,119, reflectivity 16,951–91,864, clear air 8,210–10,840.
- **D4 dry run passed** (2026-11-14 00:59 UTC): observation files found, cycle 12:00 `complete`, settings equal to `output_conv_refl_f2/settings.txt`; it would submit one job, the 40-node filter job F(12:15) with a 30-min limit. Nothing queued. No Slurm reservations then (`scontrol show reservation`: "No reservations in the system").
- **Disk**: D3's cycles took 543–556 GB each (mean 549), so 72 cycles add ~39.5 TB if everything is kept, and `output_conv_refl_f2/` goes from 26.6 to ~66 TB; `run_conv_refl_f2/` stays at 825 GB. Disk quota is not a concern for the 30-h run (user, 2026-11-13); the quota itself is unknown.
- **Expected from D3**: 16.0 min per cycle (15.3–17.7, not counting the first at 20.0), so 72 cycles take ~19.2 h plus any queue waits (none in D1 to D3; over ~19 h of other users' jobs, unknown); 12.3 node-hours per cycle, ~890 for D4. With fewer than 50 nodes free for an array, it runs fewer than 25 members at once and needs a third wave (from 06:30 on, D3's arrays ran 27–29 at once, two waves): D3's first array ran 24 at once and took 15.3 min instead of ~10.5, and its cycle took 20.0 min.

## Before submitting

1. Check what the D2-analysis session concluded (above). A change to a setting that `settings.txt` records (`HYDROSTATIC_PH`, `INF_*`, the observation set, `MRMS_FILTER`) can't continue `_conv_refl_f2`: `run_preflight` refuses it, and it means a new run from 00Z.
2. **Dry run** again if anything changed since 2026-11-14 00:59 UTC. `--dry-run` goes after the three arguments (`chain_submit.sh <experiment.sh> <first> <last> --dry-run`); in front of them it is taken as the experiment file ("readlink: unrecognized option").
3. `squeue -u $USER`: no jobs named `n50f_conv_refl_f2` or `n50w_conv_refl_f2`.
4. `scontrol show reservation`: Slurm doesn't start a job whose time limit reaches into a maintenance reservation on the nodes it needs, so a reservation within the next ~20 h would stall the chain until it ends. If there is one, tell the user before submitting.

## Submit (user's go-ahead)

From the repo root, after `source scripts/env_wrf.sh`:

```
RUN_NAME=_conv_refl_f2 OBS_NAME=_meso_a_calmkeep_mrms \
  MRMS_FILTER=one_pass scripts/da/chain_submit.sh \
  cases/20250520/da_theta_m0_n50/config/experiment.sh \
  202505201215 202505210600
```

- It submits F(12:15). Each filter job then submits the next WRF array (`afterok`) and filter job (`afterany`); the last job is a 1-node F(05-21 06:15) that checks cycle 06:00 and submits nothing. At most 80 nodes in use at a time.
- Limits stay 30 min for a WRF task and a filter job (D3's longest: WRF task 377 s, filter job 6.4 min).

## While it runs

- The chain runs in Slurm and needs no session. Progress: `squeue -u $USER`; `output_conv_refl_f2/chain.log` (one line per submission, UTC); `output_conv_refl_f2/<t>/status`; `cycle.log` per filter job. A filter job F(t) finishes cycle t − 15 (marks it `complete` once its check passes) and starts cycle t, so two cycles show `running` while it works.
- Failures (`fulltest_workflow.md` Sec. 3): a failed WRF task gets one automatic retry per cycle; a failed filter, member update or check stops the chain. Find the cause before resuming (D2's stop was an observation bug, not the machine); resume with the same command (user's go-ahead). Stop by hand: `scancel` the jobs named `n50f_conv_refl_f2` and `n50w_conv_refl_f2`.
- **Notifier**: one background command with a loop on `squeue -u $USER -h -o '%j'` every 5 min, ending when no `n50[fw]_conv_refl_f2` job is left (on a failed `squeue`, wait and try again rather than end); at the end it prints the last lines of `chain.log` and the count of cycles per status. If the session ends, only the notification is lost.
- **What D3's session learned about notifiers**: after `/exit`, the session went on as a background session in a new process (`claude bg-spare` under `claude bg-pty-host`; `claude agents --json` shows it with `"kind": "background"`), and the notifier started before, now with parent PID 1, still reported to it. So parent PID 1 alone doesn't mean an orphan: D3's session wrongly killed its own live notifier on that basis. Before starting or stopping one, run `pgrep -u $USER -af conv_refl_f2` (the check's own command line matches too) and `claude agents --json`; a loop is stale only if the session that started it is gone (D2's session saw orphans after `/stop`). D3's session survived ~4 h detached with a notifier waiting; whether it would survive D4's ~19 h is unknown (`~/.claude/rules/cirrus-detached-loops.md`).

## After D4

- **Checks as for D3** (Part D, D3), with the same sources:
  - all 72 cycles `complete`; "all checks passed" in each `check_cycle.log`; no `<t>/retries`; no `ERROR` lines in `cycle.log`;
  - CFL: cycle t's `memNNN/` holds the segment A(t) (`fulltest_workflow.md` Sec. 1.2), so D4's 3,600 segments are in cycles 12:15 to 05-21 06:00; every `cfl_count.txt` should read "ranks with cfl lines: 0  cfl lines: 0";
  - `sacct -u $USER -S <local start> -E now -X -P -o JobID,JobName,State,Eligible,Start,End,ElapsedRaw,NNodes,ExitCode --name=n50f_conv_refl_f2,n50w_conv_refl_f2` (times in local time, EST; `chain.log` is UTC). Each `chain.log` line names the A(t) and F(t + 15) job IDs, which maps jobs to cycles. From it: job and task states, filter-job times, array spans (first task start to last task end), task times, members at once (from task starts and ends), node-hours (ElapsedRaw × NNodes). D3 did this with inline Python, not kept; a script is open item E2;
  - queue waits: `Eligible` → `Start` per filter job and per array's first task (the later tasks wait inside the array for nodes: 306–335 s in D3);
  - from `cycle.log`: "filter (conv) done in N s", "filter step done in N s", and the check's "waited a -> b s" (b > a means the check delayed the job; in the final 1-node job "waited 0 -> N s" is the check alone, not a delay);
  - disk: `du -B1 --max-depth=1 output_conv_refl_f2` (every cycle and the total in one pass; 14 s for 49 cycles in D3) and `du -s -B1 run_conv_refl_f2`.
- Results go into Part D under D4, for the user to review before a commit.
- What follows the 30-h run is the user's to decide (`fulltest_steps.md` Sec. 2; the D2-analysis session's outcome).

## Working rules

- No quantitative guesses: derive from a measured run, show the basis, or say "unknown" (memory `no-unfounded-estimates`).
- Status lines before tool calls are full sentences (what, on what, why). No LaTeX in chat. Notes per `~/.claude/rules/typora-markdown.md`.
- The user's go-ahead before every `sbatch`, including `chain_submit.sh` without `--dry-run`; at most 80 nodes at a time; commits only after the user has reviewed; push only when asked.
- Never change `da_theta_m0_n50/run_conv_refl_f2/` or `output_conv_refl_f2/` by hand: the run continues from them.
- `command ls` (the `ls` alias adds `-F`); `.venv/bin/python`. The shell's `grep` is a function whose errors come from `ugrep`, which rejects some long bounded patterns (`{0,300}`); `command grep` is GNU grep 3.1. Foreground `sleep` is blocked in Bash calls; wait with a background command instead.

## Starting the session

Name it `fulltest: D4 run`, and name this file in the first prompt (`notes/handoffs/2026-11-13_fulltest_d4_run.md`).
