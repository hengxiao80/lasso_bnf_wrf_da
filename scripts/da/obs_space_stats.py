"""Observation-space statistics per analysis cycle and pooled, for one run or two runs side by side.

Usage:
  .venv/bin/python scripts/da/obs_space_stats.py RUN_A [RUN_B] --first YYYYMMDDHHMM --last YYYYMMDDHHMM
      [--step-min 15] [--types NAME,NAME,...] [--csv FILE] [--no-pooled]

RUN_A, RUN_B: a run's output directory, read at <t>/filter/obs_seq.final for every analysis time t from
--first to --last. Definitions and selections as in notes/fulltest_d1_analysis.md Sec. 3.1 (notation of
notes/obs_error_diagnostics.md; d_b = y - H(x_b), d_a = y - H(x_a), s_b the prior spread, sig_o the
assigned error sd, with the boundary inflation):

  over DART QC 0 or 7 (every observation with a valid prior; the same set in two runs that read the same
  obs_seq): n, q7 (the QC-7 count), bias = mean(d_b), rms d_b, rms s_b ("sprd"), rms sig_o, the implied
  error sqrt(mean d_b^2 - mean s_b^2) ("impl") and its ratio to rms sig_o ("impl/s");
  over QC 0 (one run: its own QC-0 set; two runs: the observations assimilated in both, so the runs are
  compared on the same observations): n0, rms d_a, Desroziers' estimate sqrt(mean d_a d_b) ("desr") and
  its ratio to rms sig_o over the same set ("desr/s"), the isolated-observation gain
  k = mean(s_b^2 / (s_b^2 + sig_o^2)) and the realized gain g = mean((H(x_a) - H(x_b)) d_b) / mean(d_b^2).

Specific humidity in g/kg, everything else in the units of the type. Two runs must have read the same
obs_seq: the script checks that each cycle's obs_seq.final lists the same types and observed values in the
same order. --csv writes one row per time (or "pooled"), type and run. Each obs_seq.final is read whole
(1.2 GB peak and ~4 s for a 178-MB file, D1); files are read one cycle at a time.
"""

import argparse
import csv
import datetime as dt
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from check_filter_gate import read_obs_seq  # noqa: E402

# columns of the per-observation array
Y, HB, SB, HA, EV, QC = range(6)
FIELDS = ["n", "q7", "bias", "rms_db", "sprd", "sig_o", "impl", "impl_ratio",
          "n0", "rms_da", "desr", "desr_ratio", "k", "g"]


def times(first, last, step_min):
    t, t1 = dt.datetime.strptime(first, "%Y%m%d%H%M"), dt.datetime.strptime(last, "%Y%m%d%H%M")
    out = []
    while t <= t1:
        out.append(t.strftime("%Y%m%d%H%M"))
        t += dt.timedelta(minutes=step_min)
    return out


def load(path):
    """Per-observation array (y, prior mean, prior spread, posterior mean, error variance, DART QC) and
    the type name of each observation."""
    copies, qcs, types, recs = read_obs_seq(path)
    ci = {n: k for k, n in enumerate(copies)}
    o = next(k for k, n in enumerate(copies) if n.endswith("observation"))
    cols = (o, ci["prior ensemble mean"], ci["prior ensemble spread"], ci["posterior ensemble mean"])
    dq = qcs.index("DART quality control")
    a = np.array([[r[1][c] for c in cols] + [r[3], r[2][dq]] for r in recs], dtype=float)
    names = np.array([types[r[0]] for r in recs])
    return a, names


def stats(a, both0, scale):
    """Statistics of one run's observations of one type; both0 marks the QC-0 set used for the analysis
    statistics."""
    out = dict.fromkeys(FIELDS, np.nan)
    use = np.isin(a[:, QC], (0, 7))
    out["n"], out["q7"] = int(use.sum()), int((a[:, QC] == 7).sum())
    if use.any():
        d = (a[use, Y] - a[use, HB]) * scale
        md2, ms2 = np.mean(d ** 2), np.mean((a[use, SB] * scale) ** 2)
        sig = np.sqrt(np.mean(a[use, EV])) * scale
        out.update(bias=d.mean(), rms_db=np.sqrt(md2), sprd=np.sqrt(ms2), sig_o=sig,
                   impl=np.sqrt(max(md2 - ms2, 0.0)))
        out["impl_ratio"] = out["impl"] / sig
    b = a[both0]
    out["n0"] = len(b)
    if len(b):
        db, da = (b[:, Y] - b[:, HB]) * scale, (b[:, Y] - b[:, HA]) * scale
        inc = (b[:, HA] - b[:, HB]) * scale
        s2, e2 = (b[:, SB] * scale) ** 2, b[:, EV] * scale ** 2
        out.update(rms_da=np.sqrt(np.mean(da ** 2)), desr=np.sqrt(max(np.mean(da * db), 0.0)),
                   k=np.mean(s2 / (s2 + e2)), g=np.mean(inc * db) / np.mean(db ** 2))
        out["desr_ratio"] = out["desr"] / np.sqrt(np.mean(e2))
    return out


