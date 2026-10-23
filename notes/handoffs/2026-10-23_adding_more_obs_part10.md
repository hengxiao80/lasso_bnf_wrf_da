# Hand-off: "Adding more obs part 10": run 5 in one pass, inflation flavor 2 against 5

Written 2026-10-23 at the end of session "Adding more obs part 9" (spread diagnostics, conventional-pass impact table,
decision to drop the two-pass setup). Commit `d9b1d46` has steps 0 and 1. The decision record (notes, `CLAUDE.md`) and
this hand-off come in the commit after it if the user agreed at the end of the session; check `git status`. The two
Dowell PDFs in `notes/` stay untracked, as before. No jobs running.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup).
- Read `CLAUDE.md` first (status updated for the one-pass decision).
- **Decision and its reasons: `notes/mrms_two_pass_inflation.md` Sec. 9**; the measurements behind it: Sec. 6 (spread by
  stage, incl. the forecast → analysis table for runs 3 and 4b), Sec. 8 (the test plan; steps 0 and 1 done, 2 and 3
  dropped).
- Run results and timing: `notes/obs_expansion.md` Sec. 9 (runs 1–4b; run 5 row updated). One-pass design: Sec. 8.5.
- Namelist decisions: `notes/dart_namelist_discussion_log.md`, entries of 2026-10-23 (conventional-pass table; one
  pass), and 2026-10-15 ("Inflation for the MRMS runs: damping, flavor 5 with an evolving sd").
- Previous hand-off: `notes/handoffs/2026-10-22_adding_more_obs_part9.md`.

## What this session did (2026-10-22/23)

1. **Spread by stage in `scripts/da/check_cycle.py`** (plan step 0). Every `check_cycle.log` now has a "spread by stage"
   section: per pass, domain RMS sd of U V THM QVAPOR QCLOUD QRAIN QSNOW QGRAUP MU before inflation (`input_sd`),
   after (`preassim_sd`) and after assimilation (`postassim_sd`), applied λ (`preassim_priorinf_mean`: mean, share
   > 1.1, max), over all points and over echo columns (background mean REFL_10CM ≥ 10 dBZ at some level, or an MRMS
   precipitation ob in or next to the column); then forecast → analysis over the cycle. ~20 s per cycle; a failure
   there is printed, not counted as a problem. `--spread-only` backfills old runs: runs 3, 4, 4b are in
   `output<RUN_NAME>/<t>/spread_by_stage.log`. Radar obs are matched to grid columns by location; `obs_seq.final` has
   locations at single precision (DART `r8 = r4`), handled by a 0.001° key with neighbours (all obs match).
   `read_obs_seq(path, locations=True)` in `check_filter_gate.py` returns the locations.
   - **Result:** from 00:45 on, two-pass analyses end with more U, V, THM, QVAPOR spread than their forecast
     (U ×1.04 all points, ×1.08 echo columns); run 3 (one pass) reduces spread every cycle. 00:45 has few surface
     obs (32 METAR altimeters against 139–313).
2. **Conventional-pass impact table** (plan step 1): `config/obs_impact_conv.txt` (88 non-radar rows of
   `obs_impact_joint.txt`) named in `input.nml.filter`. Filter's reader takes no groups or comments. Replay
   `slurm.conv_impact_test` (job 1056509): no-table replay = run 4b's pass bit for bit; with the table members and
   `obs_seq.final` bit-identical, λ different only in QRAIN QSNOW QGRAUP REFL_10CM. Affects only the first pass of
   conventional-only runs now (nothing that reaches WRF); one-pass MRMS runs use `input.nml.filter_joint`.
3. **Decision (user, 2026-10-23): one pass from run 5 on; two-pass tests stopped.** HRRRDAS's reason for two passes
   isn't stated in Dowell 2020 or Dowell et al. 2022; DART does per family in one pass what HRRRDAS separates; no
   advantage found for two passes, which cost more. The two-pass code stays, unused.

