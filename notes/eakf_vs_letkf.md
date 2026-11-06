# EAKF against LETKF: the math, the code in GSI-EnKF and JEDI, and what it means for us

Written 2026-11-05 (session "learn: EAKF vs LETKF") as a walk-through of how DART's serial EAKF differs from the local ensemble transform Kalman filter (LETKF), as written down by H07 and B17 and as implemented in GSI-EnKF (`letkf.f90`) and in JEDI's GETKF, which RRFSv2 runs. It continues `dart_eakf.md` Sec. 9.4–9.6, which has the ETKF and LETKF in brief; that note stays the reference for the EAKF itself. Sec. 2 is written; Sec. 3–7 are to come.

**How to read it.** Sec. 1 is a primer: the ideas and words the rest uses (ensemble space, square roots, serial against simultaneous, B- and R-localization), with a three-member example, Example A, that Sec. 2 comes back to. Sec. 2 puts the two filters' math side by side. Of the EAKF itself, Sec. 2 needs only `dart_eakf.md` Sec. 3–4: one observation's update in observation space, then the regression onto the state.

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

So far (Sec. 2, the math), in plain words:

- **Without localization the two filters do the same analysis.** Same analysis mean, same spread, same correlations; only which member ends up with which deviation differs (Sec. 2.2). Everything that separates them comes with localization.
- **One way to look at both.** Every analysis member at a grid point is the prior mean there plus a weighted sum of the prior members' deviations there. The weights are $N$ numbers per member. The LETKF computes them directly, once per grid point, from all nearby observations. DART's EAKF never forms them, but its regression step amounts to the same thing: each observation shrinks the part of a variable's deviations that looks like the observed quantity's deviations, and leaves the rest alone (Sec. 2.1).
- **Localization acts in different places.** DART multiplies the update by the distance weight: far from the observation, a smaller step (B-localization). The LETKF divides the observation's error variance by the weight: far from the observation, a less accurate observation, but a full update for that accuracy (R-localization). At the same weight the LETKF changes more, and much more for accurate observations: at weight 0.5, an observation with a quarter of the prior spread as its error gets 0.94 of its unlocalized update in the LETKF, 0.5 in DART. So the LETKF needs a shorter localization radius: for one observation about 0.8 times as long when $\sigma_y = \sigma_o$, 0.6 times for radar-like accuracy (Sec. 2.4).
- **Order.** DART takes the observations one at a time, each seeing the ensemble as the earlier ones left it; the LETKF takes all at once. With localization the serial result depends on the order (Sec. 2.1; `dart_eakf.md` Sec. 6.2).
- **The GETKF** (B17's "gain form"), which RRFSv2 runs, is the LETKF rewritten so that the vertical localization can be done DART's way, on covariances, while the horizontal one stays LETKF-style (Sec. 2.5).

## 1. Background and notation

### 1.1 What an ensemble filter has to produce

The Kalman filter's analysis is a mean and a covariance (`dart_eakf.md` (3)). An ensemble filter estimates the prior covariance from $N$ forecasts (members) and must hand back $N$ analysis members whose mean and sample covariance are the Kalman-filter values, so that the next forecast can start from them.

- **Deviation** (also *perturbation*): a member minus the ensemble mean. The sample covariance of two quantities is the average product of their deviations, with $N-1$ in the denominator.
- **Stochastic against deterministic filters.** The perturbed-observation EnKF updates each member with its own randomly perturbed copy of the observations, so the analysis covariance is right only on average (HM98, B98). Deterministic filters compute the analysis deviations directly so that their covariance is the Kalman covariance exactly. T03 call them **square-root filters** (Sec. 1.3). The EAKF, WH02's EnSRF, the ETKF and the LETKF are all square-root filters (`dart_eakf.md` Sec. 9.1).

### 1.2 Members as building blocks: ensemble space

Collect the prior deviations in a matrix $\mathbf X$ with $M$ rows (state elements; ~$10^8$ for our WRF grid) and $N$ columns (members; 5 now, 50 planned). Column $n$ is member $n$'s deviation field. Row $j$ holds the $N$ members' deviations at state element $j$; it is written $\mathbf x'_j$.

**Weights.** If every analysis member is the prior mean plus some combination of the prior deviations, analysis member $n$ is $\bar{\mathbf x} + \mathbf X\mathbf w_n$, where $\mathbf w_n$ holds $N$ numbers: how much of each prior member's deviation goes into analysis member $n$. The set of such weight vectors is called **ensemble space**: $N$-dimensional, one axis per member. A filter that works in ensemble space solves for $N \times N$ numbers instead of $M \times N$, which is the point of the ETKF and LETKF. Because the deviations of any quantity add up to zero, adding the same number to all $N$ weights changes nothing. The direction $\mathbf 1 = (1, 1, \dots, 1)$ in ensemble space thus corresponds to the mean: weights changed in that direction leave the members unchanged.

**Every variable is a vector in ensemble space.** The row $\mathbf x'_j$ (the members' deviations at element $j$) is a vector with $N$ components, and so is the row $\mathbf y'$ of an observed quantity's prior deviations (the H(x) ensemble minus its mean). In these terms:
- variance = squared length / $(N-1)$;
- covariance = dot product / $(N-1)$;
- correlation = cosine of the angle between the two vectors.

Sec. 2 uses this picture throughout.

