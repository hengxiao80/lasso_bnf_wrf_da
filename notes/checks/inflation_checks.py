"""Numerical checks for notes/dart_adaptive_inflation.md.

A line-by-line Python translation of DART's adaptive inflation update (adaptive_inflate_mod.f90,
DART 7bbd35a09: update_varying_state_space_inflation, update_inflation, bayes_cov_inflate,
linear_bayes, enh_linear_bayes, change_GA_IG, the two density functions, solve_quadratic), in
double precision. DART's own routines, compiled stand-alone in float32 and float64, are run by
inflation_fortran_check.sh; the two agree on every case run in both.

Sections (note section in brackets):
   1  IG parameters from (mode, sd); curvature variance tau^2            [5.2]
   2  E|r| of the sample correlation of unrelated variables             [3.2]
   3  flavor 2: linearized mode against the exact posterior mode         [7.1]
   4  one observation: both flavors, step sizes, gamma, deflation        [7.2]
   5  a run of identical observations at one element                     [7.3]
   6  random innovations at one element (toy)                            [7.3]
   7  constant gain: memory and noise of lambda with a fixed sd (toy)    [7.4]
   8  flavor 5's wrong root; when it is taken                            [5.3]
   9  float32 overflow of beta**alpha: where the flavor-5 sd freezes     [5.4]
  10  damping on lambda (code) against sqrt(lambda) (G18, guide)         [8]

Run (a few seconds; give section numbers to run only those):
  uv run --no-project --with numpy python -I notes/checks/inflation_checks.py [n ...]
"""
import math
import sys
import numpy as np

ONLY = {int(a) for a in sys.argv[1:]}
TINY = np.finfo(np.float64).tiny
SMALL = np.finfo(np.float64).eps


def run(n):
    return not ONLY or n in ONLY


def hdr(s):
    print(f"\n=== {s}")


# ------------------------------------------------------------- DART translation
def solve_quadratic(a, b, c):
    s = max(abs(a), abs(b), abs(c))
    a, b, c = a / s, b / s, c / s
    disc = math.sqrt(b * b - 4 * a * c)
    r1 = (-b - disc) / (2 * a) if b > 0 else (-b + disc) / (2 * a)
    return r1, (c / a) / r1


def theta2(lam, gam, sp2, so2, N=None):
    """theta^2 of flavor 2 (N None) or flavor 5 (with the -1/N term, dropped if s^2 < 1/N)."""
    f1 = (1 + gam * (math.sqrt(lam) - 1)) ** 2
    f2 = 0.0
    if N is not None:
        f2 = -1.0 / N
        if f1 < abs(f2):
            f2 = 0.0
    return (f1 + f2) * sp2 + so2


def lik_and_deriv(dist2, sp2, so2, lam, gam, N=None):
    th2 = theta2(lam, gam, sp2, so2, N)
    th = math.sqrt(th2)
    L = math.exp(-0.5 * dist2 / th2) / (math.sqrt(2 * math.pi) * th)
    dth = 0.5 * sp2 * gam * (1 - gam + gam * math.sqrt(lam)) / (th * math.sqrt(lam))
    Lp = L * dth * (dist2 / th2 - 1) / th
    return L, Lp


def linear_bayes(dist2, sp2, so2, lm, lsd2, gam):
    L, Lp = lik_and_deriv(dist2, sp2, so2, lm, gam)
    if L <= 0 or Lp == 0:
        return lm
    r = L / Lp
    p, m = solve_quadratic(1.0, r - 2 * lm, lm ** 2 - lsd2 - r * lm)
    return m if abs(m - lm) < abs(p - lm) else p


def gauss_post(dist2, sp2, so2, lm, lsd, gam, lam):
    th2 = theta2(lam, gam, sp2, so2)
    return (math.exp(-(lam - lm) ** 2 / (2 * lsd ** 2) - dist2 / (2 * th2))
            / (2 * math.pi * lsd * math.sqrt(th2)))


def change_GA_IG(mode, var):
    v, m = var, mode
    AA = m ** 4 * math.sqrt((v ** 2 + 47 * v * m ** 2 + 3 * m ** 4) / v ** 3)
    BB = 75 * v ** 2 * m ** 5
    CC = 21 * v * m ** 7
    DD = v ** 3 * m ** 3
    EE = (CC + BB + DD + m ** 9 + 6 * math.sqrt(3) * AA * v ** 3) / v ** 3
    return ((7 * v * m + m ** 3) / (3 * v) + EE ** (1 / 3) / 3
            + m ** 2 * (v ** 2 + 14 * v * m ** 2 + m ** 4) / (3 * v ** 2 * EE ** (1 / 3)))


