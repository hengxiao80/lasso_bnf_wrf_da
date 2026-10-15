# Local patches to pinned software

Tracked here per the plan's requirement to "pin the full commit and local patches"
(step 1A / software_lock.json). Each patch file documents one deviation from the
pinned upstream commit, why it was needed, and how it was applied.

## wrf_06d4240a_tempo_error_stop_ifort_fix.patch

- **Applies to:** WRF commit `06d4240ae989cc3e50af412bb472df3d9048783c` (v4.8.0),
  specifically the `TEMPO` physics submodule (upstream commit `881614f68aa65de8f383d56139162049baf600fa`),
  file `phys/TEMPO/src/module_mp_tempo_driver.F90`.
- **Why:** `ifort` classic 19.1.3 (loaded via the `intel/20.0.4` module on Cirrus)
  rejects `error stop` with a non-constant character expression (here, a runtime
  string built by concatenating a literal with the `filename` variable) —
  `error #6345`. This is arguably correct per the F2008 standard, which requires
  the stop-code to be a *constant* expression; gfortran just tolerates the
  non-constant form as an extension. Because `module_microphysics_driver.f90`
  references every compiled-in microphysics scheme (including TEMPO, which this
  project does not use — we run Thompson, `mp_physics=28`), TEMPO's compile
  failure cascaded into breaking the whole microphysics driver and prevented
  `real.exe`/`wrf.exe` from linking at all.
- **Fix:** split each offending `error stop '<literal>' // filename // '<literal>'`
  into a `write(*,...)` printing the same diagnostic message, followed by a bare
  `error stop 1` (a legal integer constant stop-code). Behavior (prints the
  message, aborts with nonzero exit) is unchanged; only the two lines needed for
  standard-conformance with this compiler were touched. Does not affect the
  Thompson scheme or any physics actually used by this project.
- **Applied:** 17 September 2026, before the first successful `./compile em_real`
  at this commit on Cirrus.

## wrf_06d4240a_refl_10cm_restart.patch

- **Applies to:** WRF commit `06d4240ae989cc3e50af412bb472df3d9048783c` (v4.8.0),
  file `Registry/Registry.EM_COMMON` (line 1611).
