#!/usr/bin/env python3
"""Create WPS GRIBFILE.AAA, AAB, ... symlinks to HRRR f00 analyses.

Mirrors the ordering used for the existing 20250520 runs (all wrfprs f00 hours
first, then all wrfnat f00 hours). Aborts before touching anything if any
expected source file is missing.

Usage (from the WPS run directory, or with --dest):
    uv run python3 scripts/link_hrrr_gribfiles.py \
        --start 2025-05-19T00 --end 2025-05-22T00 --dest cases/20250520/wps
"""

import argparse
import datetime as dt
import itertools
import os
import string
import sys

DEFAULT_HRRR_ROOT = "/gpfs/wolf2/arm/cli120/proj-shared/sey/bnf/wrf/forcing/hrrr"


def suffixes():
    letters = string.ascii_uppercase
    for a, b, c in itertools.product(letters, repeat=3):
        yield a + b + c


def hours(start, end):
    t = start
    while t <= end:
        yield t
        t += dt.timedelta(hours=1)


def source_path(root, kind, t):
    subdir = {"prs": "hrrr_data", "nat": "hrrrnat_data"}[kind]
    return "%s/%s/%s/hrrr.t%sz.wrf%sf00.grib2" % (
        root, subdir, t.strftime("%Y%m%d"), t.strftime("%H"), kind)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DDTHH (UTC)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DDTHH (UTC), inclusive")
    ap.add_argument("--dest", default=".")
    ap.add_argument("--hrrr-root", default=DEFAULT_HRRR_ROOT)
    args = ap.parse_args()

    fmt = "%Y-%m-%dT%H"
    start = dt.datetime.strptime(args.start, fmt)
    end = dt.datetime.strptime(args.end, fmt)

    sources = []
    for kind in ("prs", "nat"):
        for t in hours(start, end):
            sources.append(source_path(args.hrrr_root, kind, t))

    missing = [p for p in sources if not os.path.isfile(p)]
    if missing:
        print("ERROR: %d expected HRRR files missing, e.g. %s" % (len(missing), missing[0]))
        return 1

    for old in os.listdir(args.dest):
        if old.startswith("GRIBFILE."):
            os.remove(os.path.join(args.dest, old))

    for suffix, src in zip(suffixes(), sources):
        os.symlink(src, os.path.join(args.dest, "GRIBFILE." + suffix))

    print("Linked %d files (%d hours x prs+nat) into %s" % (
        len(sources), len(sources) // 2, args.dest))
    print("first: %s" % sources[0])
    print("last:  %s" % sources[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
