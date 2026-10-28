"""Numerical checks for notes/dart_flavor5_wrong_root.md: the root choice in flavor 5's mode update.

Uses the line-by-line translation of DART's routines in inflation_checks.py (double precision) and
adds the patched rule (patches/dart_7bbd35a09_flavor5_root_choice.patch): take the larger root if
like_prime > 0 and the smaller one if like_prime < 0, i.e. the root on the side of lambda_mean that
the likelihood's slope points to. DART's rule is the root closest to lambda_mean. The patched
Fortran routine itself is run by flavor5_root_fortran_check.sh.

Notation as in the note: q = like_bar/like_prime, c = lam_b/beta = 1/(alpha+1),
r = d^2/theta_bar^2 (innovation against the variance the current lambda predicts), rho = so2/sp2.

Sections (note section in brackets):
   1  the algebra: f(-q) = -c (q - lam_b)^2, the roots straddle lam_b, the valid root  [2.1-2.3]
   2  the patched root is the mode of the linearized posterior G18 (36) (grid)          [2.3]
   3  sweep: DART's root, the patched root and the exact IG-posterior mode             [4.2, 4.3]
   4  when it can happen: thresholds under the outlier check (3 sd)                    [3.2]
   5  the inflation note's cases: mean and sd after one update, both rules             [4.2]
   6  a run of identical observations at one element, both rules                       [3.3]
   7  flavor 2: its closest root is always the root the patched rule would take       [2.4]

Run (some seconds; give section numbers to run only those):
  uv run --no-project --with numpy python -I notes/checks/flavor5_root_checks.py [n ...]
"""
import math
import os
import sys
from collections import Counter
import numpy as np

# Import the DART translation without running its sections (they run only for the numbers in argv).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_argv, sys.argv = sys.argv, sys.argv[:1] + ['0']
import inflation_checks as ic          # noqa: E402
sys.argv = _argv

ONLY = {int(a) for a in sys.argv[1:]}
TINY = ic.TINY
N = 5
dart_enh_linear_bayes = ic.enh_linear_bayes


def run(n):
    return not ONLY or n in ONLY


def hdr(s):
    print(f"\n=== {s}")


# ------------------------------------------------------------------- the two rules
def enh_linear_bayes_patched(dist2, sp2, so2, lm, gam, N, beta):
    """enh_linear_bayes with the patched root choice."""
    L, Lp = ic.lik_and_deriv(dist2, sp2, so2, lm, gam, N)
    if L <= 0 or Lp == 0 or abs(L) <= TINY or abs(Lp) <= TINY:
        return lm
    r = L / Lp
    p, m = ic.solve_quadratic(1 - lm / beta, r - 2 * lm, lm ** 2 - r * lm)
    new = max(p, m) if r > 0 else min(p, m)
    if new <= 0 or new != new:
        new = lm
    return new


def update_inflation(patched, *args, **kw):
    """ic.update_inflation (bayes_cov_inflate and the bounds) with DART's or the patched root choice."""
    ic.enh_linear_bayes = enh_linear_bayes_patched if patched else dart_enh_linear_bayes
    try:
        return ic.update_inflation(*args, **kw)
    finally:
        ic.enh_linear_bayes = dart_enh_linear_bayes


def update_varying(patched, *args, **kw):
    ic.enh_linear_bayes = enh_linear_bayes_patched if patched else dart_enh_linear_bayes
    try:
        return ic.update_varying(*args, **kw)
    finally:
        ic.enh_linear_bayes = dart_enh_linear_bayes


def theta2_vec(lam, gam, sp2, so2, N=None):
    """ic.theta2 for an array of lambda."""
    f1 = (1 + gam * (np.sqrt(lam) - 1)) ** 2
    f2 = np.zeros_like(lam) if N is None else np.where(f1 < 1.0 / N, 0.0, -1.0 / N)
    return (f1 + f2) * sp2 + so2


def q_of(dist2, sp2, so2, lm, gam, N=N):
    L, Lp = ic.lik_and_deriv(dist2, sp2, so2, lm, gam, N)
    return L / Lp


def argmax_refined(logp, lo, hi, n=20001, rounds=3):
    """Maximize logp on [lo, hi]: geometric grid, then two finer linear grids around the maximum.
    Also returns where the interior local maxima of the first grid are."""
    x = np.geomspace(lo, hi, n)
    y = logp(x)
    k = int(np.nanargmax(y))
    inner = y[1:-1]
    xmax = x[1:-1][(inner > y[:-2]) & (inner >= y[2:])]
    for _ in range(rounds - 1):
        a, b = x[max(k - 2, 0)], x[min(k + 2, len(x) - 1)]
        x = np.linspace(a, b, 2001)
        y = logp(x)
        k = int(np.nanargmax(y))
    return x[k], xmax


