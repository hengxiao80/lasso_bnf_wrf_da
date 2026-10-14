# Hand-off: "Adding more obs part 4: pilot tests with mesonet and MRMS reflectivity"

Written 2026-10-14 at the end of session "Adding more obs part 3" (MRMS reflectivity), after commit `19bf43b`.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup).
- Read `CLAUDE.md` first.
- Main working note: `notes/obs_expansion.md`. §7 covers mesonet; §8 covers MRMS: 8.1 HRRR's program, 8.2 our converter and first file, 8.3 filter settings, 8.4 next steps.
- Pilot details: `notes/da_5member_pilot_steps.md`, steps 7–13.

## Goal

A few tests with mesonet and MRMS reflectivity on the 5-member pilot setup. The setup is a 1-hour pilot: cold start at 00:00, then analyses at 00:15, 00:30, 00:45 and 01:00, about 32 min on 40 nodes. It runs as `slurm.cycle` → `scripts/da/driver.sh`, with `RUN_NAME` giving `run*/` and `output*/` and `HYDROSTATIC_PH=1` as the default. The existing `_hph` run (MADIS only) is the reference. One possible set of runs, to plan with the user first:
1. + mesonet
2. + MRMS
3. + both

Step 14 of the pilot (the extension) and the fuller inflation tests are still postponed.

## Working rules

- **Jobs:** get the user's go-ahead before every `sbatch`. Run one step at a time and report each result.
- **Environment:** load `scripts/env_wrf.sh` before DART or WRF tools. Python is `.venv/bin/python`; `eccodes` and `eccodeslib` are installed.
- **Notes:** record results and decisions as we go. Add an entry to `notes/dart_namelist_discussion_log.md` whenever `input.nml` settings, observation errors or localization come up. Refer to defined items by their IDs consistently.
- **Locations:**
  - Never modify `sey/`.
  - Downloaded data goes under `cases/20250520/obs/`.
  - External repos go in `../software/`.
  - Hand-off messages go in `notes/handoffs/`.
- **Git:** work in a worktree. When the user decides something is worth committing, commit, fast-forward `main`, and remove the worktree. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Mesonet: built but not wired in

See `notes/obs_expansion.md` §7.2, "Not wired in yet".

- `scripts/da/make_cycle_mesonet.sh <YYYYMMDDHHMM> [a|b1|c] [keep|drop]` builds a cycle's `obs_seq.land_sfc`. Use option (a) with calm winds kept for the first tests.
- Errors are RAP/RRFS values (`patches/dart_7bbd35a09_madis_mesonet_obs_errors.patch`).
- Still to do:
  - `make_cycle_obs.sh` must copy the cycle's `obs_seq.land_sfc` into `prep/` (`input.nml.obs_preprocess` already names `land_sfc_extra`).
  - `input.nml.filter` must assimilate `LAND_SFC_{TEMPERATURE,SPECIFIC_HUMIDITY,U/V_WIND_COMPONENT}` and evaluate `LAND_SFC_ALTIMETER`.
  - Make the option and calm setting per-run settings in `experiment.sh` and `settings.txt`.
- Open: about 700 sites per cycle get no q, because the converter needs an altimeter.
- About 2,450 stations per cycle. Watch low-level spread and the consistency ratios.

## MRMS: converter done, filter side not wired

See `notes/obs_expansion.md` §8.

- **Converter:** `scripts/da/mrms_to_obs_seq.py MRMS_DIR YYYYMMDDHHMM GEO_EM OUT [--grid-nc]`, a Python port of HRRR's `process_NSSL_mosaic_to_dart_and_netcdf.f90` with HRRRDAS's settings.
  - Bilinear interpolation to the mass grid; precipitation obs Z ≥ 10 dBZ at 9 levels (0.5–11 km), every 2nd point; clear-air obs −10 dBZ at 4.0 and 8.5 km, every 6th point; error 5 dBZ.
  - The obs time is the MRMS valid time. The file set is chosen by HRRRDAS's minute rule.
  - Thinning was decided: keep HRRRDAS's grid-point skips. MRMS codes: −999 = No Coverage, −99 = "Missing" (covered, no echo).
