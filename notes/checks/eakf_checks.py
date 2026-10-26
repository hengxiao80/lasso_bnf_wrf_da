"""Numerical checks for notes/dart_eakf.md.

Re-implements, line by line where possible:
  - DART  obs_increment_eakf + update_from_obs_inc + obs_updates_ens (assim_tools_mod.f90)
  - DART  obs_increment_enkf (perturbed obs, mean-adjusted, sort_obs_inc optional)
  - GSI   serial EnSRF (HRRR copy, src/enkf/enkf.f90:463-470, 533, ~640-650)
  - LETKF (Hunt et al. 2007 Eqs. 20-25; GSI letkf_core R-localization rloc*Rinv)
  - ETKF  global, symmetric square root
  - A01   Appendix A adjustment matrix
  - DART  comp_cov_factor (cov_cutoff_mod.f90) and GSI taper (covlocal.f90)

Code: DART 7bbd35a09 (../software/DART), GSI-EnKF as in the HRRR repo 40ee6058
(../software/HRRR/sorc/hrrr_gsi.fd/src/enkf). Sections 1-10 match "check n" in the note.

Run (about 2 min; arguments 4 and/or 5 skip the two slow sections):
  uv run --no-project --with numpy python -I notes/checks/eakf_checks.py [4] [5]
"""
import sys
import numpy as np
SKIP = set(sys.argv[1:])

rng = np.random.default_rng(20261025)


# ---------------------------------------------------------------- DART pieces
def dart_obs_increment_eakf(ens, obs, obs_var):
    n = ens.size
    prior_mean = ens.sum() / n
    prior_var = ((ens - prior_mean) ** 2).sum() / (n - 1)
    var_ratio = obs_var / (prior_var + obs_var)
    new_mean = var_ratio * (prior_mean + prior_var * obs / obs_var)
    a = np.sqrt(var_ratio)
    return a * (ens - prior_mean) + new_mean - ens


def dart_obs_increment_enkf(ens, obs, obs_var, rng, sort_obs_inc=False):
    n = ens.size
    prior_mean = ens.mean()
    prior_var = ((ens - prior_mean) ** 2).sum() / (n - 1)
    new_var = 1.0 / (1.0 / prior_var + 1.0 / obs_var)
    temp_obs = rng.normal(obs, np.sqrt(obs_var), n)
    temp_obs = temp_obs - temp_obs.mean() + obs
    new_mean = new_var * (ens / prior_var + temp_obs / obs_var)
    inc = new_mean - ens
    if sort_obs_inc:
        new_val = ens + inc
        i1, i2 = np.argsort(ens), np.argsort(new_val)
        inc = np.empty(n)
        inc[i1] = new_val[i2] - ens[i1]
    return inc


def dart_regress(obs_ens, obs_inc, state):
    """update_from_obs_inc without SEC: reg_coef * obs_inc."""
    n = obs_ens.size
    om = obs_ens.mean()
    ov = ((obs_ens - om) ** 2).sum() / (n - 1)
    cov = ((state - state.mean()) * (obs_ens - om)).sum() / (n - 1)
    return (cov / ov) * obs_inc


def dart_serial(X, HX, y, R, loc_xo=None, loc_oo=None, order=None):
    """DART filter_assim: sequential obs, state AND not-yet-used obs priors
    updated by regression (Anderson & Collins 2007 parallel algorithm).
    X: (nx, N) state ens; HX: (ny, N) obs priors; loc_xo (nx, ny), loc_oo (ny, ny)."""
    X = X.copy(); HX = HX.copy()
    ny = HX.shape[0]
    order = range(ny) if order is None else order
    done = np.zeros(ny, bool)
    for k in order:
        yk = HX[k].copy()
        inc = dart_obs_increment_eakf(yk, y[k], R[k])
        for j in range(X.shape[0]):
            f = 1.0 if loc_xo is None else loc_xo[j, k]
            if f > 0:
                X[j] += f * dart_regress(yk, inc, X[j])
        done[k] = True
        for m in range(ny):
            if not done[m]:
                f = 1.0 if loc_oo is None else loc_oo[m, k]
                if f > 0:
                    HX[m] += f * dart_regress(yk, inc, HX[m])
    return X


