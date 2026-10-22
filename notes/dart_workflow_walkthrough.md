# DART workflow walk-through: the cycle, filter's order of operations, forward operators

Written 2026-10-22 from a question-and-answer walk-through with the user, as a reference to come back to when the
reasoning gets tangled. It explains how things work; the decisions and run results are elsewhere
(`da_5member_pilot_steps.md`, `obs_expansion.md`, `mrms_two_pass_inflation.md`, `dart_namelist_discussion_log.md`).
Code references: DART `7bbd35a09` (`../software/DART`; `filter_mod.f90`, `assim_tools_mod.f90` and
`quality_control_mod.f90` under `assimilation_code/modules/assimilation/`, `models/wrf/model_mod.f90`,
`observations/forward_operators/obs_def_{altimeter,radar}_mod.f90`) and this repo at `5d5ee8f`.

## 1. One cycle at time t (our scripts)

`slurm.cycle` → `driver.sh` (loop over the cycles, resumable, one `settings.txt` per run) → `cycle_job.sh` per cycle:

```
  wrf.exe, 5 members, true restart t-15 → t              (advance_member.sh, previous cycle)
        │  run/memNNN/wrfrst_d01_<t>
        ▼
  extract   wrfrst (_2 time level) → run/memNNN/dart_d01.nc   (copy kept as output/<t>/memNNN/prior_d01.nc)
        ▼
  filter    reads dart_d01.nc, overwrites it with the analysis   (+ MRMS pass if MRMS_FILTER=two_pass)
        ▼
  [qnrain]  QNRAIN from the changed QRAIN (MRMS runs only)
  insert    UPDATE fields → both time levels of wrfrst; PH = prior + hydrostatic increment (HYDROSTATIC_PH=1);
            recompute AL, ALT, P, P_HYD, T = THM
  re-extract → start_d01.nc → update_wrf_bc refits a fresh copy of bdy/wrfbdy_d01_memNNN
        ▼
  wrf.exe   true restart t → t+15, writes wrfout and wrfrst at t+15     → check_cycle.py → status = complete
```

| stage | script | marker in `output<RUN_NAME>/<t>/` |
|---|---|---|
| extraction, filter directory, inflation files | `prep_filter.sh` | |
| filter (40 × 32 ranks, hcoll off, exit guard) | `run_filter` in `cycle_lib.sh` | |
| filter outputs moved to `output<RUN_NAME>/<t>/filter*/` | `post_filter.sh save` | `filter.done` (after all passes) |
| insert, re-extract, boundary refit | `post_filter.sh member` | `memNNN/update.done` |
| 15-min segment | `advance_member.sh` → `run_wrf_segment.sh` | `memNNN/advance.done` |
| checks | `check_cycle.py` | `status` |

Observations are built beforehand, outside the cycling job: MADIS is converted one hour at a time
(`convert_madis_hour.sh`); `make_cycle_obs.sh` cuts the window (t − 450 s, t + 450 s], runs
`wrf_dart_obs_preprocess` (domain and boundary trim, elevation check, larger errors near the boundary) and adds the
mesonet and MRMS (`mrms_to_obs_seq.py`, Sec. 6). Every report in the window is assimilated as if valid at t (3-D, not
4-D).

## 2. Inside filter: order of operations and the stage files

`filter_main` (`filter_mod.f90`) with our `&filter_nml`: one observation window per run, `compute_posterior = .true.`,
adaptive prior inflation (flavor 2), no posterior inflation.

