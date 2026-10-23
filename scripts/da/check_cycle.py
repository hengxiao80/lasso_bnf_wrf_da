"""Per-cycle checks for the cycling (pilot step 12), run by cycle_job.sh on output/<t>/.

Usage: .venv/bin/python scripts/da/check_cycle.py <output/YYYYMMDDHHMM> [--nmem 5] [--spread-only]

Prints, if the cycle had an analysis (filter/ exists), for the first pass and, in a two-pass run
(filter_mrms/ exists), again for the MRMS pass (each pass's UPDATE variables are read from the
input.nml saved with it, so one-pass, two-pass and one-pass MRMS runs are all covered):
  - per observation type the DART QC counts and prior/posterior statistics (check_filter_gate.py obs);
  - mean increment, prior spread and updated prior inflation (check_filter_gate.py stages);
  - that postassim_priorinf_* (passed to the next cycle) equals output_priorinf_* on the UPDATE
    variables, the only ones output_priorinf_* holds;
  - spread by stage, per pass: domain RMS of the ensemble sd of U V THM QVAPOR QCLOUD QRAIN QSNOW
    QGRAUP MU before inflation (input_sd), after (preassim_sd) and after assimilation (postassim_sd),
    and the applied prior inflation (preassim_priorinf_mean: mean, share > 1.1, max); over all points
    and over the echo columns (background mean REFL_10CM >= 10 dBZ at some level, or an MRMS
    precipitation ob in or next to the column); then forecast -> analysis spread over the cycle
    (a diagnostic: a failure here is printed, not counted as a problem);
  - per member, analysis - prior of the DART-facing files (after both passes) and the insert log.
For every member: the segment's end (SUCCESS COMPLETE WRF), CFL line count, and the domain-mean
|dpsfc/dt| from diag_print over minutes 0-1, 1-5 and 5-15 of the segment (step 1 skipped on a
restart, where diag_print compares with an uninitialized previous PSFC).
Exits 1 on a NaN in a member's prior or analysis file or in the postassim mean, on an inflation
mismatch, or on a missing file; the cycle is then not marked complete.
--spread-only prints only the spread by stage (for runs from before it was added).
"""

import argparse
import glob
import math
import os
import re
import sys

import netCDF4
import numpy as np

from check_filter_gate import STATE, diff_report, obs_report, read_obs_seq, stages
from restart_increment_test import diag_series

HYDRO = ["QCLOUD", "QRAIN", "QSNOW", "QGRAUP", "REFL_10CM"]
STATE_ALL = STATE + HYDRO
SPREAD = ["U", "V", "THM", "QVAPOR", "QCLOUD", "QRAIN", "QSNOW", "QGRAUP", "MU"]
ECHO_DBZ = 10.0   # mrms_to_obs_seq.py --precip-dbz-thresh: its RADAR_REFLECTIVITY obs all have Z >= this
problems = []


def nan_check(path, names):
    with netCDF4.Dataset(path) as ds:
        for n in names:
            if n in ds.variables and np.isnan(np.asarray(ds[n][:], np.float64)).any():
                problems.append(f"NaN in {n} of {path}")


def update_vars(nml):
    """Names flagged UPDATE in &model_nml wrf_state_variables of a saved input.nml."""
    text = open(nml).read()
    block = re.search(r"wrf_state_variables\s*=(.*?)wrf_state_bounds", text, re.S).group(1)
    rows = re.findall(r"'(\w+)',\s*'(\w+)',\s*'(\w+)',\s*'(\w+)',\s*'(\w+)'", block)
    return [r[0] for r in rows if r[3] == "UPDATE"]


def inflation_check(fdir, update):
    for s in ("mean", "sd"):
        a = os.path.join(fdir, f"postassim_priorinf_{s}.nc")
        b = os.path.join(fdir, f"output_priorinf_{s}.nc")
        with netCDF4.Dataset(a) as pa, netCDF4.Dataset(b) as ou:
            for n in update:
                d = np.abs(np.asarray(pa[n][:], np.float64) - np.asarray(ou[n][:], np.float64)).max()
                if d != 0:
                    problems.append(f"postassim vs output prior inflation {s} differ in {n}: max {d:.3g}")
    print("postassim_priorinf_* vs output_priorinf_* on the UPDATE variables: "
          + ("identical" if not any("inflation" in p for p in problems) else "DIFFERENT"))