def gsi_ensrf_serial(X, HX, y, R, loc_xo=None, loc_oo=None, order=None):
    """GSI-EnKF serial EnSRF (deterministic=.true.): mean and perturbations
    updated separately; obs priors updated too (enkf.f90)."""
    N = X.shape[1]
    xm = X.mean(1); Xp = X - xm[:, None]
    ym = HX.mean(1); Yp = HX - ym[:, None]
    ny = HX.shape[0]
    order = range(ny) if order is None else order
    done = np.zeros(ny, bool)
    for k in order:
        hpfht = (Yp[k] ** 2).sum() / (N - 1)                   # :427
        obinc = y[k] - ym[k]                                     # :430
        hpfhtoberrinv = 1.0 / (hpfht + R[k])                     # :445
        obganl = -Yp[k] / (1 + np.sqrt(R[k] * hpfhtoberrinv))   # :469
        hpfhtcon = hpfhtoberrinv / (N - 1)                       # :533
        ycopy = Yp[k].copy()
        for j in range(X.shape[0]):
            f = 1.0 if loc_xo is None else loc_xo[j, k]
            kfgain = f * hpfhtcon * (Xp[j] * ycopy).sum()
            xm[j] += kfgain * obinc
            Xp[j] += kfgain * obganl
        done[k] = True
        for m in range(ny):
            if not done[m]:
                f = 1.0 if loc_oo is None else loc_oo[m, k]
                kfgain = f * hpfhtcon * (Yp[m] * ycopy).sum()
                ym[m] += kfgain * obinc
                Yp[m] += kfgain * obganl
    return xm[:, None] + Xp


def letkf(X, HX, y, R, loc_ro=None, inflate=1.0):
    """LETKF, Hunt et al. (2007) Eqs. (20)-(25); R-localization as in GSI
    letkf_core (Rinv * rloc). loc_ro (nx, ny) weights per grid point."""
    nx, N = X.shape
    xm = X.mean(1); Xp = X - xm[:, None]
    ym = HX.mean(1); Yp = HX - ym[:, None]
    d = y - ym
    Xa = np.empty_like(X)
    for j in range(nx):
        w = np.ones(len(y)) if loc_ro is None else loc_ro[j]
        use = w > 0
        Yl = Yp[use]; Rinv = w[use] / R[use]
        C = Yl.T * Rinv                                  # k x l
        Pinv = (N - 1) * np.eye(N) / inflate + C @ Yl
        evals, evecs = np.linalg.eigh(Pinv)
        Pa = evecs @ np.diag(1 / evals) @ evecs.T
        Wa = evecs @ np.diag(np.sqrt((N - 1) / evals)) @ evecs.T
        wbar = Pa @ C @ d[use]
        Xa[j] = xm[j] + Xp[j] @ (Wa + wbar[:, None])
    return Xa


def kalman(xb, B, H, y, R):
    S = H @ B @ H.T + np.diag(R)
    K = B @ H.T @ np.linalg.inv(S)
    return xb + K @ (y - H @ xb), (np.eye(len(xb)) - K @ H) @ B


def gc(z, c):
    """DART comp_cov_factor, select_localization = 1 (cov_cutoff_mod.f90)."""
    z = abs(z)
    if z >= 2 * c:
        return 0.0
    r = z / c
    if z <= c:
        return ((((-0.25 * r + 0.5) * r + 0.625) * r - 5.0 / 3.0) * r ** 2) + 1.0
    return (((((r / 12.0 - 0.5) * r + 0.625) * r + 5.0 / 3.0) * r - 5.0) * r
            + 4.0 - 2.0 / (3.0 * r))


def gsi_taper(r):
    """GSI covlocal.f90 taper: zero at r = 1."""
    if r >= 1:
        return 0.0
    if r > 0.5:
        return ((((8 / 3 * r - 8) * r + 5) * r + 20 / 3) * r - 10) * r + 4 - 1 / (3 * r)
    return ((((-8 * r + 8) * r + 5) * r - 20 / 3) * r * r) + 1


def sample_ens(mean, B, N, rng):
    ev, V = np.linalg.eigh(B)
    L = V * np.sqrt(np.clip(ev, 0, None))
    P = L @ rng.standard_normal((len(mean), N))
    P -= P.mean(1, keepdims=True)
    return mean[:, None] + P


def ens_cov(X):
    Xp = X - X.mean(1, keepdims=True)
    return Xp @ Xp.T / (X.shape[1] - 1)


def hdr(s):
    print("\n" + "=" * 72 + "\n" + s + "\n" + "=" * 72)