- **Why:** MRMS reflectivity assimilation (`notes/obs_expansion.md` Sec. 8) needs `REFL_10CM`
  (Thompson's 10-cm reflectivity, H(x) for `RADAR_REFLECTIVITY`) in the DART state. DART's input is
  extracted from each member's `wrfrst` (`scripts/da/wrfrst_dart.py extract`), but `REFL_10CM`'s I/O
  flags are `hdu` (history, nest down/up), so it is not in restart files, and WRF's runtime I/O
  (`iofields_filename`) can change only the history and input streams (`frame/module_domain.F`,
  `modify_io_masks`), not the restart stream. Decided (user, 2026-10-14): add it to the restart stream
  (option A) rather than read it from the member's `wrfout` (option B).
- **Fix:** I/O flags `hdu` → `hdur` for `refl_10cm`. Nothing else changes: Thompson still computes it only
  on history-alarm steps (`solve_em.F` `diag_flag`), so a `wrfrst` at t holds the same array as the
  `wrfout` at t when history and restart times coincide (15 min in our cycling). On restart the field
  is read back and overwritten at the next history step. About +130 MB per 550 × 390 × 150 restart
  file (13.1 GB now).
- **Applied:** 14 October 2026, with `git apply`, then `./clean` (keeps `configure.wrf`, checked unchanged)
  and `./compile -j 8 em_real` (`compile_em_real_refl_restart.log`, 38 min on the login node, "Executables
  successfully built", no ignored errors). Check: the generated `inc/allocs_6.f90` now gives `refl_10cm`
  `streams(1) = 1` (history) and `streams(2) = 2097152` (restart, as for the restart-only `SNOWNCV`);
  `mskf_refl_10cm` (still `hdu`) has only the history bit. New `wrf.exe` sha256 `886b76cd…`, `real.exe`
  `2c09ef19…` (`software_lock.json`). The executables used by every run before this date
  (`wrf.exe` `0066e888…`, `real.exe` `ab92e99f…`) are kept as `main/*.exe.pre_refl_restart`.
- **Tested** 2026-10-14, job 1051956 (`cases/20250520/da_theta_m0/slurm.refl_restart_test`, `scripts/da/check_refl_restart.py`,
  `tests/refl_restart/`, 8 nodes, 10 min), all checks passed: `REFL_10CM` is in the new `wrfrst` at 00:15 and 00:30 and
  bit-identical to `wrfout` (−35.0 .. 69.8 / 72.2 dBZ); the new 00:15 `wrfrst` equals the pre-patch one (step-7 test,
  old `wrf.exe`) in all 657 common variables, `REFL_10CM` being the only extra; a restart from the pre-patch file (no
  `REFL_10CM`) runs without any warning and gives the same 00:30 `wrfout` (287 variables) and `wrfrst` (658) as a
  restart from the new file. Restart file 13,261,878,800 vs 13,134,596,180 bytes (+127 MB). Test output (`tests/refl_restart/`,
  71 GB) deleted 2026-10-14 at the user's request; the job log `slurm.refl_restart_test.1051956.out` is kept.

## wps_335c76a1_configure.wps.reference

(Earlier versions of this README titled this section `wps_configure_ldflags_qopenmp.patch`, a file that never
existed.)

- **Applies to:** WPS commit `335c76a111f84503e8b963abaf273ea8053645bb` (v4.6.0),
  file `configure.wps` (a generated build-config file, not tracked by WPS's own
  git history — regenerated by `./configure` and hand-edited here, same as WRF's
  `configure.wrf`).
- **Why a full copy, not a patch:** WPS's `.gitignore` lists `configure.wps`, so
  there is no tracked baseline for `git diff` to produce a patch against. The file
  kept here is a byte-for-byte copy of `../software/WPS/configure.wps` as built
  (checked 2026-10-15; its sha256 is in `software_lock.json`).
- **The only intended difference** between this reference and a freshly generated
  `configure.wps` (`./configure`, option "Linux x86_64, Intel Classic compilers",
  dmpar, with the `env_wrf.sh` modules) is line 78, `LDFLAGS = -qopenmp` instead of
  the stock blank `LDFLAGS =`. Checked 2026-10-15 against the stanza in
  `arch/configure.defaults` (lines 324–348): every other difference is a
  substitution `./configure` makes itself (`CONFIGURE_FC` → `$(DM_FC)`, `-D_MPI`,
  `FDEFS`, the jasper/png paths). A diff against a regenerated file that shows
  anything beyond line 78 (other than module paths that have moved) means the
  build environment changed.
- **Why:** our WRF build's `external/io_netcdf` library (`libwrfio_nf.a`) was
  compiled with `-qopenmp` (WRF's Intel arch template applies OpenMP compile
  flags broadly, even for this plain `dmpar`, non-`smpar` build), so its
  `wrf_io.o` member contains 7 undefined references to Intel's OpenMP runtime
  (`__kmpc_*` symbols) — confirmed by extracting the object from the archive
  and inspecting it directly with `nm`. `configure.wps` ships with a blank
  `LDFLAGS`, so linking `geogrid.exe`/`metgrid.exe` against that library failed
  with dozens of `undefined reference to __kmpc_*` errors (silently continued
  past by `make -i`, same as the WRF TEMPO issue — `ungrib.exe` doesn't link
  `io_netcdf` and built fine, which is why only `geogrid`/`metgrid` failed).
  This is a toolchain/link-flag gap in stock `configure.wps` when paired with
  any current build of this WRF source on this Intel classic-`ifort` toolchain
  — not a bug introduced by our source patch or specific to the `06d4240a`
  commit. (Initially suspected this was specific to v4.8.0 vs. `sey`'s
  differently-versioned WRF pairing, since their `geogrid.exe` does not link
  `libiomp5` — but their `wrf_io.o` carries the identical 7 undefined `kmpc`
  references, and their `geogrid.exe` (built 2026-04-20) simply predates their
  own `code/WRF/external/io_netcdf` rebuild (2026-05-27); their WPS was never
  actually relinked against the WRF state currently sitting in that directory,
  so they never hit this either — they didn't avoid it, the combination was
  just never built.)
- **Fix:** set `LDFLAGS = -qopenmp` in `configure.wps` (was blank) so the
  Intel OpenMP runtime is linked in. No source code changed. To reapply after a
  new `./configure`: copy this reference over `configure.wps`, or edit line 78.
- **Why stock `./configure` can't write it:** `arch/Config.pl` has an `-ldflags=`
  option (lines 58–63) that fills a `CONFIGURE_LDFLAGS` placeholder, but
  `./configure` never passes it (line 264), and no stanza in
  `arch/configure.defaults` contains the placeholder (the Intel Classic stanza has a
  literal blank `LDFLAGS =`, line 342). No environment variable feeds it either.
- **Alternatives (not used; kept for reference, 2026-10-15):**
  1. *Scripted edit* (preferred if we move away from the copy): straight after
     `./configure`, run `sed -i 's/^LDFLAGS *=.*/LDFLAGS = -qopenmp/' configure.wps`.
     Reproducible, and the flag still shows in `configure.wps`, so
     `audit_configuration.py` still records it in `software_lock.json`. The copy
     here could then be replaced by a one-line patch or this command.
  2. *Override at compile time, file untouched:* `./configure` stock, then
     `MAKEFLAGS='LDFLAGS=-qopenmp' ./compile >& compile.log`. `./compile` forwards no
     variables to its `make -i -r` calls, but GNU make treats variable definitions in
     `MAKEFLAGS` as command-line overrides, which beat the assignment in
     `configure.wps` and reach sub-makes. Tested only on toy makefiles (GNU Make
     4.2.1), not on a WPS build. Drawback: `configure.wps` keeps a blank `LDFLAGS`,
     so `software_lock.json` would no longer show the flag, and the flag lives only
     in how `./compile` was called. Ungrib and util would also link with
     `-qopenmp` (harmless).
  3. *Patch WPS's build scripts* (`LDFLAGS = CONFIGURE_LDFLAGS` in the stanza and
     `-ldflags` passed by `./configure`): a true patch against tracked files, but more
     invasive than the one-line problem.
  With any of these, `make -i` still hides link errors: check that `geogrid.exe`
  and `metgrid.exe` exist after `./compile`.
- **Applied:** 17 September 2026 (session date; system clock read 18 September
  by the time of this note), after `geogrid.exe`/`metgrid.exe` failed to link
  on the first `./compile` pass. `ungrib.exe` needed no fix.

## dart_7bbd35a09_madis_acars_wvss_humidity.patch

- **Applies to:** DART commit `7bbd35a0995726b0274dc73a1b5783979d0f42d9` (v11.25.3), file
  `observations/obs_converters/MADIS/convert_madis_acars.f90`. Rebuild with
  `observations/obs_converters/MADIS/work/quickbuild.sh convert_madis_acars`.
- **Why:** in current MADIS `point/acars` files (checked 2025-05-20 18Z) the converter's humidity input,
  `downlinkedRH`, is empty for all reports (so is `relHumidity`), so the stock converter writes **no**
  aircraft humidity. The humidity is carried only as the WVSS-II mixing ratio `waterVaporMR` (kg/kg,
  `_FillValue = -1`). Its QC field `waterVaporQC` is also empty, so it can only be used without instrument QC.
  The user decided (2026-09-25) to use it anyway, because aircraft humidity is important for the BNF
  environment (see `notes/wrf_dart_tutorial_adaptation.md` 2.13).
- **Fix:** read `waterVaporMR` when the file has it (`nc_variable_exists`). When the stock RH/dewpoint moisture
  path is not taken, add a branch: q = w/(1+w), RH = q/q_sat(T, p), with the error computed as in the stock RH
  path (`acars_rel_hum_error` × q_sat, i.e. 20% RH). Write `ACARS_SPECIFIC_HUMIDITY` if w > 0,
  0 < RH ≤ 1.1 and q ≤ 0.07. Files with a valid `downlinkedRH` behave as before. All changed lines are marked
  `LOCAL PATCH (bnf_wrf_da)`.
- **Effect (18Z 05-20, lat/lon box around the domain):** 0 → 735 `ACARS_SPECIFIC_HUMIDITY` obs; 2,356 overall.
  Of 1,556 WVSS reports in the box, half are exact duplicates (removed by the converter's existing
  duplicate check), and about 24 fail RH ≤ 1.1.
- **Applied:** 25 September 2026.

## dart_7bbd35a09_types_mod_r8_as_r4.patch

- **Applies to:** DART commit `7bbd35a0995726b0274dc73a1b5783979d0f42d9` (v11.25.3), file
  `assimilation_code/modules/utilities/types_mod.f90`. Affects every DART executable (`filter`,
  `model_mod_check`, converters, ...), so all of them must be (re)built with it in place.
- **Why:** the WRF-DART tutorial (Step 1, "Optional: Modify for 32-bit reals") recommends it because WRF is
  normally run in single precision, and we run WRF with 4-byte reals too. It also roughly halves DART's
  state-vector memory, which matters for 50 members on the 550 × 390 × 150 grid. User's decision.
- **Fix:** comment out `integer, parameter :: r8 = SELECTED_REAL_KIND(12)` and enable the stock alternative
  `integer, parameter :: r8 = r4`. No other change.
- **Applied:** 22 September 2026 (file timestamp), before the DART builds used so far. Documented here
  25 September 2026; it was not recorded at the time.

## dart_7bbd35a09_madis_rawin_use_namelist.patch

- **Applies to:** DART commit `7bbd35a0995726b0274dc73a1b5783979d0f42d9` (v11.25.3), file
  `observations/obs_converters/MADIS/convert_madis_rawin.f90` (one line). Rebuild with
  `observations/obs_converters/MADIS/work/quickbuild.sh convert_madis_rawin`.
- **Why:** the stock source has `use_namelist = .false.`, so the converter ignores
  `&convert_madis_rawin_nml` and prompts on the console ("Include significant level winds,
  temperature?"). Run unattended (scripts, Slurm) with nothing on standard input, it crashes with
  `forrtl: severe (24): end-of-file`. The user chose (2026-09-29) to let it read its namelist instead of
  piping `echo "T T"` into it.
- **Fix:** `use_namelist = .true.`. The converter now reads `&convert_madis_rawin_nml` from `input.nml`
  in its working directory; the block in `MADIS/work/input.nml` equals the compiled-in defaults, and both
  significant-level switches are true (what the pipe supplied). Verified: the 12Z 05-20 radiosonde file
  converted without standard input gives an `obs_seq.rawin` byte-for-byte identical to the piped run.
- **Other MADIS converters are unchanged:** their options (`LH_err`, `include_specific_humidity`,
  `include_relative_humidity`, `include_dewpoint`, `use_input_qc`, ...) stay compile-time `parameter`
  constants in the source (decision 2026-09-29: keep them in the code so that changes are recorded here).
- **Applied:** 29 September 2026.

## dart_7bbd35a09_wrf_bc_hydrometeors_aerosol_shift.patch

- **Applies to:** DART commit `7bbd35a0995726b0274dc73a1b5783979d0f42d9` (v11.25.3), files
  `models/wrf/WRF_BC/update_wrf_bc.f90` and `models/wrf/WRF_BC/pert_wrf_bc.f90`. Rebuild with
  `models/wrf/work/quickbuild.sh update_wrf_bc pert_wrf_bc` (not yet done).
- **Why:** see `notes/lateral_boundary_fields_for_da.md`. Our `real.exe` `wrfbdy` has zero boundary values
  for every hydrometeor mass and number (`real.exe` computes moisture boundaries only for `QVAPOR`), and
  our WRF runs use them (`have_bcs_moist = have_bcs_scalar = .true.`). Stock, both tools refit
  `QCLOUD QRAIN QICE QSNOW QGRAUP QNICE` from full model states that carry HRRR or member hydrometeors,
  while `QNRAIN`/`QNCLOUD` stay zero. That would give the DA runs nonzero hydrometeor boundaries,
  unlike the free runs, with mass and number inconsistent. Separately, `update_wrf_bc` moves the record
  start time to the segment start for all fields, so fields it doesn't refit would be read 15–45 min late
  in 15-min cycling. Of those, only the aerosol numbers `QNWFA QNIFA QNBCA` have nonzero boundary values.
- **Fix:**
  1. Both tools: `nmoist = 1` (was 7), so only `QVAPOR` among the moisture fields is refitted. The six
     hydrometeors keep the file's values (zero).
  2. `update_wrf_bc` only: before the record start time is rewritten, `B` of `QNWFA`, `QNIFA` and `QNBCA` is
     moved to the new start along the original tendency, `B + tend × (new start − old start)`. The tendency
     is kept. This is a no-op when the segment starts at a record start. `pert_wrf_bc` doesn't need it,
     because we use it only at record starts.
- **Not changed:** both tools still read `T` (not `THM`) for `T_BXS`; for the `theta_m0` setup every file
  we write keeps `T = THM` (note Sec. 4).
- **Revisit later:** the zero hydrometeor boundaries come from the `have_bcs_moist`/`have_bcs_scalar`
  choice inherited from sey's setup. If we change those flags (e.g. both `.false.` for flow-dependent
  hydrometeor boundaries), this patch should be reconsidered.
- **Applied:** source edited and both programs rebuilt 30 September 2026 with
  `./quickbuild.sh WRF_BC/update_wrf_bc` and `./quickbuild.sh WRF_BC/pert_wrf_bc` (single-program builds
  need the path as listed in `quickbuild.sh`). Clean compile; log `models/wrf/work/quickbuild_wrf_bc_patch.log`.
  The previous (stock, 18 September) executables are kept in `models/wrf/work/stock_20260918/`.
  Behavior not yet tested: pilot step 8 (boundary test).

## dart_7bbd35a09_mkmf_fp_model_precise.patch

- **Applies to:** DART commit `7bbd35a0995726b0274dc73a1b5783979d0f42d9` (v11.25.3), file
  `build_templates/mkmf.template`. That file is git-ignored by DART; ours is a copy of the stock
  `build_templates/mkmf.template.intel.linux`, and the patch is written against that stock template. Affects
  every DART executable built with `mkmf`/`quickbuild.sh` (`filter`, the WRF_BC tools, the MADIS converters, ...),
  not the NCEP `prep_bufr` programs (`install.sh`, own flags).
- **Why:** the stock flags are `-O` only, so ifort uses its default `-fp-model fast=1`. That lets vectorized
  loops do divisions that are not correctly rounded and replace a division by a constant with multiplication by
  its reciprocal. How a vectorized loop is split depends on array alignment, so results can differ in the last bits
  between runs of the same binary. WRF, `real.exe` and WRFDA all build with `-fp-model precise`. Found while
  explaining the few-ulp differences between the `pert_wrf_bc` zero-perturbation refit and `real.exe`'s
  boundary file: the `module_couple_uv` loop compiled with `-O` reproduces `pert_wrf_bc` bit for bit, and with
  `-O -fp-model precise` reproduces `real.exe` (`notes/da_5member_pilot_steps.md` step 6). The accuracy effect is
  negligible (a few ulps); the reasons are run-to-run reproducibility and consistency with WRF. User's decision.
- **Fix:** `FFLAGS = -O -assume buffered_io $(INCS)` → `FFLAGS = -O -fp-model precise -assume buffered_io $(INCS)`.
- **Applied:** 1 October 2026, before `filter` was first run. Everything rebuilt with `./quickbuild.sh` in
  `models/wrf/work` and `observations/obs_converters/MADIS/work` (logs `quickbuild_fp_precise.log` in each).
  Clean builds (no `error #`); all 28 + 10 executables rebuilt, `filter` still linked with `mpif90`. Check: the
  `pert_wrf_bc` zero-perturbation refit (`build_member_bdy.py --zero-pert`) is now bit-identical to the `real.exe`
  boundary records in all 187 variables (before: up to 3 ulp in U/V values, 7 ulp in tendencies).

## dart_7bbd35a09_madis_metar_obs_errors.patch

**This changes the observation errors of all METAR observations (`METAR_*`), away from DART's defaults.**

- **Applies to:** DART commit `7bbd35a0995726b0274dc73a1b5783979d0f42d9` (v11.25.3), files
  `observations/obs_converters/MADIS/convert_madis_metar.f90` and
  `observations/obs_converters/obs_error/ncep_obs_err_mod.f90`. Rebuild with
  `observations/obs_converters/MADIS/work/quickbuild.sh convert_madis_metar`.
- **Why:** the pilot's innovation statistics (`scripts/da/innovation_stats.py`, 4 analyses
  00:15–01:00 05-20) put the METAR q2, T2 and 10-m wind errors 2–3× below DART's defaults, close to
  NCEP's regional error tables. Decided by the user 2026-10-03, before the pilot extension. Details:
  `notes/obs_expansion.md` Sec. 5.
