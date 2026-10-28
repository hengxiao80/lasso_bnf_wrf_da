# Flavor 5's wrong root in DART's inflation update, and a fix

Written 2026-10-27 in session "DART inflation flavor 5 wrong root issue" (hand-off `notes/handoffs/2026-10-27_dart_inflation_flavor5_wrong_root_issue.md`).

**What this note is.** `dart_adaptive_inflation.md` Sec. 5.3 found that DART's flavor-5 (G18) mode update sometimes takes the wrong root of its quadratic. This note works out why, when it can happen, which root is right, and a patch that takes it. Notation, the likelihood and the mode equations are those of `dart_adaptive_inflation.md` (the **inflation note** below; Sec. 1, 3.5, 4.1, 5.2, 5.3); its equations are cited as "inflation note (18)".

**Sources and checks.**
- **Code:** DART `7bbd35a09` (v11.25.3), `adaptive_inflate_mod.f90`: `enh_linear_bayes` (`:1122–1191`), `solve_quadratic` (`:1197–1222`), `linear_bayes` (`:1060–1116`).
- **Patch:** `patches/dart_7bbd35a09_flavor5_root_choice.patch` (entry in `patches/README.md`).
- **Python:** `notes/checks/flavor5_root_checks.py`, sections 1–7; it uses the line-by-line translation of DART's routines in `inflation_checks.py`. Run: `uv run --no-project --with numpy python -I notes/checks/flavor5_root_checks.py [n ...]` (half a minute; section 3 takes most of it).
- **Fortran:** `notes/checks/flavor5_root_fortran_check.sh` cuts `bayes_cov_inflate` … `change_GA_IG` out of DART's commit and out of a patched copy, compiles both stand-alone with our ifort at float32 (our `r8 = r4`) and float64, and runs `flavor5_root_fortran_driver.f90`. Run: `bash notes/checks/flavor5_root_fortran_check.sh`.

**Typora.** Display equations are `$$` blocks. Inline math (`$...$`) needs *Preferences → Markdown → Inline Math*.

---

## 0. Summary

- **The defect.** Flavor 5 finds the new $\lambda$ as a root of a quadratic and, like flavor 2, keeps the root closest to $\bar\lambda$. For a steep, rising likelihood (a large innovation where the prior spread is large against the observation error and the inflation sd is large against $\bar\lambda$), that is the wrong root: it lies where the linearized likelihood is negative, and it moves $\lambda$ **down** although the innovation asks for more inflation.
- **Which root is right (Sec. 2).** The two roots always lie on either side of $\bar\lambda$, and the right one is always the one on the side the likelihood's slope points to: the larger root if $\ell' > 0$, the smaller if $\ell' < 0$. It is the mode of G18's linearized posterior (36), it is always positive, and it lies on the same side of $\bar\lambda$ as the exact posterior mode. The other root is always spurious.
- **Why flavor 2 is safe and flavor 5 isn't (Sec. 2.4).** In flavor 2 the closest root is always the right one. In flavor 5 the IG prior's curvature term grows with $\lambda$, which pushes the right root out and pulls the spurious one in.
- **When (Sec. 3).** Only for $0 < q < 2\bar\lambda^2/\beta$, i.e. $d^2/\bar\theta^2$ above a threshold set by $\alpha$ (so by $\sigma_\lambda/\bar\lambda$), $\gamma$ and $\sigma_o^2/\sigma_p^2$. Through the outlier check (3 sd), and with $\bar\lambda$ equal to the applied $\lambda^0$, it needs $\sigma_\lambda/\bar\lambda \gtrsim 0.4$ ($\bar\lambda = 1$) to 0.55 ($\bar\lambda = 5$) even at $\gamma = 1$, and $\gamma \gtrsim 0.7$ at our initial (1, 0.6). Where $\bar\lambda$ has dropped below $\lambda^0$ during the cycle, or where flavor 5's sd has grown, it is reached more easily.
- **The fix (Sec. 4).** Four lines in `enh_linear_bayes`: take `max(roots)` if `like_ratio > 0`, else `min(roots)`.
  - **Checked** against the mode of (36) and the exact posterior mode (12,600 cases, Python), and with DART's own routines, original against patched, in float32 and float64 (100,800 cases).
  - **Same result as DART everywhere else:** the patch changes the result exactly in the wrong-root cases and is bit-identical in all others.
  - **Flavor 2 is untouched,** since its code path doesn't change.