def echo_columns(out, passes):
    """Mass-grid columns with echo: the background mean REFL_10CM (filter/input_mean.nc) >= ECHO_DBZ at
    some level, or an MRMS precipitation ob (RADAR_REFLECTIVITY) in the column or a neighbouring one
    (the obs are thinned to every other point). Returns the mask and a description of it."""
    with netCDF4.Dataset(os.path.join(out, "filter", "input_mean.nc")) as ds:
        model = np.asarray(ds["REFL_10CM"][0], np.float64).max(axis=0) >= ECHO_DBZ
        lat = np.asarray(ds["XLAT"][:], np.float64)
        lon = np.asarray(ds["XLONG"][:], np.float64) % 360.0
    # The obs sit on mass points (mrms_to_obs_seq.py writes geo_em's XLAT_M/XLONG_M = XLAT/XLONG), but
    # obs_seq.final has their locations at single precision (DART's r8 = r4; ~2e-5 deg), so an ob is
    # matched on a 0.001-deg key or a neighbouring one (the mass points are ~0.02 deg apart).
    key = lambda a, b: (round(a * 1000), round(b * 1000))
    index = {key(a, b): k for k, (a, b) in enumerate(zip(lat.ravel().tolist(), lon.ravel().tolist()))}
    near_keys = [(i, j) for i in (0, -1, 1) for j in (0, -1, 1)]
    radar = np.zeros(lat.size, bool)
    n = missed = 0
    for _, d in passes:
        _, _, types, recs = read_obs_seq(os.path.join(d, "obs_seq.final"), locations=True)
        for r in recs:
            if types[r[0]] == "RADAR_REFLECTIVITY":
                n += 1
                ka, kb = key(math.degrees(r[4][1]), math.degrees(r[4][0]) % 360.0)
                k = next((index[(ka + i, kb + j)] for i, j in near_keys if (ka + i, kb + j) in index), None)
                if k is None:
                    missed += 1
                else:
                    radar[k] = True
    ny, nx = lat.shape
    p = np.pad(radar.reshape(ny, nx), 1)
    near = np.zeros((ny, nx), bool)
    for dj in range(3):
        for di in range(3):
            near |= p[dj:dj + ny, di:di + nx]
    echo = model | near
    desc = (f"{100 * echo.mean():.1f} % of the columns (background mean REFL_10CM >= {ECHO_DBZ:g} dBZ:"
            f" {100 * model.mean():.1f} %; MRMS precipitation ob in or next to the column: {100 * near.mean():.1f} %,"
            f" from {n} obs" + (f", {missed} not on a mass point" if missed else "") + ")")
    return echo, desc


def on_grid(m, shape):
    """A column mask on a field's horizontal grid, broadcast to the field's shape: a staggered point is
    in it if either neighbouring mass point is."""
    if shape[-1] == m.shape[1] + 1:
        p = np.pad(m, ((0, 0), (1, 1)))
        m = p[:, :-1] | p[:, 1:]
    elif shape[-2] == m.shape[0] + 1:
        p = np.pad(m, ((1, 1), (0, 0)))
        m = p[:-1] | p[1:]
    return np.broadcast_to(m, shape)


