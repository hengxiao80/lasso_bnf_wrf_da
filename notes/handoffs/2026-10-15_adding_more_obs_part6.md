# Hand-off: "Adding more obs part 6: first runs with MRMS"

Written 2026-10-15 at the end of session "Adding more obs part 5" (MRMS reflectivity into the cycle). **Nothing from
that session is committed yet**; see "Uncommitted work" below.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup).
- Read `CLAUDE.md` first.
- Main working note: `notes/obs_expansion.md` §8 (MRMS): 8.2 converter, 8.3 settings, 8.4 two-pass design (with the
  three QNRAIN rules), 8.5 one-pass alternative.
- Namelist decisions: `notes/dart_namelist_discussion_log.md`. Entries from this session (2026-10-14/15): two-pass,
  one-pass, pass-2 damping, and inflation (damping, flavor 5 with an evolving sd).
- Pilot details: `notes/da_5member_pilot_steps.md`, steps 7–13 (Q13 for inflation).
- Previous hand-off: `notes/handoffs/2026-10-14_adding_more_obs_part5.md`.

## Goal

Run the test matrix on the 1-hour, 5-member pilot: cold start at 00:00, analyses at 00:15–01:00, via `slurm.cycle` →
`scripts/da/driver.sh`, about 32 min on 40 nodes without MRMS. Each run gets its own `RUN_NAME` (`run*/`, `output*/`).

The rule "no runs until all coding for mesonet and MRMS is done" (user, 2026-10-14) is met as far as the code goes:
everything is built. Nothing has been run with it, and none of the new namelists or the impact table has been read by
DART yet. In this order, each only after the user's go-ahead:
1. **Reference run**: `OBS_NAME=_madis`. Also the first test of the new pass-1 namelist (QCLOUD updated,
   hydrometeors and `REFL_10CM` in the state).
2. **+ mesonet**: `OBS_NAME=_meso_a_calmkeep`.
3. **+ MRMS**: `OBS_NAME=_madis_mrms` with `MRMS_FILTER=two_pass` (needs `MRMS_INFLATION`) or `one_pass`.
4. **+ both**: `OBS_NAME=_meso_a_calmkeep_mrms`.

`RUN_NAME`s are still to agree. Proposed: `_madis`, `_meso_a`, `_madis_mrms2p` / `_madis_mrms1p`, and mesonet versions.
For the first MRMS cycle check filter wall time and memory, and the DART QC counts for the radar types (see the outlier
check below).

All new runs start from the 00Z cold start: they need `REFL_10CM` in the restarts (WRF patched 2026-10-14), so the old
`run*/` directories can't be resumed.

## Working rules

- **Jobs:** get the user's go-ahead before every `sbatch`. Run one step at a time and report each result.
- **Environment:** load `scripts/env_wrf.sh` before DART or WRF tools. Python is `.venv/bin/python`.
- **Notes:** record results and decisions as we go. Add an entry to `notes/dart_namelist_discussion_log.md` whenever
  `input.nml` settings, observation errors, localization or inflation come up.
- **Locations:** never modify `sey/`; downloads under `cases/20250520/obs/`; external repos in `../software/`;
  hand-offs in `notes/handoffs/`.
- **Git:** work and commit directly on `main`, no worktrees. Commit only when the user decides to. Commits end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Transcripts (new, 2026-10-15):** project hooks in `.claude/settings.json` run `scripts/transcript_to_md.py` before
  every compaction and on `/clear`, writing the full session to `notes/transcripts/*.md` (tool results in full,
  thinking left out). `.claude/` and `notes/transcripts/` are ignored by git. Tested by hand with sample hook input;
  the real hooks had not yet fired when this was written (the user restarted the CLI to load them). After the first
  compaction, check that a file appeared there.

## Where things stand

### MRMS, built and checked by hand (not run)

- **Data:** `scripts/da/download_mrms.sh <t>` (AWS `noaa-mrms-pds`, HRRRDAS minute rule). Sets for 00:15–01:00 are in
  `cases/20250520/obs/mrms/20250520/`.
- **Converter:** `scripts/da/mrms_to_obs_seq.py`, now with the preprocessor's boundary trim and error inflation
  (`--obs-boundary 5`, `--obsdistbdy 15`, `--maxobsfac 2.5`) and `--window-half 450`.
