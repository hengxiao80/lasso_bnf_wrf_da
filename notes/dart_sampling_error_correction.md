# Sampling-error correction (SEC) in DART: the math and the code

Written 2026-10-25, to explain step 2 of the observation loop (`dart_workflow_walkthrough.md` Sec. 3) in full: what `&assim_tools_nml :: sampling_error_correction = .true.` does in our filter, where its numbers come from, and how DART's code relates to the paper.

**Sources.**
- **A12:** Anderson (2012), "Localization and sampling error correction in ensemble Kalman filter data assimilation", MWR 140, 2359–2371, doi:10.1175/MWR-D-11-00013.1 (PDF in `notes/`). Equation numbers "A12 (n)" are the paper's. The SEC table file names it as its reference.
- **GC99:** Gaspari and Cohn (1999), "Construction of correlation functions in two and three dimensions", QJRMS 125, 723–757, doi:10.1002/qj.49712555417 (PDF in `notes/`): the Gaspari–Cohn localization function, its Eq. (4.10).
- **A01:** Anderson (2001), "An ensemble adjustment Kalman filter for data assimilation", MWR 129, 2884–2903 (PDF in `notes/`): the EAKF, whose observation-space increment is $\Delta y_n$ (Sec. 2).
- **A03:** Anderson (2003), "A local least squares framework for ensemble filtering", MWR 131, 634–642 (PDF in `notes/`). The regression step that SEC modifies is A03 (6).
- **A07b:** Anderson (2007b), "Exploring the need for localization in ensemble data assimilation using a hierarchical ensemble filter", Physica D 230, 99–111 (PDF in `notes/`): the group filter (Sec. 3). The letters follow A09's reference list; A07a is the inflation paper (`dart_adaptive_inflation.md`).
- **A+09:** Anderson et al. (2009), "The Data Assimilation Research Testbed: A community facility", BAMS 90, 1283–1296 (PDF in `notes/`), p. 1292: regression sampling error and the group filter.
- **A09:** Anderson (2009), "Spatially and temporally varying adaptive covariance inflation for ensemble filters", Tellus 61A, 72–83 (PDF in `notes/`): the adaptive inflation A12 ran with (Sec. 8), our flavor 2 (`dart_adaptive_inflation.md`).
- **G+25:** Gharamti et al. (2025), "The Data Assimilation Research Testbed: A robust, scalable software facility with groundbreaking capabilities ...", BAMS (November 2025), E2328ff, doi:10.1175/BAMS-D-24-0214.1 (PDF in `notes/`). Its Table 3 lists SEC among DART's sampling-error schemes.
- **Code:** DART `7bbd35a09`, under `../software/DART/`:
  - `assimilation_code/modules/assimilation/assim_tools_mod.f90` (`update_from_obs_inc`, `get_correction_from_table`, `obs_updates_ens`) and `sampling_error_correction_mod.f90`. Bare line numbers below refer to `assim_tools_mod.f90`.
  - `assimilation_code/programs/gen_sampling_err_table/`: the table generator `gen_sampling_err_table.f90`, its `.rst`, `work/README` (with a "Theory Discussion" by J. Anderson) and the table shipped with DART, `work/sampling_error_correction_table.nc` (our `SEC_TABLE` in `experiment.sh`).
- **Numbers:** from that table, interpolated as `get_correction_from_table` does. The Monte Carlo numbers in Sec. 3 and 6 come from a Python re-creation of the generator (4×10⁶ samples for N = 5, 2×10⁶ for N = 10, 10⁶ for N = 50; DART's table uses 10⁸). It reproduces the shipped table within its sampling noise (Sec. 6).

**Related notes.** `dart_eakf.md` (the EAKF whose regression SEC modifies); `dart_workflow_walkthrough.md` Sec. 3 (where SEC sits in the observation loop); `dart_adaptive_inflation.md` Sec. 3.2–3.3 (the inflation update uses the sample correlation from before SEC). That note calls the sample correlation $r_{jk}$ and uses $\alpha$, $\beta$ for the inverse-gamma parameters; here the sample correlation is $\hat r$ as in A12, and the SEC factor is A12's $a$ (DART's `alpha`).

**Typora.** Display equations are `$$` blocks. Inline math (`$...$`) needs *Preferences → Markdown → Inline Math*.

---

## 0. Summary

