"""Checks for the boundary test (pilot step 8): update_wrf_bc refit of a member boundary file at a
segment start inside a record, and WRF runs restarted with it.

Usage: .venv/bin/python scripts/da/check_boundary_refit.py bdy <pristine_wrfbdy> <refit_wrfbdy> <dart_file>
       .venv/bin/python scripts/da/check_boundary_refit.py runs <ref_run_dir> <run_dir> ...
                                                         [--times 00_30_00 00_45_00 01_00_00]
                                                         [--target-bdy <pristine_wrfbdy>]

bdy: recomputes in float32 what the patched update_wrf_bc should write (DART is built with r8 = r4 and
  -fp-model precise, so NumPy float32 should reproduce it bit for bit) and compares, per field:
  - B at the segment start = the state in the DART-facing file along the four sides, coupled as in
    module_couple_uv (U, V, W: x muu|muv|mut / mapfac) or x (MU + MUB) (T, PH, QVAPOR). T is built
    from THM, so this also checks T_B follows THM;
  - the tendency still reaches the record's end target: B_new + dt_new * BT_new = B_old + dt_old * BT_old
    (QVAPOR target clipped at 0, as the tool does);
  - QNWFA, QNIFA, QNBCA: B moved along the unchanged tendency to the segment start;
  - every other variable (hydrometeors, other number concentrations, ...) unchanged;
  - thisbdytime of the record = the DART file's Times.
  It also prints how far the member state at the edges is from what WRF would have interpolated from
  the pristine record (B_old + elapsed * BT_old): the size of the jump the refit removes.
runs: per run directory and output time, RMS and max of W, and RMS differences from the reference run
  of PSFC, MU, T, W, QVAPOR and RAINNC, in bands by distance from the nearest lateral edge (row 0 =
  specified zone, 1-3 relaxation zone (WRF defaults spec_zone = 1, relax_zone = 4), 4-9 the rest of
  spec_bdy_width = 10 (in wrfbdy but not read by WRF), 10-29, interior). With --target-bdy, also the outer row at the
  record end against the pristine file's end target (T, QVAPOR coupled, MU), which shows whether the
  tendencies took each run to the same perturbed target. Domain-mean |dpsfc/dt| from diag_print as in
  restart_increment_test.py.
"""

import argparse
import os

import netCDF4
import numpy as np

from restart_increment_test import diag_series, label

SIDES = ["BXS", "BXE", "BYS", "BYE"]
REFIT_3D = ["U", "V", "W", "PH", "T", "QVAPOR"]
SHIFT = ["QNWFA", "QNIFA", "QNBCA"]
BANDS = [(0, 0), (1, 3), (4, 9), (10, 29), (30, 10 ** 6)]
F32 = np.float32


def times(ds, name):
    return [b"".join(r).decode() for r in np.asarray(ds[name][:])]


def seconds(a, b):
    def t(s):
        return np.datetime64(s.replace("_", "T"))
    return float((t(b) - t(a)) / np.timedelta64(1, "s"))


def sides(f):
    """Boundary strips of a (k, j, i) or (j, i) field, in wrfbdy order (bdy_width, [k,] along)."""
    nw = 10
    if f.ndim == 2:
        f = f[None]
    xs = np.stack([f[:, :, l] for l in range(nw)])
    xe = np.stack([f[:, :, -1 - l] for l in range(nw)])
    ys = np.stack([f[:, l, :] for l in range(nw)])
    ye = np.stack([f[:, -1 - l, :] for l in range(nw)])
    out = dict(zip(SIDES, (xs, xe, ys, ye)))
    return {s: (v[:, 0] if v.shape[1] == 1 else v) for s, v in out.items()} if f.shape[0] == 1 else out


