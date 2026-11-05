# Adaptive prior inflation in DART, flavors 2 and 5: the math and the code

Written 2026-10-23 for the run-5 comparison (flavor 2 against flavor 5).

**Sources.**
- **Code:** DART `7bbd35a09` (`../software/DART/assimilation_code/modules/assimilation/`): `filter_mod.f90`, `assim_tools_mod.f90`, `adaptive_inflate_mod.f90`. Line numbers below refer to these files.
- **Flavor 5:** El Gharamti (2018), "Enhanced adaptive inflation algorithm for ensemble filters", MWR 146, 623–640 (**G18** below; PDF in `notes/papers/`). Equation numbers "G18 (n)" are the paper's.
- **Flavor 2:** Anderson (2009), "Spatially and temporally varying adaptive covariance inflation for ensemble filters", Tellus 61A, 72–83 (**A09**; PDF in `notes/papers/`). Equation numbers "A09 (n)" are the paper's. Its predecessor, Anderson (2007a), "An adaptive covariance inflation error correction algorithm for ensemble filters", Tellus 59A, 210–224 (**A07a**, also in `notes/papers/`), has one spatially constant $\lambda$ (flavor 3) and the sd method that A09 reuses. The letters follow A09's reference list; A07b, the hierarchical-filter paper, is cited in `dart_sampling_error_correction.md`.
- **Named only:** the EAKF, Anderson (2001), "An ensemble adjustment Kalman filter for data assimilation", MWR 129, 2884–2903 (**A01**); the Gaspari–Cohn localization, Gaspari and Cohn (1999), "Construction of correlation functions in two and three dimensions", QJRMS 125, 723–757, doi:10.1002/qj.49712555417 (**GC99**; its Eq. (4.10)). Both PDFs are in `notes/papers/`.
- **DART's guide:** `guide/inflation.rst`.
- **Numbers in Sec. 3, 4.2, 5, 7 and 8:** from a line-by-line Python translation of the routines (`notes/checks/inflation_checks.py`), and from DART's routines copied verbatim into a stand-alone module and compiled with our ifort, in both single and double precision (`notes/checks/inflation_fortran_check.sh`); commands in Sec. 7.

