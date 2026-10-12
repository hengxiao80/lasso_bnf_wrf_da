"""Innovation statistics per observation type, pooled over a run's cycles (notes/obs_expansion.md Sec. 5).

Usage: .venv/bin/python scripts/da/innovation_stats.py <output dir name, e.g. output_hph>

Reads cases/20250520/da_theta_m0/<run>/<YYYYMMDDHHMM>/filter/obs_seq.final. Per type: DART QC counts;
for obs with a valid prior (QC 0 or 7) the innovation d = y - mean H(x_b) (bias, rms), the rms prior
spread, the rms assigned error sig_o, the consistency ratio mean(d^2) / mean(spread^2 + sig_o^2), the
implied error sqrt(mean d^2 - mean spread^2) (an upper bound if the spread is too small) and the
posterior rms. Then Desroziers' estimate sqrt(mean[(y - H x_a)(y - H x_b)]) over assimilated obs (QC 0).
sig_o includes wrf_dart_obs_preprocess's boundary inflation, so compare ratios, not absolute values.
"""

import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from check_filter_gate import read_obs_seq  # noqa: E402

EXP_DIR = os.path.join(HERE, "..", "..", "cases", "20250520", "da_theta_m0")


def main():
    run = sys.argv[1]
    files = sorted(glob.glob(os.path.join(EXP_DIR, run, "2025052*", "filter", "obs_seq.final")))
    pool = {}
    for f in files:
        copies, qcs, types, recs = read_obs_seq(f)
        ci = {n: k for k, n in enumerate(copies)}
        o = next(k for k, n in enumerate(copies) if n.endswith("observation"))
        pm, ps, qm = ci["prior ensemble mean"], ci["prior ensemble spread"], ci["posterior ensemble mean"]
        dq = qcs.index("DART quality control")
        for kind, v, qc, var in recs:
            pool.setdefault(types[kind], []).append((v[o], v[pm], v[ps], var, int(qc[dq]), v[qm]))

    print(f"{run}: {len(files)} cycles")
    print(f"{'type':32s} {'n':>5s} {'QC0':>5s} {'QC7':>4s} {'QC4':>4s} | {'bias':>8s} {'rms d':>8s} {'sprd':>8s}"
          f" {'sig_o':>8s} {'ratio':>5s} {'impl_o':>8s} {'impl/sig_o':>10s} | {'post rms':>8s}")
    for t in sorted(pool):
        a = np.array(pool[t])
        qc = a[:, 4]
        use = np.isin(qc, (0, 7))      # prior H(x) valid: assimilated or rejected as outliers
        if not use.any():
            print(f"{t:32s} {len(a):5d}  no valid prior")
            continue
        d = a[use, 0] - a[use, 1]
        d2, s2, e2 = (d ** 2).mean(), (a[use, 2] ** 2).mean(), a[use, 3].mean()
        impl = np.sqrt(max(d2 - s2, 0.0))
        a0 = a[qc == 0]
        post = np.sqrt(((a0[:, 0] - a0[:, 5]) ** 2).mean()) if len(a0) else np.nan
        print(f"{t:32s} {len(a):5d} {(qc == 0).sum():5d} {(qc == 7).sum():4d} {(qc == 4).sum():4d} |"
              f" {d.mean():8.3g} {np.sqrt(d2):8.3g} {np.sqrt(s2):8.3g} {np.sqrt(e2):8.3g} {d2 / (s2 + e2):5.2f}"
              f" {impl:8.3g} {impl / np.sqrt(e2):10.2f} | {post:8.3g}")

    print("\nDesroziers (QC 0 only): sig_o_D = sqrt(mean[(y - H x_a)(y - H x_b)]) vs assigned sig_o (rms)")
    for t in sorted(pool):
        a = np.array(pool[t])
        a = a[a[:, 4] == 0]
        if not len(a):
            continue
        c = ((a[:, 0] - a[:, 1]) * (a[:, 0] - a[:, 5])).mean()
        so = np.sqrt(a[:, 3].mean())
        sd = np.sqrt(c) if c > 0 else float("nan")
        print(f"{t:32s} n={len(a):5d}  sig_o_D {sd:9.3g}  assigned {so:9.3g}  ratio {sd / so:5.2f}")


if __name__ == "__main__":
    main()
