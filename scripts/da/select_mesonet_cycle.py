"""Select the public-MADIS mesonet reports for one analysis cycle (obs_expansion.md Sec. 7.2).

Usage: select_mesonet_cycle.py <YYYYMMDDHHMM> <out_dir> [--option a|b1|c] [--calm keep|drop]
                               [--metar-radius-km KM] [--grid-file WRFINPUT]
                               [--case-dir DIR] [--software-dir DIR]

Writes into <out_dir>:
  mesonet_input.nc   the selected records, in the MADIS layout convert_madis_mesonet reads
                     (variables it does not read are left out)
  selected.csv       one row per selected station: provider, ID, location, time, values, and which
                     variables are passed on to the converter (for per-provider statistics later)
  selection.log      settings, list files (path, sha256, RRFSv2 commit) and counts, including the
                     obs per variable removed by rules 2b and 2c
  dropped_feet.csv   the sites removed by rule 2c, with their elevation and the model terrain

Selection, in order (decisions of 2026-10-13, list IDs as in notes/mesonet_station_selection.md):
 1. Records of the hourly MADIS mesonet files (${case_dir}/obs/madis/mesonet/YYYYMMDD_HH00.gz) inside
    the domain's lat/lon box (the box of convert_madis_hour.sh) and inside the filter window of the
    analysis time t, (t - 450 s, t + 450 s].
 2. Stations whose ID is a METAR station in the METAR files of the same hours are dropped (the same
    report would enter twice).
 2b. Sites within --metar-radius-km (default 4 km) of a METAR report of the same window are dropped,
    so METAR takes precedence (decided 2026-10-14). The METAR reports are those of the converted
    hourly files (${case_dir}/obs/obs_seq_madis/metar/obs_seq.metar.YYYYMMDD_HH00, the hours t - 1 h
    to t + 1 h, as make_cycle_obs.sh slices them) with times in the window. Reason:
    wrf_dart_obs_preprocess adds the land-surface file before METAR and skips a METAR report whose
    location is a "duplicate" (get_dist <= 1e-5 rad) of one already added, for all of its
    variables, whatever the times. With DART built with r8 = r4 that test is float32 acos, which
    returns 0 for most pairs within ~1.5 km and for some up to 3.7 km (obs_expansion.md Sec. 7.2), so
    nearby mesonet sites would otherwise remove METAR reports.
 2c. Sites whose elevation is given in feet are dropped (decided 2026-10-14): inside the domain, the
    station elevation z misfits the model terrain h (HGT of --grid-file, bilinear, as
    wrf_dart_obs_preprocess's elevation check) by more than FEET_METRE_MISFIT as metres, but fits it
    within FEET_FIT as feet (|z / 3.28084 - h|). At 00:15 on 05-20: 68 sites (59 APRSWXNET, 9 MesoWest),
    most of which the 300-m elevation check would drop anyway; between 100 and 150 m misfit no site fits
    as feet, so the two groups separate cleanly. Below ~100 m misfit feet and metres can't be told
    apart. The elevation matters beyond the check: convert_madis_mesonet's q uses the station pressure
    from the altimeter and the elevation (obs_expansion.md Sec. 7.2).
 3. Per variable, a report is accepted by the station/provider option:
      a   RRFS v2: T, q, altimeter from all providers; wind if the provider is in P1 or
          (provider, station) is in S2 (both in RRFSv2 parm/observers/msonet_uv288.yaml).
      b1  GSD method (deterministic HRRR, RRFS v1): provider in P4, or the station flagged for that
          variable in S1 (RRFSv2 fix/jedi/current_mesonet_uselist.yaml: temperature -> T,
          dewpoint -> q, wind -> wind); altimeter from P4 providers only. P4 is read from P5
          (RRFSv2 fix/jedi/mesonet_trusted_provider.yaml), which holds the same 9 providers.
      c   HRRRDAS: provider in P4 only, all variables.
    Providers are compared on their first 8 characters (GSI compares c_prvstg(1:8); P5 stores
    8-character names). Subproviders are not checked (only P5's FL-Meso/FAWN entry has one).
    Station IDs are matched exactly (GSI also accepts a station whose ID starts with a list ID).
 4. A variable is usable if it is present (not _FillValue, not missing_value) with MADIS QCR = 0
    and accepted; wind needs speed and direction. --calm drop also rejects calm winds
    (speed < 0.01 m/s, as GSI's i_gsdqc = 2); the default, keep, follows RRFS v2.
 5. One record per site (latitude and longitude equal to 4 decimals, so one station reported by
    two providers, e.g. HADS and MesoWest under the same ID, or re-registered APRSWXNET IDs, count
    once): among its records with at least one usable variable, the one closest to t; ties go to
    the record with more usable variables, then the earlier one. Variables of that record that are
    not usable are not taken from another record. (convert_madis_mesonet would otherwise drop the
    second of two records with the same location and time, whatever variables it had.)

How the converter is steered: a variable that is not usable in the chosen record is set to its
missing_value (-9999), so convert_madis_mesonet skips it. The converter makes q only from T,
dewpoint and altimeter that all pass (it needs the altimeter for the pressure), so:
  - q is written only if T, dewpoint and altimeter are all usable in the record;
  - under b1 and c, altimeter is not an accepted variable for most stations, but blanking it would
    also remove their q. It is kept wherever the record's q is kept (counted in the log as
    "altimeter kept for q"); the altimeter is evaluate-only in our filter setup.
Under b1, q accepted by S1 dewpoint also needs T accepted by S1 temperature (the converter writes
T whenever it makes q from it).
"""
import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import os
import re
import sys