- **Observation sets:** `MRMS=hrrrdas` in `make_cycle_obs.sh` writes `<t>/obs_seq.mrms` and the merged
  `<t>/obs_seq.joint`. Built: `obs_madis_mrms/` and `obs_meso_a_calmkeep_mrms/` (00:15 joint counts 88,332 and
  93,094). Their conventional `obs_seq.out` is byte-identical to `obs_madis/` and `obs_meso_a_calmkeep/`.
- **Two-pass filter (HRRRDAS-like):** pass 1 `config/input.nml.filter` (conventional), pass 2
  `config/input.nml.filter_mrms` (radar only; updates U, V, THM, QVAPOR, QCLOUD, QRAIN, QSNOW, QGRAUP; 18-km /
  0.5-scale-height localization). Then `wrfrst_dart.py qnrain` (Thompson 1-mm rule where QRAIN changed).
- **One-pass alternative:** `MRMS_FILTER=one_pass` uses `config/input.nml.filter_joint` and the impact table
  `config/obs_impact_joint.txt`.
- **Settings in `config/experiment.sh`:**
  - `MRMS_FILTER` (`two_pass` | `one_pass`): no default, required for MRMS sets.
  - `MRMS_INFLATION` (`pass1` | `both`): no default, required for two-pass. **Undecided; the user is researching it.**
  - `MRMS_PASS2_DAMPING` (default 1): with `both`, pass 2 also damps the inflation with `INF_DAMPING`.
  - `INF_SD_LOWER_BOUND` (new, default 0.6 = no change): below 0.6 the inflation sd can evolve; it is what makes
    a real flavor-5 test possible (the pilot's `_hph_f5` kept sd = 0.6). Written by `prep_filter.sh` into every
    inflating pass; `driver.sh` accepts 0 < value ≤ 0.6 and records it in `settings.txt` when not 0.6. Tested on
    namelist copies only.

### Open questions for the user

- **Inflation** (`MRMS_INFLATION`; `INF_DAMPING` 0.9 vs 0.9956; flavor 5 with which `INF_SD_LOWER_BOUND`). Candidate
  runs listed in the 2026-10-15 discussion-log entry. DART's guide also recommends `inf_lower_bound = 0` for flavor 5;
  ours stays 1.0.
- **Outlier check on radar obs:** `outlier_threshold = 3` (`&quality_control_nml`) applies to all types: rejected if
  |mean H(x) − y| > 3·sqrt(var H(x) + σ_o²) (`quality_control_mod.f90:241`, called from
  `forward_operator_mod.f90:348`, prior only, after prior inflation). Zero-spread obs couldn't update anyway; the
  concern is small-but-nonzero spread. Plan: look at the QC-7 counts in the first MRMS `obs_seq.final`. Options if
  needed: `-1` in `input.nml.filter_mrms` only (two-pass), or `enable_special_outlier_code` (needs a DART source edit).
  Not yet checked whether HRRRDAS's EnKF has a similar check.
- **Impact table:** conventional → `QTY_RADAR_REFLECTIVITY` is 0 (radar priors stay at the background, as HRRRDAS);
  1 is the alternative.
- **QCLOUD** is now updated in every run's conventional pass, including the reference.
- Smaller, later: mesonet q needs an altimeter; feet-elevation sites on low terrain; clear-air obs at echo edges;
  `model_mod_check` (deferred).

## Uncommitted work

Modified: `CLAUDE.md`, `.gitignore`, `config/experiment.sh`, `config/input.nml.filter`, `slurm.cycle`,
`notes/dart_namelist_discussion_log.md`, `notes/obs_expansion.md`, and in `scripts/da/`: `check_cycle.py`,
`check_filter_gate.py`, `cycle_job.sh`, `cycle_lib.sh`, `driver.sh`, `make_cycle_obs.sh`, `mrms_to_obs_seq.py`,
`post_filter.sh`, `prep_filter.sh`, `wrfrst_dart.py`.
New: `config/input.nml.filter_mrms`, `config/input.nml.filter_joint`, `config/obs_impact_joint.txt`,
`scripts/da/download_mrms.sh`, `scripts/transcript_to_md.py`, this hand-off. (The two Dowell PDFs in `notes/` were
already untracked.) `config/` paths are under `cases/20250520/da_theta_m0/`.

## Next step

Ask the user whether to commit first, agree the `RUN_NAME`s, then (with go-ahead) submit the `_madis` reference run:
`OBS_NAME=_madis RUN_NAME=<name> sbatch slurm.cycle 202505200000 202505200100` from `cases/20250520/da_theta_m0/`
(forms for MRMS runs in `slurm.cycle`'s header comment).