- **What it does:** for every pair of an observation and a state element (or a not-yet-assimilated observation), the regression coefficient $\hat b$ that turns observation increments into state increments (A03 (6)) is multiplied by a factor $S(\hat r, N)$ between 0 and 1. $S$ is looked up in a table by the pair's ensemble sample correlation $\hat r$ and the ensemble size $N$ (A12 (16)–(17)). It acts like a localization and multiplies the Gaspari–Cohn localization and the impact-table factor.
- **Why:** with few members, sample correlations are mostly noise. For a truly uncorrelated pair and $N = 5$, $\hat r$ has a standard deviation of 0.5, and $|\hat r| > 0.5$ in 39 % of cases. Each spurious correlation gives a random increment and a spurious loss of spread (A+09).
- **The two parts of $S = a\,\bar r_N/\hat r$:**
  - $\bar r_N/\hat r$ replaces the sample correlation by the actual correlation to expect given $\hat r$, under a uniform prior on the actual correlation.
  - $a = Q^2/(1+Q^2)$ shrinks the regression further according to how uncertain it still is ($Q$ = its mean over its standard deviation); it minimizes the expected squared error of the scaled regression (A12 (3)–(9)).
- **The table** is built once, offline, by Monte Carlo: actual correlations uniform on [−1, 1], N-member samples from a bivariate normal, sample correlations sorted into bins of width 0.01.
- **DART's $a$ is smaller than A12's formula at small N.** The generator takes the spread of the regression with the sample standard deviations (A12 assumes those exact) and adds a factor $1 + 1/N$. At $N = 5$ the table's $a$ is 1.2–1.8 times smaller than A12 (9)–(13) would give; at $N = 50$ the two agree within 2 %.
- **Size for us** ($N = 5$): $S$ = 0.12 at $\hat r$ = 0.5, 0.25 at 0.7, 0.49 at 0.9 and 0.81 at 0.99. With 50 members: 0.89, 0.94, 0.98 and 0.998.
- **Side effects:** the adaptive inflation adapts with the uncorrected $\hat r$; the observation-space increment itself is not corrected; and in A12's GCM tests SEC made the analyses slightly more unbalanced (larger surface-pressure tendency on the first step).

## 1. Notation

| symbol | meaning | in the code |
|---|---|---|
| $N$, $n$ | ensemble size (5), member index | `ens_size` (`grp_size`) |
| $x$, $y$ | a state element; the observed quantity H(x) | `state`, `obs` |
| $\Delta y_n$ | EAKF observation-space increment of member $n$ | `obs_inc` |
| $\hat\sigma_x$, $\hat\sigma_y$ | sample standard deviations | from `state_var`, `obs_prior_var` |
| $\hat r$ | sample correlation of $x$ and $y$ | `correl`, `scorrel` |
| $\hat b$ | sample regression coefficient | `reg_coef` |
| $\rho$ | actual (true) correlation | `t_correl` (generator) |
| $\bar r_N$, $\sigma_{r,N}$ | mean and sd of $\rho$ given $\hat r$ | `true_corr_mean`, `exp_true_correl` |
| $\bar b_N$, $\sigma_{b,N}$ | mean and sd of the regression given $\hat r$ | `reg_mean`, `reg_sd` (generator) |
| $Q$ | $\bar b_N/\sigma_{b,N}$ | (`beta` = $Q^2$) |
| $a$ | A12's SEC localization factor | `alpha`, `mean_factor` |
| $S$ | $a\,\bar r_N/\hat r$, the SEC | applied to `reg_coef` |
| $\kappa$ | Gaspari–Cohn localization × impact factor | `final_factor` |

## 2. The regression step without SEC (A03 (6); A12 (1)–(2))

DART's EAKF first computes, for one observation, an increment $\Delta y_n$ for each member's H(x). It then updates every state element $x$ within the localization distance by regression on $y$:

$$
\Delta x_n = \kappa\,\hat b\,\Delta y_n, \qquad n = 1, \dots, N \tag{1}
$$

$$
\hat b = \hat r\,\frac{\hat\sigma_x}{\hat\sigma_y} \tag{2}
$$

In the code, `update_from_obs_inc` computes $\hat b$ (`reg_coef = obs_state_cov/obs_prior_var`, `:1498`) and the increment `state_inc = reg_coef * obs_inc` (`:1548`), and `obs_updates_ens` applies $\kappa$: `ens = ens + final_factor * increment` (`:2059`). The same routine updates the H(x) of observations not yet assimilated. As A03 notes after its Eq. (6), all the information about the prior covariance that the update uses is in the correlation $\hat r$; the standard deviations only scale it.