| # | step | line | on disk (`output<RUN_NAME>/<t>/filter*/`) |
|---|---|---|---|
| 1 | read the members and λ (the inflation factor) | 577 | `input_mean/sd`; `input_priorinf_mean/sd` = the previous cycle's `postassim_priorinf_*` (undamped), or `fill_inflation_restart`'s (1.0, sd 0.6) at the first analysis |
| 2 | damp λ ← 1 + `inf_damping`·(λ − 1), then apply the prior inflation to **every** state variable, NO_COPY_BACK ones included (the mean is unchanged) | 822–833 | |
| 3 | forward operators H(x) for every observation and member, on the inflated ensemble | 853 | |
| | preassim stage written | 864 | `preassim_mean/sd/member_*` (inflated prior), `preassim_priorinf_*` (the damped λ actually applied) |
| 4 | observation-space diagnostics and the outlier check | 890 | prior part and DART QC of `obs_seq.final` |
| 5 | the sequential observation loop (Sec. 3) | 905 | |
| 6 | postassim stage written | 936 | `postassim_*`; `postassim_priorinf_*` = the adapted λ, the next cycle's input |
| 7 | posterior inflation: none (`inf_flavor(2) = 0`) | 960 | |
| 8 | forward operators again, on the analysis | 987 | posterior part of `obs_seq.final` |
| 9 | output stage: written back in place into `dart_d01.nc`, **UPDATE variables only** | 1102 | `output_mean/sd`; `output_priorinf_*` holds only the UPDATE variables (why the cycle carries `postassim_priorinf_*`); `dart_d01.nc` is saved as `memNNN/analysis_d01.nc` |

Outlier check (`check_outlier_threshold`, `quality_control_mod.f90:241`): |mean H(x) − y| / √(var H(x) + R) >
`outlier_threshold` (3) → DART QC 7. var H(x) is taken after inflation, so more inflation also loosens the check.

## 3. The sequential observation loop (`assim_tools_mod.f90:585–836`)

For each observation in turn:

1. The rank that owns the observation broadcasts its prior ensemble H(x) (as updated by the observations before it)
   and its QC (`:658–666`). Every rank then computes the same EAKF observation-space increment itself
   (`obs_increment`, `:686`). Only the observations are owned by single ranks; the state is spread over all ranks
   (`distributed_state`) and each rank updates its own state elements, which is why 40 × 32 ranks took the
   observation loop from 97 s to 10 s.
2. Each state element within 2 × `cutoff` (300 km horizontally; vertically in scale height) gets
   increment = `final_factor` × regression × observation-space increment (`obs_updates_ens`, `:2005`).
   `final_factor` = Gaspari–Cohn weight × impact-table factor (`cov_and_impact_factors`); the regression is reduced
   by the sampling-error correction (`update_from_obs_inc`, `:1534`), which matters a lot with 5 members.
3. At the same point that element's λ is updated, from the observation's original prior mean and variance
   (`orig_obs_prior_*`), the observation and its correlation with the element
   (`update_varying_state_space_inflation`).
4. The H(x) of the observations **not yet used** is updated by the same regression (`OBS_UPDATE`, `:808–835`).
   The order of the observations therefore matters a little, and the "prior" stored in `obs_seq.final` is the
   original one, from before any of these updates.

## 4. Things to keep in mind

- **NO_COPY_BACK is not "not analysed".** Those fields are inflated, updated in memory, used by the forward operators,
  and they drive λ adaptation; they are only not written back. Only the impact table stops an observation from
  touching a field (found in run 4; `mrms_two_pass_inflation.md`).
- **W is analysed but discarded.** WRF restarts with the prior W while U, V, THM, MU and PH have changed. That is
  standard practice, but it is one source of the post-analysis adjustment.
- **T in `dart_d01.nc` is stale.** It is the prior THM, because only THM is in the state. That is why
  `post_filter.sh` re-extracts `start_d01.nc` after the insert, before `update_wrf_bc`.
- **Two passes are two complete runs of steps 1–9.** The MRMS pass starts from the conventional pass's
  `dart_d01.nc` (only its UPDATE fields changed). Under `MRMS_INFLATION=both` it applies λ again in its step 2 (and
  damps it again with `MRMS_PASS2_DAMPING=1`), the leading explanation for the larger shock in runs 4 and 4b
  (`mrms_two_pass_inflation.md`).

## 5. Forward operators: surface observations and radar "read the field directly"

For these observation types DART does no physics to get the model equivalent. It bilinearly interpolates a field WRF
has already diagnosed and that is in the state vector (T2, Q2, U10, V10, PSFC; REFL_10CM in 3-D for radar). It never
builds a 2-m temperature from THM and the lowest model levels, or a reflectivity from QRAIN, QSNOW and QGRAUP. The
altimeter is a partial exception: it applies a formula to PSFC.

