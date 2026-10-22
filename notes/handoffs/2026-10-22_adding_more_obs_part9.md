# Hand-off: "Adding more obs part 9": more two-pass tests, then run 5

Written 2026-10-22 at the end of session "Adding more obs part 8" (run 4, the MRMS-pass impact table, run 4b, the
inflation walk-through). Everything from that session is committed (`2772f4e`, `90524ff`, and this hand-off); only
the two Dowell PDFs in `notes/` are untracked, as before. No jobs running.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup).
- Read `CLAUDE.md` first (status updated for runs 1–4b and the MRMS impact table).
- **Main note for this session: `notes/mrms_two_pass_inflation.md`.** How flavor-2 inflation and the impact table work
  within a pass and carry between passes and cycles; flags and λ adaptation per state variable and pass; measured
  spread by stage; conclusions; **the proposed test plan (its Sec. 8)**. Read it before proposing anything.
- Run results and timing: `notes/obs_expansion.md` Sec. 9 (runs 1–4b). Two-pass and one-pass design: Sec. 8.4, 8.5.
- Namelist decisions: `notes/dart_namelist_discussion_log.md`, latest entries 2026-10-21 (run 4, impact table) and
  2026-10-22 (inflation and impact table; corrects the "partly offsets" claim about pass-2 damping).
- Exit hangs are solved (`notes/filter_exit_hang.md`, commit `32967aa`): filter runs with hcoll off, `wrf.exe` has an
  exit guard. Neither guard fired in runs 4 and 4b.
- Previous hand-off: `notes/handoffs/2026-10-21_adding_more_obs_part8.md`.

## Where things stand (2026-10-22)

All 1-hour runs, 5 members, cold start 00:00, analyses 00:15–01:00, filter 40 × 32, `INF_FLAVOR=2`, `INF_DAMPING=0.9`:

| run | `RUN_NAME` (job) | observations | filter | result |
|---|---|---|---|---|
| 1 | `_madis` (1054633 + 1054795) | `obs_madis/` | one pass | passed |
| 2 | `_meso_a` (1054801) | `obs_meso_a_calmkeep/` | one pass | passed |
| 3 | `_madis_mrms1p` (1054809) | `obs_madis_mrms/` | `MRMS_FILTER=one_pass` | passed |
| 4 | `_madis_mrms2p` (1054932) | `obs_madis_mrms/` | `two_pass`, `MRMS_INFLATION=both`, `MRMS_PASS2_DAMPING=1` | passed |
| 4b | `_madis_mrms2p_imp` (1054977) | `obs_madis_mrms/` | as run 4 + `obs_impact_mrms.txt` in the MRMS pass | passed |

- **One pass vs two** (run 3 vs 4b): two passes fit the radar slightly better (01:00 posterior 6.53 / +2.65 against
  6.73 / +2.76 dBZ, reflectivity QC 7 33 % against 36 %), with more spread, but the post-analysis shock is ~50 %
  larger from 00:45 on (max |dpsfc/dt| steps 2–4 at 01:00: 1,114 against 732 hPa/3h; minutes 5–15: 100 against 90,
  rising over the cycles).
- **Fixed this session:** in run 4 the radar obs still adapted the inflation of MU, PH, W, PSFC (`NO_COPY_BACK` only
  keeps increments out of the member files). `config/obs_impact_mrms.txt` (radar → those 4 quantities: 0) in
  `input.nml.filter_mrms`; `prep_filter.sh` and `slurm.filter_scaling` copy the table that `obs_impact_filename`
  names; replay `slurm.mrms_impact_test` (job 1054969): members bit-identical, λ different only in those 4 fields.
  Run 4b: MU inflation now below run 3's, **but the shock unchanged**.
- **Leading explanation** (not shown): under `both`, U, V, THM, QVAPOR, QCLOUD are inflated twice per cycle; damping
  removes only 10 % of the excess, so the MRMS pass applies about the same λ again. U spread is inflated ~×1.31 per
  cycle in 4b against ×1.12 in run 3, and the 4b analysis ends with more spread than its forecast.