- **Fix:**
  1. `convert_madis_metar` calls the `metar_*_error` functions instead of `land_*_error`. Stock, METAR
     and mesonet both use `land_*`; mesonet (`convert_madis_mesonet`) still does, so its errors stay
     DART's defaults until they are tuned separately.
  2. New values of the `metar_*` functions (NCEP tables from NOAA-EMC/GSI-fix `0ba656b6`, in
     `../software/GSI-fix_subset/`):

     | Function | Stock | Now | Source |
     |---|---|---|---|
     | `metar_temp_error` | 2.5 K | **1.26 K** | NAM `nam_errtable.r3dv`, type 187 (user's choice over RAP's 2.26 K) |
     | `metar_wind_error` | 3.5 m/s | **1.59 m/s** | RAP `rap_nam_errtable.r3dv`, type 287 |
     | `metar_rel_hum_error` | 0.2 | **0.059** (RH fraction; q error = 0.059 × q_sat) | RAP, type 187 |
     | `metar_pres_error` | 1.0 hPa | 1.0 hPa (unchanged) | = RAP's effective value (0.54 clipped to `ermin` 1.0) |

- **Side effect:** `metar_*` is otherwise used only by `obs_converters/ok_mesonet/convert_ok_mesonet.f90`
  (Oklahoma Mesonet), which we don't build.
