"""Check the WRFDA perturbation bank as a whole (notes/fulltest_steps.md A3).

Usage: .venv/bin/python scripts/da/check_bank.py <perts_dir> [--draws 1-150] [--old 1-15] [--procs 16]

For every draw N: perts_dir/bank/pert_bank_NNN.nc (wrfda_bank_diff.py) and perts_dir/work/draw_NNN/
(run_wrfda_draw.sh). "Old" draws (--old) are the ones checked before, compared with the rest.
1. Seeds: 'Setting seed_array(1|2)' in rsl.out.0000 ... of each draw equal seed_array1 and
   seed_array2 * seed_array1 + rank * 1e7 (namelist.input; WRFDA's da_random_seed.inc), 16 ranks, and
   all draws' rank seeds are distinct.
2. Reports (draws with work/draw_NNN/check_wrfda_draw.txt): the variables that differ from fg are
   U V PH T THM MU P PSFC QVAPOR, and T = THM in the output.
3. Amplitudes (bank files, unscaled): per draw the RMS over the domain of U V THM QVAPOR (3-D) and MU;
   median and range over the draws, old against new, and draws outside 0.5-2 x the median flagged;
   then the median RMS by level of the old and of the new draws, every 10th level.
4. Correlations between draws: Pearson correlation over the horizontal field for every pair of draws,
   for U THM QVAPOR at levels 5 30 60 90 and for MU. Per field and level: mean, sd and max |r| over
   all pairs, the mean for old-old, old-new and new-new pairs, and the pairs with |r| > 0.9.
   With correlation lengths of 120-340 km in a 1370 x 970 km domain a field has few independent
   samples, so single pairs reach large |r| by chance; a repeated draw would give r = 1.
Exits 1 on a missing file, a seed problem, a non-finite value, an unexpected report or |r| > 0.99.
"""

import argparse
import glob
import os
import re
import sys
from multiprocessing import Pool

import netCDF4
import numpy as np

FIELDS3D = ["U", "V", "THM", "QVAPOR"]
CORR_FIELDS = ["U", "THM", "QVAPOR"]
CORR_LEVELS = [5, 30, 60, 90]
CHANGED = {"U", "V", "PH", "T", "THM", "MU", "P", "PSFC", "QVAPOR"}
NRANKS = 16
problems = []


def draw_range(s):
    a, _, b = s.partition("-")
    return list(range(int(a), int(b or a) + 1))


def read_draw(args):
    """Bank file of one draw -> (n, 3-D RMS per field, RMS profiles, fields for the correlations)."""
    n, path = args
    rms, prof, corr = {}, {}, {}
    with netCDF4.Dataset(path) as ds:
        ds.set_auto_mask(False)
        for name in FIELDS3D:
            a = np.asarray(ds[name][0], np.float64)
            if not np.all(np.isfinite(a)):
                return n, None, None, f"non-finite values in {name}"
            p2 = np.mean(a ** 2, axis=(1, 2))
            prof[name] = np.sqrt(p2)
            rms[name] = float(np.sqrt(p2.mean()))
            if name in CORR_FIELDS:
                for k in CORR_LEVELS:
                    corr[(name, k)] = a[k].ravel().astype(np.float32)
        mu = np.asarray(ds["MU"][0], np.float64)
        if not np.all(np.isfinite(mu)):
            return n, None, None, "non-finite values in MU"
        rms["MU"] = float(np.sqrt(np.mean(mu ** 2)))
        corr[("MU", 0)] = mu.ravel().astype(np.float32)
    return n, (rms, prof), corr, None