## 3. Sampling error in $\hat r$

For a bivariate normal pair with actual correlation $\rho = 0$, the sample correlation from $N$ members has

$$
\operatorname{Var}(\hat r \mid \rho = 0) = \frac{1}{N-1} \tag{3}
$$

so its standard deviation is 0.5 for $N = 5$ and 0.14 for $N = 50$. In the Monte Carlo, $|\hat r| > 0.5$ for 39 % of truly uncorrelated pairs at $N = 5$.

A+09 (p. 1292) states the consequence: a small ensemble "can have spurious large correlations due to sampling error. This leads to an erroneous increase in ensemble confidence and random errors in the mean." A12 Sec. 2 follows A07b, the group filter, in arguing that localization is needed mainly because of this sampling error. The Gaspari–Cohn localization addresses it only through distance. SEC addresses it through $N$ and $\hat r$, at any distance and for any pair of variables, for example T2 against QVAPOR at 5 km above the station.

## 4. The SEC algorithm (A12 Sec. 3)

### 4.1 The factor $a$ (A12 (3)–(10))

A12 treats the sample regression $\hat b$ as a draw $z$ from $\mathcal N(\bar b_N, \sigma_{b,N}^2)$; a nonzero $\sigma_{b,N}$ is the sampling error. It looks for the factor $a$ that minimizes the expected squared difference between $a z$ and $\bar b_N$, which minimizes the expected error of the updated ensemble mean (A12 (3)):

$$
\mathrm E\big[(a z - \bar b_N)^2\big] = a^2\big(\bar b_N^2 + \sigma_{b,N}^2\big) - 2a\,\bar b_N^2 + \bar b_N^2 \notag
$$

Setting the derivative with respect to $a$ to zero gives (A12 (9)–(10)):

$$
a = \frac{\bar b_N^2}{\bar b_N^2 + \sigma_{b,N}^2} = \frac{Q^2}{1 + Q^2}, \qquad Q = \frac{\bar b_N}{\sigma_{b,N}} \tag{4}
$$

The README of the generator says the same in words: "reduction factor = 1 / (ratio**2 + 1)", where ratio is the standard deviation of the regression over its mean. The factor is near 1 when the regression is well determined ($Q$ large) and near 0 when its sampling spread is comparable to its size.

### 4.2 From the regression to the correlation (A12 (12)–(13))

A12 assumes that all the sampling error is in the correlation and none in $\hat\sigma_x$, $\hat\sigma_y$ (its appendix checks this, below). Then

$$
\begin{aligned}
\bar b_N &= (\hat\sigma_x/\hat\sigma_y)\,\bar r_N \\
\sigma_{b,N} &= (\hat\sigma_x/\hat\sigma_y)\,\sigma_{r,N} \\
Q &= \bar r_N/\sigma_{r,N}
\end{aligned} \tag{5}
$$

so $Q$ depends only on $N$ and $\hat r$, through a prior on the actual correlation. A12 uses a uniform prior on [−1, 1] ("a relatively uninformative prior"). $\bar r_N$ and $\sigma_{r,N}$ are then the mean and standard deviation of the actual correlation among all cases whose sample correlation is $\hat r$, which the Monte Carlo of Sec. 4.4 estimates. In formulas, with $p_N(\hat r \mid \rho)$ the distribution of the $N$-member sample correlation:

$$
\bar r_N(\hat r) = \frac{\int_{-1}^{1} \rho\; p_N(\hat r \mid \rho)\, d\rho}{\int_{-1}^{1} p_N(\hat r \mid \rho)\, d\rho} \tag{6}
$$

$$
\sigma_{r,N}^2(\hat r) = \frac{\int_{-1}^{1} (\rho - \bar r_N)^2\, p_N(\hat r \mid \rho)\, d\rho}{\int_{-1}^{1} p_N(\hat r \mid \rho)\, d\rho} \tag{7}
$$

A12's appendix tests the assumption: for correlations above 0.05, the localization computed from the spread of the regression differs from the one computed from the spread of the correlation by at most 14, 7, 3 and 2 % for $N$ = 10, 20, 40 and 80. It gives no number for $N < 10$; at our $N = 5$ the difference is large (Sec. 6).

### 4.3 The bias correction and $S$ (A12 (16)–(17))

The sample correlation is biased against $\bar r_N$: with the uniform prior, $|\bar r_N| < |\hat r|$ (a large $|\hat r|$ is more often an overestimate than an underestimate). A12 corrects this with the factor $\bar r_N/\hat r$, and the increments become