# --------------------------------------------------------------- 1. one ob
hdr("1. One observation, no localization: DART EAKF, GSI EnSRF, ETKF, A01")
N = 5
nx = 6
B = np.fromfunction(lambda i, j: np.exp(-0.5 * ((i - j) / 2.0) ** 2), (nx, nx))
X = sample_ens(np.zeros(nx), B, N, rng)
H = np.zeros((1, nx)); H[0, 2] = 0.6; H[0, 3] = 0.4   # interpolation-like
HX = H @ X
y = np.array([0.8]); R = np.array([0.5])
Xd = dart_serial(X, HX, y, R)
Xg = gsi_ensrf_serial(X, HX, y, R)
Xl = letkf(X, HX, y, R)
# A01 Appendix A on the joint state z = [x, y]
Z = np.vstack([X, HX]); zm = Z.mean(1); Zp = Z - zm[:, None]
S = Zp @ Zp.T / (N - 1)
Hj = np.zeros((1, nx + 1)); Hj[0, -1] = 1
evals, F = np.linalg.eigh(S); keep = evals > 1e-10 * evals.max()
F = F[:, keep]; G = np.diag(np.sqrt(evals[keep]))
M = G @ F.T @ Hj.T @ Hj @ F @ G / R[0]
mu, U = np.linalg.eigh(M)
Bm = np.diag(1 / np.sqrt(1 + mu))
A = F @ G @ U @ Bm @ np.linalg.inv(G) @ F.T          # A01 App. A (p. 2901)
Asym = F @ G @ U @ Bm @ U.T @ np.linalg.inv(G) @ F.T   # with the trailing U^T
Sp_inv_pinv = F @ np.diag(1 / evals[keep]) @ F.T
Su = A @ S @ A.T
zu = Su @ (Sp_inv_pinv @ zm + Hj.T[:, 0] * y[0] / R[0])
Za = zu[:, None] + A @ Zp
Zs = zu[:, None] + Asym @ Zp
print(f"max|DART - GSI EnSRF| = {abs(Xd - Xg).max():.2e}")
print(f"max|DART - ETKF(sym)| = {abs(Xd - Xl).max():.2e}")
print(f"A01, A applied : max|mean diff| = {abs(Xd.mean(1) - Za[:nx].mean(1)).max():.2e}"
      f"  max|cov diff| = {abs(ens_cov(Xd) - ens_cov(Za[:nx])).max():.2e}"
      f"  max|member diff| = {abs(Xd - Za[:nx]).max():.2e}")
print(f"A01 with U^T   : max|member diff| = {abs(Xd - Zs[:nx]).max():.2e}")
# A01 (16) and App. A apply A^T to the deviations, while Sigma_u = A Sigma A^T
Zt = zu[:, None] + A.T @ Zp
print(f"A01 A^T applied (as printed in (16)): max|cov - Sigma_u| = {abs(ens_cov(Zt) - Su).max():.2e}"
      f"  (A applied: {abs(ens_cov(Za) - Su).max():.2e})")
print(f"(increment size max  = {abs(Xd - X).max():.2e})")

# --------------------------------------------------------- 2. many obs, no loc
hdr("2. 20 obs, no localization: serial vs batch Kalman, order, ETKF")
nx, N, ny = 30, 10, 20
B = np.fromfunction(lambda i, j: np.exp(-0.5 * ((i - j) / 4.0) ** 2), (nx, nx))
X = sample_ens(np.zeros(nx), B, N, rng)
H = np.zeros((ny, nx))
for k in range(ny):
    p = rng.uniform(0, nx - 1); i0 = int(p); w = p - i0
    H[k, i0] = 1 - w; H[k, min(i0 + 1, nx - 1)] += w
