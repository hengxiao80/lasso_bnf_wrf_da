"""Check an obs_diag_output.nc against a recomputation from the obs_seq.final files it read.

Usage:
  .venv/bin/python scripts/da/check_obs_diag.py <diag dir> [--tol 1e-3]

<diag dir> is a directory written by scripts/da/run_obs_diag.sh. The obs_seq.final files are the ones named in
the file's global attributes (obs_seq_file_NNNNN), read one at a time; the time bins, level edges, trusted
types and the DART QCs counted in the rank histogram are taken from the file too. The rules are obs_diag.f90's
(DART 7bbd35a09: Bin4D, Bin3D, CountDartQC_4D, find_my_level, SetScaleFactors):

  bins: an observation belongs to the time bin whose bounds [start, end] (integer seconds) contain its time;
    surface types have one level, pressure types (hPa) bin by plevel_edges (p < upper edge, p >= lower edge),
    height types by hlevel_edges (h > lower edge, h <= upper edge), an observation on the lowest edge in bin 1;
  every observation in a bin and level counts in Nposs; prior statistics over DART QC 0-3, posterior over 0-1,
    with QC 7 added to both for a trusted type; a QC-7 observation whose posterior is missing counts as
    posterior QC 2;
  rmse = sqrt(mean (H(x) - y)^2), bias = mean (H(x) - y) (forecast minus observation, the opposite sign of the
    innovation d_b of notes/fulltest_d1_analysis.md), spread = sqrt(mean s^2), totalspread =
    sqrt(mean (s^2 + sigma_o^2)), observation and ens_mean the means of y and H(x);
  specific humidity in g/kg (values x 1000, error variance x 1e6), surface pressure in hPa.

Compared: per time bin, type and level the counts (Nposs, Nused, NbadDARTQC, N_DARTqc_0-8; exact) and the
statistics of _guess (prior) and _analy (posterior), and the time-pooled _VPguess and _VPanaly profiles of the
types with a vertical coordinate (relative difference against the recomputation; obs_diag sums in single
precision under r8 = r4). The derived HORIZONTAL_WIND variables are not checked. For the rank histograms
(_guess_RankHist): the total count per bin and level (exact), and the shape, pooled per type, against ranks
computed here with the same rule (each prior member plus Gaussian noise with the observation-error sd, rank =
number of noisy members below y, plus 1) but other random draws; max |z| is the largest difference over the
ranks of the two histograms' fractions in units of its binomial sd. For specific humidity a second set of
ranks uses the noise the stock obs_diag drew (the sd of the scaled error, in g/kg, added to members in
kg/kg). A shape with max |z| > 5 is marked but not counted as a failure. With the stock obs_diag (D1 and D2,
2026-11-13) the three specific-humidity types differed (max |z| 5-35, empty end ranks) and agreed with the
oversized-noise ranks (2-3): its humidity rank histograms were wrong. Fixed by
patches/dart_7bbd35a09_obs_diag_rank_hist_units.patch; with the patched obs_diag the humidity types agree
with the ranks here (1.8-2.5) and differ from the oversized-noise ones (9-36), like the other 13 types
(1.8-4.2; differences up to ~4 changed with the seed, --seed).

Each obs_seq.final is read whole (~6 s and ~1.5 GB for 213 MB on a login node). Exit status 1 if a count
differs or a relative difference exceeds --tol.
"""

import argparse
import os
import sys

import netCDF4
import numpy as np

MISSING = -888888.0
COPIES = ["Nposs", "Nused", "rmse", "bias", "spread", "totalspread", "NbadDARTQC", "observation", "ens_mean"]
COUNTS = ["Nposs", "Nused", "NbadDARTQC"] + [f"N_DARTqc_{k}" for k in range(9)]
STATS = ["rmse", "bias", "spread", "totalspread", "observation", "ens_mean"]