def spread_report(out, passes):
    echo, desc = echo_columns(out, passes)
    print("domain RMS of the ensemble sd (sqrt of the mean variance; mixing ratios in g/kg): before inflation"
          " (input_sd) -> after (preassim_sd), ratio -> after assimilation (postassim_sd); applied prior"
          " inflation (preassim_priorinf_mean): mean, share > 1.1, max")
    print(f"echo: {desc}")
    rms = lambda x, m: math.sqrt(np.mean(x ** 2 if m is None else x[m] ** 2))
    ratio = lambda b, a: f"x{b / a:.3f}" if a > 0 else "x -"
    forecast, analysis = {}, {}
    for name, d in passes:
        update = update_vars(os.path.join(d, "input.nml"))
        files = [os.path.join(d, f"{s}_sd.nc") for s in ("input", "preassim", "postassim")]
        lam_file = os.path.join(d, "preassim_priorinf_mean.nc")
        lam_ok = os.path.exists(lam_file)
        missing = [f for f in files if not os.path.exists(f)]
        print(f"\n{name}" + ("" if lam_ok else " (no prior inflation)") + ", * = not written back by this pass:")
        if missing:
            print(f"   no {', '.join(missing)}: skipped"); continue
        sds = [netCDF4.Dataset(f) for f in files]
        lam = netCDF4.Dataset(lam_file) if lam_ok else None
        for n in SPREAD:
            scale = 1e3 if n.startswith("Q") else 1.0
            sd = [np.asarray(f[n][0], np.float64) * scale for f in sds]
            lv = np.asarray(lam[n][0], np.float64) if lam else None
            for region, m in (("all", None), ("echo", on_grid(echo, sd[0].shape))):
                a, b, c = (rms(x, m) for x in sd)
                forecast.setdefault((n, region), a)
                if n in update:
                    analysis[(n, region)] = c
                line = f"   {n + ('' if n in update else '*'):8s}{region:5s} {a:#.3g} -> {b:#.3g} ({ratio(b, a)}) -> {c:#.3g}"
                if lv is not None:
                    v = lv if m is None else lv[m]
                    line += f"   lambda {v.mean():.3f}, {100 * (v > 1.1).mean():.1f} % > 1.1, max {v.max():.2f}"
                print(line)
        for f in sds + ([lam] if lam else []):
            f.close()
    print("\nover the cycle: forecast (first pass input_sd) -> analysis (postassim_sd of the last pass that writes"
          " the field)")
    for n in SPREAD:
        if (n, "all") in analysis:
            print(f"   {n:8s}" + "   ".join(f"{r} {forecast[(n, r)]:#.3g} -> {analysis[(n, r)]:#.3g}"
                                          f" ({ratio(analysis[(n, r)], forecast[(n, r)])})" for r in ("all", "echo")))


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
    p.add_argument("--spread-only", action="store_true")
    args = p.parse_args()
    out = args.out
    fdir = os.path.join(out, "filter")
    analysis = os.path.exists(os.path.join(fdir, "obs_seq.final"))
    mdir_ = os.path.join(out, "filter_mrms")
    two_pass = os.path.isdir(mdir_)
    print(f"cycle {os.path.basename(os.path.normpath(out))}: analysis "
          + ("no (cold start)" if not analysis else "yes, two passes" if two_pass else "yes"))

    passes = [("first pass", fdir)] + ([("MRMS pass", mdir_)] if two_pass else [])
    if args.spread_only:
        if analysis:
            spread_report(out, passes)
        return
    updated = []
    for name, d in passes if analysis else []:
        print(f"\n===== {name} ({d})")
        if not os.path.exists(os.path.join(d, "obs_seq.final")):
            problems.append(f"no {d}/obs_seq.final"); continue
        update = update_vars(os.path.join(d, "input.nml"))
        updated += [n for n in update if n not in updated]
        print(f"UPDATE variables: {' '.join(update)}")
        print(f"inflation from {open(os.path.join(d, 'inflation_source.txt')).read().strip()}\n")
        obs_report(os.path.join(d, "obs_seq.final"))
        print()
        stages(d, STATE_ALL)
        nan_check(os.path.join(d, "postassim_mean.nc"), STATE_ALL)
        if os.path.exists(os.path.join(d, "postassim_priorinf_mean.nc")):
            inflation_check(d, update)
    if analysis and all(os.path.exists(os.path.join(d, "obs_seq.final")) for _, d in passes):
        print("\n===== spread by stage")
        try:
            spread_report(out, passes)
        except Exception as e:   # a diagnostic only: don't stop the cycling for it
            print(f"spread by stage failed: {e!r}")
    if analysis:
        print("\nanalysis - prior per member (DART-facing files; T is not in the state):")
        for m in range(1, args.nmem + 1):
            mdir = os.path.join(out, f"mem{m:03d}")
            prior, anal = os.path.join(mdir, "prior_d01.nc"), os.path.join(mdir, "analysis_d01.nc")
            for f in (prior, anal):
                if not os.path.exists(f):
                    problems.append(f"no {f}")
            if os.path.exists(prior) and os.path.exists(anal):
                print(f"member {m}:")
                diff_report(prior, anal, updated + ["QNRAIN"], "")
                nan_check(prior, STATE_ALL + ["QNRAIN"])
                nan_check(anal, STATE_ALL + ["QNRAIN"])
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