$$
\Delta x_n = \kappa\, S\, \hat b\, \Delta y_n, \qquad S = a\,\frac{\bar r_N}{\hat r} \tag{8}
$$

$S$ is what A12 calls the sampling error correction. Written out with (2), the corrected regression is the expected actual correlation, shrunk by $a$, times the sample standard-deviation ratio:

$$
S\,\hat b = a\,\bar r_N\,\frac{\hat\sigma_x}{\hat\sigma_y} \tag{9}
$$

### 4.4 A12's Monte Carlo (A12 (14)–(15))

A12 takes $K = 201$ actual correlations $\rho_k = -1 + 2(k-1)/(K-1)$, draws $M = 10^8$ samples of size $N$ from a bivariate normal with unit variances and correlation $\rho_k$ for each, and computes every sample's correlation. The sample correlations are sorted into $K$ subsets, each holding the values nearest to one $\rho_k$. For a given $\hat r$, the mean and standard deviation of the actual correlations in the nearest subset give $\bar r_N$ and $\sigma_{r,N}$. Lookup tables of $S$ against $N$ and $\hat r$ (A12 Fig. 1) are then used during the assimilation.

## 5. DART's implementation

### 5.1 The table generator (`gen_sampling_err_table.f90`, `compute_table`)

For each ensemble size $N$:

1. Actual correlations $\rho_j = -1 + 2(j-1)/(M-1)$, $j = 1, \dots, M$, with $M$ = `num_samples` = 10⁸ (`:189–191`), and **one** $N$-member sample for each (`num_times = 1`), drawn from a bivariate normal with unit variances and correlation $\rho_j$ (`twod_gaussians`, `:208`). The random generator is seeded with $N$ (`:136`), so the table is reproducible.
2. The sample correlation $\hat r$ (`comp_correl`, `:212`) puts the sample into one of 200 bins of width 0.01 (`bin_num`, `:216`), centred at −0.995, −0.985, …, 0.995.
3. For each bin:
   - `true_corr_mean` = mean of the $\rho_j$ in the bin, i.e. $\bar r_N$ (`:227`, `:262`);
   - $m$ and $s$ = mean and standard deviation of $\rho_j\,\hat\sigma_2/\hat\sigma_1$ over the bin (`:238`): the regression one would compute with the actual correlation and the sample's own standard deviations;
   - $a$ from $m$ and $s$ by Eq. (10) below (`:271–272`), and `count`, the number of samples in the bin.

$$
\beta = \frac{m^2}{s^2\,(1 + 1/N)}, \qquad a = \frac{\beta}{1 + \beta} \tag{10}
$$

The code's comment on the $1 + 1/N$ is "Correct for bias in the standard deviation for very small ensembles, too"; the line without it is still there, commented out (`:269`). Without that factor, Eq. (10) is A12 (9) with $Q = m/s$.

The file shipped with DART holds $N$ = 3 to 200 (198 sizes), `num_samples` = 10⁸, and A12 as its `reference` attribute; it has been in DART's git since 2019 (commit `1a7e1b99c`). For $N = 5$ every bin has between 3.4×10⁵ and 1.6×10⁶ samples.

Our setup: `SEC_TABLE` in `experiment.sh` points at that file, and `prep_filter.sh` links it into `run/filter/` under the fixed name `sampling_error_correction_table.nc`, which filter expects.

### 5.2 In filter

1. **Switch:** `&assim_tools_nml :: sampling_error_correction`, default `.false.` (`:141`); ours is `.true.` in all three namelists (`input.nml.filter`, `input.nml.filter_mrms`, `input.nml.filter_joint`). `assim_tools_init` allocates the table arrays (`:295–299`; it can't read the table yet, since the ensemble size isn't known there) and logs "Using Sampling Error Correction" (`:2490–2492`).
2. **Reading the table:** the first call of `get_correction_from_table` reads the column for $N$ (`:1579` → `read_sampling_error_correction`, `sampling_error_correction_mod.f90:82–115`), and stops filter if the file has no entry for $N$.
3. **`update_from_obs_inc`** (`:1472–1559`), for each pair:
   - $\hat b$ (`reg_coef`, `:1498`) and $\hat r$ (`correl`, clipped to ±1, `:1527`);
   - `correl_out = correl` (`:1530`): the correlation handed back for the adaptive inflation, **before** SEC;
   - the lookup (`:1535`) returns $\bar r_N$ (`exp_true_correl`) and $a$ (`mean_factor`);
   - if $|\hat r| > 0.001$: `reg_coef = reg_coef * (exp_true_correl / correl) * mean_factor` (`:1537–1538`), i.e. $\hat b \leftarrow S\,\hat b$; otherwise $\hat b \leftarrow 0$;
   - `state_inc = reg_coef * obs_inc` (`:1548`).