def enh_linear_bayes(dist2, sp2, so2, lm, gam, N, beta):
    L, Lp = lik_and_deriv(dist2, sp2, so2, lm, gam, N)
    if L <= 0 or Lp == 0 or abs(L) <= TINY or abs(Lp) <= TINY:
        return lm
    r = L / Lp
    p, m = solve_quadratic(1 - lm / beta, r - 2 * lm, lm ** 2 - r * lm)
    new = m if abs(m - lm) < abs(p - lm) else p
    if new <= 0 or new != new:
        new = lm
    return new


def ig_post(dist2, N, sp2, so2, alpha, beta, gam, lam):
    th = math.sqrt(theta2(lam, gam, sp2, so2, N))
    return (beta ** alpha / math.gamma(alpha) * lam ** (-alpha - 1) / (math.sqrt(2 * math.pi) * th)
            * math.exp(-0.5 * dist2 / th ** 2 - beta / lam))


def bayes_cov_inflate(N, flavor, xp, sp2, yo, so2, lm, lsd, gam, sd_lb, sd_max):
    """Returns (new mean, new sd, note)."""
    if gam <= 0:
        return lm, lsd, 'gamma<=0'
    dist2 = (yo - xp) ** 2
    if flavor == 2:
        new = linear_bayes(dist2, sp2, so2, lm, lsd ** 2, gam)
        if abs(lsd - sd_lb) <= TINY:
            return new, lsd, 'sd at floor'
        nmax = gauss_post(dist2, sp2, so2, lm, lsd, gam, new)
        n1 = gauss_post(dist2, sp2, so2, lm, lsd, gam, new + lsd)
        if abs(nmax) <= TINY or abs(n1) <= TINY:
            return new, lsd, 'tiny density'
        ratio = n1 / nmax
        if ratio > 0.99:
            return new, lsd, 'ratio>0.99'
        nsd = math.sqrt(-lsd ** 2 / (2 * math.log(ratio)))
        if nsd > lsd:
            return new, lsd, 'sd would grow'
        return new, nsd, ''
    beta = change_GA_IG(lm, lsd ** 2)
    new = enh_linear_bayes(dist2, sp2, so2, lm, gam, N, beta)
    if abs(lsd - sd_lb) <= TINY:
        return new, lsd, 'sd at floor'
    alpha = beta / lm - 1
    if alpha <= 2:
        return new, lsd, 'alpha<=2'
    d1 = ig_post(dist2, N, sp2, so2, alpha, beta, gam, new + lsd)
    d2 = ig_post(dist2, N, sp2, so2, alpha, beta, gam, new)
    if abs(d1) <= TINY or abs(d2) <= TINY or d1 != d1 or d2 != d2:
        return new, lsd, 'tiny density'
    omega = math.log(new) / new + 1 / new - math.log(new + lsd) / new - 1 / (new + lsd)
    beta_u = math.log(d1 / d2) / omega
    alpha_u = beta_u / new - 1
    if alpha_u <= 2:
        return new, lsd, 'alpha_u<=2'
    nsd = math.sqrt(beta_u ** 2 / ((alpha_u - 1) ** 2 * (alpha_u - 2)))
    if nsd > sd_max * lsd or nsd != nsd:
        return new, lsd, 'sd growth > max_change: rejected'
    return new, nsd, ''


def update_inflation(N, flavor, xp, sp2, yo, so2, lm, lsd, gam, lb=1.0, ub=5.0, sd_lb=0.6, sd_max=1.05):
    if lsd <= 0:
        return lm, lsd, 'sd<=0'
    new, nsd, note = bayes_cov_inflate(N, flavor, xp, sp2, yo, so2, lm, lsd, gam, sd_lb, sd_max)
    new = min(max(new, lb), ub)
    nsd = max(nsd, sd_lb)
    return new, nsd, note


