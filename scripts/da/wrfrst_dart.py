"""Move the DART state between a WRF restart file and a small DART-facing file.

Usage: .venv/bin/python scripts/da/wrfrst_dart.py extract <wrfrst|wrfinput> <dart_file> [--extra QCLOUD ...]
       .venv/bin/python scripts/da/wrfrst_dart.py insert  <dart_file> <wrfrst>
                                                 [--fields U V W PH THM MU QVAPOR] [--no-recompute]
                                                 [--hydrostatic-ph [--prior <dart_file>]]
       .venv/bin/python scripts/da/wrfrst_dart.py qnrain  <dart_file> --prior <dart_file>

A WRF restart file stores both Runge-Kutta time levels (U_1/U_2, THM_1/THM_2, MU_1/MU_2, ...), but
DART's WRF model_mod and update_wrf_bc look fields up by their wrfinput names (U, THM, MU, ...).

extract: writes <dart_file> (64-bit-offset netCDF, same dimensions and global attributes) with
  U V W PH THM MU from the current level (_2), QVAPOR, PSFC, T2, Q2, U10, V10 and Times as they are,
  T = THM (theta_m0: the boundary tools read T), and MUB, MAPFAC_U/V/M for update_wrf_bc. --extra
  adds more single-level fields (e.g. hydrometeors). filter updates this file in place.
  <wrfrst> may also be a wrfinput file (plain names, one time level), e.g. the initial members
  for filter tests (pilot step 11).

insert: writes the --fields from <dart_file> back into <wrfrst> in place, into both time levels
  of two-level fields (WRF copies _2 to _1 at the start of the first step anyway; _1 is otherwise
  read only by implicit vertical advection, which we don't use), clipping the moisture fields
  (QVAPOR, hydrometeors, QNRAIN: names starting with Q) at 0. Then, unless
  --no-recompute, recomputes the fields a restart takes from the file but a cold start derives
  (dyn_em/start_em.F), so the first step's physics and RK tendencies see consistent values:
    AL     from PH and MU (hypsometric_opt = 2), ALT = AL + ALB,
    P      from the equation of state (use_theta_m = 0), P_HYD = P + PB,
    T      = THM.
  P_HYD_W and T are also rediagnosed by WRF in phy_prep every step, and ALT in rk_step_prep.
  --hydrostatic-ph (opt-in): PH = prior PH (the restart file's, before the insert) + the hydrostatic
  PH increment from the new MU, THM and QVAPOR (check_hydrostatic_balance.py), replacing DART's PH
  increment. This keeps the model's own non-hydrostatic part and removes the vertical acoustic
  adjustment an unbalanced PH causes (fake-increment test, notes/da_5member_pilot_steps.md Sec. 4).
  Whether to make it the default is decided from the first real filter update (step 13).
  --prior takes the prior state from a file saved before the insert (e.g. the prior DART-facing
  file) instead of the restart file, so that rerunning an interrupted insert gives the same result
  (cycling, pilot step 12).
qnrain: after the MRMS pass (two-pass cycle), sets QNRAIN in <dart_file> wherever its QRAIN differs
  from the --prior file's (QRAIN is in the state but QNRAIN is not, as in HRRRDAS, whose fifth step
  rediagnoses QNRAIN from the analysed QRAIN; Dowell 2020). Rule (user, 2026-10-14): Thompson's own
  rule for rain without a number (module_mp_thompson.F, mp_thompson: nr <= R2), an exponential size
  distribution (mu_r = 0) with a median volume diameter of 1 mm:
     lambda = (3 + mu_r + 0.672) / 1 mm,  QNRAIN = QRAIN * lambda^3 / (pi * rho_w)  [per kg],
  (i.e. crg(2) / crg(3) * QRAIN * lambda^bm_r / am_r), and QNRAIN = 0 where QRAIN <= R1 = 1e-12.
  Points where QRAIN did not change keep their QNRAIN. The alternatives (fixed N0 = 8e6 m^-4, as
  Marshall-Palmer; keeping the prior mean size) are in notes/obs_expansion.md Sec. 8.4.
See notes/da_5member_pilot_steps.md step 7.
"""

import argparse
import os

import netCDF4
import numpy as np

from check_hydrostatic_balance import G, Grid, read_state

TWO_LEVEL = ["U", "V", "W", "PH", "THM", "MU"]
SINGLE = ["QVAPOR", "PSFC", "T2", "Q2", "U10", "V10", "MUB", "MAPFAC_U", "MAPFAC_V", "MAPFAC_M"]