4. **`get_correction_from_table`** (`:1564–1632`):
   - linear interpolation of $\bar r_N$ and $a$ between the bin centres (`:1605`);
   - for $|\hat r| \ge 0.995$, interpolation between the last bin and ($\bar r_N = \pm 1$, $a = 1$) at $|\hat r| = 1$ (`:1590–1597`), so $S \to 1$ only as $|\hat r| \to 1$;
   - guards: $\bar r_N$ of the other sign than $\hat r$ is set to 0 (`:1625`), and $|\bar r_N| > |\hat r|$ is set to $\hat r$ (`:1627`), so $\bar r_N/\hat r$ stays in [0, 1].
5. **Callers:** `obs_updates_ens` (`:2005–2059`), once per group (`:2042`, `:2046`), for the state elements near the observation (`STATE_UPDATE`) and for the H(x) of the observations not yet assimilated (`OBS_UPDATE`). With `num_groups > 1` the table for the group size is used and the group filter's factor (`comp_reg_factor`, `:2053`) is applied as well; we run `num_groups = 1`.

### 5.3 What SEC does not touch

- **The observation-space increment** $\Delta y_n$ (the EAKF step, `obs_increment`). The observation's own posterior H(x), recomputed from the updated state, therefore moves less than $\Delta y_n$.
- **The adaptive inflation:** it is updated with `correl_out`, the correlation from before SEC (`dart_adaptive_inflation.md` Sec. 3.3), so $\lambda$ adapts as if the state update were the uncorrected one.
- The forward operators, the outlier check and the prior inflation.

## 6. A12 against DART's code

| item | A12 | DART |
|---|---|---|
| prior grid | 201 values × 10⁸ samples | 10⁸ values × 1 sample |
| bins of $\hat r$ | nearest of 201 $\rho_k$ | 200 bins of width 0.01 |
| lookup | nearest subset | linear interpolation |
| spread for $a$ | of $\rho$ only (sds exact) | of $\rho\,\hat\sigma_2/\hat\sigma_1$ |
| extra factor | none | $1 + 1/N$ on $s^2$ |
| $S$ | $a\,\bar r_N/\hat r$ | the same |
| guards | none stated | Sec. 5.2 item 4 |

The prior grid, binning and lookup differences only change the resolution. The spread used for $a$ matters at small $N$. At $N = 5$ the sample standard deviations, and with them their ratio, are themselves very noisy, so the spread of the regression is much larger than that of the correlation alone. The Monte Carlo for $N = 5$, with A12's $a$ (Eq. 4 with Eq. 5), the generator's recipe without and with the $1 + 1/N$ factor, and the shipped table:

| $\hat r$ | A12 | regr. spread | + $(1+1/N)$ | table |
|---|---|---|---|---|
| 0.305 | 0.158 | 0.099 | 0.084 | 0.086 |
| 0.505 | 0.370 | 0.273 | 0.238 | 0.226 |
| 0.705 | 0.592 | 0.480 | 0.434 | 0.426 |
| 0.905 | 0.831 | 0.743 | 0.707 | 0.703 |
| 0.975 | 0.926 | 0.873 | 0.852 | 0.855 |

- The re-created recipe matches the shipped table within the Monte Carlo noise (fourth and fifth columns), and $\bar r_N$ matches to ±0.002.
- At $N = 5$, A12's formula would give an $a$ 1.2–1.8 times larger than the table's (larger at small $\hat r$). Most of the gap comes from the standard-deviation sampling noise, the rest from the $1 + 1/N$.
- At $N = 10$ the ratio is 1.01–1.20 for the same $\hat r$. Without the $1 + 1/N$ it is at most 1.15, close to the 14 % of A12's appendix (a related but not identical calculation). At $N = 50$ it is at most 1.02.
- So DART's SEC is more conservative than the paper's formula, and noticeably so only for very small ensembles like ours.

## 7. Numbers from our table

$S = a\,\bar r_N/\hat r$, interpolated as filter does:

