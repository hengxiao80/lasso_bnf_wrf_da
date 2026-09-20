#!/usr/bin/env python3
"""Plot model layer thickness (domain mean, min, max per level) for two or more WRF runs.

Thickness of layer k is dz(k) = [(PH+PHB)(k+1) - (PH+PHB)(k)] / g, computed for every
column of the output time you pick, then reduced over the whole domain. Compare e.g. a
hybrid_opt=0 (terrain-following sigma) run with a hybrid_opt=2 run.

Usage:
    uv run python3 scripts/plot_layer_thickness.py --time 2025-05-20_12_00_00 \
        --run baseline=cases/20250520/baseline --run hybrid2=cases/20250520/hybrid2 \
        --out cases/20250520/figures/layer_thickness_20250520_1200.png
"""

import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from netCDF4 import Dataset  # noqa: E402

G = 9.81  # WRF's g

COLORS = ["#1f77b4", "#e6550d", "#2ca02c", "#756bb1"]


def layer_stats(path):
    with Dataset(path) as nc:
        ph = np.asarray(nc["PH"][0], dtype=np.float64) + np.asarray(nc["PHB"][0], dtype=np.float64)
        valid = b"".join(nc["Times"][0]).decode()
        hybrid = nc.getncattr("HYBRID_OPT")
        theta_m = nc.getncattr("USE_THETA_M")
    dz = np.diff(ph, axis=0) / G          # (nz, ny, nx)
    return {
        "mean": dz.mean(axis=(1, 2)),
        "min": dz.min(axis=(1, 2)),
        "max": dz.max(axis=(1, 2)),
        "valid": valid,
        "hybrid_opt": hybrid,
        "use_theta_m": theta_m,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True, help="label=run_dir (repeat)")
    ap.add_argument("--time", required=True, help="YYYY-MM-DD_HH_MM_SS")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    runs = []
    for spec in args.run:
        label, path = spec.split("=", 1)
        f = os.path.join(path, "wrfout_d01_%s" % args.time)
        runs.append((label, layer_stats(f)))
    ref_label, ref = runs[0]
    nz = len(ref["mean"])
    k = np.arange(1, nz + 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 6.5), constrained_layout=True)
    styles = {"mean": ("-", 2.0), "min": ("--", 1.2), "max": (":", 1.6)}
    for i, (label, s) in enumerate(runs):
        c = COLORS[i % len(COLORS)]
        tag = "%s (hybrid_opt=%d)" % (label, s["hybrid_opt"])
        for stat in ("mean", "min", "max"):
            ls, lw = styles[stat]
            ax1.plot(s[stat], k, color=c, ls=ls, lw=lw, label="%s, %s" % (tag, stat))
    ax1.set_xscale("log")
    ax1.set_xlabel("layer thickness (m)")
    ax1.set_ylabel("model level (1 = lowest)")
    ax1.set_title("Layer thickness over the domain")
    ax1.grid(alpha=0.3, which="both")
    ax1.legend(fontsize=8, loc="upper left")

    for i, (label, s) in enumerate(runs[1:], start=1):
        c = COLORS[i % len(COLORS)]
        for stat in ("mean", "min", "max"):
            ls, lw = styles[stat]
            ax2.plot(s[stat] - ref[stat], k, color=c, ls=ls, lw=lw,
                     label="%s - %s, %s" % (label, ref_label, stat))
    ax2.axvline(0, color="k", lw=0.6)
    ax2.set_xlabel("difference in layer thickness (m)")
    ax2.set_ylabel("model level (1 = lowest)")
    ax2.set_title("Difference from %s" % ref_label)
    ax2.grid(alpha=0.3)
    ax2.legend(fontsize=8, loc="best")

    fig.suptitle("WRF layer thickness, valid %s   (dz = d(PH+PHB)/g, %d layers, all columns)" %
                 (ref["valid"], nz))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    fig.savefig(args.out, dpi=130)
    print("wrote", args.out)

    print("\nlayer thickness (m):   level   " + "   ".join("%-26s" % l for l, _ in runs))
    for lev in (1, 2, 5, 10, 25, 50, 75, 100, 125, 149, nz):
        row = []
        for _, s in runs:
            row.append("%7.1f /%7.1f /%7.1f" % (s["mean"][lev - 1], s["min"][lev - 1], s["max"][lev - 1]))
        print("                        %5d   " % lev + "   ".join(row))
    print("(each cell: mean / min / max)")


if __name__ == "__main__":
    main()
