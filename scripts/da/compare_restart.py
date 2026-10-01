"""Compare a continuous WRF run with one restarted from its own wrfout (pilot step 7 gate).

Usage: .venv/bin/python scripts/da/compare_restart.py <continuous_dir> <restart_dir> <iofields_file>
           [--restart-time 2025-05-20_00_15_00] [--end-time 2025-05-20_00_30_00]
           [--restart-file wrfrst_d01_...]

1. The fields listed in the iofields file are in every wrfout of the continuous run.
2. Restart start frame: the restarted run's first history frame against the continuous run's frame
   at the restart time (it was read from that file), listing every variable that changed. These are
   what a cold start re-initializes or re-diagnoses.
3. End: both runs' frames at --end-time, per variable: RMS difference divided by the RMS of the
   continuous run's change over the segment (restart error relative to the 15-min evolution), and
   the max abs difference; and how many of all variables are bit-identical.
4. With --restart-file: which of the fields DART, update_wrf_bc and the post-filter recompute
   need are in that WRF restart file, its size and its number of variables.
"""

import argparse
import glob
import os

import netCDF4
import numpy as np

RESTART_NEEDS = {
    "DART state": ["U", "V", "W", "PH", "THM", "MU", "QVAPOR", "PSFC", "T2", "Q2", "U10", "V10",
                   "QCLOUD", "QRAIN", "QICE", "QSNOW", "QGRAUP", "QNICE", "QNRAIN", "Times"],
    "update_wrf_bc": ["U", "V", "W", "PH", "T", "QVAPOR", "MU", "MUB", "MAPFAC_U", "MAPFAC_V",
                      "MAPFAC_M"],
    "recompute P/AL": ["P", "AL", "ALT", "P_HYD", "P_HYD_W", "PB", "ALB", "PHB", "MUB", "C3F", "C4F",
                       "C3H", "C4H", "P_TOP", "PHP", "WW"],
    "kept by restart": ["TKE_PBL", "EL_PBL", "CANWAT", "RAINNC", "RTHRATEN", "H_DIABATIC"],
}

KEY = ["U", "V", "W", "T", "QVAPOR", "QCLOUD", "QRAIN", "QICE", "QSNOW", "QGRAUP", "MU", "PH", "P",
       "PSFC", "T2", "Q2", "U10", "V10", "TSK", "HFX", "LH", "PBLH", "RAINNC", "REFL_10CM", "SWDOWN",
       "TSLB", "SMOIS", "QNWFA", "QNIFA", "QNCLOUD", "QNRAIN", "QNICE"]


def arr(ds, name):
    return np.asarray(ds[name][:], np.float64)


def start_frame(a0, b0):
    print("   variables that changed (max |diff| / RMS of the field):")
    same = 0
    for n, v in a0.variables.items():
        if n == "Times" or n not in b0.variables or v.dtype.kind not in "fi":
            continue
        x, y = arr(a0, n), arr(b0, n)
        if np.array_equal(x, y):
            same += 1
            continue
        scale = np.sqrt((x ** 2).mean()) or 1.0
        print(f"      {n:14s} {np.abs(x - y).max() / scale:9.2e}   ({v.getncattr('description')[:50]})")
    print(f"   {same} variables identical")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cont_dir")
    p.add_argument("rest_dir")
    p.add_argument("iofields")
    p.add_argument("--restart-time", default="2025-05-20_00_15_00")
    p.add_argument("--end-time", default="2025-05-20_00_30_00")
    p.add_argument("--restart-file")
    args = p.parse_args()

    names = open(args.iofields).read().strip().split(":", 3)[3].split(",")
    print(f"1. the {len(names)} iofields fields in the continuous run's wrfout files")
    for f in sorted(glob.glob(os.path.join(args.cont_dir, "wrfout_d01_*"))):
        with netCDF4.Dataset(f) as ds:
            missing = [n for n in names if n not in ds.variables]
        print(f"   {os.path.basename(f)}: missing {missing if missing else 'none'}")

    a0 = netCDF4.Dataset(os.path.join(args.cont_dir, f"wrfout_d01_{args.restart_time}"))
    b0_path = os.path.join(args.rest_dir, f"wrfout_d01_{args.restart_time}")
    print(f"\n2. restart start frame ({args.restart_time}) vs the continuous run's frame it was read from")
    if not os.path.exists(b0_path):
        print("   no history frame at the restart time (true restart): skipped")
    else:
        start_frame(a0, netCDF4.Dataset(b0_path))

    a1 = netCDF4.Dataset(os.path.join(args.cont_dir, f"wrfout_d01_{args.end_time}"))
    b1 = netCDF4.Dataset(os.path.join(args.rest_dir, f"wrfout_d01_{args.end_time}"))
    print(f"\n3. end ({args.end_time}): RMS(restart - continuous) / RMS(continuous change over the segment),"
          " and max |diff|")
    for n in KEY:
        if n not in a1.variables:
            continue
        x, y, x0 = arr(a1, n), arr(b1, n), arr(a0, n)
        change = np.sqrt(((x - x0) ** 2).mean())
        diff = np.sqrt(((y - x) ** 2).mean())
        ratio = diff / change if change else (0.0 if diff == 0 else np.inf)
        print(f"   {n:10s} {ratio:9.3f}   max |diff| {np.abs(y - x).max():10.3g} {a1[n].getncattr('units')}")
    same, differ = 0, []
    for n, v in a1.variables.items():
        if n == "Times" or n not in b1.variables or v.dtype.kind not in "fi":
            continue
        if np.array_equal(np.asarray(v[:]), np.asarray(b1[n][:])):
            same += 1
        else:
            differ.append(n)
    print(f"   bit-identical: {same} variables; differ: {len(differ)} {differ[:40]}")

    if args.restart_file:
        print(f"\n4. restart file {args.restart_file}: {os.path.getsize(args.restart_file) / 1e9:.2f} GB")
        with netCDF4.Dataset(args.restart_file) as r:
            print(f"   {len(r.variables)} variables, format {r.data_model}")
            for what, names in RESTART_NEEDS.items():
                missing = [n for n in names if n not in r.variables]
                print(f"   {what:15s} missing: {missing if missing else 'none'}")


if __name__ == "__main__":
    main()
