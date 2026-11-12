# Hand-off: "fulltest: A7 observations"

Written 2026-11-12 at the end of session "fulltest: initial setup part 4". A second hand-off from the same session, `2026-11-12_fulltest_d1_analysis.md`, covers the look at D1's results; the two can run side by side (this one only adds new time directories to the observation set, the other only reads D1's output). Everything from that session is committed and pushed, with these two hand-offs.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da`. Read `CLAUDE.md`, then `notes/fulltest_workflow.md` (the 50-member setup) and `notes/fulltest_steps.md` (A7; Part D: the run plan and D1's results).

## Goal

Observations for D2, the 6-h gate of the production run `_conv_refl_f2` (analyses 05-20 01:15 to 06:00, 20 times), in the same observation set D1 used: `cases/20250520/da_common_theta_m0/obs_meso_a_calmkeep_mrms/` (MADIS conventional + mesonet option a with calm winds kept + MRMS reflectivity; `obs_settings.txt`: `mesonet=a_calmkeep mrms=hrrrdas`). A7 (`fulltest_steps.md`) plans all 120 analyses to 05-21 06:00 (D3 and D4 need the rest); proposed: D2's 20 first, checked, then the user decides whether to do the other 96 in the same session.

## What exists (checked 2026-11-12)

- Raw MADIS, every family (`cases/20250520/obs/madis/{metar,acars,marine,raob,mesonet}/`): hourly, 05-19 00Z to 05-21 23Z.
- Converted MADIS (`obs/obs_seq_madis/<family>/`): every hour of 05-20 and 05-21 (`rawin` only at sounding hours, 38 files). Nothing to convert.
- Per-cycle mesonet (`obs/obs_seq_mesonet/a_calmkeep/`): 00:15–01:15.
- MRMS (`obs/mrms/20250520/`): only the four times of D1 (33 `MergedReflectivityQC` levels each; ~28 MB per time, A7).
- The set `obs_meso_a_calmkeep_mrms/`: 00:15–01:00, each `<t>/` with `obs_seq.out`, `obs_seq.mrms`, `obs_seq.joint` (what a one-pass run reads), `counts.*` and logs.

## Steps per analysis time t (login node; `source scripts/env_wrf.sh` first)

1. `scripts/da/download_mrms.sh <t>`: the MRMS levels at t's minute, else 1 or 2 min earlier (HRRRDAS's rule), from the public bucket `noaa-mrms-pds`, into `obs/mrms/YYYYMMDD/`. Needs internet, so login node only.
2. `OBS_NAME=_meso_a_calmkeep_mrms MESONET=a_calmkeep MRMS=hrrrdas scripts/da/make_cycle_obs.sh <t>`: slices the MADIS families to (t − 450 s, t + 450 s], calls `make_cycle_mesonet.sh` itself, screens with `wrf_dart_obs_preprocess`, converts MRMS (`mrms_to_obs_seq.py`) and writes `obs_seq.joint`. It sources the 5-member `experiment.sh` through the `da_theta_m0` link and uses only shared settings; the set's directory is reached through that experiment's link. It refuses to write into a set whose `obs_settings.txt` differs.

Times and memory per t are not known: measure on the first one (login nodes allow 32 GB per user) before looping. A loop over 20 times goes detached (`setsid nohup … &`, log to a file), since a session's background commands end with it.

## Checks

- Per t: `counts.window`, `counts.out`, `counts.mrms`; the logs (`preprocess.log`, `mesonet.log`, `mrms.log`, `joint.log`) without errors; the MRMS valid time inside the window (the converter checks it). D1's cycles had 93,094–98,688 obs, ~77,000–80,500 of them radar reflectivity; later hours will differ with the weather (echo coverage changes), so compare type by type rather than against a fixed number.
- `obs_settings.txt` unchanged.
- Then `chain_submit.sh … 202505200115 202505200600 --dry-run` for D2 (command in `fulltest_workflow.md` Sec. 3): `run_preflight` must find observation files for every analysis time; it writes nothing.

## Then (each with the user's go-ahead)

- D2 itself: the same command without `--dry-run`. Limits stay 30 min (D1's longest: WRF task 6:11, filter job 6.7 min). Disk: ~551 GB per analysis cycle as written, so ~11 TB more for 20 cycles (`fulltest_output_files.md` Sec. 3.4); the project area's quota is not known (OLCF's documentation gives 50 TB).
- The D1 analysis (other hand-off) may lead to changes before D2 (e.g. the inflation flavor); D2 continues D1's run, and `settings.txt` refuses other settings, so a change means a new run.

## Working rules

- No quantitative guesses: derive from a measured run, show the basis, or say "unknown" and measure first (memory `no-unfounded-estimates`).
- Status lines before tool calls are full sentences (what, on what, why). No LaTeX in chat. Notes per `~/.claude/rules/typora-markdown.md`.
- The user's go-ahead before every `sbatch` (also `chain_submit.sh` without `--dry-run`); at most 80 nodes at a time; commits only after the user has reviewed; push only when asked.
- Never change `da_theta_m0_n50/run_conv_refl_f2/` or `output_conv_refl_f2/`: D2 continues from them.
- `command ls` (the `ls` alias adds `-F`); `.venv/bin/python`.

## Starting the session

Name it `fulltest: A7 observations`, and name this file in the first prompt (`notes/handoffs/2026-11-12_fulltest_a7_observations.md`).