def update_varying(N, flavor, lam, lsd, lam_applied, ymean, yvar, yo, so2, loc, corr, **kw):
    """update_varying_state_space_inflation: gamma, and this cycle's lambda taken out of yvar."""
    gam = loc * abs(corr)
    sp2 = yvar / (1 + gam * (math.sqrt(lam_applied) - 1)) ** 2 if abs(gam) > SMALL else yvar
    return update_inflation(N, flavor, ymean, sp2, yo, so2, lam, lsd, gam, **kw)


METAR = (0.25, 1.26 ** 2)       # prior var of H(x) (sd 0.5 K), obs error var (1.26 K)
RADAR2 = (4.0, 25.0)            # prior sd 2 dBZ, obs error 5 dBZ
RADAR8 = (64.0, 25.0)           # prior sd 8 dBZ

# ------------------------------------------------------------------- sections
if run(1):
    hdr("1. change_GA_IG: IG with mode lam_b and variance sd^2 [note 5.2]")
    for m, s in [(1.0, 0.6), (1.0, 0.3), (1.0, 0.1), (1.5, 0.6), (2.0, 0.6)]:
        b = change_GA_IG(m, s * s)
        a = b / m - 1
        r = b / m
        cubic = r ** 3 - (7 + m * m / (s * s)) * r ** 2 + 16 * r - 12
        var = b * b / ((a - 1) ** 2 * (a - 2))
        tau2 = m * m / (a + 1)
        print(f"lam_b={m:4.2f} sd={s:4.2f}: alpha={a:7.2f} beta={b:7.2f} mode={b / (a + 1):.6f} "
              f"var={var:.6f} (sd^2 {s * s:.6f}) cubic resid={cubic:.1e} IG mean={b / (a - 1):.3f} "
              f"tau^2={tau2:.4f} tau^2/sd^2={tau2 / (s * s):.2f}")

if run(2):
    hdr("2. E|r| for two unrelated variables [note 3.2]; theory for N = 5: 4/(3 pi) = %.4f"
        % (4 / (3 * math.pi)))
    rng = np.random.default_rng(0)
    for N in (5, 50):
        x = rng.normal(size=(200000, N))
        y = rng.normal(size=(200000, N))
        x -= x.mean(1, keepdims=True)
        y -= y.mean(1, keepdims=True)
        r = (x * y).sum(1) / np.sqrt((x * x).sum(1) * (y * y).sum(1))
        print(f"N={N:2d}: E|r| = {np.abs(r).mean():.3f}, median {np.median(np.abs(r)):.2f}, "
              f"90th percentile {np.percentile(np.abs(r), 90):.2f}")

if run(3):
    hdr("3. Flavor 2: linearized mode against the exact posterior mode, gamma = 1, sd 0.6 [note 7.1]")
    grid = np.linspace(0.05, 6, 600001)
    for name, (sp2, so2), d, lm in [("METAR, d = 1.5 K", METAR, 1.5, 1.0), ("METAR, d = 3 K", METAR, 3.0, 1.0),
                                    ("radar sd 2, d = 15 dBZ", RADAR2, 15.0, 1.0),
                                    ("radar sd 2, d = 2, lam_b 1.5", RADAR2, 2.0, 1.5)]:
        new = linear_bayes(d * d, sp2, so2, lm, 0.36, 1.0)
        th2 = grid * sp2 + so2
        lp = -(grid - lm) ** 2 / (2 * 0.36) - d * d / (2 * th2) - 0.5 * np.log(th2)
        print(f"{name:30s}: linearized {new:.4f}, exact {grid[np.argmax(lp)]:.4f}")

