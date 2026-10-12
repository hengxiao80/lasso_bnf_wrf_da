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

**Mesonet.** HRRRDAS copies the provider list (`hrrr_gsd_sfcobs_provider.txt`) but its copy of the station use-list is commented out (`exhrrr_analysis.sh:249`); deterministic HRRR copies both (`scripts/conus/exhrrr_analysis.sh:235–236`). Contents of both are in the fix directory, not public.

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

**MRMS preprocessing (`scripts/hrrrdas/exhrrr_prep_radar.sh`, `sorc/hrrr_process_mosaic.fd/process_NSSL_mosaic_to_dart_and_netcdf.f90`).** Input: the 33 `MergedReflectivityQC` levels (0.5–19 km). Mapped onto the model grid (`geo_em.d01.nc`), max over the tile overlap. Then, per the namelist HRRRDAS uses:
- precipitation obs: Z ≥ 10 dBZ, every 3rd MRMS level (`precip_dbz_vert_skip = 2`: 0.5, 1.25, 2.0, 2.75, 4.0, 5.5, 7.0, 8.5, 11.0 km), horizontal skip 1 grid point;
- clear-air obs: Z ≤ 0 dBZ, set to −10 dBZ, only at levels 13 and 22 (**4.0 and 8.5 km**; `clear_air_dbz_vert_skip = -1` is a hard-coded special case), horizontal skip 5 grid points;
- 0 < Z < 10 dBZ: not used; nothing above 11 km (`max_height = 11001`); no obs in the outermost grid row;
- error sd 5 dBZ for both.

The same program **writes a DART `obs_seq` file** (`output_dart = .true.`; `RADAR_REFLECTIVITY` and `RADAR_CLEARAIR_REFLECTIVITY`, ASCII, kinds 12/13 from its own `DART.f90`), a remnant of HRRRDAS's DART heritage. GSI reads the netCDF version (`Gridded_ref.nc` → `dbzobs.nc`).

## 2. What our `filter` can already take

- **Build.** `filter` (2026-10-01 22:20, `quickbuild_fp_precise.log`) was preprocessed with `obs_def_reanalysis_bufr, radar, metar, dew_point, rel_humidity, altimeter, gps, vortex, gts`. So `LAND_SFC_*` (mesonet), `SAT_U/V_WIND_COMPONENT`, `VADWND_*`, `PROFILER_*`, `GPS_PRECIPITABLE_WATER`, `RADAR_REFLECTIVITY`, `RADAR_CLEARAIR_REFLECTIVITY` and `DOPPLER_RADIAL_VELOCITY` are all compiled in.
- **Gotcha.** The generated `obs_kind_mod.f90`/`obs_def_mod.f90` are shared files; the MADIS converter build at 22:22 overwrote them with its own (no radar) list. They don't show what `filter` contains; `quickbuild.sh` reruns `preprocess` for its own list, so rebuilds are fine. (`strings`/`grep -a` on the binary doesn't find type names either, even `ACARS_SPECIFIC_HUMIDITY`.)
- **Mesonet converter** (`convert_madis_mesonet`, built) writes `LAND_SFC_{U,V}_WIND_COMPONENT`, `LAND_SFC_TEMPERATURE`, `LAND_SFC_SPECIFIC_HUMIDITY`, `LAND_SFC_ALTIMETER`. No other family in our pipeline uses `LAND_SFC_*`, so mesonet gets its own errors, localization and diagnostics.
- **Reflectivity.** `obs_def_radar_mod` with `microphysics_type = 5` interpolates `REFL_10CM` from the state (`QTY_RADAR_REFLECTIVITY`), the same H(x) as HRRRDAS. Our WRF runs Thompson aerosol-aware with `do_radar_ref = 1`. `REFL_10CM` is in our 15-min `wrfout` but **not in `wrfrst`**, which `wrfrst_dart.py extract` reads; it would come from the member's `wrfout` at the same time (or be added to the restart stream). It is a diagnostic: `NO_COPY_BACK`, WRF recomputes it. The hydrometeors (QCLOUD QRAIN QICE QSNOW QGRAUP QNICE QNRAIN) are in `wrfrst`.
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

**Decision and change (user, 2026-10-03): METAR errors set to NCEP values before the extension.** T2 1.26 K (NAM), 10-m wind 1.59 m/s (RAP), RH 0.059 (RAP), altimeter 1.0 hPa (unchanged), through a local patch to the METAR converter (`patches/dart_7bbd35a09_madis_metar_obs_errors.patch`, `patches/README.md`). All hourly METAR files of 05-20/05-21 are reconverted; the pilot's originals are in `obs/obs_seq_madis/metar_v1_dart_land_errors/`. The 1-hour pilot (cycles 00:15–01:00) ran with the old errors; the extension (01:15 on) uses the new ones. Radiosonde, ACARS and mesonet errors are DART's defaults.

**Future options for observation errors (recorded 2026-10-03, user; not done yet).**
1. **Height-dependent humidity errors.** Ours are constant (RH 0.2 for radiosondes and ACARS; `rawin_rel_hum_error`, `acars_rel_hum_error` in `ncep_obs_err_mod.f90`). RAP's grow with height: radiosonde (type 120) 7.3 % RH at 1000 hPa, 11.2 % at 850, 16.0 % at 500, 18.8 % at 250; ACARS (133) 16.6–19.7 %. The functions already receive the level pressure, so the change is a 33-level table interpolated in pressure, as `rawin_temp_error` already does (patch, rebuild, reconvert). ACARS wind is constant in both systems (ours 2.5, RAP 2.32 m/s).
2. **Per-type rescaling after conversion, instead of Fortran patches.** A small step after `convert_madis_hour.sh` (or in `make_cycle_obs.sh` before screening) that rewrites each observation's error variance from a config file: a factor or a pressure profile per type. This allows tuning many types without rebuilding converters. It must run before `wrf_dart_obs_preprocess`, so the boundary inflation is applied to the new errors.
3. **Evidence needed first.** The pilot's 4 analyses had no radiosondes, and its statistics pool all levels. Bin `innovation_stats.py` by pressure (and time of day) on the extension.

**ACARS humidity errors look larger than the data support** (ours 20 % RH; pilot implied/Desroziers 12–14 %; RAP 17–20 %). Weak evidence so far: 319 obs in one hour, pooled over levels, no instrument QC on WVSS (§2.13 of `wrf_dart_tutorial_adaptation.md`). Tightening to 14 % would double the weight of each report (variance ×2), a much smaller change than METAR's (×6–11 in variance). Proposed (not yet decided): keep 20 % for the extension, then decide from its pressure-binned statistics; a change would go through option 1 or 2 above.

## 6. Proposed order

1. **Mesonet**: data, converter and `filter` are ready; the work is QC/selection and thinning.
2. **MRMS reflectivity**: everything public, and the HRRR converter exists. Needs the state changes (Q8) and enough hydrometeor spread.
3. **Radar radial velocity** (§4): shares the `REFL_10CM`-in-state work with MRMS; the pyOPAWS setup and a one-volume test can run alongside steps 1–2.
4. **GOES satellite winds**: needs a new reader.
5. VAD winds from `prep48h`: small patches, but only 6-hourly files; overlaps with radial velocity.
