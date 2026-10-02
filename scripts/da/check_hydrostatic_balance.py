"""Check how far an updated state is from hydrostatic balance, and whether its PH increment is the
hydrostatic one.

Usage: .venv/bin/python scripts/da/check_hydrostatic_balance.py <static> <prior> <state> [<state> ...]

<static>: a wrfrst or wrfinput file of the same grid, for PHB, MUB, C3F/C4F/C3H/C4H and P_TOP.
<prior>, <state>: wrfrst files (current level _2 is read), DART-facing files from wrfrst_dart.py, or
  wrfinput files. <prior> is the reference (e.g. a member's prior); each <state> is compared with it
  (e.g. the same member after filter, or after a fake increment).

For each file, prints the non-hydrostatic pressure departure
    p_nh = p from the equation of state (density from PH and MU, hypsometric_opt = 2, use_theta_m = 0)
           - moist hydrostatic pressure (p_top + dry and vapor mass above, from MU and QVAPOR),
RMS over the domain and at a few levels. The prior's p_nh is the model's own non-hydrostatic part
(plus discretization of this diagnostic); for a state, the RMS change from the prior is what matters.

For each state also: the hydrostatic PH increment (PH recomputed hydrostatically from the state's MU,
THM and QVAPOR, minus the same from the prior's), the state's own PH increment and their difference,
and p_nh again with PH = prior PH + hydrostatic increment, which keeps the prior's non-hydrostatic part.
See notes/da_5member_pilot_steps.md Sec. 4, "Initial adjustment in the fake-increment test".
"""

import argparse

import netCDF4
import numpy as np

# WRF constants (share/module_model_constants.F)
R_D, R_V, P1000MB, T0, G = 287.0, 461.6, 100000.0, 300.0, 9.81
CP = 3.5 * R_D
CPOVCV = CP / (CP - R_D)
RVOVRD = R_V / R_D
LEVELS = [0, 10, 30, 60, 100]


class Grid:
    def __init__(self, path):
        with netCDF4.Dataset(path) as ds:
            f = lambda n: np.asarray(ds[n][0], np.float64)
            self.phb, self.mub = f("PHB"), f("MUB")
            self.c3f, self.c4f, self.c3h, self.c4h = f("C3F"), f("C4F"), f("C3H"), f("C4H")
            self.p_top = float(ds["P_TOP"][0])

    def levels(self, mu):
        """Dry full- and half-level pressures, and log(p_below / p_above) per layer."""
        mass = (self.mub + mu)[None]
        pf = self.c3f[:, None, None] * mass + self.c4f[:, None, None] + self.p_top
        phm = self.c3h[:, None, None] * mass + self.c4h[:, None, None] + self.p_top
        return pf, phm, np.log(pf[:-1] / pf[1:])

    def p_eos(self, s):
        pf, phm, dlog = self.levels(s["MU"])
        alt = (s["PH"][1:] - s["PH"][:-1] + self.phb[1:] - self.phb[:-1]) / phm / dlog
        return P1000MB * (R_D * (T0 + s["THM"]) * (1 + RVOVRD * s["QVAPOR"]) / (P1000MB * alt)) ** CPOVCV

    def p_hydro(self, s):
        pf, _, _ = self.levels(s["MU"])
        dm = (pf[:-1] - pf[1:]) * (1 + s["QVAPOR"])
        above = np.cumsum(dm[::-1], axis=0)[::-1]
        return self.p_top + above - 0.5 * dm

    def ph_hydro(self, s):
        """PH integrated from the surface so that the EOS pressure equals the hydrostatic one."""
        pf, phm, dlog = self.levels(s["MU"])
        alt = (R_D * (T0 + s["THM"]) * (1 + RVOVRD * s["QVAPOR"]) / P1000MB
               * (self.p_hydro(s) / P1000MB) ** (-1 / CPOVCV))
        phi = np.empty_like(s["PH"])
        phi[0] = s["PH"][0] + self.phb[0]
        phi[1:] = phi[0] + np.cumsum(alt * phm * dlog, axis=0)
        return phi - self.phb


def read_state(path):
    with netCDF4.Dataset(path) as ds:
        lev = "_2" if "PH_2" in ds.variables else ""
        s = {n: np.asarray(ds[n + lev][0], np.float64) for n in ("PH", "MU", "THM")}
        s["QVAPOR"] = np.maximum(np.asarray(ds["QVAPOR"][0], np.float64), 0.0)
    return s


rms = lambda a: np.sqrt((a ** 2).mean())


def report(tag, pnh, ref=None):
    by_lev = np.sqrt((pnh ** 2).mean(axis=(1, 2)))
    line = (f"   {tag:30s} p_nh RMS {rms(pnh):7.1f} Pa, max {np.abs(pnh).max():6.0f}"
            f" | k = {','.join(map(str, LEVELS))}: " + " ".join(f"{by_lev[k]:6.1f}" for k in LEVELS))
    if ref is not None:
        line += f" | change from prior RMS {rms(pnh - ref):6.1f} Pa"
    print(line)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("static")
    p.add_argument("prior")
    p.add_argument("states", nargs="+")
    args = p.parse_args()

    grid = Grid(args.static)
    prior = read_state(args.prior)
    pnh0 = grid.p_eos(prior) - grid.p_hydro(prior)
    ph_h0 = grid.ph_hydro(prior)
    print(f"prior {args.prior}")
    report("prior", pnh0)
    for path in args.states:
        s = read_state(path)
        print(f"state {path}")
        report("as is", grid.p_eos(s) - grid.p_hydro(s), pnh0)
        dph_h = grid.ph_hydro(s) - ph_h0
        dph = s["PH"] - prior["PH"]
        report("PH = prior + hydrostatic incr.", grid.p_eos(dict(s, PH=prior["PH"] + dph_h))
               - grid.p_hydro(s), pnh0)
        print(f"   PH increment (m): hydrostatic RMS {rms(dph_h) / G:.2f}, max {np.abs(dph_h).max() / G:.1f};"
              f" state RMS {rms(dph) / G:.2f}; state - hydrostatic RMS {rms(dph - dph_h) / G:.2f}")
        dp_lowest = grid.p_eos(s)[0] - grid.p_eos(prior)[0]
        dp_hydro = grid.p_hydro(s)[0] - grid.p_hydro(prior)[0]
        print(f"   lowest-level p change: EOS RMS {rms(dp_lowest):.1f} Pa, hydrostatic RMS {rms(dp_hydro):.1f} Pa")


if __name__ == "__main__":
    main()