- **Applied:** 3 October 2026. Clean rebuild (log `MADIS/work/quickbuild_metar_errors.log`); the previous
  executable is kept as `MADIS/work/convert_madis_metar.pre_metar_errors`. All 48 hourly METAR files of 05-20
  and 05-21 reconverted (`obs_seq_madis/convert_metar_errors_20261003.log`). Check: same observations and
  values, only the error variances differ. The old files (used by the 1-hour pilot) are kept in
  `cases/20250520/obs/obs_seq_madis/metar_v1_dart_land_errors/`. The pilot's per-cycle files
  (`da_theta_m0/obs/202505200015`–`202505200100`) were built from those and are left as they are.

## dart_7bbd35a09_madis_mesonet_obs_errors.patch

**This changes the observation errors of all mesonet observations (`LAND_SFC_*`), away from DART's defaults.**

- **Applies to:** DART commit `7bbd35a0995726b0274dc73a1b5783979d0f42d9` (v11.25.3), file
  `observations/obs_converters/obs_error/ncep_obs_err_mod.f90`, on top of
  `dart_7bbd35a09_madis_metar_obs_errors.patch` (which moved METAR off the `land_*` functions). Rebuild with
  `observations/obs_converters/MADIS/work/quickbuild.sh convert_madis_mesonet`.
