#!/usr/bin/env python
"""Checks for the REFL_10CM-in-restart WRF patch (patches/wrf_06d4240a_refl_10cm_restart.patch).

Usage: check_refl_restart.py <test_dir> <old_wrfrst_0015>
<test_dir> holds the three runs of slurm.refl_restart_test (patched wrf.exe):
  continuous/  cold start 00:00 -> 00:30, wrfout and wrfrst every 15 min
  from_old/    restart 00:15 -> 00:30 from <old_wrfrst_0015> (pre-patch, no REFL_10CM)
  from_new/    restart 00:15 -> 00:30 from continuous/wrfrst at 00:15
Checks:
  1. REFL_10CM is in continuous/wrfrst at 00:15 and 00:30 and equals wrfout's REFL_10CM there.
  2. continuous/wrfrst at 00:15 vs <old_wrfrst_0015> (same mean state, unpatched wrf.exe): every
     common variable identical, i.e. the rebuild changed nothing but the restart stream.
  3. from_old and from_new at 00:30 (wrfout and wrfrst): identical, i.e. whether REFL_10CM is read
     from the restart file or missing makes no difference (it is recomputed at the history step).
"""
import sys

import netCDF4
import numpy as np


def compare(fa, fb, label):
    with netCDF4.Dataset(fa) as a, netCDF4.Dataset(fb) as b:
        va, vb = set(a.variables), set(b.variables)
        common = sorted(va & vb)
        diff = []
        for v in common:
            xa, xb = a[v][:], b[v][:]
            if xa.shape != xb.shape:
                diff.append((v, 'shape'))
            elif xa.dtype.kind in 'fiu':
                xa, xb = np.asarray(xa), np.asarray(xb)
                if not np.array_equal(xa, xb, equal_nan=xa.dtype.kind == 'f'):
                    diff.append((v, float(np.nanmax(np.abs(xa.astype('f8') - xb.astype('f8'))))))
            elif not np.array_equal(np.asarray(xa), np.asarray(xb)):
                diff.append((v, 'differs'))
    print(f'{label}: {len(common)} common variables, {len(common) - len(diff)} identical, '
          f'{len(diff)} differ; only in first: {sorted(va - vb)}; only in second: {sorted(vb - va)}')
    for v, d in diff[:40]:
        print(f'    {v}: {d}')
    return diff


def main():
    test_dir, old_rst = sys.argv[1:3]
    ok = True
    c = f'{test_dir}/continuous'
    for t in ('00_15_00', '00_30_00'):
        with netCDF4.Dataset(f'{c}/wrfrst_d01_2025-05-20_{t}') as r, \
             netCDF4.Dataset(f'{c}/wrfout_d01_2025-05-20_{t}') as o:
            if 'REFL_10CM' not in r.variables:
                print(f'1. {t}: REFL_10CM NOT in wrfrst'); ok = False; continue
            x, y = np.asarray(r['REFL_10CM'][:]), np.asarray(o['REFL_10CM'][:])
            same = np.array_equal(x, y)
            ok &= same
            print(f'1. {t}: REFL_10CM in wrfrst, identical to wrfout: {same} '
                  f'(range {x.min():.1f} .. {x.max():.1f} dBZ, max |diff| {np.abs(x - y).max():.3g})')
    d = compare(f'{c}/wrfrst_d01_2025-05-20_00_15_00', old_rst, '2. new vs pre-patch wrfrst 00:15')
    ok &= not d
    for kind in ('wrfout', 'wrfrst'):
        d = compare(f'{test_dir}/from_old/{kind}_d01_2025-05-20_00_30_00',
                    f'{test_dir}/from_new/{kind}_d01_2025-05-20_00_30_00',
                    f'3. from_old vs from_new {kind} 00:30')
        ok &= not d
    print('ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED')


if __name__ == '__main__':
    main()