Surface observations carry the vertical coordinate VERTISSURFACE: the `-1` after the station elevation in
`obs_seq.out` (e.g. `616.0000000000000     -1` in `obs_madis_mrms/202505200030/obs_seq.out`). `model_mod` then
takes its surface branch (`model_mod.f90:1242`, `surf_var`):

| observation | H(x) | where |
|---|---|---|
| METAR / LAND_SFC temperature | bilinear interpolation of **T2** from the 4 surrounding mass points | `model_mod.f90:1770` |
| METAR / LAND_SFC humidity | bilinear interpolation of **Q2** (a mixing ratio r), then q = r/(1+r) | `model_mod.f90:2010–2037` |
| METAR / LAND_SFC wind | **U10** and **V10** both interpolated, then turned from grid-relative to earth-relative (`gridwind_to_truewind`) | `model_mod.f90:1589–1626` |
| METAR altimeter | **PSFC** interpolated, plus the model terrain (HGT, from filter's `wrfinput_d01`); altimeter = ((p − 0.3)^0.190284 + 8.4228807e-5·h)^(1/0.190284), p in hPa, h in m | `obs_def_altimeter_mod.f90:104–115, 128` |
| MRMS reflectivity (VERTISHEIGHT) | **REFL_10CM** interpolated in 3-D (horizontally, then in height), floored at −10 dBZ | `obs_def_radar_mod.f90:1125–1131` (`microphysics_type = 5`); Sec. 6 |

For comparison, ACARS and radiosonde temperatures go through the 3-D path: vertical interpolation in the column, and
sensible temperature computed from THM and pressure.

**Station elevation is not used** by any of the surface operators: T2 is not lapse-rate corrected to the station
height, and the altimeter uses the model's terrain. The only safeguard is the screening in `wrf_dart_obs_preprocess`
(`sfc_elevation_check = .true.`, `sfc_elevation_tol = 300` m, `config/input.nml.obs_preprocess:18–19`); the
`model_mod` check is off (`sfc_elev_max_diff = -1`).

Consequences:

1. **Surface observations reach the 3-D fields only through ensemble correlations.** The THM increment at level k is
   regression × innovation, with regression = cov(THM_k, T2) / var(T2). The vertical depth of a METAR temperature
   increment therefore depends entirely on how well T2 and THM_k correlate across the 5 members; for example it would
   shrink in a stable nocturnal layer where T2 is decoupled from the air above. The sampling-error correction keeps
   that from being pure noise. The inflated T2 spread is var H(x), so it (and T2's λ) also sets the gain.
2. **The posterior fits in `obs_seq.final` look better than the state WRF actually starts from.** Filter updates T2,
   Q2, U10, V10, PSFC and REFL_10CM in memory, and step 8 evaluates H(x) on those updated fields. They are all
   NO_COPY_BACK, and `post_filter.sh` never inserts REFL_10CM into the restart. WRF recomputes the 2-D fields from
   the analysed 3-D state on its first step, and REFL_10CM only at the next history step (the `diag_flag` step,
   `obs_expansion.md` Sec. 8), 15 minutes later. So the surface posterior statistics measure the regression-updated
   diagnostics, and the radar posterior (e.g. 6.53 dBZ RMS at 01:00 in run 4b) the regression-updated REFL_10CM, not
   reflectivity computed from the analysed QRAIN, QSNOW and QGRAUP. The honest measure is the next cycle's prior.
   Not quantified yet (Sec. 7).
3. **Radar is the extreme case of item 1.** DART never evaluates the nonlinear Z(q) relation. The hydrometeor updates
   come only from the 5-member covariance between REFL_10CM (in dBZ) and q (in kg/kg). Where every member is clear air
   (−35 dBZ, floored to −10), H(x) has no spread, so a precipitation observation there changes nothing
   (`obs_expansion.md` Sec. 8.3).

## 6. MRMS: from the MRMS grid to H(x)

MRMS is the observation and REFL_10CM the model equivalent, but the horizontal interpolation goes the other way: the
converter maps MRMS onto WRF's mass-point columns, and DART then interpolates REFL_10CM only vertically, to the MRMS
heights.

```
  MRMS MergedReflectivityQC, 0.01° lat-lon (~1 km), 33 levels 0.5-19 km MSL
        │  mrms_to_obs_seq.py: bilinear in dBZ, horizontal only
        ▼
  reflectivity on WRF mass-point columns (549 × 389) at the MRMS heights → thinning → obs_seq.mrms
        ▲
        │  DART, per member: that column (horizontal weights ≈ 1, 0, 0, 0), then linear in height
  WRF REFL_10CM
```

1. **Converter** (`scripts/da/mrms_to_obs_seq.py`), a port of HRRR's `process_NSSL_mosaic_to_dart_and_netcdf.f90`
   with HRRRDAS's settings (`obs_expansion.md` Sec. 8.1–8.2):
   - MRMS time: the analysis minute, else 1 or 2 minutes earlier, with all 33 levels present (`find_mrms_files`).
   - Each level is bilinearly interpolated, in dBZ, to every WRF mass point (`geo_em` `XLAT_M`/`XLONG_M`)
     (`to_model_grid`, `:101`). If any of the 4 MRMS neighbours is "covered, no echo" (−99), the point is clear air;
     if any is "no coverage" (−999), it is missing.
   - No vertical regridding: the heights stay MRMS's (`LEVELS_M`).
   - Precipitation obs: ≥ 10 dBZ, on every third MRMS level up to 11 km (0.5, 1.25, 2.0, 2.75, 4.0, 5.5, 7.0, 8.5,
     11.0 km), thinned to every other WRF column (5 km apart). Clear-air obs: ≤ 0 dBZ, written as −10 dBZ, only at
     4.0 and 8.5 km, every sixth column (15 km apart). Error sd 5 dBZ.
   - Added for our cycle: the boundary zone is dropped (5 points) and errors are inflated within 15 points of the
     edge (up to × 2.5), as `wrf_dart_obs_preprocess` does for the conventional obs.
   - Example: 00:30 gives 79,111 precipitation and 8,496 clear-air obs (`obs_madis_mrms/202505200030/mrms.log`).
   - Each ob's location is the exact lat/lon of a WRF mass point plus an MRMS height in m MSL, flagged VERTISHEIGHT
     (the `3` in `obs_seq.mrms`).
2. **DART's forward operator** (`obs_def_radar_mod.f90:1125` → `model_mod`):
   - Horizontal: the ob sits on a mass point, so the bilinear weights are essentially (1, 0, 0, 0): it takes that
     column.
   - Vertical: for each member, the column's level heights from (PH + PHB)/g; `height_to_zk`
     (`model_mod.f90:4601`) finds the two levels around the MRMS height, and REFL_10CM is interpolated linearly in
     dBZ between them. Each member uses its own level heights. An ob below a member's lowest mass level fails for
     that member (`allow_obs_below_vol = .false.`, `model_mod.f90:1235`).
   - H(x) is then floored at −10 dBZ (`apply_ref_limit_to_fwd_op`, `obs_def_radar_mod.f90:1131`).
3. **Consequences:**
   - Representativeness: each ob is a bilinear sample of the ~1-km MRMS pixels around a WRF mass point, not an
     average over the 2.5-km cell, so it carries finer detail than the model's REFL_10CM can resolve. In this setup
     the 5-dBZ error has to absorb that difference.
   - Both interpolations are in dBZ, i.e. in log space, not in linear Z. That is HRRR's practice too; near echo
     edges it gives lower values than averaging Z would.

## 7. Open

- Quantify Sec. 5 item 2: compare the posterior T2, wind and reflectivity fits in `obs_seq.final` with what WRF
  itself diagnoses from the analysis (T2, Q2, U10, V10 after its first step; REFL_10CM needs a history step, e.g. a
  test restart with output after one step).
