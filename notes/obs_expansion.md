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
6. **Data.** All 72 hourly files of 05-19..05-21 are on disk (`obs/madis/mesonet/`, 2.1 GB, downloaded 2026-09-25 with the other MADIS families; `wrf_dart_tutorial_adaptation.md` 2.13). To add to `DATA_SOURCES.md` with the other MADIS families.

### 7.3 How HRRR, HRRRDAS and RRFS select mesonet observations (checked 2026-10-13)

Moved to `mesonet_station_selection.md`: reference repos (`HRRR`, `GSI`, `RRFSv1`, `RRFSv2`, `GSI-fix_subset`), every list file found, GSI's selection logic and a per-system summary. In short: HRRR, HRRRDAS and RRFS v1 run the same GSI code (GSD method, `i_gsdsfc_uselist = 1`, `i_gsdqc = 2`); a report is used if its provider is on P4 (all variables) or, in deterministic HRRR and RRFS v1 only, its station is flagged for that variable on S5, GSL's daily station list (T, q, wind; never pressure). HRRRDAS has no station list, so P4 providers only. RRFS v2 restricts only wind (P1, 20 providers, + S2, 4,214 stations) and takes T, q and pressure from all providers. P4 is 9 regional networks (public in the HRRRv3 and RRFS v1 git history), so almost all mesonet comes in through S5; S5 is not public (dated copies S6, 2017, and S1, 2026, are).

**Calm winds pass MADIS QC and are common**: of the QCR = 0 wind reports in the box, 2,342 of 17,742 are calm at 18Z (APRSWXNET 2,185 of 13,373) and 7,589 of 17,932 at 06Z, 01 CDT (APRSWXNET 6,561 of 13,418, 49 %; MesoWest 725 of 3,146). GSI's `i_gsdqc = 2` rejects them all.
