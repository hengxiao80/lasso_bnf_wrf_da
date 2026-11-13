"""Where a run's reflectivity innovations come from, per analysis cycle and pooled.

Usage:
  .venv/bin/python scripts/da/refl_innovation_split.py RUN --first YYYYMMDDHHMM --last YYYYMMDDHHMM
      [--step-min 15] [--type RADAR_REFLECTIVITY] [--echo-dbz 10] [--csv FILE]

RUN: a run's output directory, read at <t>/filter/obs_seq.final. The split of
notes/fulltest_d1_analysis.md Sec. 3.6, over the observations of one type with a valid prior (DART QC 0 or 7;
notation of notes/obs_error_diagnostics.md, d_b = y - H(x_b)):

  all:      n, mean d_b and the share of the bias^2 in mean d_b^2, rms d_b, rms prior spread, the implied
            error, and the implied error without the bias;
  QC 0, QC 7: count, share of the summed d_b^2, mean and rms d_b, rms spread; for QC 7 also the share with
            d_b > 0;
  no echo:  observations whose prior mean is below --echo-dbz (the precipitation threshold of
            mrms_to_obs_seq.py): share of the observations and of the summed d_b^2, rms d_b, rms spread,
            share rejected as outliers;
  outside:  observations above all prior members (share of the observations and of the summed d_b^2) and
            below all of them (share of the observations), from the "prior ensemble member" copies;
  gains:    over QC 0, the isolated-observation gain k = mean(s_b^2 / (s_b^2 + sig_o^2)) and the realized
            gain g = mean((H(x_a) - H(x_b)) d_b) / mean(d_b^2).

Each obs_seq.final is read whole (1.2 GB peak and ~4 s for a 178-MB file, D1), one cycle at a time.
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

FIELDS = ["n", "bias", "bias2_share", "rms_db", "sprd", "impl", "impl_nobias",
          "n_qc0", "qc0_share_d2", "qc0_mean_db", "qc0_rms_db", "qc0_sprd",
          "n_qc7", "qc7_share_d2", "qc7_mean_db", "qc7_rms_db", "qc7_sprd", "qc7_pos",
          "noecho_share", "noecho_share_d2", "noecho_rms_db", "noecho_sprd", "noecho_qc7",
          "above_share", "above_share_d2", "below_share", "k", "g"]


def times(first, last, step_min):
    t, t1 = dt.datetime.strptime(first, "%Y%m%d%H%M"), dt.datetime.strptime(last, "%Y%m%d%H%M")
    out = []
    while t <= t1:
        out.append(t.strftime("%Y%m%d%H%M"))
        t += dt.timedelta(minutes=step_min)
    return out


def load(path, typ):
    """y, prior mean, prior spread, posterior mean, error variance, QC, member min, member max for the
    observations of one type with QC 0 or 7."""
    copies, qcs, types, recs = read_obs_seq(path)
    ci = {n: k for k, n in enumerate(copies)}
    o = next(k for k, n in enumerate(copies) if n.endswith("observation"))
    mem = [k for k, n in enumerate(copies) if n.startswith("prior ensemble member")]
    dq = qcs.index("DART quality control")
    kinds = [k for k, n in types.items() if n == typ]
    rows = []
    for r in recs:
        if r[0] in kinds and int(r[2][dq]) in (0, 7):
            v = r[1]
            m = [v[k] for k in mem]
            rows.append((v[o], v[ci["prior ensemble mean"]], v[ci["prior ensemble spread"]],
                         v[ci["posterior ensemble mean"]], r[3], r[2][dq], min(m), max(m)))
    return np.array(rows, dtype=float).reshape(-1, 8)


def split(a, echo_dbz):
    y, hb, sb, ha, ev, qc, mn, mx = a.T
    d = y - hb
    s = dict.fromkeys(FIELDS, np.nan)
    s["n"] = len(d)
    if not len(d):
        return s
    d2, tot = d ** 2, np.sum(d ** 2)
    md2, ms2 = np.mean(d2), np.mean(sb ** 2)
    rms = lambda x: np.sqrt(np.mean(x ** 2)) if len(x) else np.nan  # noqa: E731
    s.update(bias=d.mean(), bias2_share=d.mean() ** 2 / md2, rms_db=np.sqrt(md2), sprd=np.sqrt(ms2),
             impl=np.sqrt(max(md2 - ms2, 0.0)), impl_nobias=np.sqrt(max(md2 - d.mean() ** 2 - ms2, 0.0)))
    for q, pre in ((0, "qc0"), (7, "qc7")):
        m = qc == q
        s[f"n_{pre}"] = int(m.sum())
        s[f"{pre}_share_d2"] = np.sum(d2[m]) / tot
        s[f"{pre}_mean_db"] = d[m].mean() if m.any() else np.nan
        s[f"{pre}_rms_db"], s[f"{pre}_sprd"] = rms(d[m]), rms(sb[m])
    s["qc7_pos"] = np.mean(d[qc == 7] > 0) if (qc == 7).any() else np.nan
    ne = hb < echo_dbz
    s.update(noecho_share=ne.mean(), noecho_share_d2=np.sum(d2[ne]) / tot, noecho_rms_db=rms(d[ne]),
             noecho_sprd=rms(sb[ne]), noecho_qc7=np.mean(qc[ne] == 7) if ne.any() else np.nan)
    above = y > mx
    s.update(above_share=above.mean(), above_share_d2=np.sum(d2[above]) / tot, below_share=np.mean(y < mn))
    z = qc == 0
    if z.any():
        s["k"] = np.mean(sb[z] ** 2 / (sb[z] ** 2 + ev[z]))
        s["g"] = np.mean((ha[z] - hb[z]) * d[z]) / np.mean(d[z] ** 2)
    return s


def show(label, s):
    pct = lambda x: f"{100 * x:5.1f}"  # noqa: E731
    print(f"{label:7s} n {s['n']:7d} | bias {s['bias']:+6.2f} ({pct(s['bias2_share'])} %) rms_db {s['rms_db']:6.2f}"
          f" sprd {s['sprd']:5.2f} impl {s['impl']:6.2f} w/o bias {s['impl_nobias']:6.2f}"
          f" | QC7 {pct(s['n_qc7'] / s['n'])} % of obs, {pct(s['qc7_share_d2'])} % of d2, mean {s['qc7_mean_db']:+6.2f},"
          f" rms {s['qc7_rms_db']:6.2f}, sprd {s['qc7_sprd']:5.2f}, d_b>0 {pct(s['qc7_pos'])} %"
          f" | QC0 rms {s['qc0_rms_db']:6.2f} mean {s['qc0_mean_db']:+6.2f} sprd {s['qc0_sprd']:5.2f}"
          f" | no echo {pct(s['noecho_share'])} % of obs, {pct(s['noecho_share_d2'])} % of d2, rms {s['noecho_rms_db']:6.2f},"
          f" sprd {s['noecho_sprd']:5.2f}, QC7 {pct(s['noecho_qc7'])} %"
          f" | above all {pct(s['above_share'])} % of obs, {pct(s['above_share_d2'])} % of d2; below all {pct(s['below_share'])} %"
          f" | k {s['k']:.3f} g {s['g']:.3f}")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("run")
    p.add_argument("--first", required=True)
    p.add_argument("--last", required=True)
    p.add_argument("--step-min", type=int, default=15)
    p.add_argument("--type", default="RADAR_REFLECTIVITY")
    p.add_argument("--echo-dbz", type=float, default=10.0)
    p.add_argument("--csv", default="")
    a = p.parse_args()
    print(f"{a.run}: {a.type}, observations with QC 0 or 7; no echo = prior mean < {a.echo_dbz} dBZ")
    rows, pool = [], []
    for t in times(a.first, a.last, a.step_min):
        arr = load(os.path.join(a.run, t, "filter", "obs_seq.final"), a.type)
        s = split(arr, a.echo_dbz)
        show(t[-4:], s)
        rows.append([t] + [s[f] for f in FIELDS])
        pool.append(arr)
        sys.stdout.flush()
    s = split(np.vstack(pool), a.echo_dbz)
    show("pooled", s)
    rows.append(["pooled"] + [s[f] for f in FIELDS])
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time"] + FIELDS)
            w.writerows(rows)
        print(f"wrote {a.csv}")


if __name__ == "__main__":
    main()
