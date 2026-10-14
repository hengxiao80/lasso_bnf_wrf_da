#!/usr/bin/env python
"""MRMS 3-D reflectivity -> DART obs_seq on the WRF mass grid, following HRRRDAS.

Python port of HRRR's sorc/hrrr_process_mosaic.fd/process_NSSL_mosaic_to_dart_and_netcdf.f90
(GRIB2 path, tversion = 1) with the namelist of scripts/hrrrdas/exhrrr_prep_radar.sh as defaults
(../software/HRRR, 40ee6058). Same logic:

  * each MergedReflectivityQC level is bilinearly interpolated to every mass point of geo_em
    (XLAT_M/XLONG_M); if any of the 4 MRMS neighbours is <= -90 (MRMS -99 = 'Missing': covered, no echo) but all are
    > -900 (MRMS -999 = 'No Coverage'), the point is "clear" (-99); otherwise missing (-999);
  * the outermost grid row/column gives no obs;
  * precipitation obs: Z >= precip_dbz_thresh, height <= max_height, levels 1, 1+(skip+1), ...;
    clear-air obs: -900 < Z <= clear_air_dbz_thresh, value set to clear_air_dbz_value, only at
    4.0 and 8.5 km (the Fortran's hard-coded clear_air_dbz_vert_skip = -1 case);
  * greedy horizontal thinning in the Fortran scan order (j outer, i inner): a kept point removes
    all others within +-skip grid points, so the spacing is skip+1 points;
  * heights are the MRMS level heights (m MSL), VERTISHEIGHT; error sd 5 dBZ.

Differences from the Fortran: the obs time is the MRMS valid time (the Fortran writes the top of
the hour), and the MRMS time is chosen with HRRRDAS's rule (the analysis minute, else 1, else 2
minutes earlier, requiring all 33 levels) but with real date arithmetic (the script's fallback for
minute 00 is minute 59 of the same hour). Longitudes are written in [0, 2pi), as the Fortran does.

Usage:
  mrms_to_obs_seq.py MRMS_DIR YYYYMMDDHHMM GEO_EM OUT [--grid-nc FILE] [options]
MRMS_DIR holds MRMS_MergedReflectivityQC_XX.XX_YYYYMMDD-HHMMSS.grib2.gz files.
"""
import argparse
import datetime as dt
import glob
import gzip
import os
import re
import sys

import eccodes
import netCDF4
import numpy as np

LEVELS_M = [500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750, 3000, 3500, 4000, 4500,
            5000, 5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000, 10000, 11000, 12000, 13000,
            14000, 15000, 16000, 17000, 18000, 19000]
RTHRESH_REF, RTHRESH_MISS = -90.0, -900.0  # tversion = 1
FNAME = re.compile(r'MRMS_MergedReflectivityQC_(\d\d\.\d\d)_(\d{8})-(\d{6})\.grib2(\.gz)?$')


def find_mrms_files(mrms_dir, t_anal):
    """HRRRDAS rule: all 33 levels at minute mm, else mm-1, else mm-2."""
    for back in (0, 1, 2):
        t = t_anal - dt.timedelta(minutes=back)
        pat = os.path.join(mrms_dir, f'MRMS_MergedReflectivityQC_*_{t:%Y%m%d-%H%M}??.grib2*')
        files = sorted(glob.glob(pat))
        if len(files) == len(LEVELS_M):
            return files
    sys.exit(f'no complete set of {len(LEVELS_M)} MRMS levels within 2 min before {t_anal}')


def read_level(path):
    raw = open(path, 'rb').read()
    if path.endswith('.gz'):
        raw = gzip.decompress(raw)
    h = eccodes.codes_new_from_message(raw)
    try:
        g = {k: eccodes.codes_get(h, k) for k in
             ('Ni', 'Nj', 'jScansPositively', 'scaledValueOfFirstFixedSurface',
              'scaleFactorOfFirstFixedSurface', 'dataDate', 'hour', 'minute', 'second')}
        g['lat1'] = eccodes.codes_get(h, 'latitudeOfFirstGridPointInDegrees')
        g['lon1'] = eccodes.codes_get(h, 'lon' + 'gitudeOfFirstGridPointInDegrees')
        g['dlat'] = eccodes.codes_get(h, 'jDirectionIncrementInDegrees')
        g['dlon'] = eccodes.codes_get(h, 'iDirectionIncrementInDegrees')
        vals = eccodes.codes_get_values(h).reshape(g['Nj'], g['Ni'])
    finally:
        eccodes.codes_release(h)
    if g['jScansPositively'] != 0:
        sys.exit(f'{path}: expected north-to-south rows')
    g['height'] = g['scaledValueOfFirstFixedSurface'] / 10 ** g['scaleFactorOfFirstFixedSurface']
    d = str(g['dataDate'])
    g['time'] = dt.datetime(int(d[:4]), int(d[4:6]), int(d[6:]), g['hour'], g['minute'], g['second'])
    return g, vals