def coupled_state(dart):
    """The state update_wrf_bc couples, in float32 (module_couple_uv and the T/PH/QVAPOR loop)."""
    g = lambda n: np.asarray(dart[n][0], F32)
    mu, mub = g("MU"), g("MUB")
    mut = mu + mub
    ext_x = np.concatenate([mut[:, :1], mut, mut[:, -1:]], axis=1)
    muu = F32(0.5) * (ext_x[:, 1:] + ext_x[:, :-1])
    ext_y = np.concatenate([mut[:1], mut, mut[-1:]], axis=0)
    muv = F32(0.5) * (ext_y[1:] + ext_y[:-1])
    st = {"U": g("U") * muu / g("MAPFAC_U"), "V": g("V") * muv / g("MAPFAC_V"),
          "W": g("W") * mut / g("MAPFAC_M"), "MU": mu}
    for n, src in (("PH", "PH"), ("T", "THM"), ("QVAPOR", "QVAPOR")):
        st[n] = g(src) * mut
    return st


def rel_max(a, b):
    """max |a - b| / RMS(b), in float64"""
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    scale = np.sqrt((b ** 2).mean()) or 1.0
    return np.abs(a - b).max() / scale


def check_bdy(pristine_path, refit_path, dart_path):
    old, new, dart = (netCDF4.Dataset(p) for p in (pristine_path, refit_path, dart_path))
    t_state = times(dart, "Times")[0]
    t_bdy = times(old, "Times")
    this_old = times(old, "md___thisbdytimee_x_t_d_o_m_a_i_n_m_e_t_a_data_")
    nxt = times(old, "md___nextbdytimee_x_t_d_o_m_a_i_n_m_e_t_a_data_")
    it = max(i for i, t in enumerate(t_bdy) if t <= t_state)
    dt_old, dt_new = seconds(this_old[it], nxt[it]), seconds(t_state, nxt[it])
    elapsed = F32(dt_old - dt_new)
    print(f"state {t_state}; record {it}: {this_old[it]} -> {nxt[it]}; dt_old {dt_old:.0f} s, "
          f"dt_new {dt_new:.0f} s")
    this_new = times(new, "md___thisbdytimee_x_t_d_o_m_a_i_n_m_e_t_a_data_")
    print(f"thisbdytime of record {it} in the refit file: {this_new[it]} "
          f"({'OK' if this_new[it] == t_state else 'WRONG'}); other records "
          f"{'unchanged' if all(a == b for i, (a, b) in enumerate(zip(this_old, this_new)) if i != it) else 'CHANGED'}")

    st = {n: sides(f) for n, f in coupled_state(dart).items()}
    print("\nrefit fields, record", it, "(worst side): exact = fraction of points bit-identical to the "
          "float32 recompute; max rel = max |diff| / RMS")
    print(f"   {'field':7s} {'B exact':>8s} {'B max rel':>10s} {'BT exact':>9s} {'BT max rel':>11s} "
          f"{'reaches end':>12s} {'jump vs interp.':>16s} {'row 0':>9s}")
    checked = set()
    for n in REFIT_3D + ["MU"]:
        b_ex, b_rel, t_ex, t_rel, end_rel, jump, jump0 = [], [], [], [], [], [], []
        for s in SIDES:
            bo = np.asarray(old[f"{n}_{s}"][it], F32)
            to = np.asarray(old[f"{n}_BT{s[1:]}"][it], F32)
            bn = np.asarray(new[f"{n}_{s}"][it], F32)
            tn = np.asarray(new[f"{n}_BT{s[1:]}"][it], F32)
            checked.update({f"{n}_{s}", f"{n}_BT{s[1:]}"})
            want_b = st[n][s].astype(F32)
            scnd = to * F32(dt_old) + bo
            if n == "QVAPOR":
                scnd = np.maximum(F32(0), scnd)
            want_t = (scnd - want_b) / F32(dt_new)
            b_ex.append((bn == want_b).mean())
            b_rel.append(rel_max(bn, want_b))
            t_ex.append((tn == want_t).mean())
            t_rel.append(rel_max(tn, want_t) if np.any(want_t) else float(np.abs(tn).max()))
            end_rel.append(rel_max(np.float64(bn) + dt_new * np.float64(tn), scnd))
            interp = np.float64(bo) + float(elapsed) * np.float64(to)
            jump.append(np.sqrt(((np.float64(bn) - interp) ** 2).mean()) / (np.sqrt((interp ** 2).mean()) or 1))
            jump0.append(np.sqrt(((np.float64(bn[0]) - interp[0]) ** 2).mean()) / (np.sqrt((interp[0] ** 2).mean()) or 1))
        print(f"   {n:7s} {min(b_ex):8.4f} {max(b_rel):10.2e} {min(t_ex):9.4f} {max(t_rel):11.2e} "
              f"{max(end_rel):12.2e} {max(jump):16.2e} {max(jump0):9.2e}")
    print("   (reaches end: max |B_new + dt_new*BT_new - (B_old + dt_old*BT_old)| / RMS; jump: RMS of "
          "B_new - (B_old + elapsed*BT_old), relative, all rows and row 0)")
    if np.any(np.asarray(new["W_BXS"][it]) != 0):
        print("   note: W boundary values are now the member's W (real.exe wrote zeros). Harmless: with "
              "specified = .true. WRF never reads W_B/W_BT (zero gradient in the outer row)")

    print("\nshifted fields (B moved to the segment start along the unchanged tendency)")
    for n in SHIFT:
        if f"{n}_BXS" not in old.variables:
            continue
        worst_b, same_t = 0.0, True
        for s in SIDES:
            bo = np.asarray(old[f"{n}_{s}"][it], F32)
            to = np.asarray(old[f"{n}_BT{s[1:]}"][it], F32)
            bn = np.asarray(new[f"{n}_{s}"][it], F32)
            tn = np.asarray(new[f"{n}_BT{s[1:]}"][it], F32)
            checked.update({f"{n}_{s}", f"{n}_BT{s[1:]}"})
            worst_b = max(worst_b, rel_max(bn, bo + to * elapsed))
            same_t &= bool(np.array_equal(tn, to))
        print(f"   {n:7s} B max rel diff from B_old + elapsed*BT_old {worst_b:9.2e}; tendency "
              f"{'unchanged' if same_t else 'CHANGED'}")

    changed, nonzero_hydro = [], []
    for name, var in old.variables.items():
        if name in checked or name in ("Times",) or name.startswith("md___thisbdytime"):
            continue
        a, b = np.asarray(var[:]), np.asarray(new[name][:])
        if not np.array_equal(a, b):
            changed.append(name)
        if name.split("_B")[0] in ("QCLOUD", "QRAIN", "QICE", "QSNOW", "QGRAUP", "QNICE") and np.any(b != 0):
            nonzero_hydro.append(name)
    others = [n for n in new.variables if n not in checked]
    print(f"\nother variables: {len(others)} checked, changed: {changed or 'none'}")
    print(f"hydrometeor boundary values or tendencies nonzero: {nonzero_hydro or 'none'}")
    other_records = [n for n in REFIT_3D + ["MU"] + SHIFT if f"{n}_BXS" in old.variables and any(
        not np.array_equal(old[f"{n}_{s}"][i], new[f"{n}_{s}"][i])
        for s in SIDES for i in range(len(t_bdy)) if i != it)]
    print(f"refit/shifted fields changed in other records: {other_records or 'none'}")


