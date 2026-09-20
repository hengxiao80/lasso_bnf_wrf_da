#!/usr/bin/env python3
"""Move ungrib FILE:* outputs from ungrib_chunks/chunk_NN/ into the WPS directory.

Refuses to move anything unless every chunk's ungrib.log reports successful
completion and the full set of expected hourly FILE:* files is present. Moves
are renames on the same filesystem (instant). Existing FILE:* in the WPS
directory are never overwritten.

Usage:
    uv run python3 scripts/merge_ungrib_chunks.py cases/20250520/wps [--dry-run]
"""

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from setup_ungrib_chunks import DATE_FMT  # noqa: E402
import datetime as dt  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wps_dir")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    wps = os.path.abspath(args.wps_dir)
    base = os.path.join(wps, "ungrib_chunks")
    problems = []
    plan = []

    for line in open(os.path.join(base, "chunks.txt")):
        name, s, e, n = line.split()
        s = dt.datetime.strptime(s, DATE_FMT)
        d = os.path.join(base, name)
        log = os.path.join(d, "ungrib.log")
        if not os.path.isfile(log) or "Successful completion of program ungrib.exe" not in open(log, errors="replace").read():
            problems.append("%s: ungrib.log missing or not successful" % name)
            continue
        expected = ["FILE:" + (s + dt.timedelta(hours=i)).strftime("%Y-%m-%d_%H") for i in range(int(n))]
        for fn in expected:
            src = os.path.join(d, fn)
            if not os.path.isfile(src):
                problems.append("%s: missing %s" % (name, fn))
            elif os.path.exists(os.path.join(wps, fn)):
                problems.append("%s already exists in %s (not overwriting)" % (fn, wps))
            else:
                plan.append((src, os.path.join(wps, fn)))
        stray = [p for p in glob.glob(os.path.join(d, "PFILE:*"))]
        if stray:
            problems.append("%s: leftover temporary %s" % (name, os.path.basename(stray[0])))

    if problems:
        print("NOT merging; %d problem(s):" % len(problems))
        for p in problems:
            print("  - " + p)
        return 1

    print("%d FILE:* files ready to merge into %s" % (len(plan), wps))
    if args.dry_run:
        print("(dry run, nothing moved)")
        return 0
    for src, dst in plan:
        os.rename(src, dst)
    print("Moved %d files." % len(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