# WRF constants (share/module_model_constants.F)
R_D, R_V, P1000MB, T0 = 287.0, 461.6, 100000.0, 300.0
CP = 3.5 * R_D
CPOVCV = CP / (CP - R_D)
RVOVRD = R_V / R_D

# Thompson rain (phys/module_mp_thompson.F): mu_r = 0, rho_w = 1000, am_r = pi rho_w / 6, bm_r = 3,
# crg(2) = Gamma(mu_r + 1) = 1, crg(3) = Gamma(bm_r + mu_r + 1) = 6; R1 = 1e-12 (smallest mixing ratio)
THOMPSON_R1 = 1.0e-12
THOMPSON_LAMR_1MM = (3.0 + 0.0 + 0.672) / 1.0e-3


def extract(rst_path, out_path, extra):
    with netCDF4.Dataset(rst_path) as rst:
        if rst.getncattr("USE_THETA_M") != 0:
            raise SystemExit(f"{rst_path}: USE_THETA_M != 0, T = THM does not hold")
        level = "_2" if "U_2" in rst.variables else ""   # wrfinput: one level, plain names
        names = {n: n + level for n in TWO_LEVEL}
        names.update({n: n for n in SINGLE + list(extra) + ["Times"]})
        names["T"] = "THM" + level
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


def insert(dart_path, rst_path, fields, do_recompute, hydrostatic_ph=False, prior_path=None):
    if hydrostatic_ph:
        grid, prior = Grid(rst_path), read_state(prior_path or rst_path)
    with netCDF4.Dataset(dart_path) as dart, netCDF4.Dataset(rst_path, "a") as rst:
        if dart["Times"][:].tobytes() != rst["Times"][:].tobytes():
            raise SystemExit(f"time mismatch: {dart_path} vs {rst_path}")
        for name in fields:
            field = np.asarray(dart[name][:])
            if name.startswith("Q"):
                field = np.maximum(field, 0.0)
            targets = [name + "_1", name + "_2"] if name in TWO_LEVEL else [name]
            for t in targets:
                rst[t][:] = field
        if hydrostatic_ph:
            new = read_state(dart_path)
            dph = grid.ph_hydro(new) - grid.ph_hydro(prior)
            rms = lambda a: np.sqrt((a ** 2).mean()) / G
            print(f"   PH increment (m): DART RMS {rms(new['PH'] - prior['PH']):.3g},"
                  f" hydrostatic RMS {rms(dph):.3g}, DART - hydrostatic RMS"
                  f" {rms(new['PH'] - prior['PH'] - dph):.3g}; hydrostatic one used")
            ph = (prior["PH"] + dph).astype(np.float32)
            for t in ("PH_1", "PH_2"):
                rst[t][0] = ph
        if do_recompute:
            for n, (rms, mx) in recompute(rst).items():
                print(f"   {n}: recomputed - file value: RMS {rms:.3g}, max {mx:.3g}")


def qnrain(dart_path, prior_path):
    with netCDF4.Dataset(prior_path) as pr:
        qr_prior = np.asarray(pr["QRAIN"][:], np.float64)
    with netCDF4.Dataset(dart_path, "a") as ds:
        qr = np.maximum(np.asarray(ds["QRAIN"][:], np.float64), 0.0)
        nr_old = np.asarray(ds["QNRAIN"][:], np.float64)
        changed = qr != qr_prior
        nr_new = np.where(qr > THOMPSON_R1, qr * THOMPSON_LAMR_1MM ** 3 / (np.pi * 1000.0), 0.0)
        ds["QNRAIN"][:] = np.where(changed, nr_new, nr_old).astype(np.float32)
    rain = changed & (qr > THOMPSON_R1)
    both = rain & (nr_old > 0)
    print(f"   QNRAIN: QRAIN changed at {changed.sum()} points, rain (> R1) at {rain.sum()},"
          f" of which {both.sum()} had a prior QNRAIN"
          + (f" (new / old: median {np.median(nr_new[both] / nr_old[both]):.3g})" if both.any() else ""))


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
    i.add_argument("--hydrostatic-ph", action="store_true")
    i.add_argument("--prior", help="prior state for --hydrostatic-ph (default: the restart file)")
    q = sub.add_parser("qnrain")
    q.add_argument("dart_file")
    q.add_argument("--prior", required=True, help="DART-facing file before the analysis")
    args = p.parse_args()
    if args.cmd == "extract":
        extract(args.wrfrst, args.dart_file, args.extra)
    elif args.cmd == "qnrain":
        qnrain(args.dart_file, args.prior)
    else:
        insert(args.dart_file, args.wrfrst, args.fields, not args.no_recompute, args.hydrostatic_ph,
               args.prior)


if __name__ == "__main__":
    main()