import netCDF4 as nc
import numpy as np
import yaml

MIN_LAT, MAX_LAT, MIN_LON, MAX_LON = 30.36, 39.37, 262.52, 278.38   # convert_madis_hour.sh
DART_EPOCH = dt.datetime(1601, 1, 1, tzinfo=dt.timezone.utc)
HALF = 450                                                           # filter window half-width (s)
FEET_METRE_MISFIT = 100.0                                            # m
FEET_FIT = 60.0                                                      # m
FT = 3.28084                                                         # feet per metre
CALM = 0.01                                                          # m/s
MISSING = -9999.0
VALUES = ['temperature', 'dewpoint', 'altimeter', 'windDir', 'windSpeed']
QCRS = [v + 'QCR' for v in VALUES]


def read_madis(path, names, char_names=()):
    """Read the named variables of a gzipped hourly MADIS file (in memory)."""
    with gzip.open(path) as src:
        f = nc.Dataset('madis', memory=src.read())
    f.set_auto_mask(False)
    out = {n: f[n][:] for n in names}
    for n in char_names:
        out[n] = np.array([b''.join(r).decode(errors='replace').strip() for r in f[n][:]])
    out['_attrs'] = {n: {a: f[n].getncattr(a) for a in f[n].ncattrs()} for n in names}
    f.close()
    return out


def metar_window_locations(case_dir, t):
    """(lat, lon) in degrees of the METAR reports in the converted hourly obs_seq files with times in
    (t - HALF, t + HALF]: the METAR reports wrf_dart_obs_preprocess sees in this cycle (before its
    domain trim). Returns the arrays and the files read."""
    lats, lons, files = [], [], []
    for dh in (-1, 0, 1):
        stamp = dt.datetime.fromtimestamp(t + dh * 3600, dt.timezone.utc).strftime('%Y%m%d_%H00')
        path = os.path.join(case_dir, 'obs/obs_seq_madis/metar', 'obs_seq.metar.' + stamp)
        if not os.path.exists(path):
            continue
        files.append(path)
        lines = open(path).read().split('\n')
        for j, line in enumerate(lines):
            if line.strip() == 'loc3d':
                lon, lat = (float(x) for x in lines[j + 1].split()[:2])
                secs, days = (int(x) for x in lines[j + 4].split())
                ts = (DART_EPOCH + dt.timedelta(days=days, seconds=secs)).timestamp()
                if t - HALF < ts <= t + HALF:
                    lats.append(np.degrees(lat))
                    lons.append(np.degrees(lon))
    return np.array(lats), np.array(lons), files


def km_to_nearest(lat, lon, lat_ref, lon_ref):
    """Great-circle distance (km, float64) from each (lat, lon) to the nearest reference point."""
    if lat_ref.size == 0:
        return np.full(lat.size, np.inf)
    p1, p2 = np.radians(lat)[:, None], np.radians(lat_ref)[None, :]
    dl = np.radians(lon % 360)[:, None] - np.radians(lon_ref % 360)[None, :]
    h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return (2 * 6371.0 * np.arcsin(np.sqrt(h))).min(axis=1)