def exact_ig_mode(dist2, sp2, so2, lm, lsd, gam, N=N):
    """Mode of the exact (not linearized) flavor-5 posterior: IG prior times the likelihood (6), (8).
    Also returns the number of local maxima, not counting one at the jump of theta^2 where the code
    drops the -1/N term (s^2 = 1/N)."""
    beta = ic.change_GA_IG(lm, lsd * lsd)
    alpha = beta / lm - 1

    def logp(x):
        th2 = theta2_vec(x, gam, sp2, so2, N)
        return -(alpha + 1) * np.log(x) - beta / x - 0.5 * np.log(th2) - 0.5 * dist2 / th2

    mode, xmax = argmax_refined(logp, 1e-3 * lm, lm + 40 * lsd + 50)
    s2 = (1 + gam * (np.sqrt(xmax) - 1)) ** 2
    return mode, int(np.sum(np.abs(s2 - 1.0 / N) > 0.01))


def linearized_mode(dist2, sp2, so2, lm, lsd, gam, N=N):
    """Mode of the linearized posterior G18 (36) on its domain (where l + l' (lambda - lam_b) > 0)."""
    beta = ic.change_GA_IG(lm, lsd * lsd)
    alpha = beta / lm - 1
    L, Lp = ic.lik_and_deriv(dist2, sp2, so2, lm, gam, N)

    def logp(x):
        lin = L + Lp * (x - lm)
        with np.errstate(invalid='ignore', divide='ignore'):
            return np.where(lin > 0, -(alpha + 1) * np.log(x) - beta / x + np.log(np.maximum(lin, 1e-300)),
                            -np.inf)

    mode, xmax = argmax_refined(logp, 1e-4 * lm, lm + 40 * lsd + 50)
    return mode, len(xmax)


def d2_from_ratio(r, sp2, so2, lm, gam, N=N):
    """d^2 for a given r = d^2/theta_bar^2 (flavor-5 theta at lam_b)."""
    return r * ic.theta2(lm, gam, sp2, so2, N)


def r_threshold(lm, lsd, gam, rho, N=N):
    """r = d^2/theta_bar^2 above which DART takes the wrong root (sp2 = 1): q < 2 lam_b/(alpha+1)."""
    beta = ic.change_GA_IG(lm, lsd * lsd)
    s = 1 - gam + gam * math.sqrt(lm)
    th2 = ic.theta2(lm, gam, 1.0, rho, N)
    return 1 + (beta / lm) * th2 / (gam * s * math.sqrt(lm))


def outlier_ratio_threshold(lm, lsd, gam, rho, lam0, N=N):
    """The same threshold as d^2/(sigma_y^2 + sigma_o^2), the outlier check's ratio (passes <= 9).
    sigma_y^2 = s(lam0)^2 sp2: the inflated prior variance, lam0 = lambda applied this cycle."""
    s0 = 1 - gam + gam * math.sqrt(lam0)
    return r_threshold(lm, lsd, gam, rho, N) * ic.theta2(lm, gam, 1.0, rho, N) / (s0 * s0 + rho)


