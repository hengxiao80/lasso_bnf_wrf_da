# Hand-off: "Adding more obs part 5: MRMS reflectivity into the cycle"

Written 2026-10-14 at the end of session "Adding more obs part 4" (mesonet wired in), after the commit that
wires mesonet into the cycle.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup).
- Read `CLAUDE.md` first.
- Main working note: `notes/obs_expansion.md`. §7.2 covers mesonet (done this session); §8 covers MRMS: 8.1 HRRR's
  program, 8.2 our converter and first file, 8.3 filter settings, 8.4 next steps.
- Namelist decisions: `notes/dart_namelist_discussion_log.md` (latest entries 2026-10-14: MRMS settings, nothing
  changed yet; mesonet wiring and the `r8 = r4` duplicate-location finding).
- Pilot details: `notes/da_5member_pilot_steps.md`, steps 7–13.

## Goal

Get MRMS reflectivity into the 1-hour, 5-member pilot: cold start at 00:00, then analyses at 00:15, 00:30, 00:45 and
01:00. It runs as `slurm.cycle` → `scripts/da/driver.sh`, with `RUN_NAME` giving `run*/` and `output*/`; about 32 min
on 40 nodes. Then run the test matrix, one run at a time.

**No runs until all coding, scripting and parameter changes for mesonet and MRMS are done (user, 2026-10-14).**
Then, in this order and only after the user's go-ahead:
1. **New reference run**: `OBS_NAME=_madis` (MADIS only, NCEP METAR errors). Not the old `_hph`: that used `obs/`,
   built with DART's default METAR errors, so comparing against it would change two things at once (decided by the
   user, 2026-10-14).
2. **+ mesonet**: `OBS_NAME=_meso_a_calmkeep`.
3. **+ MRMS**, and 4. **+ both**: observation sets still to build.

`RUN_NAME`s are still to agree with the user.

## Working rules

- **Jobs:** get the user's go-ahead before every `sbatch`. Run one step at a time and report each result.
- **Environment:** load `scripts/env_wrf.sh` before DART or WRF tools. Python is `.venv/bin/python` (no scipy;
  `eccodes`, `eccodeslib`, `netCDF4`, `numpy` are there).
- **Notes:** record results and decisions as we go. Add an entry to `notes/dart_namelist_discussion_log.md`
  whenever `input.nml` settings, observation errors or localization come up.
- **Locations:**
  - Never modify `sey/`.
  - Downloaded data goes under `cases/20250520/obs/`.
  - External repos go in `../software/`.
  - Hand-off messages go in `notes/handoffs/`.
- **Git:** work and commit directly on `main`, with no worktrees (changed by the user, 2026-10-14). Commit only when
  the user decides to. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Where things stand

### Mesonet: done and wired in (not yet run)

See `notes/obs_expansion.md` §7.2.
- **Observation sets.** `config/experiment.sh` has two new settings:
  - `OBS_NAME`: the set is `da_theta_m0/obs${OBS_NAME}/`.
  - `MESONET`: `none`, or e.g. `a_calmkeep`.

  `make_cycle_obs.sh` writes `obs_settings.txt` into each set and refuses to mix contents or to write into the old
  `obs/`. `driver.sh` adds the set to `settings.txt` when `OBS_NAME` is set.
  Built for 00:15–01:00:
  - `obs_madis/`: MADIS families only, NCEP METAR errors.
  - `obs_meso_a_calmkeep/`: the same plus mesonet option (a), calm winds kept.
- **`input.nml.filter`** assimilates `LAND_SFC_{U,V}_WIND_COMPONENT`, `_TEMPERATURE` and `_SPECIFIC_HUMIDITY`, and
  evaluates `LAND_SFC_ALTIMETER`.
- **Selection rules added this session** (`select_mesonet_cycle.py`, all logged per cycle in `selection.log`):
  - **2b:** drop mesonet sites within 4 km of a METAR report in the same window. This is because of the finding below.
  - **2c:** drop sites whose elevation is in feet. Inside the domain, a site is dropped if its elevation misfits the
    model terrain by > 100 m read as metres but < 60 m read as feet: 60–68 sites per cycle, nearly all APRSWXNET,
    listed in `dropped_feet.csv`.
- **Screened per cycle:** T ~1,660–1,800, q ~1,000, wind ~430–540, altimeter ~1,050. METAR counts are identical to
  `obs_madis/`.

### Finding that matters for MRMS too: under `r8 = r4`, DART distances below ~2 km are unreliable

- `wrf_dart_obs_preprocess` skips a supplemental report whose location "duplicates" one already in its sequence
  (`get_dist` ≤ 1e-5 rad). It checks horizontal position only, ignores times and types, and drops all of the
  report's variables.
- With our `r8 = r4` build, `get_dist` is float32 `acos`. It returns 0 for most pairs within ~1.5 km and for some up
  to 3.7 km apart.
- Mesonet before the fix: METAR stations near mesonet sites were silently dropped.
- For MRMS:
  - Radar obs sit on columns 2.5–7.5 km apart, with many levels at the same lat/lon. The preprocessor has no radar
    family (no `radar_extra`), so it would not even take them as an extra file.
  - If any DART tool with a "same location" test touches the MRMS obs, check what it does.
  - Localization is unaffected: weights are ~1 at those distances.