## Goal for the next session

1. **Run 5 (everything: MADIS + mesonet option a + MRMS) in one pass, flavor 2 against flavor 5.**
2. Later (not this session unless the user says): RTPS; then run 5 again with a larger ensemble, once the inflation is
   settled (user, 2026-10-23).

| order (proposed) | what | command / work (from `cases/20250520/da_theta_m0/`) | needs before |
|---|---|---|---|
| 1 | run 5, flavor 2 (as run 3: `INF_FLAVOR=2`, `INF_DAMPING=0.9`, sd 0.6) | `OBS_NAME=_meso_a_calmkeep_mrms MRMS_FILTER=one_pass RUN_NAME=<to agree> sbatch slurm.cycle 202505200000 202505200100` | user: `RUN_NAME`, go-ahead |
| 2 | run 5, flavor 5 | same + `INF_FLAVOR=5 INF_SD_LOWER_BOUND=<value>` | user: the sd bound (see below), `RUN_NAME`, go-ahead |
| 3 | RTPS (later) | code: posterior `inf_flavor` 4 with α in `inf_initial(2)`, prior flavor 0; new setting in `experiment.sh`, `prep_filter.sh` (sets only the first column today), `driver.sh`/`settings.txt`, and the inflation-file hand-over and `check_cycle.py`'s inflation checks for runs without prior inflation | user's go-ahead on the design |
| 4 | larger ensemble (later) | see "Larger ensemble" below | inflation settled |

**Run 5 notes**
- Observation set `obs_meso_a_calmkeep_mrms/` is built for 00:15–01:00 (`obs_seq.joint` in each cycle;
  `mesonet=a_calmkeep mrms=hrrrdas`). `input.nml.filter_joint` and `obs_impact_joint.txt` cover all `LAND_SFC_*`
  types (`LAND_SFC_ALTIMETER` evaluated only). `MRMS_INFLATION` must be unset for one pass (`driver.sh` refuses it).
- Expected cost: conventional obs ~2.5× run 3's (run 2: ~7.5–9.8k per cycle) plus ~85–89k radar obs; run 3's cycles
  were ~620–680 s. Disk ~0.41 TB per run (run 3: `output` 336 GB + `run` 77 GB).
- **Flavor 5 needs `INF_SD_LOWER_BOUND` below 0.6**, or the sd stays 0.6 and only the inverse-gamma update of the mean
  differs (step 13's `_hph_f5` showed exactly that: about half of flavor 2's inflation). `driver.sh` accepts
  0 < value ≤ 0.6 and records it in `settings.txt`. No value chosen yet. DART's guide also suggests
  `inf_lower_bound = 0` (deflation) for flavor 5; ours is 1.0 in the namelists and not a per-run setting (would need a
  code change if wanted). `inf_sd_max_change = 1.05`: an sd update larger than that per observation is skipped.
- Compare: flavor 2 against run 3 (effect of the mesonet with MRMS) and against run 2 (effect of MRMS with the
  mesonet); flavor 5 against flavor 2. Look at the spread section of `check_cycle.log` (now routine), the |dpsfc/dt|
  lines, the QC per type, the applied λ.

**Larger ensemble (later; open items already recorded):** `notes/da_5member_pilot_steps.md` Q7 (8 nodes per member
gives 400 nodes for 50 members, not realistic on Cirrus; job arrays discussed 2026-10-20, no decision), Q10 (output
retention: ~18 TB/day of member analyses at 50 members × 96 cycles), Q18 (boundary zone 1 + 9 for the 50-member DA,
plus a free control run with 1 + 9), W possibly dropped from the state (Q8). The perturbation bank has 15 draws;
50 members need more draws (`slurm.pert_draw`) and per-member boundaries (`slurm.member_bdy`).