- **Why:** mesonet is being added (`notes/obs_expansion.md` Sec. 7.2 item 4). Decided by the user 2026-10-14:
  the RAP/RRFS mesonet errors, the mesonet counterpart of the NCEP values taken for METAR. NCEP's regional
  tables give mesonet (types 188/288) larger errors than METAR (187/287); see the discussion log entry of
  2026-10-14.
- **Fix:** new values of the `land_*` functions (NCEP tables from NOAA-EMC/GSI-fix `0ba656b6`, in
  `../software/GSI-fix_subset/`; RAP `rap_nam_errtable.r3dv` and RRFS `errtable.rrfs` have the same
  188/288 rows, and RAP and RRFS v1 clip them with the same `convinfo` bounds):

  | Function | Stock | Now | Source |
  |---|---|---|---|
  | `land_temp_error` | 2.5 K | **3.0 K** | type 188 table value 4.0 K, clipped to `convinfo` `ermax` 3.0 K (RAP, RRFS v1) |
  | `land_wind_error` | 3.5 m/s | **3.0 m/s** | type 288 |
  | `land_rel_hum_error` | 0.2 | **0.07** (RH fraction; q error = 0.07 × q_sat) | type 188 |
  | `land_pres_error` | 1.0 hPa | 1.0 hPa (unchanged) | type 188 table value 0.54 hPa, raised to `ermin` 1.0 hPa |

- **Side effect:** `land_*` is otherwise used only by `obs_converters/ok_mesonet/convert_ok_mesonet.f90`
  (Oklahoma Mesonet), which we don't build. `convert_madis_metar` uses `metar_*` since the METAR patch.
- **Applied:** 14 October 2026. Rebuild log `MADIS/work/quickbuild_mesonet_errors.log`; the previous
  executable is kept as `MADIS/work/convert_madis_mesonet.pre_mesonet_errors`. Check (cycle 2025-05-20 01:15,
  option a, from `scripts/da/make_cycle_mesonet.sh`): the same selected input converted with the old and
  the new executable gives the same 6,822 observations; error sd T 2.5 → 3.0 K, u and v 3.5 → 3.0 m/s,
  altimeter 1.0 hPa unchanged, q exactly 0.35 × the old value for every observation. No mesonet observations
  had been used in any run before.