- **What stays.** The linearization itself. For steep likelihoods the patched step is short of the exact posterior mode: 0.78–1.34 of the exact step where the outlier check passes.
- **Status.**
  - The patch is in `patches/` but **not applied**, and filter is not rebuilt.
  - Upstream DART `main` is still `7bbd35a09` (checked 2026-10-27), and DART_LAB's MATLAB version has the same rule. No GitHub issue mentions it.
  - How often it changed $\lambda$ in run 5 is not measured yet: a replay of run 5's filter steps with the patched filter would measure it (Sec. 5).

---

## 1. The mode equation

From inflation note Sec. 5.3, Step 4: with $\delta = \lambda - \bar\lambda$ and $q = \ell/\ell'$, the mode of the linearized posterior G18 (36) solves

$$
\delta\,(q+\delta) - \frac{\bar\lambda}{\beta}\,\lambda^2 = 0 . \tag{1}
$$

Write

$$
c \equiv \frac{\bar\lambda}{\beta} = \frac{1}{\alpha+1} . \notag
$$

Since $\alpha > 2$ for every IG that `change_GA_IG` returns, $0 < c < 1/3$. Put $\lambda = \bar\lambda + \delta$ into (1) and collect powers of $\delta$:

$$
f(\delta) \equiv (1-c)\,\delta^2 + (q - 2c\bar\lambda)\,\delta - c\,\bar\lambda^2 = 0 . \tag{2}
$$

This is the code's quadratic in $\lambda$ (inflation note (18); `:1169–1171`), $a = 1-\bar\lambda/\beta$, $b = q - 2\bar\lambda$, $c_0 = \bar\lambda^2 - q\bar\lambda$, shifted to $\delta$. `solve_quadratic` returns its two roots in a cancellation-safe form, and `enh_linear_bayes` keeps the one with the smaller $\lvert\lambda - \bar\lambda\rvert$.