if run(4):
    hdr("4. One observation, gamma = 1, lam_b = 1, sd 0.6, N = 5, bounds [1, 5] [note 7.2]")
    print("case                    lam_hat | fl.2 lam  sd(floor .3) | fl.5 lam | fl.5 sd (floor .3)")
    for name, (sp2, so2), d in [("METAR, d = 1 K", METAR, 1.0), ("METAR, d = 2 K", METAR, 2.0),
                                ("METAR, d = 3 K", METAR, 3.0), ("radar sd 2, d = 5", RADAR2, 5.0),
                                ("radar sd 2, d = 15", RADAR2, 15.0), ("radar sd 8, d = 15", RADAR8, 15.0)]:
        r2 = update_inflation(5, 2, 0.0, sp2, d, so2, 1.0, 0.6, 1.0, sd_lb=0.3)
        r5 = update_inflation(5, 5, 0.0, sp2, d, so2, 1.0, 0.6, 1.0, sd_lb=0.3)
        print(f"{name:22s} {(d * d - so2) / sp2:7.1f} | {r2[0]:.4f}  {r2[1]:.3f}        | {r5[0]:.4f}   | "
              f"{r5[1]:.3f} {r5[2]}")
    print("step sizes (METAR, d = 2 K) against the small-step formulas (14), (20):")
    sp2, so2 = METAR
    L, Lp = lik_and_deriv(4.0, sp2, so2, 1.0, 1.0)
    b = change_GA_IG(1.0, 0.36)
    L5, Lp5 = lik_and_deriv(4.0, sp2, so2, 1.0, 1.0, 5)
    print(f"  flavor 2: {linear_bayes(4.0, sp2, so2, 1.0, 0.36, 1.0) - 1:.4f}, sd^2/q = {0.36 * Lp / L:.4f}")
    print(f"  flavor 5: {enh_linear_bayes(4.0, sp2, so2, 1.0, 1.0, 5, b) - 1:.4f}, tau^2/q = {Lp5 / L5 / b:.4f}"
          f" (tau^2 = {1 / b:.3f}); without -1/N: {enh_linear_bayes(4.0, sp2, so2, 1.0, 1.0, None, b) - 1:.4f}")
    print("gamma dependence (flavor 2, METAR, d = 2 K): lam_u - 1 =",
          ", ".join(f"{update_inflation(5, 2, 0.0, sp2, 2.0, so2, 1.0, 0.6, g)[0] - 1:.4f} (gamma {g})"
                    for g in (1.0, 0.5, 0.1)))
    print("deflation (lower bound 0):")
    for name, (sp2, so2), d in [("METAR, d = 0.5 K", METAR, 0.5), ("radar sd 2, d = 1", RADAR2, 1.0)]:
        r2 = update_inflation(5, 2, 0.0, sp2, d, so2, 1.0, 0.6, 1.0, lb=0.0)
        r5 = update_inflation(5, 5, 0.0, sp2, d, so2, 1.0, 0.6, 1.0, lb=0.0)
        print(f"  {name}: flavor 2 {r2[0]:.3f}, flavor 5 {r5[0]:.3f}")

if run(5):
    hdr("5. Identical observations at one element: radar sd 2, d = 8, gamma = 1; lam/sd after n [note 7.3]")
    sp2, so2 = RADAR2
    for fl, sdlb in [(2, 0.6), (2, 0.3), (5, 0.6), (5, 0.3)]:
        lam, sd, out = 1.0, 0.6, []
        for k in range(1, 41):
            lam, sd, _ = update_varying(5, fl, lam, sd, 1.0, 0.0, sp2, 8.0, so2, 1.0, 1.0, sd_lb=sdlb)
            if k in (1, 5, 10, 20, 40):
                out.append(f"{k}:{lam:.3f}/{sd:.3f}")
        print(f"flavor {fl}, floor {sdlb}: " + "  ".join(out))

if run(6):
    hdr("6. Random innovations at one element, radar sd 2, 2000 obs, d ~ N(0, lam_true sp2 + so2) [note 7.3]")
    rng = np.random.default_rng(1)
    sp2, so2 = RADAR2
    for gam in [1.0, 0.3]:
        for lam_true in [0.7, 1.0, 2.0]:
            print(f"gamma={gam}, lam_true={lam_true}; lam/sd after n")
            d_all = rng.normal(0, math.sqrt(lam_true * sp2 + so2), size=2000)
            for fl, sdlb, lb in [(2, 0.6, 1.0), (2, 0.3, 1.0), (5, 0.6, 1.0), (5, 0.3, 1.0), (5, 0.3, 0.0)]:
                lam, sd, out = 1.0, 0.6, []
                for k, d in enumerate(d_all, 1):
                    lam, sd, _ = update_varying(5, fl, lam, sd, 1.0, 0.0, sp2, d, so2, 1.0, gam,
                                                sd_lb=sdlb, lb=lb, ub=5.0)
                    if k in (10, 100, 500, 2000):
                        out.append(f"{k}:{lam:.3f}/{sd:.3f}")
                print(f"   flavor {fl}, floor {sdlb}, lower bound {lb}: " + "  ".join(out))

