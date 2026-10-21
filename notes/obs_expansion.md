# Adding observations beyond the pilot's MADIS set

Started 2026-10-03 (session "Adding more obs part 1"). The 5-member pilot assimilates public MADIS METAR, ACARS (WVSS humidity patch) and radiosondes (`da_5member_pilot_steps.md` steps 9–13). This note maps what HRRRDAS assimilated, checked in the HRRR source, against what we can get for 2025-05-20, and records the plan for adding families one at a time.

Sources: `../software/HRRR` (NOAA-EMC/HRRR `40ee6058`, hrrr.v4.1.20; spot checks at `44728d00`, 2022-05-24), our DART build (`../software/DART`, v11.25.3), and `wrf_dart_tutorial_adaptation.md` 2.13 for the data searches.

## 1. What HRRRDAS assimilated (verified in code)

**Observer (GSI, per member and mean).** `scripts/hrrrdas/exhrrr_analysis.sh` loads `parm/hrrrdas/hrrrdas_gsiparm.anl` (members) or `.anl.mean` (mean). It does **not** source `parm/hrrrdas/hrrr_gsiparm.anl.sh`; only `scripts/conus/exhrrr_analysis.sh` sources a `hrrr_gsiparm.anl.sh` (its own, under `parm/conus/`). Files linked in: `prepbufr` (RAP `prepbufr.tm00`, `rap_e` at 00/12Z), `satwndbufr` (raw satellite-wind dump), `dbzobs.nc` (MRMS on the model grid), plus `l2rwbufr`, `refInGSI`, `larcInGSI`. The OBS_INPUT table that matters:

| dfile | dtype | used? |
|---|---|---|
| `dbzobs.nc` | `dbz` | yes (own EnKF pass, below) |
| `prepbufr` | `ps t q pw uv spd dw sst` | yes; which report types pass is set by the convinfo (not public) |
| `satwndbufr` | `uv` | yes (`use_prepb_satwnd = .false.`) |
| `l2rwbufr` | `rw` | **no: not in `hrrrdas_gsiparm.anl` or `.mean`** (same at `44728d00`). The file is linked but never read |
| radiances, `gpsrobufr`, ... | | listed, but no file is linked |

**Correction to `codex.HRRRv4_observations_and_WRF_DART_reference.md` and `codex.HRRRv4_radar_data_assimilation_summary.md`:** they say Level-II radial velocity entered HRRRDAS. In the repo, at both commits, only the deterministic HRRR GSI (`parm/conus/hrrr_gsiparm.anl.sh`) lists `l2rwbufr rw`. HRRRDAS's EnKF does read `rw` diag records if present (`readconvobs.f90`), but its observer never produces them.