def model_terrain(grid_file, lat, lon):
    """Bilinear model terrain (m) at the points, and whether each is inside the mass grid. Lambert
    conformal (MAP_PROJ = 1), WRF's llij_lc with WRF's earth radius; checked against XLAT/XLONG to
    0.001 grid lengths on this domain."""
    with nc.Dataset(grid_file) as g:
        if int(g.getncattr('MAP_PROJ')) != 1:
            sys.exit(f'select_mesonet_cycle.py: {grid_file} is not Lambert conformal')
        a = {k: float(g.getncattr(k)) for k in ['TRUELAT1', 'TRUELAT2', 'STAND_LON', 'CEN_LAT', 'CEN_LON', 'DX']}
        hgt = g['HGT'][0].astype(np.float64)
    t1, t2 = np.radians(a['TRUELAT1']), np.radians(a['TRUELAT2'])
    if abs(t1 - t2) < 1e-6:
        cone = np.sin(t1)
    else:
        cone = np.log(np.cos(t1) / np.cos(t2)) / np.log(np.tan(np.pi / 4 + t2 / 2) / np.tan(np.pi / 4 + t1 / 2))
    big_f = 6370000.0 * np.cos(t1) * np.tan(np.pi / 4 + t1 / 2) ** cone / cone

    def xy(la, lo):
        rho = big_f / np.tan(np.pi / 4 + np.radians(la) / 2) ** cone
        th = cone * np.radians((lo - a['STAND_LON'] + 180) % 360 - 180)
        return rho * np.sin(th), -rho * np.cos(th)

    ny, nx = hgt.shape
    x0, y0 = xy(a['CEN_LAT'], a['CEN_LON'])
    x, y = xy(np.asarray(lat, np.float64), np.asarray(lon, np.float64))
    i = (x - x0) / a['DX'] + (nx - 1) / 2
    j = (y - y0) / a['DX'] + (ny - 1) / 2
    inside = (i >= 0) & (i <= nx - 1) & (j >= 0) & (j <= ny - 1)
    i0 = np.clip(np.floor(i).astype(int), 0, nx - 2)
    j0 = np.clip(np.floor(j).astype(int), 0, ny - 2)
    fi, fj = np.clip(i - i0, 0, 1), np.clip(j - j0, 0, 1)
    h = (hgt[j0, i0] * (1 - fi) * (1 - fj) + hgt[j0, i0 + 1] * fi * (1 - fj)
         + hgt[j0 + 1, i0] * (1 - fi) * fj + hgt[j0 + 1, i0 + 1] * fi * fj)
    return h, inside


def in_box(lat, lon):
    lon = lon % 360.0
    return (lat >= MIN_LAT) & (lat <= MAX_LAT) & (lon >= MIN_LON) & (lon <= MAX_LON)


def sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def git_head(repo):
    """Commit of a clone without running git (HEAD -> ref file or packed-refs)."""
    try:
        head = open(os.path.join(repo, '.git', 'HEAD')).read().strip()
        if not head.startswith('ref: '):
            return head[:10]
        ref = head[5:]
        path = os.path.join(repo, '.git', ref)
        if os.path.exists(path):
            return open(path).read().strip()[:10] + f' ({ref})'
        for line in open(os.path.join(repo, '.git', 'packed-refs')):
            if line.rstrip().endswith(ref):
                return line.split()[0][:10] + f' ({ref})'
    except OSError:
        pass
    return 'unknown'


