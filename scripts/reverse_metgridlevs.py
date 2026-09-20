#!/usr/bin/env python3
"""Reverse the vertical order of HRRR native-level met_em files, in place.

ungrib/metgrid write the HRRR hybrid levels as [surface, model top ... lowest
level]. real.exe needs [surface, lowest ... model top] (pressure decreasing
upward). Level 0 (the surface entry) stays put; levels 1..N-1 are flipped, for
every variable that has a num_metgrid_levels dimension.

Safe to re-run: a reversed file carries the global attribute
BNF_METGRID_LEVELS_REVERSED = 1 and is skipped. Each file is rewritten to a
temporary name and swapped in atomically; the untouched original is kept in
--backup-dir (default: raw_metgrid/) so metgrid never has to be rerun.

Usage:
    .venv/bin/python scripts/reverse_metgridlevs.py cases/20250520/wps
"""

import argparse
import glob
import os
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from netCDF4 import Dataset

MARK = "BNF_METGRID_LEVELS_REVERSED"


def is_reversed(path):
    with Dataset(path) as nc:
        return MARK in nc.ncattrs()


def check_bottom_up(nc, where):
    # After reversal PRES at a mid-domain column must fall with height.
    p = nc["PRES"][0, :, nc.dimensions["south_north"].size // 2,
                   nc.dimensions["west_east"].size // 2]
    if not (p[1] > p[2] > p[-1]):
        raise RuntimeError("%s: PRES not decreasing upward after reversal: %s"
                           % (where, np.asarray(p)[:4]))


def reverse_file(args):
    path, backup_dir = args
    name = os.path.basename(path)
    raw_path = os.path.join(backup_dir, name)

    # Crash recovery: original already moved to backup but new file not swapped in.
    if not os.path.exists(path) and os.path.exists(raw_path):
        src = raw_path
    elif os.path.exists(path):
        if is_reversed(path):
            return name, "skipped (already reversed)"
        src = path
    else:
        raise FileNotFoundError(path)

    tmp = path + ".reversing"
    shutil.copyfile(src, tmp)
    nvars = 0
    with Dataset(tmp, "r+") as nc:
        if "num_metgrid_levels" not in nc.dimensions:
            raise RuntimeError("%s has no num_metgrid_levels dimension" % name)
        nlev = nc.dimensions["num_metgrid_levels"].size
        order = [0] + list(range(nlev - 1, 0, -1))
        for vname, var in nc.variables.items():
            if "num_metgrid_levels" not in var.dimensions:
                continue
            k = var.dimensions.index("num_metgrid_levels")
            data = var[:]
            var[:] = np.take(data, order, axis=k)
            nvars += 1
        setattr(nc, MARK, np.int32(1))
        check_bottom_up(nc, name)

    if src == path:
        os.makedirs(backup_dir, exist_ok=True)
        os.replace(path, raw_path)
    os.replace(tmp, path)
    return name, "reversed %d variables (nlev=%d)" % (nvars, nlev)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", help="directory containing met_em.d*.nc")
    ap.add_argument("--pattern", default="met_em.d*.nc")
    ap.add_argument("--backup-dir", default=None,
                    help="default: <directory>/raw_metgrid")
    ap.add_argument("--workers", type=int, default=min(16, os.cpu_count() or 1))
    args = ap.parse_args()

    backup = args.backup_dir or os.path.join(args.directory, "raw_metgrid")
    files = sorted(glob.glob(os.path.join(args.directory, args.pattern)))
    # also pick up files whose original was already moved aside by an interrupted run
    for raw in sorted(glob.glob(os.path.join(backup, args.pattern))):
        target = os.path.join(args.directory, os.path.basename(raw))
        if target not in files:
            files.append(target)
    if not files:
        print("No files matching %s in %s" % (args.pattern, args.directory))
        return 1

    with ProcessPoolExecutor(max_workers=min(args.workers, len(files))) as ex:
        results = list(ex.map(reverse_file, [(f, backup) for f in files]))
    for name, msg in results:
        print("%s: %s" % (name, msg))
    print("Done: %d files." % len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
