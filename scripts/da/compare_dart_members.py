#!/usr/bin/env python3
"""Compare two sets of DART-facing member files (filter analyses) variable by variable.

For each member pair: per variable, max |a - b| and max |a|; "identical" if every variable is
bit-identical. Used by slurm.filter_scaling to check that a filter run on another MPI layout or
location-box setting gives the same analysis as the reference.

Usage:
    .venv/bin/python scripts/da/compare_dart_members.py <ref_1.nc,ref_2.nc,...> <new_1.nc,new_2.nc,...>
Exit status 0 always (differences are reported, not treated as errors).
"""

import sys

import netCDF4
import numpy as np


def compare(a_path, b_path):
    worst = []
    with netCDF4.Dataset(a_path) as a, netCDF4.Dataset(b_path) as b:
        for v in a.variables:
            if v not in b.variables or a[v].dtype.kind not in 'fi' or a[v].ndim < 2:
                continue
            x = np.asarray(a[v][:], dtype=np.float64)
            y = np.asarray(b[v][:], dtype=np.float64)
            if x.shape != y.shape:
                worst.append((v, np.inf, np.nan))
                continue
            d = np.max(np.abs(x - y))
            if d > 0:
                worst.append((v, d, np.max(np.abs(x))))
    return worst


def main():
    refs, news = sys.argv[1].split(','), sys.argv[2].split(',')
    for r, n in zip(refs, news):
        worst = compare(r, n)
        if not worst:
            print(f'  {n}: identical')
        else:
            print(f'  {n}: differs in ' + ', '.join(f'{v} {d:.3g} (max |x| {m:.3g})' for v, d, m in worst))


if __name__ == '__main__':
    main()
