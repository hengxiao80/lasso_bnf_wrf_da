# External data this case depends on

Recorded 2026-09-18. Paths under `/gpfs/wolf2/arm/cli120/proj-shared/sey/` belong to
user `sey` (the colleague whose runs `bnf_wrf_eval` evaluates); they are group-readable
and are used read-only.

## Referenced in place (NOT copied) -- this case breaks if these move or change

| What | Where | Used by |
|---|---|---|
| HRRR analyses, pressure levels (`hrrr.tHHz.wrfprsf00.grib2`, 73 h, 28.7 GB) | `sey/bnf/wrf/forcing/hrrr/hrrr_data/YYYYMMDD/` | `wps/GRIBFILE.*` symlinks (ungrib) |
| HRRR analyses, native levels (`hrrr.tHHz.wrfnatf00.grib2`, 73 h, 49.6 GB) | `sey/bnf/wrf/forcing/hrrr/hrrrnat_data/YYYYMMDD/` | `wps/GRIBFILE.*` symlinks (ungrib) |

Files were downloaded by sey from the NOAA HRRR archive (`get-hrrr.py` in the same
directory). Window used: 2025-05-19 00Z to 2025-05-22 00Z, hourly. If sey moves the
data, rerun `scripts/link_hrrr_gribfiles.py` with `--hrrr-root` pointing at the new
location (or copy the 78 GB into this project first).

## Copied from sey (checksums verified identical at copy time)

| File | Copied from | sha256 |
|---|---|---|
| `geog/geo_em.d01.nc` | `sey/bnf/wrf/test1/20250520lassobnfwrfhrrr3/geog-merit-nlcd2006-smooth/org/` | `399ca6f4...d65d52` |
| `wps/QNWFA_QNIFA_QNBCA_SIGMA_MONTHLY.dat` | `.../metgrid-revk/` | `4c969c13...bf06` |
| `wps/Vtable.hrrrv4rap` (custom HRRR native+prs Vtable, not in stock WPS) | `.../metgrid-revk/` (same as `sey/bnf/wrf/code/WPS/ungrib/Variable_Tables/`) | `fbf9fd0c...7275` |
| `baseline/freezeH2O.dat`, `qr_acr_qg_V4.dat`, `qr_acr_qsV2.dat` (Thompson mp=28 lookup tables) | `.../rund1-dynlit/` | verified identical |

## Derived from sey's configuration

