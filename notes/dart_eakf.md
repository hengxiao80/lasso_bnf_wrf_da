# The EAKF in DART: theory, math, code, and the other ensemble filters

Written 2026-10-25 as a walk-through of the ensemble adjustment Kalman filter (EAKF) as our `filter` runs it: where the method comes from, the math of one observation, how DART applies it to many observations and a large state, the code step by step, and how it relates to the perturbed-observation EnKF, the serial EnSRF that HRRRDAS uses, and the ETKF and LETKF.

**Sources.**
- DART papers (PDFs in `notes/papers/`):
  - **A01:** Anderson (2001), "An ensemble adjustment Kalman filter for data assimilation", MWR 129, 2884–2903, doi:10.1175/1520-0493(2001)129<2884:AEAKFF>2.0.CO;2. Equation numbers "A01 (n)" are the paper's, as for all papers below.
  - **A03:** Anderson (2003), "A local least squares framework for ensemble filtering", MWR 131, 634–642: the two steps (observation increment, then regression).
  - **AC07:** Anderson and Collins (2007), "Scalable implementations of ensemble filter algorithms for data assimilation", JTECH 24, 1452–1463, doi:10.1175/JTECH2049.1: the parallel algorithm DART (and GSI-EnKF) use.
  - **A+09:** Anderson et al. (2009), "The Data Assimilation Research Testbed: A community facility", BAMS 90, 1283–1296.
  - **G+25:** Gharamti et al. (2025), "The Data Assimilation Research Testbed: A robust, scalable software facility with groundbreaking capabilities ...", BAMS (November 2025), E2328ff, doi:10.1175/BAMS-D-24-0214.1.
  - **GC99:** Gaspari and Cohn (1999), "Construction of correlation functions in two and three dimensions", QJRMS 125, 723–757, doi:10.1002/qj.49712555417: the localization function, their Eq. (4.10).
  - The sampling-error correction (A12) and inflation papers (A07a, A09, G18) are cited in their own notes.
- Other ensemble filters (PDFs in `notes/papers/`; DOIs checked against Crossref):
  - **B98:** Burgers, van Leeuwen and Evensen (1998), "Analysis scheme in the ensemble Kalman filter", MWR 126, 1719–1724, doi:10.1175/1520-0493(1998)126<1719:ASITEK>2.0.CO;2.
  - **HM98:** Houtekamer and Mitchell (1998), "Data assimilation using an ensemble Kalman filter technique", MWR 126, 796–811, doi:10.1175/1520-0493(1998)126<0796:DAUAEK>2.0.CO;2.
  - **HM01:** Houtekamer and Mitchell (2001), "A sequential ensemble Kalman filter for atmospheric data assimilation", MWR 129, 123–137, doi:10.1175/1520-0493(2001)129<0123:ASEKFF>2.0.CO;2.
  - **B01:** Bishop, Etherton and Majumdar (2001), "Adaptive sampling with the ensemble transform Kalman filter. Part I: Theoretical aspects", MWR 129, 420–436, doi:10.1175/1520-0493(2001)129<0420:ASWTET>2.0.CO;2.
  - **WH02:** Whitaker and Hamill (2002), "Ensemble data assimilation without perturbed observations", MWR 130, 1913–1924, doi:10.1175/1520-0493(2002)130<1913:EDAWPO>2.0.CO;2.
  - **T03:** Tippett, Anderson, Bishop, Hamill and Whitaker (2003), "Ensemble square root filters", MWR 131, 1485–1490, doi:10.1175/1520-0493(2003)131<1485:ESRF>2.0.CO;2.
  - **H07:** Hunt, Kostelich and Szunyogh (2007), "Efficient data assimilation for spatiotemporal chaos: A local ensemble transform Kalman filter", Physica D 230, 112–126, doi:10.1016/j.physd.2006.11.008.
  - **G11:** Greybush, Kalnay, Miyoshi, Ide and Hunt (2011), "Balance and ensemble Kalman filter localization techniques", MWR 139, 511–522, doi:10.1175/2010MWR3328.1.
  - **WH12:** Whitaker and Hamill (2012), "Evaluating methods to account for system errors in ensemble data assimilation", MWR 140, 3078–3089, doi:10.1175/MWR-D-11-00276.1: RTPS.
  - **HW13:** Holland and Wang (2013), "Effects of sequential or simultaneous assimilation of observations and localization methods on the performance of the ensemble Kalman filter", QJRMS 139, 758–770, doi:10.1002/qj.2006.
  - **N15:** Nerger (2015), "On serial observation processing in localized ensemble Kalman filters", MWR 143, 1554–1567, doi:10.1175/MWR-D-14-00182.1.
  - **HZ16:** Houtekamer and Zhang (2016), "Review of the ensemble Kalman filter for atmospheric data assimilation", MWR 144, 4489–4532, doi:10.1175/MWR-D-15-0440.1.
  - **B17:** Bishop, Whitaker and Lei (2017), "Gain form of the ensemble transform Kalman filter and its relevance to satellite data assimilation with model space ensemble covariance localization", MWR 145, 4575–4592, doi:10.1175/MWR-D-17-0102.1.
- HRRRDAS:
  - **D20:** Dowell (2020), "HRRR Data-Assimilation System (HRRRDAS) and HRRRE Forecasts", NOAA/GSL document, 1 March 2020 (PDF in `notes/papers/`).
  - **D22:** Dowell et al. (2022), "The High-Resolution Rapid Refresh (HRRR): An hourly updating convection-allowing forecast model. Part I: Motivation and system description", WAF 37, 1371–1395, doi:10.1175/WAF-D-21-0151.1 (PDF in `notes/papers/`): Sec. 3d and Table 5.
  - Code: the HRRR repo, `../software/HRRR` at `40ee6058` (hrrr.v4.1.20): `scripts/hrrrdas/exhrrr_enkf.sh`, `parm/hrrrdas/hrrrdas_enkf_wrf_namelist.sh`, and GSI-EnKF in `sorc/hrrr_gsi.fd/src/enkf/` (`enkf.f90`, `inflation.f90`, `covlocal.f90`, `params.f90`, `enkf_main.f90`). "GSI `enkf.f90:n`" below refers to this copy.
