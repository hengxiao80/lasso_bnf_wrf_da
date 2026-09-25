# HRRRv4 observations and WRF-DART implementation reference

**Version:** 2026-09-23  
**Scope:** Operational HRRRv4, with emphasis on the CONUS HRRRDAS + deterministic HRRR analysis cycle and on reproducible use in WRF-DART.

## Bottom line

HRRRv4 did **directly assimilate NEXRAD Level-II radial velocity in both the 36-member HRRRDAS and the deterministic HRRR GSI analysis**. In the operational interface the radial-wind observation type is `rw`, supplied through `l2rwbufr`. This is distinct from:

- MRMS three-dimensional reflectivity, which was assimilated directly by the HRRRDAS EnKF; and
- MRMS reflectivity plus lightning, which affected the deterministic HRRR through radar latent heating and stratiform cloud/hydrometeor initialization rather than an ordinary reflectivity term in the deterministic GSI cost function.

The practical WRF-DART routes are:

- conventional observations: use the maintained MADIS converters where possible, or the DART PREPBUFR path after carefully validating type/QC mappings;
- raw radial velocity and reflectivity: download NEXRAD Level II and use pyOPAWS plus DART's radar forward operators;
- MRMS reflectivity: write a GRIB2/NetCDF-to-`obs_seq` converter and use DART's reflectivity operator;
- GPS precipitable water and tropical-cyclone vortex observations: maintained DART converters exist;
- lightning and cloud analysis inputs: no turnkey WRF-DART equivalent; reproduce the HRRR nonvariational method member by member or develop and validate custom observation operators.

## Repository provenance and commit check

The earlier **HRRRv4 Radar Assimilation** audit used this exact NOAA-EMC/HRRR snapshot as its main reference:

