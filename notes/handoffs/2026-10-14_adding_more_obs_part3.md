# Hand-off: "Adding more obs part 3: MRMS reflectivity"

Given by the user at the start of session "Adding more obs part 3" (2026-10-14), after commit `ca3ef80`. Saved
verbatim; what that session found and corrected is in `notes/obs_expansion.md` §1 and §8 (e.g. the mapping is
bilinear, not a max; clear-air thinning is every 6th point, not every 5th; `microphysics_type` is 2 in our
`input.nml.filter`). Next: `2026-10-14_adding_more_obs_part4.md`.

---

Repo: /gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da (WRF-DART for LASSO BNF, case 2025-05-20, theta_m0 setup).
- Read CLAUDE.md first.
- Main working note: notes/obs_expansion.md. §1 covers HRRRDAS (including its reflectivity pass), §2 what our filter can take, §3 targets, §6 the family order, §7 mesonet.
- Last commit: ca3ef80.

Goal: add MRMS 3-D reflectivity, following HRRRDAS. This is family 2 in the agreed order: mesonet, then MRMS, then radial velocity, then GOES satellite winds, then VAD winds. Step 14 of the pilot (the extension) and the fuller inflation tests are still postponed.

Working rules
- Jobs: get my go-ahead before every sbatch. Run one step at a time and report each result.
- Environment: load scripts/env_wrf.sh before DART tools. Python is .venv/bin/python; PyYAML is now installed.
- Notes: record results and decisions as we go. Add an entry to notes/dart_namelist_discussion_log.md whenever input.nml settings, observation errors or localization come up. Refer to defined items by their IDs consistently.
- Locations:
  - Never modify sey/.
  - Downloaded data goes under cases/20250520/obs/.
  - External repos go in ../software/, one per system, with a unique name: HRRR, GSI, RRFSv1, RRFSv2, GSI-fix_subset. Commits are in notes/mesonet_station_selection.md §1.
- Git: work in a worktree. When I decide something is worth committing, commit, fast-forward main, and remove the worktree. Commits end with Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>.

Established for reflectivity (obs_expansion.md §1–3; code in ../software/HRRR):
- HRRRDAS reflectivity pass:
  - It runs as its own serial EnKF pass after the conventional one, with an 18-km zero-influence distance (DART cutoff ≈ 0.00141) and RTPS 1.08.
  - Its anavinfo adds QRAIN, QSNOW and QGRAUPEL (per Dowell 2020; the file isn't public).
  - H(x) is WRF's own REFL_10CM (if_model_dbz = .true.).
- MRMS preprocessing (scripts/hrrrdas/exhrrr_prep_radar.sh, sorc/hrrr_process_mosaic.fd/process_NSSL_mosaic_to_dart_and_netcdf.f90):
  - Input: the 33 MergedReflectivityQC levels, mapped onto the model grid (max over overlap).
  - Precipitation obs: Z ≥ 10 dBZ at every 3rd level up to 11 km.
  - Clear-air obs: Z ≤ 0 dBZ, set to −10 dBZ, only at 4.0 and 8.5 km, every 5th grid point.
  - 0–10 dBZ is unused; the error is 5 dBZ.
  - The same program already writes DART obs_seq (RADAR_REFLECTIVITY, RADAR_CLEARAIR_REFLECTIVITY).
- Data: AWS noaa-mrms-pds/CONUS/MergedReflectivityQC_XX.XX/YYYYMMDD/. Files are every 2 minutes, about 0.85 MB per level-file, so about 28 MB per time for 33 levels. Not downloaded yet.
- Our filter:
  - It is built with obs_def_radar_mod, so RADAR_REFLECTIVITY and RADAR_CLEARAIR_REFLECTIVITY are compiled in.
  - With microphysics_type = 5, the operator interpolates REFL_10CM from the state.
  - Our WRF runs Thompson aerosol-aware with do_radar_ref = 1.
  - Gotcha: the shared obs_kind_mod.f90 was overwritten by the MADIS converter build, so it doesn't show what filter contains.
- State gap:
  - REFL_10CM is in wrfout but not in wrfrst, which scripts/da/wrfrst_dart.py extract reads. It must come from the member's wrfout at the same time, or be added to the restart stream.
  - It is a diagnostic, so NO_COPY_BACK.
  - The hydrometeors (QCLOUD QRAIN QICE QSNOW QGRAUP QNICE QNRAIN) are in wrfrst but not yet in the DART state. Q8 in notes/da_5member_pilot_steps.md says: hydrometeors follow HRRRv4, worked out later.
- Restricting what reflectivity updates: HRRRDAS's separate pass maps to special_localization_obs_types/special_localization_cutoffs plus obs_impact_tool, or to a second filter call.
- Not installed: pyOPAWS (cloned, ../software/pyOPAWS) also has mrms5_2_dart.py (MRMS → DART), as an alternative to HRRR's program.

Mesonet status, done in part 2 (see obs_expansion.md §7 and notes/mesonet_station_selection.md):
- Building the files: scripts/da/make_cycle_mesonet.sh <t> [a|b1|c] [keep|drop] builds a cycle's obs_seq.land_sfc. Option (a) (RRFS v2 selection) is for the first tests; calm winds are kept by default.
- Errors: RAP/RRFS (T 3.0 K, wind 3.0 m/s, RH 0.07, altimeter 1.0 hPa), via patches/dart_7bbd35a09_madis_mesonet_obs_errors.patch.
- Not wired in yet: make_cycle_obs.sh and input.nml.filter (§7.2, "Not wired in yet").
- Open converter limitation: q needs a usable altimeter, so about 700 sites per cycle get no q. Undecided.

Likely first steps for MRMS (none started):
1. Read HRRR's process_NSSL_mosaic_to_dart_and_netcdf.f90 and its namelist in exhrrr_prep_radar.sh.
2. Decide between building it and porting its logic to Python.
3. Download one time of all 33 MRMS levels for a convective time on 05-20, under cases/20250520/obs/mrms/.
4. Produce one obs_seq on our grid (geo_em.d01.nc) and inspect the counts and values.
5. Plan the state changes: REFL_10CM from wrfout (or the restart stream) and the hydrometeors. Check hydrometeor spread in the 5 members.
6. Plan the localization and impact settings.