def to_model_grid(g, vals, lat, lon):
    """Bilinear interpolation as in the Fortran (1-based indices there, 0-based here)."""
    lon = np.where(lon < 0.0, lon + 360.0, lon)
    rip = (lon - g['lon1']) / g['dlon']          # Fortran rip - 1
    rjp = (g['lat1'] - lat) / g['dlat']          # Fortran rjp - 1 (row 0 = north)
    ip, jp = np.floor(rip).astype(int), np.floor(rjp).astype(int)
    dip, djp = rip - ip, rjp - jp
    nj, ni = vals.shape
    out = np.full(lat.shape, -999.0)
    inside = (ip >= 0) & (ip < ni) & (jp >= 0) & (jp < nj)
    ip, jp, dip, djp = ip[inside], jp[inside], dip[inside], djp[inside]
    ipp1, jpp1 = np.minimum(ip + 1, ni - 1), np.minimum(jp + 1, nj - 1)
    r1, r2, r3, r4 = vals[jp, ip], vals[jp, ipp1], vals[jpp1, ipp1], vals[jpp1, ip]
    w1, w2, w3, w4 = (1 - dip) * (1 - djp), dip * (1 - djp), dip * djp, (1 - dip) * djp
    good = (r1 > RTHRESH_REF) & (r2 > RTHRESH_REF) & (r3 > RTHRESH_REF) & (r4 > RTHRESH_REF)
    seen = (r1 > RTHRESH_MISS) & (r2 > RTHRESH_MISS) & (r3 > RTHRESH_MISS) & (r4 > RTHRESH_MISS)
    out[inside] = np.where(good, r1 * w1 + r2 * w2 + r3 * w3 + r4 * w4,
                           np.where(seen, -99.0, -999.0))
    return out


def thin(mask, skip):
    """Greedy thinning of a 2-D [j, i] mask in the Fortran order (j outer, i inner)."""
    if skip <= 0:
        return mask
    m = mask.copy()
    nj, ni = m.shape
    for j, i in zip(*np.nonzero(mask)):    # row-major = j outer, i inner
        if m[j, i]:
            j0, j1 = max(1, j - skip), min(nj - 2, j + skip)
            i0, i1 = max(1, i - skip), min(ni - 2, i + skip)
            m[j0:j1 + 1, i0:i1 + 1] = False
            m[j, i] = True
    return m


