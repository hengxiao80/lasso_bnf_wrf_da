"""Numerical checks for notes/eakf_vs_letkf.md (EAKF against LETKF).

Sections 1-n match "check n" in the note (Sec. 8). The filter translations are copies of
the ones in eakf_checks.py (checks for notes/dart_eakf.md):
  - DART  obs_increment_eakf + update_from_obs_inc (no SEC) + obs_updates_ens, i.e. the
          serial EAKF with the Anderson-Collins update of later H(x)
  - LETKF Hunt et al. (2007) Eqs. (20)-(25), R-localization as rloc * Rinv (GSI letkf.f90)
New here:
  - the serial EAKF written as an ensemble transform per state element (note Sec. 2.1)
  - the gain form of the ETKF, Bishop et al. (2017) Eqs. (24)-(29), with a raw and with a
    modulated ensemble (note Sec. 2.5)

Run (a few seconds):
  uv run --no-project --with numpy python -I notes/checks/eakf_letkf_checks.py
"""
import numpy as np

rng = np.random.default_rng(20261105)


# ------------------------------------------------- copies from eakf_checks.py
def dart_obs_increment_eakf(ens, obs, obs_var):
    n = ens.size
    prior_mean = ens.sum() / n
    prior_var = ((ens - prior_mean) ** 2).sum() / (n - 1)
    var_ratio = obs_var / (prior_var + obs_var)
    new_mean = var_ratio * (prior_mean + prior_var * obs / obs_var)
    a = np.sqrt(var_ratio)
    return a * (ens - prior_mean) + new_mean - ens


def dart_regress(obs_ens, obs_inc, state):
    n = obs_ens.size
    om = obs_ens.mean()
    ov = ((obs_ens - om) ** 2).sum() / (n - 1)
    cov = ((state - state.mean()) * (obs_ens - om)).sum() / (n - 1)
    return (cov / ov) * obs_inc


def dart_serial(X, HX, y, R, loc_xo=None, loc_oo=None, order=None, trace=None):
    """As in eakf_checks.py; if trace is a list, the H(x) ensemble each observation
    is assimilated with (as updated by the earlier ones) is appended to it."""
    X = X.copy(); HX = HX.copy()
    ny = HX.shape[0]
    order = range(ny) if order is None else order
    done = np.zeros(ny, bool)
    for k in order:
        yk = HX[k].copy()
        if trace is not None:
            trace.append((k, yk.copy()))
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


def letkf(X, HX, y, R, loc_ro=None, inflate=1.0, return_w=False):
    nx, N = X.shape
    xm = X.mean(1); Xp = X - xm[:, None]
    ym = HX.mean(1); Yp = HX - ym[:, None]
    d = y - ym
    Xa = np.empty_like(X)
    Ws, wbars = [], []
    for j in range(nx):
        w = np.ones(len(y)) if loc_ro is None else loc_ro[j]
        use = w > 0
        Yl = Yp[use]; Rinv = w[use] / R[use]
        C = Yl.T * Rinv
        Pinv = (N - 1) * np.eye(N) / inflate + C @ Yl
        evals, evecs = np.linalg.eigh(Pinv)
        Pa = evecs @ np.diag(1 / evals) @ evecs.T
        Wa = evecs @ np.diag(np.sqrt((N - 1) / evals)) @ evecs.T
        wbar = Pa @ C @ d[use]
        Xa[j] = xm[j] + Xp[j] @ (Wa + wbar[:, None])
        Ws.append(Wa); wbars.append(wbar)
    return (Xa, Ws, wbars) if return_w else Xa


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