- LETKF code: GSI, `../software/GSI` at `124138df0`, `src/enkf/letkf.f90` (the HRRR copy has it too, as `letkf.F90`; HRRRDAS doesn't use it).
- Not in `notes/papers/`, background only: the QCEFF papers, Anderson (2022), MWR 150, 1061–1074, doi:10.1175/MWR-D-21-0229.1; Anderson (2023), MWR 151, 2759–2777, doi:10.1175/MWR-D-23-0065.1; Anderson et al. (2024), MWR 152, 2111–2127, doi:10.1175/MWR-D-23-0255.1.
- **DART code:** `7bbd35a09`, under `../software/DART/assimilation_code/`: `modules/assimilation/assim_tools_mod.f90` (bare line numbers below), `cov_cutoff_mod.f90`, `algorithm_info_mod.f90`, `probit_transform_mod.f90`, `adaptive_inflate_mod.f90`, and `location/threed_sphere/location_mod.f90`. The WRF build compiles `assim_tools_mod.f90` (`models/wrf/work/quickbuild.log`); `assim_tools_mod.pf.f90` next to it is a particle-filter variant.
- **Numbers:** from `notes/checks/eakf_checks.py` (Sec. 12), which translates DART's `obs_increment_eakf`, `obs_increment_enkf`, `update_from_obs_inc` and `obs_updates_ens`, GSI's serial EnSRF, an LETKF (H07 (20)–(25) with GSI's R-localization), a global ETKF, A01's Appendix A, and both Gaspari–Cohn functions. Float64, except Sec. 7.8, which emulates float32.

**Related notes.**
- `dart_workflow_walkthrough.md` Sec. 2–3: filter's order of operations and the observation loop in brief.
- `dart_sampling_error_correction.md`: the factor $S$ on the regression. Its $a$ is A12's SEC factor, not the EAKF's $a$ used here.
- `dart_adaptive_inflation.md`: the prior inflation that sets $\sigma_y^2$ before the EAKF sees it.
- `codex.WRF_DART_Discussion_and_Branches_Summary_v1.md` Sec. 7–8: an earlier summary of the EAKF and its relatives. Its EAKF–EnSRF identity is confirmed in Sec. 9.3 here.
- `obs_expansion.md`, "EnKF" table: HRRRDAS's EnKF settings. `wrf_dart_tutorial_adaptation.md`: HRRRDAS's analysis variables.
- `eakf_vs_letkf.md`: the EAKF against the LETKF in detail (both as ensemble transforms, R- against B-localization, the gain form, GSI's and JEDI's LETKF); continues Sec. 9.4–9.6.

**Typora.** Display equations are `$$` blocks. Inline math (`$...$`) needs *Preferences → Markdown → Inline Math*.

---

## 0. Summary

- **One observation, two steps** (A03):
  1. *Observation space.* The prior ensemble of H(x) is treated as Gaussian. Its product with the Gaussian likelihood gives a posterior mean and variance. The ensemble is shifted to the new mean and shrunk about it by $a = \sqrt{\sigma_o^2/(\sigma_y^2+\sigma_o^2)}$. No random numbers; the members keep their order.
  2. *State space.* Each state element gets the observation increments times its regression coefficient $\operatorname{cov}(x,y)/\sigma_y^2$, times the localization weight (and, in our runs, the impact factor and the sampling-error correction).
- **It is the Kalman filter, one scalar at a time.** For linear H and no localization, the serial EAKF gives the Kalman-filter mean and covariance exactly (Sec. 4.2; checked to 2e-15). The observation order changes the members but not the mean or covariance (Sec. 6.2).
- **Many observations (AC07).** All H(x) are computed once, before the loop. Each observation's increments are regressed onto the state and onto the H(x) of the observations not yet used. This equals re-evaluating H only when H is linear.
- **The relatives:**
  - *Perturbed-observation EnKF* (HM98, B98): right covariance only on average. At $N = 5$ its posterior variance is off by 1.7–1.9 times as much as the EAKF's (WH02; reproduced in Sec. 9.2).
  - *Serial EnSRF* (WH02), which HRRRDAS runs through GSI-EnKF: algebraically identical to DART's EAKF, member by member, with localization too (Sec. 9.3; checked against a translation of GSI's code).
  - *ETKF* with the symmetric square root: identical for one observation. For many at once it has the same mean and covariance but different members (T03).
  - *LETKF* (H07): all local observations at once, localization on R. It differs from the serial EAKF only once localization is on. DART doesn't have it (G+25).
- **With localization, serial is not simultaneous.** The result depends on the order, and the covariance update is inconsistent (WH02, N15). It matters when observations are accurate relative to the prior spread, which is radar in convective areas (N15 Sec. 7).
- **HRRRDAS against us.** Same algorithm and the same localization cutoffs (300 km and 0.5 scale height; 18 km for radar). The differences are around it: RTPS with α = 1.08 against our adaptive prior inflation, the sampling-error correction, the 3-D shape of the localization, two passes against one, 36 members against 5.
- **Code facts:** `sort_obs_inc` affects only the perturbed-observation EnKF; `spread_restoration = .true.` stops filter; `qceff_table_filename = ''` means EAKF for every observation; single precision costs about one float32 unit.

## 1. Notation

| symbol | meaning | in the code |
|---|---|---|
| $N$, $n$ | ensemble size, member | `ens_size`, `grp_size` |
| $x_{j,n}$ | state element $j$ | `ens_handle%copies` |
| $y_n$ | prior H(x) | `obs_prior` |
| $\bar y$, $\sigma_y^2$ | sample mean, variance¹ | `prior_mean`, `prior_var` |
| $y_o$, $\sigma_o^2$ | observation, error variance | `obs`, `obs_var` |
| $d$ | innovation $y_o-\bar y$ | |
| $k$ | $\sigma_y^2/(\sigma_y^2+\sigma_o^2)$ | `1 - var_ratio` |
| $a$ | $\sqrt{1-k}$, the contraction | `a` |
| $\bar y_u$, $\sigma_u^2$ | posterior mean, variance | `new_mean` |
| $\Delta y_n$ | observation increment | `obs_inc` |
| $c_j$ | $\operatorname{cov}(x_j,y)$ | `obs_state_cov` |
| $b_j$ | $c_j/\sigma_y^2$, regression | `reg_coef` |
| $\kappa_j$ | localization × impact factor | `final_factor` |
| $S_j$ | sampling-error correction | (SEC note) |
| $x'$, $y'$ | deviation from the mean | |

¹ All sample (co)variances divide by $N-1$.

The matrix forms (Sec. 2.2, 9) use $\mathbf X$ ($M \times N$, state deviations), $\mathbf Y$ ($p \times N$, H(x) deviations), $\mathbf P = \mathbf X\mathbf X^T/(N-1)$, $\mathbf R$ and the gain $\mathbf K$.

## 2. The problem

### 2.1 Bayes on the joint state (A01 Sec. 2a; A03 Sec. 2a)

A01 appends the observed quantities to the state, $z = [x, h(x)] = [x, y]$ (A03 (1)). Given an observation $y_o$, Bayes' rule is

$$
p(z \mid y_o) \propto p(y_o \mid y)\, p(z) \tag{1}
$$

(A01 (12), A03 (2)). The likelihood depends only on the $y$ part. In the joint space the forward operator is linear (it picks out $y$), and all of $h$'s nonlinearity sits in the prior ensemble of $y = h(x)$, which is computed member by member. This is how arbitrary forward operators enter without a tangent-linear or adjoint operator (A01 Sec. 2a; G+25 Sec. "DA algorithms").

If the observation errors are mutually independent, the likelihood factors and the observations can be assimilated one at a time, in any order (A03 (3); HM01):

$$
p(\mathbf y_o \mid z) = \prod_{i=1}^{p} p(y_{o,i} \mid z) \tag{2}
$$

This is exact for the Bayesian problem. The ensemble filter built on it inherits the order independence only for linear H and without localization (Sec. 6).

### 2.2 The Kalman filter target (WH02 (1)–(3))

$$
\begin{aligned}
\mathbf K &= \mathbf P_b\mathbf H^T(\mathbf H\mathbf P_b\mathbf H^T+\mathbf R)^{-1}\\
\bar{\mathbf x}_a &= \bar{\mathbf x}_b + \mathbf K(\mathbf y_o-\mathbf H\bar{\mathbf x}_b)\\
\mathbf P_a &= (\mathbf I-\mathbf K\mathbf H)\,\mathbf P_b
\end{aligned} \tag{3}
$$

Every ensemble Kalman filter uses (3) with $\mathbf P_b$ from the ensemble. They differ in how they build an analysis ensemble with mean $\bar{\mathbf x}_a$ and covariance $\mathbf P_a$ (T03): stochastically, with perturbed observations (HM98, B98), or deterministically, with a square root of (3) (B01, A01, WH02). A01 derives the EAKF as a Monte Carlo approximation to (1) that assumes Gaussians only to compute the product; the ensemble itself can keep a non-Gaussian shape (A01 Sec. 2d, A+09 Fig. 10).

## 3. One observation: the observation-space step

### 3.1 The product of two Gaussians (A01 (13)–(14); AC07 (3.2)–(3.3))

With the prior H(x) ensemble approximated by $\mathcal N(\bar y, \sigma_y^2)$ and the likelihood $\mathcal N(y_o, \sigma_o^2)$, the posterior is Gaussian with

$$
\begin{aligned}
\sigma_u^2 &= \Big(\frac{1}{\sigma_y^2}+\frac{1}{\sigma_o^2}\Big)^{-1}\\
\bar y_u &= \sigma_u^2\Big(\frac{\bar y}{\sigma_y^2}+\frac{y_o}{\sigma_o^2}\Big)
\end{aligned} \tag{4}
$$

or, in terms of the scalar gain $k$,

$$
\begin{aligned}
k &= \frac{\sigma_y^2}{\sigma_y^2+\sigma_o^2}\\
\bar y_u &= \bar y + k\,d\\
\sigma_u^2 &= (1-k)\,\sigma_y^2
\end{aligned} \tag{5}
$$

### 3.2 Shift and contract (A03 (18)–(19); AC07 (3.4))

The EAKF moves every member to the posterior mean and scales its deviation by the ratio of the standard deviations:

$$
\begin{aligned}
y_n^u &= \bar y_u + a\,(y_n-\bar y)\\
a &= \frac{\sigma_u}{\sigma_y} = \sqrt{\frac{\sigma_o^2}{\sigma_y^2+\sigma_o^2}}
\end{aligned} \tag{6}
$$

$$
\Delta y_n = y_n^u - y_n = k\,d + (a-1)\,(y_n-\bar y) \tag{7}
$$

Properties:
- The new sample mean is $\bar y_u$ and the new sample variance $\sigma_u^2$, **exactly**, not on average.
- Deterministic: the EAKF "is deterministic after initialization, requiring no generation of random numbers" (A01 Sec. 2d), so a rerun on the same layout reproduces the analysis.
- $a > 0$, so the members keep their rank order, and the shape of the prior ensemble (skewness, bimodality) survives the update (A01 Sec. 2d, A+09 Fig. 10).
- Each member keeps its quantile: $(y_n^u-\bar y_u)/\sigma_u = (y_n-\bar y)/\sigma_y$. Quantile conservation is the property the QCEFF (Anderson 2022) generalizes; G+25: it "recovers the EAKF when using Gaussian assumptions" (Sec. 7.6).
- An observation that is weak relative to the prior ($\sigma_o \gg \sigma_y$) gives small increments, which A03 Sec. 4c lists as a requirement for any observation-space update.

In the code (`obs_increment_eakf`, `:1113–1133`):

```fortran
var_ratio = obs_var / (prior_var + obs_var)
new_mean  = var_ratio * (prior_mean  + prior_var*obs / obs_var)
a = sqrt(var_ratio)
obs_inc = a * (ens - prior_mean) + new_mean - ens
```

`var_ratio` is $1-k$, and `new_mean` is (4), since $\sigma_u^2 = (1-k)\,\sigma_y^2$. `prior_mean` and `prior_var` are computed in `obs_increment` from the ensemble passed in (`:947–948`, divisor $N-1$), i.e. from the H(x) ensemble as updated by the observations before this one (Sec. 6).

### 3.3 How much one observation does

$k$ and $a$ depend only on the ratio of the prior spread to the observation error:

| $\sigma_y/\sigma_o$ | $k$ | $a$ |
|---|---|---|
| 0.25 | 0.059 | 0.970 |
| 0.5 | 0.200 | 0.894 |
| 1 | 0.500 | 0.707 |
| 2 | 0.800 | 0.447 |
| 3 | 0.900 | 0.316 |

Our $\sigma_o$ (CLAUDE.md): METAR T2 1.26 K, wind 1.59 m/s, RH 0.059; mesonet T 3.0 K, wind 3.0 m/s, RH 0.07, altimeter 1.0 hPa; MRMS 5 dBZ. $\sigma_y$ is the spread of the **inflated** prior (the inflation is applied before H(x), `dart_adaptive_inflation.md` Sec. 2).

Two examples with five members:

- **METAR T2.** Prior H(x) = 296.0, 297.1, 297.6, 298.3, 299.0 K ($\bar y$ = 297.6 K, $\sigma_y$ = 1.147 K), $y_o$ = 298.9 K, $\sigma_o$ = 1.26 K. Then $d$ = 1.3 K, $k$ = 0.453, $a$ = 0.740. The increments are +1.006, +0.719, +0.589, +0.407, +0.224 K: the mean moves to 298.19 K (45 % of the innovation) and the spread drops to 0.848 K.
- **MRMS reflectivity.** Prior H(x) = 12, 25, 33, 38, 45 dBZ ($\sigma_y$ = 12.7 dBZ), $y_o$ = 41 dBZ, $\sigma_o$ = 5 dBZ. Then $k$ = 0.866 and $a$ = 0.366. The increments are +20.8, +12.6, +7.5, +4.3, −0.1 dBZ: one observation removes 63 % of the spread, and the weakest member gets +20.8 dBZ, which the linear regression of Sec. 4 then carries to QRAIN, QSNOW and QGRAUP.

## 4. From the observation to the state: regression

### 4.1 The regression step (A03 (6), (16); AC07 (3.6)–(3.7))

Every state element is updated by the least-squares line of $x_j$ on $y$ through the prior ensemble:

$$
\begin{aligned}
\Delta x_{j,n} &= b_j\,\Delta y_n\\
b_j &= c_j/\sigma_y^2\\
c_j &= \frac{1}{N-1}\sum_{n} x'_{j,n}\,y'_n
\end{aligned} \tag{8}
$$

A03 calls this a statistical linearization and inversion of $h$ (A03 Sec. 2c, Fig. 1). In our filter the regression is multiplied by the localization and impact weight and by the sampling-error correction:

$$
\Delta x_{j,n} = \kappa_j\,S_j\,b_j\,\Delta y_n \tag{9}
$$

Only the correlation of $x_j$ with $y$ matters: $b_j = r_j\,\sigma_{x_j}/\sigma_y$, and the prior covariance among state elements is never formed (A03 after (6)).

### 4.2 Why this is the Kalman filter (A03 (14), (20)–(27))

Split (7) into its mean and deviation parts and insert into (8), without $\kappa$ and $S$:

$$
\begin{aligned}
\Delta\bar x_j &= b_j\,k\,d = \frac{c_j}{\sigma_y^2+\sigma_o^2}\,d\\
x'^{\,u}_{j,n} &= x'_{j,n} + (a-1)\,b_j\,y'_n
\end{aligned} \tag{10}
$$

The first line is the Kalman mean update (3) for one observation, with gain $K_j = c_j/(\sigma_y^2+\sigma_o^2)$. For the covariance of two state elements $i$ and $j$ after the update, insert the second line, use $b = c/\sigma_y^2$ and $a^2-1 = -k$:

$$
\begin{aligned}
P^u_{ij} &= P_{ij} + \big[2(a-1)+(a-1)^2\big]\frac{c_i\,c_j}{\sigma_y^2}\\
&= P_{ij} + (a^2-1)\frac{c_i\,c_j}{\sigma_y^2}\\
&= P_{ij} - \frac{c_i\,c_j}{\sigma_y^2+\sigma_o^2}
\end{aligned} \tag{11}
$$

which is $\mathbf P_a = (\mathbf I-\mathbf K\mathbf H)\mathbf P_b$ for one observation. A03 (20)–(27) prove the same in matrix form: the regression update is a linear operator $\mathbf A$ = identity plus a scalar times the matrix of covariances with $y$, and A03 (27) shows it is the square root $\mathbf B$ of A03 (20)–(21), with $\mathbf P_u = \mathbf B\mathbf P\mathbf B^T$. Applied once per observation, (10) gives the Kalman analysis of all observations (Sec. 6.2).

A03 adds that multiplying the prior covariance by an inflation factor does not change the regression (A03 (16)), since $b_j$ is a ratio of covariances; inflation acts only through $k$ and $a$ in step 1. That holds for a factor common to $x_j$ and $y$. With DART's spatially varying $\lambda$, inflating $x_j$ by $\sqrt{\lambda_j}$ and $y$ by the inflation of the elements under H changes $b_j$ by the ratio of the two.

### 4.3 What the regression assumes

- **A straight line through the joint prior.** This is exact for a Gaussian joint prior and fine for interpolation-type H (T2 against the T2 field). For a curved relation it is a linearization over the prior range (A03 Figs. 1–3). In our radar setup, H is REFL_10CM itself (walkthrough Sec. 5), so the curved relation is between REFL_10CM and the mixing ratios, and only the regression sees it.
- **Small increments are better.** The linearization is local, so large observation increments make it worse (A03 Sec. 4c). Among all updates that give the posterior mean and variance, shift-and-shrink has the smallest sum of squared increments (minimizing $\sum_n (y^u_n-y_n)^2$ under those two constraints gives exactly (6)). A perturbed-observation EnKF pairs members at random unless sorted; A03's example shows increments of 3.9, 1.6, −5.8 becoming 0.2, −0.1, −0.4 after sorting.
- **Sample statistics.** $c_j$ and $\sigma_y^2$ come from $N$ members, so $b_j$ carries sampling error. Localization and the sampling-error correction deal with it (Sec. 5).

## 5. Small ensembles, large state: localization

### 5.1 The Gaspari–Cohn weight

A01 Sec. 2f follows HM01 and multiplies the state–observation covariance by the fifth-order function of GC99 (4.10) with half-width $c$; AC07 Sec. 3d multiplies the regression coefficient, which is the same thing. DART's function is `comp_cov_factor` (`cov_cutoff_mod.f90:42–173`, `select_localization = 1`, `:122`): weight 1 at distance 0, 0.208 at $c$, 0 from $2c$ on. GSI's `taper` (`covlocal.f90:50–65`) is the same function written with $r = d/(2c)$; the two agree to 1e-15 (Sec. 12, check 8).

DART's distance between an observation and a state element (`location_mod.f90`, `get_dist`, around `:535–541`):

$$
z = \sqrt{z_h^2 + \big(\Delta v/v_{\rm norm}\big)^2} \tag{12}
$$

- $z_h$ is the great-circle distance in radians.
- $\Delta v$ is the vertical difference in the localization coordinate: for us scale height (`vert_localization_coord = 4`), which WRF's `model_mod` computes as $-\ln(p/p_{\rm sfc})$ at each location (e.g. `model_mod.f90:3107`).
- $v_{\rm norm}$ is `vert_normalization_scale_height` = 10.6; the radar types use 177 (`special_vert_normalization_scale_heights` in `input.nml.filter_joint`).

Our values: `cutoff` = 0.0235 rad, so $c$ = 150 km, zero weight at 299 km horizontally and at $2 \times 0.0235 \times 10.6$ = 0.50 scale height vertically. Radar: `special_localization_cutoffs` = 0.001413, so zero weight at 18.0 km and at $2 \times 0.001413 \times 177$ = 0.50 scale height. These are HRRRDAS's zero-weight distances (`obs_expansion.md`, "EnKF"), but the 3-D shape differs (Sec. 10.3).

### 5.2 Where DART applies the weight

- **Only in step 2.** The observation-space increment of the observation itself is not localized, and neither is $\sigma_y^2$ in $b_j$. For one observation that is what HM01's (6) gives too, since its weight on $\mathbf H\mathbf P\mathbf H^T$ is 1 at distance zero.
- **On the H(x) of later observations too** (OBS_UPDATE, Sec. 7.3), with the observation–observation distance.
- **Together with the impact table:** $\kappa$ = GC weight × impact factor (`cov_and_impact_factors`, `:2065–2100`). An element with $\kappa = 0$ is skipped entirely, inflation included (`:787`).
- **Search radius:** `get_close_init` is set up with $2c$ (`:555–566`; `2.0*cutoff_list` for the special types), so only elements with a nonzero weight are visited.

### 5.3 Sampling-error correction and inflation

- **SEC** multiplies $b_j$ by $S_j(\hat r, N)$, between 0 and 1 (`dart_sampling_error_correction.md`). At $N = 5$ it is the stronger damping: $S$ = 0.25 at a sample correlation of 0.7.
- **Prior inflation** widens the ensemble before H(x) is computed. It acts on $k$ and $a$ through $\sigma_y^2$ and on $b_j$ through the spatially varying $\lambda$ (`dart_adaptive_inflation.md`).

## 6. Many observations: the sequential and the parallel algorithm (AC07)

### 6.1 The two algorithms

- **Sequential** (A03; AC07 Sec. 3a, Fig. 1): for observation $k$, apply $h_k$ to the state as updated by observations 1 to $k-1$, compute the increments, regress them onto the state.
- **Parallel** (AC07 Sec. 3b, Figs. 2–3): apply all $h_k$ to the prior state first. After observation $k$, regress its increments onto the state **and onto the H(x) ensembles of the observations not yet used**:

$$
y^{\,j}_n \leftarrow y^{\,j}_n + \kappa_{jk}\,S_{jk}\,b_{jk}\,\Delta y^{\,k}_n, \qquad j > k \tag{13}
$$

(AC07 (3.13), here with DART's $\kappa$ and $S$.) For linear $h$ the two algorithms give the same answer; for nonlinear $h$ they are different linear approximations (AC07 abstract). In check 9 (Sec. 12; $y = x^2$, 20 members), the analysis means differ by 4–12 % of the mean increment. The parallel algorithm is what DART runs, and GSI-EnKF too (`enkf.f90:10–31`).

**Both are serial in the observations.** The names are AC07's and describe the computing, not the order of the observations: both algorithms take one observation at a time. In the parallel one, the H(x) of the observations not yet used are updated by regression like state elements, at the cost of the extra regressions onto them ($O(K^2)$ for $K$ observations, AC07 Sec. 3c; with localization only the close ones). What that buys (AC07 Sec. 4):
- The forward operators run once, for all observations and members together, right after the model advance, while each member's state is still in one place ("state-complete").
- One transpose to "ensemble-complete" storage (all members of an element on one rank) before the loop; then, for each observation, every rank updates its own state elements and H(x) (Sec. 7.4). In the sequential algorithm $h_k$ needs the member states as updated by the observations before $k$, so a direct implementation needs a pair of transposes for every observation.

What stays serial is the observation increment, one observation after another, which AC07 call the rate-limiting part (Sec. 4a). They note that observations more than $2c$ apart could get their increments concurrently; DART doesn't do that (one broadcast per observation, `:583–672`). The distinction that changes the result, serial against simultaneous (all observations at once: the batch update, the ETKF, the LETKF), is Sec. 6.2.

DART's loop (Sec. 7.3 has the line numbers):

```
 all H(x) computed once, before the loop (filter_mod)
      v
 for each observation k, in obs_seq order:
   owner rank broadcasts y^k (current) and QC
   every rank: Delta y^k = EAKF(y^k, y_o, sigma_o^2)          (7)
   every rank, its own state elements within 2c:
      x_j += kappa * S * b * Delta y^k                        (9)
      update lambda_j (adaptive inflation)
   every rank, its own obs j > k within 2c:
      y^j += kappa * S * b * Delta y^k                        (13)
      v
 posterior H(x) recomputed from the analysis (filter_mod)
```

### 6.2 What serial processing preserves

**Without localization, linear H** (check 2: 30 state elements, 20 observations, $N$ = 10):

| quantity | serial vs Kalman | order A vs B |
|---|---|---|
| analysis mean | 2e-15 | 8e-16 |
| analysis covariance | 2e-15 | 2e-16 |
| members | | 0.09 |

The deviations themselves are up to 1.2, so a different order gives a different but equally valid square root: the same mean and covariance, other members.

**With localization** this no longer holds. Localization is not part of Kalman-filter theory (HZ16 Sec. 3e(1)), and three things follow:
1. **The covariance update is inconsistent.** The Potter factor $a$ in (6) assumes the unlocalized covariance. With a smooth taper, the localized update no longer satisfies (3) for the covariance (WH02 p. 1919, who still found the Gaspari–Cohn taper more accurate than a step function; N15 Sec. 2c, (22)–(24)).
2. **The inconsistency accumulates.** Each serial step hands its covariance to the next observation, while a simultaneous filter like the LETKF updates the covariance once (N15 Sec. 2c).
3. **The result depends on the order** (HM01; HZ16 Sec. 2c(1), "moderate amplitude changes"), and the analysis can become unstable when observations are accurate relative to the spread (N15 Secs. 4–5).

Check 4 shows the size of these effects in a single analysis (no cycling). A 40-point periodic domain, every point observed; the true covariance is Gaussian with length 3 points and $\sigma_b = 1$; the ensemble is drawn from it; the Gaspari–Cohn half-width is 5 points (zero at 10) for every method, not tuned per method; 300 trials. The numbers are the RMS error of the analysis mean (prior about 0.95–0.98):

$N$ = 5:

| $\sigma_o$ | KF² | serial | batch³ | LETKF | order⁴ |
|---|---|---|---|---|---|
| 1.0 | 0.441 | 0.510 | 0.513 | 0.518 | 0.118 |
| 0.3 | 0.163 | 0.212 | 0.199 | 0.253 | 0.127 |
| 0.1 | 0.061 | 0.091 | 0.075 | 0.172 | 0.088 |

$N$ = 20:

| $\sigma_o$ | KF² | serial | batch³ | LETKF | order⁴ |
|---|---|---|---|---|---|
| 1.0 | 0.423 | 0.442 | 0.449 | 0.437 | 0.104 |
| 0.3 | 0.165 | 0.180 | 0.184 | 0.172 | 0.102 |
| 0.1 | 0.061 | 0.074 | 0.071 | 0.064 | 0.064 |

² Kalman filter with the true covariance. ³ Simultaneous update with the localized ensemble covariance, $(\rho\circ\mathbf P)(\rho\circ\mathbf P+\mathbf R)^{-1}$. ⁴ RMS difference between the analysis means from the forward and the reversed observation order.

The standard errors of the paired differences to the serial EAKF are 0.0004–0.005. So:
- **Serial loses to batch only for accurate observations.** At $\sigma_o/\sigma_b$ = 0.1 the serial EAKF is worse than the batch update (0.091 against 0.075 at $N$ = 5); at $\sigma_o$ = 1 it is as good or slightly better. This matches N15 in direction, though their cycled runs are more nuanced: at $\sigma_o$ = 0.1 with a support radius below 18 points, the serial EnSRF had about 2 % smaller errors than the batch EnSRF; with wider localization or less inflation the batch version had smaller errors and diverged less (N15 Sec. 4).
- **The order changes each analysis but not the average.** Forward and reversed orders have the same mean error within 0.002, yet a single analysis differs between them by 0.06–0.13 RMS, comparable to the analysis error itself for accurate observations.
- **LETKF with the same taper** is the best at $N$ = 20 and the worst at $N$ = 5 for accurate observations. Localizing R with a given width is weaker than localizing the covariance (Sec. 9.5), which hurts when 5 members give noisy covariances; G11 and HW13 find the best R-localization length shorter than the best B-localization length.
- **GSI's EnSRF** (not in the tables) is identical to the serial EAKF in every trial (difference below 1e-8).

## 7. DART's implementation, step by step

### 7.1 Where `filter_assim` sits

`filter_main` calls `filter_assim` once per pass (`filter_mod.f90:905`), after the prior inflation and the forward operators and before the posterior output (walkthrough Sec. 2, steps 1–9). We run one pass per cycle, with `num_groups = 1` (one group of $N$ members).

### 7.2 Set-up (`filter_assim`, `:309–582`)

1. **Groups:** `grp_size = ens_size/num_groups` (`:436`).
2. **Inflation copy:** the current $\lambda$ is copied into the sd copy (`:458`).
3. **Observation locations:** each rank gets its own observations' locations (`:478`) and converts their verticals to scale height (`convert_all_obs_verticals_first = .true.`, `:480–492`).
4. **State:** each rank gets its state elements' locations and kinds and transforms them to "probit space" (`:499–512`). With no QCEFF table every kind is `NORMAL_DISTRIBUTION` and the transform is the identity (`probit_transform_mod.f90:103–105`). Our `convert_all_state_verticals_first = .true.` converts all verticals up front (`:515–520`).
5. **Frozen H(x) statistics for inflation:** mean and variance of every observation's prior, before any is assimilated (`:524–531`).
6. **H(x) to probit space** (identity, `:537–552`).
7. **Search structures** with radius $2c$ (`:555–566`).

### 7.3 For each observation (`SEQUENTIAL_OBS`, `:585–836`)

1. **Read** the observation, its error variance and its type (`:603–614`).
2. **Owner** (the rank holding this observation, `:617–650`): reads its QC and frozen prior statistics, transforms its H(x) back from probit space (identity), and broadcasts H(x), QC and the inflation values (`:658–672`).
3. **QC:** every rank skips the observation unless its DART QC is 0 (`:676`).
4. **Observation increment** (`obs_increment`, `:686` → `:912`):
   - prior mean and variance (`:947–948`);
   - `obs_inc_info` picks the method for the observation's quantity (`:971`); without a QCEFF table it returns EAKF, unbounded (`algorithm_info_mod.f90:500–504`);
   - special cases (`:979–998`): both variances zero stops filter; $\sigma_o^2 = 0$ sets every member to the observed value; $\sigma_y^2 = 0$ gives no increment (radar where every member sits at the −10 dBZ floor, walkthrough Sec. 5);
   - `obs_increment_eakf` (`:1006` → `:1113`), Eqs. (6)–(7).
5. **Probit round trip:** `obs_post = obs_prior + obs_inc`, both to probit space, `obs_inc` recomputed as their difference (`:689–723`). With normal distributions this is the identity, up to float32 rounding of the addition and subtraction.
6. **Regression statistics:** $\bar y$ and $\sigma_y^2$ for the regression, from the current H(x) ensemble (`:726–728`).
7. **Close observations and state elements:** `get_close_obs_cached` (`:744`), the cutoff for this type (`:753–757`), adaptive localization (off, `:760`), `get_close_state_cached` (`:765`).
8. **State update** (`STATE_UPDATE`, `:772–806`), for each close state element:
   - skip it if its probit transform failed or it has missing values (`:776–781`);
   - $\kappa$ = `cov_and_impact_factors` (`:784`); skip if $\kappa \le 0$ (`:787`);
   - `obs_updates_ens` (`:789` → `:2005`) calls `update_from_obs_inc` (`:1472`): $c_j$ (`:1495`), $b_j$ (`:1498`), the sample correlation for inflation and SEC (`:1511–1530`), SEC (`:1534–1543`), increment $b_j\,\Delta y_n$ (`:1548`); then `ens = ens + final_factor * increment` (`:2059`), Eq. (9);
   - the element's $\lambda$ is updated (`:796–805`).
9. **H(x) update of later observations** (`OBS_UPDATE`, `:808–835`): only observations with a later global index (`my_obs_indx(obs_index) > i`, `:817`), with the same regression and the observation–observation $\kappa$, Eq. (13).
10. **After the loop:** inverse probit transform of the state (`:839`, identity).

### 7.4 Parallel layout

Observations are owned by single ranks, state elements are spread over all ranks. The owner broadcasts the H(x) ensemble; every rank then computes the same $\Delta y_n$ and updates only its own state elements and observations (walkthrough Sec. 3, item 1). The result doesn't depend on how the state is split, which AC07 (abstract) show for their algorithm and our scaling test confirmed: 8 × 16, 40 × 16 and 40 × 32 ranks gave bit-identical analyses (CLAUDE.md).

### 7.5 Namelist items that touch the EAKF

| item | ours | effect |
|---|---|---|
| `cutoff` | 0.0235 | half-width $c$ (rad) |
| `special_localization_*` | radar 0.001413 | $c$ per type |
| `sort_obs_inc` | `.false.` | EnKF only (`:1362`) |
| `spread_restoration` | `.false.` | `.true.` stops filter |
| `sampling_error_correction` | `.true.` | $S_j$ |
| `adjust_obs_impact` | `.true.` | factor in $\kappa$ |
| `select_localization` | 1 | Gaspari–Cohn |
| `qceff_table_filename` | `''` | EAKF, normal |
| `num_groups` | 1 | no group filter |

Notes:
- `sort_obs_inc` defaults to `.true.` in the code (`:139`) but only `obs_increment_enkf` uses it, so it has no effect on the EAKF.
- `spread_restoration = .true.` gives "not supported in this version" and stops (`:241–245`).
- Special cutoffs switch off the close-observation caching (`:290–293`).

### 7.6 QCEFF: the EAKF as a special case

The current code is organized around the quantile-conserving ensemble filtering framework (G+25; Anderson 2022, 2023, 2024):
- step 1 can use other filters per quantity (`filter_kind`: EAKF, EnKF, rank histogram, bounded normal RHF, gamma, kernel, particle, KDE; `:1005–1058`);
- the regression of step 2 is done in a transformed ("probit") space chosen per quantity.

The EAKF is the Gaussian case: (6) keeps every member's quantile (Sec. 3.2), and the probit transform of a normal distribution is the identity. With `qceff_table_filename = ''` we run exactly the EAKF of A01/A03, and the QCEFF papers aren't needed to follow it.

### 7.7 What doesn't apply to us

- Observation-space inflation (`do_obs_inflate`, `:953–968`): not supported in this version (`adaptive_inflate_mod.f90:462`, `validate_inflate_options`).
- Groups (`num_groups > 1`, `comp_reg_factor`, `:2052–2056`): off.
- Adaptive localization (`adaptive_localization_threshold = -1`): off.

### 7.8 Precision

Our DART runs in float32 (`r8 = r4`, `types_mod.f90:85`). DART computes the new mean as `var_ratio*(prior_mean + prior_var*obs/obs_var)`, a sum of two large terms, instead of the innovation form $\bar y + k\,d$. Check 7 emulates both in float32, against a float64 reference (median and maximum absolute error over 4000 cases, 5 members):

| variable | float32 unit | DART form | innovation form |
|---|---|---|---|
| altimeter, hPa | 6e-5 | 4e-5, 2e-4 | 2e-5, 1e-4 |
| T2, K | 3e-5 | 1e-5, 7e-5 | 9e-6, 5e-5 |
| dBZ | 4e-6 | 2e-6, 8e-6 | 1e-6, 5e-6 |

DART's form loses about 1.5–2 times more, but both stay within a few float32 units of the value, against typical increments of 0.25 hPa, 0.3 K and 4 dBZ. Not an issue.

## 8. The papers against the code

| item | paper | DART code |
|---|---|---|
| obs-space step | A01 (16): matrix $\mathbf A$ | scalar, (6) |
| state step | A01: per pair; A03 (6) | (9) |
| many obs | A03 sequential | AC07 parallel |
| localization | A01 Sec. 2f, AC07 Sec. 3d | GC on $b_j$ |
| H(x) updates | AC07 (3.13): all later | later, within $2c$ |
| inflation | A01: fixed, tuned | adaptive $\lambda$ |
| sampling error | A01: none | SEC (A12) |

Notes:
- **A01's Appendix A** builds the adjustment matrix from an SVD of the prior covariance and of $\mathbf H^T\mathbf R^{-1}\mathbf H$: $\mathbf\Sigma_u = \mathbf A\mathbf\Sigma\mathbf A^T$ with $\mathbf A = (\mathbf F^T)^{-1}\mathbf G^T(\mathbf U^T)^{-1}\mathbf B^T(\mathbf G^T)^{-1}\mathbf F^T = \mathbf F\mathbf G\mathbf U\mathbf B\mathbf G^{-1}\mathbf F^T$ (checked on the rendered page, A01 p. 2901). Three readings, in check 1:
  - **As printed,** the members are updated with $\mathbf A^T$: $z^u_i = \mathbf A^T(z^p_i-\bar z^p)+\bar z^u$ (A01 (16) and App. A). That gives covariance $\mathbf A^T\mathbf\Sigma\mathbf A$, not $\mathbf\Sigma_u$: the error is 12.8 in check 1. A transpose slip; A03 (17) and T03 (17) write the update with $\mathbf A$.
  - **With $\mathbf A$** the mean and covariance are right (3e-15), but the members differ from DART's (up to 1.16, against increments up to 1.41).
  - **With a trailing $\mathbf U^T$,** $\mathbf A = \mathbf F\mathbf G\mathbf U\mathbf B\mathbf U^T\mathbf G^{-1}\mathbf F^T$ reproduces DART's update to 6e-15.

  T03 (18)–(20) use the form without $\mathbf U^T$ and note that the EAKF and ETKF ensembles then differ by an orthogonal rotation. The reference for what DART computes is A03 (19)–(27), and A01 Sec. 2c already used the scalar, pairwise form in its experiments.
- **AC07's H(x) update** covers all later observations; DART only visits those within $2c$, which is the same since the weight is zero beyond.

## 9. The other ensemble filters

### 9.1 The family

| filter | ensemble update | processing | localization |
|---|---|---|---|
| EnKF (HM98, B98) | perturbed obs | serial/batches | B |
| EAKF (A01, A03) | shift and shrink | serial | B (on $b_j$) |
| EnSRF (WH02) | reduced gain | serial | B |
| ETKF (B01) | ensemble-space root | all at once | none |
| LETKF (H07) | ensemble-space root | local, all at once | R |

"B" localizes the background covariance (here: the regression), "R" the observation-error covariance (HZ16 Table 2, G11). Without localization all give the Kalman mean and covariance of the ensemble, the EnKF only on average (T03).

### 9.2 The perturbed-observation EnKF (HM98, B98)

Each member is updated towards its own perturbed observation:

$$
y_n^u = y_n + k\,\big(y_o + \epsilon_n - y_n\big), \qquad \epsilon_n \sim \mathcal N(0, \sigma_o^2) \tag{14}
$$

(A01 Sec. 2b(3); WH02 (4)–(5) with $\tilde{\mathbf K} = \mathbf K$). Without the $\epsilon_n$ the analysis covariance would be $(\mathbf I-\mathbf K\mathbf H)\mathbf P(\mathbf I-\mathbf K\mathbf H)^T$, which lacks $\mathbf K\mathbf R\mathbf K^T$ (B98; WH02 (6)); with them it is right in expectation, plus sampling noise (WH02 (7)). DART has it as `obs_increment_enkf` (`:1307–1381`): the perturbations are re-centred to mean $y_o$ (`:1348–1349`) and optionally sorted (`:1362–1370`, A03 Sec. 4c).

Check 5 repeats WH02's scalar test ($\sigma_b^2 = 1$, $\sigma_o^2 = 1$, exact posterior variance 0.5):

| $N$ | filter | mean $P_a$ | mean abs. error |
|---|---|---|---|
| 5 | EAKF | 0.444 | 0.143 |
| 5 | EnKF⁵ | 0.444 | 0.244 |
| 5 | EnKF, DART⁶ | 0.443 | 0.268 |
| 13 | EnKF⁵ | 0.481 | 0.141 |
| 50 | EAKF | 0.495 | 0.040 |
| 50 | EnKF⁵ | 0.496 | 0.069 |

⁵ WH02's perturbations, re-centred to zero mean and unit variance. ⁶ DART's, re-centred only.

These match WH02 Sec. 2b: mean 0.44 for both, mean absolute error 0.14 against 0.24, and a 13-member EnKF needed to match a 5-member deterministic filter. Two lessons:
- **Every Kalman-type filter underestimates $P_a$ with a small ensemble** (0.44 instead of 0.5 at $N$ = 5), because $P_a$ is a nonlinear function of the sampled $P_b$ (WH02 Sec. 2b). This is one reason all of them need inflation.
- **Perturbed observations add noise on top.** In low-order tests the EAKF beat the EnKF (A01 Sec. 3: rms 0.390 against 0.476 with 20 members, and the EnKF needed inflation 1.08–1.16 against 1.005–1.02), and so did the EnSRF (WH02 Sec. 4: minimum error 0.20 against 0.26).

### 9.3 The serial EnSRF (WH02): HRRRDAS's filter

WH02 update the mean with the Kalman gain and the deviations with a reduced gain (WH02 (4), (5), (13)):

$$
\begin{aligned}
\bar x_a &= \bar x_b + K\,d\\
x'_a &= x'_b - \tilde K\,y'\\
\tilde K &= K/(1+a)
\end{aligned} \tag{15}
$$

(WH02's $\alpha = 1/(1+a)$, with $a$ as in (6); the Potter algorithm.) Since $(1-a)(1+a) = 1-a^2 = k$,

$$
\frac{1-a}{\sigma_y^2} = \frac{1}{(\sigma_y^2+\sigma_o^2)(1+a)} \tag{16}
$$

so $-\tilde K_j\,y' = (a-1)\,b_j\,y'$, which is the EAKF deviation update (10); the mean updates are the same Kalman gain. The two methods are therefore **algebraically identical, member by member**, and stay so with localization, because both multiply the whole state increment by the weight. N15 Sec. 1 ("algorithmically identical in case of serial observation processing") and G+25 say the same.

GSI's code (`enkf.f90`): `obganl = -anal_obtmp/(one+sqrt(oberrvaruse(nob)*hpfhtoberrinv))` (`:469`) is $-y'/(1+a)$; `hpfhtcon = hpfhtoberrinv*r_nanalsm1` (`:533`); for each close grid point and level, `kfgain = taperv*sum(anal_chunk*anal_obtmp)` (`:652`), then `ensmean += kfgain*obinc` and `anal_chunk += kfgain*obganl` (`:654–656`). A line-by-line translation agrees with DART's update to 1e-15 without localization and below 1e-8 with it (checks 1, 2, 4).

### 9.4 The ETKF and the square-root family

The ETKF does the update in the $N$-dimensional space of the ensemble (B01 (18b); H07 (21), (24)):

$$
\begin{aligned}
\tilde{\mathbf P}_a &= \big[(N-1)\mathbf I + \mathbf Y^T\mathbf R^{-1}\mathbf Y\big]^{-1}\\
\mathbf W &= \big[(N-1)\tilde{\mathbf P}_a\big]^{1/2}
\end{aligned} \tag{17}
$$

and the analysis deviations are $\mathbf X\mathbf W$. B01 used $\mathbf C(\boldsymbol\Gamma+\mathbf I)^{-1/2}$ from the eigendecomposition; H07 use the symmetric square root, which keeps the mean and changes the deviations as little as possible (H07 Sec. 2.3.3).

- **One observation:** $\mathbf Y$ is a single row $y'$, and $\mathbf W = \mathbf I + (a-1)\,y'^T y'/\lVert y'\rVert^2$. Since $\mathbf X y'^T = (N-1)\,c$ and $\lVert y'\rVert^2 = (N-1)\,\sigma_y^2$, $\mathbf X\mathbf W = \mathbf X + (a-1)\,b\,y'$: the symmetric ETKF **is** the EAKF (check 1: 7e-16).
- **Many observations at once:** same mean and covariance as the serial EAKF, different members (check 2: 0.11 against deviations of 1.2). T03 Sec. 3a: the methods "produce different analysis ensembles that span the same state-space subspace and have the same covariance".
- **Cost** (T03 Table 1, $m$ members, $n$ state elements, $p$ observations): serial $O(mp + mnp)$; ETKF and EAKF in batch form $O(m^2p + m^3 + m^2n)$. The serial filter is cheap in the ensemble size and expensive in observations × state elements reached; localization cuts the second factor.

### 9.5 The LETKF (H07)

The LETKF does an ETKF analysis for each grid point (or column) separately, with the observations around it, and localizes by weighting $\mathbf R^{-1}$ (H07 Secs. 2.3, 3; GSI `letkf.f90:433`, `:741`):

$$
\begin{aligned}
\tilde{\mathbf P}_a &= \big[(N-1)\mathbf I/\rho + \mathbf Y^T\tilde{\mathbf R}^{-1}\mathbf Y\big]^{-1}\\
\bar{\mathbf w} &= \tilde{\mathbf P}_a\,\mathbf Y^T\tilde{\mathbf R}^{-1}(\mathbf y_o-\bar{\mathbf y})\\
\mathbf x^a_n &= \bar{\mathbf x} + \mathbf X\,(\bar{\mathbf w} + \mathbf w_n)
\end{aligned} \tag{18}
$$

with $\tilde{\mathbf R}^{-1} = \operatorname{diag}(\kappa_i/\sigma_{o,i}^2)$, $\rho$ a multiplicative inflation and $\mathbf w_n$ the columns of $\mathbf W$ from (17) (H07 (20)–(25), Step 5). H(x) is linearized as $\bar{\mathbf y} + \mathbf Y\mathbf w$, which H07 Sec. 2.3.1 call "equivalent to the joint state-observation space method" of A01.

How it differs from DART's serial EAKF:

1. **R-localization is weaker than B-localization at the same weight.** For one observation at weight $\kappa$, the serial EAKF's gain is $\kappa\,c/(\sigma_y^2+\sigma_o^2)$; the LETKF's is $c/(\sigma_y^2+\sigma_o^2/\kappa)$. The table below gives both relative to the unlocalized gain (check 3). The more accurate the observation, the less R-localization damps it. So the best R-localization length is shorter than the best B-localization length (G11; HW13 Sec. 3: 4000 km against 5000–6000 km), and with each at its best the two are comparable (G11; HZ16 Sec. 3e(2)).
2. **Simultaneous:** all local observations at once, so no order dependence, no accumulated inconsistency (Sec. 6.2), and no H(x) updates during the analysis.
3. **Local and parallel:** each grid point is independent; the symmetric root makes the weights vary smoothly between neighbouring points (H07 Sec. 2.3.3–2.3.4). The cost is an $N \times N$ eigenproblem per local analysis.
4. **Not in DART:** G+25 explain that DART's serial design "avoids matrix operations central to the LETKF". GSI-EnKF has both: `letkf_flag = .true.` calls `letkf_update` instead of `enkf_update` (GSI `enkf_main.f90:207–213`), in the gain form of B17, which also allows model-space vertical localization with modulated ensembles.

Gain at localization weight $\kappa$, relative to the unlocalized gain (item 1):

| $\kappa$ | $\sigma_y^2/\sigma_o^2$ | B (EAKF) | R (LETKF) |
|---|---|---|---|
| 0.5 | 0.25 | 0.50 | 0.56 |
| 0.5 | 1 | 0.50 | 0.67 |
| 0.5 | 4 | 0.50 | 0.83 |
| 0.5 | 16 | 0.50 | 0.94 |
| 0.25 | 4 | 0.25 | 0.63 |

### 9.6 Head-to-head comparisons in the literature

- **HW13** (two-layer primitive-equation model, imperfect model): the simultaneous R-localized schemes (including the LETKF) had the lowest analysis error, the simultaneous B-localized scheme the highest, the two serial schemes were in between. With B-localization serial beat simultaneous; with R-localization simultaneous beat serial. The differences came through analysis imbalance and shrank with digital-filter initialization, wind as well as mass observations, fewer observations, a larger ensemble and a smaller $\mathbf H\mathbf P_b\mathbf H^T/\mathbf R$ (HW13 Sec. 3, Sec. 6).
- **N15** (Lorenz-96): the serial EnSRF was clearly worse and less stable than the LETKF when $\sigma_o$ was 4 % of the initial error estimate, and similar at 40 %. Reordering the observations did not fix it on average. For realistic large-scale cases N15 expects no significant effect, with one exception: "In the atmosphere a situation might appear with convective-scale models, when some ensemble members estimate convection while others do not. When in this situation accurate observations are assimilated, the effect of serial observation processing might deteriorate the assimilation performance." (N15 Sec. 7.)
- **HZ16** Sec. 2e: intercomparisons found the EnSRF and LETKF of comparable quality. Their Table 1 (2015): NCEP ran a deterministic EnSRF operationally (80 members), CMC a stochastic EnKF (256), ECMWF an LETKF for research (100).
- **G11:** B-localization disturbs geostrophic balance more at the same length scale; at each method's best length the two are comparable in accuracy and balance.

## 10. HRRRDAS's EnKF next to ours

### 10.1 What HRRRDAS runs

From `scripts/hrrrdas/exhrrr_enkf.sh`, `parm/hrrrdas/hrrrdas_enkf_wrf_namelist.sh`, D20 and D22 (Sec. 3d, Table 5):
- **Filter:** GSI-EnKF `enkf_update` with `deterministic = .true.`, i.e. WH02's serial EnSRF, implemented with AC07's parallel algorithm (`enkf.f90:10–31`). D22: "specifically the ensemble square-root filter (EnSRF; Tippett et al. 2003)".
- **Ensemble and cycle:** 36 members, hourly; two EnKF runs per hour, conventional observations first, then MRMS reflectivity on the 3-km domain.
- **Localization:** `corrlength` 300 km and `lnsigcutoff` 0.5 for the conventional pass, 18 km and 0.5 for radar, both zero-weight distances.
- **Inflation:** no prior inflation (`covinflate* = 0`); RTPS with `analpertwt` 1.20 on the 15-km domain and 1.08 on the 3-km domain, after each pass (`inflation.f90:198`; `enkf_main.f90` calls `inflate_ens` after every update).
- **Other settings:**
  - `iassim_order = 0`: observations in the order read.
  - `paoverpb_thresh = 2.0`: no adaptive thinning.
  - `sortinc = .true.`: used only by the perturbed-observation branch (`enkf.f90:471–512`), so no effect.
  - `numiter = 6`: with no satellite bias correction and `varqc = .false.`, each iteration restarts from the prior H(x) (`enkf.f90:270–288`) and only the last updates the state (`:543`). As read from the code, the result is that of `numiter = 1`, at extra cost.
  - `sprd_tol = 1e30`: the EnKF itself rejects nothing; quality control is done by the GSI observer (D20).
- **Analysis variables** (D20; D22 Table 5): U, V, T, QVAPOR, QCLOUD from conventional observations; QRAIN, QSNOW, QGRAUPEL added for radar; QNRAIN set afterwards from QRAIN.
- **Precision:** single (`r_single`).

RTPS (WH12 (2)–(3)) relaxes the posterior spread toward the prior spread, element by element:

$$
\begin{aligned}
\sigma &\leftarrow (1-\alpha)\,\sigma_a + \alpha\,\sigma_b\\
x'_a &\leftarrow x'_a\Big[1+\alpha\,\frac{\sigma_b-\sigma_a}{\sigma_a}\Big]
\end{aligned} \tag{19}
$$

The second line is the first applied to each member's deviation from the posterior mean. With α = 1.08 the spread ends up at $\sigma_b + 0.08\,(\sigma_b-\sigma_a)$, slightly **above** the prior spread wherever observations reduced it; D20 calls a factor above 1 "atypical". Where no observation reached, $\sigma_a = \sigma_b$ and nothing changes.

### 10.2 The same update

Checks 1, 2 and 4 translate GSI's update and compare it with DART's: identical to round-off, member by member, with and without localization. Any difference between our analyses and HRRRDAS-like behaviour therefore comes from what surrounds the update, not from the update.

### 10.3 What differs

Settings:

| item | HRRRDAS | ours |
|---|---|---|
| members | 36 | 5 (50 planned) |
| cycle | 1 h | 15 min |
| passes | 2 (conv., radar) | 1 (joint) |
| inflation | RTPS 1.08, posterior | adaptive prior λ |
| SEC | no | yes |
| QC | GSI observer | outlier 3σ |

Algorithm details:

| item | GSI-EnKF | DART |
|---|---|---|
| 3-D weight | GC(h) × GC(v) | GC of (12) |
| vertical coordinate | $\ln p$ | $-\ln(p/p_{\rm sfc})$ |
| H(x) updated | all close obs | later close obs |
| horizontal distance | chord | great circle |

- **3-D weight.** GSI multiplies a horizontal and a vertical taper (`enkf.f90:615`, `:640–642`); DART takes one taper of the combined distance (12). Both are zero at 300 km and at 0.5 scale height, and they agree along the axes, but DART's weight is smaller off the axes (table below, check 8).
- **Vertical coordinate.** DART's scale height is relative to each location's own surface pressure, so it follows the terrain; GSI's $\ln p$ does not.
- **H(x) updates.** GSI also updates observations already assimilated (`enkf.f90:679–720`), which it uses for its posterior statistics; DART recomputes the posterior H(x) from the analysis instead.

Conventional-observation weights, $d_v$ in scale heights:

| $d_h$ (km) | $d_v$ | DART | GSI |
|---|---|---|---|
| 75 | 0.125 | 0.466 | 0.469 |
| 75 | 0.25 | 0.133 | 0.143 |
| 150 | 0.125 | 0.133 | 0.143 |
| 150 | 0.25 | 0.029 | 0.043 |
| 225 | 0.25 | 0.000 | 0.003 |

## 11. What this means for our runs

1. **Our update is HRRRDAS's update.** Differences from HRRRDAS-like behaviour come from the surroundings: inflation (adaptive prior λ against RTPS 1.08), the sampling-error correction (strong at $N$ = 5), 5 against 36 members, one pass against two, 15-minute against hourly cycling. To mimic HRRRDAS's inflation, DART has RTPS as posterior flavor 4: `inf_flavor(2) = 4`, α = `inf_initial(2)`. It forces deterministic inflation, no damping and no restart file (`adaptive_inflate_mod.f90:477–499`), uses GSI's formula (`:551–552`), and nothing in the validation found here stops α above 1. RTPS is already on the list (discussion log, 2026-10-23).
2. **Radar is where serial processing is weakest.** MRMS observations are accurate relative to the spread in convective areas: at $\sigma_y$ = 10–15 dBZ against 5 dBZ, one observation takes 80–90 % of the innovation and removes 55–68 % of the spread (Sec. 3.3). They are also dense: every 5 km, with an 18-km radius. That is N15's warning case. Check 4 at $\sigma_o/\sigma_b$ = 0.1 had the serial EAKF 20 % worse than the batch update at $N$ = 5, and single analyses changing by about the size of their error under a reversed order. Possible diagnostics: rerun one cycle with the MRMS observations reversed in `obs_seq.joint` and compare the analyses; look at the radar posterior spread against its prior. At $N$ = 5 the sampling-error correction limits each radar observation's reach, which helps here.
3. **The EAKF is the right choice at $N$ = 5.** Its analysis-variance error is half the perturbed-observation EnKF's (Sec. 9.2). It still underestimates $P_a$ on average (0.44 instead of 0.5), so inflation remains necessary.
4. **Members stay continuous.** Of all updates that give the posterior mean and variance, shift-and-shrink has the smallest increments (Sec. 4.3), and it keeps the members' order, which suits true WRF restarts.
5. **Our H(x) are close to linear in the state.** T2, Q2, U10, V10 and REFL_10CM are interpolations of state fields, so the parallel algorithm's regression update of later H(x) is nearly exact for them. The exceptions are the −10 dBZ floor on REFL_10CM, the altimeter formula, the humidity conversions, and the temperature of ACARS and radiosondes (from THM and pressure). The curved relation that matters, between REFL_10CM and the mixing ratios, sits in the regression of step 2 either way.
6. **An LETKF would mean leaving DART.** The literature finds it comparable for conventional observations and possibly better for dense, accurate ones (N15, HW13), but with R-localization the radius would have to be retuned, since the same Gaspari–Cohn width localizes less (Sec. 9.5).
7. **From 5 to 50 members:** the sampling-error correction moves toward 1 and the regression coefficients get less noisy. The serial-processing effect depends on $\sigma_o/\sigma_b$ more than on $N$; in check 4 its gap to the batch update shrank from 20 % to 4 %.

## 12. Checks

`notes/checks/eakf_checks.py`, float64 unless noted. Run it with `uv run --no-project --with numpy python -I notes/checks/eakf_checks.py` (about 2 minutes; arguments `4` and `5` skip the two slow checks):

| # | check | result |
|---|---|---|
| 1 | one ob: DART vs GSI EnSRF, ETKF | 2e-16, 7e-16 |
| 1 | A01 App. A, $\mathbf A^T$ as printed | cov wrong by 12.8 |
| 1 | A01 App. A, $\mathbf A$ applied | mean, cov 3e-15; members 1.16 |
| 1 | A01 with $\mathbf U^T$ | 6e-15 |
| 2 | 20 obs, no loc.: serial vs Kalman | 2e-15 |
| 2 | order A vs B | mean, cov 8e-16; members 0.09 |
| 2 | serial EAKF vs ETKF | mean, cov 3e-15; members 0.11 |
| 3 | B- vs R-localized gain | Sec. 9.5 table |
| 4 | localized, 300 trials | Sec. 6.2 tables |
| 5 | WH02 scalar test | Sec. 9.2 table |
| 6 | $k$ and $a$ for our obs | Sec. 3.3 |
| 7 | float32 round-off | Sec. 7.8 |
| 8 | DART GC vs GSI taper | 1e-15; Sec. 10.3 table |
| 9 | nonlinear H, parallel vs sequential | 4–12 % of the increment |
| 10 | worked examples | Sec. 3.3 |

Set-ups: check 1, 6 state elements, $N$ = 5, an interpolation-type H; check 2, 30 elements, 20 observations at random positions, $N$ = 10, errors 0.2–1.0; check 4, as in Sec. 6.2; check 9, 6 elements, $N$ = 20, $y = x^2$ at 4 of them, prior mean 3 and variance 0.5. The DART translations follow `obs_increment_eakf`, `update_from_obs_inc` (without SEC), `obs_updates_ens` and the loop of Sec. 7.3, including the H(x) updates of later observations; the GSI translation follows `enkf.f90:424–470`, `:533`, `:640–656` and `:700–711`.