def write_obs_seq(path, obs, t_obs, err_sd):
    """obs: list of (kind_index 1|2, value, lat_deg, lon_deg, height_m), in output order."""
    days = (t_obs - dt.datetime(1601, 1, 1)).days
    secs = (t_obs - dt.datetime(t_obs.year, t_obs.month, t_obs.day)).seconds
    n = len(obs)
    with open(path, 'w') as f:
        f.write(' obs_sequence\nobs_type_definitions\n           2\n')
        f.write('           1 RADAR_REFLECTIVITY\n           2 RADAR_CLEARAIR_REFLECTIVITY\n')
        f.write(f'  num_copies:            1  num_qc:            1\n')
        f.write(f'  num_obs: {n:12d}  max_num_obs: {n:12d}\n')
        f.write('MRMS observation\nData QC\n')
        f.write(f'  first: {min(n, 1):12d}  last: {n:12d}\n')
        for k, (kind, val, la, lo, z) in enumerate(obs, start=1):
            prev = k - 1 if k > 1 else -1
            nxt = k + 1 if k < n else -1
            f.write(f' OBS {k:12d}\n {val:.6f}\n 0.000000\n {prev:11d} {nxt:11d} {-1:11d}\n')
            f.write(f'obdef\nloc3d\n {np.deg2rad(lo % 360.0):.15f} {np.deg2rad(la):.15f} '
                    f'{z:.6f} 3\nkind\n {kind:11d}\n {secs} {days}\n {err_sd ** 2:.6f}\n')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mrms_dir')
    p.add_argument('analysis_time', help='YYYYMMDDHHMM')
    p.add_argument('geo_em')
    p.add_argument('out')
    p.add_argument('--grid-nc', help='also write the gridded field and obs masks (netCDF)')
    p.add_argument('--dbz-error-sd', type=float, default=5.0)
    p.add_argument('--max-height', type=float, default=11001.0)
    p.add_argument('--no-clear-air', action='store_true')
    p.add_argument('--precip-dbz-thresh', type=float, default=10.0)
    p.add_argument('--clear-air-dbz-thresh', type=float, default=0.0)
    p.add_argument('--clear-air-dbz-value', type=float, default=-10.0)
    p.add_argument('--precip-dbz-horiz-skip', type=int, default=1)
    p.add_argument('--precip-dbz-vert-skip', type=int, default=2)
    p.add_argument('--clear-air-dbz-horiz-skip', type=int, default=5)
    p.add_argument('--clear-air-levels-m', default='4000,8500',
                   help='clear-air levels (HRRRDAS hard-codes levels 13 and 22 = 4.0, 8.5 km)')
    a = p.parse_args()

    t_anal = dt.datetime.strptime(a.analysis_time, '%Y%m%d%H%M')
    with netCDF4.Dataset(a.geo_em) as nc:
        lat = np.asarray(nc['XLAT_M'][0], dtype=np.float64)
        lon = np.asarray(nc['XLONG_M'][0], dtype=np.float64)
    nj, ni = lat.shape

    ref = np.full((len(LEVELS_M), nj, ni), -999.0)
    times = set()
    for path in find_mrms_files(a.mrms_dir, t_anal):
        g, vals = read_level(path)
        k = LEVELS_M.index(int(round(g['height'])))
        ref[k] = np.maximum(ref[k], to_model_grid(g, vals, lat, lon))
        times.add(g['time'])
    if len(times) != 1:
        print(f'warning: levels have different valid times: {sorted(times)}')
    t_obs = min(times)
    print(f'analysis {t_anal}, MRMS valid {t_obs}, grid {ni} x {nj}')

    ref[:, 0, :] = ref[:, -1, :] = ref[:, :, 0] = ref[:, :, -1] = -999.0
    hgt_ok = np.array(LEVELS_M)[:, None, None] <= a.max_height
    precip = hgt_ok & (ref >= a.precip_dbz_thresh)
    clear = (~precip & hgt_ok & (ref > -900.0) & (ref <= a.clear_air_dbz_thresh)
             if not a.no_clear_air else np.zeros_like(precip))
    print(f'before thinning: precip {precip.sum()}, clear air {clear.sum()}')

    clear_levels = [LEVELS_M.index(int(z)) for z in a.clear_air_levels_m.split(',')]
    for k in range(len(LEVELS_M)):
        if a.precip_dbz_vert_skip > 0 and k % (a.precip_dbz_vert_skip + 1) != 0:
            precip[k] = False
        if k not in clear_levels:
            clear[k] = False
        precip[k] = thin(precip[k], a.precip_dbz_horiz_skip)
        clear[k] = thin(clear[k], a.clear_air_dbz_horiz_skip)

    obs = []
    for k, z in enumerate(LEVELS_M):
        for j, i in zip(*np.nonzero(precip[k] | clear[k])):
            if clear[k, j, i]:
                obs.append((2, a.clear_air_dbz_value, lat[j, i], lon[j, i], float(z)))
            else:
                obs.append((1, ref[k, j, i], lat[j, i], lon[j, i], float(z)))
    print(f'after thinning: precip {int(precip.sum())}, clear air {int(clear.sum())}')
    for k, z in enumerate(LEVELS_M):
        if precip[k].any() or clear[k].any():
            print(f'  {z / 1000:5.2f} km: precip {int(precip[k].sum()):6d}  clear {int(clear[k].sum()):6d}')
    write_obs_seq(a.out, obs, t_obs, a.dbz_error_sd)
    print(f'wrote {len(obs)} obs to {a.out}')

    if a.grid_nc:
        with netCDF4.Dataset(a.grid_nc, 'w') as nc:
            nc.createDimension('level', len(LEVELS_M))
            nc.createDimension('south_north', nj)
            nc.createDimension('west_east', ni)
            nc.createVariable('height', 'f4', ('level',))[:] = LEVELS_M
            v = nc.createVariable('refl', 'f4', ('level', 'south_north', 'west_east'), zlib=True)
            v[:] = ref
            v.description = 'MRMS on the mass grid; -99 clear (MRMS Missing: covered, no echo), -999 MRMS No Coverage'
            nc.createVariable('precip_ob', 'i1', ('level', 'south_north', 'west_east'), zlib=True)[:] = precip
            nc.createVariable('clear_air_ob', 'i1', ('level', 'south_north', 'west_east'), zlib=True)[:] = clear
            nc.mrms_valid_time = f'{t_obs:%Y-%m-%d %H:%M:%S}'


if __name__ == '__main__':
    main()