**Example A** ($N$ = 3; check 6). An observed quantity $y$ (the prior H(x)) and another state variable $x$ somewhere else:

| | member 1 | member 2 | member 3 | mean |
|---|---|---|---|---|
| $y$ | 9 | 10 | 11 | 10 |
| $x$ | 18 | 21 | 21 | 20 |

So $\mathbf y' = (-1, 0, 1)$ and $\mathbf x' = (-2, 1, 1)$, with $\sigma_y^2 = 1$, $\sigma_x^2 = 3$, covariance 1.5, correlation 0.87 (an angle of 30°). The observation is $y_o$ = 11 with $\sigma_o^2$ = 1, so the innovation is $d$ = 1. Split $\mathbf x'$ into its part along $\mathbf y'$ and the rest:
- part along $\mathbf y'$: $(-1.5, 0, 1.5)$, i.e. 1.5 times $\mathbf y'$;
- the rest: $(-0.5, 1, -0.5)$, perpendicular to $\mathbf y'$ (dot product 0), i.e. uncorrelated with $y$.

The observation can only tell us about the first part. Sec. 2.1 shows that this is exactly what the EAKF changes.

### 1.3 Square roots: many ensembles share one covariance

The sample covariance is $\mathbf P = \mathbf X\mathbf X^T/(N-1)$, so $\mathbf X/\sqrt{N-1}$ is a matrix "square root" of $\mathbf P$, the way 3 is a square root of 9. A deterministic filter has to find analysis deviations $\mathbf X_a$ with $\mathbf X_a\mathbf X_a^T/(N-1) = \mathbf P_a$: a square root of the analysis covariance. The name square-root filter comes from that.

**The root is not unique.** Swapping the labels of two members changes no mean, variance or covariance. More generally, the members' deviations can be mixed by any **orthogonal** $N \times N$ matrix $\mathbf U$ ($\mathbf U\mathbf U^T = \mathbf I$, a rotation or reflection in ensemble space) without changing the covariance, and if $\mathbf U\mathbf 1 = \mathbf 1$ the deviations still add up to zero. Different square-root filters pick different roots: same mean and covariance, different members (T03 Sec. 3a: they "produce different analysis ensembles that span the same state-space subspace and have the same covariance"). Swapping members 1 and 3 is such a $\mathbf U$ (check 6).

In ensemble space the analysis deviations are $\mathbf X_a = \mathbf X\mathbf T$ for an $N \times N$ **transform** $\mathbf T$, and the requirement on $\mathbf X_a$ becomes a requirement on $\mathbf T\mathbf T^T$ (Sec. 2.2). The ETKF and LETKF choose the **symmetric square root** ($\mathbf T = \mathbf T^T$), which is unique and has two useful properties: it changes the deviations least, and it changes smoothly when the observations change a little, so neighbouring grid points get similar members (H07 Sec. 2.3.3).

### 1.4 One at a time or all at once

- **Serial** filters (DART's EAKF, WH02's EnSRF in GSI and HRRRDAS) assimilate one scalar observation at a time. Each uses the ensemble, including the other observations' H(x), as the earlier observations left it.
- **Simultaneous** filters (the ETKF, the LETKF) assimilate all observations in one matrix computation, all against the prior.

For the Kalman filter the order of observations with independent errors doesn't matter (`dart_eakf.md` (2)), and without localization the two kinds give the same mean and covariance (Sec. 2.2). AC07's "parallel" algorithm, which DART runs, is still serial in this sense (`dart_eakf.md` Sec. 6.1).

### 1.5 Localization: B and R

