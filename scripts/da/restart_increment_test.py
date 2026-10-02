"""Helpers for the modified-restart test (pilot step 7, test b).

Usage: .venv/bin/python scripts/da/restart_increment_test.py perturb <dart_file> <pert_file>
                                                            [--hydrostatic-ph <wrfrst>]
       .venv/bin/python scripts/da/restart_increment_test.py report <ref_run_dir> <run_dir> ...
                                                            [--end-time 2025-05-20_00_30_00]

perturb: adds a member perturbation (U, V, THM, QVAPOR, MU; e.g. perts/members/pert_mem001.nc)
  to a DART-facing file, as a stand-in for a filter update, and sets T = THM. With --hydrostatic-ph
  (the restart file the DART-facing file came from, for the static fields), also adds the
  hydrostatic PH increment (check_hydrostatic_balance.py), so PH stays consistent with the new MU,
  THM and QVAPOR while keeping the model's own non-hydrostatic part.
report: per run, the domain-mean |dpsfc/dt| and |dmu/dt| (hPa/3h) from WRF's diag_print lines in
  rsl.out.0000 (first steps, then averages), and the RMS difference of key fields at --end-time
  from the reference run.
"""

import argparse
import os
import re

import netCDF4
import numpy as np

from check_hydrostatic_balance import Grid, read_state

FIELDS = ["U", "V", "THM", "QVAPOR", "MU"]
KEY = ["U", "V", "W", "T", "QVAPOR", "MU", "PH", "P", "PSFC", "T2", "QCLOUD", "QRAIN", "RAINNC", "PBLH"]


def perturb(dart_path, pert_path, static_path=None):
    prior = read_state(dart_path) if static_path else None
    with netCDF4.Dataset(pert_path) as pert, netCDF4.Dataset(dart_path, "a") as d:
        for n in FIELDS:
            field = np.asarray(d[n][:], np.float64) + np.asarray(pert[n][:], np.float64)
            if n == "QVAPOR":
                field = np.maximum(field, 0.0)
            d[n][:] = field.astype(np.float32)
        d["T"][:] = d["THM"][:]
    if static_path:
        grid = Grid(static_path)
        dph = grid.ph_hydro(read_state(dart_path)) - grid.ph_hydro(prior)
        with netCDF4.Dataset(dart_path, "a") as d:
            d["PH"][0] = (np.asarray(d["PH"][0], np.float64) + dph).astype(np.float32)
        print(f"hydrostatic PH increment added: RMS {np.sqrt((dph ** 2).mean()) / 9.81:.2f} m,"
              f" max {np.abs(dph).max() / 9.81:.1f} m")


def label(run_dir):
    """<case>/run -> <case>"""
    run_dir = os.path.normpath(run_dir)
    return os.path.basename(os.path.dirname(run_dir)) if os.path.basename(run_dir) == "run" \
        else os.path.basename(run_dir)


def diag_series(run_dir):
    pat = re.compile(r"Domain average of dpsdt, dmudt \(mb/3h\):\s+(\S+)\s+(\S+)\s+(\S+)")
    rows = []
    for line in open(os.path.join(run_dir, "rsl.out.0000")):
        m = pat.search(line)
        if m:
            rows.append([float(x) for x in m.groups()])
    return np.array(rows)


def report(ref_dir, run_dirs, end_time):
    # Step 1 is skipped: on a restart diag_print compares with an uninitialized previous PSFC.
    print("domain-mean |dpsfc/dt| (hPa/3h) from diag_print, per 5-s step, from step 2")
    for d in [ref_dir] + run_dirs:
        s = diag_series(d)
        if len(s) == 0:
            print(f"   {label(d):18s} no diag_print lines")
            continue
        ps, mus = s[1:, 1], s[1:, 2]
        print(f"   {label(d):18s} steps 2-8: " + " ".join(f"{x:7.1f}" for x in ps[:7])
              + f" | mean min 0-1 {ps[:11].mean():7.1f}, 1-5 {ps[11:59].mean():6.1f},"
              f" 5-15 {ps[59:].mean():6.1f}; |dmu/dt| {mus[:11].mean():5.1f}, {mus[11:59].mean():5.1f},"
              f" {mus[59:].mean():5.1f}")
    ref = netCDF4.Dataset(os.path.join(ref_dir, f"wrfout_d01_{end_time}"))
    print(f"\nRMS difference from {label(ref_dir)} at {end_time}")
    print("   " + " ".join(f"{n:>9s}" for n in KEY))
    for d in run_dirs:
        ds = netCDF4.Dataset(os.path.join(d, f"wrfout_d01_{end_time}"))
        vals = [np.sqrt(((np.asarray(ds[n][:], np.float64) - ref[n][:]) ** 2).mean()) for n in KEY]
        print(f"   {label(d):18s}\n   " + " ".join(f"{v:9.3g}" for v in vals))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("perturb")
    a.add_argument("dart_file")
    a.add_argument("pert_file")
    a.add_argument("--hydrostatic-ph", metavar="WRFRST")
    b = sub.add_parser("report")
    b.add_argument("ref_run_dir")
    b.add_argument("run_dirs", nargs="+")
    b.add_argument("--end-time", default="2025-05-20_00_30_00")
    args = p.parse_args()
    if args.cmd == "perturb":
        perturb(args.dart_file, args.pert_file, args.hydrostatic_ph)
    else:
        report(args.ref_run_dir, args.run_dirs, args.end_time)


if __name__ == "__main__":
    main()
