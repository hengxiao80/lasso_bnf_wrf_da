"""Checks for the filter gate (pilot step 11) and, later, for each cycle's filter run.

Usage: .venv/bin/python scripts/da/check_filter_gate.py obs <obs_seq.final>
       .venv/bin/python scripts/da/check_filter_gate.py states <before_dir> <after_dir> [--nmem 5]
       .venv/bin/python scripts/da/check_filter_gate.py stages <run_dir>

obs: reads an ASCII obs_seq.final and prints, per observation type, the count by DART QC
  (0 assimilated, 1 evaluated only, 2/3 posterior forward operator failed, 4 prior forward operator
  failed, 5 not used, 6 input QC, 7 outlier, 8 vertical conversion failed) and, for QC 0/1, the
  prior and posterior RMS and mean of (obs - ensemble mean), the mean prior spread and the total
  spread sqrt(spread^2 + obs error variance) to compare with the prior RMS.

states: compares dart_d01.nc of each member in <before_dir>/memNNN/ and <after_dir>/memNNN/ (what
  filter wrote back): RMS and max |after - before| per variable, and NaN counts. Variables that
  are NO_COPY_BACK must be unchanged; with evaluate-only types, all must be.

stages: from filter's stage files in <run_dir>, the mean increment postassim_mean - preassim_mean
  (RMS and max per variable, including the NO_COPY_BACK ones such as W), the prior spread at
  preassim, and the updated prior inflation (postassim_priorinf_mean.nc).
"""

import argparse
import os

import netCDF4
import numpy as np

QC_NAMES = {0: "assim", 1: "eval", 2: "post-fail", 3: "eval-post-fail", 4: "prior-fail",
            5: "unused", 6: "inputQC", 7: "outlier", 8: "vert-fail"}
STATE = ["U", "V", "W", "PH", "THM", "MU", "QVAPOR", "PSFC", "T2", "Q2", "U10", "V10"]


def read_obs_seq(path):
    """ASCII obs_seq: returns copy names, QC names, type names by number, and per-obs records."""
    with open(path) as f:
        tok = f.read().split("\n")
    i = 0
    assert tok[i].strip() == "obs_sequence"
    i += 2
    ntypes = int(tok[i]); i += 1
    types = {}
    for _ in range(ntypes):
        num, name = tok[i].split(); types[int(num)] = name; i += 1
    ncopy, nqc = int(tok[i].split()[1]), int(tok[i].split()[3]); i += 1
    nobs = int(tok[i].split()[1]); i += 1
    copies = [tok[i + k].strip() for k in range(ncopy)]; i += ncopy
    qcs = [tok[i + k].strip() for k in range(nqc)]; i += nqc
    i += 1  # first/last
    recs = []
    for _ in range(nobs):
        assert tok[i].split()[0] == "OBS"; i += 1
        vals = [float(tok[i + k]) for k in range(ncopy)]; i += ncopy
        qc = [float(tok[i + k]) for k in range(nqc)]; i += nqc
        i += 1  # links
        assert tok[i].strip() == "obdef"; i += 2  # obdef, loc3d
        i += 1  # location
        assert tok[i].strip() == "kind"; i += 1
        kind = int(tok[i]); i += 1
        i += 1  # time
        var = float(tok[i]); i += 1
        recs.append((kind, vals, qc, var))
    return copies, qcs, types, recs


