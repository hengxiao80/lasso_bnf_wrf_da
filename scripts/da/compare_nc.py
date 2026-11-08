#!/usr/bin/env python3
"""Compare two netCDF files variable by variable (fulltest_steps.md B1 and later tests).

Prints the variables found in only one of the files, then, for every variable in both, whether it is
bit-identical (same shape, same bytes); for those that are not, max |a - b| and max |a| (numeric) or
"differs" (characters). All variables are compared, scalars and Times included. One variable is read
at a time, without netCDF chunk caches (fulltest_steps.md A6: the caches stay until a file closes).

Usage:
    .venv/bin/python scripts/da/compare_nc.py <a.nc> <b.nc> [--skip VAR,VAR,...] [--suffix2]
--suffix2: a variable of a that b lacks is compared with b's <name>_2 if b has it (a WRF restart file
stores the current time level of U, V, W, PH, THM, MU, PC, ... as <name>_2, a history file as <name>).
Exit status 0 if every common variable not skipped is bit-identical, 1 otherwise (variables found in
only one file don't count).
"""

import argparse
import sys

import netCDF4
import numpy as np


def read(ds, name):
    v = ds[name]
    v.set_auto_maskandscale(False)
    if ds.data_model.startswith('NETCDF4') and v.chunking() != 'contiguous':
        v.set_var_chunk_cache(size=0)
    return np.asarray(v[...])


def names(lst, n=30):
    return ' '.join(lst[:n]) + (f' ... and {len(lst) - n} more' if len(lst) > n else '') if lst else '-'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('a')
    p.add_argument('b')
    p.add_argument('--skip', default='', help='comma-separated variables not to compare')
    p.add_argument('--suffix2', action='store_true', help="compare a's X with b's X_2 if b has no X")
    args = p.parse_args()
    skip = set(filter(None, args.skip.split(',')))
    with netCDF4.Dataset(args.a) as a, netCDF4.Dataset(args.b) as b:
        va, vb = list(a.variables), set(b.variables)
        pair = {v: v for v in va if v in vb}
        if args.suffix2:
            pair.update({v: v + '_2' for v in va if v not in vb and v + '_2' in vb})
        only_a = [v for v in va if v not in pair]
        only_b = sorted(vb - set(pair.values()))
        common = [v for v in va if v in pair and v not in skip]
        print(f'a: {args.a} ({len(va)} variables)')
        print(f'b: {args.b} ({len(vb)} variables)')
        print(f'only in a ({len(only_a)}): {names(only_a)}')
        print(f'only in b ({len(only_b)}): {names(only_b)}')
        renamed = [f'{v}={w}' for v, w in pair.items() if v != w]
        if renamed:
            print(f'compared under another name in b ({len(renamed)}): {names(renamed)}')
        if skip:
            print(f'skipped ({len(skip)}): {" ".join(sorted(skip))}')
        differ = []
        for v in common:
            x, y = read(a, v), read(b, pair[v])
            if x.shape != y.shape or x.dtype != y.dtype:
                differ.append(f'   {v}: shape/type {x.shape} {x.dtype} vs {y.shape} {y.dtype}')
            elif x.tobytes() != y.tobytes():
                if x.dtype.kind in 'fiu':
                    x64, y64 = x.astype(np.float64), y.astype(np.float64)
                    n = int(np.count_nonzero(x64 != y64))
                    differ.append(f'   {v}: max |a-b| {np.nanmax(np.abs(x64 - y64)):.6g}, max |a| '
                                  f'{np.nanmax(np.abs(x64)):.6g}, {n} of {x.size} values differ')
                else:
                    differ.append(f'   {v}: differs')
        print(f'common: {len(common)}, bit-identical: {len(common) - len(differ)}, differ: {len(differ)}')
        for line in differ:
            print(line)
    sys.exit(1 if differ else 0)


if __name__ == '__main__':
    main()