# ------------------------------------------------------------- new pieces
def eakf_transform(trace, y, R, kappa_j, N):
    """Serial EAKF for one state element as an ensemble transform (note Eq. (21)):
    returns (wbar, T) with  x_j^a = xbar_j + x'_j (wbar 1^T + T)."""
    T = np.eye(N)
    wbar = np.zeros(N)
    for k, yk in trace:
        yp = yk - yk.mean()
        s2 = yp @ yp / (N - 1)
        kk = s2 / (s2 + R[k])
        a = np.sqrt(1 - kk)
        d = y[k] - yk.mean()
        kap = kappa_j[k]
        g = kap * kk * d * yp / (yp @ yp)                    # mean step, weight space
        wbar = wbar + T @ g
        T = T @ (np.eye(N) + kap * (a - 1) * np.outer(yp, yp) / (yp @ yp))
    return wbar, T


def symroot(S):
    ev, V = np.linalg.eigh(S)
    return V @ np.diag(np.sqrt(ev)) @ V.T


# ============================================================================
hdr("1. Serial EAKF with localization = one ensemble transform per state element")
nx, N, ny = 30, 10, 20
B = np.fromfunction(lambda i, j: np.exp(-0.5 * ((i - j) / 4.0) ** 2), (nx, nx))
X = sample_ens(np.zeros(nx), B, N, rng)
pos = np.sort(rng.uniform(0, nx - 1, ny))
H = np.zeros((ny, nx))
for k, p in enumerate(pos):
    i0 = int(p); w = p - i0
    H[k, i0] = 1 - w; H[k, min(i0 + 1, nx - 1)] += w
HX = H @ X
R = rng.uniform(0.2, 1.0, ny)
y = H @ rng.multivariate_normal(np.zeros(nx), B) + rng.normal(0, np.sqrt(R))
c = 3.0
loc_xo = np.array([[gc(j - pos[k], c) for k in range(ny)] for j in range(nx)])
loc_oo = np.array([[gc(pos[m] - pos[k], c) for k in range(ny)] for m in range(ny)])
order = rng.permutation(ny)
trace = []
Xd = dart_serial(X, HX, y, R, loc_xo, loc_oo, order=order, trace=trace)
xm = X.mean(1); Xp = X - xm[:, None]
err = 0.0
for j in range(nx):
    wbar, T = eakf_transform(trace, y, R, loc_xo[j], N)
    err = max(err, abs(xm[j] + Xp[j] @ (T + wbar[:, None]) - Xd[j]).max())
print(f"max|DART serial - xbar + x' (wbar 1^T + T_j)| = {err:.1e}  "
      f"(analysis deviations up to {abs(Xd - Xd.mean(1, keepdims=True)).max():.2f})")
# how much T_j varies between elements
Ts = [eakf_transform(trace, y, R, loc_xo[j], N)[1] for j in range(nx)]
print(f"T_j at neighbouring elements differ by at most "
      f"{max(abs(Ts[j + 1] - Ts[j]).max() for j in range(nx - 1)):.3f}; "
      f"T_0 vs T_15: {abs(Ts[0] - Ts[15]).max():.3f}")