- **`MRMS_INFLATION=pass1` is not a clean test of it:** it also removes all inflation of QRAIN, QSNOW, QGRAUP and
  REFL_10CM (the conventional pass discards them, the MRMS pass doesn't inflate), and any radar adaptation of λ.
- **Remaining λ difference from run 3:** the conventional pass has no impact table, so the conventional obs adapt the
  hydrometeor and REFL_10CM λ, which the MRMS pass applies.
- **Disk:** `output*/` + `run*/` of runs 1–4b ~2.3 TB (two-pass runs ~550 GB each); step-13 dirs ~0.33 TB. Ask
  before deleting anything.

## Goal

1. More two-pass tests, following the plan in `notes/mrms_two_pass_inflation.md` Sec. 8 (the user has not chosen the
   steps or their order yet: ask first).
2. Run 5 ("everything": MADIS + mesonet option a + MRMS; observation set `obs_meso_a_calmkeep_mrms/` is built for
   00:15–01:00, `mesonet=a_calmkeep mrms=hrrrdas`).

| order (proposed) | what | command / work (from `cases/20250520/da_theta_m0/`) | needs before |
|---|---|---|---|
| 0 | Spread-by-stage block in `scripts/da/check_cycle.py` (per pass: domain RMS sd of U V THM QVAPOR QCLOUD QRAIN QSNOW QGRAUP before inflation / after / after assimilation; applied λ mean, share > 1.1, max; also in echo regions); backfill runs 3, 4, 4b | code, no job | user's choice of steps |
| 1 | Conventional-pass impact table: `config/obs_impact_conv.txt` = the non-radar rows of `obs_impact_joint.txt` (`grep -v '^RADAR'`; covers METAR, ACARS, RADIOSONDE, MARINE, LAND_SFC types), `adjust_obs_impact` + `obs_impact_filename` in `input.nml.filter`; replay check | replay: adapt `slurm.mrms_impact_test` to the conventional pass (its inputs are saved exactly: `output_madis_mrms2p_imp/<t>/memNNN/prior_d01.nc`, `filter/input_priorinf_*`, `filter/input.nml`; compare also with run 4b's `filter/postassim_member_*`) | user; no run going (changes `input.nml.filter`, used by every run) |
| 2 | `pass1` | `OBS_NAME=_madis_mrms MRMS_FILTER=two_pass MRMS_INFLATION=pass1 RUN_NAME=_madis_mrms2p_p1 sbatch slurm.cycle 202505200000 202505200100` | user's go-ahead; independent of step 1 (under `pass1` the hydrometeor λ is never applied, so the analyses are the same with or without the conventional table) |
| 3 | "Inflate once" mode (MRMS pass inflates only QRAIN QSNOW QGRAUP REFL_10CM; next cycle's λ composed from both passes) | code (Python helper called from `prep_filter.sh`, new `MRMS_INFLATION` value, `settings.txt`), login-node test, replay, 1-hour run | step 1; user's decisions on the name and the composition rule (note Sec. 8, item 3) |
| 4 | RTPS in both passes (HRRRDAS-like) | new setting in `experiment.sh` / `prep_filter.sh`; posterior `inf_flavor` 4, α in `inf_initial(2)` | after 2–3, if the user wants it |
| 5 | Run 5 | one pass: `OBS_NAME=_meso_a_calmkeep_mrms MRMS_FILTER=one_pass RUN_NAME=<to agree> sbatch slurm.cycle 202505200000 202505200100`; two pass: with `MRMS_FILTER=two_pass` and the inflation setting chosen from 2–4 | user's choice of one or two passes (and when: now, as one pass, or after the tests) |
| – | `real.exe` writes `REFL_10CM` (grid-file interim fix out) | steps in `obs_expansion.md` Sec. 9 (run 1's to-do); `FIRST_HOUR=24 LAST_HOUR=24 sbatch slurm.make_mean_icbc` (~3 min, 4 nodes) | user said: after runs 3 or 4, not during a run; still pending |

Run 5 notes: the mesonet types are in `&obs_kind_nml` of both `input.nml.filter` and `input.nml.filter_joint`, and
`obs_impact_joint.txt` has rows for all assimilated `LAND_SFC_*` types (`LAND_SFC_ALTIMETER` is evaluated only). With
the mesonet the conventional obs are ~2.5× (run 2: filter srun ~85–100 s). For a two-pass run 5, step 1's table must
cover the `LAND_SFC_*` types too (it does if built with `grep -v '^RADAR'`).

## After each run

1. `slurm.cycle.<job>.out`: every cycle `complete`, `driver: done`; "filter exit guard" / "wrf exit guard" lines
   (none expected; a firing leaves `filter_exit_guard.txt` / `wrf_exit_guard.txt` and, for `wrf.exe`, a
   `hang_snapshot/` with a summary); nodes (`sacct -j <job> -X --format=NodeList`).
2. Per-cycle checks: `output<RUN_NAME>/<t>/check_cycle.log` (QC per type, increments, spread, inflation per pass, NaNs,
   CFL, |dpsfc/dt| steps 2–4 and minutes 1–5 / 5–15). Compare with runs 3 and 4b at the same cycle.
3. Timing: `.venv/bin/python scripts/da/summarize_cycle_timing.py cases/20250520/da_theta_m0/output<RUN_NAME>
   --slurm-out cases/20250520/da_theta_m0/slurm.cycle.<job>.out`; add the rows to the run table in Sec. 9.
4. Radar QC per pass: `.venv/bin/python scripts/da/check_filter_gate.py obs <obs_seq.final>`.
5. Spread by stage and applied λ (until step 0 automates it): the ad-hoc numbers in `mrms_two_pass_inflation.md`
   Sec. 6 came from `input_sd.nc`, `preassim_sd.nc`, `postassim_sd.nc` and `preassim_priorinf_mean.nc` in
   `output<RUN_NAME>/<t>/filter*/` (domain RMS = sqrt of the mean variance over all points).
6. Record results in Sec. 9 as they come, and in `mrms_two_pass_inflation.md` where they bear on the inflation
   question; a discussion-log entry whenever `input.nml` settings, obs errors, localization, impact tables or
   inflation come up.

## Open questions for the user

- Which steps of the plan, in which order (proposed: 0 → 1 → 2, with 3 coded while 2 runs; 4–6 after).
- Run 5: one pass or two, when, and its `RUN_NAME`.
- Step 3: the mode's name, and whether the dynamics' λ for the next cycle keeps the radar's relative adaptation.
- Step 4 (RTPS): pursue? α (HRRRDAS: 1.08 on its 3-km domain; DART recommends 0–1).
- Disk: trim runs 1–4b (e.g. the per-member stage files in `output*/<t>/filter*/`) before more runs?
- When to do the `real.exe` `REFL_10CM` grid-file cleanup.

## Working rules

- **Jobs:** the user's go-ahead before every `sbatch`; one step at a time; report each result. `sbatch --test-only`
  checks a script without queuing it.
- **Environment:** `source scripts/env_wrf.sh` before DART or WRF tools; Python is `.venv/bin/python`. In Claude Code's
  shell `find` is `bfs` (no relative `-newermt`), `ls` is aliased with `-F` (use `command ls`).
- **Don't change files a running job uses** (each cycle re-reads the scripts and configs, including the impact
  tables), nor `GRID_FILE` during a run.
- **Notes:** results and decisions as they come (Sec. 9, `mrms_two_pass_inflation.md`); discussion-log entries for
  namelist matters.
- **Locations:** never modify `sey/`; observation downloads under `cases/20250520/obs/`; external repos in
  `../software/`; hand-offs in `notes/handoffs/`.
- **Git:** work and commit directly on `main`, no worktrees; commit only when the user decides to, and only this
  session's own files (`git add <paths>`); commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Transcripts:** project hooks write each session to `notes/transcripts/` (ignored by git) before compaction and on
  `/clear`.

## Next step

Read `notes/mrms_two_pass_inflation.md`; ask the user which test steps to do and in which order, and whether run 5 is
one or two passes; then start with the first chosen step (code changes need no go-ahead to write, but every job does).