def check_seeds(work, draws):
    seen = {}
    for n in draws:
        d = os.path.join(work, f"draw_{n:03d}")
        try:
            text = open(os.path.join(d, "namelist.input")).read()
            s1, s2 = (int(re.search(rf"{k}\s*=\s*(-?\d+)", text).group(1)) for k in ("seed_array1", "seed_array2"))
        except (OSError, AttributeError) as e:
            problems.append(f"draw {n}: no seeds in namelist.input ({e})")
            continue
        logs = sorted(glob.glob(os.path.join(d, "rsl.out.[0-9][0-9][0-9][0-9]")))
        if len(logs) != NRANKS:
            problems.append(f"draw {n}: {len(logs)} rsl.out files, not {NRANKS}")
        for log in logs:
            rank = int(log[-4:])
            text = open(log).read()
            got1 = re.search(r"Setting seed_array\(1\) =\s*(-?\d+)", text)
            got2 = re.search(r"Setting seed_array\(2\) =\s*(-?\d+)", text)
            want2 = s2 * s1 + rank * 10_000_000
            if not got1 or not got2 or int(got1.group(1)) != s1 or int(got2.group(1)) != want2:
                problems.append(f"draw {n} rank {rank}: seeds {got1 and got1.group(1)} {got2 and got2.group(1)},"
                                f" expected {s1} {want2}")
                continue
            if want2 >= 2 ** 31:
                problems.append(f"draw {n} rank {rank}: seed {want2} overflows 32 bits")
            key = (s1, want2)
            if key in seen:
                problems.append(f"draw {n} rank {rank}: same seeds as draw {seen[key][0]} rank {seen[key][1]}")
            seen[key] = (n, rank)
    print(f"seeds: {len(seen)} distinct (seed_array1, seed_array2) pairs from {len(draws)} draws x {NRANKS} ranks"
          f" expected {len(draws) * NRANKS}; largest seed_array2 {max(k[1] for k in seen) if seen else '-'}")