**Related notes.**
- `dart_workflow_walkthrough.md` Sec. 2–3 (filter's order of operations, the observation loop).
- `mrms_two_pass_inflation.md` Sec. 2 (what one filter pass does with λ).
- `dart_sampling_error_correction.md` (the sampling-error correction, which shrinks the state update but not the correlation the inflation uses).
- `dart_eakf.md` (the EAKF update that the inflated prior feeds; RTPS as HRRRDAS uses it, Sec. 10–11).
- Discussion-log entries of 2026-10-02, 10-03, 10-15, 10-22, 10-23.

**Typora.** Display equations are `$$` blocks. Inline math (`$...$`) needs *Preferences → Markdown → Inline Math*.

---

## 0. Summary

- **What the two flavors share:**
  - For every state element (one grid point of one variable) DART keeps an inflation pdf described by two numbers in the inflation files: $\lambda$ (the inflation) and $\sigma_\lambda$ (its sd).
  - The pipeline is the same: damp, inflate, compute H(x), then let each observation update ($\lambda$, $\sigma_\lambda$) of every element it reaches.
  - The likelihood has the same structure, and so do the localization weighting and the bounds.
  - **The only thing that differs is the Bayesian update of one ($\lambda$, $\sigma_\lambda$) pair by one observation** (`bayes_cov_inflate`).
- **Flavor 2 (A09):** the prior is Gaussian. The new $\lambda$ is the mode of a posterior whose likelihood is linearized. The sd can only shrink, because the code drops every increase (Sec. 4.2).
- **Flavor 5 (G18):**
  - The prior is inverse-gamma (IG), with the same mode and variance as the Gaussian.
  - The likelihood has a $-1/N$ term, which raises the target by $1/N$ (0.2 for our 5 members).
  - The sd can shrink or grow. A growth larger than 5 % per observation is rejected.
- **Flavor 2 against 5 at our settings:**
  1. At $\bar\lambda = 1$, $\sigma_\lambda = 0.6$, one observation moves flavor-5 $\lambda$ by only about 0.35–0.45 times as much as flavor 2 (small steps). This is because the IG's curvature at its mode is sharper than the Gaussian's (Sec. 5.3).
  2. The $+1/N$ shift.
  3. The sd evolves only when its floor is below its current value.
- **Found while checking the code (Sec. 5.3, 5.4, 8):**
  1. In flavor 5 the rule "take the root closest to $\bar\lambda$" picks the wrong root when the likelihood is very steep. $\lambda$ then goes **down** after a large innovation. This needs a large radar innovation where the ensemble spread is large, while the sd is still near 0.6.
  2. Our DART runs in single precision (`r8 = r4`). Wherever $\sigma_\lambda/\bar\lambda \lesssim 0.22$, flavor 5's sd update overflows, and the sd silently stays where it is.
  3. The code damps $\lambda$, while G18 and part of DART's guide damp $\sqrt\lambda$.

---

## 1. Notation

The same symbol means the same thing throughout the note. Where a paper uses another symbol, the last table gives it. Derivations that the papers write with the observed variable as a state variable ($H$ = identity: $x^t$, $\bar x_b$, …) are written here in observation space, with H(x).

- **A bar** means an ensemble mean on $x$ and $y$ ($\bar x_k$, $\bar y$). On $\lambda$ it means the value before one Bayesian update, the mean (flavor 2) or mode (flavor 5) of the inflation pdf. On $\theta$ and $\theta'$ it means the value at $\bar\lambda$.
- **The element index $k$** is dropped where only one element is meant ($\lambda$, $\sigma_\lambda$, $\lambda^0$), and the observation index $j$ where only one observation is meant.
- **Derivatives** are written with $\partial$ ($L$ and $\theta$ also depend on $d$, $\sigma_p^2$ and $\sigma_o^2$), so that $d$ is always the innovation. A prime is $\partial/\partial\lambda$ ($\theta'$, $L'$, $(\ln L)'$).
- **Symbols used inside one derivation only** ($\Delta$, $\xi_1$, $\xi_2$, $v$, $\mu$, $A$, $W$, $C$, $I$, $M$) are defined where they are used.

**Indices, settings, weights**

| symbol | meaning | in the code |
|---|---|---|
| $k$, $j$ | a state element; an observation | |
| $x_{k,i}$, $\bar x_k$, $x_t$ | member $i$ of element $k$; its ensemble mean; the true state | |
| $N$ | ensemble size (5) | `ens_size`, `grp_size` |
| $\rho$ | damping | `inf_damping` (0.9) |
| $\kappa_{jk}$ | localization (Gaspari–Cohn) × impact-table factor | `final_factor` ¹ |
| $r_{jk}$ | sample correlation of H(x)$_j$ with $x_k$ (current ensembles) | `correl` |
| $\gamma_{jk}$ | $\kappa_{jk}\,\lvert r_{jk}\rvert$ | `gamma_corr` |

**One observation** (index $j$ dropped)

| symbol | meaning | in the code |
|---|---|---|
| $y_o$, $\sigma_o^2$ | observed value, observation-error variance | `obs(1)`, `obs_err_var` |
| $y_i$, $\tilde y_i$ | H(x) of member $i$; its deviation from $\bar y$ | |
| $\bar y$, $\sigma_y^2$ | mean and variance of H(x) over the inflated members, frozen before the cycle's first observation | `orig_obs_prior_mean/var` |
| $\sigma_p^2$ | the H(x) sample variance without this cycle's inflation, Eq. (5) | `r_var` → `sigma_p_2` |
| $d$, $d_i$ | innovation $y_o - \bar y$; member innovation $y_o - y_i$ (Sec. 5.1) | `dist_2` $= d^2$ |
| $\epsilon_o$, $\epsilon_b$ | errors of $y_o$ and $\bar y$: $d = \epsilon_o + \epsilon_b$ (Sec. 3.4) | |
| $\sigma_b^2$ | true error variance of $\bar y$, $\operatorname{Var}(\epsilon_b)$ | |
| $E(d^2)$ | the true expected squared innovation, $= \operatorname{Var}(d)$; one $d^2$ is one sample of it | |
| $\theta^2(\lambda)$ | what $\operatorname{Var}(d)$ would be if the inflation were $\lambda$, Eq. (7) or (8) | `theta_2`, `theta` |
| $\bar\theta$, $\bar\theta'$ | $\theta$ and $\partial\theta/\partial\lambda$ at $\bar\lambda$ | `theta_bar`, `dtheta_dlambda` ² |

**Inflation**

| symbol | meaning | in the code |
|---|---|---|
| $\lambda_k$ | inflation of element $k$, a **variance** factor; for flavor 5 the IG **mode** | `PRIOR_INF_COPY`, `*_priorinf_mean.nc` |
| $\sigma_{\lambda,k}$ | sd of the inflation | `PRIOR_INF_SD_COPY`, `*_priorinf_sd.nc` |
| $\lambda^0_k$ | the (damped) $\lambda$ applied this cycle | `ENS_SD_COPY` ³ |
| $\bar\lambda$, $\sigma_\lambda$ | inflation mean (mode) and sd **before** one Bayesian update | `lambda_mean`, `lambda_sd` |
| $\lambda_u$, $\sigma_{\lambda,u}$ | the same **after** it | `new_cov_inflate`, `new_cov_inflate_sd` |
| $\delta$, $\delta_u$ | $\lambda - \bar\lambda$; the step $\lambda_u - \bar\lambda$ | |
| $s(\lambda)^2$ | the observation's variance factor implied by $\lambda_k$, Eq. (4) | |
| $\lambda_o$ | the observation's variance factor that the innovations call for, $\sigma_b^2 = \lambda_o\sigma_p^2$, Eq. (3) | |
| $\hat\lambda_o$, $\lambda_o^*$ | Eq. (3) with one $d^2$; G18's $\lambda_o + 1/N$ (Sec. 5.1) | |
| $\lambda_{\rm true}$ | in toys, an element's true inflation: $d \sim N(0, \theta^2(\lambda_{\rm true}))$ ⁴ | |

**Likelihood, posterior, flavor 5**

| symbol | meaning | in the code |
|---|---|---|
| $L(\lambda)$ | likelihood of $\lambda$ given $d$, Eq. (6) | |
| $\ell$, $\ell'$ | $L$ and $\partial L/\partial\lambda$ at $\bar\lambda$ | `like_bar`, `like_prime` |
| $q$ | $\ell/\ell'$ | `like_ratio` |
| $R$ | posterior at $\lambda_u + \sigma_\lambda$ over posterior at $\lambda_u$ (Sec. 4.2, 5.4) | `ratio` |
| $\alpha$, $\beta$ | IG shape and rate | `shape_old/new`, `rate`, `rate_new` |
| $m$, $\tau^2$ | $\alpha + 1 = \beta/\bar\lambda$; the IG's curvature variance $\bar\lambda^2/(\alpha+1)$ (Sec. 5.2–5.3) | |
| $\omega$ | $\ln R/\beta_u$ in the flavor-5 sd update, Eq. (21) | `omega` |

¹ `reg_factor` inside `update_varying_state_space_inflation`. ² `deriv_theta` in flavor 5. ³ Inside `filter_assim` ("`ss_inflate_base`"). ⁴ With $\gamma = 1$ this is the same as drawing $d$ with $\lambda_o = \lambda_{\rm true}$; Sec. 7.3–7.4 draw with $\lambda_o$.

**The papers' symbols for the same things**

| paper | there | here |
|---|---|---|
| A07a, A09 | $\bar y_p$, $y^o$, $D$ | $\bar y$, $y_o$, $\lvert d\rvert$ |
| A07a, A09 | $y_{p,n}$ (A07a $y_{p,k}$), $h$ | $y_i$, $H$ |
| A07a, A09 | $\bar\lambda_p$, $\sigma^2_{\lambda,p}$; $\bar\lambda_u$, $\sigma^2_{\lambda,u}$ | $\bar\lambda$, $\sigma_\lambda^2$; $\lambda_u$, $\sigma^2_{\lambda,u}$ |
| A09 | $\lambda^o$ | $s(\lambda)^2$ |
| A09 | $\alpha$ in $\gamma = \alpha r$ | $\kappa$ |
| G18 | $\lambda_b$, $\sigma^2_{\lambda_b}$ | $\bar\lambda$, $\sigma_\lambda^2$ |
| G18 | $\lambda^k_o$ | $s(\lambda)^2$ |
| G18 | $x^t$, $\bar x_b$, $x^k_i$, $\tilde x_i$ | $H(x_t)$, $\bar y$, $y_i$, $\tilde y_i$ |
| G18 | $\widehat{\sigma_b}^2$ | $\sigma_p^2$ |
| G18 | $y$, $N_e$ | $y_o$, $N$ |

---

## 2. Where inflation sits in one filter run

The steps that touch $\lambda$, in order. Section 2 of `dart_workflow_walkthrough.md` has the full list.

1. **Read** $\lambda_k$ and $\sigma_{\lambda,k}$ for every state element from `input_priorinf_mean.nc` and `input_priorinf_sd.nc`. For the first analysis these come from `fill_inflation_restart` (1.0 and 0.6); after that, from the previous cycle's `postassim_priorinf_*`.
2. **Damp** (`filter_mod.f90:824–827`), the mean only; the sd is not damped:

   $$
   \lambda_k \leftarrow 1 + \rho\,(\lambda_k - 1) \tag{1}
   $$

3. **Inflate** every state element, `UPDATE` or `NO_COPY_BACK` (`filter_ensemble_inflate`, `filter_mod.f90:1563–1638` → `inflate_ens`, `adaptive_inflate_mod.f90:555–560`):

   $$
   x_{k,i} \leftarrow \bar x_k + \sqrt{\lambda_k}\,\big(x_{k,i} - \bar x_k\big),\qquad i = 1..N \tag{2}
   $$

   - The ensemble mean is unchanged, and the sample variance is multiplied by $\lambda_k$.
   - The code writes this as `ens*sqrt(λ) + mean*(1-sqrt(λ))` so that $\lambda = 1$ leaves the values bit-identical.
   - It runs in "probit space", but with no QCEFF table every quantity is `NORMAL_DISTRIBUTION`, and the transform is the identity (`probit_transform_mod.f90:103–105`).
4. **H(x)** for every observation, computed from the **inflated** members. The preassim stage is then written, and `preassim_priorinf_mean` is the damped $\lambda$ that was applied.
5. **`filter_assim` starts:**
   - It copies $\lambda_k$ into the sd copy (`assim_tools_mod.f90:458`). This is $\lambda^0_k$, the value applied this cycle, which stays fixed while $\lambda_k$ evolves.
   - It computes and **freezes** $\bar y_j$ and $\sigma^2_{y,j}$ for every observation, before any is assimilated (`:524–531`).
6. **For each observation $j$, in sequence:** first the EAKF observation-space increment. Then, for each state element $k$ within the localization radius:
   - **Weight:** $\kappa_{jk}$ = Gaspari–Cohn × impact factor (`cov_and_impact_factors`, `:784`, `:2065–2100`). If $\kappa_{jk} \le 0$, element $k$ is skipped: **neither its value nor its $\lambda$ is updated** (`:787`).
   - **State update** (`obs_updates_ens`, `:789–793`). On the way, `update_from_obs_inc` computes $r_{jk}$ from the current H(x)$_j$ and $x_k$ ensembles (`:1503–1530`). This is **before** the sampling-error correction (`:1534`), so the inflation sees the raw sample correlation.
   - **Inflation update** of ($\lambda_k$, $\sigma_{\lambda,k}$) (`update_varying_state_space_inflation`, `:796–805`), Sec. 3–5.
7. **Postassim stage:** `postassim_priorinf_mean/sd` hold the updated ($\lambda_k$, $\sigma_{\lambda,k}$). They are the next cycle's input.

Over cycles $t$, for one element $k$ reached by observations $j_1, \dots, j_M$:

$$
\begin{aligned}
\lambda^{0,(t)}_k &= 1 + \rho\,\big(\lambda^{(t-1)}_k - 1\big)\\
x_{k,i} &\leftarrow \bar x_k + \sqrt{\lambda^{0,(t)}_k}\,\big(x_{k,i}-\bar x_k\big)\\
\big(\lambda^{(t)}_k,\ \sigma^{(t)}_{\lambda,k}\big) &= \mathcal U_{j_M}\circ\cdots\circ\mathcal U_{j_1}\big(\lambda^{0,(t)}_k,\ \sigma^{(t-1)}_{\lambda,k}\big)
\end{aligned} \notag
$$

The three lines are the damping, the inflation, and one Bayesian update $\mathcal U_j$ per observation.

Consequences:
- **Unobserved elements.** Where no observation reaches $k$ (outside every localization radius, impact 0, or no spread so that $r = 0$), $\lambda$ is only damped. Its excess $\lambda - 1$ decays as $\rho^n$: an e-folding time of $-1/\ln\rho \approx 9.5$ cycles $\approx 2.4$ h for $\rho = 0.9$ at 15 min.
- **Damped prior.** This cycle's Bayesian updates start from the **damped** $\lambda$, and the sd carries over undamped.
- **Damping is the only model of how $\lambda$ evolves between cycles.** A09 took the prior at one time to be the posterior at the previous one, and named damping toward 1 as the simplest fix for inflation left behind where observations disappear (A09 Sec. 5). G18 lists the missing forecast model for the inflation among its limitations.
- **Every observation is evidence against the original prior.** Each one is compared with the prior as it was before any observation of the cycle ($\bar y_j$, $\sigma^2_{y,j}$ frozen in step 5), so each innovation counts as independent evidence about $\lambda$, even though the state itself is updated sequentially.

---

## 3. The likelihood (both flavors)

### 3.1 Innovation statistics (G18 Sec. 2a)

For one observation $y_o$ of a quantity whose true value is $H(x_t)$, let the prior H(x) ensemble have mean $\bar y$ and sample variance $\sigma_p^2$ (no inflation applied). Then $d = y_o - \bar y = \epsilon_o + \epsilon_b$, with $\epsilon_o$ the observation error and $\epsilon_b$ the error of $\bar y$ (Sec. 3.4, Step 1). If the two errors are uncorrelated,

$$
E(d^2) = \sigma_o^2 + \sigma_b^2 , \notag
$$

where $\sigma_b^2$ is the true error variance of $\bar y$. If it is a multiple of the ensemble's variance, $\sigma_b^2 = \lambda_o\,\sigma_p^2$ (multiplicative inflation), then

$$
\lambda_o = \frac{E(d^2) - \sigma_o^2}{\sigma_p^2}. \tag{3}
$$

This is G18 (8), written there with $\widehat{\sigma_b}^2$ for $\sigma_p^2$. With a single $d$ in place of $E(d^2)$, Eq. (3) is very noisy and can be negative. The Bayesian scheme therefore treats $\lambda$ as a random variable and lets each $d$ nudge its pdf.

### 3.2 From the observation to a state element: $\gamma$ (A09 (9)–(10); G18 (13)–(14))

Observation $j$ is generally not state element $k$. A09 assumes that inflating element $k$ alone by $\lambda_k$ multiplies the **sd** of the observation's prior by a factor that, through $\gamma$, interpolates linearly between 1 (no relation, $\gamma = 0$) and $\sqrt{\lambda_k}$ (the observation is element $k$, $\gamma = 1$):

$$
s(\lambda) = 1 + \gamma\,(\sqrt{\lambda} - 1),\qquad \gamma = \kappa\,\lvert r\rvert,\qquad 0\le\gamma\le 1 . \tag{4}
$$

The observation-space variance factor is then $s(\lambda)^2$; G18 calls it $\lambda_o^k$.

- **Where $\gamma$ comes from:** $\kappa$ is the localization × impact factor and $r$ the sample correlation (step 6 above). With zero spread, $r = 0$, so nothing happens.
- **With 5 members, $\lvert r\rvert$ is large even for unrelated variables.** For two independent variables the sample correlation has density $\propto (1-r^2)^{(N-4)/2}$, so $E\lvert r\rvert = 4/(3\pi) = 0.42$ for $N = 5$ (90th percentile 0.81). For $N = 50$ it's 0.11 (checked by simulation).
- **A09 writes $\gamma = \alpha r$ with the signed $r$.** A09's $\alpha$ (localization × hierarchical-filter factor) is our $\kappa$, not the IG shape. The code (`:729`) and G18 use $\lvert r\rvert$, which keeps $s(\lambda) \ge 1$ for $\lambda \ge 1$ whatever the sign of the correlation.
- **So with 5 members, inflation adapts noisily across the whole localization volume.** Only the Gaspari–Cohn taper limits it, and the sampling-error correction, which shrinks the state update, doesn't reach the inflation (the correlation is taken before it, step 6).

### 3.3 What the code puts in (`update_varying_state_space_inflation`, `adaptive_inflate_mod.f90:707–756`)

Here $\sigma^2_y$ is the H(x) variance of the **already inflated** ensemble. The code removes this cycle's inflation as seen from element $k$ (`:732–737`, "Remove the impact of inflation to allow efficient single pass"):

$$
\sigma_p^2 = \frac{\sigma_y^2}{\big[1+\gamma(\sqrt{\lambda^0_k}-1)\big]^2},\qquad d = y_o - \bar y . \tag{5}
$$

- **This is A09's "second algorithm"** (A09 Sec. 3, step 5b(iii)): forward operators once, after inflating; then, for each observation–element pair, the saved observation variance divided by the r.h.s. of A09 (10). A09 notes that for linear forward operators and Gaussian priors without sampling error it is equivalent to the first algorithm, which recomputes H(x) after inflating.
- **The posterior-inflation branch** (`inflate_only`, `:740–745`) also removes the observation's own impact; prior inflation doesn't use it.
- **$\lambda^0_k$ stands in for the forward operator's whole support.** It is the applied $\lambda$ of the element being updated, whereas $\sigma_y^2$ actually depends on the $\lambda$ of all state elements the forward operator touches.

### 3.4 The likelihood (A07a (5.6)–(5.8); A09 (7)–(11))

For one observation, the inflation sees one number: the innovation $d = y_o - \bar y$. The likelihood of $\lambda$ is the pdf of $d$ if the inflation were $\lambda$, read as a function of $\lambda$ at the observed $d$. A07a derives it for one global $\lambda$ ($\gamma = 1$), A09 for $\lambda_k$ with $\gamma \le 1$.

**Step 1: split $d$ into errors.** With $x_t$ the truth, $\epsilon_o$ the observation error and $\epsilon_b$ the error of the prior mean $\bar y$:

$$
\begin{aligned}
y_o &= H(x_t) + \epsilon_o,\\
\bar y &= H(x_t) - \epsilon_b,\\
d &= y_o - \bar y = \epsilon_o + \epsilon_b .
\end{aligned} \notag
$$

**Step 2: the assumptions.**
- **(a)** $\epsilon_o \sim N(0, \sigma_o^2)$, and the $\sigma_o^2$ given to filter is right.
- **(b)** $\epsilon_b \sim N(0, \sigma_b^2)$: the prior mean is unbiased and its error Gaussian.
- **(c)** $\epsilon_o$ and $\epsilon_b$ are independent.
- **(d) This is where $\lambda$ comes in.** If $\lambda$ is the right inflation for element $k$, then the observation's prior variance becomes right when multiplied by $s(\lambda)^2$ of Eq. (4): $\sigma_b^2 = s(\lambda)^2\,\sigma_p^2$. For $\gamma = 1$ this is $\sigma_b^2 = \lambda\,\sigma_p^2$ (A07a (5.7)); A09 (8)–(10) add $\gamma$.
- **(e)** $\bar y$ and $\sigma_p^2$ are known numbers: the likelihood conditions on the prior ensemble, and only the truth and the observation error are random. With 5 members neither number is accurate: $\sigma_p^2$ is a sample variance with 4 degrees of freedom, and $\bar y$ a 5-member average.

**Step 3: mean and variance of $d$.** By (a) and (b) the means are zero; by (c) the covariance term vanishes; (d) gives $\sigma_b^2$:

$$
\begin{aligned}
E(d) &= E(\epsilon_o) + E(\epsilon_b) = 0,\\
\operatorname{Var}(d) &= \sigma_o^2 + \sigma_b^2 + 2\operatorname{Cov}(\epsilon_o, \epsilon_b)\\
&= s(\lambda)^2\,\sigma_p^2 + \sigma_o^2 \;\equiv\; \theta^2(\lambda) .
\end{aligned} \notag
$$

**Step 4: the density.** A sum of independent Gaussians is Gaussian, so $d \sim N(0, \theta^2(\lambda))$, and its density at the observed $d$ is the likelihood:

$$
L(\lambda) = p(d\mid\lambda) = \frac{1}{\sqrt{2\pi}\,\theta(\lambda)}\exp\!\Big(-\frac{d^2}{2\theta^2(\lambda)}\Big),\tag{6}
$$

$$
\text{flavor 2:}\quad \theta^2(\lambda) = s(\lambda)^2\,\sigma_p^2 + \sigma_o^2, \tag{7}
$$

$$
\text{flavor 5:}\quad \theta^2(\lambda) = \Big(s(\lambda)^2 - \frac{1}{N}\Big)\sigma_p^2 + \sigma_o^2 . \tag{8}
$$

- **Where these come from:** (7) is Step 3's variance: A09 (8) with (10), and A09 (11) is (6). (8) is G18 (26); it changes assumption (d) (Sec. 5.1). In (8) the code drops the $1/N$ term when $s(\lambda)^2 < 1/N$.
- **In the code:** `compute_new_density` (`:995–1003` evaluates (6) with (7), times the Gaussian prior) and `linear_bayes` for flavor 2; `enh_compute_new_density` and `enh_linear_bayes` for flavor 5 (`:1028–1032`, `:1135–1140`).
- **Sign:** A09 writes $D = \lvert\bar y - y_o\rvert$. Only $d^2$ enters, so the sign of the innovation doesn't matter.
- **A09's wording is loose:** it calls $\theta$ "the expected value of the distance" between $\bar y$ and $y_o$, but $\theta$ is the rms of $d$, the sd of its normal. The expected distance is $E\lvert d\rvert = \theta\sqrt{2/\pi} \approx 0.8\,\theta$. A09 also writes "Normal (0, θ)" with $\theta$ as the sd.

**The shape of $L$ in $\lambda$.** $\lambda$ enters only through $\theta^2$:

$$
\begin{aligned}
\ln L &= -\tfrac12\ln(2\pi) - \tfrac12\ln\theta^2 - \frac{d^2}{2\theta^2},\\
\frac{\partial\ln L}{\partial\theta^2} &= \frac{d^2 - \theta^2}{2\,\theta^4} .
\end{aligned} \notag
$$

- **Maximum at $\theta^2 = d^2$.** For $\gamma = 1$ that is $\hat\lambda_o = (d^2 - \sigma_o^2)/\sigma_p^2$, Eq. (3) with the single $d^2$ in place of $E(d^2)$. So (6) is the likelihood whose one-observation maximum is Eq. (3). If $d^2 < \sigma_o^2$, no $\lambda$ reaches $\theta^2 = d^2$, and $L$ is largest at the smallest $\lambda$ allowed.
- **Two factors pull against each other.** The exponential rises with $\theta$ toward 1; the prefactor $1/\theta$ falls. Without the prefactor, $L$ would rise with $\lambda$ for ever.
- **A long right tail.** For large $\lambda$, $\theta^2 \approx \gamma^2\lambda\,\sigma_p^2$, so $L$ falls only as $\lambda^{-1/2}$, and $\int L\,d\lambda$ diverges. The prior is what keeps the posterior's right tail finite.

Further properties:

- **Same QC denominator.** By Eq. (5), $\theta^2(\lambda^0) = \sigma_y^2 + \sigma_o^2$ in flavor 2 for every element, whatever $\gamma$. This is the denominator of the outlier check. With `outlier_threshold = 3`, every assimilated observation therefore has $d^2 \le 9\,\theta^2(\lambda^0)$ at the start of the cycle's updates.
- **$L$ is not Gaussian in $\lambda$.** That is why both flavors linearize it.

### 3.5 Linearizing the likelihood around $\bar\lambda$

Write $\theta' = \partial\theta/\partial\lambda = (\partial\theta^2/\partial\lambda)/(2\theta)$. The $-\sigma_p^2/N$ term of (8) is a constant, so $\partial\theta^2/\partial\lambda$ is the same in both flavors, and so is the formula for $\theta'$; each flavor puts in its own $\theta$, from (7) or (8):

$$
\begin{aligned}
\frac{\partial\theta}{\partial\lambda} &= \frac{\gamma\,(1-\gamma+\gamma\sqrt{\lambda})\,\sigma_p^2}{2\,\theta\,\sqrt{\lambda}},\\
\frac{\partial L}{\partial\lambda} &= L\,\frac{\theta'}{\theta}\Big(\frac{d^2}{\theta^2}-1\Big).
\end{aligned} \tag{9}
$$

This is A09 (A.3), (A.6), and in the code `dtheta_dlambda` (`:1092`) and `deriv_theta` (`:1154`).

On $\theta$, a bar marks the value at $\bar\lambda$, the inflation before this one update (Sec. 1):
- $\bar\theta = \theta(\bar\lambda)$, from (7) in flavor 2 and (8) in flavor 5: the sd of $d$ that the current inflation predicts. In the code `theta_bar`, with `theta_bar_2` $= \bar\theta^2$ (`:1071–1072`, `:1140–1141`).
- $\bar\theta' = \theta'(\bar\lambda)$, Eq. (9) at $\bar\lambda$: how fast that sd grows with $\lambda$. In the code `dtheta_dlambda` and `deriv_theta`.

DART writes

$$
\begin{aligned}
L(\lambda) &\approx \ell + \ell'(\lambda-\bar\lambda),\qquad \ell = L(\bar\lambda),\ \ \ell' = L'(\bar\lambda),\\
q &\equiv \frac{\ell}{\ell'} = \frac{\bar\theta}{\bar\theta'}\Big(\frac{d^2}{\bar\theta^2}-1\Big)^{-1}.
\end{aligned} \tag{10}
$$

- **Sign.** If $d^2 > \bar\theta^2$ (innovation larger than the current $\lambda$ predicts), then $\ell' > 0$ and $q > 0$: the evidence says "more inflation". If $d^2 < \bar\theta^2$, it says less.
- **Size.** For $\gamma = 1$, $\bar\theta'/\bar\theta = \sigma_p^2/(2\bar\theta^2)$, so $q = 2\bar\theta^4/\big(\sigma_p^2(d^2-\bar\theta^2)\big)$. A small $\lvert q\rvert$ means a steep likelihood.

---

## 4. Flavor 2: Gaussian prior (A09)

### 4.1 The new mode (`linear_bayes`, `:1060–1116`; A09 (12)–(13), Appendix A)

Why linearize: for $\gamma = 1$ the exact mode solves a cubic (A07a; that solution is still in `bayes_cov_inflate`, commented out, `:789–846`), and for $0 < \gamma < 1$ a sixth-order equation (A09 Sec. 3).

The prior is $p(\lambda) = N(\bar\lambda, \sigma_\lambda^2)$. With the linearized likelihood the posterior is

$$
p(\lambda\mid d) \;\propto\; \exp\!\Big(-\frac{(\lambda-\bar\lambda)^2}{2\sigma_\lambda^2}\Big)\big[\ell + \ell'(\lambda-\bar\lambda)\big]. \tag{11}
$$

The new $\lambda$ is the mode of this posterior, where its $\lambda$-derivative is zero. The right side of (11) is enough, since the normalizing constant doesn't move the mode. With $\delta = \lambda - \bar\lambda$, the product rule gives

$$
\begin{aligned}
&\frac{\partial}{\partial\lambda}\Big[e^{-\delta^2/2\sigma_\lambda^2}\big(\ell+\ell'\delta\big)\Big]\\
&\quad= e^{-\delta^2/2\sigma_\lambda^2}\Big[-\frac{\delta}{\sigma_\lambda^2}\big(\ell+\ell'\delta\big) + \ell'\Big] = 0 .
\end{aligned} \notag
$$

The exponential is positive, so the bracket is zero. Multiply the bracket by $-\sigma_\lambda^2/\ell'$ and use $q = \ell/\ell'$:

$$
\begin{aligned}
&\delta\,(q + \delta) - \sigma_\lambda^2 = 0\\
\Longleftrightarrow\quad &\delta^2 + q\,\delta - \sigma_\lambda^2 = 0 .
\end{aligned} \tag{12}
$$

In $\lambda$ this is A09 (A.8) and the code's quadratic (`:1102–1104`):

$$
\lambda^2 + (q - 2\bar\lambda)\,\lambda + \big(\bar\lambda^2 - \sigma_\lambda^2 - q\,\bar\lambda\big) = 0 . \notag
$$

`solve_quadratic` (`:1197–1222`) solves it in a scaled, cancellation-safe form, and the root **closest to $\bar\lambda$** is kept. For flavor 2 that root is always the right one:
- The roots are $\delta_\pm = \tfrac12\big(-q \pm\sqrt{q^2+4\sigma_\lambda^2}\big)$, with product $-\sigma_\lambda^2 < 0$ and sum $-q$.
- So the root closest to 0 has the sign of $q$, the direction the likelihood slope points.
- The other root lies where the linearized likelihood $\ell + \ell'(\lambda-\bar\lambda)$, and so the posterior (11), is negative, so it is spurious.

The chosen step is

$$
\begin{aligned}
\lambda_u - \bar\lambda &= \frac{2\sigma_\lambda^2}{q + \operatorname{sign}(q)\sqrt{q^2+4\sigma_\lambda^2}}\\
&\Longrightarrow\quad \lvert\lambda_u-\bar\lambda\rvert < \sigma_\lambda ,
\end{aligned} \tag{13}
$$

so **one observation can move $\lambda$ by less than one $\sigma_\lambda$**. For a small step ($\lvert q\rvert \gg \sigma_\lambda$):

$$
\begin{aligned}
\lambda_u - \bar\lambda &\approx \frac{\sigma_\lambda^2}{q} = \sigma_\lambda^2\,(\ln L)'(\bar\lambda)\\
&\overset{\gamma=1}{=} \sigma_\lambda^2\,\frac{\sigma_p^2\,(d^2-\bar\theta^2)}{2\,\bar\theta^4}.
\end{aligned} \tag{14}
$$

So one flavor-2 update is a gradient step on $\ln L$ with step size $\sigma_\lambda^2$. It is proportional to the excess of $d^2$ over $\bar\theta^2$, its expected value at $\bar\lambda$. At $\bar\lambda = 1$ it is also proportional to $\gamma$, since $\bar\theta'/\bar\theta = \gamma\sigma_p^2/(2\bar\theta^2)$ there.

### 4.2 The new sd (`bayes_cov_inflate`, `:848–903`; A09 (14))

The code evaluates the **exact** (not linearized) unnormalized posterior $p(\lambda) \propto e^{-(\lambda-\bar\lambda)^2/2\sigma_\lambda^2} L(\lambda)$ (`compute_new_density`, `:980–1005`) at the new mode and one **old** sd above it, then fits a Gaussian through the two values:

$$
\begin{aligned}
R &= \frac{p(\lambda_u+\sigma_\lambda)}{p(\lambda_u)} = \exp\!\Big(-\frac{\sigma_\lambda^2}{2\sigma_{\lambda,u}^2}\Big)\\
&\Longrightarrow\quad \sigma_{\lambda,u} = \sqrt{\frac{-\sigma_\lambda^2}{2\ln R}} .
\end{aligned} \tag{15}
$$

If the likelihood is flat, $\ln R = -\tfrac12$ and the sd is unchanged. Otherwise the fit narrows or widens with the sign of the log-likelihood's curvature (below). The code keeps the old $\sigma_\lambda$ in these cases:
- $\sigma_\lambda$ is already at `inf_sd_lower_bound` (within `TINY`): an early exit after the mode update (`:862–864`). **With `inf_sd_initial = inf_sd_lower_bound` the sd therefore never changes.**
- Either density is ~0 (`:878–881`).
- $R > 0.99$ (`:886–889`).
- $\sigma_{\lambda,u} > \sigma_\lambda$ (`:898–901`).

**So the flavor-2 sd can only shrink.** Three things together make it so:
1. **Each update lowers the sd or keeps it.** The last guard drops every increase, and the floor (Sec. 4.3) only raises a value that fell below it, back to the floor.
2. **Nothing else touches the sd.** Damping acts on $\lambda$ only (Sec. 2, step 2), and each cycle's posterior sd is the next cycle's prior sd, unchanged.
3. **So over a run, every element's sd is non-increasing,** down to `inf_sd_lower_bound`. In our flavor-2 runs the floor is the initial 0.6, so the ratio is never even computed (first bullet above).

**When the ratio method would raise the sd.** With $\delta_u = \lambda_u - \bar\lambda$, the prior's part of $\ln R$ is exact:

$$
\begin{aligned}
\ln R &= -\frac{(\delta_u+\sigma_\lambda)^2 - \delta_u^2}{2\sigma_\lambda^2} + \Delta\\
&= -\frac12 - \frac{\delta_u}{\sigma_\lambda} + \Delta,\\
\Delta &\equiv \ln L(\lambda_u+\sigma_\lambda) - \ln L(\lambda_u) .
\end{aligned} \notag
$$

By (15), $\sigma_{\lambda,u} > \sigma_\lambda$ exactly when $\ln R > -\tfrac12$:

$$
\sigma_{\lambda,u} > \sigma_\lambda \quad\Longleftrightarrow\quad \Delta > \frac{\delta_u}{\sigma_\lambda} . \notag
$$

- **In words:** the likelihood must still rise from $\lambda_u$ to $\lambda_u + \sigma_\lambda$ by more than the mode step has already taken into account.
- **To leading order in $\sigma_\lambda$:** with $\delta_u \approx \sigma_\lambda^2 (\ln L)'$ (Eq. (14)) and a Taylor expansion of $\Delta$, the first derivatives cancel and

$$
\Delta - \frac{\delta_u}{\sigma_\lambda} \approx \frac{\sigma_\lambda^2}{2}\,\frac{\partial^2\ln L}{\partial\lambda^2} . \notag
$$

So the sd grows where $\ln L$ is **convex** in $\lambda$ and shrinks where it is concave. For $\gamma = 1$, $\theta^2 = \lambda\sigma_p^2 + \sigma_o^2$ is linear in $\lambda$, so the curvature in $\lambda$ has the sign of the curvature in $\theta^2$:

$$
\frac{\partial^2\ln L}{\partial(\theta^2)^2} = \frac{\theta^2 - 2d^2}{2\,\theta^6} . \notag
$$

- **The sd would grow for small innovations,** $d^2 < \bar\theta^2/2$ to leading order. If the innovations match the current $\bar\lambda$ ($d \sim N(0, \bar\theta^2)$), that is $P(\lvert z\rvert < 1/\sqrt2) = 52$ % of the observations.
- **For $\gamma < 1$ even more often:** $s(\lambda)^2$, and with it $\theta^2$, is concave in $\lambda$, which widens the convex range.
- **These increases are not numerical errors,** whatever the code's comment says: they come from every small enough innovation.

Toy (`inflation_checks.py` section 11): $\bar\lambda = 1$, $\sigma_\lambda = 0.6$, 4000 observations with $d \sim N(0, \theta^2(1))$, and the sd ratio $\sigma_{\lambda,u}/\sigma_\lambda$ without the guard. The exact criterion matched every update; $d^2 < \bar\theta^2/2$ matched 98–100 % of them for $\gamma = 1$ and 89–94 % for $\gamma = 0.5$. With $\sigma_\lambda = 0.3$, or innovations drawn with $\lambda_{\rm true} = 2$, the share that would grow is 43–65 %.

| case | $\gamma$ | would grow | ratio, 5 % | ratio, 95 % |
|---|---|---|---|---|
| METAR | 1 | 52 % | 0.989 | 1.0014 |
| METAR | 0.5 | 63 % | 0.994 | 1.0015 |
| radar sd 2 | 1 | 53 % | 0.989 | 1.0014 |
| radar sd 2 | 0.5 | 65 % | 0.994 | 1.0015 |
| radar sd 8 | 1 | 54 % | 0.849 | 1.013 |
| radar sd 8 | 0.5 | 58 % | 0.929 | 1.011 |

So about half the updates would raise the sd, each by little (≤ 0.15 %, or ~1 % for radar sd 8), while the falls are larger (to −1 %, or −15 %). The guard keeps only the falls, a ratchet.

**Why the guard? The papers don't say, and they argue the other way.**
- **A07a Sec. 6, "Avoiding inflation filter divergence":** each observation is expected to lower $\sigma_\lambda^2$ (citing Chui and Chen 1987). Since nothing raises it between times, this "systematic loss of variance for λ could eventually lead to filter divergence": $\lambda$ stops responding to observations. In A07a's Fig. 2 it falls from 0.25 to about 0.06 over 2000 assimilation times (the text calls this the variance, the figure's axis the sd). For most of its results A07a therefore holds $\sigma_\lambda$ fixed (its Eq. (6.1)).
- **A07a Sec. 5 and A09 Sec. 2** call the ratio method naive and say it "is biased to produce slightly larger values of $\sigma^2_{\lambda,u}$ in the mean over many observations. This is a convenient property", because of that divergence. A09 also expects that a model for $\lambda$'s time evolution would let $\sigma_\lambda^2$ grow with time. A09's own Lorenz-96 runs held $\sigma_\lambda$ fixed at 0.1, with little sensitivity between 0.01 and 0.5.
- **G18** names the guard only as an option (Sec. 3d: one can "only accept updates that decrease the inflation variance"), and presents the IG's sd, which can grow, as what prevents the collapse of the inflation pdf (Sec. 3c). Its GCM test (Sec. 4c, "Varying $\sigma_\lambda$") attributes A09's monotonically falling sd to "the Gaussian assumption". In the code it is the guard: without it, about half the Gaussian updates would raise the sd (toy above).
- **DART's guide** says only that the flavor-2 sd "could never increase" and generally shrinks to the lower bound (`inf_sd_lower_bound`, `inf_sd_max_change` entries).
- **The code:** the guard and its comment ("Prevent an increase in the sd of lambda???", "For now, this is mostly countering numerical errors in this computation", `:896–901`) were already in the module's first version (DART commit `ada898619`, J. Anderson, 2006-01-10, before A07a appeared), and are essentially unchanged since.
- **A guess at the reason (not stated anywhere):** in a Kalman filter an observation never increases the variance, and A07a Sec. 6 assumes the same for the $\lambda$ filter. Against that expectation the small increases (≤ 0.15 % per observation for $\gamma = 1$ at our sizes) look like round-off. They aren't: the likelihood isn't Gaussian in $\lambda$, and where its log is convex (small innovations) the posterior is wider than the prior. Even exact Bayesian updating only lowers the variance on average over the possible observations, not for every one.

### 4.3 Bounds (`update_inflation`, `:611–650`)

These apply after **every** single update, for both flavors:
- $\sigma_\lambda \le 0$ means no update (`:624`).
- $\lambda_u$ is clipped to [`inf_lower_bound`, `inf_upper_bound`] (ours: [1, 5]).
- $\sigma_{\lambda,u}$ is floored at `inf_sd_lower_bound`.

---

## 5. Flavor 5: inverse-gamma prior (G18)

The pipeline (Sec. 2, 3.2, 3.3, 4.3) is the same. Three things change: the likelihood's variance (8), the prior's shape, and the sd update. Flavor 5 is flavor 2 with the `GHA2017` sub-flavor (`adaptive_inflate_init`, `:285–287`; `update_inflation`, `:630–634`).

**Why G18 changed the prior** (G18 abstract, Sec. 1, 3b–3d):
1. **Excessive deflation and negative $\lambda$.** A09's likelihood often peaks below 1, sometimes at a negative $\lambda$ (Eq. (3) with one innovation can be negative), and a Gaussian prior puts probability on $\lambda \le 0$. Deflation with A09 performed poorly; G18 Sec. 4c tests A09 with a varying sd only with lower bound 1 for that reason. The usual fix, a lower bound of 1, forbids deflation altogether. The IG keeps $\lambda > 0$ and, together with the $+1/N$ (Sec. 5.1), makes deflation rarer and milder. A09 itself (Sec. 2) had called a Gaussian "with its unbounded tails … probably not the most appropriate choice", and asked for distributions that "formally restrict the inflation to positive values".
2. **Simpler code,** "without lengthy checks on the sign and magnitude of the inflation factor" (G18 Sec. 3b). DART's flavor-5 code still has such checks (Sec. 8 item 6), and its root choice can go wrong (Sec. 5.3).
3. **An sd that can evolve:** "a flexible framework for the inflation variance to evolve" (abstract); the IG posterior's variance "can both increase and decrease … This is empirically shown to prevent collapse in the spread of the inflation pdf" (Sec. 3c). But the ratio method is the same in both flavors, and what keeps the flavor-2 sd from rising is the code's guard, not the Gaussian prior (Sec. 4.2).
4. **Background, not in G18's words:** the IG is the standard conjugate prior for a variance factor. For $d \sim N(0, \lambda\sigma_p^2)$ (no observation error, $\gamma = 1$), an IG prior on $\lambda$ gives an IG posterior. G18 follows Stroud and Bengtsson (2007) here, and mentions Raanes (2016), who proposed the inverse chi-square, a special case of the IG. Here $\sigma_o^2$ and $\gamma < 1$ break the conjugacy, so G18 still linearizes the likelihood.

**How much of point 3 does flavor 2 get without the guard?** Toy (`inflation_checks.py` section 12): one element, radar sd 2, random innovations $d \sim N(0, \theta^2(\lambda_{\rm true}))$, start ($\lambda$, $\sigma_\lambda$) = (1, 0.6), sd floor 0.1, bounds [0.2, 50], mean $\sigma_\lambda$ of 20 runs after 3000 observations:

| $\gamma$ | $\lambda_{\rm true}$ | flavor 2 | flavor 2, no guard | flavor 5 |
|---|---|---|---|---|
| 1 | 1 | 0.16 | 0.18 | 0.15 |
| 1 | 2 | 0.17 | 0.19 | 0.21 |
| 0.3 | 1 | 0.26 | 0.42 | 0.41 |
| 0.3 | 2 | 0.27 | 0.42 | 0.52 |

- **For $\gamma = 1$** all three sds fall about alike.
- **For small $\gamma$** the flavor-2 sd without the guard stays about as high as flavor 5's. So most of the sd behaviour G18 credits to the IG is what the guard takes away from flavor 2.
- **What the IG adds beyond that** is positivity and the skewed shape, and with the skew the smaller steps of Sec. 5.3.
- **For us,** with `inf_lower_bound = 1`, point 1 doesn't apply. What flavor 5 changes then is the $+1/N$, the smaller steps and an sd that can grow, with its defects (Sec. 5.3, 5.4).

### 5.1 The $-1/N$ term (G18 (16)–(26))

G18 builds the innovation statistics from the **member** innovations, not only from the mean innovation $d$. G18 takes the observed variable to be a state variable; here it is written in observation space (symbols in Sec. 1). Each member's H(x) is the mean plus a deviation:

$$
\begin{gathered}
y_o = H(x_t) + \epsilon_o,\qquad \epsilon_b = H(x_t) - \bar y,\\
y_i = \bar y + \tilde y_i,\qquad \sum_i \tilde y_i = 0,\\
\sigma_p^2 = \frac{1}{N-1}\sum_i \tilde y_i^2 .
\end{gathered} \notag
$$

As in Sec. 3.4, $d = y_o - \bar y = \epsilon_o + \epsilon_b$.

**Step 1: member innovations** (G18 (16)–(18)):

$$
\begin{aligned}
d_i = y_o - y_i &= \epsilon_o + H(x_t) - (\bar y + \tilde y_i)\\
&= \epsilon_o + \epsilon_b - \tilde y_i \;=\; d - \tilde y_i .
\end{aligned} \notag
$$

**Step 2: square** (G18 (19)):

$$
\begin{aligned}
d_i^2 &= \epsilon_o^2 + \epsilon_b^2 + 2\epsilon_o\epsilon_b\\
&\quad + \tilde y_i^2 - 2(\epsilon_o + \epsilon_b)\,\tilde y_i .
\end{aligned} \notag
$$

**Step 3: average over the members** (G18 (20)–(22)). $\epsilon_o$ and $\epsilon_b$ are the same for every member, so they come out of the sums. The deviations sum to zero, so the term linear in $\tilde y_i$ drops out, and $\frac1N\sum_i\tilde y_i^2 = \frac{N-1}{N}\sigma_p^2$. This gives, exactly, G18 (22):

$$
\frac1N\sum_i d_i^2 = \epsilon_o^2 + \epsilon_b^2 + \frac{N-1}{N}\sigma_p^2 + 2\epsilon_o\epsilon_b . \notag
$$

**Step 4: G18's approximation** (footnote 2; G18 (23)–(25)). G18 replaces the left side by $E(d^2) + \sigma_p^2$, takes expectations on the right ($E(\epsilon_o^2) = \sigma_o^2$, $E(\epsilon_b^2) = \sigma_b^2$, $E(\epsilon_o\epsilon_b) = 0$), and sets $\sigma_b^2 = \lambda_o^*\sigma_p^2$:

$$
\begin{aligned}
E(d^2) + \sigma_p^2 &= \sigma_o^2 + \lambda_o^*\sigma_p^2 + \frac{N-1}{N}\sigma_p^2\\
\Longrightarrow\quad \lambda_o^* &= \frac{E(d^2)-\sigma_o^2}{\sigma_p^2} + \frac1N = \lambda_o + \frac1N ,
\end{aligned} \notag
$$

which is G18 (25) and leads to Eq. (8).

**The $1/N$ comes only from that approximation.** By Step 1, $d_i = d - \tilde y_i$, so the same averaging gives the left side exactly:

$$
\frac1N\sum_i d_i^2 = d^2 + \frac{N-1}{N}\sigma_p^2 . \notag
$$

- **Without the approximation:** the $\frac{N-1}{N}\sigma_p^2$ terms cancel on the two sides, and the expectation gives back $E(d^2) = \sigma_o^2 + \sigma_b^2$, Eq. (3), with no $1/N$.
- **What footnote 2 does:** it writes the left side as $d^2 + V(d)$, with $V(d)$ the sample variance of the $d_i$, which is $\sigma_p^2$ (denominator $N-1$). The exact value has $\frac{N-1}{N}V(d)$. The footnote calls this omitting the factor $N/(N-1)$, a "biased assumption" that is valid for large $N$.
- **So:** the difference, $\sigma_p^2/N$, is exactly the $1/N$ of (25). The member innovations carry no information beyond $d$ and $\sigma_p^2$. The $1/N$ term is not required by the innovation statistics; G18 keeps it for its effect, fewer negative and deflating estimates (G18 Sec. 3a and 5).

**What it does:** with the same evidence, the likelihood peaks where $s(\lambda)^2 = (d^2-\sigma_o^2)/\sigma_p^2 + 1/N$. **For $\gamma = 1$ the target variance factor is higher by $1/N$**: 0.2 at 5 members, 0.02 at 50. G18 adds that the shift "does not always yield larger posterior inflation values" (Sec. 5) and that it reduces, but doesn't remove, negative and deflating estimates.

### 5.2 The IG prior and its conversion from ($\bar\lambda$, $\sigma_\lambda$) (G18 (27)–(35))

$$
\begin{gathered}
p(\lambda) = \frac{\beta^\alpha}{\Gamma(\alpha)}\,\lambda^{-\alpha-1}e^{-\beta/\lambda},\\
\text{mode} = \frac{\beta}{\alpha+1},\qquad \text{mean} = \frac{\beta}{\alpha-1},\\
\text{var} = \frac{\beta^2}{(\alpha-1)^2(\alpha-2)}\quad (\alpha>2).
\end{gathered} \tag{16}
$$

DART keeps the files Gaussian-looking: it stores $\lambda$ = **mode** and $\sigma_\lambda$ = sd. At every single update it converts them to ($\alpha$, $\beta$), updates, and converts back. So the two flavors' files are interchangeable.

**This is a conversion, not a Bayesian step.** No observation enters. Eq. (17) only finds the IG with the same mode and the same variance as the stored pair ($\bar\lambda$, $\sigma_\lambda$). The posterior mode, with the IG as prior, comes afterwards (Sec. 5.3, Eq. (18)).

**Step 1: match the mode** (G18 (28)). With $m \equiv \alpha + 1$:

$$
\begin{gathered}
\frac{\beta}{\alpha+1} = \bar\lambda \quad\Longrightarrow\quad \beta = \bar\lambda\,m,\\
\alpha - 1 = m - 2,\qquad \alpha - 2 = m - 3 .
\end{gathered} \notag
$$

**Step 2: match the variance** (G18 (29)–(30)), and put in Step 1:

$$
\sigma_\lambda^2 = \frac{\beta^2}{(\alpha-1)^2(\alpha-2)} = \frac{\bar\lambda^2 m^2}{(m-2)^2(m-3)} . \notag
$$

**Step 3: clear the denominator,** expand $(m-2)^2(m-3) = m^3 - 7m^2 + 16m - 12$, and divide by $\sigma_\lambda^2$:

$$
\begin{aligned}
&\sigma_\lambda^2\,(m-2)^2(m-3) = \bar\lambda^2 m^2\\
\Longleftrightarrow\quad &m^3 - \Big(7 + \frac{\bar\lambda^2}{\sigma_\lambda^2}\Big)m^2 + 16\,m - 12 = 0 .
\end{aligned} \tag{17}
$$

**G18 (31) has a misprint.** G18 writes the cubic in $\beta$. Putting $m = \beta/\bar\lambda$ into (17) gives

$$
\frac{\beta^3}{\bar\lambda^3} - \Big(\frac{7}{\bar\lambda^2} + \frac{1}{\sigma_\lambda^2}\Big)\beta^2 + \frac{16}{\bar\lambda}\,\beta - 12 = 0 , \notag
$$

but G18 (31) prints $7/\bar\lambda$ for $7/\bar\lambda^2$. The two agree only at $\bar\lambda = 1$. The code isn't affected: `change_GA_IG` solves the correct cubic (below).

The cubic has one real root (G18 (32): its discriminant is negative). `change_GA_IG` (`:1229–1262`, G18 (33)–(35)) evaluates it in closed form (Cardano), with $v = \sigma_\lambda^2$ and $\mu = \bar\lambda$ ($A$ and $W$ are the code's `AA` and `EE`):

$$
\begin{aligned}
A &= \mu^4\sqrt{\frac{v^2+47v\mu^2+3\mu^4}{v^3}},\\
W &= \frac{21v\mu^7 + 75v^2\mu^5 + v^3\mu^3 + \mu^9 + 6\sqrt3\,A\,v^3}{v^3},\\
\beta &= \frac{7v\mu+\mu^3}{3v} + \frac{W^{1/3}}{3} + \frac{\mu^2\,(v^2+14v\mu^2+\mu^4)}{3v^2W^{1/3}},\\
\alpha &= \frac{\beta}{\bar\lambda}-1 .
\end{aligned} \notag
$$

Checked numerically (`inflation_checks.py` section 1) for every row of the table below, including $\bar\lambda$ = 1.5 and 2: the root satisfies (17) to rounding error (residuals $\le 10^{-11}$ against terms up to $10^6$), and the IG has the requested mode and variance. In the table, $\tau^2 = \bar\lambda^2/(\alpha+1)$ is the IG's curvature variance (Sec. 5.3).

| $\bar\lambda$ | $\sigma_\lambda$ | $\alpha$ | $\beta$ | IG mean | $\tau^2$ | $\tau^2/\sigma_\lambda^2$ |
|---|---|---|---|---|---|---|
| 1.0 | 0.6 | 6.96 | 7.96 | 1.34 | 0.126 | 0.35 |
| 1.0 | 0.3 | 16.2 | 17.2 | 1.13 | 0.058 | 0.65 |
| 1.0 | 0.1 | 105.9 | 106.9 | 1.02 | 0.0094 | 0.94 |
| 1.5 | 0.6 | 11.0 | 18.0 | 1.80 | 0.188 | 0.52 |
| 2.0 | 0.6 | 16.2 | 34.4 | 2.26 | 0.232 | 0.65 |

The IG with mode 1 and sd 0.6 is strongly right-skewed: its mean is 1.34. It approaches a Gaussian as $\sigma_\lambda/\bar\lambda \to 0$.

### 5.3 The new mode (`enh_linear_bayes`, `:1122–1191`; G18 (36)–(38))

The posterior is G18 (36):

$$
p(\lambda\mid d)\propto \lambda^{-\alpha-1}e^{-\beta/\lambda}\,\big[\ell+\ell'(\lambda-\bar\lambda)\big]. \notag
$$

The new $\lambda$ is the mode of this posterior. It is easier to find from the logarithm: the log turns the product into a sum, and since the log only increases, $p$ and $\ln p$ peak at the same $\lambda$. So the mode is where the **log-derivative**, the derivative of $\ln p$ (not the log of the derivative), is zero. As in Sec. 4.1, write $\delta = \lambda - \bar\lambda$ and $q = \ell/\ell'$.

**Step 1: take the log.** With $C$ a constant (the normalization):

$$
\begin{aligned}
\ln p(\lambda\mid d) &= -(\alpha+1)\ln\lambda - \frac{\beta}{\lambda}\\
&\quad + \ln\big[\ell+\ell'(\lambda-\bar\lambda)\big] + C .
\end{aligned} \notag
$$

**Step 2: differentiate and set to zero.** The three terms give $-(\alpha+1)/\lambda$, $\beta/\lambda^2$ and $\ell'/(\ell+\ell'\delta)$:

$$
\frac{-(\alpha+1)\lambda+\beta}{\lambda^2} + \frac{\ell'}{\ell+\ell'(\lambda-\bar\lambda)} = 0 . \notag
$$

This holds only where $\ell + \ell'\delta > 0$: the log of the linearized likelihood exists only there.

**Step 3: clear the denominators.** Multiply by $\lambda^2\,(\ell+\ell'\delta)/\ell'$:

$$
\big[\beta - (\alpha+1)\lambda\big]\,(q + \delta) + \lambda^2 = 0 . \notag
$$

This step also admits a root where $\ell + \ell'\delta < 0$, outside Step 2's domain. That is the spurious root ("The root choice can be wrong", below).

**Step 4: use the prior's mode,** $\alpha + 1 = \beta/\bar\lambda$ (Sec. 5.2, Step 1). Then $\beta - (\alpha+1)\lambda = -(\beta/\bar\lambda)\,\delta$, and multiplying by $-\bar\lambda/\beta$ gives

$$
\delta\,(q + \delta) - \frac{\bar\lambda}{\beta}\,\lambda^2 = 0 . \notag
$$

**Step 5: collect powers of $\lambda$** (put in $\delta = \lambda - \bar\lambda$):

$$
\Big(1-\frac{\bar\lambda}{\beta}\Big)\lambda^2 + (q-2\bar\lambda)\,\lambda + \big(\bar\lambda^2 - q\,\bar\lambda\big) = 0 , \tag{18}
$$

which is G18 (38) and the code's `a, b, c` (`:1169–1171`). Since $\bar\lambda/\beta = 1/(\alpha+1)$, Step 4's equation also reads

$$
\delta^2 + q\,\delta - \frac{\lambda^2}{\alpha+1} = 0 . \tag{19}
$$

**This is flavor 2's equation (12) with $\sigma_\lambda^2$ replaced by $\lambda^2/(\alpha+1)$.** At the mode, $\bar\lambda^2/(\alpha+1) \equiv \tau^2$ is the IG's "curvature variance", $-1\big/\tfrac{\partial^2}{\partial\lambda^2}\ln p\big|_{\bar\lambda}$. Because $\alpha$ is chosen to match the **variance**, which the long right tail inflates, $\tau^2 = \sigma_\lambda^2(\alpha-1)^2(\alpha-2)/(\alpha+1)^3 < \sigma_\lambda^2$. The small-step form of (19) is

$$
\lambda_u - \bar\lambda \approx \frac{\tau^2}{q} = \tau^2\,(\ln L)'(\bar\lambda). \tag{20}
$$

At $\bar\lambda = 1$, $\sigma_\lambda = 0.6$, one flavor-5 observation therefore moves $\lambda$ about 0.35 times as far as one flavor-2 observation: 0.39–0.44 in the small-step cases of Sec. 7.2, where the $+1/N$ shift adds a little, and 0.65 in its large-step case. This fits the 2026-10-03 discussion-log entry: step 13's `_hph_f5`, with the sd fixed at 0.6, gave about half of flavor 2's inflation. At $\sigma_\lambda = 0.3$ the factor is 0.65, but against flavor 2's 0.6 it is $0.058/0.36 = 0.16$.

The guards are at `:1148–1151` and `:1161–1166`. A root $\le 0$ or NaN keeps $\bar\lambda$ (`:1188–1189`).

**The root choice can be wrong in flavor 5.** The code keeps A09's rule, "the root closest to $\bar\lambda$". In (19) the roots have product $-\bar\lambda^2/\alpha < 0$, so there is one on each side, as in flavor 2. But (18)'s linear term in $\delta$ is $q - 2\bar\lambda/(\alpha+1)$, not $q$. As a result:

- **Where it fails:** for $0 < q < 2\bar\lambda/(\alpha+1)$ (a steep, rising likelihood; the threshold is 0.25 at $\bar\lambda = 1$, $\sigma_\lambda = 0.6$), the root closer to $\bar\lambda$ is the **negative** one.
- **Why that root is spurious:** it lies where $\ell + \ell'(\lambda - \bar\lambda) < 0$, i.e. where the linearized "posterior" is negative.
- **The right root:** the one where $\ell + \ell'(\lambda_u-\bar\lambda) > 0$.

Reproduced with DART's own routines compiled stand-alone (Sec. 7), for $\sigma_p^2 = 1$, $\sigma_o^2 = 0.2$, $\gamma = 1$, $\bar\lambda = 1$, $\sigma_\lambda = 0.6$, $N = 5$:

| $d^2/(\sigma_y^2+\sigma_o^2)$ | 4 | 6 | 8 | 9 | 12 |
|---|---|---|---|---|---|
| flavor 5, DART | 1.2532 | 1.3406 | **0.6315** | **0.6469** | **0.6748** |
| flavor 5, exact mode (grid) | 1.225 | 1.367 | 1.508 | 1.579 | 1.792 |
| flavor 2, DART | 1.3211 | 1.4062 | 1.4526 | 1.4685 | 1.5007 |

The outlier check passes $d^2/(\sigma_y^2+\sigma_o^2) \le 9$. At $\bar\lambda = \lambda^0 = 1$, $\gamma = 1$, the wrong root is taken when this ratio exceeds:

| $\sigma_o^2/\sigma_p^2$ | 0.05 | 0.1 | 0.2 | 0.5 |
|---|---|---|---|---|
| $\sigma_\lambda = 0.6$ | 6.3 | 6.7 | 7.5 | 9.8 |
| $\sigma_\lambda = 0.3$ | 12.7 | 13.5 | 15.2 | 20.3 |

So it needs $\sigma_\lambda$ near 0.6 (our first cycles; it is the initial sd) and an observation with a small error relative to the ensemble spread. For the radar ($\sigma_o = 5$ dBZ) that means a reflectivity spread $\sigma_p \gtrsim 10$ dBZ, an innovation within a few dBZ of the 3-sd outlier limit (e.g. 35–39 dBZ at $\sigma_p$ = 12 dBZ), and $\gamma$ near 1 (REFL_10CM and hydrometeors in the observed column). Missed or misplaced cells are exactly such cases. What happens then:
- **Where $\bar\lambda = 1$:** with `inf_lower_bound = 1` the result is clipped back to 1, so the observation's push is simply lost.
- **Where $\bar\lambda > 1$:** $\lambda$ goes down.
- **With a lower bound of 0** it would deflate.

This is not reported upstream.

**Worked out in `dart_flavor5_wrong_root.md`** (2026-10-27): the right root is always the one on the side of $\bar\lambda$ that $q$ points to (the larger if $\ell' > 0$, the smaller if $\ell' < 0$); flavor 2's closest root always is that one, flavor 5's not for $0 < q < 2\bar\lambda/(\alpha+1)$ $(= 2\bar\lambda^2/\beta)$. It also has where the wrong root can pass the outlier check, and a patch (`patches/dart_7bbd35a09_flavor5_root_choice.patch`).

### 5.4 The new sd (G18 (39)–(43); `bayes_cov_inflate`, `:905–966`)

Assume the posterior is IG($\alpha_u$, $\beta_u$) with mode $\lambda_u$, so $\alpha_u + 1 = \beta_u/\lambda_u$. The code evaluates the exact unnormalized posterior $p(\lambda) \propto \lambda^{-\alpha-1}e^{-\beta/\lambda}L(\lambda)$ (`enh_compute_new_density`, `:1011–1054`) at $\xi_1 = \lambda_u + \sigma_\lambda$ and $\xi_2 = \lambda_u$. For an IG, the normalizing constants cancel:

$$
\begin{aligned}
\ln R &\equiv \ln\frac{p(\xi_1)}{p(\xi_2)}\\
&= -(\alpha_u+1)\ln\frac{\xi_1}{\xi_2} - \beta_u\Big(\frac1{\xi_1}-\frac1{\xi_2}\Big)\\
&= \beta_u\,\omega,
\end{aligned} \notag
$$

$$
\omega = \frac{1}{\lambda_u}\ln\frac{\lambda_u}{\lambda_u+\sigma_\lambda} + \frac1{\lambda_u} - \frac{1}{\lambda_u+\sigma_\lambda}\ (<0), \tag{21}
$$

$$
\begin{gathered}
\beta_u = \frac{\ln R}{\omega},\qquad \alpha_u = \frac{\beta_u}{\lambda_u}-1,\\
\sigma_{\lambda,u} = \sqrt{\frac{\beta_u^2}{(\alpha_u-1)^2(\alpha_u-2)}} .
\end{gathered} \tag{22}
$$

This is `:945–956`, G18 (41)–(43).

**Why the sd can grow.**
- **It scales with the mode.** At fixed shape, the IG sd is proportional to its mode: by (16) with $\beta = \bar\lambda(\alpha+1)$, $\sigma_\lambda = \bar\lambda(\alpha+1)/\big((\alpha-1)\sqrt{\alpha-2}\big)$. Moving the mode up raises $\sigma_\lambda$ in proportion.
- **A still-rising likelihood widens the fit.** If the likelihood is still rising between $\lambda_u$ and $\lambda_u + \sigma_\lambda$ (innovations persistently larger than $\bar\theta$ predicts, i.e. $\lambda$ has not caught up yet), $R$ is closer to 1, so $\beta_u$ and $\alpha_u$ are smaller and the fitted IG is wider.
- **When it narrows instead:** with innovations consistent with the current $\lambda$, the sd narrows (Sec. 7.3).

**When the old sd is kept:**
- $\sigma_\lambda$ is at the floor: an early exit **after** the mode update (`:916–918`). With `inf_sd_initial = inf_sd_lower_bound`, flavor 5 changes only the mean. That was step 13's `_hph_f5`.
- $\alpha \le 2$ (`:924–927`) or $\alpha_u \le 2$ (`:952–955`).
- A density is ~0 or NaN (`:936–942`).
- **$\sigma_{\lambda,u} > $ `inf_sd_max_change` $\times\,\sigma_\lambda$ or NaN (`:961–965`).** Two consequences:
  - The test applies per **observation** update, and a larger growth is **rejected** (old sd kept), not clipped to the limit.
  - **There is no upper bound on the sd itself.** With 1.05, a run of large innovations can grow it by up to 5 % per observation (Sec. 7.3).
- **Single precision.** Our DART has `r8 = r4` (`types_mod.f90:85`), so this arithmetic is float32. `enh_compute_new_density` computes $\beta^\alpha/\Gamma(\alpha)$ first, and $\beta^\alpha$ overflows float32 ($3.4\times10^{38}$) once $\alpha\ln\beta > 88.7$. The densities then become Inf, $R$ is NaN, and the sd is kept by the NaN test. **So the flavor-5 sd silently freezes wherever $\sigma_\lambda/\bar\lambda \lesssim 0.22$–0.27**; the mode update is unaffected:

| $\bar\lambda$ | 1.0 | 1.25 | 1.5 | 2.0 | 3.0 | 5.0 |
|---|---|---|---|---|---|---|
| sd frozen (float32) for $\sigma_\lambda \le$ | 0.216 | 0.279 | 0.344 | 0.476 | 0.753 | 1.34 |

Checked with the compiled routines: at $\bar\lambda = 1$, an update from $\sigma_\lambda = 0.20$ gives 0.2000 in float32 against 0.2011 in float64. With our floor of 0.3, this matters where $\lambda$ has grown beyond ~1.35 and the sd sits near the floor: there the sd can neither shrink nor grow.

### 5.5 Bounds and deflation

The bounds are those of Sec. 4.3.
- **DART's guide** recommends `inf_lower_bound = 0` for flavor 5, since the IG keeps $\lambda > 0$. Ours is 1.0 (user, 2026-10-23).
- **G18's case for allowing moderate deflation (Sec. 4c):**
  - Forbidding deflation means the innovation statistics (3) are no longer satisfied.
  - Inflation inserts artificial spread that the model is unaware of; deflation can remove it.
  - The IG and the $1/N$ term keep deflation moderate.
- **G18's radar example (Sec. 5):** after a convective event ends and the Doppler observations vanish, the added variance is removed only slowly. A lower bound of 0 removes it through deflation, but only where some observations remain.
- **A09 (Sec. 5) on radar** makes the same point and the converse: when a cell begins to form and dense observations appear, adaptive inflation may not adjust quickly enough. It gives the same warning for any network whose density changes quickly in time.

---

## 6. Code map

**`filter_mod.f90`**

| what | lines |
|---|---|
| damping (on $\lambda$) | 824–827 |
| inflating the ensemble (`filter_ensemble_inflate`) | 829, 1563–1638 |

**`assim_tools_mod.f90`**

| what | lines |
|---|---|
| $\lambda^0$ into `ENS_SD_COPY` | 458 |
| frozen $\bar y$, $\sigma_y^2$ | 524–531, 638–641 |
| $\kappa$ (localization × impact), skip if 0 | 784–787, 2065–2100 |
| $r$ (before sampling-error correction) | 1503–1530 |
| per-element inflation update call | 796–805 |

**`adaptive_inflate_mod.f90`**

| what | routine | lines |
|---|---|---|
| namelist checks | `validate_inflate_options` | 409–517 |
| flavor 5 = flavor 2 + `GHA2017` | `adaptive_inflate_init`, `update_inflation` | 285–287, 630–634 |
| inflating one element | `inflate_ens` | 524–596 |
| $\gamma$, $\lambda^0$ out of $\sigma_y^2$ | `update_varying_state_space_inflation` | 707–756 |
| bounds | `update_inflation` | 611–650 |
| flavor 2 mode | `linear_bayes` | 1060–1116 |
| flavor 2 sd | `bayes_cov_inflate`, `compute_new_density` | 848–903, 980–1005 |
| flavor 5: ($\bar\lambda$, $\sigma_\lambda$) → IG | `change_GA_IG` | 1229–1262 |
| flavor 5 mode | `enh_linear_bayes` | 1122–1191 |
| flavor 5 sd | `bayes_cov_inflate`, `enh_compute_new_density` | 905–966, 1011–1054 |
| quadratic solver | `solve_quadratic` | 1197–1222 |

---

## 7. Worked numbers

Two checks, both in `notes/checks/`:
- **Python translation:** `inflation_checks.py` translates `update_varying_state_space_inflation`, `update_inflation` and `bayes_cov_inflate` with their helpers line by line, in double precision. Its sections 1–12 give the numbers of Sec. 3.2, 4.2, 5 (start), 5.2–5.4, 7 and 8 (the section list is at the top of the script). Run, in a few seconds: `uv run --no-project --with numpy python -I notes/checks/inflation_checks.py [n ...]`.
- **Verbatim Fortran:** `inflation_fortran_check.sh` copies `adaptive_inflate_mod.f90:763–1262` from `../software/DART` into a stand-alone module with stubs for `error_handler` (in a temporary directory; DART's source isn't kept in the repo), compiles it with `inflation_fortran_driver.f90` using ifort 19.1.3 at `r8` = float32 and float64, and runs both: the wrong-root table (Sec. 5.3) and the sd update at small sd (Sec. 5.4). Run: `bash notes/checks/inflation_fortran_check.sh`.

The two agree on every case run in both. Cases use $N = 5$, bounds [1, 5], `inf_sd_max_change` 1.05 and $\lambda^0 = 1$. The two kinds of observation:
- **"METAR T2":** $\sigma_o = 1.26$ K, prior sd of H(x) $\sigma_p = 0.5$ K.
- **"radar":** $\sigma_o = 5$ dBZ, $\sigma_p$ = 2 or 8 dBZ ("radar sd 2", "radar sd 8").

### 7.1 Flavor 2's linearization against the exact posterior mode ($\gamma = 1$, $\bar\lambda = 1$, $\sigma_\lambda = 0.6$)

| case | linearized (DART) | exact (grid) |
|---|---|---|
| METAR, $d$ = 1.5 K | 1.0055 | 1.0055 |
| METAR, $d$ = 3 K | 1.0931 | 1.0928 |
| radar sd 2, $d$ = 15 dBZ | 1.1564 | 1.1601 |

The linearization is very good for these sizes.

### 7.2 One observation, $\gamma = 1$, $\bar\lambda = 1$, $\sigma_\lambda = 0.6$

$\hat\lambda_o = (d^2-\sigma_o^2)/\sigma_p^2$ is Eq. (3) with a single innovation. ¹ clipped at the lower bound 1. ² growth > 5 %, rejected (old sd kept).

| case | $\hat\lambda_o$ | flavor 2 $\lambda_u$ | flavor 5 $\lambda_u$ | flavor 5 sd (floor 0.3) |
|---|---|---|---|---|
| METAR, $d$ = 1 K | −2.4 | 1.0000 ¹ | 1.0000 ¹ | 0.591 |
| METAR, $d$ = 2 K | 9.6 | 1.0288 | 1.0111 | 0.620 |
| METAR, $d$ = 3 K | 29.6 | 1.0931 | 1.0378 | 0.600 ² |
| radar sd 2, $d$ = 5 | 0.0 | 1.0000 ¹ | 1.0000 ¹ | 0.597 |
| radar sd 2, $d$ = 15 | 50 | 1.1564 | 1.0687 | 0.600 ² |
| radar sd 8, $d$ = 15 | 3.1 | 1.1800 | 1.1174 | 0.609 |

- Flavor 5 moves $\lambda$ 0.39–0.65 times as far as flavor 2.
- The flavor-2 sd, with the floor at 0.3, never grows: 0.600, 0.597, 0.592, 0.599, 0.591, 0.525 down the table.
- **Step sizes:** the small-step formulas (14) and (20) reproduce the METAR, $d$ = 2 K case: flavor 2, 0.0288 against 0.0288; flavor 5, 0.0109 against 0.0111 ($\tau^2 = 0.126$). Without the $-1/N$ term flavor 5 would give 0.0103.
- **Dependence on $\gamma$** (flavor 2, METAR, $d$ = 2 K): $\lambda_u - 1$ = 0.0288, 0.0144, 0.0029 for $\gamma$ = 1, 0.5, 0.1. It is nearly linear in $\gamma$.
- **Deflation** (lower bound 0, small innovations): METAR $d$ = 0.5 K gives 0.979 with flavor 2 and 0.993 with flavor 5. Radar $d$ = 1 gives 0.976 and 0.992. Flavor 5 deflates less, as G18 intends.

### 7.3 A run of identical observations at one element

Radar sd 2, $d$ = 8, $\gamma = 1$, the same observation $n$ times. $\lambda$ after $n$ observations:

| | $n$ = 1 | 5 | 10 | 20 | 40 |
|---|---|---|---|---|---|
| flavor 2, floor 0.6 | 1.030 | 1.146 | 1.284 | 1.541 | 1.989 |
| flavor 2, floor 0.3 | 1.030 | 1.143 | 1.272 | 1.496 | 1.856 |
| flavor 5, floor 0.6 | 1.012 | 1.059 | 1.120 | 1.248 | 1.523 |
| flavor 5, floor 0.3 | 1.012 | 1.063 | 1.140 | 1.336 | 1.902 |

The sd after $n$ observations (with the floor at 0.6 it stays 0.600 in both flavors):

| | $n$ = 1 | 5 | 10 | 20 | 40 |
|---|---|---|---|---|---|
| flavor 2, floor 0.3 | 0.597 | 0.584 | 0.570 | 0.546 | 0.511 |
| flavor 5, floor 0.3 | 0.620 | 0.718 | 0.893 | 1.033 | 1.447 |

- **Persistently large innovations:** here the innovation stays far above what $\lambda$ predicts, so the flavor-5 sd keeps growing (to 1.45). After it has grown, flavor 5 moves $\lambda$ as fast as flavor 2.
- **Random innovations** (toy, 2000 observations, $d \sim N(0, \lambda_o\sigma_p^2+\sigma_o^2)$):
  - With $\gamma = 1$ the flavor-5 sd fell to the 0.3 floor within 100–500 observations for every $\lambda_o$ tried (0.7, 1, 2): $\lambda$ catches up, and the innovations become consistent.
  - With $\gamma = 0.3$, where $\lambda$ catches up slowly, it fell more slowly ($\lambda_o$ 0.7, 1: 0.33, 0.41 after 2000), and with $\lambda_o = 2$ it rose to 0.82.
  - The flavor-2 sd falls slowly toward 0.3 in all cases (0.30–0.34 after 2000).

### 7.4 A fixed sd is a constant gain: $\lambda$ never settles

- **Constant gain.** With $\sigma_\lambda$ at its floor, each observation moves $\lambda$ by about $\sigma_\lambda^2\,(\ln L)'$ (14), however many observations came before. This is a constant-gain estimator.
- **Fisher information.** The information one observation carries about $\lambda$ is $I = \tfrac12\big((\theta^2)'/\theta^2\big)^2$, which is $\tfrac12\gamma^2(\sigma_p^2/\theta^2)^2$ at $\lambda = 1$ (flavor 2).
- **Consequences:**
  - **Memory:** $\lambda$ forgets its start after $M \approx 1/(\sigma_\lambda^2 I)$ observations.
  - **Noise:** it then fluctuates around its target with sd $\approx \sigma_\lambda/\sqrt2$, independent of $I$ (AR(1) argument).
- **Toy check** (flavor 2, radar sd 2, $\gamma = 1$, $d \sim N(0, \lambda_o\sigma_p^2 + \sigma_o^2)$ with $\lambda_o = 1.5$, lower bound 0):
  - sd of $\lambda$ 0.430 for floor 0.6 (prediction 0.424) and 0.212 for floor 0.3 (0.212).
  - $M$ ≈ 290 and 1170 observations.
  - For $\gamma = 0.5$ the toy gave less noise (0.28, 0.12), so treat the rule as an order of magnitude.
- **Target for $\gamma < 1$:** an element's $\lambda$ heads for $\big[1 + (\sqrt{\lambda_o}-1)/\gamma\big]^2$, e.g. 2.1 for $\lambda_o = 1.5$, $\gamma = 0.5$; the toy gave 2.12. It overshoots so that the observation's variance comes out right. Its memory grows as $1/\gamma^2$.

---

## 8. Documentation against code

1. **Damping.**
   - **What the code does:** `filter_mod.f90:825–826` damps $\lambda$, Eq. (1). The prose of DART's guide (the `inf_damping` entry) agrees.
   - **What the paper and the guide's note say:** G18 Sec. 3d and the guide's "Order of (prior) inflation operations" note damp $\sqrt\lambda$: $\sqrt\lambda \leftarrow 1 + \rho(\sqrt\lambda - 1)$.
   - **How much it matters:** for $\rho = 0.9$, $\lambda$ = 1.5, 2, 3, 5 become 1.450, 1.900, 2.800, 4.600 (code) against 1.446, 1.885, 2.752, 4.463 ($\sqrt\lambda$ form). The e-folding time of $\lambda - 1$ in the code is $-1/\ln\rho$ cycles.
2. **`inf_sd_max_change`.** The guide calls it the maximum increase "in an assimilation cycle". In the code the test applies to each observation's update, and a larger increase is rejected (old sd kept), not clipped (Sec. 5.4).
3. **Flavor 5's sd evolves only with `inf_sd_lower_bound` below the current sd.** The guide says so only under `inf_sd_max_change`.
4. **A09's $\gamma$ uses the signed correlation** (A09 (9)–(10)). The code uses $\lvert r\rvert$ (`:729`), as G18 does.
5. **A09's sd method may raise the sd** ("biased to produce slightly larger values", Sec. 4.2). The code keeps the old sd instead (`:896–901`). No paper gives a reason for this guard, which dates from the module's first version (2006), and G18 Sec. 4c attributes A09's monotonically falling sd to the Gaussian prior when the guard is the cause (Sec. 4.2).
6. **"By construction, does not require enforcing the inflation to be nonnegative"** (G18 Sec. 3d). The IG prior is positive, but the linearized quadratic (18) can still give a negative root, guarded at `:1188–1189`, or a wrong one (Sec. 5.3). With the right root it is always positive (`dart_flavor5_wrong_root.md` Sec. 2.3).
7. **G18 (31), the cubic for $\beta$,** prints $7/\bar\lambda$ where it should be $7/\bar\lambda^2$ (Sec. 5.2). The code's closed form (G18 (33)–(35)) solves the correct cubic.

---

## 9. What this means for run 5 (flavor 2 against flavor 5)

Settings: `INF_DAMPING = 0.9`, bounds [1, 5], initial sd 0.6. Flavor 2 (`_conv_refl_f2`) keeps the floor at 0.6; flavor 5 (`_conv_refl_f5`) has `INF_SD_LOWER_BOUND = 0.3` (discussion log, 2026-10-23).

**Flavor 2.** The sd stays 0.6. Each observation moves $\lambda$ by less than 0.6, usually by about $\gamma\,\sigma_\lambda^2\sigma_p^2(d^2-\bar\theta^2)/(2\bar\theta^4)$. $\lambda$ never settles: in densely observed places it fluctuates by roughly $0.6/\sqrt2 \approx 0.4$ around its target, with a memory of a few hundred strongly correlated observations (Sec. 7.4).

**Flavor 5 with floor 0.3, in the order things happen:**

1. **First cycles, sd near 0.6:**
   - Steps are 0.35–0.45 of flavor 2's.
   - The target is higher by $1/N$ = 0.2.
   - Large radar innovations where the reflectivity spread is large can take the wrong root (Sec. 5.3).
2. **Where innovations become consistent with $\lambda$:** the sd falls toward 0.3. Steps there are ~1/6 of flavor 2's at 0.6, so $\lambda$ moves slowly but with less noise (~0.2).
3. **Where innovations stay larger than expected** ($\lambda$ not catching up, e.g. small $\gamma$): the sd grows by up to 5 % per accepted update, with no upper bound on the sd. Once it has grown, $\lambda$ moves as fast as flavor 2's or faster, until it reaches the cap of 5.
4. **Where $\lambda \gtrsim 1.35$ and the sd is near 0.3:** the float32 overflow freezes the sd (Sec. 5.4).

**What to look at in the run-5 output:**
- **sd field:** the distribution and maximum of `postassim_priorinf_sd`. Where did it exceed 0.6?
- **Applied $\lambda$:** the share of `preassim_priorinf_mean` at 1.0 and at 5.0, over all points and in echo columns.
- **Wrong-root cases:** how many radar observations in `obs_seq.final` with DART QC 0 have prior spread $\sigma_y \gtrsim 2.2\,\sigma_o$ ($\sigma_o^2/\sigma_y^2 \le 0.2$; $\sigma_y = \sigma_p$ where $\lambda^0 = 1$) and $d^2/(\sigma_y^2+\sigma_o^2) > 7$. Runs 3 and 4 already allow this count.
