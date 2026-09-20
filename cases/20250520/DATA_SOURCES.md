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
