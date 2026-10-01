"""Check the member boundary files written by build_member_bdy.py (pilot step 6 gate).

Usage: .venv/bin/python scripts/da/check_member_bdy.py <exp_dir> [--start 2025-05-20_00:00:00]
           [--hours 2] [--nmem 5]

Compares exp_dir/bdy/wrfbdy_d01_memNNN (and wrfbdy_d01_refit_mean, if present) with the mean subset
exp_dir/bdy/wrfbdy_d01_mean_<start>_<hours>h:
- refit_mean: B and tendency of the refit fields should reproduce the real.exe values;
- members: refit fields differ from the mean, all other variables are identical; moisture is
  non-negative at record start and end; consecutive records join up (B_h + dt * BT_h = B_(h+1));
  the member mean of B stays close to the mean file (centering), relative to the member spread.
"""

import argparse
import os

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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("exp_dir")
    p.add_argument("--start", default="2025-05-20_00:00:00")
    p.add_argument("--hours", type=int, default=2)
    p.add_argument("--nmem", type=int, default=5)
    args = p.parse_args()

    bdy = os.path.join(args.exp_dir, "bdy")
    mean = netCDF4.Dataset(os.path.join(
        bdy, f"wrfbdy_d01_mean_{args.start[:13].replace(':', '_')}_{args.hours}h"))
    refit_names = {f + "_" + k + s for f in REFIT for k in ("B", "BT") for s in SIDES}

    refit_path = os.path.join(bdy, "wrfbdy_d01_refit_mean")
    if os.path.exists(refit_path):
        ref = netCDF4.Dataset(refit_path)
        print("refit_mean vs real.exe subset: max |diff| / RMS, per field (B, tendency), worst side")
        for f in REFIT:
            rb = max(rel(ref[f"{f}_B{s}"][:], mean[f"{f}_B{s}"][:]) for s in SIDES)
            rt = max(rel(ref[f"{f}_BT{s}"][:], mean[f"{f}_BT{s}"][:]) for s in SIDES)
            print(f"   {f:7s} B {rb:9.2e}   BT {rt:9.2e}")

    paths = [os.path.join(bdy, f"wrfbdy_d01_mem{m:03d}") for m in range(1, args.nmem + 1)]
    mems = [netCDF4.Dataset(p) for p in paths if os.path.exists(p)]
    if not mems:
        return
    secs = record_seconds(mean)
    print(f"\n{len(mems)} members; record lengths {secs} s")
    for m, ds in enumerate(mems, start=1):
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
        print(f"mem{m:03d}: other vars changed {other}; refit vars left unchanged {unchanged}; "
              f"min moisture (start, end) {qmin:.2e}; max record-join error {join:.1e}")

    print("\nmember spread and member-mean offset from the mean file, RMS over the boundary zone")
    print("   field      spread    |mean offset|   ratio   (all records and sides)")
    for f in REFIT:
        stack = np.array([np.concatenate([np.asarray(ds[f"{f}_B{s}"][:], np.float64).ravel() for s in SIDES])
                          for ds in mems])
        ref = np.concatenate([np.asarray(mean[f"{f}_B{s}"][:], np.float64).ravel() for s in SIDES])
        spread = np.sqrt(stack.var(axis=0, ddof=1).mean())
        offset = np.sqrt(((stack.mean(axis=0) - ref) ** 2).mean())
        print(f"   {f:7s} {spread:11.3e} {offset:13.3e} {offset / spread if spread else np.nan:9.3f}")


if __name__ == "__main__":
    main()