**Mesonet.** HRRRDAS copies the provider list P4 (`hrrr_gsd_sfcobs_provider.txt`) but its copy of the station list S5 (`hrrr_current_mesonet_uselist.txt`) is commented out (`exhrrr_analysis.sh:249`); deterministic HRRR copies both (`scripts/conus/exhrrr_analysis.sh:235–236`). IDs, contents and which copies are public (P4 is, in the HRRRv3 and RRFS v1 git history; S5 is not): `mesonet_station_selection.md` (added 2026-10-13; this paragraph's "contents not public" was written before).

**EnKF (`scripts/hrrrdas/exhrrr_enkf.sh`, `parm/hrrrdas/hrrrdas_enkf_wrf_namelist.sh`).** Two serial passes, conventional first:

| | conventional | reflectivity |
|---|---|---|
| input | `diag_conv_ges.*` | `diag_radardbz_ges.*` |
| `anavinfo` | `hrrrdas_anavinfo_arw_netcdf_HRRRENS` | `..._HRRRENS_radar` (contents not public; Dowell 2020: adds QRAIN, QSNOW, QGRAUPEL) |
| `corrlength` | 300 km | 18 km |
| `lnsigcutoff` | 0.5 (all, incl. ps) | 0.5 |
| RTPS (`analpertwt`) | 1.20 (15-km d01), 1.08 (3-km d02) | same |
| prior inflation | off (`covinflate* = 0`) | off |

`corrlength` and `lnsigcutoff` are where the Gaspari–Cohn taper reaches zero (`covlocal.f90:52`: "taper = 0 at r = 1"; `enkf.f90:562`: r = dist/corrlength, `params.f90:634` converts km to radians). So **Q12's reading is confirmed**: DART `cutoff` (half-width) = 0.0235 rad ≈ 150 km for conventional obs, and 18 km zero-influence → `cutoff` ≈ 0.00141 for reflectivity.

**Reflectivity operator.** `if_model_dbz = .true.`: H(x) is WRF's own `REFL_10CM` (read from the member file, `cplr_get_wrf_mass_ensperts.f90:1496–1499`), i.e. Thompson's diagnostic reflectivity.

**MRMS preprocessing (`scripts/hrrrdas/exhrrr_prep_radar.sh`, `sorc/hrrr_process_mosaic.fd/process_NSSL_mosaic_to_dart_and_netcdf.f90`).** Input: the 33 `MergedReflectivityQC` levels (0.5–19 km). Mapped onto the model mass grid (`geo_em.d01.nc` `XLAT_M`/`XLONG_M`) by **bilinear interpolation of the 4 surrounding MRMS points** (0.01°), not by a max or average over the model box; the "max" in the code is only the `MPI_REDUCE` that merges the levels (or tiles) handled by different ranks (corrected 2026-10-14, §8). If any of the 4 points is MRMS −99 ("Missing" in NSSL's table; in practice covered but no echo detected) the model point is "clear", even next to strong echo. Then, per the namelist HRRRDAS uses:
- precipitation obs: Z ≥ 10 dBZ, every 3rd MRMS level (`precip_dbz_vert_skip = 2`: 0.5, 1.25, 2.0, 2.75, 4.0, 5.5, 7.0, 8.5, 11.0 km), horizontal skip 1 grid point (greedy: a kept point removes the others within ±1, so **every 2nd point**);
- clear-air obs: Z ≤ 0 dBZ, set to −10 dBZ, only at levels 13 and 22 (**4.0 and 8.5 km**; `clear_air_dbz_vert_skip = -1` is a hard-coded special case), horizontal skip 5 grid points (**every 6th point**);
- 0 < Z < 10 dBZ: not used; nothing above 11 km (`max_height = 11001`); no obs in the outermost grid row;
- error sd 5 dBZ for both.

The same program **writes a DART `obs_seq` file** (`output_dart = .true.`; `RADAR_REFLECTIVITY` and `RADAR_CLEARAIR_REFLECTIVITY`, ASCII, kinds 12/13 from its own `DART.f90`), a remnant of HRRRDAS's DART heritage. GSI reads the netCDF version (`Gridded_ref.nc` → `dbzobs.nc`).

## 2. What our `filter` can already take

- **Build.** `filter` (2026-10-01 22:20, `quickbuild_fp_precise.log`) was preprocessed with `obs_def_reanalysis_bufr, radar, metar, dew_point, rel_humidity, altimeter, gps, vortex, gts`. So `LAND_SFC_*` (mesonet), `SAT_U/V_WIND_COMPONENT`, `VADWND_*`, `PROFILER_*`, `GPS_PRECIPITABLE_WATER`, `RADAR_REFLECTIVITY`, `RADAR_CLEARAIR_REFLECTIVITY` and `DOPPLER_RADIAL_VELOCITY` are all compiled in.
- **Gotcha.** The generated `obs_kind_mod.f90`/`obs_def_mod.f90` are shared files; the MADIS converter build at 22:22 overwrote them with its own (no radar) list. They don't show what `filter` contains; `quickbuild.sh` reruns `preprocess` for its own list, so rebuilds are fine. (`strings`/`grep -a` on the binary doesn't find type names either, even `ACARS_SPECIFIC_HUMIDITY`.)
- **Mesonet converter** (`convert_madis_mesonet`, built) writes `LAND_SFC_{U,V}_WIND_COMPONENT`, `LAND_SFC_TEMPERATURE`, `LAND_SFC_SPECIFIC_HUMIDITY`, `LAND_SFC_ALTIMETER`. No other family in our pipeline uses `LAND_SFC_*`, so mesonet gets its own errors, localization and diagnostics.
- **Reflectivity.** `obs_def_radar_mod` with `microphysics_type = 5` interpolates `REFL_10CM` from the state (our `input.nml.filter` still has the default **2**; checked 2026-10-14, §8.3) (`QTY_RADAR_REFLECTIVITY`), the same H(x) as HRRRDAS. Our WRF runs Thompson aerosol-aware with `do_radar_ref = 1`. `REFL_10CM` is in our 15-min `wrfout` but **not in `wrfrst`**, which `wrfrst_dart.py extract` reads; it would come from the member's `wrfout` at the same time (or be added to the restart stream). It is a diagnostic: `NO_COPY_BACK`, WRF recomputes it. The hydrometeors (QCLOUD QRAIN QICE QSNOW QGRAUP QNICE QNRAIN) are in `wrfrst`.
- **Restricting what reflectivity updates.** HRRRDAS's separate pass with its own `anavinfo` maps to DART's per-type `special_localization_obs_types`/`special_localization_cutoffs` (18 km) plus `obs_impact_tool` (which quantities each obs type may update), or to a second `filter` call.
- **Not installed:** pyOPAWS and Py-ART (needed only for Level-II radar).

## 3. Target vs obtainable, for 2025-05-20

| Family | HRRRDAS | Source for us | Converter / DART | Status, work left |
|---|---|---|---|---|
| METAR, ACARS, radiosondes | prepbufr | public MADIS | stock (+2 patches) | **in the pilot** |
| Marine | prepbufr | public MADIS | stock | in the pipeline; none usable in the domain |
| **Mesonet** | prepbufr, provider list | public MADIS, on disk (05-19..05-21, ~19,000 reports/h in domain at 18Z) | `convert_madis_mesonet` built; `LAND_SFC_*` in `filter` | provider/station selection, thinning (DART has none for surface), errors, terrain screening |
| **MRMS 3-D reflectivity** | own EnKF pass, 18 km | AWS `noaa-mrms-pds/CONUS/MergedReflectivityQC_XX.XX/YYYYMMDD/`: 2-min files, 719 per level on 05-20, ~0.85 MB per level-file (≈28 MB per time for 33 levels) | HRRR's `process_NSSL_mosaic_to_dart_and_netcdf.f90` already writes DART obs on a WRF grid; `RADAR_*` in `filter` | build that program (or port its logic), `REFL_10CM` + hydrometeors into the DART state, localization/impact settings, check hydrometeor spread |
| Satellite winds | raw `satwndbufr` | GOES-19 ABI-L2-DMWC on AWS (2.13) | `SAT_U/V` in `filter`; **reader missing** | new GOES-R netCDF reader with HRRR's QC (2.13) |
| VAD winds | prepbufr (type 224) | GDAS `prep48h` (6-hourly files), on disk | `VADWND_*` in `filter`; `prepbufr.x` drops them | two small patches (2.13) |
| GPS PW | prepbufr `pw` | GDAS `prep48h`, synoptic times only, PWQ = 9 | `GPS_PRECIPITABLE_WATER` in `filter` | parked (2.13: low value) |
| Profilers | prepbufr | MADIS | stock | 0 in the domain |
| Level-II radial velocity | **not in HRRRDAS** (deterministic HRRR only) | AWS NEXRAD Level II | radar operator in `filter`; pyOPAWS not installed | outside "follow HRRRDAS"; optional later |
| Cloud clearing, lightning, PBL pseudo-obs | not EnKF obs | — | — | out of scope |

## 4. Radar radial velocity: preparation (user, 2026-10-03)

Not part of HRRRDAS (§1), but we prepare to assimilate it: deterministic HRRR uses it, and it is a natural convective-scale observation for the EnKF.

**HRRRDAS output on NOMADS (checked 2026-10-03).** `hrrr/prod/nwges/hrrrdasges/` holds the 36 member 1-h backgrounds (`hrrrdas_small_d02_<YYYYMMDDHH>f01_memNNNN`, 6.3 GB each) for the last two cycles only. `hrrr.YYYYMMDD/conus/` has only deterministic GRIB2/BUFR soundings. No GSI `diag_*` files or EnKF logs are published, so the radial-velocity question can't be settled from output. AWS `noaa-hrrr-bdp-pds` has no HRRRDAS output. (NOMADS `/pub` listings time out from Cirrus; read through a web fetch.)

**Data.** AWS `unidata-nexrad-level2/YYYY/MM/DD/<SITE>/` (`noaa-nexrad-level2` returns nothing for 2025). KHTX on 05-20: 326 volumes (~5-min VCPs), 7.9 MB each, 2.6 GB/day. One volume per radar per 15-min cycle for all 29 radars ≈ 22 GB/day.

**Radars inside the domain** (NCEI `nexrad-stations.txt`, nearest grid point; edge distance in grid points): 29 WSR-88Ds: KBMX KDGX KEAX KEOX KFFC KGSP KGWX KHPX KHTX KINX KJGX KJKL KLSX KLVX KLZK KMOB KMRX KMXX KNQA KOHX KPAH KPOE KRLX KSGF KSHV KSRX KTWX KVAX KVWX. KHTX (Huntsville) is nearest BNF. KMOB, KRLX, KTWX, KGSP sit within 10 points of the edge (their nearby coverage is in the boundary zone; their far coverage still reaches inside). Also 7 TDWRs (TATL TBNA TCVG TMEM TSDF TSTL TTUL): C-band, short Nyquist; leave out.

**Processing: pyOPAWS** (cloned to `../software/pyOPAWS`, `6c14895`, 2025-03-05; DART's recommended route).
- `opaws2d.py`: Level-II → QC (`-q None|Minimal|MetSignal`) → dealiasing through Py-ART (`-u region|phase`) → Cressman superobs on each sweep onto a Cartesian grid → DART ASCII `obs_seq` (`DOPPLER_RADIAL_VELOCITY` with radar location, beam direction and Nyquist velocity; `RADAR_REFLECTIVITY`, `RADAR_CLEARAIR_REFLECTIVITY`) and netCDF.
- `opaws_config.yml` defaults: 5-km grid, 150-km radius and max range, 10-km min range, ROI 7.07 km, min 6 gates, max height 10 km, velocity masked where there is no reflectivity, errors 3 m/s (velocity) and 5 dBZ.
- Also has `mrms5_2_dart.py` (MRMS → DART), relevant to the reflectivity step.
- Needs Python 3.10, `arm_pyart`, `wradlib`, a Fortran compiler for the Cressman module (f2py). Cirrus: system `gfortran` 8.5, module `gcc/10.3.0`. **Not installed yet**: a separate `uv` environment would keep Py-ART out of the project one.

**DART forward operator** (`obs_def_radar_mod`): Vr = u, v, w projected on the beam, plus the fall speed × sin(elevation). Needs `QTY_VERTICAL_VELOCITY` (W is in our state, `NO_COPY_BACK`; keep it there if Vr is added) and `QTY_POWER_WEIGHTED_FALL_SPEED`. Our WRF has no fall-speed field: WRF `model_mod` looks for `FALL_SPD_Z_WEIGHTED` (`model_mod.f90:760`), which isn't in our Registry or Thompson. Options:
- **A.** `microphysics_type = 5` + `allow_dbztowt_conv = .true.`: fall speed from `REFL_10CM` by an empirical relation. No WRF change; needs `REFL_10CM` in the state, which the MRMS step needs anyway. Weak for low-density ice at high elevation.
- **B.** Patch WRF/Thompson to write a reflectivity-weighted fall speed (what DART's README asks WRF users to do).
- **C.** `microphysics_type = -1` (fall speed 0): testing only.

At low tilts the fall-speed term is small (sin 5° ≈ 0.09: 10 m/s rain → 0.9 m/s, below the 3 m/s error). HRRR's GSI kept only elevations ≤ 5°. So A with an elevation limit is a reasonable start.

**Other choices to make.**
- Localization: radar-specific, DART suggests 12–24 km (`special_localization_obs_types`).
- Duplication: don't use VAD winds and Vr from the same radars at full weight.
- Volume per cycle: the volume nearest the analysis time, or all volumes in the 15-min window.
- Which tilts: all, or ≤ 5° like HRRR.

**Next steps (none needs a job):** set up the pyOPAWS environment; download one hour of a few radars (KHTX, KOHX, KBMX, KGWX) at a convective time on 05-20; run `opaws2d.py` on one volume; inspect the `obs_seq` (counts, metadata, unfolding) and check that `obs_sequence_tool` reads it.

## 5. Observation errors: DART's MADIS errors vs NCEP regional tables (2026-10-03)

**Ours.** The MADIS converters link `obs_converters/obs_error/ncep_obs_err_mod.f90` (`MADIS/work/obs_errors.path_names`): fixed functions of platform and pressure, not tied to BUFR. Every humidity type uses RH error 0.2, written as a q error of 0.2 × q_sat(T, p). METAR and mesonet both use the `land_*` functions.

**NCEP tables** (NOAA-EMC/GSI-fix `0ba656b6`, downloaded to `../software/GSI-fix_subset/`: `rap_nam_errtable.r3dv`, `nam_errtable.r3dv`, `errtable.rrfs`, `rap_nam_regional_convinfo`, `nam_regional_convinfo.txt`, `convinfo.rrfs`). HRRR's own `hrrr_nam_errtable.r3dv` and HRRRDAS's convinfo aren't public; RAP's are the closest relatives (same `*_nam_errtable` lineage, and HRRR inherits RAP's observation set).

**RAP (13 km) vs RRFS (3 km), full diff.** The error tables are identical for all 200 report types except satellite wind 245 above 500 hPa (RAP 4.1–7 m/s, RRFS 4.0). So NCEP did not retune conventional errors for 3 km. The convinfo files differ in what is used and how:
- mesonet 188/288: RAP `iuse = -1`, RRFS `iuse = 1` with a ±0.1 h (6-min) time window (METAR: ±0.25 h);
- radial velocity `rw 999`: RRFS `iuse = 1` (gross 5, error bounds [2, 10] m/s); RAP −1;
- RRFS adds reflectivity `dbz 888` and lightning flash-extent density `fed 555`, GNSS RO, and satellite winds by satellite subtype (GOES 16/17/18 IDs 270–272 used).

This is GSI-fix HEAD; RRFS's operational fix files (rrfs-workflow) not checked.
- errtable columns: T (K), q (in units of 10 % RH; `read_prepbufr.f90:2261`), wind (m/s), ps (hPa).
- GSI then clips each error to convinfo's `[ermin, ermax]` (`setupt.f90:445`, `setupq.f90:481`, `setupw.f90:489`, `setupps.f90:389`). RAP: T [1.3, 5.6] K upper air and [1.0, 3.0] K surface; q [5, 50] % RH; wind [1.4, 6.1] m/s upper air and [1.0, 5.0] m/s surface; ps [1, 3] hPa. The "RAP effective" columns below include this clipping.

| Type (NCEP report type) | Level (hPa) | Ours (DART MADIS) | RAP table | RAP effective |
|---|---|---|---|---|
| Radiosonde T (120) | 1000 / 850 / 500 / 250 | 1.2 / 0.8 / 0.8 / 1.2 K | 1.40 / 1.39 / 0.93 / 1.19 | 1.40 / 1.39 / 1.3 / 1.3 K |
| Radiosonde q (120) | 1000 / 850 / 500 / 250 | 20 % RH | 7.3 / 11.2 / 16.0 / 18.8 % | same |
| Radiosonde wind (220) | 1000 / 850 / 500 / 250 | 1.4 / 1.5 / 2.1 / 3.2 m/s | 2.29 / 2.57 / 2.50 / 2.69 | same |
| Radiosonde surface pressure (120) | | 2.0 hPa | 0.68 | 1.0 hPa |
| ACARS T (133) | 1000 / 850 / ≤700 | 1.47 / 1.11 / 1.0 K | 1.24 / 0.98 / 0.74–0.93 | 1.3 K everywhere |
| ACARS q (133) | all | 20 % RH | 16.6–19.7 % | same |
| ACARS wind (233) | all | 2.5 m/s | 2.32 (NAM 2.4–3.5) | 2.32 m/s |
| METAR T (187) | sfc | 2.5 K | 2.26 (NAM 1.26) | 2.26 K |
| METAR q (187) | sfc | 20 % RH | 5.9 % (NAM 2.7) | 5.9 % RH |
| METAR wind (287) | sfc | 3.5 m/s | 1.59 (NAM 1.92) | 1.59 m/s |
| METAR altimeter / ps (187) | sfc | 1.0 hPa | 0.54 | 1.0 hPa |
| Mesonet T / q / wind / ps (188, 288) | sfc | 2.5 K / 20 % / 3.5 m/s / 1.0 hPa | 4.0 / 7 % / 3.0 / 0.54 | 3.0 K / 7 % / 3.0 m/s / 1.0 hPa; **RAP `iuse = -1` (monitored only)**, NAM and RRFS `iuse = 1` |
| VAD wind (224), for later | 850 / 500 / 250 | — | 2.24 / 3.03 / 5.70 | same |

**Reading.**
- **Humidity at the surface is the biggest difference:** our METAR q error (20 % RH) is ~3.4× RAP's (5.9 %), i.e. ~11× smaller weight in variance. Radiosonde low-level q is ~2–3× looser. ACARS q is about the same.
- **Surface wind:** ours 3.5 m/s vs RAP 1.59 (2.2×).
- **Upper-air T is tighter in ours:** radiosonde 0.8 K mid-troposphere and ACARS 1.0 K vs RAP's 1.3 K floor.
- Radiosonde wind is tighter in ours near the surface (1.4–1.6 vs 2.3–2.6 m/s) and similar near the jet. ACARS wind and METAR T are about the same.
- Mesonet: RAP's public convinfo only monitors it. HRRR's scripts load a mesonet provider list (HRRRDAS) and a station use-list (deterministic HRRR) (§1), so HRRR uses mesonet, with a convinfo and errors we can't see.
- Scale: NCEP kept the same errors from 13 km (RAP) to 3 km (RRFS). That doesn't show they're wrong at 3 km. Representativeness error shrinks as resolution increases, so 13-km errors would be slightly conservative at 3 km; upper-air errors are mostly instrument error anyway; and NCEP handles much of the rest with thinning, time windows and gross/variational QC (user's point, 2026-10-03). The NCEP values are a reasonable baseline. The open question is the gap between DART's MADIS defaults and NCEP's (surface humidity and wind above all), to be settled from our own innovation statistics (prior spread² + obs error² vs innovation² per type, from `obs_seq.final`).

**First look at our innovation statistics (2026-10-03, `scripts/da/innovation_stats.py output_hph`).** The math behind both estimates, with assumptions and caveats: `obs_error_diagnostics.md`. Pooled over the 4 pilot analyses (00:15–01:00 on 05-20, evening local time). Two estimates of the error each type's innovations support, as a ratio to the assigned error (rms, including boundary inflation):
- **implied:** sqrt(mean d² − mean spread²)/σ_o. An upper bound if the 5-member spread is too small.
- **Desroziers:** sqrt(mean[(y − Hx_a)(y − Hx_b)])/σ_o, over assimilated obs.

The columns convert the ratio to the base error unit (ratio × the unboosted DART error). The other three runs give the same numbers to two digits.

| Type | n | consistency mean d²/(spread²+σ_o²) | implied | Desroziers | → error (ours now) | NCEP (RAP table / effective) |
|---|---|---|---|---|---|---|
| METAR q2 | 612 | 0.11 | 0.29 | 0.32 | **5.8–6.4 % RH** (20 %) | 5.9 % |
| METAR T2 | 627 | 0.19 | 0.38 | 0.43 | **0.95–1.1 K** (2.5 K) | 2.26 K (NAM 1.26) |
| METAR U10/V10 | 574 | 0.17 / 0.26 | 0.38 / 0.48 | 0.41 / 0.47 | **1.3–1.7 m/s** (3.5) | 1.59 m/s |
| METAR altimeter | 626 | 1.05 | 1.03 | 0.83 | 0.8–1.0 hPa (1.0) | 0.54 / 1.0 hPa |
| ACARS T | 3,456 | 0.76 | 0.84 | 0.69 | 0.7–0.85 K (1.0) | 0.74–0.98 / 1.3 K |
| ACARS U/V | 3,697 | 1.19 / 1.00 | 1.10 / 1.00 | 0.93 / 0.87 | 2.2–2.75 m/s (2.5) | 2.32 m/s |
| ACARS q | 319 | 0.48 | 0.69 | 0.60 | 12–14 % RH (20 %) | 17–20 % |

- **Surface.** METAR q2, T2 and 10-m wind innovations are 3–5× smaller than our error variances allow. Both estimates put the errors near NCEP's table values (q2 almost exactly at 5.9 % RH). So surface obs carry little weight now: posterior rms vs prior: T2 1.12 vs 1.20 K, q2 1.42 vs 1.48 g/kg.
- **Aircraft.** ACARS wind is consistent. ACARS T and q could be somewhat tighter.
- **Ensemble spread.** Spread is much smaller than the innovations aloft (ACARS wind 0.9 vs 3.1 m/s rms), i.e. the 5-member ensemble is underdispersive there. The implied errors are upper bounds.
- **Caveats.** One hour, one time of day, 5 members, spatially correlated surface errors ignored. Desroziers is only exact when the assigned B and R are already right; in practice it is iterated. Read these as a direction (surface errors too large by ~2–3× in sd), not as final values. Recheck on the extension, by time of day.

**Decision and change (user, 2026-10-03): METAR errors set to NCEP values before the extension.** T2 1.26 K (NAM), 10-m wind 1.59 m/s (RAP), RH 0.059 (RAP), altimeter 1.0 hPa (unchanged), through a local patch to the METAR converter (`patches/dart_7bbd35a09_madis_metar_obs_errors.patch`, `patches/README.md`). All hourly METAR files of 05-20/05-21 are reconverted; the pilot's originals are in `obs/obs_seq_madis/metar_v1_dart_land_errors/`. The 1-hour pilot (cycles 00:15–01:00) ran with the old errors; the extension (01:15 on) uses the new ones. Radiosonde, ACARS and mesonet errors are DART's defaults (mesonet: set to RAP/RRFS values on 2026-10-14, Sec. 7.2 item 4).

**Future options for observation errors (recorded 2026-10-03, user; not done yet).**
1. **Height-dependent humidity errors.** Ours are constant (RH 0.2 for radiosondes and ACARS; `rawin_rel_hum_error`, `acars_rel_hum_error` in `ncep_obs_err_mod.f90`). RAP's grow with height: radiosonde (type 120) 7.3 % RH at 1000 hPa, 11.2 % at 850, 16.0 % at 500, 18.8 % at 250; ACARS (133) 16.6–19.7 %. The functions already receive the level pressure, so the change is a 33-level table interpolated in pressure, as `rawin_temp_error` already does (patch, rebuild, reconvert). ACARS wind is constant in both systems (ours 2.5, RAP 2.32 m/s).
2. **Per-type rescaling after conversion, instead of Fortran patches.** A small step after `convert_madis_hour.sh` (or in `make_cycle_obs.sh` before screening) that rewrites each observation's error variance from a config file: a factor or a pressure profile per type. This allows tuning many types without rebuilding converters. It must run before `wrf_dart_obs_preprocess`, so the boundary inflation is applied to the new errors.
3. **Evidence needed first.** The pilot's 4 analyses had no radiosondes, and its statistics pool all levels. Bin `innovation_stats.py` by pressure (and time of day) on the extension.

**ACARS humidity errors look larger than the data support** (ours 20 % RH; pilot implied/Desroziers 12–14 %; RAP 17–20 %). Weak evidence so far: 319 obs in one hour, pooled over levels, no instrument QC on WVSS (§2.13 of `wrf_dart_tutorial_adaptation.md`). Tightening to 14 % would double the weight of each report (variance ×2), a much smaller change than METAR's (×6–11 in variance). **Decided (user, 2026-10-13): keep 20 % for the extension**, then decide from its pressure-binned statistics; a change would go through option 1 or 2 above.

## 6. Order

**Decided (user, 2026-10-13, session "Adding more obs part 2"): this order.** Not now: the correction notes on the two `codex.HRRRv4_*` notes and a Dowell et al. check on radial velocity in HRRRDAS.

1. **Mesonet**: data, converter and `filter` are ready; the work is QC/selection and thinning.
2. **MRMS reflectivity**: everything public, and the HRRR converter exists. Needs the state changes (Q8) and enough hydrometeor spread.
3. **Radar radial velocity** (§4): shares the `REFL_10CM`-in-state work with MRMS; the pyOPAWS setup and a one-volume test can run alongside steps 1–2.
4. **GOES satellite winds**: needs a new reader.
5. VAD winds from `prep48h`: small patches, but only 6-hourly files; overlaps with radial velocity.

## 7. Mesonet (started 2026-10-13)

### 7.1 Profile of the public MADIS mesonet files

`scripts/da/profile_madis_mesonet.py <mesonet hour> [<metar hour>]`, run on 05-20 18Z (plus counts at 00, 06, 12Z). Box = `convert_madis_hour.sh`'s lat/lon box.

- **Volume.** ~198,000 records per hourly file, ~22,600 in the box from ~4,450 stations; nearly the same at 00, 06, 12, 18Z. `restrictedDataLevel` is missing everywhere (public set only).
- **Providers (18Z, reports / stations):** APRSWXNET (CWOP citizen stations) 13,862 / 1,700; MesoWest 4,574 / 1,015; HADS 2,780 / 1,306; NonFedAWOS 337 / 127; MOComAgNet 262 / 22; RAWS 244 / 241; KSDOT 224 / 25; OHDOT 187 / 17; a few NOS, CRN, SURFRAD, LCRA. APRSWXNET is ~60 % of all T, Td and wind reports. HADS is mostly hydrological: 102 usable T and 117 wind of its 2,780 reports.
- **MADIS QC.** The converter keeps a variable when its `*QCR` is 0 (`use_input_qc = .true.`). QCR = 0: T 18,378 of 18,819 present, Td 17,324 / 17,933, wind 17,742 / 18,094 (≈ 96–98 %). **Altimeter only 12,335 / 15,924 (77 %)**: APRSWXNET 10,266 / 13,649, failing mostly the spatial-consistency checks (QCR bits 6–7), as do most T, Td and wind failures. DD summary: mostly `V` (verified); failures are mostly `Q` (questioned).
- **Time.** APRSWXNET and MesoWest report every 5 min (with peaks at :00, :15, :30, :45), NonFedAWOS every 20 min, RAWS hourly. In one cycle window (t ± 7.5 min, our `filter` window) at 18:15: 4,734 QCR = 0 T reports from 2,445 stations; 1,040 stations report once, 533 twice, 861 three times. ± 6 min (RRFS's mesonet window): 4,225 from 2,393. 00, 06, 12Z windows: 4,730–4,830 reports from ~2,450 stations.
- **Duplicates with METAR.** 44 mesonet station IDs (all NonFedAWOS) are also METAR stations in the same hour (435 METAR stations in the box), so they would enter twice. 45 mesonet stations sit within 1 km of a METAR site (mostly the same NonFedAWOS ones, plus 9 RAWS).
- **Density after one report per station:** ~2,450 stations per cycle over the 1,375 × 975 km domain, ~1 per 550 km² (mean spacing ~24 km, clustered in cities for APRSWXNET), against ~160 METAR T obs per cycle in the pilot. So mesonet would be ~15× the METAR count at the surface.
- **Converter.** `convert_madis_mesonet` has no provider selection, no per-station time selection and no thinning; it writes every QCR = 0 report of the hour. Its errors come from the `land_*` functions in `ncep_obs_err_mod.f90` (DART defaults 2.5 K, 3.5 m/s, RH 0.2, 1.0 hPa), which no other converter we build uses, so they can be changed without touching METAR.
- **Already in place downstream.** `input.nml.obs_preprocess` names `land_sfc_extra = 'obs_seq.land_sfc'` and its surface elevation check (`sfc_elevation_tol = 300` m) and boundary error inflation apply to `LAND_SFC_*` as to METAR. `make_cycle_obs.sh` doesn't have the family yet.

### 7.2 Proposed design (for decision)

1. **Per-cycle selection before the converter.** A Python step builds, for each analysis time t, a reduced `mesonet_input.nc` from the hourly files around t: records in (t − 450 s, t + 450 s] (the `filter` window, as for the other families), the **one record per station closest to t** (ties: the earlier one), **stations with a METAR ID in the same hour dropped**, then the stock converter and the box trim. Within the chosen record, a variable that fails QC is dropped, not taken from another record. Reason: 5-min stations would otherwise enter 2–3 times per cycle with correlated errors; the stock converter can't select, and DART has no surface thinning. The output is a per-cycle `obs_seq.land_sfc`, which `make_cycle_obs.sh` uses directly instead of slicing hourly files.
   **Written 2026-10-13:** `scripts/da/select_mesonet_cycle.py` (selection, options a / b1 / c, calm keep / drop) and `scripts/da/make_cycle_mesonet.sh <YYYYMMDDHHMM> [option] [calm]` (selection, stock `convert_madis_mesonet`, per-type counts), output in `obs/obs_seq_mesonet/<option>_calm<calm>/<t>/` (`obs_seq.land_sfc`, `counts`, `selected.csv` with provider per station, `selection.log` with the list files' sha256 and the RRFSv2 commit). Lists read from the `RRFSv2` clone: P1 and S2 from `msonet_uv288.yaml`, S1, and P4 from P5 (same 9 providers). Not yet called by `make_cycle_obs.sh`. Observation errors: the patched `land_*` functions (item 4) since 2026-10-14; before that, DART's defaults. Changes from the design above, found in testing:
   - **One record per site, not per station**: same latitude and longitude (4 decimals), closest to t, ties to the record with more usable variables. At 01:15, 2,521 (provider, station) pairs were 2,506 sites: HADS and MesoWest report some stations under the same ID, some APRSWXNET stations have two IDs, and `convert_madis_mesonet` drops the second of two records with the same location and time, whatever variables it holds.
   - A record is a candidate only if it has at least one usable variable.
   - **q needs a usable altimeter**: `convert_madis_mesonet` computes q from T, dewpoint and the pressure from the altimeter, and writes no q without the altimeter. At 01:15 (option a), 712 sites with usable T and dewpoint get no q for this reason (APRSWXNET 382, MesoWest 214, RAWS 72, KSDOT 18, OHDOT 17): q 1,498 vs T 2,425. Fixing it needs a converter patch (e.g. pressure from the station elevation when there is no altimeter); not done, for decision.
   - Under b1 and c, blanking a non-accepted altimeter would also remove q, so the altimeter is kept where q is kept (370 extra altimeter obs at 01:15 under b1, logged); the altimeter is evaluate-only.
   - Test results (no job; ~4 s per cycle on a login node), obs per type T / q / u (= v) / altimeter: 01:15 (a) 2,425 / 1,498 / 658 / 1,583 (147 calm winds kept); (a) with calm drop 2,425 / 1,498 / 529 / 1,583; (b1) 1,815 / 370 / 22 / 373; (c) 4 / 0 / 2 / 3; 01:00 (a), window over two hourly files, 2,532 / 1,465 / 768 / 1,552. The selection's per-variable counts equal the converter's output counts; 31 METAR-duplicate stations dropped at 01:15.
2. **Station and provider selection. Decided (user, 2026-10-13): keep (a), (b1) and (c) as options; use (a) for the first tests.** (b2), S6 instead of S1, and the earlier stand-in (d) are dropped. Details, list files (P1–P5, S1–S6), code references and the counts: `mesonet_station_selection.md` §2–5. Kept stations at 18Z (usable: T 2,953, q 2,553, wind 2,572 non-calm, altimeter 1,715): **(a) RRFS v2 as it is** (T, q, pressure from all providers; wind from P1 providers + S2 stations): 2,953 / 2,553 / 950 / 1,715. **(b) GSD method as in deterministic HRRR and RRFS v1** (P4, 9 providers, from the HRRRv3 and RRFS v1 repo history, plus a stand-in for the non-public S5): with S1 (2026) 2,108 / 815 / 41 / 3, with S6 (2017) 932 / 799 / 160 / 3. **(c) HRRRDAS** (P4 only): 4 / 0 / 2 / 3, i.e. essentially no mesonet in our domain. Under (b) almost everything comes through S5, so its date matters, and the May 2025 S5 is not available. Calm winds were dropped in these counts (as GSI's `i_gsdqc = 2` does in HRRR and RRFS v1). **Calm winds, decided (user, 2026-10-13): a switch in the selection step, default keep, as RRFS v2 does** (its wind observer has no calm check). DART can't drop them: `convert_madis_mesonet` turns a calm report into u = v = 0 (it checks only |u|, |v| < 150 m/s), `obs_sequence_tool`'s value filter (`min_copy`/`max_copy`/`copy_type`) keeps one type within one range and can't express u = v = 0, and `filter` has no value-based check; so the selection step marks the wind of a calm report missing when the switch says drop. Under (a), calm reports are 128 of 4,093 accepted wind reports at 18Z (3 %) and 919 of 4,157 at 06Z, 01 CDT (22 %; MesoWest 725 of 3,146, RAWS 69 of 241). Per-cycle counts come from the selection script.
3. **Variables in the first round: T, q and wind assimilated; altimeter evaluated only** (`evaluate_these_obs_types`). Wind is assimilated because the item-2 selection (P1 + S2 under (a), P4 + S1 under (b1)) restricts it to the stations RRFS/HRRR trust; altimeter fails MADIS QC 23 % of the time, and under (b) and (c) only P4 providers pass (3 stations). Alternative (the earlier proposal): wind evaluated only too, for a first look at its statistics. Per-provider statistics need the provider in the output; `obs_seq` can't carry it, so keep a per-cycle CSV (station, provider, lat, lon, time, values) next to the obs file and match by location when analysing.
4. **Errors. Decided (user, 2026-10-14): RAP/RRFS values, applied** (`patches/dart_7bbd35a09_madis_mesonet_obs_errors.patch`, `convert_madis_mesonet` rebuilt; check: same observations as before, error sd T 2.5 → 3.0 K, wind 3.5 → 3.0 m/s, q × 0.35, altimeter unchanged). The proposal: RAP effective values (§5), which are also RRFS v1's (same errtable and convinfo bounds, §5 and `mesonet_station_selection.md` §4): T 3.0 K, q 7 % RH, wind 3.0 m/s, altimeter 1.0 hPa (unchanged), through a local patch of the `land_*` functions, as for METAR. Alternative: keep DART's defaults (2.5 K, RH 0.2, 3.5 m/s) for a first look. RAP's mesonet T error is looser than its METAR error (3.0 vs 2.26 K) and its q error about the same (7 vs 5.9 % RH). RRFS v2 (JEDI) assigns T 4.0 K without the 3.0 K clip, then inflates it further. **Why not our METAR values** (1.26 K, 5.9 %, 1.59 m/s, 1.0 hPa): every NCEP table (NAM, RAP, RRFS) gives mesonet (188/288: 4.0 K, 7 %, 3.0 m/s, 0.54 hPa) larger errors than METAR (187/287: RAP/RRFS 2.26 K, 5.9 %, 1.59 m/s; NAM 1.26 K, 2.7 %, 1.92 m/s), and RAP, RRFS v1 and RRFS v2 all keep that difference. Our METAR T (NAM's 1.26 K) was chosen from the pilot's METAR statistics; there are no mesonet statistics yet, so mesonet T follows RAP/RRFS. To check against mesonet innovation statistics once mesonet is assimilated.
5. **No spatial thinning at first; localization as for METAR** (one conventional cutoff, as HRRRDAS's single 300-km pass). Risk to watch: ~2,450 extra surface obs per cycle with 5 members may collapse low-level spread; check prior spread and the T/q consistency ratios. Fallbacks: superobbing on a ~10–20 km grid or a larger error.
6. **Data.** All 72 hourly files of 05-19..05-21 are on disk (`obs/madis/mesonet/`, 2.1 GB, downloaded 2026-09-25 with the other MADIS families; `wrf_dart_tutorial_adaptation.md` 2.13). Listed in `cases/20250520/DATA_SOURCES.md` with the other downloads (2026-10-15).

**Wired in (2026-10-14, session "Adding more obs part 4").** Settings in `config/experiment.sh`: `MESONET` (`none`, default, or `<option>_calm<calm>`, e.g. `a_calmkeep`) and `OBS_NAME` (observation set `obs${OBS_NAME}/`; default `obs/`, step 13's, built 2026-10-02 with DART's METAR errors). `make_cycle_obs.sh` runs `make_cycle_mesonet.sh` when `MESONET != none`, puts its `obs_seq.land_sfc` in `prep/` (no slicing) and records the set's contents in `obs${OBS_NAME}/obs_settings.txt`; it refuses to write into a set with other contents or into `obs/`. `driver.sh` adds `obs=obs${OBS_NAME} mesonet=...` to `settings.txt` when `OBS_NAME` is set (step 13 runs keep their line). `input.nml.filter` assimilates `LAND_SFC_{U,V}_WIND_COMPONENT`, `_TEMPERATURE`, `_SPECIFIC_HUMIDITY` and evaluates `LAND_SFC_ALTIMETER`.
**METAR precedence (decided, user, 2026-10-14).** The first build lost METAR stations (00:15: 4 of 139; 01:00: 16 of 315): `wrf_dart_obs_preprocess` adds land surface before METAR and skips "duplicate" locations, and with `r8 = r4` its 1e-5 rad test is in practice a ~1.5–3.7 km test (float32 `acos`; `dart_namelist_discussion_log.md`, 2026-10-14 entry). `select_mesonet_cycle.py` now drops mesonet sites within 4 km (`--metar-radius-km`) of a METAR report of the same window (from the converted hourly METAR `obs_seq` files); the hourly METAR-ID check stays. METAR counts after screening are identical to the MADIS-only set in all four cycles.
**Elevation in feet (decided, user, 2026-10-14: drop those sites).** Found while breaking down the screening (below): the sites the 300-m elevation check drops are nearly all APRSWXNET, with reported elevations a median 3.3 × the model terrain, i.e. feet. `select_mesonet_cycle.py` rule 2c drops a site inside the domain whose elevation misfits the bilinear model terrain (mean `wrfinput` `HGT`, Lambert `llij_lc` checked against XLAT/XLONG to 0.001 grid lengths) by > 100 m as metres but < 60 m as feet. At 00:15 the misfit-as-metres bins separate cleanly: 0–50 m 1,799 sites (feet and metres indistinguishable), 50–100 m 94 (6 fit as feet), 100–150 m 37 (none), 150–200 m 17 (5), 200–300 m 18 (8), > 300 m 60 (55). Each cycle writes the dropped sites to `dropped_feet.csv` (reported elevation, as metres from feet, model terrain). Why it matters beyond the check: `convert_madis_mesonet` makes q with the station pressure from the altimeter and the elevation. Not caught: feet sites on low terrain (misfit < 100 m). For later: report the stations to MADIS/CWOP? check APRSWXNET q innovations for the low-terrain ones.
**Per-cycle effect of rules 2b and 2c** (obs the removed sites would have put into `obs_seq.land_sfc`, before screening; `selection.log`, "removed by"):

| cycle | 2b near METAR: sites / T / q / wind (u, v each) / alt | 2c feet: sites / T / q / wind / alt |
|---|---|---|
| 00:15 | 38 / 37 / 26 / 18 / 26 | 68 / 56 / 38 / 4 / 52 |
| 00:30 | 36 / 35 / 25 / 18 / 25 | 68 / 59 / 42 / 4 / 53 |
| 00:45 | 10 / 10 / 7 / 4 / 7 | 66 / 57 / 41 / 4 / 51 |
| 01:00 | 113 / 110 / 57 / 45 / 59 | 60 / 49 / 35 / 4 / 47 |

2b removes most at 01:00, when the hourly METARs (~:53) fall in the window; 2b's sites are about half APRSWXNET, half MesoWest; 2c's are APRSWXNET (56–64) and MesoWest (4). Most 2c sites would have failed the 300-m check anyway (screened T at 00:15: 1,740 before 2c, 1,727 after).
**Screening breakdown** (`wrf_dart_obs_preprocess` rerun on the mesonet file alone: as configured; without the elevation check; without it and with `obs_boundary = 0`; the as-configured run reproduces the cycle's counts; boundary is tested first). Before rule 2c, all four cycles, share of the obs in `obs_seq.land_sfc`: T 9,441: outside the Lambert domain 17.4 %, 5-point boundary zone 7.0 %, elevation 2.1 %, kept 73.6 %; q 19.4 / 6.6 / 2.6 / 71.4 %; wind 22.0 / 5.4 / 0.3 / 72.3 %; altimeter 19.6 / 6.9 / 3.1 / 70.5 %. "Outside" is the selection's lat/lon box (that of `convert_madis_hour.sh`) being a rectangle around the curved domain; harmless.
Set `obs_meso_a_calmkeep/` after screening (rules 2b and 2c), T / q / u (= v) / altimeter: 00:15 1,727 / 1,035 / 459 / 1,082; 00:30 1,706 / 1,023 / 433 / 1,076; 00:45 1,663 / 1,002 / 427 / 1,051; 01:00 1,799 / 1,006 / 537 / 1,053.
**Reference for the mesonet/MRMS tests (decided, user, 2026-10-14): a new MADIS-only run, not `_hph`.** `_hph` used `obs/` (DART's METAR errors), while every set built now has the NCEP METAR errors, so comparing against `_hph` would change two things at once. Set `obs_madis/` (`OBS_NAME=_madis MESONET=none`, 00:15–01:00) is built: counts per type identical to `obs/`, METAR error sd T 2.5 → 1.26 K, wind 3.5 → 1.59 m/s, humidity RH 0.2 → 0.059 (checked in `obs_seq.out` at 00:15, where the q error is stored as σ_RH × q_sat in kg/kg: median 4.5 → 1.3 g/kg, ratio 0.295 = 0.059 / 0.2). **Runs wait until all coding, scripting and parameter changes (mesonet and MRMS) are done (user, 2026-10-14);** then the reference and the test runs go one at a time.

Earlier status, kept for the record: **Not wired in yet (2026-10-14): mesonet is built per cycle but not used by `filter`.** Two steps remained before a cycle assimilates it:
1. **`make_cycle_obs.sh` doesn't include it.** Its family loop is `metar acars rawin marine` (hourly files sliced to the window). It needs to run (or find) `make_cycle_mesonet.sh <t> [option] [calm]` and copy that cycle's `obs/obs_seq_mesonet/<option>_calm<calm>/<t>/obs_seq.land_sfc` into its `prep/` directory as `obs_seq.land_sfc`, which `config/input.nml.obs_preprocess` already names as `land_sfc_extra`; no time slicing (the selection already applies the window). Then check that `wrf_dart_obs_preprocess` keeps them (domain and boundary trim, `sfc_elevation_check` with 300-m tolerance, boundary error inflation) and how many survive. The option and calm setting should become per-run settings in `config/experiment.sh`, recorded in `settings.txt` like the other run settings.
2. **`config/input.nml.filter` doesn't list the types.** Add `LAND_SFC_TEMPERATURE`, `LAND_SFC_SPECIFIC_HUMIDITY`, `LAND_SFC_U_WIND_COMPONENT`, `LAND_SFC_V_WIND_COMPONENT` to `assimilate_these_obs_types` and `LAND_SFC_ALTIMETER` to `evaluate_these_obs_types` (item 3; discussion log 2026-10-13). They are compiled into our `filter` (Sec. 2); nothing else in the namelist changes (same `cutoff`, no special localization). `innovation_stats.py` then gives the first mesonet statistics, to check the errors of item 4.

### 7.3 How HRRR, HRRRDAS and RRFS select mesonet observations (checked 2026-10-13)

Moved to `mesonet_station_selection.md`: reference repos (`HRRR`, `GSI`, `RRFSv1`, `RRFSv2`, `GSI-fix_subset`), every list file found, GSI's selection logic and a per-system summary. In short: HRRR, HRRRDAS and RRFS v1 run the same GSI code (GSD method, `i_gsdsfc_uselist = 1`, `i_gsdqc = 2`); a report is used if its provider is on P4 (all variables) or, in deterministic HRRR and RRFS v1 only, its station is flagged for that variable on S5, GSL's daily station list (T, q, wind; never pressure). HRRRDAS has no station list, so P4 providers only. RRFS v2 restricts only wind (P1, 20 providers, + S2, 4,214 stations) and takes T, q and pressure from all providers. P4 is 9 regional networks (public in the HRRRv3 and RRFS v1 git history), so almost all mesonet comes in through S5; S5 is not public (dated copies S6, 2017, and S1, 2026, are).

**Calm winds pass MADIS QC and are common**: of the QCR = 0 wind reports in the box, 2,342 of 17,742 are calm at 18Z (APRSWXNET 2,185 of 13,373) and 7,589 of 17,932 at 06Z, 01 CDT (APRSWXNET 6,561 of 13,418, 49 %; MesoWest 725 of 3,146). GSI's `i_gsdqc = 2` rejects them all.

## 8. MRMS reflectivity (started 2026-10-14, session "Adding more obs part 3")

Family 2 of §6. Following HRRRDAS (§1: preprocessing, separate 18-km EnKF pass, H(x) = `REFL_10CM`).

### 8.1 HRRR's program, read (step 1)

`sorc/hrrr_process_mosaic.fd/process_NSSL_mosaic_to_dart_and_netcdf.f90` with the namelist in `scripts/hrrrdas/exhrrr_prep_radar.sh` (`HRRR` clone, `40ee6058`). Besides §1 (corrected there: bilinear interpolation, not a max; thinning spacing skip + 1):
- **Missing/clear rule** (GRIB2 path, `tversion = 1`): all 4 MRMS neighbours > −90 → bilinear value (it can be negative: real echoes go down to about −15 dBZ); else all > −900 → −99 (clear); else −999 (no coverage, MRMS −999). The MRMS codes, per NSSL's GRIB2 table (`mrms-support/GRIB2_TABLES/UserTable_MRMS_v12.2.csv`, row `209,9,0,MergedReflectivityQC`): **Missing = −99, No Coverage = −999**. "Missing" there means a point inside radar coverage with no valid reflectivity, i.e. no echo detected (probably also where MRMS QC removed non-weather echo; not checked); "No Coverage" means no radar samples that height there. The data agree: −999 is mostly at low levels (69 % of our domain at 0.5 km, beam above the level), −99 dominates aloft (99.5 % at 19 km). HRRR treats −99 as clear air and −999 as no ob, and so does our port. The outermost model row/column gives no obs. Clear-air candidates are −900 < Z ≤ 0, which includes weak real echoes (−15..0 dBZ) and the −99 "mixed" points at echo edges.
- **Thinning** is greedy in the Fortran scan order (j outer, i inner, per level), applied after the vertical selection.
- **Obs time.** HRRRDAS runs the radar prep once per hourly cycle with `subhtime = 00` (`ecf/prep/jhrrrdas_prep_radar.ecf`), so it wants the MRMS set at HH:00. The program receives only `analysis_time = YYYYMMDDHH` and sets `minute = 0, second = 0` itself, so every DART ob is stamped HH:00:00, not the MRMS valid time (files come at irregular seconds, e.g. HH:00:38). This doesn't matter for HRRRDAS: GSI reads the netCDF copy (`Gridded_ref.nc` → `dbzobs.nc`, also dated only by `YYYYMMDDHH`), and the DART file is a by-product. (Which MRMS set it reads, and its fallback quirk: "Input files" below.)
- **Longitudes.** `DART.f90` (`write_DART_ob`) converts negative longitudes to [0, 2π) before writing (`if (olon.lt.0.0) olon=olon + 2.0*pii`), as DART expects: `threed_sphere/location_mod.f90` stores longitude in radians, 0 to 2π, and `set_location` rejects longitudes outside [0, 360]°, but `read_location` reads an ASCII `loc3d` line without any check, so a negative value would be read silently. Our port writes [0, 2π) too. (Corrected 2026-10-14: the first version of this note said HRRR writes negative radians; it doesn't.)
- **What our port does instead:** each ob gets the MRMS valid time read from the GRIB2 (00:14:38 for the 00:15 analysis). For `filter` this only decides whether the ob is inside the cycle window, (t − 450 s, t + 450 s] for `assimilation_period_seconds = 900` (as in `make_cycle_obs.sh`); DART does no time interpolation within the window, so the ob is used exactly as if stamped 00:15:00. The file set is chosen with HRRRDAS's rule (minute mm, else mm − 1, else mm − 2), done with real date arithmetic, so the 01:00 fallback is 00:59, not 01:59. Since MRMS sets come every ~2 min, the chosen set is always 0–2 min (plus seconds) before t, well inside the window. The time recorded in `obs_seq.final` is then the real MRMS time. Copying the Fortran's stamp would put every ob of a :15, :30 or :45 analysis at HH:00:00, outside that cycle's window, so `filter` would use none of them.
- **Input files: which set, and which format** (`scripts/hrrrdas/exhrrr_prep_radar.sh`; `scripts/conus/exhrrr_prep_radar.sh` has the same code; checked 2026-10-14).
  - *Which time.* The script looks in NCO's MRMS GRIB2 directory (`${COMINmosaic}/conus/MergedReflectivityQC`, `COMINmosaic = ${DCOMROOT}/ldmdata/obs/upperair/mrms`, `jobs/JHRRR_PREP_RADAR`) for a complete set of 33 levels at the analysis minute mm, else mm − 1, else mm − 2. **Timing quirk:** the earlier minutes are computed as `mmm1 = mm − 1` (+ 60 if negative) with the hour unchanged, so for HRRRDAS (mm = 00) the fallbacks are HH:59 and HH:58 of the **same** hour, 59 and 58 minutes *after* the analysis, not 1 and 2 minutes before. In real time those files don't exist yet, so HRRRDAS in effect has no GRIB2 fallback. (For the deterministic HRRR runs at :16, :30, :46 the arithmetic is fine; `subhtime = 60` gives mm = 00 again.)
  - *Which format.* The program has a reader for each of three containers of the same product (MRMS/NMQ merged 3-D reflectivity on a lat/lon grid), selected by `tversion`:
    - **GRIB2** (`tversion = 1`, `read_grib2_mod.f90`): one CONUS file per level, 33 files; one MPI rank per level, so ≥ 33 ranks. This is the product on AWS and the path our port follows.
    - **4-tile NSSL binary** (`tversion = 4`, `read_nssl_binary.f90`, M. Hu 2013): NSSL's `MREF3D33L` format, the CONUS mosaic split into 4 geographic tiles, each file one tile with all 33 levels; header (grid, NW corner, spacing, the 33 heights, scale, missing value) then 2-byte integers in dBZ × 10. Read from `${COMINmosaic}/tile1..4/mrefl/MREF3D33L.YYYYMMDD.HHMM00.gz`, at the analysis minute only.
    - **8-tile NCEP binary** (`tversion = 81`, `read_ncep_binary.f90`, M. Hu 2007): an older format of the earlier NMQ mosaic, 8 tiles, **31 levels**, header with size, spacing, centre lat/lon, 31 heights, missing and no-coverage values. Read from `${COMINradar}/radar.${ymdh}/tile1..8/`, but `COMINradar` now points to the Level-II directory (`radarl2`; the old `hourly` setting is commented "2beRemoved"), so this last fallback looks like a leftover that would find nothing.
  - *The 33/36 mismatch.* The script copies a GRIB2 set only when it finds exactly 33 files, sets `numgrib2` = 33 from that list, but takes the GRIB2 path only `if [ $numgrib2 -eq 36 ]`; otherwise it uses the 4-tile files if all 4 exist, else the 8-tile ones. As written the GRIB2 path never runs, and HRRRDAS reads the 4-tile binaries. Only the script is visible to us, not the operational directories, so whether operations actually received `MREF3D33L` tiles is not confirmed.
  - *Why the "max".* Each rank reads one piece (a tile, or a level for GRIB2) and interpolates it to the model grid; `MPI_REDUCE(MAX)` merges the pieces, taking the larger value where tiles overlap. That is the origin of the earlier "max over the tile overlap" wording (corrected in §1): it merges pieces, it doesn't average over the model box.
  - *For us:* AWS has only GRIB2, so the format question doesn't affect our files; after reading, all formats go through the same interpolation, thresholds, thinning and output (the 8-tile path aside, with its 31 levels).
- **Against `codex.HRRRv4_radar_data_assimilation_summary.md` §2** (which quotes Dowell et al. 2022: ~6 km in precipitation, ~12 km in non-precipitating regions, "together with vertical thinning"), checked 2026-10-14. The skips are in grid points; HRRRDAS's reflectivity domain is the 3-km d02 (`parm/hrrrdas/hrrrdas_namelist.wps`, 1801 × 1061; the same program also runs on the 15-km d01). Precipitation: every 2nd point = **6 km, agrees**. Clear air: every 6th point = **18 km, not 12 km** (12 km would be `clear_air_dbz_horiz_skip = 3`). The namelist values are unchanged since the first HRRRv4 commit (`6c22a053`), so the code has never given 12 km. Vertical, which the codex note doesn't detail: precipitation at every 3rd MRMS level up to 11 km (9 levels), clear air at 4.0 and 8.5 km only. On our 2.5-km grid the same skips give 5 km and 15 km; matching HRRRDAS in km instead would be skip 1 (5 km) and skip 6 (17.5 km) or, for the paper's 12 km, skip 4 (12.5 km). **Decided (user, 2026-10-14): keep HRRRDAS's grid-point skips** (precipitation skip 1, clear air skip 5; 5 km and 15 km on our grid), the converter's defaults.

### 8.2 Port to Python, first file (steps 2–4)

**Port, not build (confirmed by the user 2026-10-14):** building needs NCEPLIBS bufr/g2/w3 (not on Cirrus) and ≥ 33 MPI ranks, writes BUFR and netCDF we don't use, and fixes the obs time to the hour. `scripts/da/mrms_to_obs_seq.py MRMS_DIR YYYYMMDDHHMM GEO_EM OUT [--grid-nc FILE]` reproduces the Fortran (GRIB2 path, HRRRDAS namelist as defaults, all overridable) with two differences: obs time = MRMS valid time, and HRRRDAS's minute rule for picking the file set done with real date arithmetic. Longitudes are written in [0, 2π), as the Fortran does. Reads GRIB2 with `eccodes` + `eccodeslib` (added to the uv environment). ~15 s per time on a login node.

- **Data** (2026-10-14): `obs/mrms/20250520/`, the 33 `MergedReflectivityQC_XX.XX` levels at 00:14:38, 00:30:40, 00:44:42 and 01:00:38 (all levels of a set share the time; `scripts/da/download_mrms.sh <t>`, HRRRDAS's minute rule; each inside its cycle window), 28 MB per set, from `https://noaa-mrms-pds.s3.amazonaws.com/CONUS/MergedReflectivityQC_XX.XX/20250520/`. Files are at irregular seconds about every 2 min (00:12:38, 00:14:38, 00:16:39, ...). GRIB2: 7000 × 3500, 0.01°, rows north → south from 54.995 N, 230.005–299.995 E, PNG packing; −999 No Coverage, −99 Missing (= covered, no echo; §8.1).
- **Test time 2025-05-20 00:15** (first pilot analysis; convection is active over the domain all day on 05-20 in the `theta_m0` run: 10–25 % of columns ≥ 10 dBZ). Output `obs/obs_seq_mrms/obs_seq.mrms.2025052000_15` and the gridded field `mrms_grid.2025052000_15.nc`; figures `figures/mrms/mrms_obs_2025052000_15.png` (MRMS composite on the grid, `theta_m0` column max at 00:15, 4-km obs; the clear-air markers there are drawn larger than a grid point and the precipitation obs as single pixels, so it overstates the clear-air obs) and `figures/mrms/mrms_obs_zoom_4km_2025052000_15.png` (80 × 60-point zoom at 4 km: precipitation obs every 2nd point inside ≥ 10 dBZ, a no-ob band at 0–10 dBZ, clear-air obs about every 6th point elsewhere, a few at echo edges).
- **Counts:** 88,155 obs = 79,075 `RADAR_REFLECTIVITY` + 9,080 `RADAR_CLEARAIR_REFLECTIVITY` (4.0 km 4,633, 8.5 km 4,447). Before thinning 882,834 precipitation and 3,887,460 clear-air candidates. Precipitation obs per level (0.5 → 11 km): 1,153, 4,705, 6,352, 8,193, 11,413, 13,131, 13,469, 12,478, 8,181. DART's `obs_sequence_tool` (same build as `filter`) reads the file: both types recognised, all at 2025-05-20 00:14:38.
- **Coverage:** no MRMS coverage over 69 % of the domain at 0.5 km, 26 % at 1.0 km, 2 % at 2.0 km, none above 2.75 km, so few low-level obs. ≥ 10 dBZ on 12–24 % of the domain at 2–9 km (much of it the trailing stratiform/anvil of the NW line); 0–10 dBZ (unused) 1–6 %. Precipitation obs: median 26 dBZ at 0.5 km falling to 14 dBZ at 11 km, maxima 50–63 dBZ.
- **Clear-air obs at echo edges:** 439 of 4,633 (4 km) and 390 of 4,447 (8.5 km), about 9 %, are next to a ≥ 10-dBZ point, from the −99 neighbour rule. Kept, as in HRRRDAS; with 18-km localization they pull against adjacent precipitation obs. Option for later: a one-point buffer.
- **At 1 MRMS time per cycle, 15-min cycles:** ~90,000 obs per cycle at a convective time, against ~160 METAR T obs (pilot) and ~2,450 mesonet stations (§7.1) per cycle. `filter` cost and the per-type cutoff (§8.3) to check before the first cycled test.

### 8.3 Found while checking our `filter` setup

- **Set 2026-10-14 (both filter namelists, Sec. 8.4): `microphysics_type = 5` and the −10 dBZ forward-operator floor below.** Before: `input.nml.filter` had `microphysics_type = 2` (DART default). `get_expected_radar_ref` first tries `QTY_RADAR_REFLECTIVITY` from the state whatever the setting; when that fails, 1/2 fall back to a Lin-type calculation from qr/qs/qg (not Thompson-consistent), while 3/5 stop with a message. With `REFL_10CM` in the state it must be **5**, so a missing field can't pass silently.
- **Clear-air floor (checked 2026-10-14).** Thompson floors `REFL_10CM` at −35 dBZ (`refl_10cm = MAX(-35., dBZ)`; `module_mp_thompson.F:1465` in HRRR's WRF (`sorc/hrrr_wrfarw.fd/WRFV3.9`), `:1461` in ours), so clear model air is −35 dBZ. HRRR and HRRRDAS run aerosol-aware Thompson, `mp_physics = 28` with `do_radar_ref = 1` (`parm/conus/hrrr_wrf.nl:107,109`, `parm/hrrrdas/hrrrdas_wrf.nl:100,103`; package `thompsonaero` → `mp_gt_driver`), the same scheme as our runs (`namelist.input.wrf`: `mp_physics = 28`). HRRRDAS's GSI observer (`hrrrdas_gsiparm.anl`: `if_model_dbz = .true.`, `static_gsi_nopcp_dbz = -10.0`, `miter = 0`) **floors H(x) at −10 dBZ** for each member and the mean (`setupdbz.f90:436–442`, applied when `miter == 0`, i.e. EnKF runs) and floors the obs at −10 too (`read_dbz_nc.f90:372–375`; MRMS clear-air obs are −10 already, precipitation obs ≥ 10). Effects: a clear-air ob (−10) at a point where every member is clear (−35 → −10) has zero innovation and zero H(x) spread, so it does nothing; it acts only where some members have echo above −10 dBZ, pulling them down (spurious-convection suppression). A precipitation ob where all members are clear has zero H(x) spread, so it does nothing either; where some are clear, those count as −10, not −35, which keeps innovations and spread from being inflated by the model's arbitrary −35 floor. Other settings: `missing_to_nopcp = .false.` (MRMS No Coverage stays unused), `ens_hx_dbz_cut` default `.false.` (no 60-dBZ cap on H(x)), `radar_no_thinning = .true.` (thinning only in the prep program). **DART equivalent:** `- `apply_ref_limit_to_fwd_op = .false.`: `REFL_10CM` goes down to −35 dBZ in clear air, while the clear-air obs are −10 dBZ. To decide with the localization/impact settings (step 6).obs_def_radar_mod_nml` `apply_ref_limit_to_fwd_op = .true.`, `reflectivity_limit_fwd_op = -10.0`, `lowest_reflectivity_fwd_op = -10.0` (`where (ref < limit) ref = lowest`, `obs_def_radar_mod.f90`, after the state interpolation of `REFL_10CM`); now `.false.`. Proposed for step 6.
- DART's `grid_refl_obs` (built) is not a converter: it maps reflectivity obs from an `obs_seq` onto WRF grid points (for `add_pert_where_high_refl`).

### 8.4 Into the cycle: two-pass filter (built 2026-10-14, not run; `MRMS_FILTER=two_pass`; one-pass alternative in Sec. 8.5)

**Decisions (user, 2026-10-14):** port, not build (Sec. 8.2); HRRRDAS's analysis variables; the converter copies the
preprocessor's boundary trim and error inflation; **two filter passes per cycle, as HRRRDAS**; QNRAIN by Thompson's
1-mm rule (all three rules below); the spread check of `REFL_10CM` and the hydrometeors counts as a run. Open:
inflation in the second pass (user researching); `outlier_threshold` for radar obs.

**How HRRRDAS does it** (Dowell 2020 pp. 5–6; `scripts/hrrrdas/exhrrr_analysis.sh`, `exhrrr_enkf.sh`, `../software/HRRR`
@ 40ee6058):
1. GSI observer, once per member and for the mean, **on the background**: writes `diag_conv_ges` and `diag_radardbz_ges`
   (H(x) for reflectivity = background `REFL_10CM`, `if_model_dbz`). The same step clears clouds and hydrometeors
   from GOES cloud top, METAR and MRMS (as in HRRRv4); we have no equivalent.
2. EnKF, conventional obs: 300 km / 0.5 scale height; analysis variables U, V, T, QVAPOR, QCLOUD; RTPS 1.20 (15 km) /
   1.08 (3 km). Writes the members in place (`analysis.memNNN` and `firstguess.memNNN` are both links to the member file).
3. EnKF, reflectivity (3-km domain only): 18 km / 0.5 scale height; U, V, T, QVAPOR, QCLOUD, QRAIN, QSNOW, QGRAUPEL;
   RTPS 1.08. **Its H(x) are the diag files of step 1**, so the radar pass regresses the conventional analysis on
   background-reflectivity priors; reflectivity is never updated (GSI's EnKF can read/write `REFL_10CM` if `dbz` is in
   `anavinfo`, but Dowell's variable list has no reflectivity). (Aside: `exhrrr_enkf.sh` links the radar pass's
   `diag_conv_ges.ensmean` to `diag_radardbz_ges...mem${ensmemid}`, where `${ensmemid}` is left over from the loop
   above, i.e. a member's file, not the mean's.)
4. QNRAIN, not analysed ("EnKF analysis of rain number concentration (QNRAIN) did not benefit the forecasts"), is set
   from the analysed QRAIN "according to a Marshall-Palmer type exponential distribution"; QNCLOUD could be too but isn't.
   This step's code is not in the public repo (QNRAIN appears only in I/O, averaging, boundary and post code).

**Ours** (`slurm.cycle` → `driver.sh` → `cycle_job.sh`; a run is two-pass when its observation set has MRMS, i.e.
`mrms=` in `obs_settings.txt`, `cycle_lib.sh two_pass`):
- **Observations.** `MRMS=hrrrdas` (`experiment.sh`) makes `make_cycle_obs.sh` also write `<t>/obs_seq.mrms` with
  `mrms_to_obs_seq.py` (and `counts.mrms`, `mrms.log`); not merged into `obs_seq.out`. The converter (2026-10-14
  additions): `--obs-boundary 5` (the preprocessor's test on the 1-based x = i + 1: kept if 6 ≤ x ≤ nx − 6, so 5 rows
  dropped on the west/south sides and 6 on the east/north), `--obsdistbdy 15 --maxobsfac 2.5` (error sd × (2.607 − 0.107 d),
  d = distance to the edge in points, up to 15), both after thinning; `--window-half 450` (fails if the MRMS time is
  outside (t − 450 s, t + 450 s]); reads `YYYYMMDD/` subdirectories so the minute fallback can cross midnight.
  Set **`obs_madis_mrms/`** built for 00:15–01:00 (`mesonet=none mrms=hrrrdas`): `obs_seq.out` byte-identical to
  `obs_madis/`'s; MRMS (precipitation + clear air) 76,962 + 8,589 (00:15), 79,111 + 8,496 (00:30), 80,182 + 8,493 (00:45),
  80,507 + 8,398 (01:00); boundary zone: 2,600–2,720 dropped and 6,460–6,870 with inflated errors per cycle.
- **State.** `prep_filter.sh` extracts `QCLOUD QRAIN QSNOW QGRAUP REFL_10CM QNRAIN` too (`DART_EXTRA`, all runs).
  Pass 1 (`input.nml.filter`): QCLOUD `UPDATE`; QRAIN, QSNOW, QGRAUP, `REFL_10CM` `NO_COPY_BACK`. Pass 2
  (`input.nml.filter_mrms`, same variables): U V THM QVAPOR QCLOUD QRAIN QSNOW QGRAUP `UPDATE`; PH, MU, W, `REFL_10CM`
  `NO_COPY_BACK`. As in HRRRDAS, pass 2's H(x) is the background `REFL_10CM`: pass 1 doesn't write it back. QICE,
  QNICE, QNRAIN are not in the state. Same variables in both passes: required only with `MRMS_INFLATION=both` (pass 2
  reads pass 1's inflation files, one field per state variable), but kept the same with `pass1` too (user, 2026-10-15).
- **Localization of pass 2:** `cutoff = 0.001413` (18 km zero), `vert_normalization_scale_height = 177.0` (zero at 0.5
  scale height).
- **Flow per cycle:** extract → filter pass 1 in `run/filter/` → save to `output/<t>/filter/` → filter pass 2 in
  `run/filter_mrms/` on the same member files → save to `output/<t>/filter_mrms/` → `filter.done` → per member
  `wrfrst_dart.py qnrain` → `insert --fields U V PH THM MU QVAPOR QCLOUD QRAIN QSNOW QGRAUP QNRAIN` (hydrostatic PH
  from the saved prior, i.e. both passes' MU/THM/QVAPOR changes) → boundary refit → advance. A failure before
  `filter.done` reruns both passes from the extraction. `check_cycle.py` reports both passes.
- **Inflation (`MRMS_INFLATION`, no default; `driver.sh` refuses a two-pass run without it and records it in
  `settings.txt`):** `pass1` = adaptive prior inflation only in pass 1, carried cycle to cycle as now; pass 2 has
  `inf_flavor = 0`. `both` = pass 2 starts from pass 1's `postassim_priorinf_*`, inflates and updates it; the next cycle's
  pass 1 starts from pass 2's. **`MRMS_PASS2_DAMPING`** (user, 2026-10-15; `both` only): 1 (default) = pass 2 damps with
  `INF_DAMPING` too, so the inflation is damped twice per cycle (effectively `INF_DAMPING`² per cycle); 0 = `inf_damping
  = 1.0` in pass 2, damped once per cycle. Recorded in `settings.txt`. DART's prior
  inflation acts on the whole state, so under `both` the pass-1 analysis is inflated a second time everywhere the
  inflation exceeds 1, not only near radar obs. HRRRDAS has no prior inflation, only RTPS after each pass.
- **QNRAIN** (`wrfrst_dart.py qnrain`, after pass 2, where QRAIN differs from the prior). What Thompson does
  (`phys/module_mp_thompson.F`, our WRF): rain is exponential (`mu_r = 0`); in `mp_thompson`, rain with no number
  (`nr <= R2`) gets one from a median volume diameter of 1 mm, λ = (3 + μ_r + 0.672) / D₀; every step the diameter is
  then clipped to 37.5 µm–2.5 mm (rescaling nr); otherwise nr is kept, so a changed qr with the old nr changes the mean
  drop size by (qr_a / qr_b)^(1/3) (and is clipped if it leaves the range). Number per kg:
  nr = crg(2)/crg(3) · qr · λ³ / am_r = qr · λ³ / (π ρ_w), no air density needed. Three rules:
  1. **Thompson's 1-mm rule (used, user 2026-10-14):** λ = 3672 m⁻¹, nr = 1.576e7 · qr; nr = 0 where qr ≤ R1 = 1e-12.
  2. **Fixed intercept, Marshall–Palmer** (the literal reading of Dowell 2020): N0 = 8e6 m⁻⁴, λ = (π ρ_w N0 / (ρ_air qr))^(1/4),
     nr = N0 / (λ ρ_air) per kg (needs ρ_air), then Thompson's clip.
  3. **Keep the prior mean size:** nr_a = nr_b · qr_a / qr_b where qr_b > R1, rule 1 where the prior had no rain; then
     Thompson's clip. Closest to the model's own state, not what HRRRDAS describes.
  Tested 2026-10-14 on the pre-patch 00:15 restart of the step-7 test with a fake QRAIN change: diameter exactly 1 mm after;
  rerunning changes nothing; the prior's median diameter at rain points is 0.89 mm (so rule 1 is close to the model's
  sizes there); 15,609 points have nr > 0 with qr = 0 in the prior, left as they are.
- **Open:** `outlier_threshold = 3` also applies to radar obs (discussion log, 2026-10-14 entry); look at the QC counts
  of the first MRMS cycle. Clear-air obs at echo edges (Sec. 8.2). Filter cost: ~85–89k radar obs per cycle; check
  time and memory with a one-cycle filter-only test before a full run (needs a job).

### 8.5 One-pass alternative (built 2026-10-14, not run; asked for by the user)

A second way to take MRMS, chosen per run: **`MRMS_FILTER=one_pass`** (vs `two_pass`, Sec. 8.4; no default,
`driver.sh` requires one in a run on an MRMS observation set and records it in `settings.txt`).

- **Observations:** `make_cycle_obs.sh` (MRMS set) also writes `<t>/obs_seq.joint`, `obs_seq.out` + `obs_seq.mrms`
  merged by `obs_sequence_tool` (time order; the copy/QC names differ, "NCEP BUFR observation"/"NCEP QC index" vs
  "MRMS observation"/"Data QC", declared synonymous; the output keeps the first file's). The count is checked
  (= screened conventional + MRMS). `obs_sequence_tool` has no duplicate-location test, so the `r8 = r4` problem
  (Sec. 7.2) doesn't arise. Its `input.nml` needs an (empty) `&obs_def_radar_mod_nml` once radar obs are read.
  Built 2026-10-14 for 00:15–01:00 in both MRMS sets: `obs_madis_mrms` 88,332 / 91,099 / 91,733 / 93,756 obs per cycle,
  `obs_meso_a_calmkeep_mrms` 93,094 / 95,770 / 96,303 / 98,688; the conventional `obs_seq.out` of both still
  byte-identical to `obs_madis/` and `obs_meso_a_calmkeep/`.
- **`config/input.nml.filter_joint`:** `input.nml.filter` plus the radar types in `assimilate_these_obs_types`;
  QRAIN, QSNOW, QGRAUP `UPDATE`; `special_localization_obs_types`/`_cutoffs` = the radar types / 0.001413 (18 km);
  `special_vert_normalization_*` for the radar types with scale height 177.0 (0.5 scale height) and the other three
  at the defaults; `adjust_obs_impact = .true.` with `obs_impact_joint.txt`.
- **`config/obs_impact_joint.txt`** (runtime format of DART's impact table: one "TYPE QTY factor" line per pair,
  pairs not listed = 1, no comments or blank lines allowed by `read_impact_table`; written directly rather than with
  `obs_impact_tool`, which isn't built in `models/wrf/work` and would need DART's `quickbuild.sh` edited; documented
  in the namelist): 96 zeros, giving each family its pass's limits:
  - radar types → `QTY_PRESSURE` (MU), `QTY_GEOPOTENTIAL_HEIGHT` (PH), `QTY_SURFACE_PRESSURE` (PSFC, altimeter
    priors), `QTY_VERTICAL_VELOCITY` (W);
  - each of the 22 assimilated conventional types → `QTY_RAINWATER_`, `QTY_SNOW_`, `QTY_GRAUPEL_MIXING_RATIO` and
    `QTY_RADAR_REFLECTIVITY`. The last keeps the radar obs priors at their background values, as HRRRDAS's
    radar H(x); setting it to 1 would let them follow the conventional update (more consistent with serial
    filtering, unlike HRRRDAS).
  The table applies to state variables and to the priors of other obs (`assim_tools_mod.f90`, `cov_and_impact_factors`
  for both), by the quantity of each.
- **Inflation:** the first pass's, one adaptive prior inflation (`INF_FLAVOR`, `INF_DAMPING`) damped once per cycle and
  updated by both families. `MRMS_INFLATION` must be unset.
- **Afterwards** as in two-pass runs: `qnrain`, insert with the hydrometeors (`post_filter.sh`, `has_mrms`).
- **Differences from two_pass, i.e. what a comparison would test:** (1) order: DART processes the obs in time order, so
  MRMS (one time, 00:14:38 etc.) is assimilated in the middle of the conventional obs rather than after them, and the
  conventional obs after it see radar-updated priors (except the altimeters, by the table); (2) one inflation instead
  of pass1/both; (3) everything else (localization, update limits, radar H(x) from the background) is the same.
  Filter cost should be close to the two passes together, without the second pass's I/O.

**Earlier notes, step 5 (`REFL_10CM` in the restart file):**

5. State: `REFL_10CM` (`NO_COPY_BACK`) into the file `wrfrst_dart.py extract` builds from `wrfrst`. Checked 2026-10-14: `REFL_10CM` is not in `wrfrst` because its Registry I/O flags are `hdu` (history, nest down/up; `Registry.EM_COMMON:1611`), and runtime I/O (`iofields_filename`) accepts only the history (`h`) and input (`i`) streams (`frame/module_domain.F`, `modify_io_masks`), so putting it in the restart stream needs a **Registry patch (`hdu` → `hdur`) and a WRF rebuild** (option A). Thompson computes it only on `diag_flag` steps, i.e. steps where the history alarm rings (`solve_em.F:374–379`, `module_mp_thompson.F:1450`); our members write history every 15 min (`namelist.input.wrf`) at the same times as the restarts, so `wrfout` and a `wrfrst` with `REFL_10CM` at time t would hold the same array. Option B: `extract` reads `REFL_10CM` from the member's `wrfout` at t (no rebuild). **Decided (user, 2026-10-14): option A**, `patches/wrf_06d4240a_refl_10cm_restart.patch`, **applied and WRF rebuilt 2026-10-14** (old executables kept as `main/*.exe.pre_refl_restart`; `patches/README.md`). **Tested 2026-10-14 (job 1051956, all checks passed):** `REFL_10CM` in the new `wrfrst` is bit-identical to `wrfout` at the same time; nothing else changed against the pre-patch build (657 variables identical); restarting from a pre-patch `wrfrst` works and gives the same 00:30 state as from a new one (`patches/README.md`). Next in step 5: `wrfrst_dart.py extract --extra REFL_10CM` (and the hydrometeors), the state-variable list, `microphysics_type = 5`. Checked at the same time (2026-10-14) that nothing else DART reads comes from `wrfout`: the 12 pilot state fields come from `wrfrst` (`_2` level renamed by `extract`); the static grid fields and global attributes `model_mod` reads (XLAT/XLONG and U/V versions, HGT, PHB, MUB, P_TOP, ZNU, ZNW, DN, DNW, C1H, C2H, XLAND, ZS; MAP_PROJ, DX, DT, ...) come from filter's `wrfinput_d01` = `GRID_FILE`, the mean 00Z `wrfinput`, which has them all; the hydrometeors QCLOUD QRAIN QICE QSNOW QGRAUP QNICE QNRAIN are in `wrfrst` (`extract --extra`). `REFL_10CM` is the only field DART would need that is in neither; the hydrometeors (Q8). **Missed here (found 2026-10-21, run 1, Sec. 9):** `GRID_FILE` is also the template for every state variable's dimensions (`add_domain('wrfinput_d01', ...)`, `model_mod.f90:778`), so it must hold `REFL_10CM` too; `GRID_FILE` is now `mean/dart_wrfinput_d01_2025-05-20_00_00_00` (`scripts/da/make_grid_file.py`). Check hydrometeor and `REFL_10CM` spread in the 5 members at 00:15 against these obs.

## 9. First runs with the new observations (planned 2026-10-15, session "Adding more obs part 6")

1-hour, 5-member pilot as in step 13 (cold start 00:00, analyses 00:15–01:00, `slurm.cycle 202505200000
202505200100`, 40 nodes); every run starts from the 00Z cold start (restarts need `REFL_10CM`). **Run list (user,
2026-10-15)**, one at a time, each only after the user's go-ahead. `RUN_NAME`s agreed (user, 2026-10-21):

| # | Observations | `OBS_NAME` | Filter | `RUN_NAME` | Before it can run |
|---|---|---|---|---|---|
| 1 | MADIS (rerun of the reference) | `_madis` | one pass | `_madis` | nothing (set built) |
| 2 | MADIS + mesonet (a), calm winds kept | `_meso_a_calmkeep` | one pass | `_meso_a` | nothing (set built) |
| 3 | MADIS + MRMS | `_madis_mrms` | `MRMS_FILTER=one_pass` | `_madis_mrms1p` | nothing (set built) |
| 4 | MADIS + MRMS | `_madis_mrms` | `MRMS_FILTER=two_pass` | `_madis_mrms2p` | choose `MRMS_INFLATION` (pass1 / both; open) |
| 5 | everything | to decide | to decide | to decide | decided after 1–4 |

Run 2: the user first asked for calm winds dropped, then (2026-10-15) kept them ("does not matter really"), so it
uses the built `obs_meso_a_calmkeep/` (Sec. 7). Run 1 is also the first test of the new
pass-1 namelist (QCLOUD updated, hydrometeors and `REFL_10CM` in the state). At the first MRMS cycle (run 3): filter
wall time and memory, and the DART QC-7 (outlier) counts of the radar types (hand-off part 6, outlier check).

**Timing of runs 1–4 (user, 2026-10-15: WRF should cost the same; record how the filter cost changes).** After each
run: `.venv/bin/python scripts/da/summarize_cycle_timing.py output<RUN_NAME> --slurm-out slurm.cycle.<job>.out`
(per cycle and pass: prep_filter and the filter srun step separately, filter's read / H(x) / assimilation phases
from `filter.log`, obs count and ms per ob, post_filter update, WRF advance, total; filter steps' Elapsed and MaxRSS
from the sacct table). Results go in the table below. (Until 2026-10-21 the script had one "filter" column, the wall
`cycle_job.sh` logs; that covers prep + srun since the two-pass wiring of 10-14, but srun only in step 13, so the
columns were split and step 13's prep added below.)

Baseline, step 13 `_hph` (job 1047842, MADIS with DART's METAR errors, 5 members, filter on 8 nodes × 16 ranks), s:

| cycle | prep | srun | read | H(x) | assim | obs | ms/ob | update | advance | total |
|---|---|---|---|---|---|---|---|---|---|---|
| 00:00 (cold start) | – | – | | | | | | – | 133 | 135 |
| 00:15 | 52 | 99 | 2 | 4 | 79 | 2,781 | 28.4 | 114 | 135 | 433 |
| 00:30 | 49 | 114 | 2 | 3 | 96 | 3,492 | 27.5 | 114 | 123 | 433 |
| 00:45 | 49 | 106 | 2 | 3 | 87 | 3,058 | 28.4 | 132 | 130 | 450 |
| 01:00 | 48 | 161 | 2 | 4 | 142 | 4,851 | 29.3 | 119 | 133 | 494 |

Filter MaxRSS 1.70 GB per task in every cycle. The filter is almost all the serial observation loop, ~28 ms per ob
at the conventional cutoff (0.0235 rad, zero at ~300 km). **Wall-time risk for runs 3 and 4:** MRMS adds ~85,000–89,000
obs per cycle (Sec. 8.4); at 28 ms/ob that would be ~40 min per cycle, ~2.7 h for the hour, over `slurm.cycle`'s
2-h limit. The radar cutoff is ~17× smaller (18 km), so the cost per ob should be far lower, but DART's loop also has
a fixed per-ob cost (broadcast of the ob's prior, close-state search) that the step-13 numbers can't separate. Before
run 3: raise the time limit for that submission (e.g. `sbatch --time=06:00:00`), and check the 00:15 MRMS pass's
ms/ob as soon as it finishes.

| run | cycle | pass | prep | srun | read | H(x) | assim | obs | ms/ob | rest | update | advance | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 `_madis` | 00:00 (cold start, job 1054633) | – | – | – | | | | | | | – | 134 | 136 |
| 1 | 00:15 | conv | 137 | 59 | 3 | 4 | 18 | 2,781 | 6.5 | 20 | 138 | 151 | 553 |
| 1 | 00:30 | conv | 129 | 92 (guard) | 4 | 5 | 23 | 3,492 | 6.6 | 18 | 156 | 151 | 593 |
| 1 | 00:45 | conv | 128 | 61 | 4 | 5 | 20 | 3,058 | 6.5 | 19 | 161 | 157 | 572 |
| 1 | 01:00 | conv | 131 | 71 | 3 | 5 | 29 | 4,851 | 6.0 | 20 | 157 | 211 | 635 |
| 2 `_meso_a` | 00:00 (cold start) | – | – | – | | | | | | | – | 151 | 152 |
| 2 | 00:15 | conv | 133 | 115 (guard) | 3 | 5 | 43 | 7,543 | 5.7 | 19 | 151 | 147 | 611 |
| 2 | 00:30 | conv | 125 | 119 (guard) | 4 | 5 | 46 | 8,163 | 5.6 | 19 | 167 | 152 | 631 |
| 2 | 00:45 | conv | 131 | 117 (guard) | 4 | 5 | 44 | 7,628 | 5.8 | 19 | 162 | 149 | 624 |
| 2 | 01:00 | conv | 129 | 131 (guard) | 4 | 6 | 56 | 9,783 | 5.7 | 19 | 150 | 148 | 622 |

s; run 1's 00:15–01:00 in job 1054795 (resumed, cirrus1–4, 17–52), 39 min; run 2 job 1054801 (same nodes), 44 min.
sacct MaxRSS of run 1's filter steps 0.40, 1.99, 0.33, 2.00 GB per task (run 2: 1.99–2.00): unreliable for steps
this short (sampled; the larger values in the steps that lived longer), so not used. Step 13's `rest` was 10–11 s.

**Speeding up filter (looked up 2026-10-15; DART is v11.25.3, `7bbd35a09`).** The EAKF loop over observations is
serial; each observation's update is spread over the MPI ranks (state distributed; Anderson and Collins 2007). No
OpenMP in the update. Levers, none tested yet:
- **More ranks.** Filter runs on 8 nodes × 16 ranks (`FILTER_NODES`, `FILTER_TASKS_PER_NODE`; `-c 1`), 16 of 128 cores
  per node, while the other 32 nodes of the 40-node job wait. Nodes: 128 cores, ~256 GB; filter 1.7 GB per rank. Helps
  most where the per-ob work is large (conventional, ~300-km cutoff); the radar pass (18 km) is probably limited by the
  per-ob communication instead. Results across rank counts need not be bit-identical: pick one layout for runs 1–4.
- **`&location_nml` `nlon`/`nlat` (search boxes).** The docs: defaults are usually sufficient; for large models "the
  assimilation may run faster by doubling these values or multiplying them by 4" (more memory, shorter linear part of
  the search). The boxes are in longitude × latitude (not grid x/y) and span the searched locations' lat/lon range
  plus the search distance (2 × cutoff) on each side (`find_box_ranges` in `threed_sphere/location_mod.f90`), so they
  differ by pass. Computed from `geo_em.d01.nc` (2026-10-21; E–W at mid-domain): radar pass (search 18 km) 71 × 36
  → ~21 × 29 km, 283 × 144 → ~5 × 7 km; conventional pass (search 300 km) 71 × 36 → ~29 × 44 km, 283 × 144 → ~7 × 11
  km. (Earlier "~19 × 27 km" divided the grid itself, without the margin.) At 71 × 36 a radar ob's search covers ~5×
  the area of its 18-km circle, at 283 × 144 ~1.7×. Changes only the search, not the results. `nlon` must be odd.
  `nlon`/`nlat` apply to all types, so in `input.nml.filter_joint` the conventional obs would get the finer boxes too.
- **Settings already right:** `convert_all_{state,obs}_verticals_first = .true.`, `distribute_mean = .false.` (faster,
  more memory), `sort_obs_inc = .false.` (expensive, unneeded for EAKF), `approximate_distance = .false.` (docs: keep
  false for regional models). `close_obs_caching` (default true) is switched off by DART itself when special cutoffs
  are used (`assim_tools_mod.f90:290`), i.e. in `input.nml.filter_joint`: results correct, a little caching lost.
- **Less work (changes results):** coarser MRMS thinning / superobs (clear air especially), smaller conventional cutoff.

**Scaling test, written 2026-10-15 (not run: 40 nodes not available).** `cases/20250520/da_theta_m0/slurm.filter_scaling`
replays one saved analysis with filter only, on configs `<nodes>x<ranks per node>[:<nlon>x<nlat>]` (`SCALE_CONFIGS`),
in `tests/filter_scaling/<case>_<t>/<config>/`; per config: wall, `filter.log` phases, obs, ms/ob, analyses compared
with `scripts/da/compare_dart_members.py`, sacct MaxRSS. Cases: `conv` (default): step 13 `_hph` at 00:30, its priors,
`input.nml`, obs and input inflation; reference = that run's analyses, so 8x16 also checks the replay is exact;
default configs 8x16, 40x16, 40x32. `mrms`: `config/input.nml.filter_mrms` (no inflation) on a new run's priors
(`SCALE_SRC`, e.g. run 1's `output_madis`, which has `REFL_10CM`) with `obs_madis_mrms/<t>/obs_seq.mrms`; reference =
the first config; default configs 40x16, 40x16:283x144, 40x32, 40x32:283x144. Smaller variant without 40 free nodes:
`SCALE_CONFIGS="8x16 8x32 8x64" sbatch -N 8 slurm.filter_scaling` (ranks per node only).

**First scaling test (job 1054410, 2026-10-20, `conv`, cancelled).** 8x16 replay of step 13's 00:30 analysis:
bit-identical analyses for all 5 members (the setup and the 10-01 `filter` reproduce step 13 exactly), but the
observation loop took 122 s against step 13's 96 s for the same 3,492 obs, and the step never exited: filter printed
"Finished ... at" at 18:45:56 with all outputs written, then all ranks kept spinning at ~99 % CPU (in DART's final
barrier or `MPI_Finalize`; `ptrace` is not permitted on the nodes, so no stack). Cancelled at 18:50 before 40x16 and
40x32 ran. The job differed from `slurm.cycle` in its shape (128 tasks × 1 CPU per node, against 16 × 8) and its
environment (no `OMP_*`, `ulimit -s unlimited`); filter's own launch (`srun -N 8 -n 128 --ntasks-per-node=16 -c 1
--exact`), UCX settings, executable, namelist and inputs were the same. Changes (2026-10-20): `slurm.filter_scaling`
now has `slurm.cycle`'s shape and environment; **filter exit guard** `run_filter` in `scripts/da/cycle_lib.sh`, used
by `cycle_job.sh` and `slurm.filter_scaling`: once "Finished" is in `filter.log`, the step gets `FILTER_EXIT_GRACE`
(120 s) to exit, then, if no output file has changed for 30 s, it is cancelled (`scancel` of the step) and the run
counts as finished; logged as "filter exit guard" (also in `slurm.cycle`'s output) with `filter_exit_guard.txt` in
the filter directory. Tested on the login node with stand-ins (normal exit, hang, crash, hang while writing).

**Scaling test, `conv` (job 1054411, 2026-10-20, `slurm.cycle`'s shape and environment, nodes cirrus61–100).** Step 13's
00:30 analysis (3,492 obs) replayed; s, from `filter.log` (wall includes the exit guard's ~2-min wait):

| config | wall | read | H(x) | assim | ms/ob | rest | MaxRSS per rank | exit guard |
|---|---|---|---|---|---|---|---|---|
| 8x16 (step 13's) | 239 | 2 | 3 | 97 | 27.8 | 10 | 1.70 GB | fired |
| 40x16 | 163 | 2 | 3 | 18 | 5.2 | 9 | 0.51 GB | fired |
| 40x32 | 159 | 2 | 3 | 10 | 2.9 | 10 | 0.50 GB | fired |

- **Analyses bit-identical** in all three configs, to each other and to step 13's: the rank count doesn't change the
  results, so a new layout keeps runs comparable with step 13.
- **Speed:** with `slurm.cycle`'s shape the 8x16 loop is step 13's again (97 s against 96 s; 122 s in job 1054410
  with 128 × 1 per node and no `OMP_*`). 40x32 makes the loop ~10× faster and filter's own time ~25 s instead of ~112 s.
- **Exit hang in every config** (guard cancelled steps .0, .1, .2 after 121 s; outputs complete). Not in step 13
  (cirrus77–116, 10-02/03) with the same executable, inputs and environment. No library changes since then (Open MPI
  2021 build, UCX 1.14 2024-12, Slurm 25.11.8 and MLNX OFED 5.8 installed 09-04, same kernel); `slurmd` was restarted
  on all nodes 2026-10-14 09:20 (configuration change? unknown). All of today's configs included cirrus61–64, which
  are 512-GB nodes (cirrus57–64 and 121–128; the rest 256 GB); step 13 used only 256-GB nodes. Not established which,
  if any, of these is the cause.
- **Diagnostic (job 1054413, 2026-10-20):** the 8x16 replay with the 512-GB nodes excluded
  (`--exclude=cirrus[57-64,121-128]`; ran on cirrus49–56) **exited normally** (step COMPLETED, no guard), loop 96 s,
  analyses bit-identical. With step 13 (cirrus77–116, never hung) and job 1054411 (every config included cirrus61–64,
  every config hung), this points to the 512-GB nodes, though one clean run doesn't prove it. Job 1054411's test
  directory kept as `tests/filter_scaling/conv_202505200030_job1054411/`.

**Decisions (user, 2026-10-20) for runs 1–4, coded, not run:**
- **Filter on 40 × 32** (`FILTER_NODES=40`, `FILTER_TASKS_PER_NODE=32`, `experiment.sh` defaults, overridable from
  sbatch's environment; not in `settings.txt`, since the analyses don't depend on the layout). `prep_filter.sh` writes
  32 into `tasks_per_node`; `driver.sh` stops at the start if `FILTER_NODES` exceeds the job's nodes (so a cold start
  alone on fewer nodes needs `FILTER_NODES=<n>`), and logs the layout.
- **512-GB nodes excluded:** `#SBATCH --exclude=cirrus[57-64,121-128]` in `slurm.cycle` and `slurm.filter_scaling`.
- **Exit guard kept as a safety net, wait 30 s** (`FILTER_EXIT_GRACE`, was 120 s): normal exits take a few s after
  "Finished", and the guard still waits for 30 s without output-file changes.
- Still to do: the MRMS scaling test after run 1 (`SCALE_CASE=mrms SCALE_SRC=output_madis`), which gives the radar
  ms per ob for runs 3–4 at 40 × 32 and the search-box setting; `MRMS_INFLATION` for run 4.

**Run 1, first submission (job 1054633, 2026-10-21, cirrus65–104, all 256-GB nodes): stopped at the first analysis.**
The 00:00 cold start completed (136 s; `wrf.exe` 2:04–2:13 per member). At 00:15 the extraction worked
(`dart_d01.nc` has all 17 state fields), then `fill_inflation_restart` stopped in `static_init_model`: "inq_varid
REFL_10CM: NetCDF: Variable not found". DART's WRF `model_mod` uses filter's `wrfinput_d01` (= `GRID_FILE`, the mean
00Z `wrfinput`) not only for the static grid fields but as the template for every state variable's dimensions and
attributes (`add_domain`, `model_mod.f90:778`); `real.exe` writes no `REFL_10CM`. The other 16 state fields are in it
(checked for all three namelists, `input.nml.filter`, `_mrms`, `_joint`). filter itself and the MRMS scaling test
(same `GRID_FILE`) would have stopped the same way. **Fix (2026-10-21):** `scripts/da/make_grid_file.py` writes
`mean/dart_wrfinput_d01_2025-05-20_00_00_00` = the mean 00Z `wrfinput`, copied unchanged, plus `REFL_10CM` defined as
in the patched `wrfrst` (dimensions, type, attributes; filled with zeros, since only the shape is read); `GRID_FILE`
in `experiment.sh` points to it. Checked: all 198 original variables, global attributes and dimensions identical
to the mean `wrfinput`; `fill_inflation_restart` on the login node with run 1's `input.nml` and member 1's
`dart_d01.nc` finished, inflation 1.0 / sd 0.6 for all 17 state fields. Nothing in the restart files had been
touched (`prep_filter.sh` only reads them), so resubmitting the same command resumes run 1 at 00:15.

**To do after runs 3 or 4 (user, 2026-10-21): the cleaner fix, `REFL_10CM` from `real.exe`.** Runtime I/O can add it
to the main input stream: `+:i:0:REFL_10CM` (`frame/module_domain.F`, `modify_io_masks1`: type `i`, stream 0 = main
input), and `real.exe` applies `iofields_filename` on every write (`share/output_wrf.F:114`); `REFL_10CM` is allocated
in `real.exe` because `namelist.input.real` has `do_radar_ref = 1` (package `radar_refl`). Values are whatever
`real.exe` leaves in it (it computes no reflectivity); DART never reads them. Steps: (1) `config/iofields_real.txt`
with that line, `iofields_filename` in `config/namelist.input.real`, `make_mean_icbc.sh` links the file into its
work directory, so every mean `wrfinput` has `REFL_10CM` from the start (also for the 50-member setup); (2) keep the
current file as `mean/wrfinput_d01_2025-05-20_00_00_00.pre_refl` and rerun `real.exe` for 05-20 00Z only (hour 24,
`FIRST_HOUR=24 LAST_HOUR=24 sbatch slurm.make_mean_icbc`, ~3 min on 4 nodes; all 73 hours would take ~83 min and are
not needed: only 00Z is `GRID_FILE`); (3) check all 198 variables bit-identical to the old file, plus `REFL_10CM`
(`real.exe` was rebuilt 10-14, but only the restart I/O flag changed); (4) `GRID_FILE` back to the plain mean 00Z
`wrfinput`; delete `scripts/da/make_grid_file.py` and `mean/dart_wrfinput_d01_2025-05-20_00_00_00`; update this note
and the `CLAUDE.md` gotcha. Not during a run: every cycle's `prep_filter.sh` reads `GRID_FILE`.

**Run 1 `_madis` (jobs 1054633 + 1054795, 2026-10-21): passed.** All 4 analyses `complete`, `check_cycle` passed in
every cycle, no CFL lines, `driver: done`. Same obs as step 13 `_hph` (2,781 / 3,492 / 3,058 / 4,851), with the NCEP
METAR errors.
- **Exit hang on 256-GB nodes:** the guard fired at 00:30 (step 1054795.22, cancelled 30 s after "Finished",
  outputs complete); 00:15, 00:45 and 01:00 exited normally on the same nodes. This refutes the 512-GB-node
  explanation of 10-20. Side investigation handed off: `notes/handoffs/2026-10-21_filter_exit_hang.md`.
- **Same start as step 13:** the 00:15 priors of members 1 and 3 are bit-identical to `_hph`'s in all 17 common
  variables (so the patched `wrf.exe` and the new grid file change nothing before the first analysis).
- **What differs from `_hph` in the filter:** (a) the METAR errors (T2 1.26 K, wind 1.59 m/s, RH 0.059, against
  DART's); (b) the state list: QCLOUD `UPDATE`, QRAIN QSNOW QGRAUP `REFL_10CM` `NO_COPY_BACK` (and their clamps);
  (c) settings that act only on radar or mesonet obs, absent here (`microphysics_type` 5, `apply_ref_limit_to_fwd_op`,
  the `LAND_SFC_*` lists); (d) 40 × 32 ranks (bit-identical analyses, job 1054411). In DART's EAKF each state
  element is updated by regression on the observation's prior ensemble, the conventional forward operators read no
  hydrometeors, and inflation is per element, so the added `NO_COPY_BACK` fields should not change the analysis of
  the other variables (expected, not tested; a replay of 00:15 with run 1's namelist and `obs/` would show it).
  QCLOUD does matter from 00:30 on: its increment goes into the model.
- **00:15, mean increment RMS, `_hph` → run 1** (only the obs errors differ here): T2 0.127 → 0.259 K, Q2 9.5e-5 →
  2.5e-4, V10 0.154 → 0.32, U10 0.10 → 0.17 m/s, QVAPOR 4.1e-5 → 7.8e-5, THM 0.10 → 0.12 K, U 0.13 → 0.16 m/s, MU
  28.0 → 29.7 Pa, PSFC 26.6 → 28.3 Pa (altimeter error unchanged); QCLOUD 3.5e-6 (new). Posterior METAR T2 RMS
  0.95 → 0.81 K. Post-analysis |dpsfc/dt| (steps 2–4) higher than `_hph` (00:30: up to 305 against 257 hPa/3h),
  the same by minutes 5–15 (84–91); from these two runs the METAR errors and the QCLOUD insertion can't be told apart.
- **Cost, against step 13** (obs errors don't change it; the state list and layout do): srun 99–161 → 59–71 s (one
  hang: 92 s); assim 28 → 6.5 ms/ob (40 × 32 alone gave 2.9 ms/ob with step 13's state, job 1054411, so the 17-field
  state costs ~2.2× per ob); read 2 → 3–4 s and rest 10 → 18–20 s (more fields in and out); **prep 48–52 → 128–137 s**
  (`wrfrst_dart.py extract` of 6 more 3-D fields per member, now the largest part of the filter stage); update
  114–132 → 138–161 s (QCLOUD inserted too, bigger files); `check_cycle` ~33 → ~68 s. WRF per member unchanged
  (~120 s on contiguous nodes), but the member on the split node set cirrus1–4, 17, 50–52 took ~150 s in every cycle,
  and one member on cirrus18–25 took 209 s at 01:00, hence advance 151–211 s. Cycle total 553–635 s against 433–494.

**MRMS scaling test (job 1054799, 2026-10-21, cirrus1–4, 17–52, 9 min):** `SCALE_CASE=mrms SCALE_SRC=output_madis`,
the MRMS pass (`input.nml.filter_mrms`, no inflation) on run 1's 00:15 priors with `obs_madis_mrms/<t>/obs_seq.mrms`
(85,551 obs: 76,962 `RADAR_REFLECTIVITY`, 8,589 `RADAR_CLEARAIR_REFLECTIVITY`). Results in
`tests/filter_scaling/mrms_202505200015/`. s:

| config | wall | read | H(x) | assim | ms/ob | rest | exit guard |
|---|---|---|---|---|---|---|---|
| 40x32 | 101 | 3 | 9 | 19 | 0.22 | 25 | fired |
| 40x32:283x144 | 94 | 3 | 8 | 14 | 0.16 | 26 | fired |
| 40x64 | 125 | 4 | 9 | 23 | 0.27 | 25 | fired |
| 40x64:283x144 | 124 | 4 | 9 | 21 | 0.25 | 24 | fired |

- **The radar pass is cheap:** 0.22 ms per ob at 40 × 32, against 6.5 ms for a conventional ob in run 1 (cutoff
  0.001413 against 0.0235 rad: each ob touches far less state). Filter itself ~60–70 s per MRMS pass, plus the guard's
  30 s when it fires. The wall-time risk above is gone: runs 3 and 4 fit in `slurm.cycle`'s 2 h.
- **Search boxes ×4 (283 × 144):** observation loop −26 % (19 → 14 s), analyses bit-identical in all 5 members. Saves
  ~5 s per MRMS pass.
- **64 ranks per node is slower** than 32 (23 against 19 s; bit-identical). 40 × 32 stays.
- **Exit guard fired in all 4 configs**, on 256-GB nodes only.
- **Outlier check (`outlier_threshold = 3`) on the radar obs (first config):**

  | type | n | assimilated | QC 7 | prior obs−mean (assim.) | spread median (assim. / QC 7) | zero spread among QC 7 |
  |---|---|---|---|---|---|---|
  | `RADAR_REFLECTIVITY` | 76,962 | 52,273 | **24,688 (32 %)** | +3.9 dBZ (RMS 9.4) | 1.40 / 0.29 dBZ | 44 % |
  | `RADAR_CLEARAIR_REFLECTIVITY` | 8,589 | 8,409 | 180 (2 %) | −0.5 dBZ (RMS 2.3) | 0.00 / 2.20 dBZ | 0 % |

  The reflectivity outliers are almost all **observed echo where every member is (nearly) clear**: 87 % have obs >
  prior mean, prior mean median −9 dBZ (quartiles −10, −9, 0.3), obs median 14.7 dBZ (quartiles 12.0, 14.7, 21.2);
  15 % are obs ≥ 20 dBZ with prior mean < 10; 8 % both ≥ 20 dBZ (intensity); none is a spurious model echo (obs <
  10, prior ≥ 20). Obs error 5 dBZ (up to 10.4 near the boundary). The clear-air outliers are the opposite: model
  echo (prior mean median 15 dBZ) where MRMS is clear. With zero prior spread (44 % of the reflectivity outliers) an
  ob can't change the state whether it passes or not; with small spread its increment is small (Δx ∝ cov(x, y) /
  (σ_y² + σ_o²) × innovation). **HRRRDAS:** its EnKF has `sprd_tol = 1.e30` (`parm/hrrrdas/hrrrdas_enkf_wrf_namelist.sh`),
  i.e. no EnKF outlier check for any type; the GSI observer's dBZ gross check is set in its convinfo, which is not
  public. In DART a per-type threshold needs `enable_special_outlier_code` and code in `failed_outlier`
  (`quality_control_mod.f90`); in a two-pass run the MRMS pass has its own `&quality_control_nml`
  (`input.nml.filter_mrms`), in one pass (`input.nml.filter_joint`) only the special code can separate the types.

**Decisions (user, 2026-10-21) for runs 3–4:**
1. **Search boxes 283 × 144** in `input.nml.filter_mrms` and `input.nml.filter_joint` (done; `input.nml.filter` keeps
   71 × 36).
2. **`outlier_threshold = 3` kept for all types**, radar included: no code change, one- and two-pass runs stay
   comparable, and most of what it rejects can't act (zero spread). Watch the QC-7 fraction of the radar types over
   the cycles as hydrometeor spread builds; a radar threshold off (or ~5) is a later variant.
3. **Run 4: `MRMS_INFLATION=both`**; the details (`MRMS_PASS2_DAMPING`, `INF_DAMPING`, flavor) to be decided when
   run 4 comes up.
4. **Impact table:** conventional → `QTY_RADAR_REFLECTIVITY` stays 0 (as HRRRDAS; `config/obs_impact_joint.txt`).
5. No `--time` change for runs 3–4: the MRMS pass costs ~1 min of filter per cycle.

**Run 2 `_meso_a` (job 1054801, 2026-10-21, cirrus1–4, 17–52, 44 min): passed.** Observation set
`obs_meso_a_calmkeep/` (MADIS + mesonet option a, calm winds kept). All 4 analyses `complete`, `check_cycle` passed,
no CFL lines, `driver: done`. **Exit guard fired in all 4 cycles** (since 10-20: 13 hangs in 17 multi-node filter
runs).
- **Mesonet obs per cycle:** `LAND_SFC_TEMPERATURE` 1,663–1,799, `_SPECIFIC_HUMIDITY` 1,002–1,035 (4–7 outliers),
  `_U/_V_WIND_COMPONENT` 427–537 each, all assimilated; `LAND_SFC_ALTIMETER` 1,051–1,082 evaluated only (38–75
  outliers). Obs−prior biases: T ≈ 0 (−0.10 to −0.02 K), q +0.44 to +0.95 g/kg (obs moister), u +0.35 to +0.63 m/s,
  **v −0.93 to −1.19 m/s**; prior RMS T 1.2 K, u 1.6–1.8, v 2.1–2.3 m/s, q 1.3–1.7 g/kg (errors 3.0 K, 3.0 m/s,
  RH 0.07). The posterior fits to the mesonet obs improve little (e.g. T 1.21 → 1.11 K at 00:15, v bias kept),
  as expected with errors of 3 K / 3 m/s against ~0.4–0.8 prior spread.
- **METAR fits (assimilated in both runs):** similar to run 1 (01:00 T2 posterior 1.08 against 1.05 K); the prior
  2-m T spread is lower (01:00: 0.37 against 0.50 K).
- **Post-analysis |dpsfc/dt| (max of steps 2–4, hPa/3h, per cycle 00:15–01:00):** `_hph` 171 / 257 / 217 / 310,
  run 1 212 / 305 / 292 / 429, run 2 261 / 374 / 332 / 452; minutes 5–15 the same in all three (80–92). The
  initial adjustment grows with the surface-obs impact (smaller METAR errors, then the mesonet); it dies out within
  ~5 min in every cycle so far.
- **Cost against run 1:** 2.2–2.7× the obs (7,543–9,783, including ~1,060 evaluated altimeters), assim 43–56 s
  (5.7 ms/ob, about run 1's per ob), filter srun ~85–100 s without the guard's wait; prep, update and advance as in
  run 1. Cycle total 611–631 s.