def read_final(path):
    """ASCII obs_seq.final with no per-observation metadata: copy names, QC names, type names by number, and
    per-observation arrays (values (nobs, ncopy), QCs (nobs, nqc), type number, lon, lat, vertical value,
    vertical code, time in seconds since 1601-01-01, error variance)."""
    with open(path) as f:
        lines = f.read().split("\n")
    assert lines[0].strip() == "obs_sequence" and lines[1].strip() == "obs_type_definitions"
    ntypes = int(lines[2])
    types = {int(l.split()[0]): l.split()[1] for l in lines[3:3 + ntypes]}
    i = 3 + ntypes
    w = lines[i].split(); ncopy, nqc = int(w[1]), int(w[3])
    nobs = int(lines[i + 1].split()[1])
    i += 2
    copies = [l.strip() for l in lines[i:i + ncopy]]; i += ncopy
    qcs = [l.strip() for l in lines[i:i + nqc]]; i += nqc
    assert lines[i].split()[0] == "first:"
    i += 1
    rec = ncopy + nqc + 9   # OBS, copies, QCs, links, obdef, loc3d, location, kind, type, time, error variance
    blk = np.array(lines[i:i + nobs * rec], dtype=object).reshape(nobs, rec)
    if not all(s.split()[0] == "OBS" for s in blk[:, 0]) or not all(s.strip() == "kind" for s in blk[:, rec - 4]):
        raise ValueError(f"{path}: records are not {rec} lines each (per-observation metadata?)")
    rest = lines[i + nobs * rec:]
    assert all(not l.strip() for l in rest), f"{path}: lines after the last record"
    vals = np.array(blk[:, 1:1 + ncopy].astype(str), dtype=float)
    qc = np.array(blk[:, 1 + ncopy:1 + ncopy + nqc].astype(str), dtype=float)
    loc = np.array([s.split()[:4] for s in blk[:, rec - 5]], dtype=float)
    kind = np.array(blk[:, rec - 3].astype(str), dtype=int)
    tm = np.array([s.split()[:2] for s in blk[:, rec - 2]], dtype=np.int64)
    ev = np.array(blk[:, rec - 1].astype(str), dtype=float)
    return dict(copies=copies, qcs=qcs, types=types, vals=vals, qc=qc, kind=kind, lon=loc[:, 0], lat=loc[:, 1],
                vert=loc[:, 2], vcode=loc[:, 3].astype(int), time=tm[:, 1] * 86400 + tm[:, 0], evar=ev)


def level_index(vert, vcode, pedges, hedges):
    """0-based level index as obs_diag's find_my_level (-1: outside the edges); surface (code -1) -> 0."""
    lev = np.full(len(vert), -1)
    lev[vcode == -1] = 0
    p = vcode == 2
    ph = vert[p] / 100.0
    lp = np.full(ph.shape, -1)
    for k in range(len(pedges) - 1):
        lp[(ph < pedges[k]) & (ph >= pedges[k + 1])] = k
    lp[ph == pedges[0]] = 0
    lev[p] = lp
    h = vcode == 3
    hh = vert[h]
    lh = np.full(hh.shape, -1)
    for k in range(len(hedges) - 1):
        lh[(hh > hedges[k]) & (hh <= hedges[k + 1])] = k
    lh[hh == hedges[0]] = 0
    lev[h] = lh
    if np.any(~np.isin(vcode, (-1, 2, 3))):
        raise ValueError(f"vertical codes {sorted(set(vcode) - {-1, 2, 3})} not handled")
    return lev