# ============================================================================
hdr("2. One observation at weight kappa: both filters as weight-space updates")
N = 8
for kap in (1.0, 0.5, 0.2):
    for s2_over_o2 in (0.25, 1.0, 4.0):
        Xs = sample_ens(np.zeros(3), np.eye(3) + 0.6, N, rng)
        HX1 = Xs[1:2].copy()
        HX1 = HX1 / HX1.std(ddof=1) * np.sqrt(s2_over_o2)          # sigma_y^2 = s2/o2
        Xs[1] = HX1[0]
        y1 = np.array([HX1.mean() + 0.7]); R1 = np.array([1.0])
        Xe = dart_serial(Xs, HX1, y1, R1, loc_xo=np.full((3, 1), kap))
        Xl, Ws, wbars = letkf(Xs, HX1, y1, R1, loc_ro=np.full((3, 1), kap), return_w=True)
        yp = HX1[0] - HX1.mean(); s2 = yp @ yp / (N - 1); d = y1[0] - HX1.mean()
        a = np.sqrt(1 / (s2 + 1)); aR = np.sqrt(1 / (1 + kap * s2))
        # note Eqs. (22)-(23)
        w_e = kap * d * yp / ((N - 1) * (s2 + 1))
        T_e = np.eye(N) + kap * (a - 1) * np.outer(yp, yp) / (yp @ yp)
        w_l = d * yp / ((N - 1) * (s2 + 1 / kap))
        T_l = np.eye(N) + (aR - 1) * np.outer(yp, yp) / (yp @ yp)
        xm = Xs.mean(1); Xp = Xs - xm[:, None]
        e1 = abs(xm[:, None] + Xp @ (T_e + w_e[:, None]) - Xe).max()
        e2 = abs(wbars[0] - w_l).max() + abs(Ws[0] - T_l).max()
        kreg = kap / (1 + s2 * (1 - kap))        # regulated R-weight, N15 (21)
        areg = np.sqrt(1 / (1 + kreg * s2))
        print(f"kappa={kap:3.1f} sy2/so2={s2_over_o2:4.2f}: EAKF formula {e1:.0e}, "
              f"LETKF formula {e2:.0e};  mean factor EAKF {kap / (s2 + 1):.3f} "
              f"LETKF {1 / (s2 + 1 / kap):.3f};  contraction EAKF {1 + kap * (a - 1):.3f} "
              f"LETKF {aR:.3f} LETKF(regulated) {areg:.3f}")

print("\nvariance factor in the direction y^ (posterior / prior variance of that component):")
print("  kappa  sy2/so2  Joseph(raw P)  EAKF   Kalman(same mean)  LETKF(same kappa)")
for kap in (0.5, 0.2):
    for r in (0.25, 1.0, 4.0):
        k = r / (1 + r); a = np.sqrt(1 - k)
        joseph = 1 - kap * k * (2 - kap)          # N15 (22), raw covariance, gain kappa*k
        eakf = (1 - kap * (1 - a)) ** 2
        bayes = 1 - kap * k                       # Kalman update with mean step kappa*k
        letkf_v = 1 / (1 + kap * r)
        print(f"  {kap:5.2f} {r:7.2f} {joseph:12.3f} {eakf:7.3f} {bayes:12.3f} {letkf_v:16.3f}")

# ============================================================================
hdr("3. No localization: serial product T vs symmetric root W")
nx, N, ny = 30, 10, 20
X = sample_ens(np.zeros(nx), B, N, rng)
HX = H @ X
trace = []
Xd = dart_serial(X, HX, y, R, order=rng.permutation(ny), trace=trace)
wbar_s, T = eakf_transform(trace, y, R, np.ones(ny), N)
Xl, Ws, wbars = letkf(X, HX, y, R, return_w=True)
W = Ws[0]; wbar_l = wbars[0]
Yp = HX - HX.mean(1, keepdims=True)
Pt = np.linalg.inv((N - 1) * np.eye(N) + Yp.T @ np.diag(1 / R) @ Yp)
U = np.linalg.solve(W, T)
one = np.ones(N)
print(f"max|T T^T - (N-1) Pa~|   = {abs(T @ T.T - (N - 1) * Pt).max():.1e}")
print(f"max|U U^T - I|           = {abs(U @ U.T - np.eye(N)).max():.1e}   (U = W^-1 T)")
print(f"max|U 1 - 1|             = {abs(U @ one - one).max():.1e}")
print(f"max|wbar serial - wbar ETKF| = {abs(wbar_s - wbar_l).max():.1e}")
print(f"max|T - W| = {abs(T - W).max():.3f};  max|U - I| = {abs(U - np.eye(N)).max():.3f};"
      f"  members: max|serial - ETKF| = {abs(Xd - Xl).max():.3f}")
print(f"T symmetric? max|T - T^T| = {abs(T - T.T).max():.3f};  "
      f"||T - I||_F = {np.linalg.norm(T - np.eye(N)):.3f}, ||W - I||_F = {np.linalg.norm(W - np.eye(N)):.3f}")