HX = H @ X
R = rng.uniform(0.2, 1.0, ny)
y = H @ rng.multivariate_normal(np.zeros(nx), B) + rng.normal(0, np.sqrt(R))
Pe = ens_cov(X)
xa_k, Pa_k = kalman(X.mean(1), Pe, H, y, R)
Xd1 = dart_serial(X, HX, y, R)
Xd2 = dart_serial(X, HX, y, R, order=rng.permutation(ny))
Xg1 = gsi_ensrf_serial(X, HX, y, R)
Xe = letkf(X, HX, y, R)
print(f"mean : max|serial EAKF - KF(ens P)| = {abs(Xd1.mean(1) - xa_k).max():.2e}")
print(f"cov  : max|serial EAKF - KF(ens P)| = {abs(ens_cov(Xd1) - Pa_k).max():.2e}")
print(f"mean : max|order A - order B|       = {abs(Xd1.mean(1) - Xd2.mean(1)).max():.2e}")
print(f"cov  : max|order A - order B|       = {abs(ens_cov(Xd1) - ens_cov(Xd2)).max():.2e}")
print(f"memb : max|order A - order B|       = {abs(Xd1 - Xd2).max():.2e}")
print(f"memb : max|DART - GSI EnSRF|        = {abs(Xd1 - Xg1).max():.2e}")
print(f"mean : max|DART - ETKF|             = {abs(Xd1.mean(1) - Xe.mean(1)).max():.2e}")
print(f"cov  : max|DART - ETKF|             = {abs(ens_cov(Xd1) - ens_cov(Xe)).max():.2e}")
print(f"memb : max|DART - ETKF|             = {abs(Xd1 - Xe).max():.2e}")
print(f"(analysis perturbation size, max    = {abs(Xd1 - Xd1.mean(1, keepdims=True)).max():.2e})")

# ------------------------------------------- 3. localization: B vs R, one ob
hdr("3. One ob, localization weight rho: gain relative to unlocalized")
print(" rho   s2/R   B-loc(EAKF/EnSRF)  R-loc(LETKF)")
for rho in (0.75, 0.5, 0.25):
    for r in (0.25, 1.0, 4.0, 16.0):
        print(f"{rho:5.2f} {r:6.2f} {rho:12.3f} {(r + 1) / (r + 1 / rho):14.3f}")

# --------------------------------------------- 4. localized, single analysis
hdr("4. 1-D periodic, 40 points, all observed, GC localization, one analysis")


def periodic_dist(i, j, n):
    d = abs(i - j)
    return min(d, n - d)


def run_trials(N, sig_o, half_width, ntrial, rng):
    nx = 40
    Lc = 3.0
    Bt = np.fromfunction(
        lambda i, j: np.exp(-0.5 * (np.minimum(abs(i - j), nx - abs(i - j)) / Lc) ** 2),
        (nx, nx))
    H = np.eye(nx)
    R = np.full(nx, sig_o ** 2)
    loc = np.array([[gc(periodic_dist(i, j, nx), half_width) for j in range(nx)]
                    for i in range(nx)])
    err = {k: [] for k in ("prior", "KF(true B)", "DART serial", "DART reversed",
                           "GSI EnSRF", "LETKF", "batch B-loc")}
    dord = []
    for _ in range(ntrial):
        xt = rng.multivariate_normal(np.zeros(nx), Bt)
        xb = np.zeros(nx)
        X = sample_ens(xb, Bt, N, rng)
        y = xt + rng.normal(0, sig_o, nx)
        HX = X.copy()
        err["prior"].append(np.sqrt(((X.mean(1) - xt) ** 2).mean()))
        xa, _ = kalman(xb, Bt, H, y, R)
        err["KF(true B)"].append(np.sqrt(((xa - xt) ** 2).mean()))
        Xd = dart_serial(X, HX, y, R, loc, loc)
        Xr = dart_serial(X, HX, y, R, loc, loc, order=range(nx - 1, -1, -1))
        Xg = gsi_ensrf_serial(X, HX, y, R, loc, loc)
        Xl = letkf(X, HX, y, R, loc)
        Pl = loc * ens_cov(X)
        K = Pl @ np.linalg.inv(Pl + np.diag(R))
        xb_loc = X.mean(1) + K @ (y - X.mean(1))
        for k, Xa in (("DART serial", Xd), ("DART reversed", Xr), ("GSI EnSRF", Xg),
                      ("LETKF", Xl)):
            err[k].append(np.sqrt(((Xa.mean(1) - xt) ** 2).mean()))
        err["batch B-loc"].append(np.sqrt(((xb_loc - xt) ** 2).mean()))
        dord.append(np.sqrt(((Xd.mean(1) - Xr.mean(1)) ** 2).mean()))
        assert abs(Xd - Xg).max() < 1e-8
    se = {k: np.std(np.array(v) - np.array(err["DART serial"]), ddof=1) / np.sqrt(len(v))
          for k, v in err.items()}
    print("   s.e. of (method - DART serial): " +
          "  ".join(f"{k}={v:.4f}" for k, v in se.items() if k != "DART serial"))
    return {k: np.mean(v) for k, v in err.items()}, np.mean(dord)