SP2 = 1.0
GAMS = [0.05, 0.2, 0.5, 0.8, 1.0]
LMS = [1.0, 1.5, 2.0, 3.0, 5.0]
LSDS = [0.3, 0.6, 1.0, 1.5]
RHOS = [0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
RATIOS = [0.0, 0.05, 0.3, 0.7, 0.95, 0.999, 1.001, 1.05, 1.5, 2, 3, 5, 7, 9, 12, 16, 25, 50]


def sweep():
    for gam in GAMS:
        for lm in LMS:
            for lsd in LSDS:
                for rho in RHOS:
                    for r in RATIOS:
                        yield gam, lm, lsd, rho, r


# ------------------------------------------------------------------- sections
if run(1):
    hdr("1. The algebra [note 2.1-2.3]: f(delta) = (1-c) delta^2 + (q - 2 c lam_b) delta - c lam_b^2")
    worst_fq, n, n_straddle, n_valid, n_spur = 0.0, 0, 0, 0, 0
    for gam, lm, lsd, rho, r in sweep():
        d2 = d2_from_ratio(r, SP2, rho, lm, gam)
        if r == 1.0:
            continue
        beta = ic.change_GA_IG(lm, lsd * lsd)
        c = lm / beta
        q = q_of(d2, SP2, rho, lm, gam)
        fq = (1 - c) * q * q - (q - 2 * c * lm) * q - c * lm * lm
        worst_fq = max(worst_fq, abs(fq + c * (q - lm) ** 2) / max(1.0, q * q))
        p, m = ic.solve_quadratic(1 - c, q - 2 * lm, lm * lm - q * lm)
        dlo, dhi = min(p, m) - lm, max(p, m) - lm
        n += 1
        n_straddle += dlo < 0 < dhi and dlo <= -q <= dhi
        valid = dhi if q > 0 else dlo            # the patched choice
        spur = dlo if q > 0 else dhi
        n_valid += (q + valid) * q > 0           # l + l' delta > 0  <=>  q (q + delta) > 0
        n_spur += (q + spur) * q <= 1e-12 * q * q
    print(f"cases: {n}; f(-q) = -c (q - lam_b)^2 to {worst_fq:.1e} (relative)")
    print(f"roots on either side of lam_b, with -q between them: {n_straddle}/{n}")
    print(f"root with the sign of q inside the domain l + l' delta > 0: {n_valid}/{n}; "
          f"other root outside (or on its edge): {n_spur}/{n}")

if run(2):
    hdr("2. The patched root is the mode of the linearized posterior G18 (36) [note 2.3]")
    print("sp2 = 1, so2 = 0.2, gamma = 1, N = 5; lam_b, sd, r = d^2/theta_bar^2")
    for lm, lsd, r in [(1.0, 0.6, 9.0), (1.0, 0.6, 12.0), (1.0, 0.6, 3.0), (1.0, 0.6, 0.3),
                       (2.0, 1.2, 15.0), (2.0, 0.6, 0.0), (1.5, 0.3, 30.0)]:
        d2 = d2_from_ratio(r, SP2, 0.2, lm, 1.0)
        beta = ic.change_GA_IG(lm, lsd * lsd)
        q = q_of(d2, SP2, 0.2, lm, 1.0)
        mode, nmax = linearized_mode(d2, SP2, 0.2, lm, lsd, 1.0)
        print(f"lam_b {lm} sd {lsd} r {r:5.1f}: q = {q:8.4f} (2c lam_b = {2 * lm * lm / beta:.4f})  "
              f"DART {dart_enh_linear_bayes(d2, SP2, 0.2, lm, 1.0, N, beta):.5f}  "
              f"patched {enh_linear_bayes_patched(d2, SP2, 0.2, lm, 1.0, N, beta):.5f}  "
              f"grid mode of (36) {mode:.5f} ({nmax} local max)")

if run(3):
    hdr("3. Sweep: DART's root, the patched root, the exact IG-posterior mode [note 4.2, 4.3]")
    print(f"gamma {GAMS}\nlam_b {LMS}\nsd {LSDS}\nrho = so2/sp2 {RHOS}\nr = d^2/theta_bar^2 {RATIOS}")
    n = n_fail = n_diff = n_diff_outside = n_fail_same = 0
    n_dir_patched = n_dir_exact = n_multimodal = 0
    n_closer = 0
    fail_old_below, fail_new_above = 0, 0
    step_ratio_fail, step_ratio_ord, step_ratio_fail_qc = [], [], []
    multimodal = []
    sd_notes_fail_old, sd_notes_fail_new = Counter(), Counter()
    for gam, lm, lsd, rho, r in sweep():
        d2 = d2_from_ratio(r, SP2, rho, lm, gam)
        beta = ic.change_GA_IG(lm, lsd * lsd)
        L, Lp = ic.lik_and_deriv(d2, SP2, rho, lm, gam, N)
        if L <= 0 or Lp == 0:
            continue
        q = L / Lp
        old = dart_enh_linear_bayes(d2, SP2, rho, lm, gam, N, beta)
        new = enh_linear_bayes_patched(d2, SP2, rho, lm, gam, N, beta)
        exact, nmax = exact_ig_mode(d2, SP2, rho, lm, lsd, gam)
        n += 1
        n_multimodal += nmax > 1
        # passes the outlier check (3 sd) if lam0 = lam_b: flavor-2 theta^2 is sigma_y^2 + sigma_o^2 then
        passes_qc = d2 / ic.theta2(lm, gam, SP2, rho) <= 9.0
        if nmax > 1:
            multimodal.append((gam, lm, lsd, rho, r, passes_qc))
        fail = 0 < q < 2 * lm * lm / beta
        n_fail += fail
        n_diff += old != new
        n_diff_outside += (old != new) and not fail
        n_fail_same += fail and old == new
        n_dir_patched += (new - lm) * q >= 0
        n_dir_exact += (exact - lm) * q > 0 or abs(exact - lm) < 1e-6 * lm
        if fail:
            fail_old_below += old < lm
            fail_new_above += new > lm
            n_closer += abs(new - exact) < abs(old - exact)
            step_ratio_fail.append((new - lm) / (exact - lm))
            if passes_qc:
                step_ratio_fail_qc.append((new - lm) / (exact - lm))
            # the sd update, flavor-5 floor 0.3 and bounds [1, 5] (our run-5 settings), from yo = sqrt(d2)
            sd_notes_fail_old[update_inflation(False, N, 5, 0.0, SP2, math.sqrt(d2), rho, lm, lsd, gam,
                                               sd_lb=0.3)[2] or 'sd updated'] += 1
            sd_notes_fail_new[update_inflation(True, N, 5, 0.0, SP2, math.sqrt(d2), rho, lm, lsd, gam,
                                               sd_lb=0.3)[2] or 'sd updated'] += 1
        elif q > 0 and exact - lm > 1e-3 * lm:
            step_ratio_ord.append((new - lm) / (exact - lm))
    print(f"cases: {n}; exact posterior with more than one local maximum (besides the theta jump): "
          f"{n_multimodal}, passing the outlier check: {sum(m[-1] for m in multimodal)}")
    for m in multimodal:
        print(f"   gamma {m[0]}, lam_b {m[1]}, sd {m[2]}, rho {m[3]}, r {m[4]}, passes the outlier check: {m[5]}")
    print(f"wrong-root region 0 < q < 2 lam_b^2/beta: {n_fail} cases; DART and patched differ in {n_diff} "
          f"({n_diff_outside} outside the region; {n_fail_same} inside it where they agree)")
    print(f"patched step has the sign of q: {n_dir_patched}/{n}; exact mode on the side of q: {n_dir_exact}/{n}")
    print(f"in the region: DART's root below lam_b {fail_old_below}/{n_fail}, patched above {fail_new_above}/{n_fail}, "
          f"patched closer to the exact mode {n_closer}/{n_fail}")
    for name, v in [("in the region", step_ratio_fail), ("in the region, passing the outlier check", step_ratio_fail_qc),
                    ("q > 0 outside it", step_ratio_ord)]:
        v = np.array(v)
        print(f"step (patched - lam_b)/(exact - lam_b), {name} ({len(v)} cases): "
              f"min {v.min():.3f}, 10 % {np.percentile(v, 10):.3f}, median {np.median(v):.3f}, max {v.max():.3f}")
    print(f"sd update in the region (floor 0.3), DART: {dict(sd_notes_fail_old)}")
    print(f"                                 patched: {dict(sd_notes_fail_new)}")

if run(4):
    hdr("4. When it can happen, outlier check passing d^2/(sigma_y^2 + sigma_o^2) <= 9 [note 3.2]")
    print("(a) threshold on d^2/(sigma_y^2 + sigma_o^2) for the wrong root, lam_b = lam0 = 1, gamma = 1")
    print("    (check: DART's root just below and just above the threshold, rho 0.2)")
    for lsd in (0.3, 0.45, 0.6, 0.8, 1.0, 1.5):
        a = ic.change_GA_IG(1.0, lsd * lsd) - 1
        row = "  ".join(f"rho {rho}: {outlier_ratio_threshold(1.0, lsd, 1.0, rho, 1.0):5.1f}"
                        for rho in (0.05, 0.1, 0.2, 0.5))
        rt = r_threshold(1.0, lsd, 1.0, 0.2)
        beta = ic.change_GA_IG(1.0, lsd * lsd)
        lo, hi = [dart_enh_linear_bayes(d2_from_ratio(rt * f, SP2, 0.2, 1.0, 1.0), SP2, 0.2, 1.0, 1.0, N, beta)
                  for f in (0.999, 1.001)]
        print(f"  sd {lsd:4.2f} (alpha {a:5.2f}): {row}   [{lo:.4f} / {hi:.4f}]")
    print("(b) smallest gamma at which the wrong root can be taken (none: '-')")
    cases = [(1.0, 1.0, "lam_b = lam0 = 1"), (2.0, 2.0, "lam_b = lam0 = 2"), (1.0, 2.0, "lam_b = 1, lam0 = 2"),
             (1.0, 3.0, "lam_b = 1, lam0 = 3")]
    for lm, lam0, name in cases:
        print(f"  {name}:")
        for lsd in (0.3, 0.6, 1.0, 1.5):
            row = []
            for rho in (0.05, 0.1, 0.2, 0.5):
                gs = np.linspace(0.001, 1.0, 1000)
                ok = [g for g in gs if outlier_ratio_threshold(lm, lsd, g, rho, lam0) < 9.0]
                row.append(f"rho {rho}: {ok[0]:.2f}" if ok else f"rho {rho}:   - ")
            print(f"    sd {lsd:3.1f} (sd/lam_b {lsd / lm:.2f}): " + "  ".join(row))
    print("(c) smallest sd/lam_b at which the wrong root can be taken, gamma = 1, lam_b = lam0")
    for lm in (1.0, 1.5, 2.0, 3.0, 5.0):
        row = []
        for rho in (0.0, 0.02, 0.05, 0.2):
            rel = next(x for x in np.arange(0.2, 2.0, 0.001) if outlier_ratio_threshold(lm, x * lm, 1.0, rho, lm) < 9)
            row.append(f"rho {rho}: {rel:.3f}")
        print(f"  lam_b {lm}: " + "  ".join(row))

if run(5):
    hdr("5. The inflation note's cases (Sec. 5.3): one update, bounds [1, 5], sd floor 0.3, N = 5 [note 4.2]")
    print("sp2 = 1, so2 = 0.2, gamma = 1; d^2/(sigma_y^2 + sigma_o^2) at lam0 = lam_b")
    for lm, lsd, ratios in [(1.0, 0.6, (4, 6, 8, 9, 12)), (2.0, 1.2, (6, 8, 9))]:
        for k in ratios:
            d2 = k * (lm * SP2 + 0.2)
            old = update_inflation(False, N, 5, 0.0, SP2, math.sqrt(d2), 0.2, lm, lsd, 1.0, sd_lb=0.3)
            new = update_inflation(True, N, 5, 0.0, SP2, math.sqrt(d2), 0.2, lm, lsd, 1.0, sd_lb=0.3)
            exact, _ = exact_ig_mode(d2, SP2, 0.2, lm, lsd, 1.0)
            f2 = update_inflation(False, N, 2, 0.0, SP2, math.sqrt(d2), 0.2, lm, lsd, 1.0, sd_lb=0.3)
            print(f"lam_b {lm} sd {lsd} ratio {k:2d}: DART {old[0]:.4f} sd {old[1]:.4f} {old[2] or '':12s} | "
                  f"patched {new[0]:.4f} sd {new[1]:.4f} {new[2] or '':34s} | exact mode {exact:.3f} | "
                  f"flavor 2 {f2[0]:.4f}")

if run(6):
    hdr("6. Identical observations at one element, ratio d^2/(sigma_y^2 + sigma_o^2) = 8 [note 3.3]")
    print("sp2 = 1, so2 = 0.2, gamma = 1, lam0 = 1, start lam 1, sd 0.6; bounds [1, 5]; lam/sd after n")
    d = math.sqrt(8 * 1.2)
    for fl, patched, sdlb in [(5, False, 0.3), (5, True, 0.3), (5, True, 0.6), (2, False, 0.6), (2, False, 0.3)]:
        lam, sd, out = 1.0, 0.6, []
        for k in range(1, 41):
            lam, sd, _ = update_varying(patched, N, fl, lam, sd, 1.0, 0.0, SP2, d, 0.2, 1.0, 1.0, sd_lb=sdlb)
            if k in (1, 2, 5, 10, 20, 40):
                out.append(f"{k}:{lam:.3f}/{sd:.3f}")
        name = f"flavor {fl}" + ("" if fl == 2 else (", patched" if patched else ", DART   "))
        print(f"{name:18s} floor {sdlb}: " + "  ".join(out))

if run(7):
    hdr("7. Flavor 2: the closest root is the root on the side of q [note 2.4]")
    n = n_same = n_neg = 0
    for gam, lm, lsd, rho, r in sweep():
        d2 = d2_from_ratio(r, SP2, rho, lm, gam, None)
        L, Lp = ic.lik_and_deriv(d2, SP2, rho, lm, gam)
        if L <= 0 or Lp == 0:
            continue
        q = L / Lp
        p, m = ic.solve_quadratic(1.0, q - 2 * lm, lm ** 2 - lsd ** 2 - q * lm)
        closest = ic.linear_bayes(d2, SP2, rho, lm, lsd ** 2, gam)
        n += 1
        n_same += closest == (max(p, m) if q > 0 else min(p, m))
        n_neg += closest <= 0
    print(f"cases {n}: closest root = root on the side of q in {n_same}; closest root <= 0 in {n_neg} "
          f"(clipped by inf_lower_bound)")