# ============================================================================
hdr("4. R-localization with a GC weight as an effective B-localization weight")
# One observation, prior variance ratio r = sigma_y^2/sigma_o^2.  The LETKF gain at
# R-weight kR equals the EAKF gain at B-weight  k_eff = kR (1+r) / (1 + kR r)
# (HW13 Eq. (10); N15 Eq. (21) is the inverse).
zs = np.linspace(0, 2, 20001)              # distance in units of the GC half-width c
g = np.array([gc(z, 1.0) for z in zs])


def first_below(v, level):
    i = np.argmax(v < level)
    return zs[i]


print("distance (units of c) where the gain falls to 50 %, 21 %, 5 % of the unlocalized gain")
print(f"{'':22s} {'50%':>6s} {'21%':>6s} {'5%':>6s}   c_R/c to match B at 50 %")
print(f"{'B (EAKF), GC':22s} {first_below(g, 0.5):6.3f} {first_below(g, 0.208):6.3f}"
      f" {first_below(g, 0.05):6.3f}")
for name, r in (("R, sy/so = 0.5", 0.25), ("R, sy/so = 1", 1.0), ("R, sy/so = 2", 4.0),
                ("R, sy/so = 2.5 (MRMS)", 6.25), ("R, sy/so = 4", 16.0)):
    ke = g * (1 + r) / (1 + g * r)
    z50 = first_below(ke, 0.5)
    print(f"{name:22s} {z50:6.3f} {first_below(ke, 0.208):6.3f} {first_below(ke, 0.05):6.3f}"
          f"   {first_below(g, 0.5) / z50:6.3f}")

# ============================================================================
hdr("5. Gain form (B17): raw ensemble = symmetric LETKF; modulated, one ob = EnSRF")


def getkf_raw_update(Xb, Hlin, y, R, Z):
    """B17 Eqs. (22)-(29) with a = 1: gain from the (possibly modulated) ensemble Z
    (n x M, Z Z^T = covariance), applied to the K raw members Xb (n x K).
    Linear H; mean from B17 (12)."""
    K = Xb.shape[1]
    xm = Xb.mean(1); Xp = Xb - xm[:, None]
    Rmh = np.diag(1 / np.sqrt(R))
    HZ = Rmh @ Hlin @ Z                                           # H~Z, p x M
    E, sv, Ct = np.linalg.svd(HZ, full_matrices=False)
    keep = sv > 1e-12 * sv.max()
    E, sv, C = E[:, keep], sv[keep], Ct[keep].T
    Gam = sv ** 2
    Ktil = Z @ C @ np.diag((1 - (Gam + 1) ** -0.5) / Gam) @ C.T @ HZ.T   # B17 (25)
    Xap = Xp - Ktil @ (Rmh @ Hlin @ Xp)                                # B17 (29)
    Za = Z - Z @ C @ np.diag(1 - (Gam + 1) ** -0.5) @ C.T                # B17 (24)
    xa = xm + Za @ (Rmh @ Hlin @ Za).T @ (Rmh @ y - Rmh @ Hlin @ xm)    # B17 (12)
    return xa[:, None] + Xap


nx, N = 30, 10
X = sample_ens(np.zeros(nx), B, N, rng)
Xp = X - X.mean(1, keepdims=True)
Xg = getkf_raw_update(X, H, y, R, Xp / np.sqrt(N - 1))
Xl = letkf(X, H @ X, y, R)
print(f"raw ensemble, 20 obs, no localization: max|GETKF - LETKF(sym)| = {abs(Xg - Xl).max():.1e}")