Two facts about $q$ (inflation note (10)):
- $\ell > 0$, so **$q$ has the sign of $\ell'$**: $q > 0$ when $d^2 > \bar\theta^2$ (the innovation asks for more inflation), $q < 0$ when $d^2 < \bar\theta^2$.
- **$q$ never comes close to 0 from below.** $q = (\bar\theta/\bar\theta')/(d^2/\bar\theta^2 - 1)$, so $q < 0$ means $q \le -\bar\theta/\bar\theta'$ (reached at $d = 0$). Only $q \to 0^+$ is possible, as $d^2 \to \infty$: a very steep, rising likelihood.

---

## 2. Which root is right

### 2.1 The roots lie on either side of $\bar\lambda$, with $-q$ between them

- $f(0) = -c\bar\lambda^2 < 0$ and the leading coefficient $1 - c$ is positive, so $f$ has one negative root $\delta_-$ and one positive root $\delta_+$. In $\lambda$, one root is below $\bar\lambda$ and one above.
- At $\delta = -q$:

  $$
  \begin{aligned}
  f(-q) &= (1-c)\,q^2 - (q - 2c\bar\lambda)\,q - c\bar\lambda^2\\
  &= -c\,\big(q^2 - 2\bar\lambda q + \bar\lambda^2\big) = -c\,(q-\bar\lambda)^2 \;\le\; 0 .
  \end{aligned} \tag{3}
  $$

  So $-q$ lies between the roots: $\delta_- \le -q \le \delta_+$.

### 2.2 Only one root is in the domain

The log-derivative of Step 2 in the inflation note exists only where the linearized likelihood is positive:

$$
\ell + \ell'\delta > 0 \;\Longleftrightarrow\; \ell'\,(q+\delta) > 0 \;\Longleftrightarrow\; q\,(q+\delta) > 0 . \tag{4}
$$

The last step uses that $q$ has the sign of $\ell'$. So the domain is $\delta > -q$ if $q > 0$, and $\delta < -q$ if $q < 0$. With Sec. 2.1:

- **$q > 0$:** $\delta_+ > 0 > -q$ is in the domain; $\delta_- \le -q$ is not.
- **$q < 0$:** $\delta_- < 0 < -q$ is in the domain; $\delta_+ \ge -q$ is not.

**The right root is the one with the sign of $q$, and the other one is always spurious.** Step 3 of the inflation note (clearing the denominator $\ell + \ell'\delta$) is what lets the spurious root in.

### 2.3 The right root is the mode, and it is positive

- **It is the maximum of (36).** On the domain (4), together with $\lambda > 0$, the log-posterior $-(\alpha+1)\ln\lambda - \beta/\lambda + \ln(\ell+\ell'\delta)$ goes to $-\infty$ at both ends:
  - $\ln(\ell+\ell'\delta) \to -\infty$ at $\delta = -q$;
  - $-\beta/\lambda \to -\infty$ at $\lambda \to 0$;
  - $-(\alpha+1)\ln\lambda + \ln(\ldots) \sim -\alpha\ln\lambda \to -\infty$ as $\lambda \to \infty$ (for $q > 0$).

  On the domain, $q + \delta \ne 0$, so its log-derivative is zero exactly where $f = 0$. Its only zero there is the right root, so that root is the global maximum.
- **It is positive.** For $q > 0$ it is above $\bar\lambda$. For $q < 0$:

  $$
  f(-\bar\lambda) = \bar\lambda\,(\bar\lambda - q) > 0 , \tag{5}
  $$

  and $f(0) < 0$, so $-\bar\lambda < \delta_- < 0$, i.e. $0 < \lambda_u < \bar\lambda$. So with the right root, the guard "$\lambda_u \le 0$ keeps $\bar\lambda$" (`:1188–1189`) can only catch a NaN.
- **The exact posterior mode is on the same side.** The IG prior has its mode at $\bar\lambda$, so its log-derivative is zero there. The exact (not linearized) posterior's log-derivative at $\bar\lambda$ is therefore the likelihood's, $\ell'/\ell = 1/q$. A unimodal exact posterior thus has its mode on the side of $\bar\lambda$ that $q$ points to, like the right root. The wrong root moves $\lambda$ away from the exact mode.
- **Edge case $q = \bar\lambda$:** by (3), $-q$ is then itself a root, the spurious one, at $\lambda = 0$, where the linearized posterior is zero. The right root is unaffected.

Checked numerically (`flavor5_root_checks.py` sections 1–2):
- **Over the sweep of Sec. 4.3** (12,600 cases): (3) holds to $4\times10^{-16}$ (relative); the roots straddle $\bar\lambda$ with $-q$ between them in every case; the root with the sign of $q$ satisfies (4) in every case and the other root never does.
- **Against a grid maximization of (36)** on its domain: the root with the sign of $q$ is the grid mode to 5 decimals, also where DART takes the other root, e.g. $\bar\lambda = 1$, $\sigma_\lambda = 0.6$, $d^2/\bar\theta^2 = 9$: DART 0.62164, grid mode 1.37993.

### 2.4 Why DART's rule fails in flavor 5 and not in flavor 2

**Flavor 2.** Inflation note (12) is $\delta^2 + q\,\delta - \sigma_\lambda^2 = 0$. Its roots have product $-\sigma_\lambda^2$ and sum $-q$, so the one closer to 0 has the sign of $q$. Sec. 2.2's argument applies unchanged (here $f(-q) = -\sigma_\lambda^2 < 0$), so **the closest root is always the right one**. `flavor5_root_checks.py` section 7 confirms it in all 12,600 cases of the sweep.

**Flavor 5.** In (2), the roots have product $-c\bar\lambda^2/(1-c) < 0$ and sum $-(q - 2c\bar\lambda)/(1-c)$. So the root closer to 0 has the sign of $q - 2c\bar\lambda$, not of $q$:

| $q$ | sign of $q - 2c\bar\lambda$ | closest root | right? |
|---|---|---|---|
| $q < 0$ | − | $\delta_- < 0$ | yes |
| $0 < q < 2c\bar\lambda$ | − | $\delta_- < 0$ | **no** |
| $q > 2c\bar\lambda$ | + | $\delta_+ > 0$ | yes |

**Where the $-2c\bar\lambda$ comes from.** Equation (1) is flavor 2's (12) with $\sigma_\lambda^2$ replaced by $c\lambda^2 = \lambda^2/(\alpha+1)$ (inflation note (19)). That term is the IG's curvature variance, and unlike $\sigma_\lambda^2$ it grows with $\lambda$: the IG is wider to the right of its mode than to the left. This pushes the right root out to the right and pulls the left (spurious) root in. In the limit of an infinitely steep, rising likelihood ($q \to 0^+$):

$$
\begin{aligned}
\delta_+ &\to \bar\lambda\,\frac{\sqrt c}{1-\sqrt c},\\
\delta_- &\to -\bar\lambda\,\frac{\sqrt c}{1+\sqrt c} .
\end{aligned} \tag{6}
$$

At $\bar\lambda = 1$, $\sigma_\lambda = 0.6$ ($\alpha = 6.96$, $c = 0.126$) these are $+0.55$ and $-0.26$: the spurious root is closer.

---

## 3. When it happens

### 3.1 The threshold on the innovation

With inflation note (9),

$$
\frac{\bar\theta'}{\bar\theta} = \frac{\gamma\,\bar s\,\sigma_p^2}{2\,\bar\theta^2\sqrt{\bar\lambda}},\qquad \bar s = 1-\gamma+\gamma\sqrt{\bar\lambda} , \notag
$$

so, with $r \equiv d^2/\bar\theta^2$ (the innovation against the variance the current $\bar\lambda$ predicts),

$$
q = \frac{2\,\bar\theta^2\sqrt{\bar\lambda}}{\gamma\,\bar s\,\sigma_p^2\,(r-1)} . \tag{7}
$$

The wrong-root condition $0 < q < 2c\bar\lambda$ becomes

$$
r \;>\; r^* \equiv 1 + \frac{(\alpha+1)\,\bar\theta^2}{\gamma\,\bar s\,\sqrt{\bar\lambda}\,\sigma_p^2} . \tag{8}
$$

For $\gamma = 1$ ($\bar s\sqrt{\bar\lambda} = \bar\lambda$), with flavor 5's $\bar\theta^2 = (\bar\lambda - 1/N)\sigma_p^2 + \sigma_o^2$ and $\rho \equiv \sigma_o^2/\sigma_p^2$:

$$
r^* = 1 + (\alpha+1)\Big(1 - \frac{1}{N\bar\lambda} + \frac{\rho}{\bar\lambda}\Big) . \tag{9}
$$

- **$\alpha$ matters most:** $\alpha$ depends only on $\sigma_\lambda/\bar\lambda$ (inflation note (17)). At $\bar\lambda = 1$, $\rho = 1/N$ the threshold is exactly $\alpha + 2$.
- **A smaller $\gamma$ raises the threshold** about as $1/\gamma$.
- **A larger $\rho$ raises it a little.**

### 3.2 Through the outlier check

Every assimilated observation has $d^2 \le 9\,(\sigma_y^2 + \sigma_o^2)$, with $\sigma_y^2 = s(\lambda^0)^2\sigma_p^2$ the variance of the inflated prior ($\lambda^0$: the $\lambda$ applied this cycle, inflation note Sec. 3.3). So the wrong root is reachable only if $r^*\bar\theta^2 < 9\,(\sigma_y^2+\sigma_o^2)$. `flavor5_root_checks.py` section 4 gives the numbers.

**(a) Threshold on the outlier ratio $d^2/(\sigma_y^2+\sigma_o^2)$** for $\gamma = 1$, $\bar\lambda = \lambda^0 = 1$. The outlier check passes ratios up to 9. The rows for $\sigma_\lambda$ = 0.3 and 0.6 are the inflation note's table; DART's root just below and above the threshold confirms (8) (e.g. 1.3790 and 0.6210 at $\sigma_\lambda = 0.6$, $\rho = 0.2$).

| $\sigma_\lambda$ | $\alpha$ | $\rho$ = 0.05 | 0.1 | 0.2 | 0.5 |
|---|---|---|---|---|---|
| 0.3 | 16.2 | 12.7 | 13.5 | 15.2 | 20.3 |
| 0.45 | 9.53 | 8.1 | 8.6 | 9.6 | 12.7 |
| 0.6 | 6.96 | 6.3 | 6.7 | 7.5 | 9.8 |
| 0.8 | 5.34 | 5.2 | 5.5 | 6.1 | 8.0 |
| 1.0 | 4.48 | 4.6 | 4.9 | 5.4 | 7.0 |
| 1.5 | 3.46 | 3.9 | 4.1 | 4.6 | 5.9 |

**(b) Smallest $\gamma$ at which the wrong root can be taken** ("–": not at all, $\gamma \le 1$). Columns are $\rho$.

| $\bar\lambda$, $\lambda^0$, $\sigma_\lambda$ | 0.05 | 0.1 | 0.2 | 0.5 |
|---|---|---|---|---|
| 1, 1, 0.3 | – | – | – | – |
| 1, 1, 0.6 | 0.67 | 0.72 | 0.81 | – |
| 1, 1, 1.0 | 0.46 | 0.49 | 0.56 | 0.76 |
| 2, 2, 0.6 | – | – | – | – |
| 2, 2, 1.0 | 0.96 | – | – | – |
| 2, 2, 1.5 | 0.56 | 0.59 | 0.66 | 0.83 |
| 1, 2, 0.3 | 0.80 | 0.85 | 0.95 | – |
| 1, 2, 0.6 | 0.46 | 0.49 | 0.55 | 0.73 |
| 1, 3, 0.3 | 0.65 | 0.69 | 0.76 | 0.98 |
| 1, 3, 0.6 | 0.40 | 0.42 | 0.47 | 0.61 |

What raises the risk, in a flavor-5 run like our run 5 (sd floor 0.3, bounds [1, 5], initial sd 0.6):
- **A large $\sigma_\lambda/\bar\lambda$.** At $\bar\lambda = \lambda^0$ and $\gamma = 1$, the outlier check rules it out below $\sigma_\lambda/\bar\lambda$ = 0.38–0.48 at $\bar\lambda = 1$, 0.47–0.53 at 2 and 0.54–0.57 at 5 ($\rho$ from 0 to 0.2; section 4 (c)). It is reachable at the initial (1, 0.6), and more easily where flavor 5's sd has **grown** (inflation note Sec. 5.4, 7.3; run 5: the sd grows at 16–17 % of the points each cycle). Persistently large innovations both grow the sd and make the wrong root likelier.
- **$\bar\lambda$ below $\lambda^0$.** During a cycle, earlier observations can lower $\lambda_k$ from the applied $\lambda^0$ (down to the lower bound 1), while $\sigma_y^2$ and $\sigma_p^2$ stay those of $\lambda^0$. A later large innovation then has a larger $r$. With $\lambda^0 = 2$ or 3 and $\bar\lambda = 1$, it is reachable even at the sd floor 0.3.
- **Observations with a small error against the prior spread** (small $\rho$): radar reflectivity where the reflectivity spread is large, as in missed or misplaced cells.
- **$\gamma$ near 1:** the observed column's REFL_10CM and hydrometeors, where the 5-member correlation with H(x) is high.

### 3.3 What DART does then

- **The step goes the wrong way:** $\lambda_u = \bar\lambda + \delta_- \in (0, \bar\lambda)$, since (5) holds for any $q < \bar\lambda$ and in the region $q < 2c\bar\lambda < \bar\lambda$. So $\lambda$ goes down after an innovation that asks for more.
  - **At $\bar\lambda = 1$** the lower bound clips it back to 1, and the observation's push is lost.
  - **At $\bar\lambda > 1$** $\lambda$ really drops. For example, at $\bar\lambda = 2$, $\sigma_\lambda = 1.2$ and an outlier ratio of 9, DART gives 1.27 where the exact mode is 3.05 (Sec. 4.3).
- **The sd is kept.** The exact posterior rises from the wrong root toward its mode, so the sd fit gives $\alpha_u \le 2$, and `bayes_cov_inflate` keeps the old sd (877 of the 921 wrong-root cases of the sweep; the other 44 have the sd at its floor).
- **A run of such observations never moves $\lambda$** (`flavor5_root_checks.py` section 6). With the same observation at outlier ratio 8 ($\sigma_p^2 = 1$, $\sigma_o^2 = 0.2$, $\gamma = 1$), starting at (1, 0.6):

| | n = 1 | 2 | 5 | 10 | 20 | 40 |
|---|---|---|---|---|---|---|
| flavor 5, DART | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| flavor 5, patched ¹ | 1.390 | 1.725 | 2.414 | 3.172 | 4.154 | 5.000 |
| flavor 2 ² | 1.453 | 1.800 | 2.479 | 3.133 | 3.901 | 4.781 |

¹ sd floor 0.3; the sd grows to 0.81 by n = 40. With floor 0.6: 3.087 at n = 10, 4.788 at n = 40. ² sd floor 0.6 (run 5's flavor-2 setting).

With DART's rule, $\lambda$ stays at 1 and $r$ stays above the threshold, so every one of these observations is lost. With the right root, $\lambda$ rises, $\bar\theta^2$ grows, $r$ falls below the threshold, and the later updates are ordinary ones.

---

## 4. The fix

### 4.1 The patch

`patches/dart_7bbd35a09_flavor5_root_choice.patch` replaces the root choice in `enh_linear_bayes` (`:1176–1181`):

```fortran
if(like_ratio > 0.0_r8) then
   new_cov_inflate = max(plus_root, minus_root)
else
   new_cov_inflate = min(plus_root, minus_root)
endif
```

The final guard ($\lambda_u \le 0$ or NaN keeps $\bar\lambda$) stays; by Sec. 2.3 it can now only catch a NaN.

**Why compare the two roots and not $\lambda_u - \bar\lambda$ with $q$.** `solve_quadratic`'s two roots are not ordered (`plus_root` is the one of larger magnitude). The two roots differ by at least $\lvert q\rvert$ (Sec. 2.1), so `max`/`min` picks the right one even when the near root's step is below round-off. A sign test on $\lambda_u - \bar\lambda$ would fail there: in float32 with $q \sim 10^8$, the step ($\sim 10^{-10}$) rounds to 0 or to an ulp or two on either side of $\bar\lambda$.

**What doesn't change:**
- **Outside $0 < q < 2c\bar\lambda$** the closest root *is* the root on the side of $q$ (Sec. 2.4), and the patch picks the same one of the same two computed numbers. So the result is bit-identical to DART's.
- **Flavor 2** (`linear_bayes`) and the sd update are untouched. With `inf_flavor = 2`, filter's results can't change.
- **The early exits** (likelihood or its slope 0 or below `TINY`) come before the root choice and are unchanged.

### 4.2 Checks

**Python sweep** (`flavor5_root_checks.py` section 3):
- **Grid:** $\gamma \in$ {0.05, 0.2, 0.5, 0.8, 1}; $\bar\lambda \in$ {1, 1.5, 2, 3, 5}; $\sigma_\lambda \in$ {0.3, 0.6, 1.0, 1.5}; $\rho \in$ {0.02, 0.05, 0.1, 0.2, 0.5, 1, 2}; $r \in$ 18 values from 0 to 50; $\sigma_p^2 = 1$, $N = 5$. That is 12,600 cases.
- **Exact posterior mode:** the IG prior times the exact likelihood (inflation note (6), (8)), maximized on a refined grid.

Results:
- 921 cases are in the wrong-root region. DART and the patched rule differ in exactly these, and in no other case.
- In all 921, DART's root is below $\bar\lambda$, the patched root is above it, and the patched root is closer to the exact mode.
- The patched step has the sign of $q$ in all 12,600 cases, and so does the exact mode.
- **The exact posterior is unimodal** in all cases but one.
  - **The exception** is $\gamma = 0.2$, $\sigma_\lambda = 1.5$, $\rho = 2$, $r = 50$, a second maximum at $\lambda \approx 68$. That case can't pass the outlier check.
  - **A spurious second maximum** shows up in about 4,000 cases, but it is an artefact of DART's $\theta^2$: it drops the $-1/N$ term where $s^2 < 1/N$, so $\theta^2$ jumps there. It never is the global maximum.

**DART's Fortran, original against patched** (`flavor5_root_fortran_check.sh`):
- **Grid:** the sweep above, widened to $\gamma \in$ {0.001, …, 0.99, 1}, $\sigma_\lambda$ up to 3, $\rho$ down to 0.001, $\sigma_p^2 \in$ {0.25, 1, 100}, and $r$ from 0 to $10^5$ (including $1 \pm 10^{-5}$). That is 100,800 cases.

| | float32 (ours) | float64 |
|---|---|---|
| stopped by the early exits ¹ | 12,600 | 8,400 |
| in the wrong-root region | 9,924 | 13,455 |
| DART ≠ patched | 9,924 | 13,455 |
| … outside the region | 0 | 0 |
| patched step against $q$ | 0 | 0 |
| patched NaN | 0 | 0 |
| within 2 ulp below $\bar\lambda$ ² | 413 | 0 |

¹ like_bar underflows at large $r$, or like_prime is 0 at $r = 1$. More cases in float32. ² $\gamma = 0.001$, $r \approx 1$: the true step is $\sim 10^{-10}$ and the near root itself rounds to just below $\bar\lambda$. DART gives the same number there.

**One update, the inflation note's cases** ($\sigma_p^2 = 1$, $\sigma_o^2 = 0.2$, $\gamma = 1$, $N = 5$; ratio = $d^2/(\sigma_y^2+\sigma_o^2)$ at $\lambda^0 = \bar\lambda$). DART's root before the bounds clip it. The Fortran gives the same values to 4 decimals in both precisions; exact mode and flavor 2 are from the Python.

| $\bar\lambda$, $\sigma_\lambda$, ratio | DART | patched | exact mode | flavor 2 |
|---|---|---|---|---|
| 1, 0.6, 4 | 1.2532 | 1.2532 | 1.225 | 1.3211 |
| 1, 0.6, 6 | 1.3406 | 1.3406 | 1.367 | 1.4062 |
| 1, 0.6, 8 | **0.6315** | 1.3901 | 1.508 | 1.4526 |
| 1, 0.6, 9 | **0.6469** | 1.4072 | 1.579 | 1.4685 |
| 1, 0.6, 12 | **0.6748** | 1.4420 | 1.792 | 1.5007 |
| 2, 1.2, 8 | 2.7526 | 2.7526 | 2.922 | 2.9262 |
| 2, 1.2, 9 | **1.2716** | 2.7894 | 3.052 | 2.9561 |

### 4.3 What stays: the linearization

The patched root is the mode of G18's **linearized** posterior. For a steep likelihood that mode falls short of the exact one. The step $(\lambda_u - \bar\lambda)/(\lambda_{\rm exact} - \bar\lambda)$ over the sweep:

| cases | n | min | 10 % | median | max |
|---|---|---|---|---|---|
| wrong-root region | 921 | 0.015 | 0.13 | 0.33 | 1.34 |
| … passing the outlier check ³ | 72 | 0.78 | 0.81 | 0.83 | 1.34 |
| $q > 0$, outside the region | 6,115 | 0.007 | 0.71 | 1.00 | 1.59 |

³ At $\lambda^0 = \bar\lambda$.

- **Where observations actually reach:** the patched root takes about 80 % of the exact step there. The very short steps come from innovations that the outlier check rejects.
- **This error is the method's, not the root choice's.** Flavor 2 linearizes the same way (inflation note Sec. 7.1).
- **The sd update after a patched step:** of the 921 cases, 806 keep the sd ($\alpha_u \le 2$, the exact posterior still rising beyond the new mode), 44 have it at the floor, 68 reject a growth above 5 %, and 3 update it. So the patch changes $\lambda$, and hardly ever $\sigma_\lambda$.

---

## 5. How often it matters in our runs (not yet measured)

- **What we have.** Run 5 (`notes/obs_expansion.md` Sec. 9) counted **candidate observations**: radar observations with DART QC 0, $\rho \le 0.2$ and outlier ratio > 7. That gave 19 / 32 / 55 at 00:30 / 00:45 / 01:00 in `_conv_refl_f5` (0.04–0.11 % of the radar observations).
- **Why that count isn't the answer.** It assumes $\sigma_\lambda = 0.6$ and $\bar\lambda = \lambda^0$, and it counts observations, not (observation, element) updates. By Sec. 3.2 it misses points where the sd has grown or where $\lambda_k$ dropped below $\lambda^0$ during the cycle. It also overcounts, since many elements an observation reaches have $\gamma$ well below 1.
- **How to measure it: replay run 5's filter steps with the patched filter.** Every input of each cycle is still on disk in `output_conv_refl_f5/<t>/`: the members' `prior_d01.nc`, `filter/input_priorinf_{mean,sd}.nc`, `filter/input.nml` and `filter/obs_seq.out.path`. Running the patched filter on them gives three things:
  - **Where and how much.** In the inflation update an element's $\lambda$ never feeds back into the state or into other elements' updates, so the elements whose `postassim_priorinf_mean` differs from the original are exactly those with at least one wrong-root update in that cycle. The difference says how much.
  - **A test of the build.** The state analysis (`postassim_mean`, members) must be bit-identical to the original.
  - **Cost:** about 4 min per cycle on 40 nodes, so about 20 min for 00:15–01:00.

  The replay measures each cycle against the original's inflation input, not the effect accumulated over cycles; that needs a full patched rerun of the hour.

---

## 6. Upstream

- **Not fixed upstream.** DART `main` on GitHub is `7bbd35a09` (checked 2026-10-27 with `git ls-remote`), and its `adaptive_inflate_mod.f90` is ours.
- **DART_LAB has the same rule.** Its MATLAB `guide/DART_LAB/matlab/private/update_inflate.m` keeps the root closest to $\bar\lambda$ for the IG prior too.
- **No issue mentions it.** A GitHub issue search of NCAR/DART for `enh_linear_bayes`, "inflation root", "inflation quadratic" and "flavor 5 inflation" found nothing on it. Issue #116 added the enhanced inflation to DART_LAB.
- **A report upstream** (an issue, possibly with the patch as a PR) is possible. It is an outward-facing step and is the user's call.