if run(7):
    hdr("7. Constant gain: lambda with a fixed sd, radar sd 2, lam_true 1.5, lower bound 0, 20000 obs [note 7.4]")
    rng = np.random.default_rng(2)
    sp2, so2 = RADAR2
    for gam in [1.0, 0.5]:
        d_all = rng.normal(0, math.sqrt(1.5 * sp2 + so2), size=20000)
        I = 0.5 * (gam * sp2 / (sp2 + so2)) ** 2          # Fisher information at lambda = 1 (flavor 2)
        for fl in (2, 5):
            for sd in (0.6, 0.3):
                lam, s, tr = 1.0, sd, []
                for d in d_all:
                    lam, s, _ = update_varying(5, fl, lam, s, 1.0, 0.0, sp2, d, so2, 1.0, gam,
                                               sd_lb=sd, lb=0.0, ub=50.0)
                    tr.append(lam)
                tr = np.array(tr[3000:])
                print(f"gamma={gam} flavor {fl} sd {sd}: mean lam {tr.mean():.3f}, sd of lam {tr.std():.3f} "
                      f"(sd/sqrt2 = {sd / math.sqrt(2):.3f}), memory 1/(sd^2 I) = {1 / (sd * sd * I):.0f} obs")

if run(8):
    hdr("8. Flavor 5's wrong root: sp2 = 1, so2 = 0.2, gamma = 1, lam_b = 1, sd 0.6, N = 5 [note 5.3]")
    b = change_GA_IG(1.0, 0.36)
    a = b - 1
    print(f"alpha = {a:.3f}; wrong root when 0 < q = l/l' < 2 lam_b/(alpha+1) = {2 / (a + 1):.3f}")
    sp2, so2 = 1.0, 0.2
    grid = np.linspace(0.05, 8, 400001)
    th2 = np.where(grid < 1 / 5, grid, grid - 1 / 5) * sp2 + so2      # flavor-5 theta^2, gamma = 1
    for q in (4, 6, 8, 9, 12):
        d2 = q * (sp2 + so2)                   # the outlier check passes q <= 9
        L, Lp = lik_and_deriv(d2, sp2, so2, 1.0, 1.0, 5)
        lp = (-a - 1) * np.log(grid) - b / grid - 0.5 * np.log(th2) - d2 / (2 * th2)
        print(f"d^2/(var+R) = {q:2d}: q = {L / Lp:6.3f}  flavor 5 (DART) {enh_linear_bayes(d2, sp2, so2, 1.0, 1.0, 5, b):.4f}"
              f"  exact IG-posterior mode {grid[np.argmax(lp)]:.3f}  flavor 2 (DART) "
              f"{linear_bayes(d2, sp2, so2, 1.0, 0.36, 1.0):.4f}")
    print("threshold on d^2/(sp2+so2) for the wrong root (lam_b = lam0 = 1, gamma = 1):")
    for sd in (0.6, 0.3):
        a = change_GA_IG(1.0, sd * sd) - 1
        row = []
        for ratio in (0.05, 0.1, 0.2, 0.5):        # so2/sp2
            th2 = 0.8 + ratio                       # flavor-5 theta^2 at lambda 1, in units of sp2
            row.append(f"so2/sp2 {ratio}: {(1 + th2 * (a + 1)) * th2 / (1 + ratio):.1f}")
        print(f"  sd {sd}: " + ";  ".join(row))

if run(9):
    hdr("9. float32: beta**alpha overflows (alpha ln beta > ln FLT_MAX), so the flavor-5 sd freezes [note 5.4]")
    lim = math.log(float(np.finfo(np.float32).max))
    for lm in [1.0, 1.25, 1.5, 2.0, 3.0, 5.0]:
        sd = 2.0
        while sd > 0.01:
            b = change_GA_IG(lm, sd * sd)
            a = b / lm - 1
            if a * math.log(b) > lim:
                break
            sd -= 0.001
        print(f"lam_b={lm:4.2f}: sd frozen for sd <= {sd:.3f} (alpha {a:.1f}, beta {b:.1f}; sd/lam {sd / lm:.3f})")

if run(10):
    hdr("10. Damping 0.9: on lambda (code) against on sqrt(lambda) (G18, guide note) [note 8]")
    for lam in [1.5, 2.0, 3.0, 5.0]:
        print(f"lam={lam}: code {1 + 0.9 * (lam - 1):.4f}; sqrt form {(1 + 0.9 * (math.sqrt(lam) - 1)) ** 2:.4f}")