**Why.** With 5–50 members, the sample correlation between distant points is mostly noise. Without localization a T2 observation in Oklahoma would change the winds in Florida. So the update is weighted by a factor $\kappa$ that is 1 at the observation and falls with distance to 0 beyond a cutoff. The usual shape is the Gaspari–Cohn (GC) function: with half-width $c$, it is 0.21 at $c$ and 0 from $2c$ on (`dart_eakf.md` Sec. 5.1; DART's `cutoff` is $c$).

**Where the weight goes.** The letters are the usual symbols: $\mathbf B$ for the background (prior) error covariance, $\mathbf R$ for the observation error covariance.
- **B-localization:** multiply covariances by $\kappa$. DART multiplies the state–observation covariance, i.e. the regression coefficient (`dart_eakf.md` (9)). Far from the observation the step is shorter. G11 Sec. 2b call this localization "on $\mathbf B\mathbf H^T$"; it is the same as localizing $\mathbf B$ when observations are at grid points. N15 call it CL (covariance localization).
- **R-localization:** divide the observation's error variance by $\kappa$ (multiply $\mathbf R^{-1}$ by $\kappa$). Far from the grid point being updated, the observation counts as less accurate, and beyond the cutoff as infinitely inaccurate, i.e. ignored (H07 Sec. 2.3.4). This only works in a filter that does a separate analysis for each grid point, since the same observation needs a different error at every point. The LETKF does exactly that, a **local analysis** per grid point (or per column, or per small patch of points). N15 call it OL (observation localization).

### 1.6 Notation

As in `dart_eakf.md` Sec. 1 ($N$, $\sigma_y^2$, $\sigma_o^2$, $d$, $k$, $a$, $c_j$, $b_j$, $\kappa$), plus:

| symbol | meaning |
|---|---|
| $\mathbf X$ | $M \times N$ state deviations |
| $\mathbf x'_j$ | row $j$ of $\mathbf X$ ($1 \times N$) |
| $\mathbf Y$ | $p \times N$ H(x) deviations |
| $\mathbf y'_i$ | row $i$ of $\mathbf Y$ ($1 \times N$) |
| $\hat{\mathbf y}_i$ | $\mathbf y'_i/\lVert\mathbf y'_i\rVert$, unit length |
| $\mathbf 1$ | $N$-vector of ones |
| $\bar{\mathbf w}_j$ | mean weights ($N \times 1$) |
| $\mathbf T_j$ | deviation transform ($N \times N$) |
| $\mathbf W$ | symmetric root, Eq. (6) |
| $\tilde{\mathbf P}_a$ | analysis covariance of the weights |
| $\kappa_{ji}$ | weight of obs $i$ at element $j$ |
| $r$ | $\sigma_y^2/\sigma_o^2$ |

Observations are numbered $i = 1, \dots, p$ in the order the serial filter takes them. Since sample variances divide by $N-1$, $\lVert\mathbf y'_i\rVert^2 = (N-1)\,\sigma_{y,i}^2$ and $c_j = \mathbf x'_j\mathbf y_i'^T/(N-1)$.

Terms used below:
- **Gain:** the factor that turns the innovation into an increment. For the observed quantity itself it is the scalar $k = \sigma_y^2/(\sigma_y^2+\sigma_o^2)$; for a state element it is $c_j/(\sigma_y^2+\sigma_o^2)$, the regression coefficient times $k$ (`dart_eakf.md` (10)).
- **Contraction:** the factor by which the spread shrinks; for the observed quantity $a = \sqrt{1-k}$ (`dart_eakf.md` (6)).
- **Potter's square root:** the classical one-observation square-root update (N15 Sec. 2a). In DART's terms, the shrinking of the deviations by $a$; WH02 write it as a "reduced gain" for the deviations.
- **Joseph form:** the error covariance after an update with *any* gain, optimal or not, $\mathbf P_a = (\mathbf I-\mathbf K\mathbf H)\mathbf P(\mathbf I-\mathbf K\mathbf H)^T + \mathbf K\mathbf R\mathbf K^T$ (N15 (22)). For the Kalman gain it reduces to $(\mathbf I-\mathbf K\mathbf H)\mathbf P$.
- **RTPP, RTPS:** relaxation to prior perturbations / spread: after the analysis, each member's deviation is mixed back toward its prior deviation (RTPP), or all deviations are scaled up toward the prior spread (RTPS; WH12; `dart_adaptive_inflation.md`).
- **Modulated ensemble, raw members, GETKF:** Sec. 2.5.

## 2. The math side by side

### 2.1 Both are ensemble transforms

**The LETKF's output at a grid point.** At each state element $j$ the LETKF computes an $N$-vector of mean weights $\bar{\mathbf w}_j$ and an $N \times N$ transform $\mathbf T_j$, and the analysis members there are

$$
\mathbf x^a_j = \bar x_j\,\mathbf 1^T + \mathbf x'_j\big(\bar{\mathbf w}_j\mathbf 1^T + \mathbf T_j\big) \tag{1}
$$

where $\mathbf x^a_j$ is the $1 \times N$ row of analysis members at $j$. In words: new mean = old mean + $\mathbf x'_j\bar{\mathbf w}_j$ (a weighted sum of the prior deviations at $j$), and new deviation of member $n$ = $\mathbf x'_j$ times column $n$ of $\mathbf T_j$ (another weighted sum of the prior deviations at $j$). This is H07 (25). How $\bar{\mathbf w}_j$ and $\mathbf T_j$ are computed is Sec. 2.3.

**DART's update, seen in ensemble space.** DART never forms weights. It regresses: the observation increments times $b_j$, the regression coefficient of $x_j$ on $y$, times $\kappa$ (`dart_eakf.md` (8)–(10)). But the regression has a simple meaning in the picture of Sec. 1.2. Since $b_j = c_j/\sigma_y^2 = \mathbf x'_j\mathbf y'^T/\lVert\mathbf y'\rVert^2$, the product $b_j\,\mathbf y'$ is exactly the part of $\mathbf x'_j$ along $\mathbf y'$, the projection. The EAKF's deviation update, $\kappa(a-1)\,b_j\,\mathbf y'$, therefore:
- shrinks the part of $\mathbf x'_j$ along $\mathbf y'$ by the factor $1+\kappa(a-1)$ (by $a$ when $\kappa$ = 1);
- leaves the rest of $\mathbf x'_j$, the part uncorrelated with $y$, as it was.

The mean moves by $\kappa\,b_j\,k\,d$, which is $\mathbf x'_j$ times a weight vector pointing along $\mathbf y'$.

*Example A*, $\kappa$ = 1: $k = 0.5$, $a = 0.707$. The part of $\mathbf x'$ along $\mathbf y'$, $(-1.5, 0, 1.5)$, becomes $(-1.06, 0, 1.06)$; the rest, $(-0.5, 1, -0.5)$, stays. The new deviations are $(-1.56, 1, 0.56)$ and the mean moves by $b\,k\,d$ = 1.5 × 0.5 × 1 = 0.75, so the $x$ members become 19.19, 21.75, 21.31. As weights:

- mean weights $\bar{\mathbf w} = (-0.25, 0, 0.25)$: $\mathbf x'\bar{\mathbf w}$ = 0.5 + 0.25 = 0.75;
- transform $\mathbf T$ with rows $(0.854, 0, 0.146)$, $(0, 1, 0)$, $(0.146, 0, 0.854)$: analysis member 1's deviation is 85 % of prior member 1's plus 15 % of member 3's, member 2's is unchanged, and members 1 and 3 are pulled toward each other.

The LETKF with this one observation gives the same members (Sec. 2.4).

**Formally,** for observation $i$ at weight $\kappa_{ji}$ on element $j$:

$$
\begin{aligned}
\mathbf x'_j &\leftarrow \mathbf x'_j\,\mathbf F_{ji}\\
\bar x_j &\leftarrow \bar x_j + \mathbf x'_j\,\mathbf g_{ji}\\
\mathbf F_{ji} &= \mathbf I + \kappa_{ji}\,(a_i-1)\,\hat{\mathbf y}_i^T\hat{\mathbf y}_i\\
\mathbf g_{ji} &= \kappa_{ji}\,k_i\,d_i\,\hat{\mathbf y}_i^T/\lVert\mathbf y'_i\rVert
\end{aligned} \tag{2}
$$

$\hat{\mathbf y}_i^T\hat{\mathbf y}_i$ is the $N \times N$ matrix that projects onto the direction $\hat{\mathbf y}_i$, so $\mathbf F_{ji}$ is the identity except in that one direction, where it multiplies by $1+\kappa_{ji}(a_i-1)$. A matrix that differs from the identity in only one direction is called a *rank-one* update. For $\kappa = 1$, $\mathbf F_{ji}$ is Potter's square root written in ensemble space (T03 (9)–(10)).

**Many observations.** Each observation multiplies the current deviations by its own factor, so after $p$ observations the deviations are $\mathbf x'_j\mathbf F_{j1}\mathbf F_{j2}\cdots\mathbf F_{jp}$, and the mean has collected one step per observation, each taken with the deviations as they were at that moment. That is (1) with

$$
\begin{aligned}
\mathbf T_j &= \mathbf F_{j1}\,\mathbf F_{j2}\cdots\mathbf F_{jp}\\
\bar{\mathbf w}_j &= \sum_{i=1}^{p}\mathbf F_{j1}\cdots\mathbf F_{j,i-1}\,\mathbf g_{ji}
\end{aligned} \tag{3}
$$

Check 1 confirms (3) against the DART translation, with 20 observations and localization, to 9e-16. In (2)–(3), $\mathbf y'_i$, $a_i$, $k_i$ and $d_i$ belong to the H(x) ensemble that observation $i$ is assimilated with, i.e. after the updates by observations $1, \dots, i-1$ (`dart_eakf.md` (13)).

**What follows.**
- **In both filters the analysis at a point is a combination of the members' prior values at that point**, with weights that differ from point to point. That is how localization lets the analysis take shapes that no single combination of the $N$ prior members could (H07 Sec. 2.2.3).
- **The weights change smoothly between neighbouring points** as long as the localization weights do. In check 1 the $\mathbf T_j$ of neighbouring elements differ by at most 0.08. The LETKF relies on the symmetric root for this (H07 Sec. 2.3.3); in the serial product it comes from each factor's smooth dependence on $\kappa$.

**What differs** is how $\bar{\mathbf w}_j$ and $\mathbf T_j$ are built:

| | serial EAKF | LETKF |
|---|---|---|
| $\mathbf T_j$ | product, one factor per ob¹ | one symmetric root |
| $\kappa$ acts on | the step | $\mathbf R^{-1}$ |
| H(x) used | updated by earlier obs² | prior, for all obs |
| ob–ob weights | yes | none |
| $\mathbf T_j$ symmetric | no³ | yes |

¹ In the order of the observation sequence, so the result depends on it (`dart_eakf.md` Sec. 6.2). ² DART updates the H(x) of the observations not yet used, like state elements, weighted by the distance between the two observations (`dart_eakf.md` (13)). So observation $l$ reaches element $j$ directly ($\kappa_{jl}$) and also through the later observations it changed ($\kappa_{il}$, then $\kappa_{ji}$). In the LETKF only $\kappa_{jl}$ counts. ³ Check 3: $\mathbf T - \mathbf T^T$ up to 0.07.

Row by row: the first row is how the analysis is assembled; the second is B- against R-localization (Sec. 2.4); the third and fourth are serial against simultaneous (`dart_eakf.md` Sec. 6.2); the last is which square root (Sec. 1.3). Without localization only the first and last rows remain, and they don't change the mean or covariance (Sec. 2.2).

### 2.2 Why they agree without localization

With all $\kappa = 1$ the factors in (2) are the same for every element $j$, so the serial EAKF applies one transform to the whole ensemble, $\mathbf X_a = \mathbf X\,\mathbf T$, as the ETKF does. Two facts make the two equivalent.

**Information adds up, in any order.** For a scalar, the analysis precision (inverse variance) is the prior precision plus the observations' precisions, $1/\sigma_a^2 = 1/\sigma_b^2 + 1/\sigma_{o,1}^2 + 1/\sigma_{o,2}^2 + \dots$, whether they are added one by one or all at once. The same holds for the weights in ensemble space. Their prior covariance is $\mathbf I/(N-1)$ (H07 Sec. 2.3), i.e. precision $(N-1)\mathbf I$, and each observation adds $\mathbf y_i'^T\mathbf y'_i/\sigma_{o,i}^2$. One serial factor delivers exactly its own observation's share: $\mathbf F_i\mathbf F_i^T = \mathbf I - k_i\,\hat{\mathbf y}_i^T\hat{\mathbf y}_i = (\mathbf I + r_i\,\hat{\mathbf y}_i^T\hat{\mathbf y}_i)^{-1}$. With linear H, the H(x) deviations of a later observation are updated like any state element, $\mathbf y'_2 \leftarrow \mathbf y'_2\mathbf F_1$, and two observations give

$$
\begin{aligned}
\mathbf F_1\mathbf F_2\mathbf F_2^T\mathbf F_1^T &= \mathbf F_1\Big[\mathbf I + \tfrac{1}{N-1}\mathbf F_1^T\mathbf y_2'^T\sigma_{o,2}^{-2}\,\mathbf y'_2\mathbf F_1\Big]^{-1}\mathbf F_1^T\\
&= \Big[\mathbf I + \tfrac{1}{N-1}\textstyle\sum_{i=1}^{2}\mathbf y_i'^T\sigma_{o,i}^{-2}\,\mathbf y'_i\Big]^{-1}
\end{aligned} \tag{4}
$$

with $\mathbf y'_2$ the prior deviations throughout. The first line is "the second observation, seen through the ensemble the first one left"; the second line says that equals both observations' information added to the prior. By induction, $\mathbf T\mathbf T^T = [\mathbf I + \mathbf Y^T\mathbf R^{-1}\mathbf Y/(N-1)]^{-1} = (N-1)\,\tilde{\mathbf P}_a$, the ETKF's (`dart_eakf.md` (17); check 3: 9e-16).

**Square roots differ by a rotation.** So $\mathbf T$ is a square root of the same matrix the ETKF takes the symmetric root of, $\mathbf W = [(N-1)\tilde{\mathbf P}_a]^{1/2}$ (H07 (24)). By Sec. 1.3 the two differ by an orthogonal $\mathbf U$. Both leave $\mathbf 1$ unchanged (each $\hat{\mathbf y}_i$ is perpendicular to $\mathbf 1$; H07 p. 119), so

$$
\begin{aligned}
\mathbf T &= \mathbf W\,\mathbf U\\
\mathbf U\mathbf U^T &= \mathbf I\\
\mathbf U\mathbf 1 &= \mathbf 1
\end{aligned} \tag{5}
$$

and the mean weights are equal too (check 3: 4e-15, 3e-15 and 6e-16 for the three). The serial EAKF and the ETKF therefore have the same mean and covariance, and their members differ by a rotation in ensemble space that keeps the mean. In check 3 (20 observations, 10 members), $\mathbf U$ differs from $\mathbf I$ by up to 0.10, and the members by 0.12 against deviations of about 1.2 (`dart_eakf.md` check 2 found 0.11). Which rotation depends on the observation order. The symmetric root changes the deviations least (H07 Sec. 2.3.3), and the serial product is close to it (check 3: distance from $\mathbf I$ 1.369 against 1.356). The rotation doesn't affect the mean or covariance, but it does affect the higher moments of the ensemble (skewness and so on), which matter once a nonlinear model integrates the members (T03 Sec. 3a).

### 2.3 The local analysis (H07)

For each grid point (or column, or patch) $j$, the LETKF takes the observations within a chosen distance and does an ETKF analysis with them (H07 Secs. 2.3, 3, Steps 3–8):

$$
\begin{aligned}
\tilde{\mathbf P}_{a,j} &= \big[(N-1)\,\mathbf I/\rho + \mathbf Y^T\tilde{\mathbf R}_j^{-1}\mathbf Y\big]^{-1}\\
\bar{\mathbf w}_j &= \tilde{\mathbf P}_{a,j}\,\mathbf Y^T\tilde{\mathbf R}_j^{-1}\,(\mathbf y_o-\bar{\mathbf y})\\
\mathbf W_j &= \big[(N-1)\,\tilde{\mathbf P}_{a,j}\big]^{1/2}
\end{aligned} \tag{6}
$$

then (1) with $\mathbf T_j = \mathbf W_j$ (H07 (20)–(25); `dart_eakf.md` (18)). $\mathbf Y$ and $\mathbf y_o-\bar{\mathbf y}$ are restricted to the local observations, $\tilde{\mathbf R}_j^{-1} = \operatorname{diag}(\kappa_{ji}/\sigma_{o,i}^2)$ is their R-localized inverse error variance, and $\rho$ a multiplicative inflation. Line by line:

1. The analysis precision of the weights: prior precision $(N-1)\mathbf I$ (divided by $\rho$ for inflation, see below) plus the local observations' information, as in Sec. 2.2.
2. The mean weights: the precision-weighted fit to the innovations, the ensemble-space version of the Kalman mean update.
3. The deviation transform: the symmetric square root (Sec. 1.3).

The pieces:

- **Where it comes from.** H07 write the analysis as $\bar{\mathbf x} + \mathbf X\mathbf w$ and look for the weights $\mathbf w$ that best fit the observations while staying close to $\mathbf 0$, the prior mean. "Close" is measured with the prior covariance of the weights, $\mathbf I/(N-1)$ (H07 (15)–(19)). That is the Kalman-filter (3D-Var-like) cost function, written for $N$ unknowns instead of $M$. Because $N$ is small, the minimization and the square root are cheap: one $N \times N$ eigenvalue problem per local analysis (H07 Steps 5–6).
- **H(x) is linearized about the prior:** $H(\bar{\mathbf x}+\mathbf X\mathbf w) \approx \bar{\mathbf y} + \mathbf Y\mathbf w$ (H07 (18)). In words: an analysis that mixes the members with weights $\mathbf w$ is assumed to have H(x) equal to the same mix of the members' H(x). H07 note this is "equivalent to the joint state-observation space method" of A01. All observations are compared with the prior H(x); none is updated during the analysis. For linear H the serial filter's regression of later H(x) gives the same thing (`dart_eakf.md` Sec. 6.1).
- **Choosing and weighting observations.** H07 Sec. 2.2.3 select the observations in a region around the point, e.g. a cylinder of given radius and height. For smoothness they then multiply $\mathbf R^{-1}$ by a weight that decays with distance, "gradually increasing the uncertainty assigned to the observations until beyond a certain distance they have infinite uncertainty" (H07 Sec. 2.3.4, Step 4). Neighbouring points share most of their observations, so their weights and analyses stay close.
- **The symmetric root** keeps $\mathbf 1$ unchanged, so the analysis deviations still add up to zero; it changes smoothly with $\tilde{\mathbf P}_a$; and it changes the deviations least (H07 Sec. 2.3.3).
- **Inflation.** Dividing the prior precision $(N-1)\mathbf I$ by $\rho$ is multiplicative prior inflation by $\rho$, without touching the members (exact for linear H). RTPP is $\mathbf W$ replaced by a weighted mean of $\mathbf W$ and $\mathbf I$ (H07 Sec. 2.3.5). GSI's and JEDI's inflation options are Sec. 3 and 6.
- **Cost.** The local analyses are independent of each other, so the work splits over grid points. Per local analysis it grows about as $N^2$ times the number of local observations, plus $N^3$ for the eigenvalue problem (H07 Sec. 3). The serial filter costs $O(N)$ per observation and per state element it reaches (T03 Table 1), so it is cheap in $N$ and expensive in observations × reach.

### 2.4 R- against B-localization

**Example A at weight 0.5.** Give $x$ the weight $\kappa = 0.5$ for this observation (it is some distance away); $y$, at the observation, keeps weight 1. Check 6:
- *EAKF:* half the step. The mean of $x$ moves by 0.375 instead of 0.75, and its part along $\mathbf y'$ shrinks by $1 + 0.5\,(0.707-1) = 0.854$ instead of 0.707.
- *LETKF:* at $x$'s grid point the observation's error variance becomes $1/0.5 = 2$, so the gain there is $k = 1/(1+2) = 1/3$ and the contraction $\sqrt{2/3} = 0.816$. The mean of $x$ moves by $b\,k\,d = 1.5/3 = 0.5$.

The LETKF changes $x$ more, both mean and spread. The difference grows with the observation's accuracy. If the observation error is a quarter of the prior spread ($\sigma_y/\sigma_o = 4$), doubling a tiny error variance hardly matters: at $\kappa$ = 0.5 the LETKF keeps 0.94 of the unlocalized gain, the EAKF 0.5 (`dart_eakf.md` Sec. 9.5 table).

**One observation, in general** (check 2). Both updates change only the direction $\hat{\mathbf y}$ in ensemble space. The serial EAKF:

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

At $\kappa = 1$ they are the same. For $\kappa < 1$:

- **The EAKF shortens the step; the LETKF weakens the observation.** The EAKF moves the mean by $\kappa$ times the unlocalized step and the deviations by $\kappa$ times the unlocalized change (a factor $1+\kappa(a-1)$ instead of $a$). The LETKF does a full Kalman update for an observation with error variance $\sigma_o^2/\kappa$: $a_\kappa$ is the $a$ of `dart_eakf.md` (6) with that variance.
- **At the same $\kappa$ the LETKF does more**, to the mean (`dart_eakf.md` Sec. 9.5 table: 0.67 against 0.50 of the unlocalized gain at $\kappa$ = 0.5, $\sigma_y = \sigma_o$) and to the spread (table below).
- **The LETKF's local update is always a Kalman update; the EAKF's localized one is not.** A Kalman update has its mean step and its contraction tied together by one error variance. The LETKF's pair belongs to $\sigma_o^2/\kappa$. The EAKF's mean step would belong to an observation with error variance $(\sigma_y^2+\sigma_o^2)/\kappa - \sigma_y^2$, but a Kalman update with that variance would shrink the spread by $\sqrt{1-\kappa k}$, while the EAKF shrinks it by $1-\kappa(1-a)$. The squares differ by $\kappa(1-\kappa)(1-a)^2 \ge 0$: for the same mean step, the EAKF removes more spread than a Kalman update would.
- **Which spread is right is not defined once covariances are tapered.** The Joseph form (Sec. 1.6) gives the actual error variance of the EAKF's mean, if the raw ensemble covariance were the truth. The EAKF leaves more spread than that (the squares differ by $2\kappa a(1-a)(1-\kappa) \ge 0$), so it sits between the two references. This is the inconsistency of N15 Sec. 2c in its simplest case: with a tapered covariance, no single factor in place of Potter's makes the spread agree with the Joseph form (N15 p. 1558). In a serial filter, the next observation inherits that spread; in the LETKF it doesn't, because all observations at a point are taken in one update.

The table below gives these spreads. Take a state variable whose deviations lie along $\mathbf y'$ (perfectly correlated with the observed quantity) at a distance where the weight is $\kappa$; each column is its analysis variance divided by its prior variance. For any other variable, the same factor applies to its part along $\mathbf y'$. "Joseph": the Joseph form for the EAKF's gain with the raw covariance. "Kalman": the Kalman update with the EAKF's mean step (check 2):

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

($r = \sigma_y^2/\sigma_o^2$.) The LETKF column is smaller than the EAKF's because at the same $\kappa$ it takes a bigger step (previous bullets).

**Effective weight.** To compare the two at matching strength, ask which B-weight gives the same mean step as a given R-weight (HW13 (10)), or the other way round (N15 (21), from N12's "regulated localization"):

$$
\begin{aligned}
\kappa_{\rm eff} &= \frac{\kappa_R\,(1+r)}{1+\kappa_R\,r}\\
\kappa_R &= \frac{\kappa_B}{1+r\,(1-\kappa_B)}
\end{aligned} \tag{9}
$$

The first line: an R-weight $\kappa_R$ acts like the larger B-weight $\kappa_{\rm eff}$; they agree only at 0 and 1, and the gap grows with $r$. The second line is N12's recipe for giving the LETKF the EAKF's localization for one observation: shrink the R-weight. Even then the spreads differ (the "Kalman" column above against "EAKF").

**Same GC function on R.** Use the GC weight of half-width $c$ (zero at $2c$) as an R-weight, as GSI's LETKF does, and convert it with (9) into the B-weight it acts like (check 4). The table gives the distance, in units of $c$, at which the gain has fallen to 50 %, 21 % (GC's value at $c$) and 5 % of the unlocalized gain. The last column is the factor by which the R half-width must shrink to put the 50 % point where B-localization has it:

| | 50 % | 21 % | 5 % | $c_R/c$ |
|---|---|---|---|---|
| B, GC | 0.68 | 1.00 | 1.33 | |
| R, $\sigma_y/\sigma_o$ = 0.5 | 0.73 | 1.05 | 1.37 | 0.93 |
| R, $\sigma_y/\sigma_o$ = 1 | 0.85 | 1.15 | 1.44 | 0.80 |
| R, $\sigma_y/\sigma_o$ = 2 | 1.06 | 1.33 | 1.56 | 0.64 |
| R, $\sigma_y/\sigma_o$ = 2.5 | 1.14 | 1.39 | 1.60 | 0.59 |
| R, $\sigma_y/\sigma_o$ = 4 | 1.31 | 1.51 | 1.68 | 0.52 |

What it shows:
- **Same cutoff, different shape.** Both reach zero at $2c$, but the R-localized gain stays high for longer and then drops more steeply. For accurate observations it approaches an on/off switch: at $\sigma_y/\sigma_o$ = 4 it falls from 50 % to 5 % within $0.37c$, where GC itself takes $0.65c$.
- **How much to shrink depends on $\sigma_y/\sigma_o$,** which varies from observation to observation and from cycle to cycle. So no single R-localization length matches a B-localization length. HW13 Sec. 1 (p. 759): "there are no two localization functions depending only on distance that can cause the B- and R-localization methods to produce the same increment". The row $\sigma_y/\sigma_o$ = 2.5 is the MRMS example of `dart_eakf.md` Sec. 3.3 (12.7 dBZ against 5 dBZ).
- **This is one observation.** With many, the effective localization also depends on how many observations there are and where they sit (N15 Sec. 2b: N12's recipe is then only approximate; SB11 treat the general relation). `dart_eakf.md` check 4 is a many-observation case: with the same taper, the LETKF was the best at $N$ = 20 and the worst at $N$ = 5 for accurate observations.
- **The literature agrees in direction.** G11: the best R-localization length is shorter than the best B-localization length, and with each at its best the two are comparable in accuracy; at the same length, B-localization disturbs geostrophic balance more. HW13 Sec. 3: best lengths 4000 km (R) against 5000–6000 km (B), a factor 0.67–0.8, close to the one-observation factor at $\sigma_y \approx \sigma_o$.

### 2.5 The gain form (B17)

**Two ways to write an update.** A *gain* turns observation-space quantities into state increments: a matrix with one row per state element and one column per observation. DART's regression and WH02's EnSRF update the deviations with a gain, applied from the left, one state element at a time: $\mathbf X_a = \mathbf X - \tilde{\mathbf K}\,\mathbf H\mathbf X$, where $\tilde{\mathbf K}$ is a "reduced" gain for the deviations (T03 (11)–(14)). The ETKF instead recombines the members, a transform applied from the right: $\mathbf X_a = \mathbf X\mathbf T$. For the same analysis these are two ways of writing the same thing, and B17 give the gain that reproduces the symmetric ETKF:

$$
\begin{aligned}
\mathbf X_a &= \mathbf X - \tilde{\mathbf K}\,\tilde{\mathbf H}\mathbf X\\
\tilde{\mathbf K} &= \mathbf Z\mathbf C\big[\mathbf I-(\boldsymbol\Gamma+\mathbf I)^{-1/2}\big]\boldsymbol\Gamma^{-1}\mathbf C^T(\tilde{\mathbf H}\mathbf Z)^T\\
\tilde{\mathbf H}\mathbf Z &= \mathbf E\,\boldsymbol\Gamma^{1/2}\mathbf C^T
\end{aligned} \tag{10}
$$

(B17 (21)–(26), (29) with $a = 1$.) The symbols:
- $\tilde{\mathbf H} = \mathbf R^{-1/2}\mathbf H$: H(x) divided by the observation error standard deviation, so that all observations are in units of their own error.
- $\mathbf Z$: a square root of the prior covariance the gain is to be computed from ($\mathbf Z\mathbf Z^T$ = that covariance).
- The last line is the singular value decomposition of $\tilde{\mathbf H}\mathbf Z$: $\boldsymbol\Gamma$ holds the squared singular values, the columns of $\mathbf C$ are directions in ensemble space, those of $\mathbf E$ in observation space. B17's $\mathbf C$ is not H07's $\mathbf C = \mathbf Y^T\mathbf R^{-1}$.

The mean is updated with the same $\mathbf Z$ (B17 (12)).

**With the raw ensemble it is the LETKF.** For $\mathbf Z = \mathbf X/\sqrt{N-1}$, $(\tilde{\mathbf H}\mathbf Z)^T\tilde{\mathbf H}\mathbf X = \sqrt{N-1}\,\mathbf C\boldsymbol\Gamma\mathbf C^T$, so $\tilde{\mathbf K}\tilde{\mathbf H}\mathbf X = \mathbf X\mathbf C[\mathbf I-(\boldsymbol\Gamma+\mathbf I)^{-1/2}]\mathbf C^T$ and $\mathbf X_a = \mathbf X\mathbf W$, the symmetric root (check 5: 5e-15 against the LETKF translation). It is a rewrite, not a different filter.

**What it is for: a gain from a bigger ensemble.** In (10) the ensemble that supplies the gain ($\mathbf Z$) need not be the one that is updated ($\mathbf X$). B17 build a larger **modulated ensemble** for $\mathbf Z$ whose covariance is the *localized* covariance, then update the $N$ original (**raw**) members with its gain. The construction, for vertical localization over $L$ levels:
1. Take the vertical localization matrix $\mathbf F$ (the weight between every pair of levels) and its leading eigenvectors, scaled by the square roots of their eigenvalues, so that $\mathbf F \approx \sum_l \mathbf v_l\mathbf v_l^T$. They are smooth vertical profiles: the first broad, the next with one sign change, and so on (B17 Fig. 3).
2. Multiply each member's deviation, level by level, by each profile: $N$ × (number of profiles) new members.
3. Their covariance is $\mathbf F\circ\mathbf P$, the prior covariance with each element multiplied by the corresponding localization weight. The reason: for each member deviation $\mathbf u$, $\sum_l(\mathbf u\circ\mathbf v_l)(\mathbf u\circ\mathbf v_l)^T = (\mathbf u\mathbf u^T)\circ(\sum_l\mathbf v_l\mathbf v_l^T)$, where $\circ$ is the element-by-element product (B17 (5)–(7); check 5: 2e-15 with all eigenvectors kept).

RRFSv2's comment "12 modulated members" refers to this construction; what exactly the 12 counts is for Sec. 5–6. With $\mathbf Z$ modulated, (10) is a covariance-localized (B-localized) ETKF that hands back $N$ members; B17 call it the GETKF.

**For one observation it is DART's EAKF.** B17 p. 4584: for one observation, (26) gives "identical results to" WH02's and A01's filters. Check 5 confirms it: one observation at a grid point, the GETKF with the modulated ensemble against DART's EAKF with localization weights $\mathbf F$, 1e-15. They differ for an observation that integrates over many levels: the GETKF's $\sigma_y^2$ then uses the localized covariance, where DART uses the raw one (Sec. 5).

**So the two directions can be localized differently.** GSI's `modelspace_vloc` and RRFSv2's GETKF use modulation in the vertical and the LETKF's choice and weighting of observations in the horizontal (to be confirmed in the code, Sec. 3 and 6): B-localization in the vertical, R-localization in the horizontal.

**One cost.** The raw members updated with the modulated gain have too little spread: $N$ members cannot represent the localized covariance, which has many more independent directions. B17 (30) scale the raw analysis deviations by $a = [\operatorname{tr}(\mathbf P^a_{\rm METKF})/\operatorname{tr}(\mathbf P^a_{\rm raw})]^{1/2}$, the ratio of total analysis variance in the modulated and the raw ensembles ("inherent GETKF inflation"). Sec. 5.

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
| 6 | Example A | Sec. 1.2, 2.1, 2.4 |

Set-ups: checks 1 and 3, 30 state elements, 20 observations at random positions (interpolation H), $N$ = 10, errors 0.2–1.0, random order; check 1 with GC half-width 3 grid lengths for state–observation and observation–observation weights. Check 2: $N$ = 8, $\sigma_o$ = 1. Check 5: 30 elements, 20 observations, $N$ = 10 (raw); 12 elements, $N$ = 5, GC half-width 2.5, $\mathbf F$ of full rank, 60 modulated members, one observation at element 5 (modulated). Check 6: Example A with weight 1 and 0.5 on $x$.