- **Primary reference snapshot:** [`44728d00f2ea7a09cd79cb5274484ab84e1dfc38`](https://github.com/NOAA-EMC/HRRR/commit/44728d00f2ea7a09cd79cb5274484ab84e1dfc38)
- **Commit time recorded in that audit:** 2022-05-24 18:27 UTC
- **Why this snapshot:** it is contemporaneous with the 2022 HRRRv4 system papers.

It was compared with the later repository state synchronized from the operational `hrrr.v4.1.20` directory:

- **Later comparison snapshot:** [`40ee6058c2fc6624cbfbbe8cf1c20c59e6a45827`](https://github.com/NOAA-EMC/HRRR/commit/40ee6058c2fc6624cbfbbe8cf1c20c59e6a45827)
- **Commit time recorded in that audit:** 2026-05-01 14:08:25 UTC
- **Commit message:** `Sync changes from NCO's hrrr.v4.1.20 operational directory.`

The audit found no scientifically material change between those snapshots in the radar-data-assimilation paths relevant here. The one noteworthy code change was a 2024 robustness fix to the Level-II reader, commit [`85e21fa324d0f700b2a30d60fa8fadf7f6e5e659`](https://github.com/NOAA-EMC/HRRR/commit/85e21fa324d0f700b2a30d60fa8fadf7f6e5e659): it increased the supported radar-site count, repaired site indexing, and changed file-opening logic after an operational failure, but did not change the scientific superob geometry, VAD consistency QC, radial-velocity operator, or EnKF methodology. Files checked included the CONUS and HRRRDAS analysis scripts and GSI parameter files, `read_l2bufr_mod.f90`, `read_radar.f90`, `setuprw.f90`, `intrw.f90`, `stprw.f90`, `m_rwNode.F90`, `read_obs.F90`, `setuprhsall.F90`, and the HRRRDAS conventional-observation reader.

**Answer to the commit question:** my immediately preceding reply cited files on the moving `develop` branch, so it was **not demonstrably the same commit**. I have now checked the saved audit from the earlier chat directly. This document uses the same main reference, `44728d00…`, and the same later comparison, `40ee6058…`. Direct remote re-fetch of the old Git objects was unavailable in this session, so the comparison is confirmed against that retained audit artifact rather than a new byte-for-byte clone. The public HRRRv4 papers and the operational v4.1.13 release note independently corroborate the `l2rwbufr`/`read_l2bufr_mod.f90` radial-wind path.

## What “assimilated by HRRRv4” means

There were several distinct paths. Treating all of them as “GSI observations” obscures important differences.

1. **HRRRDAS EnKF:** hourly conventional observations, Level-II radial velocity, and MRMS reflectivity updated the 36-member ensemble. Cloud clearing was also applied member by member.
2. **Deterministic HRRR GSI:** conventional observations and Level-II radial velocity entered the hourly 3-km hybrid 3DEnVar analysis. HRRRDAS supplied the flow-dependent covariance.
3. **Deterministic nonvariational initialization:** MRMS reflectivity and NLDN lightning drove the 1-hour preforecast latent-heating procedure; METAR and satellite cloud information drove SCHDA/cloud clearing and building.
4. **Parent/global inheritance:** the HRRR first guess and boundaries inherited information already assimilated by RAP/GDAS. That indirect information is not counted as a direct HRRR observation below.
5. **Surface, lake, and smoke updates:** several analyzed or remotely sensed datasets updated lower-boundary or smoke states outside the atmospheric EnKF/3DEnVar observation update.

The [HRRRv4 system paper](https://repository.library.noaa.gov/view/noaa/53029/noaa_53029_DS1.pdf) says HRRR used the RAP conventional-observation set, with satellite radiances excluded from the CONUS HRRR analysis, and describes the special radar, lightning, cloud, land, lake, and smoke paths. The [HRRRDAS technical description](https://rapidrefresh.noaa.gov/internal/pdfs/2020_Spring_Experiment_HRRRE_Documentation.pdf) documents the PREPBUFR/Langley/MRMS inputs and the staged EnKF updates. The older [RAP system paper](https://journals.ametsoc.org/view/journals/mwre/144/4/mwr-d-15-0242.1.xml) supplies the detailed conventional-observation inventory inherited by HRRR.

## Complete direct and special-input inventory

“Public source” identifies a scientifically usable archive. It is not always the exact operational BUFR file that NCEP delivered to HRRR. Exact operational replay requires the original dump files, tables, QC, thinning, and observation errors; those are not preserved together in a single public HRRRv4 observation archive.

### Conventional and direct observations

| Observation family | Variables used by HRRRv4 | HRRRv4 path | Practical public source | WRF-DART route | Readiness |
|---|---|---|---|---|---|
| Radiosondes, dropsondes, and pibals | Temperature, humidity, wind, pressure/geopotential; pibal wind | Conventional `PREPBUFR`; HRRRDAS EnKF and deterministic GSI | [NCAR GDEX d337000 PREPBUFR](https://gdex.ucar.edu/datasets/d337000/), [NOAA MADIS](https://madis.ncep.noaa.gov/) | `convert_madis_rawin`, or DART's [NCEP PREPBUFR converter](https://docs.dart.ucar.edu/en/stable/observations/obs_converters/NCEP/prep_bufr/prep_bufr.html); select matching types and retain defensible QC | **Stock** |
| Aircraft: AMDAR/ACARS/MDCRS and WVSS | Wind, temperature; water vapor where supplied | Conventional `PREPBUFR`; both analysis systems | GDEX PREPBUFR (some aircraft reports have access restrictions) or MADIS aircraft files | `convert_madis_acars`, or PREPBUFR-to-DART | **Stock**, subject to data licensing |
| METAR/aviation surface | Temperature, moisture/dewpoint, wind, pressure/altimeter; clouds, ceiling, visibility, and present weather | Thermodynamic/wind/pressure fields in EnKF/GSI; cloud/visibility/weather also used by nonvariational cloud analysis | [MADIS](https://madis.ncep.noaa.gov/) or GDEX PREPBUFR | `convert_madis_metar` for ordinary state variables. Ceiling/visibility/cloud categories require a custom operator or external cloud-analysis step | **Stock** for conventional fields; **custom/external** for cloud fields |
| Mesonet surface | Temperature, moisture, wind, and accepted pressure reports | Conventional `PREPBUFR`; both analysis systems, with surface-elevation adjustment and PBL pseudo-innovations | MADIS mesonet or GDEX PREPBUFR | `convert_madis_mesonet`; apply network-specific QC, duplicate removal, representativeness errors, and terrain screening | **Stock** |
| Marine surface: buoys and ships | Wind, pressure; temperature/moisture where present and accepted | Conventional `PREPBUFR`; both analysis systems | MADIS marine or GDEX PREPBUFR | `convert_madis_marine`, or supported PREPBUFR types | **Stock** |
| 915-MHz boundary-layer profilers/RASS | Wind and virtual temperature | Conventional observation path | MADIS profiler or GDEX PREPBUFR | `convert_madis_profiler`; confirm height, virtual-temperature, and QC conventions | **Stock** |
| WSR-88D VAD wind profiles | Horizontal wind profiles derived from radar | Conventional observation path, separate from raw radial velocity | GDEX PREPBUFR includes U.S. radar-derived winds; current RAP PREPBUFR may also contain them | DART's distributed PREPBUFR decoder does not cover every PREPBUFR type. Decode VAD BUFR explicitly and map to profile U/V observations, or extend the converter | **Custom/validate** |
| **WSR-88D Level-II radial velocity** | Doppler radial velocity | **Direct in HRRRDAS EnKF and direct in deterministic HRRR GSI**; operational type `rw`, input `l2rwbufr` | [NEXRAD Level II open archive](https://registry.opendata.aws/noaa-nexrad/) (`s3://unidata-nexrad-level2/`); NCEI Level II is another route | Use [pyOPAWS and the DART radar converter](https://docs.dart.ucar.edu/en/stable/observations/obs_converters/radar/README.html). In WRF-DART, expose reflectivity and terminal fall speed to the state/diagnostic interface, handle velocity dealiasing/range folding, and use radar-specific localization | **Supported, with WRF setup work** |
| Satellite atmospheric motion vectors (AMVs/cloud-drift winds) | Wind, with assigned pressure/height | Conventional observation path | MADIS satellite winds, GDEX PREPBUFR, or GOES products from [NOAA Open Data Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination) | `convert_madis_satwnd`, or supported PREPBUFR satellite-wind types | **Stock** |
| Ground-based GPS/GNSS precipitable water | Column precipitable water | Conventional humidity observation | MADIS/SuomiNet holdings; historical reports can also occur in NCEP observation products | DART's [GPSPW converter](https://docs.dart.ucar.edu/en/stable/observations/obs_converters/GPSPW/README.html) | **Stock** |
| Satellite ocean-surface vector winds | Surface wind over water; WindSat is named in the RAP reference-era inventory | RAP conventional set inherited by HRRR where observations fall in-domain and pass QC | GDEX PREPBUFR; mission products through NOAA CLASS or the relevant satellite archive | Use a custom input converter mapped to DART ocean-surface U/V quantities; the distributed PREPBUFR path is not turnkey for every scatterometer type | **Custom/validate** |
| TCVitals | Tropical-cyclone center location and minimum sea-level pressure | New in RAPv5/HRRRv4; deterministic vortex constraint where a storm is present | [NHC ATCF archive](https://ftp.nhc.noaa.gov/atcf/archive/) (b-decks provide an accessible analogue to the operational vitals) | DART's [`tc_to_obs`](https://docs.dart.ucar.edu/en/stable/observations/obs_converters/tropical_cyclone/tc_to_obs.html) creates storm-center, minimum-pressure, and maximum-wind observations; WRF has the supported vortex forward operator | **Stock**, but tune errors |
| Satellite radiances: polar microwave/IR and geostationary radiances | Brightness temperatures/radiances | Used by RAP and by HRRR-Alaska; **not directly assimilated in the CONUS HRRRv4 GSI analysis** | NOAA [CLASS](https://www.class.noaa.gov/) and mission-specific NOAA/NASA archives | DART supports radiance assimilation through [RTTOV](https://docs.dart.ucar.edu/en/wrf-unified/guide/Radiance_support.html), but instrument/channel QC, bias correction, clouds, thinning, and correlated errors make this an advanced project | **Advanced; omit for a CONUS HRRR-like first implementation** |

### Radar, lightning, and cloud inputs with special treatment

| Observation/input | Variables or information | HRRRv4 path | Practical public source | WRF-DART route | Readiness |
|---|---|---|---|---|---|
| **MRMS 3-D reflectivity mosaic**, including precipitation and no-precipitation information | Reflectivity; clear-air/no-echo constraints | HRRRDAS: direct EnKF reflectivity update after strong horizontal/vertical thinning. Deterministic HRRR: latent-heating preforecast and limited SCHDA hydrometeor building/clearing, not an ordinary GSI reflectivity cost term | [NOAA MRMS open archive](https://registry.opendata.aws/noaa-mrms-pds/) (`s3://noaa-mrms-pds/`); check product/date retention | Convert each 3-D grid point or superob to DART radar reflectivity observations. Preserve vertical coordinates and explicit no-echo observations. Use the DART reflectivity operator, radar-specific localization, and strong thinning | **Custom converter; existing forward operator** |
| Vaisala NLDN lightning | Flash information converted to a reflectivity/latent-heating proxy | Combined with MRMS at four 15-min times during the deterministic 1-h preforecast; not a direct GSI flash-rate update | Exact NLDN data require a Vaisala license; see the [Vaisala lightning-data API](https://ltg.vaisala.com/reprocessed/nldn/v3/api-docs). GOES GLM is open but is **not the same observing system** | No turnkey stock equivalent. Either apply an HRRR-like latent-heating adjustment to every ensemble member before `filter`, or implement and validate a flash-rate/proxy-reflectivity operator | **External/custom** |
| GOES/SatCORPS cloud-top pressure, cloud-top temperature, and cloud fraction | Cloud-top height/pressure/temperature and cloud coverage/absence | Nonvariational SCHDA and cloud clearing/building in deterministic HRRR and member-wise HRRRDAS observer workflow | Operational HRRR used NASA Langley-processed BUFR. Public GOES ABI L2 cloud products are available through [NOAA's GOES open-data program](https://registry.opendata.aws/noaa-goes/), but are not byte-identical to the Langley feed | Best HRRR analogue is an external, member-wise cloud analysis. Direct EnKF use requires new observation definitions/operators and careful treatment of categorical cloud/no-cloud information | **External/custom** |
| METAR ceiling, cloud fraction, visibility, present weather/precipitation category | Cloud layers or their absence; near-surface visibility/weather constraints | Nonvariational SCHDA/cloud clearing and building, in addition to the conventional METAR state variables | MADIS METAR | Retain the conventional METAR fields via `convert_madis_metar`; implement the cloud analysis separately or add new operators | **External/custom for clouds** |

## Inputs that affected HRRRv4 but are not independent atmospheric EnKF/GSI observations

These belong in a complete reproduction plan, but should not be counted as another set of ordinary observations in DART `filter`.

| Input/update | HRRRv4 use | Public source or analogue | WRF-DART treatment |
|---|---|---|---|
| Surface-based PBL pseudo-innovations | Vertically project information from accepted surface observations through the PBL | Derived from the surface observations above | Do not ingest as a second independent dataset unless you reproduce HRRR's correlated-error treatment; otherwise this double-counts the same report |
| Soil temperature and moisture adjustment | Derived from lowest-model-level temperature and relative-humidity analysis increments | No separate observed soil dataset | Apply an external member-wise land-state adjustment only if intentionally reproducing HRRR; it is not a new obs stream |
| VIIRS greenness vegetation fraction | Daily land-surface greenness update | [NOAA VIIRS GVF catalog entry](https://catalog.data.gov/dataset/noaa-jpss-visible-infrared-imaging-radiometer-suite-viirs-global-and-regional-level-3-green-veg2) | Update WRF/land-surface fields outside atmospheric DART filtering, with consistent cycling |
| Daily SST analysis | Lower boundary; RTG SST, changing to a GDAS SST analysis in February 2020 | [NCEP SST products](https://polar.ncep.noaa.gov/sst/ophi/verification.shtml) | Prescribe consistently for all members or perturb deliberately; do not treat as an atmospheric scalar observation |
| IMS snow/ice analysis | Daily snow-cover lower boundary | [NOAA/NESDIS IMS at NSIDC](https://nsidc.org/data/g02156/versions/1) | External land/snow initialization |
| Great Lakes FVCOM lake temperature and fractional ice | HRRRv4 lake initial conditions | [NOAA CO-OPS operational forecast systems](https://www.ncei.noaa.gov/products/weather-climate-models/co-ops-operational-forecast) | External lake-state initialization; outside the ordinary WRF-DART atmospheric state unless the lake model is explicitly coupled into DART |
| VIIRS and MODIS fire hotspots plus fire radiative power | Fire emissions and smoke initialization | [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/download/) | External emissions/smoke initialization or a purpose-built coupled composition DA system |
| RAP/GDAS analyses and forecasts | HRRR initial/boundary conditions and HRRRDAS perturbations; they carry the influence of many additional observations | NCEP model archives | These are priors/boundaries, not direct HRRR observations. Do not list every GDAS observation as though HRRR ingested it directly |

## WRF-DART implementation notes

### 1. Conventional observations

For the cleanest first implementation, use MADIS converters for radiosonde, aircraft, METAR, mesonet, marine, profiler, and satellite-wind data. DART documents those converters explicitly. Merge their output with `obs_sequence_tool`, remove duplicates across feeds, and use `wrf_dart_obs_preprocess` to enforce the domain, boundary buffer, and vertical-coordinate checks.

PREPBUFR is attractive because it resembles the operational HRRR conventional feed, but DART's distributed decoder is not a universal PREPBUFR reader. Its documentation says additional types require code changes and detailed PREPBUFR knowledge. Validate at least:

- mnemonic/type mapping and units;
- which event-stack value and NCEP QC mark were selected;
- observation time relative to the cycling window;
- elevation and pressure/height handling;
- aircraft duplication among AMDAR/ACARS/MDCRS sources; and
- overlap between MADIS and PREPBUFR.

### 2. Radial velocity and reflectivity

The maintained DART radar route is NEXRAD Level II → pyOPAWS → separate radial-velocity and reflectivity `obs_seq` files. DART's WRF guidance requires model-equivalent reflectivity and a terminal-fall-speed diagnostic for radial velocity. It also recommends a radar-specific localization scale of roughly 12–24 km and provides an optional range-folding-aware build.

For a convection-permitting BNF-style domain around 2.5 km grid spacing, a reasonable starting experiment is:

- thin storm radar observations to about 5 km horizontally, with additional vertical thinning;
- thin no-echo/clear-air reflectivity more aggressively, roughly 10–12 km;
- begin with 12–24 km radar localization, then tune using innovation and increment diagnostics;
- assimilate reflectivity and radial velocity in distinct passes if that simplifies QC/localization/state choices; and
- explicitly test sensitivity to hydrometeor state variables and to the Thompson terminal-velocity implementation.

These are starting values, not HRRR's exact settings transplanted to another ensemble size/domain. HRRRDAS documentation reports 6-km precipitation-region and 12-km nonprecipitation-region reflectivity thinning and an 18-km full localization width for reflectivity.

### 3. MRMS reflectivity

MRMS is already mosaicked and quality controlled differently from raw radar volumes. Do not run it through pyOPAWS as though it were Level II. A converter should:

1. read the chosen three-dimensional MRMS reflectivity product and its valid time;
2. retain the physical height of every accepted datum;
3. create DART reflectivity observations with documented errors and QC;
4. encode no-precipitation information explicitly rather than silently discarding missing/low values;
5. superob/thin before filtering; and
6. keep MRMS reflectivity separate from Level-II reflectivity to prevent duplicate use of the same radar information.

### 4. Avoiding correlated and duplicated information

- Do not assimilate VAD winds and all underlying raw radial velocities as though they were independent. Either omit VAD when Level-II radial velocity is used or inflate errors/thin with a defensible correlation strategy.
- Do not combine MADIS and PREPBUFR versions of the same METAR, aircraft, radiosonde, or mesonet report without deduplication.
- Do not combine MRMS and Level-II reflectivity at the same place/time without an explicit choice about which product owns the information.
- If the ensemble is initialized from an HRRR analysis, those same valid-time observations have already influenced the prior. Start cycling with later observations, or design a controlled reanalysis experiment; simply re-assimilating the initialization-time observations double counts them.
- HRRR surface PBL pseudo-innovations are derived from surface reports, not independent observations.

## Recommended implementation order

1. **Conventional core:** radiosonde, aircraft, METAR, mesonet, marine, profiler, AMV, and GPS PW.
2. **Raw radar wind:** Level-II radial velocity with pyOPAWS, fall-speed support, radar QC, thinning, and radar localization.
3. **Raw reflectivity:** use the same Level-II volumes first because the DART route is maintained and provenance is clear.
4. **MRMS reflectivity:** add only after a dedicated converter and duplicate-control strategy are tested.
5. **TCVitals:** add for tropical-cyclone cases.
6. **Cloud and lightning initialization:** reproduce member-wise only after the conventional/radar cycling system is stable.
7. **Radiances:** consider only for Alaska or a deliberately broader experiment; they were not direct CONUS HRRRv4 observations.

## Evidence map for the radial-velocity correction

At the pinned operational snapshot, the decisive chain is:

- CONUS and HRRRDAS analysis scripts stage/link `l2rwbufr`;
- their GSI parameter/namelist files enable the `rw` observation type;
- `read_l2bufr_mod.f90` reads Level-II radial-wind BUFR;
- `setuprw.f90`, `intrw.f90`, and `stprw.f90` implement radial-wind setup, interpolation/adjoint, and observation handling in GSI;
- HRRRDAS EnKF radar-observation modules carry the `rw` observation into the ensemble update; and
- deterministic HRRR GSI includes the same radial-wind type in its analysis.

This code evidence is more specific than summary tables in the papers. In particular, Table 5 of the HRRR system paper is explicitly a summary of **conventional and MRMS reflectivity** assimilation; it is not an exhaustive list of every configured observation type. The HRRRDAS overview likewise highlights the new MRMS-reflectivity workflow and does not negate the configured `rw` path.

## Primary references and data/converter links

- Dowell et al. (2022), [*The High-Resolution Rapid Refresh (HRRR): An Hourly Updating Convection-Allowing Forecast Model. Part I*](https://repository.library.noaa.gov/view/noaa/53029/noaa_53029_DS1.pdf).
- Dowell (2020), [*HRRR Data-Assimilation System (HRRRDAS) and HRRRE Forecasts*](https://rapidrefresh.noaa.gov/internal/pdfs/2020_Spring_Experiment_HRRRE_Documentation.pdf).
- Benjamin et al. (2016), [*A North American Hourly Assimilation and Model Forecast Cycle: The Rapid Refresh*](https://journals.ametsoc.org/view/journals/mwre/144/4/mwr-d-15-0242.1.xml).
- Benjamin et al. (2021), [*Stratiform Cloud-Hydrometeor Assimilation for HRRR and RAP*](https://repository.library.noaa.gov/view/noaa/31766/noaa_31766_DS1.pdf).
- Weygandt et al. (2022), [radar-reflectivity latent-heating initialization paper](https://repository.library.noaa.gov/view/noaa/55036).
- NOAA-EMC HRRR [repository](https://github.com/NOAA-EMC/HRRR) and [v4.1.13 release note](https://github.com/NOAA-EMC/HRRR/blob/develop/release_notes_v4.1.13), which records an operational `l2rwbufr`/`read_l2bufr_mod.f90` fix.
- [GDEX d337000 NCEP ADP PREPBUFR](https://gdex.ucar.edu/datasets/d337000/): surface, marine, radiosonde/pibal, aircraft, profiler/radar-derived wind, ocean wind, and satellite wind holdings.
- [DART MADIS converters](https://docs.dart.ucar.edu/en/stable/observations/obs_converters/MADIS/MADIS.html).
- [DART NCEP PREPBUFR converter](https://docs.dart.ucar.edu/en/stable/observations/obs_converters/NCEP/prep_bufr/prep_bufr.html).
- [DART radar observations and pyOPAWS workflow](https://docs.dart.ucar.edu/en/stable/observations/obs_converters/radar/README.html).
- [NEXRAD Level II open archive](https://registry.opendata.aws/noaa-nexrad/) and [MRMS open archive](https://registry.opendata.aws/noaa-mrms-pds/).
- [DART GPSPW converter](https://docs.dart.ucar.edu/en/stable/observations/obs_converters/GPSPW/README.html) and [DART tropical-cyclone converter](https://docs.dart.ucar.edu/en/stable/observations/obs_converters/tropical_cyclone/tc_to_obs.html).

## Confidence and limitations

- **High confidence:** observation-family inventory; CONUS radiance exclusion; HRRRDAS direct MRMS-reflectivity path; deterministic latent-heating/SCHDA use; and direct radial-velocity use in both HRRRDAS and deterministic HRRR at the audited `44728d00…` reference commit and the later `40ee6058…` comparison.
- **Moderate confidence in exact operational replay from public data:** public archives contain scientifically equivalent source observations, but often not the exact NCEP operational BUFR dump after its original decoding, QC, thinning, blacklisting, and error assignment.
- **Feed evolution caveat:** individual satellite missions and data providers changed during the HRRRv4 era. The stable scientific categories are more reliable than assuming one sensor/platform name applied unchanged to every operational date.
- **WRF-DART caveat:** “stock” means a distributed converter/operator exists, not that the observation can be assimilated safely without format, unit, QC, error, localization, and representativeness checks.