def load_lists(rrfsv2):
    """P1 and S2 from the wind observer, S1 and P5 (= P4) from fix/jedi."""
    obs_file = os.path.join(rrfsv2, 'parm/observers/msonet_uv288.yaml')
    # The observer is a fragment of a larger YAML: drop its one merge key whose anchor
    # (polygonConfig, used by the Polygon Check filter) is defined elsewhere.
    text = ''.join(l for l in open(obs_file) if not re.match(r'\s*<<:\s*\*', l))
    filters = yaml.safe_load(text)[0]['obs filters']
    p1, s2 = None, set()
    for flt in filters:
        if flt.get('filter') != 'AcceptList' or 'where' not in flt:
            continue
        where = {w['variable']: w['is_in'] for w in flt['where']}
        provs = where.get('MetaData/dataProviderOrigin')
        stations = where.get('MetaData/stationIdentification')
        if provs and stations is None:
            if p1 is not None:
                raise RuntimeError(f'{obs_file}: more than one provider AcceptList')
            p1 = set(provs)
        elif provs and stations:
            s2 |= {(p, str(s)) for p in provs for s in stations}
    if p1 is None or not s2:
        raise RuntimeError(f'{obs_file}: provider list or station blocks not found')

    s1_file = os.path.join(rrfsv2, 'fix/jedi/current_mesonet_uselist.yaml')
    s1 = {k: {str(s) for s in v} for k, v in yaml.safe_load(open(s1_file)).items()}
    p5_file = os.path.join(rrfsv2, 'fix/jedi/mesonet_trusted_provider.yaml')
    p4 = {str(p)[:8] for e in yaml.safe_load(open(p5_file))['trusted'] for p in e['provider']}
    files = {'P1, S2': obs_file, 'S1': s1_file, 'P4 (from P5)': p5_file}
    return p1, s2, s1, p4, files


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('stamp', help='analysis time YYYYMMDDHHMM')
    ap.add_argument('out_dir')
    ap.add_argument('--option', choices=['a', 'b1', 'c'], default='a')
    ap.add_argument('--calm', choices=['keep', 'drop'], default='keep')
    ap.add_argument('--metar-radius-km', type=float, default=4.0,
                    help='drop sites this close to a METAR report of the same window (default 4)')
    ap.add_argument('--grid-file', default='/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da/cases/20250520/'
                    'da_theta_m0/mean/wrfinput_d01_2025-05-20_00_00_00', help='wrfinput for the model terrain (rule 2c)')
    ap.add_argument('--case-dir', default='/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da/cases/20250520')
    ap.add_argument('--software-dir', default='/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/software')
    args = ap.parse_args()

    t = int(dt.datetime.strptime(args.stamp, '%Y%m%d%H%M').replace(tzinfo=dt.timezone.utc).timestamp())
    hours = range((t - HALF + 1) // 3600, (t + HALF) // 3600 + 1)
    stamps = [dt.datetime.fromtimestamp(h * 3600, dt.timezone.utc).strftime('%Y%m%d_%H00') for h in hours]
    rrfsv2 = os.path.join(args.software_dir, 'RRFSv2')
    p1, s2, s1, p4, list_files = load_lists(rrfsv2)
    os.makedirs(args.out_dir, exist_ok=True)
    log = open(os.path.join(args.out_dir, 'selection.log'), 'w')

    def say(*a):
        print(*a)
        print(*a, file=log)

    say(f'select_mesonet_cycle.py {args.stamp}: option {args.option}, calm {args.calm}, '
        f'METAR radius {args.metar_radius_km} km, feet rule (misfit > {FEET_METRE_MISFIT:.0f} m as metres, < {FEET_FIT:.0f} m as feet, terrain {args.grid_file}), window ({t - HALF}, {t + HALF}] s, hours {stamps}')
    say(f'RRFSv2 {git_head(rrfsv2)}')
    for k, path in list_files.items():
        say(f'  {k}: {path} sha256 {sha256(path)}')
    say(f'  sizes: P1 {len(p1)}, S2 {len(s2)}, S1 ' + ', '.join(f'{k} {len(v)}' for k, v in s1.items())
        + f', P4 {len(p4)} {sorted(p4)}')

    # --- 1. records in the box and the window ------------------------------------------------
    names = ['latitude', 'longitude', 'elevation', 'observationTime'] + VALUES + QCRS
    parts, attrs = [], None
    for s in stamps:
        path = os.path.join(args.case_dir, 'obs/madis/mesonet', s + '.gz')
        if not os.path.exists(path):
            say(f'  missing mesonet file {path}, skipped')
            continue
        d = read_madis(path, names, ['stationId', 'dataProvider'])
        attrs = d.pop('_attrs')
        keep = in_box(d['latitude'], d['longitude']) & (d['observationTime'] > t - HALF) & \
            (d['observationTime'] <= t + HALF)
        parts.append({k: v[keep] for k, v in d.items()})
        say(f'  {s}: {keep.size} records, {keep.sum()} in box and window')
    if not parts:
        sys.exit('select_mesonet_cycle.py: no mesonet file for this cycle')
    r = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    n = r['latitude'].size

    # --- 2. METAR duplicates ------------------------------------------------------------------
    metar_ids = set()
    for s in stamps:
        path = os.path.join(args.case_dir, 'obs/madis/metar', s + '.gz')
        if os.path.exists(path):
            m = read_madis(path, ['latitude', 'longitude'], ['stationName'])
            metar_ids |= set(m['stationName'][in_box(m['latitude'], m['longitude'])])
    not_metar = ~np.isin(r['stationId'], list(metar_ids))
    say(f'  METAR stations in box {len(metar_ids)}; mesonet records dropped as METAR duplicates '
        f'{(~not_metar).sum()} ({len(set(r["stationId"][~not_metar]))} stations)')

    # --- 2b. sites near a METAR report of the window -----------------------------------------
    m_lat, m_lon, m_files = metar_window_locations(args.case_dir, t)
    near_metar = km_to_nearest(r['latitude'], r['longitude'], m_lat, m_lon) < args.metar_radius_km
    say(f'  METAR reports in window {m_lat.size} (from {", ".join(os.path.basename(f) for f in m_files)}); '
        f'mesonet records within {args.metar_radius_km} km of one {(near_metar & not_metar).sum()} '
        f'({len(set(r["stationId"][near_metar & not_metar]))} stations), dropped')

    # --- 2c. elevation in feet ----------------------------------------------------------------
    h_model, in_domain = model_terrain(args.grid_file, r['latitude'], r['longitude'])
    z = r['elevation'].astype(np.float64)
    feet = in_domain & (np.abs(z - h_model) > FEET_METRE_MISFIT) & (np.abs(z / FT - h_model) < FEET_FIT)

    # --- 3, 4. accepted and usable, per variable ---------------------------------------------
    def present(v):
        x = r[v]
        return (x != attrs[v]['_FillValue']) & (x != attrs[v]['missing_value'])

    passed = {v: present(v) & (r[v + 'QCR'] == 0) for v in VALUES}
    prov8 = np.array([p[:8] for p in r['dataProvider']])
    in_p4 = np.isin(prov8, list(p4))
    if args.option == 'a':
        acc_t = acc_q = acc_alt = np.ones(n, bool)
        acc_w = np.isin(r['dataProvider'], list(p1)) | \
            np.array([(p, s) in s2 for p, s in zip(r['dataProvider'], r['stationId'])])
    elif args.option == 'b1':
        acc_t = in_p4 | np.isin(r['stationId'], list(s1['temperature']))
        acc_q = in_p4 | np.isin(r['stationId'], list(s1['dewpoint']))
        acc_w = in_p4 | np.isin(r['stationId'], list(s1['wind']))
        acc_alt = in_p4
    else:
        acc_t = acc_q = acc_w = acc_alt = in_p4
    calm = passed['windSpeed'] & (r['windSpeed'] < CALM)
    use_t = passed['temperature'] & acc_t
    use_w = passed['windSpeed'] & passed['windDir'] & acc_w
    if args.calm == 'drop':
        use_w &= ~calm
    use_alt = passed['altimeter'] & acc_alt
    use_q = passed['dewpoint'] & acc_q & use_t & passed['altimeter']
    usable = (use_t | use_q | use_w | use_alt) & not_metar
    any_use = usable & ~near_metar & ~feet

    # --- 5. one record per site, closest to t -------------------------------------------------
    dt_abs = np.abs(r['observationTime'] - t)
    n_use = use_t.astype(int) + use_q + use_w + use_alt
    rank = lambda i: (dt_abs[i], -n_use[i], r['observationTime'][i])

    def one_per_site(mask):
        best = {}
        for i in np.flatnonzero(mask):
            key = (round(float(r['latitude'][i]), 4), round(float(r['longitude'][i]), 4))
            j = best.get(key)
            if j is None or rank(i) < rank(j):
                best[key] = i
        return np.array(sorted(best.values()), dtype=int)

    sel = one_per_site(any_use)
    # What rules 2b and 2c removed, as the obs those sites would have given (same one-per-site choice;
    # a site near a METAR with feet elevation counts under 2b).
    for rule, mask in [('2b near METAR', usable & near_metar), ('2c feet', usable & ~near_metar & feet)]:
        k = one_per_site(mask)
        say(f'  removed by {rule}: sites {k.size}, obs T {use_t[k].sum()}, q {use_q[k].sum()}, '
            f'wind {use_w[k].sum()} (u and v each), altimeter {use_alt[k].sum()}; by provider '
            + ', '.join(f'{p} {c}' for p, c in collections.Counter(r['dataProvider'][k]).most_common()))
    kf = one_per_site(usable & ~near_metar & feet)
    with open(os.path.join(args.out_dir, 'dropped_feet.csv'), 'w', newline='') as fcsv:
        w = csv.writer(fcsv)
        w.writerow(['provider', 'station', 'lat', 'lon', 'elev_reported', 'elev_as_feet_m', 'model_terrain_m'])
        for i in kf:
            w.writerow([r['dataProvider'][i], r['stationId'][i], f"{r['latitude'][i]:.4f}", f"{r['longitude'][i]:.4f}",
                        f'{z[i]:.1f}', f'{z[i] / FT:.1f}', f'{h_model[i]:.1f}'])
    ids_any = {(r['dataProvider'][i], r['stationId'][i]) for i in np.flatnonzero(any_use)}
    say(f'  (provider, station) pairs with a usable report {len(ids_any)}, sites {sel.size}')
    alt_out = use_alt | use_q          # altimeter written where usable, or kept for q
    say(f'  per variable (selected records): '
        f'T {use_t[sel].sum()}, q {use_q[sel].sum()}, wind {use_w[sel].sum()} '
        f'(calm {(use_w & calm)[sel].sum()}), altimeter {use_alt[sel].sum()}'
        + (f', altimeter kept for q {(alt_out & ~use_alt)[sel].sum()}' if args.option != 'a' else ''))
    byprov = collections.Counter(r['dataProvider'][sel])
    say('  stations by provider: ' + ', '.join(f'{p} {k}' for p, k in byprov.most_common()))
    off = np.abs(r['observationTime'][sel] - t)
    say(f'  |obs time - t| of selected records: median {np.median(off):.0f} s, max {off.max():.0f} s')

    # --- outputs -----------------------------------------------------------------------------
    out = {v: r[v][sel].astype(np.float32 if v != 'observationTime' else np.float64)
           for v in ['latitude', 'longitude', 'elevation', 'observationTime']}
    masks = {'temperature': use_t, 'dewpoint': use_q, 'altimeter': alt_out,
             'windDir': use_w, 'windSpeed': use_w}
    for v in VALUES:
        out[v] = np.where(masks[v][sel], r[v][sel], MISSING).astype(np.float32)
    with nc.Dataset(os.path.join(args.out_dir, 'mesonet_input.nc'), 'w', format='NETCDF3_64BIT_OFFSET') as f:
        f.createDimension('recNum', None)
        for v, x in out.items():
            var = f.createVariable(v, x.dtype, ('recNum',), fill_value=attrs[v]['_FillValue'])
            var.missing_value = np.array(MISSING, dtype=x.dtype)
            var[:] = x
        for q in QCRS:
            var = f.createVariable(q, 'i4', ('recNum',))
            var[:] = np.zeros(sel.size, 'i4')    # only usable values are left; missing ones are -9999
        f.title = f'MADIS mesonet selected for {args.stamp} by select_mesonet_cycle.py ' \
                  f'(option {args.option}, calm {args.calm})'

    with open(os.path.join(args.out_dir, 'selected.csv'), 'w', newline='') as fcsv:
        w = csv.writer(fcsv)
        w.writerow(['provider', 'station', 'lat', 'lon', 'elev_m', 'obs_time_utc', 'dt_s',
                    'T_K', 'Td_K', 'altimeter_Pa', 'wdir_deg', 'wspd_ms',
                    'use_T', 'use_q', 'use_wind', 'use_altimeter', 'altimeter_for_q_only', 'calm'])
        for i in sel:
            w.writerow([r['dataProvider'][i], r['stationId'][i], f"{r['latitude'][i]:.4f}",
                        f"{r['longitude'][i]:.4f}", f"{r['elevation'][i]:.1f}",
                        dt.datetime.fromtimestamp(r['observationTime'][i], dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
                        int(r['observationTime'][i] - t)]
                       + [f'{r[v][i]:.2f}' if passed[v][i] else '' for v in
                          ['temperature', 'dewpoint', 'altimeter', 'windDir', 'windSpeed']]
                       + [int(use_t[i]), int(use_q[i]), int(use_w[i]), int(use_alt[i]),
                          int(alt_out[i] and not use_alt[i]), int(calm[i])])
    say(f'  wrote {sel.size} records to {args.out_dir}/mesonet_input.nc and selected.csv')
    log.close()


if __name__ == '__main__':
    main()