- `baseline/namelist.input`: sey's `rund1-dynlit/namelist.input` with these changes.
  Original kept as `namelist.input.sey_rund1-dynlit`; the intermediate version (physics
  changes only) as `namelist.input.before_iotuning`.
  - Model: `hybrid_opt` 2 -> 0 and an explicit `use_theta_m = 1`.
  - I/O and decomposition (from the tests in `iotest/`, variant K): `io_form_history`
    11 -> 2 with `use_netcdf_classic = .true.` (uncompressed classic netCDF, same format
    as sey's wrfout), `nocolons = .true.`, `nproc_x = nproc_y = 16`.
    None of these change the model results (30-min output bit-identical across variants).
  - History output can be compressed after the run, losslessly, with
    `nccopy -k nc4 -d 2 -s in.nc out.nc` (tested: 3.95 -> 1.27 GB, ~41 s per file,
    all 222 variables identical).
- `wps/namelist.wps`: sey's `metgrid-revk/namelist.wps`, d01 only, dates 05-19_00 -> 05-22_00.
- Level reversal of met_em files: our own `scripts/reverse_metgridlevs.py`; verified
  bit-identical to sey's `reverse_metgridlevs.py` output on two files.

## Observations downloaded into this case (`obs/`, untracked)

Added 2026-10-15. All public, no account. Sizes are `du -sh` on 2026-10-15. Details and
the searches behind each choice: `notes/wrf_dart_tutorial_adaptation.md` 2.13 (MADIS,
GDAS, GOES) and `notes/obs_expansion.md` (mesonet Sec. 7, MRMS Sec. 8).

| What | Where here | Source | Downloaded | Used by |
|---|---|---|---|---|
| Public MADIS hourly point files: `acars`, `marine`, `mesonet`, `metar` (72 each), `raob` (53, launch hours only), 05-19 00Z – 05-21 23Z, `YYYYMMDD_HH00.gz` | `obs/madis/<family>/` (2.3 GB, 2.1 GB of it mesonet) | `https://madis-data.ncep.noaa.gov/madisPublic1/data/archive/` (public archive; the research archive needs credentials) | 2026-09-25 (all pass `gzip -t`) | `scripts/da/convert_madis_hour.sh`, `scripts/da/make_cycle_mesonet.sh` |
| MADIS single-hour test files (05-20 12/18Z; includes `profiler`) | `obs/madis_test/` (109 MB) | same | 2026-09-25 | first converter tests only |
| MRMS `MergedReflectivityQC`, 33 levels × 4 times (00:14:38, 00:30:40, 00:44:42, 01:00:38 on 05-20), GRIB2 | `obs/mrms/20250520/` (131 MB) | AWS `https://noaa-mrms-pds.s3.amazonaws.com/CONUS/MergedReflectivityQC_XX.XX/YYYYMMDD/` | 2026-10-14 | `scripts/da/download_mrms.sh` (HRRRDAS minute rule), `scripts/da/mrms_to_obs_seq.py` |
| GDAS PREPBUFR, 6-hourly, 05-19 00Z – 05-22 00Z (13 times each): `prepnr/prepbufr.gdas.YYYYMMDDHH.nr`, `prep48h/prepbufr.gdas.YYYYMMDD.tHHz.nr.48h` (+ `test*` dirs) | `obs/gdas_prepbufr/` (2.0 GB) | NCAR GDEX `d337000` via OSDF, `https://osdf-director.osg-htc.org/ncar/gdex/d337000/{prepnr,prep48h}/2025/` | 2026-09-25 | not used yet (fallback for conventional obs; source for VAD winds and GPS PW) |
| GOES-19 ABI L2 derived motion winds, CONUS, one scan (05-20 12:01Z, channels 2, 7, 8, 9, 10, 14) | `obs/goes_dmw_test/` (1 MB) | AWS `noaa-goes19/ABI-L2-DMWC/YYYY/DDD/HH/` | 2026-09-25 | reader test only (no converter yet) |

Not downloaded: the 05-22 00Z MADIS METAR/marine files (reports from 05-21 23:45; needed
only if cycling runs past 05-21 23:30), NEXRAD Level II (planned source for radial
velocity: AWS `unidata-nexrad-level2`).

Derived observation files (`obs/obs_seq_*`, `da_theta_m0/obs*/`) are made from these by
the scripts above and can be rebuilt.

## Reference code and fixed files outside this repo (`../software/`, read-only use)

| What | Where | Used by |
|---|---|---|
| RRFS v2 mesonet lists: `parm/observers/msonet_uv288.yaml` (P1, S2), `fix/jedi/current_mesonet_uselist.yaml` (S1), `fix/jedi/mesonet_trusted_provider.yaml` (P5) | `../software/RRFSv2` (NOAA-EMC/rrfs-workflow `rrfs-mpas-jedi` `08eee4ce`) | `scripts/da/select_mesonet_cycle.py` (records path, sha256 and commit in each cycle's `selection.log`) |
| NCEP error tables and convinfo (RAP, NAM, RRFS) | `../software/GSI-fix_subset` (NOAA-EMC/GSI-fix `0ba656b6`, single files) | the METAR and mesonet error patches (`patches/`) |
| HRRR / HRRRDAS code (MRMS program, HRRRDAS settings) | `../software/HRRR` (NOAA-EMC/HRRR `40ee6058`) | ported in `scripts/da/mrms_to_obs_seq.py` |
| WRFDA CV3 background errors `be.dat.cv3` | `../software/WRFDA/var/run/` | perturbation bank (`scripts/da/run_wrfda_draw.sh`) |
| DART sampling-error-correction table | `../software/DART/assimilation_code/programs/gen_sampling_err_table/work/sampling_error_correction_table.nc` | filter (`SEC_TABLE` in `da_theta_m0/config/experiment.sh`) |

Other reference clones (`GSI`, `RRFSv1`, `pyOPAWS`) are cited in
`notes/mesonet_station_selection.md` Sec. 1 and `notes/obs_expansion.md` Sec. 4.