def fmt(label, typ, run, s):
    return (f"{label:7s} {typ:32s} {run:2s} {s['n']:7d} {s['q7']:6d} | {s['bias']:8.3g} {s['rms_db']:8.3g}"
            f" {s['sprd']:8.3g} {s['sig_o']:8.3g} {s['impl']:8.3g} {s['impl_ratio']:6.2f} | {s['n0']:7d}"
            f" {s['rms_da']:8.3g} {s['desr']:8.3g} {s['desr_ratio']:6.2f} {s['k']:6.3f} {s['g']:6.3f}")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("runs", nargs="+", help="one or two run output directories")
    p.add_argument("--first", required=True)
    p.add_argument("--last", required=True)
    p.add_argument("--step-min", type=int, default=15)
    p.add_argument("--types", default="", help="comma-separated type names (default: all)")
    p.add_argument("--csv", default="")
    p.add_argument("--no-pooled", action="store_true")
    a = p.parse_args()
    if len(a.runs) > 2:
        p.error("one or two runs")
    labels = ["A", "B"][:len(a.runs)]
    for lab, r in zip(labels, a.runs):
        print(f"{lab} = {r}")
    print("prior statistics over QC 0 or 7; analysis statistics over "
          + ("the observations assimilated in both runs" if len(a.runs) == 2 else "QC 0"))
    print(f"{'time':7s} {'type':32s} {'run':2s} {'n':>7s} {'q7':>6s} | {'bias':>8s} {'rms_db':>8s} {'sprd':>8s}"
          f" {'sig_o':>8s} {'impl':>8s} {'impl/s':>6s} | {'n0':>7s} {'rms_da':>8s} {'desr':>8s} {'desr/s':>6s}"
          f" {'k':>6s} {'g':>6s}")
    want = set(t for t in a.types.split(",") if t)
    pool = {}
    rows = []
    for t in times(a.first, a.last, a.step_min):
        arrs = [load(os.path.join(r, t, "filter", "obs_seq.final")) for r in a.runs]
        if len(arrs) == 2:
            (x, nx), (y, ny) = arrs
            if not (np.array_equal(nx, ny) and np.array_equal(x[:, Y], y[:, Y])):
                sys.exit(f"{t}: the two runs' obs_seq.final don't list the same observations")
            both0 = (x[:, QC] == 0) & (y[:, QC] == 0)
        else:
            both0 = arrs[0][0][:, QC] == 0
        names = arrs[0][1]
        for typ in sorted(set(names)):
            if want and typ not in want:
                continue
            m = names == typ
            scale = 1000.0 if "HUMIDITY" in typ else 1.0
            for lab, (arr, _) in zip(labels, arrs):
                s = stats(arr[m], both0[m], scale)
                print(fmt(t[-4:], typ, lab, s))
                rows.append([t, typ, lab] + [s[f] for f in FIELDS])
                pool.setdefault((typ, lab), ([], [], scale))
                pool[(typ, lab)][0].append(arr[m])
                pool[(typ, lab)][1].append(both0[m])
        sys.stdout.flush()
    if not a.no_pooled:
        print("\npooled over", a.first, "to", a.last)
        for (typ, lab) in sorted(pool):
            arrs, masks, scale = pool[(typ, lab)]
            s = stats(np.vstack(arrs), np.concatenate(masks), scale)
            print(fmt("pooled", typ, lab, s))
            rows.append(["pooled", typ, lab] + [s[f] for f in FIELDS])
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time", "type", "run"] + FIELDS)
            w.writerows(rows)
        print(f"wrote {a.csv}")


if __name__ == "__main__":
    main()