**Longer runs** (plan step 6, still wanted): observation sets exist only for 00:15–01:00. MRMS is downloaded only for
00:14, 00:30, 00:44, 01:00 (`cases/20250520/obs/mrms/20250520/`): later cycles need `download_mrms.sh`, the mesonet
selection (`make_cycle_mesonet.sh`) and `make_cycle_obs.sh`; MADIS hours for 05-20/21 are converted.

## After each run

1. `slurm.cycle.<job>.out`: every cycle `complete`, `driver: done`; "filter exit guard" / "wrf exit guard" lines
   (none expected); nodes (`sacct -j <job> -X --format=NodeList`).
2. `output<RUN_NAME>/<t>/check_cycle.log`: QC per type, increments, **spread by stage** (all points and echo columns,
   forecast → analysis), inflation, NaNs, CFL, |dpsfc/dt| steps 2–4 and minutes 1–5 / 5–15. Compare with run 3 at the
   same cycle (`output_madis_mrms1p/<t>/check_cycle.log` and `spread_by_stage.log`).
3. Timing: `.venv/bin/python scripts/da/summarize_cycle_timing.py cases/20250520/da_theta_m0/output<RUN_NAME>
   --slurm-out cases/20250520/da_theta_m0/slurm.cycle.<job>.out`; add the rows to the run table in
   `obs_expansion.md` Sec. 9.
4. Radar QC: `.venv/bin/python scripts/da/check_filter_gate.py obs <obs_seq.final>`.
5. Record results in `obs_expansion.md` Sec. 9; a discussion-log entry for the inflation settings and outcome.

## Open questions for the user

- `RUN_NAME`s for the two run-5 variants (e.g. `_all1p_f2`, `_all1p_f5`; none agreed).
- Flavor 5: the value of `INF_SD_LOWER_BOUND`; whether to allow deflation (`inf_lower_bound = 0`, needs code).
- Order and timing: flavor 2 first, then 5 (one at a time, each after a go-ahead)?
- Disk: runs 1–4b ~2.3 TB plus step-13 dirs ~0.33 TB; two run-5 variants add ~0.8 TB. The user said "not yet" to
  trimming on 2026-10-22; ask again before the larger ensemble or longer runs.
- RTPS: α (HRRRDAS 1.08 on 3 km; DART's guide recommends 0–1) and whether it replaces or joins the adaptive prior
  inflation.
- When to do the `real.exe` `REFL_10CM` grid-file cleanup (steps in `obs_expansion.md` Sec. 9, run 1's to-do;
  `FIRST_HOUR=24 LAST_HOUR=24 sbatch slurm.make_mean_icbc`); still pending.

## Working rules

- **Jobs:** the user's go-ahead before every `sbatch`; one step at a time; report each result. `sbatch --test-only`
  checks a script without queuing it.
- **Environment:** `source scripts/env_wrf.sh` before DART or WRF tools; Python is `.venv/bin/python`. In Claude Code's
  shell `find` is `bfs`, `ls` is aliased with `-F` (use `command ls`). No PDF tools on the system (no poppler); to read
  the PDFs in `notes/`, install `pypdf` into the session's scratch dir (`uv pip install --target <scratch>/pylib pypdf`,
  then `PYTHONPATH=<scratch>/pylib`), not into the project environment.
- **Don't change files a running job uses** (each cycle re-reads the scripts and configs, including the impact
  tables and `check_cycle.py`), nor `GRID_FILE` during a run.
- **Notes:** results and decisions as they come; discussion-log entries for namelist matters (inflation included).
- **Locations:** never modify `sey/`; observation downloads under `cases/20250520/obs/`; external repos in
  `../software/`; hand-offs in `notes/handoffs/`.
- **Git:** work and commit directly on `main`, no worktrees; commit only when the user decides to, and only the
  session's own files (`git add <paths>`); commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Transcripts:** project hooks write each session to `notes/transcripts/` (ignored by git).

## Next step

Ask the user for the run-5 `RUN_NAME`s and the flavor-5 sd bound, then (with the go-ahead) submit run 5 with flavor 2.