class Acc:
    """Sums per (bin, level) for one type and one of prior/posterior; bin -1 holds the time-pooled sums."""

    def __init__(self, nbins, nlev):
        self.s = {k: np.zeros((nbins + 1, nlev)) for k in COUNTS + ["sq", "b", "v", "vp", "o", "m"]}

    def add(self, b, lev, key, w):
        np.add.at(self.s[key], (b, lev), w)
        np.add.at(self.s[key], (np.full_like(b, -1), lev), w)

    def stats(self):
        s, n = self.s, self.s["Nused"]
        with np.errstate(invalid="ignore", divide="ignore"):
            out = dict(rmse=np.sqrt(s["sq"] / n), bias=s["b"] / n, spread=np.sqrt(s["v"] / n),
                       totalspread=np.sqrt(s["vp"] / n), observation=s["o"] / n, ens_mean=s["m"] / n)
        for k in COUNTS:
            out[k] = s[k]
        return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("diag")
    ap.add_argument("--tol", type=float, default=1e-3, help="largest relative difference allowed")
    ap.add_argument("--seed", type=int, default=12345, help="seed of the noise added to the members for the ranks")
    args = ap.parse_args()

    nc = netCDF4.Dataset(os.path.join(args.diag, "obs_diag_output.nc"))
    nc.set_auto_mask(False)
    files = [nc.getncattr(a) for a in sorted(a for a in nc.ncattrs() if a.startswith("obs_seq_file_"))]
    trusted = {nc.getncattr(a).strip() for a in nc.ncattrs() if a.startswith("trusted_obs_")}
    hist_qcs = np.atleast_1d(nc.getncattr("DART_QCs_in_histogram")) if "DART_QCs_in_histogram" in nc.ncattrs() \
        else np.array([], int)
    copy_names = [str(s).strip() for s in netCDF4.chartostring(nc["CopyMetaData"][:])]
    ci = {n: k for k, n in enumerate(copy_names)}
    tb = np.rint(nc["time_bounds"][:] * 86400).astype(np.int64)   # (nbins, 2), seconds since 1601-01-01
    nbins = len(tb)
    pedges, hedges = nc["plevel_edges"][:], nc["hlevel_edges"][:]
    print(f"{args.diag}: {len(files)} obs_seq.final, {nbins} time bins, trusted types: {len(trusted)}, "
          f"DART QCs in the rank histogram: {list(hist_qcs)}")

    acc = {}            # (type, "guess"/"analy") -> Acc
    ranks = {}          # type -> list of rank arrays (counted in the histogram), and the obs_diag-noise ranks
    hist_tot = {}       # type -> (nbins, nlev) counts
    nlev_of = {}
    rng = np.random.default_rng(args.seed)
    for path in files:
        d = read_final(path)
        cp = d["copies"]
        iobs = next(k for k, n in enumerate(cp) if n.endswith("observation"))
        ipm, ips = cp.index("prior ensemble mean"), cp.index("prior ensemble spread")
        iqm, iqs = cp.index("posterior ensemble mean"), cp.index("posterior ensemble spread")
        imem = [k for k, n in enumerate(cp) if n.startswith("prior ensemble member")]
        dq = d["qcs"].index("DART quality control")
        t = d["time"]
        b = np.full(len(t), -1)
        for k, (t0, t1) in enumerate(tb):
            b[(t >= t0) & (t <= t1)] = k
        lev = level_index(d["vert"], d["vcode"], pedges, hedges)
        qc = d["qc"][:, dq].astype(int)
        for kind, name in d["types"].items():
            sel = (d["kind"] == kind) & (b >= 0)
            if not sel.any():
                continue
            if np.any(lev[sel] < 0):
                raise SystemExit(f"{path}: {name}: {np.sum(lev[sel] < 0)} obs outside the level edges")
            sf = 1000.0 if "SPECIFIC_HUMIDITY" in name else (0.01 if "SURFACE_PRESSURE" in name else 1.0)
            vcodes = set(d["vcode"][sel])
            nlev = 1 if vcodes == {-1} else (len(pedges) - 1 if vcodes == {2} else len(hedges) - 1)
            nlev_of[name] = nlev
            bb, ll, q = b[sel], lev[sel], qc[sel]
            v = d["vals"][sel]
            y, ev = v[:, iobs] * sf, d["evar"][sel] * sf * sf
            tr = name in trusted
            for which, im, isd, good in (("guess", ipm, ips, (0, 1, 2, 3) + ((7,) if tr else ())),
                                         ("analy", iqm, iqs, (0, 1) + ((7,) if tr else ()))):
                a = acc.setdefault((name, which), Acc(nbins, nlev))
                qq = q.copy()
                if which == "analy":
                    qq[(q == 7) & (v[:, iqm] == MISSING)] = 2
                a.add(bb, ll, "Nposs", 1.0)
                for k in range(9):
                    m = qq == k
                    if m.any():
                        a.add(bb[m], ll[m], f"N_DARTqc_{k}", 1.0)
                u = np.isin(qq, good)
                a.add(bb[~u], ll[~u], "NbadDARTQC", 1.0)
                hx, s = v[u, im] * sf, v[u, isd] * sf
                a.add(bb[u], ll[u], "Nused", 1.0)
                a.add(bb[u], ll[u], "sq", (hx - y[u]) ** 2)
                a.add(bb[u], ll[u], "b", hx - y[u])
                a.add(bb[u], ll[u], "v", s ** 2)
                a.add(bb[u], ll[u], "vp", s ** 2 + ev[u])
                a.add(bb[u], ll[u], "o", y[u])
                a.add(bb[u], ll[u], "m", hx)
            if imem:
                h = np.isin(q, hist_qcs)
                ht = hist_tot.setdefault(name, np.zeros((nbins, nlev)))
                np.add.at(ht, (bb[h], ll[h]), 1)
                mem = v[h][:, imem]
                yy = v[h, iobs]
                sd = np.sqrt(d["evar"][sel][h])
                noisy = mem + rng.standard_normal(mem.shape) * sd[:, None]
                r = np.sum(noisy < yy[:, None], axis=1) + 1
                r2 = None
                if sf != 1.0:
                    noisy2 = mem + rng.standard_normal(mem.shape) * (sd * sf)[:, None]
                    r2 = np.sum(noisy2 < yy[:, None], axis=1) + 1
                ranks.setdefault(name, []).append((r, r2))
        print(f"  read {os.path.basename(os.path.dirname(os.path.dirname(path)))}: {len(t)} obs")

    bad = 0
    print(f"\n{'type':34s} {'':5s} {'counts':>7s} {'rmse':>8s} {'bias':>8s} {'spread':>8s} {'totsprd':>8s}"
          f" {'obs':>8s} {'mean':>8s}   (max relative difference; counts: number of mismatches)")
    for (name, which), a in sorted(acc.items()):
        ref = a.stats()
        nlev = nlev_of[name]
        for prof in ((False, True) if nlev_of[name] > 1 else (False,)):
            var = f"{name}_{'VP' if prof else ''}{which}"
            if var not in nc.variables:
                print(f"{name:34s} {which}: {var} missing"); bad += 1; continue
            x = nc[var][:]                        # (time, copy, level, region) or (copy, level, region)
            x = x[..., :nlev, 0] if not prof else x[:, :nlev, 0]
            sl = slice(None, -1) if not prof else -1
            nmis, rel = 0, {}
            for k in COUNTS:
                r = ref[k][sl]
                o = x[:, ci[k]] if not prof else x[ci[k]]
                nmis += int(np.sum(o != r))
            n = ref["Nused"][sl]
            for k in STATS:
                r = ref[k][sl]
                o = x[:, ci[k]] if not prof else x[ci[k]]
                ok = n > 0
                if np.any((o == MISSING) != ~ok):
                    nmis += int(np.sum((o == MISSING) != ~ok))
                scale = np.abs(ref["rmse"][sl]) if k == "bias" else np.abs(r)
                rel[k] = float(np.max(np.abs(o[ok] - r[ok]) / np.maximum(scale[ok], 1e-30))) if ok.any() else 0.0
            flag = nmis > 0 or max(rel.values()) > args.tol
            bad += flag
            label = ("VP" if prof else "") + which
            print(f"{name:34s} {label:7s} {nmis:5d} " + " ".join(f"{rel[k]:8.1e}" for k in STATS)
                  + ("  <--" if flag else ""))

    if hist_tot:
        print(f"\nRank histograms (pooled over time and levels): obs_diag against ranks recomputed here")
        print(f"{'type':34s} {'n':>8s} {'tot':>4s} {'first':>6s} {'last':>6s} {'here1':>6s} {'hereN':>6s}"
              f" {'max|z|':>7s} {'z(obs_diag noise)':>18s}")
        for name in sorted(hist_tot):
            full = f"{name}_guess_RankHist"          # obs_diag truncates names to 40 characters
            var = next((v for v in (full, full[:40]) if v in nc.variables), None)
            if var is None:
                print(f"{name:34s} no rank histogram variable"); continue
            h = nc[var][:][..., :nlev_of[name], 0]           # (time, rank, level)
            tot_ok = np.array_equal(h.sum(axis=1), hist_tot[name])
            bad += not tot_ok
            hd = h.sum(axis=(0, 2)).astype(float)
            r = np.concatenate([x[0] for x in ranks[name]])
            nb = h.shape[1]
            mine = np.bincount(r, minlength=nb + 1)[1:].astype(float)

            def zmax(p, q):
                na, nq = p.sum(), q.sum()
                pa, pq = p / na, q / nq
                pp = (p + q) / (na + nq)
                with np.errstate(invalid="ignore", divide="ignore"):
                    z = (pa - pq) / np.sqrt(pp * (1 - pp) * (1 / na + 1 / nq))
                return float(np.nanmax(np.abs(z)))

            z1 = zmax(hd, mine)
            z2 = ""
            if ranks[name][0][1] is not None:
                r2 = np.concatenate([x[1] for x in ranks[name]])
                z2 = f"{zmax(hd, np.bincount(r2, minlength=nb + 1)[1:].astype(float)):18.1f}"
            print(f"{name:34s} {int(hd.sum()):8d} {'ok' if tot_ok else 'DIFF':>4s} {hd[0] / hd.sum():6.3f}"
                  f" {hd[-1] / hd.sum():6.3f} {mine[0] / mine.sum():6.3f} {mine[-1] / mine.sum():6.3f}"
                  f" {z1:7.1f} {z2}" + ("  <-- shape" if z1 > 5 else ""))
    print(f"\n{'FAILED' if bad else 'PASSED'}: {bad} problem(s) (tolerance {args.tol:g})")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
