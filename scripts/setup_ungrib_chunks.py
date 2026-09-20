#!/usr/bin/env python3
"""Split an ungrib run into per-time-chunk working directories.

ungrib.exe is serial, but each hourly analysis is independent, so the time
range can be split across a Slurm job array. This creates, under
<wps-dir>/ungrib_chunks/chunk_NN/:
  - namelist.wps  (parent namelist with start_date/end_date set to the chunk)
  - Vtable        (link to the parent's Vtable)
  - ungrib.exe    (link to the parent's ungrib.exe)
  - GRIBFILE.*    (links to that chunk's HRRR wrfprs then wrfnat f00 files)

It only creates directories and links; it does not run anything. After the
array job finishes, scripts/merge_ungrib_chunks.py moves the FILE:* outputs
into <wps-dir>.

Usage:
    uv run python3 scripts/setup_ungrib_chunks.py cases/20250520/wps --chunk-hours 6
"""

import argparse
import datetime as dt
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from link_hrrr_gribfiles import DEFAULT_HRRR_ROOT, hours, source_path, suffixes  # noqa: E402

DATE_FMT = "%Y-%m-%d_%H:%M:%S"


def read_window(namelist_text):
    s = re.search(r"start_date\s*=\s*'([^']+)'", namelist_text).group(1)
    e = re.search(r"end_date\s*=\s*'([^']+)'", namelist_text).group(1)
    return dt.datetime.strptime(s, DATE_FMT), dt.datetime.strptime(e, DATE_FMT)


def chunk_namelist(text, start, end):
    text = re.sub(r"(start_date\s*=\s*)'[^']+'", r"\g<1>'%s'" % start.strftime(DATE_FMT), text, count=1)
    text = re.sub(r"(end_date\s*=\s*)'[^']+'", r"\g<1>'%s'" % end.strftime(DATE_FMT), text, count=1)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wps_dir")
    ap.add_argument("--chunk-hours", type=int, default=6)
    ap.add_argument("--hrrr-root", default=DEFAULT_HRRR_ROOT)
    args = ap.parse_args()

    wps = os.path.abspath(args.wps_dir)
    text = open(os.path.join(wps, "namelist.wps")).read()
    if not re.search(r"max_dom\s*=\s*1\s*,", text):
        print("ERROR: expected max_dom = 1 in %s/namelist.wps" % wps)
        return 1
    start, end = read_window(text)
    all_hours = list(hours(start, end))

    chunks = [all_hours[i:i + args.chunk_hours] for i in range(0, len(all_hours), args.chunk_hours)]

    missing = [source_path(args.hrrr_root, k, t) for t in all_hours for k in ("prs", "nat")
               if not os.path.isfile(source_path(args.hrrr_root, k, t))]
    if missing:
        print("ERROR: %d HRRR files missing, e.g. %s" % (len(missing), missing[0]))
        return 1

    base = os.path.join(wps, "ungrib_chunks")
    if os.path.exists(base):
        shutil.rmtree(base)
    os.makedirs(base)

    vtable = os.path.realpath(os.path.join(wps, "Vtable"))
    exe = os.path.realpath(os.path.join(wps, "ungrib.exe"))

    with open(os.path.join(base, "chunks.txt"), "w") as manifest:
        for n, hrs in enumerate(chunks):
            d = os.path.join(base, "chunk_%02d" % n)
            os.makedirs(d)
            with open(os.path.join(d, "namelist.wps"), "w") as f:
                f.write(chunk_namelist(text, hrs[0], hrs[-1]))
            os.symlink(vtable, os.path.join(d, "Vtable"))
            os.symlink(exe, os.path.join(d, "ungrib.exe"))
            srcs = [source_path(args.hrrr_root, k, t) for k in ("prs", "nat") for t in hrs]
            for suffix, src in zip(suffixes(), srcs):
                os.symlink(src, os.path.join(d, "GRIBFILE." + suffix))
            manifest.write("chunk_%02d %s %s %d\n" % (
                n, hrs[0].strftime(DATE_FMT), hrs[-1].strftime(DATE_FMT), len(hrs)))

    print("%d hourly times -> %d chunks of up to %d h in %s" % (
        len(all_hours), len(chunks), args.chunk_hours, base))
    print("Slurm array range: --array=0-%d" % (len(chunks) - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