def edge_distance(shape):
    ny, nx = shape
    j, i = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
    return np.minimum(np.minimum(i, nx - 1 - i), np.minimum(j, ny - 1 - j))


def band_rms(f, dist, lo, hi):
    m = (dist >= lo) & (dist <= hi)
    return np.sqrt((f[..., m] ** 2).mean()), np.abs(f[..., m]).max()


def check_runs(ref_dir, run_dirs, out_times, target_bdy, day):
    print("domain-mean |dpsfc/dt| (hPa/3h) from diag_print, from step 2")
    for d in [ref_dir] + run_dirs:
        s = diag_series(d)
        if len(s) == 0:
            print(f"   {label(d):12s} no diag_print lines")
            continue
        ps = s[1:, 1]
        print(f"   {label(d):12s} steps 2-8: " + " ".join(f"{x:6.0f}" for x in ps[:7])
              + f" | min 0-1 {ps[:11].mean():6.1f}, 1-5 {ps[11:59].mean():6.1f}, 5-15 {ps[59:179].mean():6.1f},"
              + (f" 15-45 {ps[179:].mean():6.1f}" if len(ps) > 179 else ""))
    bands = " ".join(f"{f'{lo}-{hi}' if hi < 10 ** 6 else f'>={lo}':>17s}" for lo, hi in BANDS)
    print(f"\nby distance from the edge (rows): RMS / max   {bands}")
    for t in out_times:
        fn = f"wrfout_d01_{day}_{t}"
        ref = netCDF4.Dataset(os.path.join(ref_dir, fn))
        dist = edge_distance(ref["PSFC"].shape[1:])
        print(f"{t}")
        for d in [ref_dir] + run_dirs:
            ds = netCDF4.Dataset(os.path.join(d, fn))
            w = np.asarray(ds["W"][0], np.float64)
            print(f"   {label(d):12s} W        " + " ".join(
                f"{r:8.3f} {m:8.2f}" for r, m in (band_rms(w, dist, *b) for b in BANDS)))
            if d == ref_dir:
                continue
            for n in ["PSFC", "MU", "T", "W", "QVAPOR", "RAINNC"]:
                diff = np.asarray(ds[n][0], np.float64) - np.asarray(ref[n][0], np.float64)
                print(f"   {'':12s} d{n:7s} " + " ".join(
                    f"{r:8.3g} {m:8.3g}" for r, m in (band_rms(diff, dist, *b) for b in BANDS)))
            ds.close()
        ref.close()

    if target_bdy:
        old = netCDF4.Dataset(target_bdy)
        nxt = times(old, "md___nextbdytimee_x_t_d_o_m_a_i_n_m_e_t_a_data_")
        this = times(old, "md___thisbdytimee_x_t_d_o_m_a_i_n_m_e_t_a_data_")
        end = nxt[0]
        fn = f"wrfout_d01_{end.replace(':', '_')}"
        if not os.path.exists(os.path.join(ref_dir, fn)):
            print(f"\nno {fn}: target check skipped")
            return
        dt = F32(seconds(this[0], end))
        print(f"\nouter row (specified zone) at {end} against the pristine record-end target "
              f"B + {dt:.0f} s * BT: max |diff| / RMS over the four sides")
        for d in [ref_dir] + run_dirs:
            ds = netCDF4.Dataset(os.path.join(d, fn))
            mut = np.asarray(ds["MU"][0], F32) + np.asarray(ds["MUB"][0], F32)
            st = {"MU": np.asarray(ds["MU"][0], F32), "T": np.asarray(ds["T"][0], F32) * mut,
                  "QVAPOR": np.asarray(ds["QVAPOR"][0], F32) * mut}
            out = []
            for n, f in st.items():
                sd = sides(f)
                worst = 0.0
                for s in SIDES:
                    target = np.asarray(old[f"{n}_{s}"][0], F32) + dt * np.asarray(old[f"{n}_BT{s[1:]}"][0], F32)
                    if n == "QVAPOR":
                        target = np.maximum(target, 0)
                    worst = max(worst, rel_max(sd[s][0], target[0]))
                out.append(f"{n} {worst:9.2e}")
            print(f"   {label(d):12s} " + "   ".join(out))
            ds.close()


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("bdy")
    a.add_argument("pristine_wrfbdy")
    a.add_argument("refit_wrfbdy")
    a.add_argument("dart_file")
    b = sub.add_parser("runs")
    b.add_argument("ref_run_dir")
    b.add_argument("run_dirs", nargs="+")
    b.add_argument("--day", default="2025-05-20")
    b.add_argument("--times", nargs="+", default=["00_30_00", "00_45_00", "01_00_00"])
    b.add_argument("--target-bdy")
    args = p.parse_args()
    if args.cmd == "bdy":
        check_bdy(args.pristine_wrfbdy, args.refit_wrfbdy, args.dart_file)
    else:
        check_runs(args.ref_run_dir, args.run_dirs, args.times, args.target_bdy, args.day)


if __name__ == "__main__":
    main()
