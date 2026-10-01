"""Move the DART state between a WRF restart file and a small DART-facing file.

Usage: .venv/bin/python scripts/da/wrfrst_dart.py extract <wrfrst> <dart_file> [--extra QCLOUD ...]
       .venv/bin/python scripts/da/wrfrst_dart.py insert  <dart_file> <wrfrst>
                                                 [--fields U V W PH THM MU QVAPOR] [--no-recompute]

A WRF restart file stores both Runge-Kutta time levels (U_1/U_2, THM_1/THM_2, MU_1/MU_2, ...), but
DART's WRF model_mod and update_wrf_bc look fields up by their wrfinput names (U, THM, MU, ...).

extract: writes <dart_file> (64-bit-offset netCDF, same dimensions and global attributes) with
  U V W PH THM MU from the current level (_2), QVAPOR, PSFC, T2, Q2, U10, V10 and Times as they are,
  T = THM (theta_m0: the boundary tools read T), and MUB, MAPFAC_U/V/M for update_wrf_bc. --extra
  adds more single-level fields (e.g. hydrometeors). filter updates this file in place.

insert: writes the --fields from <dart_file> back into <wrfrst> in place, into both time levels
  of two-level fields (WRF copies _2 to _1 at the start of the first step anyway; _1 is otherwise
  read only by implicit vertical advection, which we don't use), clipping QVAPOR at 0. Then, unless
  --no-recompute, recomputes the fields a restart takes from the file but a cold start derives
  (dyn_em/start_em.F), so the first step's physics and RK tendencies see consistent values:
    AL     from PH and MU (hypsometric_opt = 2), ALT = AL + ALB,
    P      from the equation of state (use_theta_m = 0), P_HYD = P + PB,
    T      = THM.
  P_HYD_W and T are also rediagnosed by WRF in phy_prep every step, and ALT in rk_step_prep.
See notes/da_5member_pilot_steps.md step 7.
"""

import argparse
import os

import netCDF4
import numpy as np

TWO_LEVEL = ["U", "V", "W", "PH", "THM", "MU"]
SINGLE = ["QVAPOR", "PSFC", "T2", "Q2", "U10", "V10", "MUB", "MAPFAC_U", "MAPFAC_V", "MAPFAC_M"]

# WRF constants (share/module_model_constants.F)
R_D, R_V, P1000MB, T0 = 287.0, 461.6, 100000.0, 300.0
CP = 3.5 * R_D
CPOVCV = CP / (CP - R_D)
RVOVRD = R_V / R_D


def extract(rst_path, out_path, extra):
    with netCDF4.Dataset(rst_path) as rst:
        if rst.getncattr("USE_THETA_M") != 0:
            raise SystemExit(f"{rst_path}: USE_THETA_M != 0, T = THM does not hold")
        names = {n: n + "_2" for n in TWO_LEVEL}
        names.update({n: n for n in SINGLE + list(extra) + ["Times"]})
        names["T"] = "THM_2"
        tmp = out_path + ".tmp"
        with netCDF4.Dataset(tmp, "w", format="NETCDF3_64BIT_OFFSET") as out:
            out.setncatts({a: rst.getncattr(a) for a in rst.ncattrs()})
            dims = set()
            for src in names.values():
                dims.update(rst[src].dimensions)
            for d in sorted(dims):
                out.createDimension(d, None if rst.dimensions[d].isunlimited() else len(rst.dimensions[d]))
            for name, src in names.items():
                v = out.createVariable(name, rst[src].dtype, rst[src].dimensions)
                v.setncatts({a: rst[src].getncattr(a) for a in rst[src].ncattrs()})
                v[:] = rst[src][:]
    os.replace(tmp, out_path)


def recompute(rst):
    """AL, ALT, P, P_HYD and T from PH_2, MU_2, THM_2, QVAPOR, as in start_em.F for a cold start."""
    f = lambda n: np.asarray(rst[n][0], np.float64)
    ph, phb, mu, mub = f("PH_2"), f("PHB"), f("MU_2"), f("MUB")
    thm, qv, alb, pb = f("THM_2"), f("QVAPOR"), f("ALB"), f("PB")
    c3f, c4f, c3h, c4h = f("C3F"), f("C4F"), f("C3H"), f("C4H")
    p_top = float(rst["P_TOP"][0])
    mass = (mub + mu)[None, :, :]
    pfu = c3f[1:, None, None] * mass + c4f[1:, None, None] + p_top
    pfd = c3f[:-1, None, None] * mass + c4f[:-1, None, None] + p_top
    phm = c3h[:, None, None] * mass + c4h[:, None, None] + p_top
    al = (ph[1:] - ph[:-1] + phb[1:] - phb[:-1]) / phm / np.log(pfd / pfu) - alb
    qvf = 1.0 + RVOVRD * qv
    p = P1000MB * ((R_D * (T0 + thm) * qvf) / (P1000MB * (al + alb))) ** CPOVCV - pb
    old = {n: np.asarray(rst[n][0], np.float64) for n in ("AL", "P")}
    rst["AL"][0] = al.astype(np.float32)
    rst["ALT"][0] = (al + alb).astype(np.float32)
    rst["P"][0] = p.astype(np.float32)
    rst["P_HYD"][0] = (p + pb).astype(np.float32)
    rst["T"][0] = thm.astype(np.float32)
    rms = lambda a: np.sqrt((a ** 2).mean())
    return {n: (rms(new - old[n]), np.abs(new - old[n]).max()) for n, new in (("AL", al), ("P", p))}


def insert(dart_path, rst_path, fields, do_recompute):
    with netCDF4.Dataset(dart_path) as dart, netCDF4.Dataset(rst_path, "a") as rst:
        if dart["Times"][:].tobytes() != rst["Times"][:].tobytes():
            raise SystemExit(f"time mismatch: {dart_path} vs {rst_path}")
        for name in fields:
            field = np.asarray(dart[name][:])
            if name == "QVAPOR":
                field = np.maximum(field, 0.0)
            targets = [name + "_1", name + "_2"] if name in TWO_LEVEL else [name]
            for t in targets:
                rst[t][:] = field
        if do_recompute:
            for n, (rms, mx) in recompute(rst).items():
                print(f"   {n}: recomputed - file value: RMS {rms:.3g}, max {mx:.3g}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("wrfrst")
    e.add_argument("dart_file")
    e.add_argument("--extra", nargs="*", default=[])
    i = sub.add_parser("insert")
    i.add_argument("dart_file")
    i.add_argument("wrfrst")
    i.add_argument("--fields", nargs="+", default=["U", "V", "W", "PH", "THM", "MU", "QVAPOR"])
    i.add_argument("--no-recompute", action="store_true")
    args = p.parse_args()
    if args.cmd == "extract":
        extract(args.wrfrst, args.dart_file, args.extra)
    else:
        insert(args.dart_file, args.wrfrst, args.fields, not args.no_recompute)


if __name__ == "__main__":
    main()