for N in (() if '4' in SKIP else (5, 20)):
    for sig_o in (1.0, 0.3, 0.1):
        res, dord = run_trials(N, sig_o, half_width=5.0, ntrial=300, rng=rng)
        print(f"N={N:2d} sig_o={sig_o:4.2f}  " +
              "  ".join(f"{k}={v:.3f}" for k, v in res.items()) +
              f"  |serial order diff|={dord:.3f}")

# ---------------------------------------------- 5. EnKF vs EAKF, scalar Pa
hdr("5. Scalar Pb=1, R=1: sampling error of the posterior variance (WH02 Fig. 1)")
for N in (() if '5' in SKIP else (5, 13, 50)):
    pa_srf, pa_enkf, pa_enkf_unit = [], [], []
    for _ in range(200000 // N):
        x = rng.standard_normal(N)
        x = x  # prior ensemble, truth Pb = 1
        pb = x.var(ddof=1)
        xa = x + dart_obs_increment_eakf(x, 0.0, 1.0)
        pa_srf.append(xa.var(ddof=1))
        xe = x + dart_obs_increment_enkf(x, 0.0, 1.0, rng)
        pa_enkf.append(xe.var(ddof=1))
        # WH02 perturbations: zero mean AND unit variance
        e = rng.standard_normal(N); e = (e - e.mean()) / e.std(ddof=1)
        k = pb / (pb + 1.0)
        xw = x + k * (e - x)
        pa_enkf_unit.append(xw.var(ddof=1))
    for name, v in (("EAKF", pa_srf), ("EnKF DART pert", pa_enkf),
                    ("EnKF WH02 pert", pa_enkf_unit)):
        v = np.array(v)
        print(f"N={N:2d} {name:15s} mean Pa={v.mean():.3f}  MAE vs 0.5={abs(v - 0.5).mean():.3f}"
              f"  P(Pa<0.5)={np.mean(v < 0.5):.2f}")

# -------------------------------------------- 6. worked numbers, our obs
hdr("6. One observation: fraction of innovation taken, spread factor a")
cases = [("METAR T2, sd_o 1.26 K", 1.26, (0.5, 1.0, 2.0)),
         ("mesonet T, sd_o 3.0 K", 3.0, (0.5, 1.0, 2.0)),
         ("METAR wind, sd_o 1.59 m/s", 1.59, (0.5, 1.0, 2.0)),
         ("altimeter (meso), 1 hPa", 1.0, (0.3, 1.0, 2.0)),
         ("MRMS, sd_o 5 dBZ", 5.0, (2.0, 5.0, 10.0, 15.0))]
for name, so, sps in cases:
    for sp in sps:
        vr = so ** 2 / (sp ** 2 + so ** 2)
        print(f"{name:28s} sd_y={sp:5.2f}: gain 1-vr={1 - vr:.3f}  a={np.sqrt(vr):.3f}")

# ------------------------------------------------ 7. float32 round-off
hdr("7. float32 round-off of the EAKF mean increment (5 members)")
print("units of the variable; ulp = float32 spacing at the value")
for name, mean, sp, so, inn in (("altimeter hPa", 1013.25, 0.8, 1.0, 0.7),
                                ("T2 K", 300.15, 1.0, 1.26, 1.0),
                                ("PSFC-like Pa", 95000.0, 80.0, 100.0, 70.0),
                                ("dBZ", 35.0, 8.0, 5.0, 6.0)):
    e_dart, e_alt, incs = [], [], []
    for _ in range(4000):
        ens32 = (mean + sp * rng.standard_normal(5)).astype(np.float32)
        obs32 = np.float32(ens32.mean() + inn)
        ov32 = np.float32(so ** 2)
        pm = ens32.sum(dtype=np.float32) / np.float32(5)
        pv = ((ens32 - pm) ** 2).sum(dtype=np.float32) / np.float32(4)
        vr = ov32 / (pv + ov32)
        nm_dart = vr * (pm + pv * obs32 / ov32)                  # DART :1127
        nm_alt = pm + (pv / (pv + ov32)) * (obs32 - pm)          # innovation form
        e = ens32.astype(np.float64); o = float(obs32)
        pm64 = e.mean(); pv64 = e.var(ddof=1)
        nm64 = pm64 + pv64 / (pv64 + so ** 2) * (o - pm64)
        e_dart.append(abs(float(nm_dart) - nm64)); e_alt.append(abs(float(nm_alt) - nm64))
        incs.append(abs(nm64 - pm64))
    ulp = float(np.spacing(np.float32(mean)))
    print(f"{name:14s} ulp={ulp:.1e}  median|inc|={np.median(incs):.2e}  "
          f"DART formula err: median={np.median(e_dart):.1e} max={max(e_dart):.1e}   "
          f"innovation form err: median={np.median(e_alt):.1e} max={max(e_alt):.1e}")

# --------------------------------------------- 8. localization shapes
hdr("8. DART GC(c) vs GSI taper; non-separable vs separable 3-D weights")
c = 0.0235 * 6371.0  # km, DART half-width
print("max |DART gc(2c r, c) - GSI taper(r)| =",
      f"{max(abs(gc(2 * c * r, c) - gsi_taper(r)) for r in np.linspace(0, 1.2, 1201)):.1e}")
print(f"(DART zero at 2c = {2 * c:.1f} km; vertical zero at 2c*10.6/6371 = "
      f"{2 * 0.0235 * 10.6:.3f} scale heights)")
print("   dh(km)  dv(sh)   DART GC(sqrt(dh^2+dv^2))   GSI GC(dh)*GC(dv)")
for dh in (0, 75, 150, 225):
    for dv in (0.0, 0.125, 0.25, 0.375):
        zh = dh / 6371.0                     # radians
        zv = dv / 10.6                       # radians (vert_normalization_scale_height)
        dart = gc(np.hypot(zh, zv), 0.0235)
        gsi = gsi_taper(dh / 300.0) * gsi_taper(dv / 0.5)
        print(f"{dh:8.0f} {dv:7.3f} {dart:22.3f} {gsi:20.3f}")

# --------------------------------------- 9. nonlinear H: parallel vs sequential
hdr("9. Nonlinear H (y = x^2): A&C parallel (DART) vs sequential re-evaluation")
nx, N = 6, 20
B = np.fromfunction(lambda i, j: 0.5 * np.exp(-0.5 * ((i - j) / 2.0) ** 2), (nx, nx))
for trial in range(3):
    X = sample_ens(np.full(nx, 3.0), B, N, rng)
    obs_idx = [1, 2, 3, 4]
    xt = X.mean(1) + rng.multivariate_normal(np.zeros(nx), B)
    y = xt[obs_idx] ** 2 + rng.normal(0, 1.0, len(obs_idx))
    R = np.full(len(obs_idx), 1.0)
    HX = X[obs_idx] ** 2
    Xp = dart_serial(X, HX, y, R)                       # obs priors regressed
    Xs = X.copy()                                      # sequential, H recomputed
    for k, i in enumerate(obs_idx):
        yk = Xs[i] ** 2
        inc = dart_obs_increment_eakf(yk, y[k], R[k])
        for j in range(nx):
            Xs[j] += dart_regress(yk, inc, Xs[j])
    print(f"trial {trial}: max|mean(parallel)-mean(sequential)| = "
          f"{abs(Xp.mean(1) - Xs.mean(1)).max():.3f}   "
          f"max|mean increment| = {abs(Xs.mean(1) - X.mean(1)).max():.3f}")

# ------------------------------------------- 10. worked examples (note Sec. 3.3)
hdr("10. Worked examples: METAR T2 and MRMS reflectivity, 5 members")
for name, ens, obs, so in (("T2 (K)", np.array([296.0, 297.1, 297.6, 298.3, 299.0]), 298.9, 1.26),
                           ("REFL (dBZ)", np.array([12.0, 25.0, 33.0, 38.0, 45.0]), 41.0, 5.0)):
    inc = dart_obs_increment_eakf(ens, obs, so ** 2)
    pv = ens.var(ddof=1)
    k = pv / (pv + so ** 2)
    print(f"{name}: mean={ens.mean():.3f} sd={np.sqrt(pv):.3f} d={obs - ens.mean():.3f} "
          f"k={k:.3f} a={np.sqrt(1 - k):.3f}")
    print(f"   increments {np.round(inc, 3)}  posterior mean {(ens + inc).mean():.3f}"
          f"  sd {(ens + inc).std(ddof=1):.3f}")
