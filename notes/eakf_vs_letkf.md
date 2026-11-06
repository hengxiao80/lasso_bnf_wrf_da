# EAKF against LETKF: the math, the code in GSI-EnKF and JEDI, and what it means for us

Written 2026-11-05 (session "learn: EAKF vs LETKF") as a walk-through of how DART's serial EAKF differs from the local ensemble transform Kalman filter (LETKF), as written down by H07 and B17 and as implemented in GSI-EnKF (`letkf.f90`) and in JEDI's GETKF, which RRFSv2 runs. It continues `dart_eakf.md` Sec. 9.4–9.6, which has the ETKF and LETKF in brief; that note stays the reference for the EAKF itself. Sec. 2 is written; Sec. 3–7 are to come.

**Sources.**
- Papers (PDFs in `notes/papers/`; labels, full references and DOIs as in `dart_eakf.md`, Sources): **H07** (the LETKF), **B01** (the ETKF), **T03** (square-root filters), **B17** (the gain form, GETKF), **WH02** (serial EnSRF), **N15** (serial against simultaneous), **G11** and **HW13** (R- against B-localization), **HZ16** (review), **A01**, **A03**, **AC07** (DART's EAKF), **G+25** (DART today). Equation numbers "H07 (n)" are the paper's.
- Cited as background, not in `notes/papers/` (checked against Crossref):
  - **N12:** Nerger, Janjić, Schröter and Hiller (2012), "A regulated localization scheme for ensemble-based Kalman filters", QJRMS 138, 802–812, doi:10.1002/qj.945. N15 (21) gives its formula, used in Sec. 2.4; HW13 cite it as "Nerger et al. (2011)".
  - **SB11:** Sakov and Bertino (2011), "Relation between two common localisation methods for the EnKF", Comput. Geosci. 15, 225–237, doi:10.1007/s10596-010-9202-6.
- Code: GSI `124138df0` (`../software/GSI/src/enkf/letkf.f90`, `params.f90`, `enkf_main.f90`), the HRRR copy `40ee6058` (`../software/HRRR/sorc/hrrr_gsi.fd/src/enkf/letkf.F90`), RRFSv2 `08eee4ce` (`../software/RRFSv2/parm/getkf_header.yaml`), DART `7bbd35a09`.
- Numbers: `notes/checks/eakf_letkf_checks.py` (Sec. 8), which reuses the DART and LETKF translations of `notes/checks/eakf_checks.py` (`dart_eakf.md` Sec. 12).

**Related notes.** `dart_eakf.md`: the EAKF (Sec. 3–7), serial against simultaneous (Sec. 6.2), the ETKF and LETKF (Sec. 9.4–9.5), HRRRDAS (Sec. 10), our runs (Sec. 11). `dart_adaptive_inflation.md`: our inflation against RTPS. `obs_expansion.md`, "EnKF": HRRRDAS's settings.

**Typora.** Display equations are `$$` blocks. Inline math (`$...$`) needs *Preferences → Markdown → Inline Math*.

---

## 0. Summary

So far (Sec. 2, the math):

- **Both filters are ensemble transforms at each state element.** The analysis members at element $j$ are the prior mean there plus the prior deviations there times an $N$-vector of mean weights and an $N \times N$ transform: $\mathbf x^a_j = \bar x_j\mathbf 1^T + \mathbf x'_j(\bar{\mathbf w}_j\mathbf 1^T + \mathbf T_j)$. For the LETKF this is its definition; for the serial EAKF it follows from the regression step, with $\mathbf T_j$ a product of one rank-one factor per observation (Sec. 2.1; check 1: 9e-16). So in both, the analysis at a point is a combination of the members' prior values at that point.
- **Without localization** the transforms agree up to a rotation: the serial product is $\mathbf T = \mathbf W\mathbf U$, with $\mathbf W$ the LETKF's symmetric root and $\mathbf U$ orthogonal, keeping the mean. The reason: in ensemble space the observations' information adds up, and each serial factor is the square root of its own term (Sec. 2.2; check 3).
- **Localization separates them in two ways** (Sec. 2.1, 2.4):
  1. *Where the weight enters.* The EAKF scales its step by $\kappa$ (B-localization); the LETKF divides $\sigma_o^2$ by $\kappa$ (R-localization). The LETKF's local update is therefore always a Kalman update, for the observation error $\sigma_o^2/\kappa$. The EAKF's is a Kalman update for no observation error: for the same mean step it removes more spread than a Kalman update would, and less than the Joseph form of N15 (22) with the raw covariance.
  2. *Which H(x).* The serial EAKF assimilates each observation with H(x) already updated by the earlier ones, with observation–observation weights. The LETKF uses the prior H(x) for all observations and has no observation–observation localization.
- **With the same Gaspari–Cohn width, R-localization is wider,** and more so for accurate observations. To put the half-gain distance where the B-localized gain has it, the R half-width has to shrink by a factor 0.80 at $\sigma_y = \sigma_o$ and 0.59 at an MRMS-like $\sigma_y/\sigma_o$ = 2.5. The effective shape tends to a step function as $\sigma_y/\sigma_o$ grows, and no distance-only function makes the two equal (Sec. 2.4; check 4; HW13).
- **The gain form (B17)** is the symmetric LETKF rewritten (check 5: 5e-15). It exists so that a modulated ensemble can supply a model-space (B-) localized gain for the raw members. For one observation at a grid point it is the B-localized EAKF (check 5: 1e-15). A GETKF with horizontal patches and modulated vertical localization is therefore R-localized horizontally and B-localized vertically (Sec. 2.5).

## 1. Notation

As in `dart_eakf.md` Sec. 1 ($N$, $\sigma_y^2$, $\sigma_o^2$, $d$, $k$, $a$, $c_j$, $b_j$, $\kappa$), plus:

| symbol | meaning |
|---|---|
| $\mathbf X$ | $M \times N$ state deviations |
| $\mathbf x'_j$ | row $j$ of $\mathbf X$ ($1 \times N$) |
| $\mathbf Y$ | $p \times N$ H(x) deviations |
| $\mathbf y'_i$ | row $i$ of $\mathbf Y$ ($1 \times N$) |
| $\hat{\mathbf y}_i$ | $\mathbf y'_i/\lVert\mathbf y'_i\rVert$ |
| $\mathbf 1$ | $N$-vector of ones |
| $\bar{\mathbf w}_j$ | mean weights ($N \times 1$) |
| $\mathbf T_j$ | deviation transform ($N \times N$) |
| $\mathbf W$ | symmetric root, Eq. (6) |
| $\tilde{\mathbf P}_a$ | analysis covariance in ensemble space |
| $\kappa_{ji}$ | weight of obs $i$ at element $j$ |
| $r$ | $\sigma_y^2/\sigma_o^2$ |

Observations are numbered $i = 1, \dots, p$ in the order the serial filter takes them. Since sample variances divide by $N-1$, $\lVert\mathbf y'_i\rVert^2 = (N-1)\,\sigma_{y,i}^2$ and $c_j = \mathbf x'_j\mathbf y_i'^T/(N-1)$.

**B- and R-localization** (G11 and HW13's terms):
- *B-localization* multiplies covariances by the weight. DART multiplies the state–observation covariance (the regression, `dart_eakf.md` (9)), which G11 Sec. 2b call localization "on $\mathbf B\mathbf H^T$": the same as localizing $\mathbf B$ for observations at grid points, a mix of B and R for observations between grid points or integrating over several. N15 calls it CL, covariance localization.
- *R-localization* divides the observation error variance by the weight, i.e. multiplies $\mathbf R^{-1}$ (H07 Sec. 2.3.4). N15 calls the local analysis with it OL, observation localization.

## 2. The math side by side

### 2.1 Both are ensemble transforms

Any analysis that adds to each member a combination of the prior deviations can be written, at state element $j$, as

$$
\mathbf x^a_j = \bar x_j\,\mathbf 1^T + \mathbf x'_j\big(\bar{\mathbf w}_j\mathbf 1^T + \mathbf T_j\big) \tag{1}
$$

where $\mathbf x^a_j$ is the $1 \times N$ row of analysis members at $j$. Column $n$ of $\bar{\mathbf w}_j\mathbf 1^T + \mathbf T_j$ holds the weights of the $N$ prior deviations in member $n$, as in H07 (25). The LETKF is built this way: $\bar{\mathbf w}_j$ and $\mathbf T_j = \mathbf W_j$ come from an ETKF analysis with the observations near $j$ (Sec. 2.3).

**The serial EAKF has the same form.** For observation $i$ at weight $\kappa_{ji}$, the regression step (`dart_eakf.md` (9) without $S$, split as in its (10)) changes the mean by $\kappa_{ji}\,b_j\,k_i\,d_i$ and the deviations by $\kappa_{ji}\,(a_i-1)\,b_j\,\mathbf y'_i$. Since $b_j = c_j/\sigma_{y,i}^2 = \mathbf x'_j\mathbf y_i'^T/\lVert\mathbf y'_i\rVert^2$, both are the current $\mathbf x'_j$ times something that depends only on observation $i$:

$$
\begin{aligned}
\mathbf x'_j &\leftarrow \mathbf x'_j\,\mathbf F_{ji}\\
\bar x_j &\leftarrow \bar x_j + \mathbf x'_j\,\mathbf g_{ji}\\
\mathbf F_{ji} &= \mathbf I + \kappa_{ji}\,(a_i-1)\,\hat{\mathbf y}_i^T\hat{\mathbf y}_i\\
\mathbf g_{ji} &= \kappa_{ji}\,k_i\,d_i\,\hat{\mathbf y}_i^T/\lVert\mathbf y'_i\rVert
\end{aligned} \tag{2}
$$

$\mathbf F_{ji}$ is the identity except in the direction $\hat{\mathbf y}_i$, where it scales by $1+\kappa_{ji}(a_i-1)$; for $\kappa = 1$ it is T03's single-observation square root (T03 (9)–(10)). Applying (2) for $i = 1, \dots, p$ in turn gives (1) with

$$
\begin{aligned}
\mathbf T_j &= \mathbf F_{j1}\,\mathbf F_{j2}\cdots\mathbf F_{jp}\\
\bar{\mathbf w}_j &= \sum_{i=1}^{p}\mathbf F_{j1}\cdots\mathbf F_{j,i-1}\,\mathbf g_{ji}
\end{aligned} \tag{3}
$$

(check 1: (3) reproduces the DART translation, 20 observations with localization, to 9e-16). Here $\mathbf y'_i$, $a_i$, $k_i$ and $d_i$ are those of the H(x) ensemble that observation $i$ is assimilated with, i.e. after the updates by observations $1, \dots, i-1$ (`dart_eakf.md` (13)).

So **in both filters the analysis at a point is a combination of the members' prior values at that point**, with weights that vary from point to point. That is how localization lets the analysis leave the $N-1$-dimensional span of the global ensemble (H07 Sec. 2.2.3). The weights change smoothly between neighbouring points as long as the localization weights do: in check 1, the $\mathbf T_j$ of neighbouring elements differ by at most 0.08. The LETKF also needs the symmetric root for this (H07 Sec. 2.3.3); the serial product gets it from the continuity of each factor in $\kappa$.

What differs is how $\bar{\mathbf w}_j$ and $\mathbf T_j$ are built:

| | serial EAKF | LETKF |
|---|---|---|
| $\mathbf T_j$ | product, one factor per ob¹ | one symmetric root |
| $\kappa$ acts on | the step | $\mathbf R^{-1}$ |
| H(x) used | updated by earlier obs² | prior, for all obs |
| ob–ob weights | yes | none |
| $\mathbf T_j$ symmetric | no³ | yes |

¹ In the order of the observation sequence, so the result depends on it (`dart_eakf.md` Sec. 6.2). ² With the observation–observation weights, `dart_eakf.md` (13). How observation $l$ reaches element $j$ thus runs both directly ($\kappa_{jl}$) and through the later observations it changed ($\kappa_{il}$, then $\kappa_{ji}$); in the LETKF only $\kappa_{jl}$ counts. ³ Check 3: $\mathbf T - \mathbf T^T$ up to 0.07.

Without localization, rows 2–4 drop out and the two give the same mean and covariance (Sec. 2.2). With localization each row is a difference: rows 2 and 4 are B- against R-localization (Sec. 2.4), row 3 is serial against simultaneous (`dart_eakf.md` Sec. 6.2).

### 2.2 Why they agree without localization

With all $\kappa = 1$, the factors in (2) no longer depend on $j$, so the serial EAKF is a single global transform, $\mathbf X_a = \mathbf X\,\mathbf T$, like the ETKF. Two facts make it equivalent to the ETKF.

**Information adds up in ensemble space.** Each factor is the square root of its own observation's term: $\mathbf F_i\mathbf F_i^T = \mathbf I - k_i\,\hat{\mathbf y}_i^T\hat{\mathbf y}_i = (\mathbf I + r_i\,\hat{\mathbf y}_i^T\hat{\mathbf y}_i)^{-1}$. With linear H, the H(x) deviations of a later observation are updated like any state element, $\mathbf y'_2 \leftarrow \mathbf y'_2\mathbf F_1$, so after two observations

$$
\begin{aligned}
\mathbf F_1\mathbf F_2\mathbf F_2^T\mathbf F_1^T &= \mathbf F_1\Big[\mathbf I + \tfrac{1}{N-1}\mathbf F_1^T\mathbf y_2'^T\sigma_{o,2}^{-2}\,\mathbf y'_2\mathbf F_1\Big]^{-1}\mathbf F_1^T\\
&= \Big[\mathbf I + \tfrac{1}{N-1}\textstyle\sum_{i=1}^{2}\mathbf y_i'^T\sigma_{o,i}^{-2}\,\mathbf y'_i\Big]^{-1}
\end{aligned} \tag{4}
$$

with $\mathbf y'_2$ the prior deviations on the right. By induction, $\mathbf T\mathbf T^T = [\mathbf I + \mathbf Y^T\mathbf R^{-1}\mathbf Y/(N-1)]^{-1} = (N-1)\,\tilde{\mathbf P}_a$, the ETKF's (`dart_eakf.md` (17); check 3: 9e-16).

**Square roots differ by a rotation.** The ETKF takes the symmetric root $\mathbf W = [(N-1)\tilde{\mathbf P}_a]^{1/2}$ (H07 (24)). Any other root is $\mathbf T = \mathbf W\mathbf U$ with $\mathbf U$ orthogonal (T03 Sec. 2). Both $\mathbf T$ and $\mathbf W$ leave $\mathbf 1$ unchanged ($\hat{\mathbf y}_i\mathbf 1 = 0$; H07 p. 119), so

$$
\begin{aligned}
\mathbf T &= \mathbf W\,\mathbf U\\
\mathbf U\mathbf U^T &= \mathbf I\\
\mathbf U\mathbf 1 &= \mathbf 1
\end{aligned} \tag{5}
$$

and the mean weights are equal too (check 3: 4e-15, 3e-15, 6e-16). The serial EAKF and the ETKF therefore have the same mean and covariance, and their members differ by a rotation in ensemble space that keeps the mean: in check 3, $\mathbf U$ differs from $\mathbf I$ by up to 0.10, and the members by 0.12 against deviations of about 1.2 (`dart_eakf.md` check 2: 0.11). Which rotation depends on the observation order. The symmetric root is the one closest to the identity, i.e. it changes the deviations least (H07 Sec. 2.3.3; check 3: $\lVert\mathbf T-\mathbf I\rVert_F$ = 1.369 against 1.356). The rotation doesn't matter for the mean and covariance, but it changes the higher moments of the ensemble, which matters once a nonlinear model integrates it (T03 Sec. 3a).

### 2.3 The local analysis (H07)

For each grid point (or column, or patch) $j$, H07 take the observations within a chosen distance and do an ETKF analysis with them (H07 Secs. 2.3, 3, Steps 3–8):

$$
\begin{aligned}
\tilde{\mathbf P}_{a,j} &= \big[(N-1)\,\mathbf I/\rho + \mathbf Y^T\tilde{\mathbf R}_j^{-1}\mathbf Y\big]^{-1}\\
\bar{\mathbf w}_j &= \tilde{\mathbf P}_{a,j}\,\mathbf Y^T\tilde{\mathbf R}_j^{-1}\,(\mathbf y_o-\bar{\mathbf y})\\
\mathbf W_j &= \big[(N-1)\,\tilde{\mathbf P}_{a,j}\big]^{1/2}
\end{aligned} \tag{6}
$$

with $\tilde{\mathbf R}_j^{-1} = \operatorname{diag}(\kappa_{ji}/\sigma_{o,i}^2)$ over the local observations, $\rho$ a multiplicative inflation, and the analysis (1) with $\mathbf T_j = \mathbf W_j$ (H07 (20)–(25); `dart_eakf.md` (18)). The pieces:

- **Where it comes from.** H07 write the analysis as $\bar{\mathbf x} + \mathbf X\mathbf w$ and minimize the Kalman-filter cost function over the $N$-vector $\mathbf w$, whose prior is $\mathcal N(\mathbf 0, \mathbf I/(N-1))$ (H07 (15)–(19)). The ensemble space is small, so the minimization and the square root are cheap: one $N \times N$ eigenproblem per local analysis (H07 Steps 5–6).
- **H(x) is linearized about the prior:** $H(\bar{\mathbf x}+\mathbf X\mathbf w) \approx \bar{\mathbf y} + \mathbf Y\mathbf w$ (H07 (18)), "equivalent to the joint state-observation space method" of A01. All observations are compared with the prior H(x); none is updated during the analysis. For linear H this is what the serial filter's regression of later H(x) gives too (`dart_eakf.md` Sec. 6.1).
- **Localization by choosing and weighting observations.** H07 Sec. 2.2.3 select the observations in a region around the point (e.g. a cylinder) and, for smoothness, multiply $\mathbf R^{-1}$ by a weight that decays with distance: "gradually increasing the uncertainty assigned to the observations until beyond a certain distance they have infinite uncertainty" (H07 Sec. 2.3.4, Step 4). Neighbouring points should share most of their observations, so their weights, and their analyses, stay close.
- **The symmetric root** keeps $\mathbf 1$ as an eigenvector with eigenvalue 1, so the analysis deviations sum to zero; it depends continuously on $\tilde{\mathbf P}_a$, so neighbouring points with slightly different $\tilde{\mathbf P}_a$ get similar members; and it is closest to $\mathbf I$ (H07 Sec. 2.3.3).
- **Inflation in ensemble space.** $(N-1)\mathbf I/\rho$ in place of $(N-1)\mathbf I$ is multiplicative prior inflation by $\rho$, exactly for linear H. Relaxation to the prior (RTPP) is $\mathbf W$ replaced by a weighted mean of $\mathbf W$ and $\mathbf I$ (H07 Sec. 2.3.5). GSI's and JEDI's inflation hooks are Sec. 3 and 6.
- **Cost.** Each local analysis is independent of the others, so the analysis parallelizes over grid points; the cost grows about as $N^2$ per observation per local analysis and $N^3$ per local analysis (H07 Sec. 3). The serial filter costs $O(N)$ per observation and state element reached (T03 Table 1).

### 2.4 R- against B-localization

**One observation, one element.** With a single observation at weight $\kappa$, the transforms (2)–(3) and (6) reduce to rank-one changes in the direction $\hat{\mathbf y}$ (check 2). The serial EAKF:

$$
\begin{aligned}
\bar{\mathbf w} &= \frac{\kappa\,d}{\sigma_y^2+\sigma_o^2}\,\frac{\mathbf y'^T}{N-1}\\
\mathbf T &= \mathbf I + \kappa\,(a-1)\,\hat{\mathbf y}^T\hat{\mathbf y}
\end{aligned} \tag{7}
$$

The LETKF:

$$
\begin{aligned}
\bar{\mathbf w} &= \frac{d}{\sigma_y^2+\sigma_o^2/\kappa}\,\frac{\mathbf y'^T}{N-1}\\
\mathbf T &= \mathbf I + (a_\kappa-1)\,\hat{\mathbf y}^T\hat{\mathbf y}\\
a_\kappa &= \sqrt{\frac{\sigma_o^2/\kappa}{\sigma_y^2+\sigma_o^2/\kappa}}
\end{aligned} \tag{8}
$$

At $\kappa = 1$ the two are the same. For $\kappa < 1$:

- **The EAKF shortens the step; the LETKF weakens the observation.** The EAKF moves the mean by $\kappa$ times the unlocalized step and the deviations by $\kappa$ times the unlocalized change ($1+\kappa(a-1)$ instead of $a$). The LETKF does the full Kalman update for an observation with error variance $\sigma_o^2/\kappa$: $a_\kappa$ is the $a$ of `dart_eakf.md` (6) with that variance.
- **At the same $\kappa$ the LETKF does more**, both to the mean (`dart_eakf.md` Sec. 9.5 table: 0.67 against 0.50 of the unlocalized gain at $\kappa$ = 0.5, $\sigma_y = \sigma_o$) and to the spread (the variance table below).
- **The LETKF's update is a Kalman update; the EAKF's is not.** The mean step of (7) is that of a Kalman update with error variance $\sigma_e^2 = (\sigma_y^2+\sigma_o^2)/\kappa - \sigma_y^2$. That update would scale the spread by $\sqrt{1-\kappa k}$, while the EAKF scales it by $1-\kappa(1-a)$. The squares differ by $\kappa(1-\kappa)(1-a)^2 \ge 0$: for the same mean step, the EAKF removes more spread. It removes less than the Joseph form of N15 (22) gives for its gain with the raw covariance (the squares differ by $2\kappa a(1-a)(1-\kappa) \ge 0$). Once the covariance is tapered, the right spread is no longer defined: the Joseph form takes the raw covariance as the truth, the Kalman update reads the shortened step as a larger observation error. That is the inconsistency of N15 Sec. 2c in its simplest case; N15 show that no other factor in place of the Potter factor removes it.

Variance of the component of $\mathbf x'_j$ along $\hat{\mathbf y}$, posterior over prior, for one observation (check 2). "Joseph" is N15 (22) with the raw covariance and the EAKF's gain; "Kalman" is the Kalman update with the EAKF's mean step:

$\kappa$ = 0.5:

| $r$ | Joseph | EAKF | Kalman | LETKF |
|---|---|---|---|---|
| 0.25 | 0.850 | 0.897 | 0.900 | 0.889 |
| 1 | 0.625 | 0.729 | 0.750 | 0.667 |
| 4 | 0.400 | 0.524 | 0.600 | 0.333 |

$\kappa$ = 0.2:

| $r$ | Joseph | EAKF | Kalman | LETKF |
|---|---|---|---|---|
| 0.25 | 0.928 | 0.958 | 0.960 | 0.952 |
| 1 | 0.820 | 0.886 | 0.900 | 0.833 |
| 4 | 0.712 | 0.791 | 0.840 | 0.556 |

**Effective weight.** The LETKF's mean step at R-weight $\kappa_R$ equals the EAKF's at B-weight $\kappa_{\rm eff}$, and the other way round (HW13 (10); N15 (21), from N12's "regulated localization"):

$$
\begin{aligned}
\kappa_{\rm eff} &= \frac{\kappa_R\,(1+r)}{1+\kappa_R\,r}\\
\kappa_R &= \frac{\kappa_B}{1+r\,(1-\kappa_B)}
\end{aligned} \tag{9}
$$

$\kappa_{\rm eff} \ge \kappa_R$, with equality only at 0 and 1, and the gap grows with $r$. N12 use the second line to give the LETKF the EAKF's localization for one observation; the spread then still differs (the "Kalman" column above, against "EAKF").

With a Gaspari–Cohn weight of half-width $c$ (zero at $2c$, `dart_eakf.md` Sec. 5.1) used on $\mathbf R^{-1}$, (9) gives the effective B-weight as a function of distance (check 4). Distance in units of $c$ at which the gain falls to 50 %, 21 % (GC's value at $c$) and 5 % of the unlocalized gain, and the factor by which the R half-width must shrink to put the 50 % point back where B-localization has it:

| | 50 % | 21 % | 5 % | $c_R/c$ |
|---|---|---|---|---|
| B, GC | 0.68 | 1.00 | 1.33 | |
| R, $\sigma_y/\sigma_o$ = 0.5 | 0.73 | 1.05 | 1.37 | 0.93 |
| R, $\sigma_y/\sigma_o$ = 1 | 0.85 | 1.15 | 1.44 | 0.80 |
| R, $\sigma_y/\sigma_o$ = 2 | 1.06 | 1.33 | 1.56 | 0.64 |
| R, $\sigma_y/\sigma_o$ = 2.5 | 1.14 | 1.39 | 1.60 | 0.59 |
| R, $\sigma_y/\sigma_o$ = 4 | 1.31 | 1.51 | 1.68 | 0.52 |

What this shows:
- **Same zero point, different shape.** Both reach zero at $2c$, but the R-localized gain stays high longer and then falls more steeply. For accurate observations it tends to a step: at $\sigma_y/\sigma_o$ = 4 it falls from 50 % to 5 % within $0.37c$, against $0.65c$ for GC itself.
- **The needed shrinking depends on $\sigma_y/\sigma_o$,** which varies from observation to observation and cycle to cycle. So no single R-localization length matches a B-localization length, and HW13 Sec. 1 (p. 759) add that "there are no two localization functions depending only on distance that can cause the B- and R-localization methods to produce the same increment". $\sigma_y/\sigma_o$ = 2.5 is the MRMS example of `dart_eakf.md` Sec. 3.3 (12.7 dBZ against 5 dBZ).
- **This is one observation.** With many, the effective localization also depends on how many observations there are and where (N15 Sec. 2b: N12's function is then only an approximation; SB11 treat the general relation). `dart_eakf.md` check 4 is the many-observation case: with the same taper the LETKF is the best at $N$ = 20 and the worst at $N$ = 5 for accurate observations.
- **The literature agrees in direction.** G11: the best R-localization length is shorter than the best B-localization length, and with each at its best the two are comparable in accuracy; at the same length, B-localization disturbs geostrophic balance more. HW13 Sec. 3: best lengths 4000 km (R) against 5000–6000 km (B), a factor 0.67–0.8, close to the one-observation factor at $\sigma_y \approx \sigma_o$.

### 2.5 The gain form (B17)

B17 rewrite the symmetric ETKF so that the deviations are updated by a gain, like WH02's EnSRF:

$$
\begin{aligned}
\mathbf X_a &= \mathbf X - \tilde{\mathbf K}\,\tilde{\mathbf H}\mathbf X\\
\tilde{\mathbf K} &= \mathbf Z\mathbf C\big[\mathbf I-(\boldsymbol\Gamma+\mathbf I)^{-1/2}\big]\boldsymbol\Gamma^{-1}\mathbf C^T(\tilde{\mathbf H}\mathbf Z)^T\\
\tilde{\mathbf H}\mathbf Z &= \mathbf E\,\boldsymbol\Gamma^{1/2}\mathbf C^T
\end{aligned} \tag{10}
$$

(B17 (21)–(26), (29) with $a = 1$). $\tilde{\mathbf H} = \mathbf R^{-1/2}\mathbf H$ is the normalized observation operator, $\mathbf Z$ any square root of the prior covariance that is to be used for the gain ($\mathbf Z\mathbf Z^T$ = that covariance), and the last line is the SVD of $\tilde{\mathbf H}\mathbf Z$ without its zero singular values. B17's $\mathbf C$ (eigenvectors) is not H07's $\mathbf C = \mathbf Y^T\mathbf R^{-1}$. The mean is updated with the same $\mathbf Z$ (B17 (12)).

- **With the raw ensemble it is the symmetric LETKF.** For $\mathbf Z = \mathbf X/\sqrt{N-1}$, $(\tilde{\mathbf H}\mathbf Z)^T\tilde{\mathbf H}\mathbf X = \sqrt{N-1}\,\mathbf C\boldsymbol\Gamma\mathbf C^T$, so $\tilde{\mathbf K}\tilde{\mathbf H}\mathbf X = \mathbf X\mathbf C[\mathbf I-(\boldsymbol\Gamma+\mathbf I)^{-1/2}]\mathbf C^T$ and $\mathbf X_a = \mathbf X\mathbf W$ (check 5: 5e-15 against the LETKF translation). An algebraic rewrite, not a different filter.
- **What it is for: a gain from a different ensemble.** $\mathbf Z$ need not be the ensemble that is updated. B17's modulated ensemble has $N L$ members, each the product of a member's deviation and one of $L$ columns of a square root of a localization matrix $\mathbf F$, so that $\mathbf Z\mathbf Z^T = \mathbf F\circ\mathbf P$ (B17 (5)–(7); check 5: 2e-15). With it, (10) is a model-space localized ETKF whose gain updates the $N$ raw members ("GETKF").
- **For one observation it is the B-localized EAKF.** B17 p. 4584: for $p = 1$, (26) gives "identical results to" WH02's and A01's filters. Check 5 confirms it: one observation at a grid point, $\mathbf F$ of full rank, GETKF with the modulated ensemble against DART's EAKF with weights $\mathbf F$, 1e-15. (For an observation that integrates over many levels, $\tilde{\mathbf H}\mathbf Z$ uses the localized covariance where DART uses the raw $\sigma_y^2$; Sec. 5.)
- **So the two directions can be localized differently.** GSI's `modelspace_vloc` and RRFSv2's GETKF modulate in the vertical and select and weight observations horizontally (to be confirmed in the code, Sec. 3 and 6): B-localization in the vertical, R-localization in the horizontal.
- **The raw members get too little spread** when the gain comes from the modulated ensemble, since $N$ members cannot carry the localized covariance's rank. B17 (30) rescale the raw analysis deviations by $a = [\operatorname{tr}(\mathbf P^a_{\rm METKF})/\operatorname{tr}(\mathbf P^a_{\rm raw})]^{1/2}$, the "inherent GETKF inflation". Sec. 5.

## 3. GSI-EnKF's `letkf_update`, step by step

To come: set-up and options (`params.f90`), observation search (kd-tree, `nobsl_max`), the 3-D weight on $\mathbf R^{-1}$, the eigenproblem per point and level, the gain form, how H(x) is treated, inflation hooks, parallel layout.

## 4. The HRRR copy against current GSI

To come: the 283 lines in which `letkf.F90` (HRRR `40ee6058`) and `letkf.f90` (GSI `124138df0`) differ.

## 5. Model-space vertical localization with modulated ensembles

To come: B17 Sec. 2, GSI's `modelspace_vloc` (`neigv`, `vlocal_eig.dat`), RRFSv2's 12 modulated members, the inherent GETKF inflation, integrated observations.

## 6. JEDI's GETKF in RRFSv2

To come: `getkf_header.yaml` and the observer files; what `lengthscale` means; RTPS 0.95 against HRRRDAS's 1.08 and RRFSv1's 1.10. The JEDI source is not here (`RRFSv2/sorc/RDASApp` is an empty submodule).

## 7. What it means for our runs

To come: MRMS (`dart_eakf.md` Sec. 11, items 2 and 6) and what a fair comparison needs.

## 8. Checks

`notes/checks/eakf_letkf_checks.py`, float64. Run it with `uv run --no-project --with numpy python -I notes/checks/eakf_letkf_checks.py` (a few seconds):

| # | check | result |
|---|---|---|
| 1 | serial EAKF with loc. as (1)–(3) | 9e-16 |
| 1 | $\mathbf T_j$, neighbouring elements | differ ≤ 0.08 |
| 2 | one ob: (7) and (8) against the codes | ≤ 9e-16 |
| 2 | variance factors | Sec. 2.4 tables |
| 3 | no loc.: $\mathbf T\mathbf T^T$ vs $(N-1)\tilde{\mathbf P}_a$ | 9e-16 |
| 3 | $\mathbf U$ orthogonal, $\mathbf U\mathbf 1 = \mathbf 1$ | 4e-15, 3e-15 |
| 3 | $\bar{\mathbf w}$ serial vs ETKF | 6e-16 |
| 3 | $\mathbf U - \mathbf I$; members | 0.10; 0.12 |
| 4 | GC as R-weight, (9) | Sec. 2.4 table |
| 5 | gain form, raw, vs LETKF | 5e-15 |
| 5 | modulated $\mathbf Z\mathbf Z^T$ vs $\mathbf F\circ\mathbf P$ | 2e-15 |
| 5 | modulated, one ob, vs DART B-loc | 1e-15 |

Set-ups: checks 1 and 3, 30 state elements, 20 observations at random positions (interpolation H), $N$ = 10, errors 0.2–1.0, random order; check 1 with GC half-width 3 grid lengths for state–observation and observation–observation weights. Check 2: $N$ = 8, $\sigma_o$ = 1. Check 5: 30 elements, 20 observations, $N$ = 10 (raw); 12 elements, $N$ = 5, GC half-width 2.5, $\mathbf F$ of full rank, 60 modulated members, one observation at element 5 (modulated).