- **Data:** only the 00:14:38 set is downloaded (`cases/20250520/obs/mrms/20250520/`, 33 levels, 28 MB). Download the sets for 00:30, 00:45 and 01:00 the same way (AWS `noaa-mrms-pds`, HRRRDAS rule: minute mm, else mm−1, else mm−2).
- **Test file:** `cases/20250520/obs/obs_seq_mrms/obs_seq.mrms.2025052000_15` has 88,155 obs (79,075 `RADAR_REFLECTIVITY`, 9,080 `RADAR_CLEARAIR_REFLECTIVITY`). DART's `obs_sequence_tool` reads it.
- **Still to decide:** how MRMS joins the per-cycle `obs_seq.out`. Either pass it through `wrf_dart_obs_preprocess`, checking what its boundary trim and screening do to radar obs, or merge it after with `obs_sequence_tool`.
- **Filter cost:** about 90k obs per cycle at convective times. Check filter time and memory.

## WRF is patched; new restarts carry `REFL_10CM`

- `patches/wrf_06d4240a_refl_10cm_restart.patch` changes `refl_10cm`'s I/O flags `hdu` → `hdur`. WRF was rebuilt on 2026-10-14; the old executables are kept as `main/*.exe.pre_refl_restart`.
- Test job 1051956 passed:
  - `REFL_10CM` in `wrfrst` is bit-identical to `wrfout`;
  - nothing else changed;
  - restarts from pre-patch files work.
- The existing `run*/` restarts are pre-patch and lack `REFL_10CM`, so MRMS tests must start from the 00Z cold start.

## DART side for MRMS: to do, each a decision to make with the user

- **State:**
  - `prep_filter.sh` calls `wrfrst_dart.py extract` without `--extra`. Add `--extra REFL_10CM`, which copies any field, 3-D included.
  - Add `REFL_10CM` to `wrf_state_variables` as `QTY_RADAR_REFLECTIVITY`, `NO_COPY_BACK`. `model_mod` finds it by the name `REFL_10CM`; check the type-column convention.
  - Hydrometeors (QCLOUD QRAIN QICE QSNOW QGRAUP QNICE QNRAIN) are in `wrfrst` and can be extracted the same way. Whether they go in the state and are `UPDATE`d is Q8: HRRRDAS's reflectivity pass updates U, V, T, QV, QC, QR, QS, QG. `UPDATE` would also need `insert --fields`. Check the hydrometeor and `REFL_10CM` spread in the 5 members first.
- **`&obs_def_radar_mod_nml`:**
  - `microphysics_type = 5`; we have 2, which silently falls back to a Lin-type operator.
  - `apply_ref_limit_to_fwd_op = .true.`, `reflectivity_limit_fwd_op = -10.0`, `lowest_reflectivity_fwd_op = -10.0`. This matches HRRRDAS's `static_gsi_nopcp_dbz = -10` floor on H(x) (§8.3).
- **Localization:**
  - HRRRDAS's 18-km zero influence corresponds to `cutoff` ≈ 0.00141 for both radar types via `special_localization_obs_types`.
  - Caution: our vertical normalization ties the vertical width to `cutoff` (see the comment in `input.nml.filter`). At 0.00141 the vertical influence would be tiny, so use `special_vert_normalization_obs_types` (supported by `threed_sphere/location_mod`) to keep HRRRDAS's 0.5 scale heights.
  - Decide whether to restrict which quantities radar obs update (`obs_impact_tool`) or run a separate `filter` pass. HRRRDAS uses RTPS 1.08 for its 3-km pass; our inflation is still the pilot's.
- Every change to `input.nml` needs an entry in the discussion log; there is already a 2026-10-14 MRMS entry.

## Suggested first steps

1. Wire mesonet into `make_cycle_obs.sh`, `input.nml.filter` and `experiment.sh`, and build the per-cycle obs for 00:15–01:00.
2. Download MRMS for the remaining three times; convert all four; decide how they join `obs_seq.out`.
3. Make the DART state and namelist changes for MRMS. Check `REFL_10CM`/hydrometeor spread from a cold-start segment before the full pilot.
4. Plan the test matrix and `RUN_NAME`s with the user, then run one at a time.
