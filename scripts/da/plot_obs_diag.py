"""Figures from obs_diag_output.nc files written by scripts/da/run_obs_diag.sh.

Usage:
  .venv/bin/python scripts/da/plot_obs_diag.py --all <diag dir> --assim <diag dir> --out <figure dir>
      [--figs refl_time,refl_height,rank] [--tag <file name prefix>]

--all, --assim: the run_obs_diag.sh directories of the two selections ("all": every type trusted, prior
statistics over DART QC 0 or 7 as in notes/fulltest_d1_analysis.md Sec. 3.1, posterior over QC 0, 1 or 7;
"assim": DART's default, prior and posterior over QC 0 and 1). Statistics as obs_diag defines them (rmse of the
ensemble mean, spread = sqrt(mean s^2), total spread = sqrt(mean(s^2 + sigma_o^2))); the bias is plotted as the
innovation y - H(x) (obs_diag stores H(x) - y). Pooling over levels weights each level by its count (rmse,
spread and total spread pooled as mean squares).

Figures (PNG, 150 dpi, 7 in wide for a letter page):
  refl_time:   RADAR_REFLECTIVITY per cycle: rmse, bias (as y - H(x)), spread and total spread, prior and
               posterior, for both selections; spread / rmse and total spread / rmse (1 for an ensemble whose
               spread, plus the assigned obs error for the total, matches its error); the share of outliers
               (QC 7) among the obs with a valid prior; the number of obs in each selection.
  refl_height: RADAR_REFLECTIVITY by MRMS height, pooled over the cycles (obs_diag's _VPguess, _VPanaly).
  rank:        prior rank histograms pooled over the cycles and levels, for the types in RANK_TYPES. The
               specific-humidity ones need obs_diag with patches/dart_7bbd35a09_obs_diag_rank_hist_units.patch
               (built 2026-11-13); the stock obs_diag's are wrong (scripts/da/check_obs_diag.py).
"""

import argparse
import datetime as dt
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import netCDF4  # noqa: E402
import numpy as np  # noqa: E402

# Categorical slots 1-3 of the dataviz reference palette (validated all-pairs, light mode); text and grid inks.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
RANK_TYPES = ["RADAR_REFLECTIVITY", "RADAR_CLEARAIR_REFLECTIVITY", "METAR_TEMPERATURE_2_METER",
              "LAND_SFC_TEMPERATURE", "LAND_SFC_U_WIND_COMPONENT", "ACARS_TEMPERATURE",
              "METAR_SPECIFIC_HUMIDITY_2_METER", "LAND_SFC_SPECIFIC_HUMIDITY", "ACARS_SPECIFIC_HUMIDITY"]
SHORT = {"RADAR_REFLECTIVITY": "Radar reflectivity", "RADAR_CLEARAIR_REFLECTIVITY": "Clear-air reflectivity",
         "METAR_TEMPERATURE_2_METER": "METAR T2", "LAND_SFC_TEMPERATURE": "Mesonet T",
         "LAND_SFC_U_WIND_COMPONENT": "Mesonet u", "ACARS_TEMPERATURE": "ACARS T",
         "METAR_SPECIFIC_HUMIDITY_2_METER": "METAR q2", "LAND_SFC_SPECIFIC_HUMIDITY": "Mesonet q",
         "ACARS_SPECIFIC_HUMIDITY": "ACARS q"}

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "legend.fontsize": 7,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.edgecolor": INK2, "axes.labelcolor": INK,
    "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.linewidth": 0.6,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "figure.facecolor": "white", "savefig.facecolor": "white", "lines.linewidth": 1.5,
})


class Diag:
    def __init__(self, path):
        self.nc = netCDF4.Dataset(os.path.join(path, "obs_diag_output.nc"))
        self.nc.set_auto_mask(False)
        names = [str(s).strip() for s in netCDF4.chartostring(self.nc["CopyMetaData"][:])]
        self.c = {n: k for k, n in enumerate(names)}
        t0 = dt.datetime(1601, 1, 1)
        self.time = [t0 + dt.timedelta(seconds=round(float(t) * 86400)) for t in self.nc["time"][:]]

    def series(self, name, which="guess"):
        """Per time bin, pooled over levels: n used, rmse, innovation bias, spread, total spread, outlier share."""
        x = self.nc[f"{name}_{which}"][:, :, :, 0]               # (time, copy, level)
        c = self.c
        n = x[:, c["Nused"]]
        w = np.where(n > 0, n, 0.0)
        val = lambda q: np.where(n > 0, x[:, c[q]], 0.0)        # noqa: E731
        with np.errstate(invalid="ignore", divide="ignore"):
            out = dict(n=w.sum(1),
                       rmse=np.sqrt((w * val("rmse") ** 2).sum(1) / w.sum(1)),
                       bias=-(w * val("bias")).sum(1) / w.sum(1),
                       spread=np.sqrt((w * val("spread") ** 2).sum(1) / w.sum(1)),
                       totalspread=np.sqrt((w * val("totalspread") ** 2).sum(1) / w.sum(1)),
                       q7=x[:, c["N_DARTqc_7"]].sum(1) / (x[:, c["Nposs"]].sum(1) - x[:, c["N_DARTqc_4"]].sum(1)))
        return out

    def profile(self, name, which="guess"):
        x = self.nc[f"{name}_VP{which}"][:, :, 0]                # (copy, level)
        c = self.c
        n = x[c["Nused"]]
        ok = n > 0
        get = lambda q: np.where(ok, x[c[q]], np.nan)            # noqa: E731
        return dict(n=n, rmse=get("rmse"), bias=-get("bias"), spread=get("spread"),
                    totalspread=get("totalspread"),
                    q7=x[c["N_DARTqc_7"]] / np.maximum(x[c["Nposs"]] - x[c["N_DARTqc_4"]], 1))

    def rank(self, name):
        full = f"{name}_guess_RankHist"
        var = next(v for v in (full, full[:40]) if v in self.nc.variables)
        return self.nc[var][:][..., 0].sum(axis=(0, 2)).astype(float)   # (rank,)