## MRMS: converter done, filter side not wired

See `notes/obs_expansion.md` §8.

- **Converter:** `scripts/da/mrms_to_obs_seq.py MRMS_DIR YYYYMMDDHHMM GEO_EM OUT [--grid-nc]`, a Python port of HRRR's
  `process_NSSL_mosaic_to_dart_and_netcdf.f90` with HRRRDAS's settings.
  - Bilinear interpolation to the mass grid.
  - Precipitation obs: Z ≥ 10 dBZ at 9 levels (0.5–11 km), every 2nd point.
  - Clear-air obs: −10 dBZ at 4.0 and 8.5 km, every 6th point.
  - Error 5 dBZ.
  - The obs time is the MRMS valid time; the file set is chosen by HRRRDAS's minute rule.
  - **Porting rather than building HRRR's program is an assumption in §8.2 still for the user to confirm.**
- **Data:** only the 00:14:38 set is downloaded (`cases/20250520/obs/mrms/20250520/`, 33 levels, 28 MB). Download
  the sets for 00:30, 00:45 and 01:00 the same way: AWS `noaa-mrms-pds`, HRRRDAS rule (minute mm, else mm−1, else
  mm−2).
- **Test file:** `cases/20250520/obs/obs_seq_mrms/obs_seq.mrms.2025052000_15`: 88,155 obs (79,075
  `RADAR_REFLECTIVITY`, 9,080 `RADAR_CLEARAIR_REFLECTIVITY`), all at 00:14:38.
- **WRF is patched:** `REFL_10CM` is in `wrfrst` (`patches/wrf_06d4240a_refl_10cm_restart.patch`, test job 1051956
  passed). The existing `run*/` restarts predate the patch, so **MRMS tests must start from the 00Z cold start.**

## To do, each a decision to make with the user

1. **Data and conversion:** download and convert 00:30, 00:45 and 01:00. Check the obs time against the window
   (t − 450 s, t + 450 s]: the HRRRDAS minute rule picks mm, mm−1 or mm−2, inside the window.
2. **How MRMS joins the per-cycle `obs_seq.out`.**
   - Preferred: merge after screening with `obs_sequence_tool` (two inputs, the screened conventional file and the
     MRMS file), inside `make_cycle_obs.sh`, switched by a new `experiment.sh` setting (e.g. `MRMS=none|hrrrdas`)
     recorded in `obs_settings.txt`.
   - The preprocessor's boundary trim does not apply then, so decide whether the converter trims the boundary zone
     itself (it already maps to the grid).
3. **DART state:**
   - `prep_filter.sh` calls `wrfrst_dart.py extract` without `--extra`; add `--extra REFL_10CM`.
   - Add `REFL_10CM` to `wrf_state_variables` as `QTY_RADAR_REFLECTIVITY`, `NO_COPY_BACK`. Check the type-column
     convention.
   - Hydrometeors (QCLOUD QRAIN QICE QSNOW QGRAUP QNICE QNRAIN) in the state, and whether they are `UPDATE`d, is
     Q8. HRRRDAS's reflectivity pass updates U, V, T, QV, QC, QR, QS, QG. `UPDATE` also needs
     `wrfrst_dart.py insert --fields`.
   - First check the spread of `REFL_10CM` and the hydrometeors across the 5 members, from a cold-start segment.
4. **`&obs_def_radar_mod_nml`:**
   - `microphysics_type = 5` (we have 2, which silently falls back to a Lin-type operator).
   - `apply_ref_limit_to_fwd_op = .true.`, `reflectivity_limit_fwd_op = -10.0`, `lowest_reflectivity_fwd_op = -10.0`
     (HRRRDAS's −10 dBZ floor on H(x), §8.3).
5. **Localization:**
   - 18-km zero influence → `cutoff` ≈ 0.00141 for both radar types via `special_localization_obs_types`.
   - Our vertical normalization ties the vertical width to `cutoff` (see the comment in `input.nml.filter`), so set
     `special_vert_normalization_obs_types` to keep HRRRDAS's 0.5 scale heights.
   - Decide between restricting what radar obs update (`obs_impact_tool`) and a separate `filter` pass. HRRRDAS
     uses RTPS 1.08 for its 3-km pass; our inflation is still the pilot's.
6. **Filter cost:** ~90k obs per cycle at convective times (vs ~7,500–9,800 conventional obs per cycle with mesonet). Check filter time and
   memory, ideally with a one-cycle filter-only test once 1–5 are in place.
7. **Test matrix and `RUN_NAME`s** with the user, then the runs in the order under Goal.

## Smaller items left for later

- Mesonet q needs an altimeter: about 700 sites per cycle have usable T and dewpoint but no q (converter patch
  possible; not decided).
- Feet-elevation sites on low terrain (misfit < 100 m) can't be detected. Watch APRSWXNET q innovations.
- The selection's lat/lon box is wider than the Lambert domain: 17–22 % of selected mesonet obs fall outside it.
  Harmless.
- Clear-air MRMS obs at echo edges (~9 %): optional one-point buffer (§8.2).
