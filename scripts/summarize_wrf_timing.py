#!/usr/bin/env python3
"""Summarize WRF timing from rsl logs (and wrfout format) for I/O/decomposition tests.

For each run directory (with rsls/rsl.out.* or rsl.out.* in it):
  - compute-only step time: median / mean of 'Timing for main' steps that are not
    write-stalled (< STALL s)
  - stalled steps: count and total time (a step containing a synchronous write shows
    up as one very long step)
  - total time-stepping wall (sum of all 'Timing for main')
  - 'Timing for Writing' times seen on any rank (for quilted runs these come from
    the I/O server ranks)
  - wrfout on-disk format

Usage:
    uv run python3 scripts/summarize_wrf_timing.py cases/20250520/iotest/*/
"""

import glob
import os
import re
import statistics as st
import subprocess
import sys

STALL = 10.0
MAIN = re.compile(r"Timing for main: time (\S+) on domain\s+1:\s+([\d.]+) elapsed")
WRITE = re.compile(r"Timing for Writing (\S+) for domain\s+1:\s+([\d.]+) elapsed")


def rsl_files(d):
    for sub in ("rsls", "."):
        fs = sorted(glob.glob(os.path.join(d, sub, "rsl.out.*")))
        if fs:
            return fs
    return []


def summarize(d):
    files = rsl_files(d)
    if not files:
        return "%s: no rsl files" % os.path.basename(d.rstrip("/"))
    main, writes = [], []
    for i, f in enumerate(files):
        for line in open(f, errors="replace"):
            m = MAIN.search(line)
            if m and i == 0:
                main.append(float(m.group(2)))
            m = WRITE.search(line)
            if m:
                writes.append((os.path.basename(f), m.group(1), float(m.group(2))))
    ok = "SUCCESS COMPLETE WRF" in open(files[0], errors="replace").read()
    out = ["== %s  (%d rsl files, run %s)" % (os.path.basename(d.rstrip("/")), len(files), "COMPLETED" if ok else "NOT COMPLETED")]
    if main:
        norm = [t for t in main if t < STALL]
        stall = [t for t in main if t >= STALL]
        out.append("   steps=%d | compute step median %.3f s, mean %.3f s | stalled steps %d (sum %.0f s) | total time-stepping %.0f s" % (
            len(main), st.median(norm), st.mean(norm), len(stall), sum(stall), sum(main)))
    if writes:
        ts = [w[2] for w in writes]
        ranks = sorted(set(w[0] for w in writes))
        out.append("   history writes seen=%d on %d rank log(s): %s s (mean %.0f)" % (
            len(writes), len(ranks), ", ".join("%.0f" % t for t in ts[:8]), st.mean(ts)))
    wo = sorted(glob.glob(os.path.join(d, "wrfout_d01_*")))
    if wo:
        fmt = subprocess.run(["ncdump", "-k", wo[-1]], stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()
        out.append("   wrfout: %d file(s), %.2f GB each, format: %s" % (len(wo), os.path.getsize(wo[-1]) / 1e9, fmt))
    return "\n".join(out)


if __name__ == "__main__":
    for d in sys.argv[1:]:
        if os.path.isdir(d):
            print(summarize(d))