| $\hat r$ | N = 5 | N = 10 | N = 20 | N = 50 |
|---|---|---|---|---|
| 0.1 | 0.005 | 0.033 | 0.105 | 0.283 |
| 0.2 | 0.019 | 0.116 | 0.308 | 0.601 |
| 0.3 | 0.043 | 0.226 | 0.489 | 0.760 |
| 0.5 | 0.121 | 0.447 | 0.710 | 0.885 |
| 0.7 | 0.247 | 0.634 | 0.836 | 0.940 |
| 0.8 | 0.341 | 0.729 | 0.888 | 0.960 |
| 0.9 | 0.486 | 0.839 | 0.941 | 0.980 |
| 0.95 | 0.606 | 0.908 | 0.969 | 0.990 |
| 0.99 | 0.813 | 0.979 | 0.994 | 0.998 |

The two factors for $N = 5$:

| $\hat r$ | $\bar r_N$ | $a$ | $S$ |
|---|---|---|---|
| 0.1 | 0.051 | 0.010 | 0.005 |
| 0.3 | 0.155 | 0.084 | 0.043 |
| 0.5 | 0.270 | 0.224 | 0.121 |
| 0.7 | 0.412 | 0.420 | 0.247 |
| 0.9 | 0.630 | 0.695 | 0.486 |
| 0.99 | 0.878 | 0.916 | 0.813 |

And for $N = 50$:

| $\hat r$ | $\bar r_N$ | $a$ | $S$ |
|---|---|---|---|
| 0.1 | 0.093 | 0.303 | 0.283 |
| 0.3 | 0.281 | 0.810 | 0.760 |
| 0.5 | 0.474 | 0.934 | 0.885 |
| 0.7 | 0.674 | 0.976 | 0.940 |
| 0.9 | 0.887 | 0.994 | 0.980 |
| 0.99 | 0.988 | 1.000 | 0.998 |

At $N = 5$ both factors are small, and $a$ dominates below $\hat r \approx 0.7$. At $N = 50$, $\bar r_N/\hat r$ is close to 1 and $a$ matters only for weak correlations.

## 8. What this means for our runs

1. **With 5 members the update is heavily damped.** A state element correlated 0.7 with H(x) gets a quarter of the plain EAKF increment, and one at 0.9 about half. This multiplies the 300-km Gaspari–Cohn localization and the impact table.
2. **Even the observed field is damped.** A METAR temperature's H(x) is the bilinear interpolation of four T2 values, so each of them has a sample correlation with H(x) just below 1, where $S$ is still well below 1 at $N = 5$ (0.73 at 0.98, 0.81 at 0.99). In A12's simple linear model, where each observation is exactly one state variable, $S$ was 1 for those pairs.
3. **Results from the 5-member runs won't carry over to 50 members as they are.** Under the same localization, $S$ at $\hat r$ = 0.7 goes from 0.25 to 0.94. The size of the increments, the post-analysis shock and the inflation can all change for this reason alone.
4. **A12's tests relevant to us:**
   - SEC gives no gain where a Gaspari–Cohn localization is already well tuned, but it makes the results less sensitive to the localization width, and it helped most in the three-dimensional model, which has many weakly related remote observations (A12 Sec. 4c, 5).
   - It needed less inflation there: at 80 members and a 3-rad half-width, mean inflation 1.05 with SEC against 1.7 without.
   - **It made the analyses more unbalanced** (larger surface-pressure tendency after each analysis) for all but the widest localizations, "even for a large ensemble" (A12 Fig. 9, Sec. 5). Whether SEC adds to our post-analysis shock is untested: all our runs have it on.
   - A12's inflation settings were the same as our flavor 2: A09 adaptive inflation with the sd fixed at 0.6 and damping of 10 % towards 1.
5. **The uniform prior ignores physics.** The same $\hat r$ gets the same $S$ for a neighbouring grid point of the same field and for an unrelated variable far up the column. A12 Sec. 5 suggests more informative priors (e.g. U(0.8, 1.0) for pairs known to be strongly correlated, U(−0.5, 0.5) for weakly related ones); DART's generator offers only the uniform one.
6. **SEC can't correct systematic errors** in the ensemble covariances from model error or nonlinearity, since it looks only at the prior ensemble (A12 Sec. 5). That is the job of the adaptive inflation, which uses the observations.
7. **Other sampling-error tools in DART** (G+25 Table 3): adaptive localization from empirical localization functions, variable-based localization, hierarchical groups (the group filter, `num_groups > 1`), randomized dormant ensembles and spread restoration.