# modulated ensemble: F = full-rank localization matrix, Z = all products u_j o w_i
nx, N = 12, 5
Bs = np.fromfunction(lambda i, j: np.exp(-0.5 * ((i - j) / 3.0) ** 2), (nx, nx))
Xs = sample_ens(np.zeros(nx), Bs, N, rng)
Xsp = Xs - Xs.mean(1, keepdims=True)
F = np.array([[gc(i - j, 2.5) for j in range(nx)] for i in range(nx)])
ev, V = np.linalg.eigh(F)
Wf = V * np.sqrt(np.clip(ev, 0, None))                          # F = Wf Wf^T
Zm = np.hstack([(Xsp / np.sqrt(N - 1)) * Wf[:, [i]] for i in range(nx)])
print(f"modulated: M = {Zm.shape[1]} members, max|Z Z^T - F o P| = "
      f"{abs(Zm @ Zm.T - F * ens_cov(Xs)).max():.1e}")
io = 5
H1 = np.zeros((1, nx)); H1[0, io] = 1.0
y1 = np.array([0.9]); R1 = np.array([0.3])
Xg1 = getkf_raw_update(Xs, H1, y1, R1, Zm)
Xd1 = dart_serial(Xs, H1 @ Xs, y1, R1, loc_xo=F[:, [io]])
print(f"one ob at a grid point: max|GETKF(modulated) - DART EAKF with B-loc| = "
      f"{abs(Xg1 - Xd1).max():.1e}  (increments up to {abs(Xd1 - Xs).max():.2f})")

# ============================================================================
hdr("6. Example A of the note: 3 members, y observed, x another variable")
Xa_ = np.array([[9.0, 10.0, 11.0],        # y, the observed quantity (row 0)
                [18.0, 21.0, 21.0]])      # x, another state variable (row 1)
yA = np.array([11.0]); RA = np.array([1.0])
HA = Xa_[0:1].copy()
yp = Xa_[0] - Xa_[0].mean(); xp = Xa_[1] - Xa_[1].mean()
print(f"y' = {yp}, x' = {xp}, var y = {yp @ yp / 2:.3f}, var x = {xp @ xp / 2:.3f}, "
      f"cov = {xp @ yp / 2:.3f}, corr = {(xp @ yp) / np.sqrt((xp @ xp) * (yp @ yp)):.3f}")
proj = (xp @ yp) / (yp @ yp) * yp
print(f"x' along y': {proj}, rest: {xp - proj} (rest . y' = {(xp - proj) @ yp:.1e})")
for kap in (1.0, 0.5):
    Xe = dart_serial(Xa_, HA, yA, RA, loc_xo=np.array([[1.0], [kap]]))
    Xl, Ws, wbars = letkf(Xa_, HA, yA, RA, loc_ro=np.array([[1.0], [kap]]), return_w=True)
    trace = []
    dart_serial(Xa_, HA, yA, RA, loc_xo=np.array([[1.0], [kap]]), trace=trace)
    wbar, T = eakf_transform(trace, yA, RA, np.array([kap]), 3)
    print(f"kappa = {kap}: EAKF x members {np.round(Xe[1], 3)} (mean {Xe[1].mean():.3f}), "
          f"y members {np.round(Xe[0], 3)}")
    print(f"   EAKF weights wbar = {np.round(wbar, 3)}, T =\n{np.round(T, 3)}")
    print(f"   LETKF x members {np.round(Xl[1], 3)} (mean {Xl[1].mean():.3f}); "
          f"shrink factor along y' {np.sqrt(1 / (1 + kap)):.3f} vs EAKF {1 + kap * (np.sqrt(0.5) - 1):.3f}")
# swapping two members: same mean and covariance, different members
Pm = np.eye(3)[:, [2, 1, 0]]
print(f"permutation U: U U^T = I {np.allclose(Pm @ Pm.T, np.eye(3))}, U 1 = 1 "
      f"{np.allclose(Pm @ np.ones(3), np.ones(3))}")
# accurate observation: sigma_o = sigma_y / 4, weight 0.5
r = 16.0
print(f"sigma_y/sigma_o = 4, kappa = 0.5: gain relative to unlocalized: EAKF 0.500, "
      f"LETKF {(r + 1) / (r + 2):.3f}")