def check_reports(work, draws):
    found = 0
    for n in draws:
        f = os.path.join(work, f"draw_{n:03d}", "check_wrfda_draw.txt")
        if not os.path.exists(f):
            continue
        found += 1
        text = open(f).read()
        if "== Variables that differ" not in text or "max |T - THM|" not in text:
            problems.append(f"draw {n}: incomplete {f}")
            continue
        block = text.split("== Variables that differ")[1].split("\n\n")[0].splitlines()[1:]
        changed = {line.split()[0] for line in block if line.strip()}
        if changed != CHANGED:
            problems.append(f"draw {n}: changed variables {sorted(changed)}, expected {sorted(CHANGED)}")
        m = re.search(r"max \|T - THM\| output = (\S+) K", text)
        if not m or float(m.group(1)) != 0.0:
            problems.append(f"draw {n}: T - THM in the output {m and m.group(1)}")
    print(f"check reports: {found} found; changed variables and T = THM checked")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("perts_dir")
    p.add_argument("--draws", type=draw_range, default=draw_range("1-150"))
    p.add_argument("--old", type=draw_range, default=draw_range("1-15"))
    p.add_argument("--procs", type=int, default=16)
    args = p.parse_args()
    draws, old = args.draws, set(args.old)
    work, bank = os.path.join(args.perts_dir, "work"), os.path.join(args.perts_dir, "bank")

    print(f"bank {os.path.realpath(bank)}: draws {draws[0]}-{draws[-1]} ({len(draws)}), old {min(old)}-{max(old)}")
    paths = [(n, os.path.join(bank, f"pert_bank_{n:03d}.nc")) for n in draws]
    missing = [n for n, f in paths if not os.path.exists(f)]
    if missing:
        problems.append(f"no bank file for draws {missing}")
        paths = [(n, f) for n, f in paths if n not in missing]
    check_seeds(work, draws)
    check_reports(work, draws)

    rms, prof, corr = {}, {}, {}
    with Pool(args.procs) as pool:
        for n, stats, fields, err in pool.imap_unordered(read_draw, paths):
            if err:
                problems.append(f"draw {n}: {err}")
                continue
            rms[n], prof[n] = stats
            for key, v in fields.items():
                corr.setdefault(key, {})[n] = v
    ok = sorted(rms)
    new = [n for n in ok if n not in old]
    olds = [n for n in ok if n in old]

    # --- amplitudes ---------------------------------------------------------------------------
    names = FIELDS3D + ["MU"]
    unit = {"U": "m/s", "V": "m/s", "THM": "K", "QVAPOR": "g/kg", "MU": "Pa"}
    scale = {"QVAPOR": 1000.0}
    print("\n== RMS over the domain per draw (unscaled bank files)")
    print("   draw " + " ".join(f"{n + ' ' + unit[n]:>13s}" for n in names))
    for n in ok:
        print(f"   {n:4d} " + " ".join(f"{rms[n][k] * scale.get(k, 1):13.4g}" for k in names))
    print("\n   field         median     min     max   median old  median new  new/old")
    for k in names:
        v = np.array([rms[n][k] for n in ok]) * scale.get(k, 1)
        mo = np.median([rms[n][k] for n in olds]) * scale.get(k, 1) if olds else np.nan
        mn = np.median([rms[n][k] for n in new]) * scale.get(k, 1) if new else np.nan
        med = np.median(v)
        print(f"   {k:10s} {med:9.4g} {v.min():7.4g} {v.max():7.4g} {mo:11.4g} {mn:11.4g} {mn / mo:8.3f}")
        out = [n for n in ok if not 0.5 <= rms[n][k] * scale.get(k, 1) / med <= 2.0]
        if out:
            print(f"      outside 0.5-2 x median: draws {out}")
    if olds and new:
        nz = len(prof[ok[0]]["U"])
        print("\n== median RMS by level, old / new draws")
        print("   lev  " + " ".join(f"{k + ' ' + unit[k]:>17s}" for k in FIELDS3D))
        for lev in list(range(0, nz, 10)) + [nz - 1]:
            cells = []
            for k in FIELDS3D:
                a = np.median([prof[n][k][lev] for n in olds]) * scale.get(k, 1)
                b = np.median([prof[n][k][lev] for n in new]) * scale.get(k, 1)
                cells.append(f"{a:8.3g} /{b:8.3g}")
            print(f"   {lev:3d}  " + " ".join(f"{c:>17s}" for c in cells))

    # --- correlations between draws ---------------------------------------------------------------
    print(f"\n== correlation between draws over the horizontal field ({len(ok)} draws,"
          f" {len(ok) * (len(ok) - 1) // 2} pairs)")
    print("   field   lev   mean     sd  max|r|  mean old-old  old-new  new-new  pairs |r|>0.9")
    for (k, lev), byn in sorted(corr.items(), key=lambda kv: (names.index(kv[0][0]), kv[0][1])):
        x = np.array([byn[n] for n in ok], np.float64)
        x -= x.mean(axis=1, keepdims=True)
        x /= np.linalg.norm(x, axis=1, keepdims=True)
        r = x @ x.T
        iu = np.triu_indices(len(ok), 1)
        rr = r[iu]
        isold = np.array([n in old for n in ok])
        oo, on = isold[iu[0]] & isold[iu[1]], isold[iu[0]] ^ isold[iu[1]]
        nn = ~isold[iu[0]] & ~isold[iu[1]]
        grp = [rr[g].mean() if g.any() else np.nan for g in (oo, on, nn)]
        big = [(ok[i], ok[j], r[i, j]) for i, j in zip(*iu) if abs(r[i, j]) > 0.9]
        print(f"   {k:7s} {lev:3d} {rr.mean():6.3f} {rr.std():6.3f} {np.abs(rr).max():7.3f}"
              f" {grp[0]:13.3f} {grp[1]:8.3f} {grp[2]:8.3f}  {len(big)}")
        for i, j, v in big[:10]:
            print(f"      draws {i} and {j}: r = {v:.3f}")
        if np.abs(rr).max() > 0.99:
            problems.append(f"{k} level {lev}: |r| = {np.abs(rr).max():.4f} between two draws")

    if problems:
        print("\nPROBLEMS:\n" + "\n".join(f"   {q}" for q in problems))
        sys.exit(1)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
