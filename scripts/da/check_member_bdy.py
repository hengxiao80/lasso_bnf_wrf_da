"""Check the member boundary files written by build_member_bdy.py (pilot step 6 gate).

Usage: .venv/bin/python scripts/da/check_member_bdy.py <exp_dir> [--start 2025-05-20_00:00:00]
           [--hours 2] [--nmem 5] [--jobs 1]

Compares exp_dir/bdy/wrfbdy_d01_memNNN (and wrfbdy_d01_refit_mean, if present) with the mean subset
exp_dir/bdy/wrfbdy_d01_mean_<start>_<hours>h:
- refit_mean: B and tendency of the refit fields should reproduce the real.exe values;
- members: refit fields differ from the mean, all other variables are identical; moisture is
  non-negative at record start and end; consecutive records join up (B_h + dt * BT_h = B_(h+1));
  the member mean of B stays close to the mean file (centering), relative to the member spread.
Since 2026-11-07 (50 members x 32 records, notes/fulltest_steps.md A6): the per-member checks and the
per-field spreads run in --jobs processes, each opening its files itself with no netCDF chunk cache, and
every result is printed (flushed) as it is ready; elapsed seconds per member and field go to stderr.
The first 50-member run, one process with buffered output, read ~480 GB and was cut off at its 2-h limit
with nothing printed (job 1194824).
"""

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import netCDF4
import numpy as np

REFIT = ["U", "V", "W", "PH", "T", "QVAPOR", "MU"]
SIDES = ["XS", "XE", "YS", "YE"]


def record_seconds(ds):
    def t(name):
        return [np.datetime64(b"".join(r).decode().replace("_", "T")) for r in np.asarray(ds[name][:])]
    this = t("md___thisbdytimee_x_t_d_o_m_a_i_n_m_e_t_a_data_")
    nxt = t("md___nextbdytimee_x_t_d_o_m_a_i_n_m_e_t_a_data_")
    return np.array([(b - a) / np.timedelta64(1, "s") for a, b in zip(this, nxt)])


def rel(a, b):
    """max |a - b| / RMS(b)"""
    scale = np.sqrt((np.asarray(b, np.float64) ** 2).mean()) or 1.0
    return np.abs(np.asarray(a, np.float64) - b).max() / scale


def opn(path):
    """Open without chunk caches: each chunk is read once, and netCDF keeps every variable's cache open."""
    ds = netCDF4.Dataset(path)
    if ds.data_model == "NETCDF4":
        for v in ds.variables.values():
            v.set_var_chunk_cache(size=0)
    return ds


def member_check(job):
    m, path, mean_path = job
    t0 = time.time()
    refit_names = {f + "_" + k + s for f in REFIT for k in ("B", "BT") for s in SIDES}
    with opn(mean_path) as mean, opn(path) as ds:
        secs = record_seconds(mean)
        other = [v for v in mean.variables if v not in refit_names
                 and not np.array_equal(np.asarray(ds[v][:]), np.asarray(mean[v][:]))]
        unchanged = [v for v in refit_names if v.startswith(tuple(f + "_B" for f in REFIT if f != "W"))
                     and np.array_equal(np.asarray(ds[v][:]), np.asarray(mean[v][:]))]
        qmin = min(min(np.asarray(ds[f"QVAPOR_B{s}"][:]).min(),
                       (np.asarray(ds[f"QVAPOR_B{s}"][:], np.float64)
                        + secs[:, None, None, None] * ds[f"QVAPOR_BT{s}"][:]).min()) for s in SIDES)
        join = max(rel(np.asarray(ds[f"{f}_B{s}"][h], np.float64) + secs[h] * ds[f"{f}_BT{s}"][h],
                       ds[f"{f}_B{s}"][h + 1])
                   for f in REFIT for s in SIDES for h in range(len(secs) - 1)) if len(secs) > 1 else np.nan
    line = (f"mem{m:03d}: other vars changed {other}; refit vars left unchanged {unchanged}; "
            f"min moisture (start, end) {qmin:.2e}; max record-join error {join:.1e}")
    return line, f"mem{m:03d} checked in {time.time() - t0:.0f} s"


def field_spread(job):
    """Member spread and member-mean offset of one refit field, summed member by member."""
    f, paths, mean_path = job
    t0 = time.time()
    with opn(mean_path) as mean:
        ref = np.concatenate([np.asarray(mean[f"{f}_B{s}"][:], np.float64).ravel() for s in SIDES])
    s1 = s2 = 0.0   # sums of d and d^2 over the members, d = member - mean file
    for path in paths:
        with opn(path) as ds:
            d = np.concatenate([np.asarray(ds[f"{f}_B{s}"][:], np.float64).ravel() for s in SIDES]) - ref
        s1 = s1 + d
        s2 = s2 + d * d
    n = len(paths)
    spread = np.sqrt((np.maximum(s2 - s1 * s1 / n, 0.0) / (n - 1)).mean())
    offset = np.sqrt(((s1 / n) ** 2).mean())
    line = f"   {f:7s} {spread:11.3e} {offset:13.3e} {offset / spread if spread else np.nan:9.3f}"
    return line, f"{f} spread in {time.time() - t0:.0f} s"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("exp_dir")
    p.add_argument("--start", default="2025-05-20_00:00:00")
    p.add_argument("--hours", type=int, default=2)
    p.add_argument("--nmem", type=int, default=5)
    p.add_argument("--jobs", type=int, default=1)
    args = p.parse_args()

    bdy = os.path.join(args.exp_dir, "bdy")
    mean_path = os.path.join(bdy, f"wrfbdy_d01_mean_{args.start[:13].replace(':', '_')}_{args.hours}h")

    refit_path = os.path.join(bdy, "wrfbdy_d01_refit_mean")
    if os.path.exists(refit_path):
        t0 = time.time()
        with opn(mean_path) as mean, opn(refit_path) as ref:
            print("refit_mean vs real.exe subset: max |diff| / RMS, per field (B, tendency), worst side")
            for f in REFIT:
                rb = max(rel(ref[f"{f}_B{s}"][:], mean[f"{f}_B{s}"][:]) for s in SIDES)
                rt = max(rel(ref[f"{f}_BT{s}"][:], mean[f"{f}_BT{s}"][:]) for s in SIDES)
                print(f"   {f:7s} B {rb:9.2e}   BT {rt:9.2e}", flush=True)
        print(f"refit_mean checked in {time.time() - t0:.0f} s", file=sys.stderr, flush=True)

    paths = [os.path.join(bdy, f"wrfbdy_d01_mem{m:03d}") for m in range(1, args.nmem + 1)]
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        return
    with opn(mean_path) as mean:
        secs = record_seconds(mean)
    print(f"\n{len(paths)} members; record lengths {secs} s", flush=True)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for line, timing in pool.map(member_check, [(m, path, mean_path) for m, path in enumerate(paths, start=1)]):
            print(line, flush=True)
            print(timing, file=sys.stderr, flush=True)

        print("\nmember spread and member-mean offset from the mean file, RMS over the boundary zone")
        print("   field      spread    |mean offset|   ratio   (all records and sides)", flush=True)
        for line, timing in pool.map(field_spread, [(f, paths, mean_path) for f in REFIT]):
            print(line, flush=True)
            print(timing, file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
