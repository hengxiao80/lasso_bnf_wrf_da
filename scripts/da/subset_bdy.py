"""Copy consecutive records of a WRF lateral boundary file (wrfbdy) into a new file.

Usage: .venv/bin/python scripts/da/subset_bdy.py <in_wrfbdy> <out_wrfbdy> --records N
           (--start YYYY-MM-DD_HH:MM:SS | --time-from <state file>)

--start: the first record is the one whose Times is exactly that time.
--time-from: the first record is the one containing the state file's time (its Times): the last record
  that starts at or before it. Used by refit_member_bdy.sh (BDY_RECORDS) so that each cycle's member
  boundary file holds only the record of the analysis time and the next one, not all 32 (option A of
  notes/fulltest_steps.md A6, 2026-11-07).
All variables are copied with the source's storage (format, compression, chunking) and attributes;
variables without a Time dimension are copied whole. Fails if fewer than N records are left from the
first one. Written to <out>.tmp, then renamed.
make_subset() was build_member_bdy.py's subset step (pilot step 6) until 2026-11-07; it imports it from here.
"""

import argparse
import os

import netCDF4
import numpy as np


def times(ds):
    return [b"".join(t).decode() for t in np.asarray(ds["Times"][:])]


def make_subset(src_path, out_path, start, hours, quiet=False):
    """Copy records start .. start + hours - 1 h of a wrfbdy file (all variables, same storage)."""
    with netCDF4.Dataset(src_path) as src:
        all_times = times(src)
        first = all_times.index(start)
        recs = slice(first, first + hours)
        if len(all_times[recs]) != hours:
            raise SystemExit(f"{src_path} has only {len(all_times) - first} records from {start}")
        tmp = out_path + ".tmp"
        with netCDF4.Dataset(tmp, "w", format=src.data_model) as out:
            out.setncatts({a: src.getncattr(a) for a in src.ncattrs()})
            for name, dim in src.dimensions.items():
                out.createDimension(name, None if dim.isunlimited() else len(dim))
            for name, var in src.variables.items():
                # No chunk cache: each chunk is read and written once, and netCDF keeps every variable's
                # cache until the file closes (a 32-record subset peaked at 15 GB with the defaults).
                if src.data_model == "NETCDF4":
                    var.set_var_chunk_cache(size=0)
                filt = var.filters() or {}
                chunks = var.chunking()
                v = out.createVariable(name, var.dtype, var.dimensions,
                                       zlib=bool(filt.get("zlib")), complevel=filt.get("complevel") or 4,
                                       shuffle=bool(filt.get("shuffle")),
                                       chunksizes=None if chunks == "contiguous" else chunks)
                v.setncatts({a: var.getncattr(a) for a in var.ncattrs()})
                if out.data_model == "NETCDF4":
                    v.set_var_chunk_cache(size=0)
                v[:] = var[recs] if var.dimensions[0] == "Time" else var[:]
    os.replace(tmp, out_path)
    if not quiet:
        print(f"subset: records {first}..{first + hours - 1} ({start}, {hours} h) -> {out_path}")


def record_containing(bdy_path, state_path):
    """Times of the last record of bdy_path that starts at or before the time of state_path."""
    with netCDF4.Dataset(state_path) as st:
        t = times(st)[0]
    with netCDF4.Dataset(bdy_path) as b:
        starts = [s for s in times(b) if s <= t]   # YYYY-MM-DD_HH:MM:SS sorts as time
    if not starts:
        raise SystemExit(f"{bdy_path}: no record starts at or before {t} ({state_path})")
    return starts[-1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("out")
    p.add_argument("--records", type=int, required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--start")
    g.add_argument("--time-from")
    args = p.parse_args()
    start = args.start or record_containing(args.src, args.time_from)
    make_subset(args.src, args.out, start, args.records)


if __name__ == "__main__":
    main()