def time_axis(ax):
    ax.xaxis.set_major_locator(mdates.HourLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H"))
    ax.set_xlabel("05-20, UTC hour (analysis time)")


# The four statistics of a time-series panel: obs_diag copy, legend label, colour.
STAT_STYLE = (("rmse", "rmse", BLUE), ("totalspread", "total spread", AQUA), ("spread", "spread", ORANGE),
              ("bias", "bias, y - H(x)", INK2))


def stats_panel(ax, d, name, which, title):
    s = d.series(name, which)
    ax.axhline(0, color=INK2, lw=0.6)
    for key, label, color in STAT_STYLE:
        ax.plot(d.time, s[key], color=color, label=label)
    ax.set_title(title, loc="left")
    ax.set_ylabel("dBZ")
    ax.legend(loc="upper right", ncol=2, fontsize=6.5, handlelength=2.5)
    time_axis(ax)


def ratio_panel(ax, d, name, title, legend):
    """spread / rmse and total spread / rmse, prior (solid) and posterior (dashed)."""
    ax.axhline(1, color=INK2, lw=0.6)
    for which, ls, stage in (("guess", "-", "prior"), ("analy", "--", "posterior")):
        s = d.series(name, which)
        ax.plot(d.time, s["spread"] / s["rmse"], color=ORANGE, ls=ls, label=f"spread / rmse, {stage}")
        ax.plot(d.time, s["totalspread"] / s["rmse"], color=AQUA, ls=ls, label=f"total spread / rmse, {stage}")
    ax.set_title(title, loc="left")
    ax.set_ylabel("ratio")
    time_axis(ax)
    if legend:
        ax.legend(loc="upper left", ncol=1, handlelength=3, fontsize=6.5)


def fig_refl_time(da, ds, out):
    name = "RADAR_REFLECTIVITY"
    fig, axs = plt.subplots(4, 2, figsize=(7, 9.2), sharex=True, layout="constrained")
    stats_panel(axs[0, 0], da, name, "guess", "(a) Prior, all obs with a valid prior (QC 0 or 7)")
    stats_panel(axs[0, 1], ds, name, "guess", "(b) Prior, assimilated obs (QC 0)")
    stats_panel(axs[1, 0], da, name, "analy", "(c) Posterior, QC 0 or 7")
    stats_panel(axs[1, 1], ds, name, "analy", "(d) Posterior, QC 0")
    lo = min(ax.get_ylim()[0] for ax in axs[:2].flat)
    hi = max(ax.get_ylim()[1] for ax in axs[:2].flat)
    for ax in axs[:2].flat:
        ax.set_ylim(lo, hi)
    ratio_panel(axs[2, 0], da, name, "(e) Spread / rmse, QC 0 or 7", True)
    ratio_panel(axs[2, 1], ds, name, "(f) Spread / rmse, QC 0", False)
    lo = min(ax.get_ylim()[0] for ax in axs[2])
    hi = max(ax.get_ylim()[1] for ax in axs[2])
    for ax in axs[2]:
        ax.set_ylim(min(lo, 0), hi)
    for ax in axs[:3].flat:
        ax.set_xlabel("")
    a, s = da.series(name), ds.series(name)
    ax = axs[3, 0]
    ax.plot(da.time, 100 * a["q7"], color=BLUE)
    ax.set_title("(g) Outliers (QC 7), % of obs with a valid prior", loc="left")
    ax.set_ylabel("%")
    ax.set_ylim(0, None)
    time_axis(ax)
    ax = axs[3, 1]
    ax.plot(da.time, a["n"] / 1000, color=BLUE, label="QC 0 or 7")
    ax.plot(ds.time, s["n"] / 1000, color=BLUE, ls="--", label="QC 0")
    ax.set_title("(h) Observations per cycle", loc="left")
    ax.set_ylabel("thousands")
    ax.set_ylim(0, None)
    ax.legend(loc="lower right", handlelength=3)
    time_axis(ax)
    fig.suptitle("Radar reflectivity in observation space, 50 members, 05-20 00:15-06:00 (24 cycles)",
                 x=0.01, ha="left", fontsize=9)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def fig_refl_height(da, ds, out):
    h = da.nc["hlevel"][:] / 1000.0
    fig, axs = plt.subplots(1, 3, figsize=(7, 3.7), sharey=True, layout="constrained",
                            gridspec_kw=dict(width_ratios=[1.3, 1.3, 0.8]))
    for ax, d, title in ((axs[0], da, "(a) All obs (QC 0 or 7)"), (axs[1], ds, "(b) Assimilated (QC 0)")):
        pr, po = d.profile("RADAR_REFLECTIVITY", "guess"), d.profile("RADAR_REFLECTIVITY", "analy")
        ax.plot(pr["rmse"], h, color=BLUE, marker="o", ms=3, label="rms, prior")
        ax.plot(po["rmse"], h, color=BLUE, ls="--", marker="o", ms=3, label="rms, posterior")
        ax.plot(pr["totalspread"], h, color=AQUA, marker="o", ms=3, label="total spread, prior")
        ax.plot(pr["spread"], h, color=ORANGE, marker="o", ms=3, label="spread, prior")
        ax.plot(pr["bias"], h, color=INK2, lw=1, marker="o", ms=3, label="bias y - H(x), prior")
        ax.axvline(0, color=INK2, lw=0.6)
        ax.set_title(title, loc="left")
        ax.set_xlabel("dBZ")
    axs[0].set_ylabel("height (km)")
    lo = min(axs[0].get_xlim()[0], axs[1].get_xlim()[0])
    hi = max(axs[0].get_xlim()[1], axs[1].get_xlim()[1])
    for ax in axs[:2]:
        ax.set_xlim(lo, hi)
    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=5, fontsize=6.5, handlelength=3.5)
    q = da.profile("RADAR_REFLECTIVITY")["q7"]
    axs[2].plot(100 * q, h, color=BLUE, marker="o", ms=3)
    axs[2].set_title("(c) Outliers, %", loc="left")
    axs[2].set_xlabel("%")
    axs[2].set_xlim(0, None)
    axs[2].set_yticks(h)
    axs[2].set_yticklabels([f"{x:g}" for x in h])
    fig.suptitle("Radar reflectivity by MRMS height, pooled over 05-20 00:15-06:00 (24 cycles)",
                 x=0.01, ha="left", fontsize=9)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def fig_rank(da, ds, out):
    panels = [(ds, "RADAR_REFLECTIVITY", "QC 0 only")] + [(da, t, "QC 0 or 7") for t in RANK_TYPES]
    ncol = 3
    nrow = int(np.ceil(len(panels) / ncol))
    fig, axs = plt.subplots(nrow, ncol, figsize=(7, 1.9 * nrow), constrained_layout=True)
    for k, (ax, (d, name, sel)) in enumerate(zip(axs.flat, panels)):
        h = d.rank(name)
        nb = len(h)
        ax.bar(np.arange(1, nb + 1), h / h.sum() * nb, width=0.75, color=BLUE)
        ax.axhline(1, color=INK2, lw=0.6)
        ax.set_title(f"({chr(97 + k)}) {SHORT.get(name, name)}\n{sel}, n = {int(h.sum()):,}", loc="left",
                     fontsize=7.5)
        ax.set_xlim(0, nb + 1)
        ax.set_xticks([1, 26, 51])
        ax.grid(axis="x", visible=False)
    for ax in axs.flat[len(panels):]:
        ax.set_visible(False)
    for j in range(ncol):                                  # x label on the lowest panel of each column
        col = [ax for ax in axs[:, j] if ax.get_visible()]
        if col:
            col[-1].set_xlabel("rank of y among 50 prior members")
    for ax in axs[:, 0]:
        ax.set_ylabel("frequency / uniform")
    fig.suptitle("Prior rank histograms (members plus obs-error noise), pooled over 05-20 00:15-06:00",
                 x=0.01, ha="left", fontsize=9)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", required=True)
    ap.add_argument("--assim", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--figs", default="refl_time,refl_height,rank")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    da, ds = Diag(args.all), Diag(args.assim)
    funcs = dict(refl_time=fig_refl_time, refl_height=fig_refl_height, rank=fig_rank)
    for f in args.figs.split(","):
        path = os.path.join(args.out, f"{args.tag}{f}.png")
        funcs[f](da, ds, path)
        print(path)


if __name__ == "__main__":
    main()
