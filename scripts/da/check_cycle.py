"""Per-cycle checks for the cycling (pilot step 12), run by cycle_job.sh on output/<t>/.

Usage: .venv/bin/python scripts/da/check_cycle.py <output/YYYYMMDDHHMM> [--nmem 5]

Prints, if the cycle had an analysis (filter/ exists):
  - per observation type the DART QC counts and prior/posterior statistics (check_filter_gate.py obs);
  - mean increment, prior spread and updated prior inflation (check_filter_gate.py stages);
  - that postassim_priorinf_* (passed to the next cycle) equals output_priorinf_* on the UPDATE
    variables, the only ones output_priorinf_* holds;
  - per member, analysis - prior of the DART-facing files and the insert log.
For every member: the segment's end (SUCCESS COMPLETE WRF), CFL line count, and the domain-mean
|dpsfc/dt| from diag_print over minutes 0-1, 1-5 and 5-15 of the segment (step 1 skipped on a
restart, where diag_print compares with an uninitialized previous PSFC).
Exits 1 on a NaN in a member's prior or analysis file or in the postassim mean, on an inflation
mismatch, or on a missing file; the cycle is then not marked complete.
"""

import argparse
import glob
import os
import sys

import netCDF4
import numpy as np

from check_filter_gate import STATE, diff_report, obs_report, stages
from restart_increment_test import diag_series

UPDATE = ["U", "V", "PH", "THM", "MU", "QVAPOR"]
problems = []


def nan_check(path, names):
    with netCDF4.Dataset(path) as ds:
        for n in names:
            if n in ds.variables and np.isnan(np.asarray(ds[n][:], np.float64)).any():
                problems.append(f"NaN in {n} of {path}")


def inflation_check(fdir):
    for s in ("mean", "sd"):
        a = os.path.join(fdir, f"postassim_priorinf_{s}.nc")
        b = os.path.join(fdir, f"output_priorinf_{s}.nc")
        with netCDF4.Dataset(a) as pa, netCDF4.Dataset(b) as ou:
            for n in UPDATE:
                d = np.abs(np.asarray(pa[n][:], np.float64) - np.asarray(ou[n][:], np.float64)).max()
                if d != 0:
                    problems.append(f"postassim vs output prior inflation {s} differ in {n}: max {d:.3g}")
    print("postassim_priorinf_* vs output_priorinf_* on the UPDATE variables: "
          + ("identical" if not any("inflation" in p for p in problems) else "DIFFERENT"))


def segment_report(mdir, m, restart):
    rsl = os.path.join(mdir, "rsl.out.0000")
    if not os.path.exists(rsl):
        problems.append(f"member {m}: no {rsl}"); return
    ok = "SUCCESS COMPLETE WRF" in open(rsl).read()[-2000:]
    if not ok:
        problems.append(f"member {m}: wrf.exe did not complete")
    s = diag_series(mdir)
    cfl = open(os.path.join(mdir, "cfl_count.txt")).read().strip()
    wrfouts = sorted(os.path.basename(f) for f in glob.glob(os.path.join(mdir, "wrfout_d01_*")))
    if not wrfouts:
        problems.append(f"member {m}: no wrfout")
    line = f"   member {m}: {'SUCCESS' if ok else 'FAILED'}, {cfl}, {', '.join(wrfouts)}"
    if len(s):
        ps = s[1:, 1] if restart else s[:, 1]   # 12 steps per minute (dt = 5 s)
        line += (f"\n      |dpsfc/dt| hPa/3h: steps 2-4 {' '.join(f'{x:.0f}' for x in ps[:3])},"
                 f" min 0-1 {ps[:11].mean():.0f}, 1-5 {ps[11:59].mean():.0f}, 5-15 {ps[59:].mean():.0f}")
    print(line)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--nmem", type=int, default=5)
    args = p.parse_args()
    out = args.out
    fdir = os.path.join(out, "filter")
    analysis = os.path.exists(os.path.join(fdir, "obs_seq.final"))
    print(f"cycle {os.path.basename(os.path.normpath(out))}: analysis {'yes' if analysis else 'no (cold start)'}")

    if analysis:
        print(f"inflation from {open(os.path.join(fdir, 'inflation_source.txt')).read().strip()}\n")
        obs_report(os.path.join(fdir, "obs_seq.final"))
        print()
        stages(fdir)
        nan_check(os.path.join(fdir, "postassim_mean.nc"), STATE)
        inflation_check(fdir)
        print("\nanalysis - prior per member (DART-facing files; T is not in the state):")
        for m in range(1, args.nmem + 1):
            mdir = os.path.join(out, f"mem{m:03d}")
            prior, anal = os.path.join(mdir, "prior_d01.nc"), os.path.join(mdir, "analysis_d01.nc")
            for f in (prior, anal):
                if not os.path.exists(f):
                    problems.append(f"no {f}")
            if os.path.exists(prior) and os.path.exists(anal):
                print(f"member {m}:")
                diff_report(prior, anal, UPDATE, "")
                nan_check(prior, STATE)
                nan_check(anal, STATE)
            log = os.path.join(mdir, "insert.log")
            if os.path.exists(log):
                print("".join(f"   insert: {l}" for l in open(log)), end="")

    print("\nsegments:")
    for m in range(1, args.nmem + 1):
        segment_report(os.path.join(out, f"mem{m:03d}"), m, restart=analysis)

    if problems:
        print("\nPROBLEMS:\n" + "\n".join(f"   {p}" for p in problems))
        sys.exit(1)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
