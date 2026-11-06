# Hand-off: "fulltest: initial setup": 50-member ensembles for longer runs

Written 2026-11-06 at the end of session "Adding more obs part 10" (run 5, flavor 2 against flavor 5, commits `3b96171` and `812ae9c`). This hand-off and the new `fulltest` group in `.claude-sessions.toml` come in one commit if the user agreed; check `git status`. No jobs running.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup). Read `CLAUDE.md` first.

## The task

**Set up the first full tests: 50-member ensembles, cycled for longer than the 1-hour pilots** (user, 2026-11-06; "fulltest" is the new session group for this work, `.claude-sessions.toml`). This first session is the setup: agree the scope with the user, list what has to be built or decided, and start on it one step at a time.

- **Start by agreeing the scope with the user** (open questions below). Then propose a step list as a note, as `notes/da_5member_pilot_steps.md` was for the pilot (suggested name `notes/fulltest_steps.md`). Propose its outline and file name before writing it.
- **The 5-member tests are on hold** (user, 2026-11-06): SEC off, MRMS order reversed, RTPS mechanics, the flavor-5 wrong-root replay. Don't propose them as steps before the full test.
- **Why the move to 50 members now.** Inflation and the sampling-error correction behave very differently at 5 members, so settings tuned there won't carry over (`dart_sampling_error_correction.md` Sec. 8 item 3; `dart_adaptive_inflation.md` Sec. 3.2). Inflation is to be compared at the ensemble size we'll use, over a longer window.

## Settings carried over from run 5

**For most settings, follow the one-pass conv+MRMS 5-member runs** (user, 2026-11-06): run 5, `_conv_refl_f2` and `_conv_refl_f5` (`notes/obs_expansion.md` Sec. 9, run 5; `output_conv_refl_f2/settings.txt`). That means:

- **Setup:** `theta_m0` (`hybrid_opt = 0`, `use_theta_m = 0`), single 2.5-km domain, 15-min cycles with true WRF restarts, `HYDROSTATIC_PH=1`.
- **Observations:** MADIS (METAR, ACARS, radiosondes, marine) + mesonet option a with calm winds kept + MRMS reflectivity (HRRRDAS settings): `OBS_NAME=_meso_a_calmkeep_mrms`.
- **Filter:** one pass, `MRMS_FILTER=one_pass` (`config/input.nml.filter_joint`, impact table `config/obs_impact_joint.txt`); `outlier_threshold = 3`; `sampling_error_correction = .true.`; localization 300 km / 0.5 scale height (conventional) and 18 km / 0.5 scale height (radar).
- **Observation errors:** METAR and mesonet as patched (`CLAUDE.md`); radiosondes and ACARS DART's.
- **Layout:** filter on 40 nodes × 32 ranks with hcoll off; WRF 8 nodes per member with hcoll on and the exit guards (both may have to change at 50 members, see below).

**Inflation: flavor 2 for now** (user, 2026-11-06), as `_conv_refl_f2`: adaptive prior inflation, sd fixed at 0.6, damping 0.9, bounds [1, 5], no posterior inflation. These are the defaults of `experiment.sh` (`INF_FLAVOR=2`, `INF_DAMPING=0.9`, `INF_SD_LOWER_BOUND=0.6`). The two run-5 variants differed only here. Flavor 5 (sd floor 0.3) had a growing tail of points at the cap and two code defects (`dart_flavor5_wrong_root.md`; the float32 sd freeze, `dart_adaptive_inflation.md` Sec. 5.4). **Flavor 5 will be patched and tested later** (user, 2026-11-06): the root-choice patch (`patches/dart_7bbd35a09_flavor5_root_choice.patch`, not applied yet) needs a filter rebuild, which leaves flavor-2 results bit-identical (`dart_flavor5_wrong_root.md` Sec. 4.1). Not part of the setup unless the user says. RTPS (`inf_flavor(2) = 4`) stays an option for later (`dart_eakf.md` Sec. 10–11). Decision record: discussion log, 2026-11-06.

## What exists for 5 members, and what 50 members need

| item | now | for 50 members |
|---|---|---|
| bank | 15 draws | more (plan: 3 × N = 150) |
| members | 5, 00Z | 50, centered |
| member boundaries | 2 records | the whole period |
| boundary zone | 1 + 4 | 1 + 9 (Q18) |
| nodes per cycle | 40 | 400 at 8 per member |
| output per cycle | ~45 GB | ~10× (Q10) |
| obs sets | 00:15–01:00 | the whole period |

Details, row by row:

1. **Perturbation bank.** 15 WRFDA RANDOMCV draws in `cases/20250520/da_theta_m0/perts/bank/` (`slurm.pert_draw`, one node, ~1.7 min per draw, run as an array; `scripts/da/run_wrfda_draw.sh`, `wrfda_bank_diff.py`, `check_wrfda_draw.py`). The plan's rule is 3 × N, i.e. 150 for 50 members (`initial_plan_from_codex/LASSO_BNF_DA_Detailed_Implementation_Plan_rev2.md` Step 3B); the pilot's choice was 3 × 5 (pilot note Q2). Amplitudes are the tutorial's (Q3: 1.3 for U, V, THM, QVAPOR; 0.6 for MU).
2. **Initial members.** `scripts/da/assign_perturbations.py` (member × hour → bank-draw table, `perts/assignment.txt`) and `make_initial_members.py`; centered (Q4). No free spin-up: in the pilot the 15-min cycling from 00Z is the spin-up (pilot note Sec. 0, Q15). The plan's Phase 3E suggests a 6-h free spin-up as a first trial; that choice is open for the full test.
3. **Member boundaries.** `slurm.member_bdy` → `build_member_bdy.py` (patched `pert_wrf_bc`, one node, 5 members in 73 s) wrote only **2 records from 05-20 00Z** (its default `--hours 2`; `bdy/wrfbdy_d01_mean_2025-05-20_00_2h`, `bdy/wrfbdy_d01_memNNN`). A longer run needs member boundaries for its whole period. The hourly mean states exist from 05-19 00Z to 05-22 00Z (`mean/wrfinput_d01_*`, 73 files). Q5 (same bank draw for every hour, option A, or distinct draws per hour, option B) was left for after the pilot.
4. **Boundary zone (Q18).** The 50-member DA switches from 1 + 4 to 1 + 9 rows (`config/namelist.input.wrf`, `&bdy_control`: `spec_zone = 1`, `relax_zone = 9`; the boundary files already have 10 rows). A free control run with 1 + 9 is then needed for the DA-against-free comparison.
5. **Nodes and job structure (Q7, and pilot note step 14).** 50 members × 8 nodes = 400 nodes is not possible: `batch_all` has ~116 nodes (2026-11-06: 59 idle, 55 allocated, 1 drained). Options already listed (no decision): fewer nodes per member, members in waves inside one allocation, Slurm job arrays per cycle (filter job + member array with dependencies), chained shorter allocations. At 5 members a cycle took 515–587 s on 40 nodes (WRF segment 127–135 s on 8 nodes per member, filter step 133–164 s).
6. **Filter at 50 members: unmeasured.** Run 5's filter used 1.9 GB per task on 40 × 32 and spent 63–94 s in the observation loop for ~95,000 observations. Its memory and time at 50 members need a test (filter gate on 50 initial members, as `slurm.filter_gate` did for 5). `&ensemble_manager_nml :: tasks_per_node` must match the ranks per node.
7. **Output retention (Q10).** Each member writes per cycle `prior_d01.nc` and `analysis_d01.nc` (1.67 GB each), a `wrfout` (4.4 GB) and a refit `wrfbdy` (0.33 GB): ~45 GB per cycle with the filter files at 5 members, so ~400–450 GB per cycle and ~40 TB per simulated day at 50 members if everything is kept. Each member's `wrfrst` is 13.1 GB (650 GB for 50 in `run*/`). `num_output_state_members` and `num_output_obs_members` are 5 in the namelists. The current runs use 2.7 TB (`cases/20250520/da_theta_m0/`); the user said "not yet" to trimming on 2026-10-22, so ask again.
8. **Observations for the whole period.** Observation sets exist only for 00:15–01:00. MADIS is converted for every hour of 05-20 and 05-21 (`cases/20250520/obs/obs_seq_madis/`), but MRMS is downloaded only for 00:14, 00:30, 00:44 and 01:00 (`obs/mrms/20250520/`). Later cycles need `download_mrms.sh`, the mesonet selection (`make_cycle_mesonet.sh`) and `make_cycle_obs.sh` with `MESONET=a_calmkeep MRMS=hrrrdas` (`obs_expansion.md` Sec. 7–8).
9. **Places that assume 5 members.** At least `config/experiment.sh` (`NUM_ENS=5`), `ens_size` and `num_output_*_members` in the filter namelists, `slurm.cycle` (`--nodes=40`, `--time=02:00:00`), the `--nmem 5` default of `make_initial_members.py` and `build_member_bdy.py`, `perts/assignment.txt`. Find the rest with a grep before changing anything.
10. **Pending clean-up that the 50 members would inherit.** `GRID_FILE` is still `mean/dart_wrfinput_d01_2025-05-20_00_00_00` (made by `make_grid_file.py` because `real.exe`'s `wrfinput` lacks `REFL_10CM`). The decided fix (user, 2026-10-21) is for `real.exe` to write `REFL_10CM` itself (`FIRST_HOUR=24 LAST_HOUR=24 sbatch slurm.make_mean_icbc`; steps in `obs_expansion.md` Sec. 9, run 1). Also open: W possibly dropped from the state for the 50-member cycling (Q8).
11. **First real job under the new modules.** `env_wrf.sh` loads `Core/A100` since 2026-10-30 (`notes/cirrus_modules_core.md`). It was checked with `ldd` and a small MPI test on compute nodes, but no WRF or filter job has run since. Check the first job's logs with that in mind.

## Open questions for the user

- **Period and length:** which window (from 05-20 00Z as in the pilots, or a development window chosen by its precipitation, plan Step 1D) and how long; extend in steps (e.g. 1 h, 6 h, 24 h)?
- **Moist theta:** run the full test in `theta_m0`, or first implement the moist/dry conversion for `use_theta_m = 1`, the target configuration (`CLAUDE.md`, "Purpose and plan")?
- **Spin-up:** cycling from the 00Z cold start (as the pilot), or a free spin-up first (plan Phase 3E)?
- **Ensemble:** bank size (150?), boundary perturbation pattern over time (Q5 option A or B).
- **Layout:** nodes per member and job structure (item 5).
- **Retention and disk:** what to keep per cycle at 50 members; trimming the 5-member runs.
- **Free control run(s):** with the 1 + 9 boundary zone, how many members, which period.

## Sources at hand

- **Run results and settings:** `notes/obs_expansion.md` Sec. 9 (runs 1–5, timing table); `cases/20250520/da_theta_m0/output_conv_refl_f2/` and `output_conv_refl_f5/` (`settings.txt`, `<t>/check_cycle.log`).
- **Pilot step list and decisions Q1–Q18:** `notes/da_5member_pilot_steps.md` (Sec. 2 step 14 for the job-structure options, Sec. 4 for the decisions).
- **The plan for 50 members:** `initial_plan_from_codex/LASSO_BNF_DA_Detailed_Implementation_Plan_rev2.md`, Phase 3 (bank, 50 centered members, boundaries, spin-up), Phase 4 (cycling, a multi-hour 50-member pilot) and Phase 5A (cost profile). Direction, not finished details (`CLAUDE.md`).
- **DA method notes:** `dart_eakf.md`, `dart_sampling_error_correction.md`, `dart_adaptive_inflation.md`, `dart_flavor5_wrong_root.md`; namelist decisions in `dart_namelist_discussion_log.md`.
- **Scripts:** `scripts/da/` (the cycle: `slurm.cycle` → `driver.sh` → `cycle_job.sh`, `prep_filter.sh`, `post_filter.sh`, `advance_member.sh`, `check_cycle.py`; timing: `summarize_cycle_timing.py`); job scripts and their logs in `cases/20250520/da_theta_m0/`.

## Working rules

- **Jobs:** the user's go-ahead before every `sbatch`; one step at a time; report each result. `sbatch --test-only` checks a script without queuing it. A full-size run is a production run: confirm before it, even after a successful test.
- **Commits:** only after the user has reviewed the changes and said so; on `main`, only the session's own files (`git add <paths>`); commits end with `Co-Authored-By: Claude ...`. Push to GitHub only when asked.
- **Step order:** follow the order the user sets; a gate is a hard stop.
- **Don't change files a running job uses** (each cycle re-reads the scripts and configs), nor `GRID_FILE` during a run.
- **Notes:** results and decisions as they come; discussion-log entries for namelist matters. Typora rules (`~/.claude/rules/typora-markdown.md`): no hard-wrapped prose (unwrap all of a note's prose when editing it; `obs_expansion.md` is still mostly hard-wrapped), narrow tables, `\tag`/`\notag` on every `$$` block. No LaTeX in chat.
- **Environment:** `source scripts/env_wrf.sh` before DART or WRF tools; Python is `.venv/bin/python`; `ls` is aliased with `-F` (use `command ls` or `find`).
- **Locations:** never modify `sey/`; observation downloads under `cases/20250520/obs/`; external repos in `../software/`; hand-offs in `notes/handoffs/`.

## Starting the session

Name it `fulltest: initial setup` (it then files into the `fulltest` group), and name this file in the first prompt (`notes/handoffs/2026-11-06_fulltest_initial_setup.md`).