def obs_report(path):
    copies, qcs, types, recs = read_obs_seq(path)
    ci = {n: k for k, n in enumerate(copies)}
    dqc = qcs.index("DART quality control")
    obs = next(k for k, n in enumerate(copies) if n.endswith("observation"))   # e.g. "NCEP BUFR observation"
    pm, ps = ci["prior ensemble mean"], ci["prior ensemble spread"]
    qm = ci.get("posterior ensemble mean")
    print(f"{path}: {len(recs)} obs, copies: {', '.join(copies[:5])}, ...")
    print(f"{'type':34s} {'n':>6s}  QC counts | prior rms/bias, spread, total | posterior rms/bias")
    for kind in sorted({r[0] for r in recs}):
        sel = [r for r in recs if r[0] == kind]
        q = np.array([int(r[2][dqc]) for r in sel])
        counts = " ".join(f"{QC_NAMES.get(c, c)}={(q == c).sum()}" for c in np.unique(q))
        ok = [r for r, c in zip(sel, q) if c in (0, 1)]
        line = f"{types[kind]:34s} {len(sel):6d}  {counts}"
        if ok:
            o = np.array([r[1][obs] for r in ok])
            d = o - np.array([r[1][pm] for r in ok])
            sp = np.array([r[1][ps] for r in ok])
            ev = np.array([r[3] for r in ok])
            line += (f" | {np.sqrt((d ** 2).mean()):.3g}/{d.mean():+.3g}, {np.sqrt((sp ** 2).mean()):.3g},"
                     f" {np.sqrt((sp ** 2 + ev).mean()):.3g}")
            if qm is not None:
                da = o - np.array([r[1][qm] for r in ok])
                line += f" | {np.sqrt((da ** 2).mean()):.3g}/{da.mean():+.3g}"
        print(line)


def diff_report(a_path, b_path, names, tag):
    with netCDF4.Dataset(a_path) as a, netCDF4.Dataset(b_path) as b:
        for n in names:
            if n not in a.variables or n not in b.variables:
                print(f"   {tag} {n}: missing"); continue
            x = np.asarray(a[n][:], np.float64)
            y = np.asarray(b[n][:], np.float64)
            dd = y - x
            nan = int(np.isnan(y).sum())
            print(f"   {tag} {n:7s} RMS {np.sqrt(np.nanmean(dd ** 2)):.3g}  max {np.nanmax(np.abs(dd)):.3g}"
                  + (f"  NaN {nan}" if nan else ""))


def states(before, after, nmem):
    for m in range(1, nmem + 1):
        sub = f"mem{m:03d}/dart_d01.nc"
        print(f"member {m}: after - before")
        diff_report(os.path.join(before, sub), os.path.join(after, sub), STATE + ["T"], "")


def stages(run, names=STATE):
    j = lambda f: os.path.join(run, f)
    print("mean increment, postassim_mean - preassim_mean:")
    diff_report(j("preassim_mean.nc"), j("postassim_mean.nc"), names, "")
    with netCDF4.Dataset(j("preassim_sd.nc")) as sd:
        names = [n for n in names if n in sd.variables]
        print("prior spread (preassim_sd), domain RMS:")
        for n in names:
            print(f"   {n:7s} {np.sqrt((np.asarray(sd[n][:], np.float64) ** 2).mean()):.3g}")
    # output_priorinf_* holds only the UPDATE variables; postassim_priorinf_* has the same updated
    # values for those and also the NO_COPY_BACK ones, so it is the one to pass to the next cycle.
    if os.path.exists(j("postassim_priorinf_mean.nc")):
        with netCDF4.Dataset(j("postassim_priorinf_mean.nc")) as inf:
            print("updated prior inflation mean, postassim_priorinf_mean (min / mean / max):")
            for n in names:
                v = np.asarray(inf[n][:], np.float64)
                print(f"   {n:7s} {v.min():.4f} / {v.mean():.4f} / {v.max():.4f}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("obs")
    o.add_argument("obs_seq_final")
    s = sub.add_parser("states")
    s.add_argument("before")
    s.add_argument("after")
    s.add_argument("--nmem", type=int, default=5)
    g = sub.add_parser("stages")
    g.add_argument("run")
    args = p.parse_args()
    if args.cmd == "obs":
        obs_report(args.obs_seq_final)
    elif args.cmd == "states":
        states(args.before, args.after, args.nmem)
    else:
        stages(args.run)


if __name__ == "__main__":
    main()
