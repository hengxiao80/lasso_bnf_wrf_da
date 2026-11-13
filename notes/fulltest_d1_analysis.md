# D1 against run 5: sampling-error correction and innovation statistics

Written 2026-11-12 in session "fulltest: D1 analysis". Compares D1, the first gate of the 50-member run `_conv_refl_f2` (`cases/20250520/da_theta_m0_n50/output_conv_refl_f2/`, analyses 00:15–01:00), with run 5 `_conv_refl_f2` of the 5-member experiment (`da_theta_m0_n5/output_conv_refl_f2/`). It continues `fulltest_steps.md` D1 ("D1 against run 5", from both runs' `check_cycle.log`), which it doesn't repeat. Background: `dart_sampling_error_correction.md` (the correction's math, table and code path; its notation is used here) and `obs_error_diagnostics.md` (the implied error and Desroziers' estimate).

**Typora.** Display equations are `$$` blocks. Inline math (`$...$`) needs *Preferences → Markdown → Inline Math*.

## Summary

- **The filter namelists differ only in `ens_size`** (and the number of members written). Both runs use the sampling-error correction, which multiplies each observation-to-state regression by a factor $S(\hat r, N)$: at a sample correlation $\hat r$ = 0.5, $S$ = 0.12 for 5 members and 0.89 for 50; at 0.9, 0.49 and 0.98 (`dart_sampling_error_correction.md` Sec. 7). That note's Sec. 8 expected the 5-member results not to carry over to 50 members for this reason alone. D1 shows the effect (Sec. 2, 3.2).
- **At 00:15 the forecasts are the same and the analyses are not** (Sec. 3.2). Both priors are 15-min forecasts from the cold start; their rms innovation (rms $d_b$, observation minus prior mean; Sec. 3.1) agrees within 2 % for every type. On the observations both runs assimilated, D1's analysis fits closer for 14 of 15 types (rms analysis residual $d_a$ 2–18 % smaller), also where its spread is smaller (METAR T2, ACARS T). That difference comes from the analysis step, not from the spread.
- **From 00:30 on the forecasts diverge** (Sec. 3.3): D1's are better for the surface types and reflectivity (at 01:00 mesonet q −17 %, reflectivity −10 %, METAR T2 −9 % in rms $d_b$), worse for clear-air reflectivity (+7 % at 00:45, +15 % at 01:00).
- **The error diagnosis keeps its direction** (Sec. 3.5): the conventional errors we assign are generous (mesonet T and wind most) and the clear-air error too large, in both runs. For precipitation reflectivity these statistics can't tell: its implied error, 3.1 times the assigned one, is mostly prior error the ensemble doesn't represent (missed and misplaced storms) and a bias built in by the observation selection, and its Desroziers estimate is exact only at the optimal gain, which is unknown for reflectivity: the realized gain (0.58) is more than twice the value that would be optimal if the spread were right (0.25), but the spread is far too small, so the true optimum could lie anywhere from 0.25 to 1 (Sec. 3.6). The implied errors are 2–11 % smaller in D1, because its forecasts fit better. Desroziers' estimates are smaller by more for several types (reflectivity −17 %, METAR altimeter −11 %, METAR U10 −9 %, ACARS T −7 %): they depend on the gain as well as on the observations, and a realized gain below the optimal one raises them (Eq. 2).
- **Not known yet**: how much of D1's larger increments is the correction and how much the less noisy covariances; why D1's adaptive inflation is smaller; where the clear-air misfit grows. Next steps in Sec. 5.

## 1. What differs between the runs

- **Which 5-member run**: run 5 `_conv_refl_f2` of 2026-10-23 (`obs_expansion.md` Sec. 9, run 5), not the step-13 1-hour pilot of 2026-10-02/03 (`output_hph` and its variants). The pilot still had DART's default MADIS errors (METAR T2 2.5 K); its statistics led to the METAR change (`obs_expansion.md` Sec. 5) and are the examples of `obs_error_diagnostics.md` Sec. 4.3 and 5, so they are not comparable with the numbers here.
- **The same observations and errors**: both runs' filters read the same files (`da_common_theta_m0/obs_meso_a_calmkeep_mrms/<t>/obs_seq.joint`, through each experiment's link), with the METAR errors set on 2026-10-03 and the mesonet errors set on 2026-10-14 (`obs_expansion.md` Sec. 5 and 7.2, `patches/README.md`). In run 5's 00:15 `obs_seq.final` the median error sd is 1.26 K for METAR T2 (up to 2.47 K with the boundary inflation), 1.59 m/s for METAR 10-m wind and 3.0 K for mesonet T.
- **Namelist**: the diff of the two runs' 00:30 `filter/input.nml` shows only `ens_size` (5, 50), `num_output_state_members` and `num_output_obs_members` (5, 50), and the comment block naming the 50-member file's origin.
- **Initial perturbations**: 50 of the 150 bank draws against 5 of the pilot's 15 (`fulltest_steps.md` D1).
- **The same otherwise**: the observation counts per type and cycle, `settings.txt`, the mean states and the boundary recipe. At 00:15 both runs had prior inflation 1 everywhere (`fill_inflation_restart`, `prior_inf_mean = 1.00`), so the 00:15 spreads are the raw ensemble spreads.

## 2. Sampling-error correction

Both runs have `sampling_error_correction = .true.` and read the same table (`SEC_TABLE` in both experiments' `experiment.sh`). For an observation and a state element (or a not-yet-assimilated observation), filter adds to member $n$

$$
\Delta x_n = \kappa \, S(\hat r, N) \, \hat b \, \Delta y_n
\tag{1}
$$

with $\hat b$ the sample regression, $\Delta y_n$ the EAKF observation-space increment, $\kappa$ the Gaspari–Cohn localization times the impact-table factor and $S = a\,\bar r_N/\hat r$ from the table (`dart_sampling_error_correction.md` Sec. 0, 1 and 5). From that note's Sec. 7 (the same for $-\hat r$ within 0.002, checked 2026-11-12):

| $\hat r$ | $S$, N = 5 | $S$, N = 50 |
|---|---|---|
| 0.1 | 0.005 | 0.283 |
| 0.3 | 0.043 | 0.760 |
| 0.5 | 0.121 | 0.885 |
| 0.7 | 0.247 | 0.940 |
| 0.9 | 0.486 | 0.980 |

What bears on D1 against run 5:
- **Run 5's analyses were heavily damped** (`dart_sampling_error_correction.md` Sec. 8 items 1–3), whatever its initial perturbations: this part of the difference is an effect of the ensemble size, not of the bank draws.
- **The posterior in observation space is damped too.** The observation's own EAKF increment $\Delta y_n$ is not corrected, but the posterior values in `obs_seq.final` are the forward operators applied to the posterior state (`filter_mod.f90`, `compute_posterior`), and the state elements the forward operator reads have $\hat r$ just below 1, where $S$ is still well below 1 at $N = 5$ (Sec. 8 item 2 there). This enters Desroziers' estimate (Sec. 3.5).
- **What `fulltest_steps.md` D1 found on the analysis side follows**: larger increments in D1 (MU, U, QRAIN, QGRAUP, `REFL_10CM`) and a closer analysis fit (reflectivity rms $d_a$ 5.0 against 6.7 dBZ at 01:00 in `check_cycle.log`). Sec. 3.2 shows the same at 00:15, where the priors are the same.
- **The inflation** adapts with the uncorrected $\hat r$, so the correction doesn't explain D1's smaller adaptive inflation directly.
- **The post-analysis shock**: A12 found the correction made analyses more unbalanced (Sec. 8 item 4 there). Both of our runs have it on, so D1 doesn't test that; D1, with the less damped and larger increments, had the larger first-minute adjustment through 00:45.
- **Even at 50 members** the correction is not small for weak correlations: 0.28 at $\hat r$ = 0.1, 0.60 at 0.2.
- **Not known**: the distribution of sample correlations in our analyses, so how much of the increment difference is the correction and how much the other effect of size, the noise in $\hat b$ itself. A one-cycle test would measure it (Sec. 5).

## 3. Innovation statistics

### 3.1 What the tables show

All quantities are those of `obs_error_diagnostics.md` Sec. 1, computed from each run's `obs_seq.final`, separately for each observation type. For one observation:

- $y$ is the observed value;
- $H(x_b)$ and $H(x_a)$ are the prior and the posterior ensemble mean in observation space (the forward operator applied to each member, averaged over the members);
- $s_b$ is the prior ensemble spread in observation space, after prior inflation (at 00:15 the inflation is 1, Sec. 1);
- $\sigma_o$ is the assigned observation-error sd, including `wrf_dart_obs_preprocess`'s boundary inflation;
- $d_b = y - H(x_b)$ is the innovation (observation minus prior mean, "O−F" in `fulltest_steps.md`), and $d_a = y - H(x_a)$ the analysis residual (observation minus analysis mean).

$\operatorname{mean}$ averages over a set of observations of one type (below): at one analysis time in Sec. 3.2 and 3.3, and over the four analysis times together in Sec. 3.4. The columns of the tables:

| column | definition | `obs_error_diagnostics.md` |
|---|---|---|
| n | the number of observations in the set | |
| rms $d_b$ | $\sqrt{\operatorname{mean}(d_b^2)}$, the rms innovation | Sec. 1, 3 |
| rms $d_a$ | $\sqrt{\operatorname{mean}(d_a^2)}$, the rms analysis residual | Sec. 1 |
| spread | $\sqrt{\operatorname{mean}(s_b^2)}$, the rms prior spread | Sec. 1, 3 |
| implied | $\sigma_{o,\mathrm{implied}}$ | Eq. (2) |
| Desroziers | $\sigma_{o,D} = \sqrt{\operatorname{mean}(d_a d_b)}$ | Sec. 4.1 |

**Which observations.** DART QC 0 means assimilated; QC 7 means rejected as an outlier, because $|d_b| > 3\sqrt{s_b^2 + \sigma_o^2}$ (`outlier_threshold = 3`); such an observation has a prior but no influence on the analysis. The tables use two sets:

- **QC 0 or 7** (Sec. 3.3, the first table of Sec. 3.4, and the implied error): every observation with a valid prior. An observation one run rejects is assimilated or rejected by the other, so this set is the same in both runs. Including the outliers follows `obs_error_diagnostics.md` Sec. 6 ("QC selection"; leaving them out would bias $\operatorname{mean}(d_b^2)$ low). For reflectivity, 30 % of this set are outliers in D1 and 36 % in run 5 (Sec. 3.4); that is why its rms $d_b$ here (16–19 dBZ) is much larger than over the assimilated observations (9.2 dBZ at 00:15, Sec. 3.2).
- **QC 0 in both runs** (all of Sec. 3.2, and Desroziers' estimate in Sec. 3.4): the observations both runs assimilated. Statistics involving the analysis need assimilated observations. The runs reject different observations, because the outlier test depends on each run's spread, so each run's own QC-0 set would compare the runs on different observations; a single observation assimilated by one run only can move that run's numbers noticeably (the worked example in Sec. 3.2 has one). Both runs read the same `obs_seq.joint`, so their `obs_seq.final` list the observations in the same order (checked: the same types and observed values), and the set is taken observation by observation.

Further:

- **Gains.** The *isolated-observation gain* $k = s_b^2/(s_b^2 + \sigma_o^2)$ is the fraction of its innovation an observation's EAKF update removes when it is the only observation assimilated (`obs_error_diagnostics.md` Sec. 4.1). It is computed for each observation from its own spread and assigned error and averaged over the set; "isolated" means one observation, not one type. The *realized gain* $g$ (Sec. 3.5) is the fraction the whole analysis removed at the observation's site, with all observations of all types assimilated. For an isolated observation, $g = k$.
- **Ratios** (Sec. 3.4): the implied error and Desroziers' estimate divided by the rms assigned error $\sqrt{\operatorname{mean}(\sigma_o^2)}$ over the same set. Below 1: the innovations support a smaller error than the one assigned.
- **Units**: specific humidity in g/kg; the others as in each row (K, m/s, hPa, dBZ).
- **Left out**: the mesonet altimeter, which is evaluated only (QC 1), so its rows would cover only its rejected outliers.
- **Against `check_cycle.log`**: its `obs_report` (the numbers in `fulltest_steps.md` D1) uses each run's own QC 0 and 1 for both the prior and the posterior statistics, so its numbers differ somewhat from these; its reflectivity rms $d_b$ (~11 dBZ) is smaller than over QC 0 or 7 here.

How they were computed:

- Over QC 0 or 7, pooled (Sec. 3.4): `scripts/da/innovation_stats.py`. D1's output directory also holds D2's cycles (01:15 on), so the script was given a directory of links to D1's four `obs_seq.final` files. Per file: 3.6 s, 1.2 GB peak memory (login node).
- Over QC 0 or 7, per analysis time (Sec. 3.3): the same statistics from a short script (session scratchpad, not kept) that uses `check_filter_gate.read_obs_seq`.
- Over the observations assimilated in both runs (Sec. 3.2, Desroziers' estimate in Sec. 3.4): a second short script (session scratchpad, not kept). `innovation_stats.py` takes each run's own QC-0 set for Desroziers' estimate, so its values differ from these.

### 3.2 00:15: the same forecasts, different analyses

All columns are over the observations assimilated (QC 0) in both runs at 00:15 (Sec. 3.1). Per type: their number n, the rms innovation and the rms analysis residual, for D1 and run 5:

| type | n | rms $d_b$ D1 | rms $d_b$ run 5 | rms $d_a$ D1 | rms $d_a$ run 5 |
|---|---|---|---|---|---|
| METAR T2 (K) | 138 | 0.977 | 0.985 | 0.766 | 0.827 |
| METAR q2 (g/kg) | 134 | 1.26 | 1.26 | 1.13 | 1.09 |
| METAR U10 (m/s) | 130 | 1.50 | 1.51 | 1.28 | 1.33 |
| METAR V10 (m/s) | 128 | 1.33 | 1.33 | 1.06 | 1.15 |
| METAR altimeter (hPa) | 134 | 1.06 | 1.06 | 0.675 | 0.824 |
| mesonet T (K) | 1,726 | 1.21 | 1.21 | 1.08 | 1.11 |
| mesonet q (g/kg) | 1,029 | 1.69 | 1.66 | 1.18 | 1.31 |
| mesonet U (m/s) | 459 | 1.60 | 1.60 | 1.48 | 1.51 |
| mesonet V (m/s) | 459 | 2.27 | 2.28 | 1.88 | 1.94 |
| ACARS T (K) | 620 | 0.900 | 0.902 | 0.665 | 0.741 |
| ACARS q (g/kg) | 50 | 0.791 | 0.789 | 0.735 | 0.788 |
| ACARS U (m/s) | 684 | 2.78 | 2.78 | 2.44 | 2.56 |
| ACARS V (m/s) | 698 | 2.63 | 2.64 | 2.18 | 2.32 |
| reflectivity (dBZ) | 51,746 | 9.18 | 9.21 | 6.84 | 7.46 |
| clear air (dBZ) | 8,402 | 2.25 | 2.25 | 1.71 | 1.73 |

Over the same observations: the rms prior spread and Desroziers' estimate $\sigma_{o,D}$, in the units of the type:

| type | spread D1 | spread run 5 | $\sigma_{o,D}$ D1 | $\sigma_{o,D}$ run 5 |
|---|---|---|---|---|
| METAR T2 (K) | 0.743 | 0.765 | 0.824 | 0.867 |
| METAR q2 (g/kg) | 0.773 | 0.711 | 1.06 | 1.13 |
| METAR U10 (m/s) | 0.588 | 0.567 | 1.36 | 1.39 |
| METAR V10 (m/s) | 0.774 | 0.774 | 1.09 | 1.17 |
| METAR altimeter (hPa) | 0.781 | 0.643 | 0.799 | 0.913 |
| mesonet T (K) | 0.749 | 0.767 | 1.11 | 1.13 |
| mesonet q (g/kg) | 0.782 | 0.709 | 1.30 | 1.42 |
| mesonet U (m/s) | 0.558 | 0.537 | 1.53 | 1.55 |
| mesonet V (m/s) | 0.719 | 0.762 | 2.03 | 2.08 |
| ACARS T (K) | 0.579 | 0.628 | 0.749 | 0.802 |
| ACARS q (g/kg) | 0.251 | 0.166 | 0.762 | 0.788 |
| ACARS U (m/s) | 0.894 | 0.912 | 2.57 | 2.65 |
| ACARS V (m/s) | 0.941 | 0.869 | 2.33 | 2.44 |
| reflectivity (dBZ) | 3.05 | 3.04 | 7.56 | 8.06 |
| clear air (dBZ) | 1.07 | 1.09 | 1.85 | 1.88 |

- The ensemble means of the two 00:15 forecasts are close: the same mean state, 15 min of integration, and rms $d_b$ within 2 % for every type (within 1 % for all but mesonet q).
- D1's analysis fits closer for 14 of 15 types, by 2–18 % in rms $d_a$ (METAR altimeter −18 %, ACARS T and mesonet q −10 %, reflectivity and METAR V10 −8 %, METAR T2 −7 %); METAR q2 (+3 %) is the exception.
- Desroziers' estimate is lower in D1 for every type, by 1–13 % (Sec. 3.5).
- **The spread doesn't explain it.** For METAR T2, ACARS T, mesonet T and V and clear air, D1's spread is smaller than run 5's, yet its analysis fits closer: from the same rms $d_b$, D1 removed more of the innovation, although the spread, which sets the isolated-observation gain $k$ (Sec. 3.1), was smaller. That points to the analysis step: the correction of Sec. 2 and the sampling noise in the covariances. For the METAR altimeter (spread 0.78 against 0.64 hPa, from the larger MU perturbations) and the moisture types, the larger spread may add to it.

**Worked example: the METAR T2 rows at 00:15.**

- **The set.** 139 METAR T2 observations had a valid prior at 00:15. Run 5 assimilated all of them; D1 rejected one as an outlier, so n = 138. That observation (35.44° N, 94.80° W) had the same innovation in both runs, $d_b$ = −4.35 K, and the same $\sigma_o$ = 1.26 K, but a smaller spread in D1 (0.64 against 0.77 K). Its outlier threshold $3\sqrt{s_b^2 + \sigma_o^2}$ was therefore 4.24 K in D1 and 4.43 K in run 5: D1 rejected it, run 5 assimilated it. Over each run's own QC-0 set, this one observation would raise run 5's rms $d_a$ from 0.827 to 0.865 K and its $\sigma_{o,D}$ from 0.867 to 0.919 K, and D1's analysis would look 11 % closer instead of 7 %.
- **rms $d_b$** = 0.977 K in D1: the square root of the mean, over the 138 observations, of $d_b^2$, where $d_b$ is the observed 2-m temperature minus the mean of D1's 50 prior members' 2-m temperature at the site. In run 5 (5 members) 0.985 K. The two forecasts fit the observations equally well: $\operatorname{mean}(d_b^2)$ = 0.955 and 0.970 K².
- **spread** = 0.743 K in D1: the rms over the 138 observations of the prior members' standard deviation at the site; 0.765 K in run 5. The rms assigned error is 1.375 K (1.26 K, more near the boundary). The isolated-observation gain $k = s_b^2/(s_b^2 + \sigma_o^2)$ (Sec. 3.1), the fraction of the innovation the analysis would remove if each observation were assimilated alone, averages 0.24 in D1 and 0.23 in run 5.
- **rms $d_a$** = 0.766 K in D1 and 0.827 K in run 5: the same, after the analysis. The analysis took $\operatorname{mean}(d^2)$ from 0.955 to 0.587 K² in D1 (−39 %) and from 0.970 to 0.684 K² in run 5 (−30 %).
- **The realized gain** $g$, the fraction of the innovation the analysis removed, $1 - \operatorname{mean}(d_a d_b)/\operatorname{mean}(d_b^2)$ (Sec. 3.5): 1 − 0.679 / 0.955 = 0.289 in D1, 1 − 0.752 / 0.970 = 0.225 in run 5. With about the same $k$, D1's analysis removed more than one isolated observation would (nearby observations of the same and other types pulled it further), run 5's about as much: the analysis step of Sec. 2 at work.
- **Desroziers**: $\sigma_{o,D} = \sqrt{\operatorname{mean}(d_a d_b)}$ = √0.679 = 0.824 K in D1, √0.752 = 0.867 K in run 5. Same innovations, larger realized gain, smaller product (Eq. 2).
- **Implied** over the same set: √(0.955 − 0.552) = 0.635 K in D1, √(0.970 − 0.585) = 0.620 K in run 5. The one-pass Desroziers estimate lies between it and the assigned 1.375 K in both runs, as the scalar picture says (`obs_error_diagnostics.md` Sec. 5), nearer the implied error in D1. Over QC 0 or 7 (139 observations, with the outlier) the implied error is 0.73 K in D1 and 0.72 K in run 5: one observation with $d_b$ = −4.35 K raises $\operatorname{mean}(d_b^2)$ by 13 % (`obs_error_diagnostics.md` Eq. 2b).

### 3.3 00:30–01:00: the forecasts diverge

The rms innovation (rms $d_b$, QC 0 and 7) of D1 relative to run 5, per type and analysis time: 100 × (D1 / run 5 − 1) %. Negative: D1's prior, its 15-min forecast, fits the observations better.

| type | 00:15 | 00:30 | 00:45 | 01:00 |
|---|---|---|---|---|
| METAR T2 (K) | −1 % | −6 % | 0 % | −9 % |
| METAR q2 (g/kg) | 0 % | −2 % | +2 % | −6 % |
| METAR U10 (m/s) | 0 % | −2 % | −12 % | +1 % |
| METAR V10 (m/s) | 0 % | 0 % | −26 % | −9 % |
| METAR altimeter (hPa) | 0 % | 0 % | −7 % | −6 % |
| mesonet T (K) | 0 % | −3 % | −5 % | −8 % |
| mesonet q (g/kg) | +2 % | −12 % | −14 % | −17 % |
| mesonet U (m/s) | 0 % | −2 % | −1 % | −4 % |
| mesonet V (m/s) | −1 % | −3 % | −6 % | −8 % |
| ACARS T (K) | 0 % | −1 % | −1 % | −4 % |
| ACARS q (g/kg) | 0 % | −10 % | −8 % | +7 % |
| ACARS U (m/s) | 0 % | 0 % | −3 % | −6 % |
| ACARS V (m/s) | 0 % | −1 % | −1 % | −4 % |
| reflectivity (dBZ) | 0 % | −3 % | −7 % | −10 % |
| clear air (dBZ) | 0 % | 0 % | +7 % | +15 % |

- The METARs at 00:45 are few (27–32 per type, against 130–315 at the other times), so their −12 % and −26 % rest on little data.
- The surface types and reflectivity improve in D1 cycle by cycle. Clear-air reflectivity goes the other way from 00:45 (Sec. 4).

### 3.4 Pooled over the four cycles

Pooled over the four analysis times (all observations of a type at 00:15–01:00 together): the rms innovation (rms $d_b$) and the rms prior spread (spread), both over QC 0 and 7, for D1 and run 5:

| type | rms $d_b$ D1 | rms $d_b$ run 5 | spread D1 | spread run 5 |
|---|---|---|---|---|
| METAR T2 (K) | 1.07 | 1.14 | 0.491 | 0.490 |
| METAR q2 (g/kg) | 1.25 | 1.30 | 0.543 | 0.487 |
| METAR U10 (m/s) | 1.59 | 1.61 | 0.688 | 0.627 |
| METAR V10 (m/s) | 1.82 | 1.91 | 0.724 | 0.674 |
| METAR altimeter (hPa) | 1.22 | 1.25 | 0.643 | 0.584 |
| mesonet T (K) | 1.19 | 1.24 | 0.494 | 0.494 |
| mesonet q (g/kg) | 1.33 | 1.45 | 0.528 | 0.472 |
| mesonet U (m/s) | 1.67 | 1.70 | 0.584 | 0.526 |
| mesonet V (m/s) | 2.11 | 2.21 | 0.654 | 0.629 |
| ACARS T (K) | 1.04 | 1.06 | 0.459 | 0.464 |
| ACARS q (g/kg) | 0.902 | 0.871 | 0.292 | 0.189 |
| ACARS U (m/s) | 3.04 | 3.11 | 1.07 | 0.928 |
| ACARS V (m/s) | 2.80 | 2.84 | 0.995 | 0.881 |
| reflectivity (dBZ) | 17.1 | 18.1 | 4.77 | 4.65 |
| clear air (dBZ) | 5.10 | 4.80 | 2.46 | 2.18 |

Pooled the same way, each divided by the rms assigned error $\sqrt{\operatorname{mean}(\sigma_o^2)}$ over its set: the implied error $\sigma_{o,\mathrm{implied}}$ (`obs_error_diagnostics.md` Eq. 2) over QC 0 or 7, and Desroziers' estimate $\sigma_{o,D}$ (Sec. 4.1 there) over the observations assimilated in both runs (Sec. 3.1). Below 1: the innovations support a smaller error than the one assigned.

| type | implied ratio D1 | implied ratio run 5 | Desroziers ratio D1 | Desroziers ratio run 5 |
|---|---|---|---|---|
| METAR T2 | 0.70 | 0.76 | 0.69 | 0.76 |
| METAR q2 | 0.85 | 0.91 | 0.82 | 0.87 |
| METAR U10 | 0.83 | 0.86 | 0.73 | 0.80 |
| METAR V10 | 0.97 | 1.04 | 0.71 | 0.78 |
| METAR altimeter | 0.96 | 1.03 | 0.75 | 0.84 |
| mesonet T | 0.33 | 0.35 | 0.34 | 0.36 |
| mesonet q | 0.78 | 0.88 | 0.72 | 0.84 |
| mesonet U | 0.48 | 0.50 | 0.49 | 0.50 |
| mesonet V | 0.61 | 0.65 | 0.60 | 0.64 |
| ACARS T | 0.84 | 0.86 | 0.66 | 0.70 |
| ACARS q | 0.68 | 0.67 | 0.58 | 0.59 |
| ACARS U | 1.06 | 1.10 | 0.86 | 0.93 |
| ACARS V | 0.97 | 1.01 | 0.82 | 0.88 |
| reflectivity | 3.13 | 3.33 | 1.29 | 1.56 |
| clear air | 0.83 | 0.80 | 0.39 | 0.38 |

The rms assigned errors $\sqrt{\operatorname{mean}(\sigma_o^2)}$ the ratios divide by (with the boundary inflation; the same in both runs, and the same to 0.01 over both sets): METAR T2 1.36 K, q2 1.32 g/kg, wind 1.72 m/s, altimeter 1.08 hPa; mesonet T 3.27 K, q 1.56 g/kg, wind 3.26 m/s; ACARS T 1.10 K, q 1.26 g/kg, wind 2.69 m/s; reflectivity 5.24 dBZ, clear air 5.35 dBZ.

- D1's prior spread is about the same for temperature and larger for moisture (ACARS q +55 %, METAR q2 +11 %, mesonet q +12 %) and wind (+4–15 %), as the state-space spreads in `fulltest_steps.md` D1 (QVAPOR 13–20 % larger from 00:30).
- D1 rejected 15 % fewer reflectivity observations as outliers (96,017 against 112,656 over the four cycles) and assimilated 8 % more (220,740 against 204,101); 200,202 were assimilated in both.

### 3.5 What changes in the error diagnosis

**The implied error** depends only on the innovations $d_b$ and the spread (`obs_error_diagnostics.md` Sec. 3). It is 2–11 % smaller in D1 for 13 of 15 types (not ACARS q, +1 %, nor clear air, +4 %), mostly because D1's forecasts fit better from 00:30 on.

**Desroziers' estimate** also depends on the gain. Let $g$ be the realized gain, the fraction of the innovation the analysis removed in observation space: $g = \operatorname{mean}\big((H(x_a) - H(x_b))\,d_b\big) / \operatorname{mean}(d_b^2)$, so that $\operatorname{mean}(d_a d_b) = (1 - g)\operatorname{mean}(d_b^2)$. With (A1) and (A2) of `obs_error_diagnostics.md`, $\operatorname{mean}(d_b^2) = \sigma_b^2 + \sigma_o^2$ with the true variances, and

$$
\begin{aligned}
\operatorname{mean}(d_a d_b) &= (1 - g) \, \operatorname{mean}(d_b^2) \\
&= \sigma_o^2 + (g_{\mathrm{opt}} - g) \, \operatorname{mean}(d_b^2)
\end{aligned}
\tag{2}
$$

where $g_{\mathrm{opt}} = \sigma_b^2 / (\sigma_b^2 + \sigma_o^2)$ is the gain the true variances would give. Desroziers' estimate is right when the realized gain is the optimal one (`obs_error_diagnostics.md` Sec. 4.1–4.2), too high when it is smaller and too low when it is larger, by $(g_{\mathrm{opt}} - g)\operatorname{mean}(d_b^2)$, at most $\sigma_b^2$ (for $g \ge 0$). The realized gain departs from the optimal one for several reasons: assigned errors or spread that are off (`obs_error_diagnostics.md` Sec. 4.3), and in the EAKF the localization, the updates by nearby observations and the sampling-error correction of Sec. 2. For an observation assimilated alone, $g$ is the isolated-observation gain $k = s_b^2/(s_b^2 + \sigma_o^2)$ (Sec. 3.1; `obs_error_diagnostics.md` Sec. 4.1).

- At 00:15, on the observations both runs assimilated, the innovations are the same, and Desroziers' estimate is 1–13 % lower in D1 for every type (METAR T2 0.82 against 0.87 K), because D1's realized gain is larger (METAR T2: 0.29 against 0.225; worked example in Sec. 3.2).
- Pooled, Desroziers' estimate falls by clearly more than the implied error for METAR U10 (−9 % against −3 %), the METAR altimeter (−11 % against −6 %), ACARS T (−7 % against −2 %) and reflectivity (−17 % against −6 %); for the other 11 types the two fall by amounts within 4 percentage points of each other.
- Which run's estimate is nearer the truth depends on $g_{\mathrm{opt}}$, i.e. on the true prior error, which is unknown. If the spread were right ($\sigma_b^2 = s_b^2$), METAR T2 at 00:15 would have $g_{\mathrm{opt}}$ = 0.552 / 0.955 = 0.58 in D1 and 0.585 / 0.970 = 0.60 in run 5, far above both realized gains: both estimates too high, run 5's more. With assigned errors larger than the innovations support (Sec. 3.4), a realized gain below the optimal one is what to expect.

**The direction of `obs_expansion.md` Sec. 5 holds at 50 members.** METAR T2's implied and Desroziers errors are 0.69–0.70 of the assigned error in D1 (≈ 0.95 K), mesonet T 0.33–0.34 and mesonet wind 0.48–0.61. The pilot's METAR ratios of Sec. 5 (T2 0.38–0.43) were relative to DART's default errors (Sec. 1); in kelvin, METAR T2's implied error is 1.03 K in the pilot (`obs_error_diagnostics.md` Sec. 4.3), 1.03 K in run 5 and 0.95 K in D1, and the ratio is higher now because the assigned error was lowered to 1.26 K after the pilot. Reflectivity's Desroziers estimate stays above the assigned 5.2 dBZ (6.8 dBZ in D1, over the observations both runs assimilated), clear air's far below its 5.35 dBZ (2.1 dBZ); Sec. 3.6 explains why reflectivity's numbers say little about its observation error. One hour of one case, as in the pilot; no change to the errors is proposed here. Sec. 5 of `obs_expansion.md` already asked for a recheck on a longer run, by time of day, and D2's six hours could give it.

### 3.6 Reflectivity: why the implied error is three times the assigned one

Reflectivity's implied ratio is 3.1 (Sec. 3.4): in D1, pooled, $\sqrt{291.5 - 22.8}$ = 16.4 dBZ against 5.24 dBZ assigned. By `obs_error_diagnostics.md` Eq. 2b the implied error holds the observation error, the prior error variance the spread misses, and the squared bias. For reflectivity it is almost all the last two. The numbers below are D1's, pooled over 00:15–01:00, over its QC 0 or 7 set (316,757 observations) unless said otherwise.

**How the observations are chosen** (`scripts/da/mrms_to_obs_seq.py`, HRRRDAS settings):

- precipitation observations only where MRMS has at least 10 dBZ (`--precip-dbz-thresh`), at every other grid point (5 km) and every third MRMS level;
- clear-air observations only where MRMS has 0 dBZ or less, set to −10 dBZ, at 4.0 and 8.5 km and every sixth grid point (15 km);
- the forward operator is floored at −10 dBZ (`apply_ref_limit_to_fwd_op = .true.`, `reflectivity_limit_fwd_op = -10.0` in `&obs_def_radar_mod_nml`); −10.0 dBZ is also the smallest prior member value in observation space.

So a missed or misplaced storm gives a large positive $d_b$ in the precipitation type, while the opposite error, a forecast echo where MRMS has less than 10 dBZ, never enters this type; the clear-air type sees it only where MRMS has 0 dBZ or less, and only on two levels. The observed values are 10 dBZ and above (median 17.5 dBZ); the prior means reach down to the floor (median 10.6 dBZ).

**Where the summed $d_b^2$ comes from** (the rows overlap):

| observations | share of observations | share of summed $d_b^2$ |
|---|---|---|
| rejected as outliers (QC 7) | 30 % | 71 % |
| prior mean below 10 dBZ | 49 % | 75 % |
| above all 50 prior members | 54 % | 77 % |

- **The bias**: $\operatorname{mean}(d_b)$ = +8.84 dBZ, 27 % of $\operatorname{mean}(d_b^2)$ = 291.5 dBZ². Without it the implied error would be 13.8 dBZ.
- **The outliers**: mean $d_b$ +19.4 dBZ, rms $d_b$ 26.2 dBZ, rms spread 2.5 dBZ; 86,005 of the 96,017 have $d_b > 0$ (forecast too low). The assimilated observations: mean $d_b$ +4.2 dBZ, rms $d_b$ 11.0 dBZ, rms spread 5.5 dBZ.
- **No forecast echo** (prior mean below 10 dBZ): rms $d_b$ 21.2 dBZ against an rms spread of 4.0 dBZ; 52 % of these observations are outliers.
- **Outside the ensemble**: at 54 % of the observations the observed value is above all 50 prior members, at 10.6 % below all of them. These are the end bins of a rank histogram (here without observation-error noise added to the members).

**Reading.** The implied error mostly measures prior error that the ensemble doesn't represent: storms missing or in the wrong place, in a quantity that is bounded below (the −10 dBZ floor) and far from Gaussian, so assumption (A3) of `obs_error_diagnostics.md` fails badly; plus a bias that the selection of the observations builds in. It is not an estimate of MRMS's error. One hour after the cold start the ensemble doesn't cover the observed echoes, which is the 6-h gate's spin-up question (`fulltest_steps.md` Sec. 0, `handoffs/2026-11-13_fulltest_d2_analysis.md`).

**From the implied error to Desroziers' estimate** (D1, pooled; each value divided by the rms assigned error over its set, 5.24 and 5.23 dBZ):

| estimate | observations | dBZ | ratio |
|---|---|---|---|
| implied | QC 0 or 7 | 16.4 | 3.13 |
| implied | D1's QC 0 | 9.5 | 1.82 |
| Desroziers | D1's QC 0 | 7.1 | 1.35 |

(Over the observations assimilated in both runs, Sec. 3.4: 6.8 dBZ, ratio 1.29.) Dropping the outliers is the bigger step. The gain does the rest. From the definitions alone (Sec. 3.5 and `obs_error_diagnostics.md` Eq. 2), over one set,

$$
\sigma_{o,D}^2 = \sigma_{o,\mathrm{implied}}^2 - \left( g - \frac{\operatorname{mean}(s_b^2)}{\operatorname{mean}(d_b^2)} \right) \operatorname{mean}(d_b^2)
\tag{3}
$$

so Desroziers' estimate falls below the implied error exactly when the realized gain is larger than $\operatorname{mean}(s_b^2)/\operatorname{mean}(d_b^2)$, the optimal gain if the spread were right. Over D1's assimilated reflectivity observations, $\operatorname{mean}(d_b^2)$ = 120.1 dBZ², $\operatorname{mean}(s_b^2)$ = 29.9 dBZ² and $\operatorname{mean}(d_a d_b)$ = 50.0 dBZ², so $g$ = 1 − 50.0 / 120.1 = 0.584 against 29.9 / 120.1 = 0.249, and Eq. 3 gives 90.2 − 0.335 × 120.1 = 50.0 dBZ².

Per cycle, over the observations assimilated in both runs, the isolated-observation gain $k$ and the realized gain $g$ (Sec. 3.1):

| time | $k$ D1 | $g$ D1 | $k$ run 5 | $g$ run 5 |
|---|---|---|---|---|
| 00:15 | 0.17 | 0.32 | 0.15 | 0.24 |
| 00:30 | 0.32 | 0.51 | 0.29 | 0.39 |
| 00:45 | 0.39 | 0.61 | 0.37 | 0.48 |
| 01:00 | 0.43 | 0.68 | 0.43 | 0.55 |

- $k$ grows over the hour as the reflectivity spread grows. $g$ is 1.6–1.9 times $k$ in D1 and 1.3–1.5 times in run 5.
- $g > k$ because each radar observation has many neighbours seeing the same storm error: precipitation observations every 5 km and every third level, with the radar localization reaching zero at 18 km, so dozens of them update the state the forward operator reads at one observation's site. As an illustration, with $s_b$ = 3 dBZ and $\sigma_o$ = 5.24 dBZ one observation alone gets $k$ = 9 / (9 + 27.4) = 0.25, while four observations of the same point with independent errors act like one with a quarter of the error variance: 9 / (9 + 6.85) = 0.57. The same effect is behind ACARS T in `obs_error_diagnostics.md` Sec. 5.
- Run 5's ratios are smaller: at 5 members the sampling-error correction damps the neighbours' contributions (Sec. 2).
- By Eq. 2, a gain above the optimal one makes Desroziers' estimate too low, a gain below it too high. Here the optimal gain is unknown. With (A1) and (A2), $g_{\mathrm{opt}} = \sigma_b^2/\operatorname{mean}(d_b^2)$: it is at least 0.25 if the ensemble is underdispersive (the spread-based value; the 54 % of observations above all members say it is), and at most 1. The realized 0.58 can be on either side of it, and (A1) fails here anyway (the bias). So 6.8–7.1 dBZ is not a clean estimate of the radar error either.

## 4. Clear-air reflectivity

From 00:45 on, D1's clear-air rms innovation (rms $d_b$, QC 0 and 7) grows faster than run 5's: 5.31 against 4.96 dBZ at 00:45 and 5.87 against 5.09 at 01:00. The rms prior spread grows with it (3.30 against 2.82 dBZ at 01:00). In `check_cycle.log`'s subset (QC 0 and 1) rms $d_b$ is 3.59 / 4.18 dBZ against 3.24 / 3.79, with the bias $\operatorname{mean}(d_b)$ (observation minus forecast) −0.98 / −1.25 against −0.80 / −0.98 (`fulltest_steps.md` D1): the forecasts put more reflectivity than observed into clear air, by more each cycle, and more in D1. Whether that is spurious echo and where it is would need maps (`REFL_10CM` of the priors against the MRMS clear-air points); not done.

## 5. Open questions and next steps

1. **The correction's share of the increment difference**, from one analysis at 00:15 (no cycling), compared with the existing 00:15 analyses: (a) run 5's 00:15 prior with `sampling_error_correction = .false.`; or (b) 5-member subsets of D1's 00:15 prior, with the correction on and off. Run 5's extraction plus filter took 220 s on 40 nodes at 00:15, so about 2.4 node-hours per analysis if it needs 40 nodes; a 5-member filter on fewer nodes is not measured. A test, with the user's go-ahead.
2. **Whether to keep the correction at 50 members.** It still damps weak correlations (0.28 at $\hat r$ = 0.1, 0.60 at 0.2), on top of the localization. A design question for D2 and after; nothing changed. `dart_sampling_error_correction.md` Sec. 8 items 4–5 have A12's results on it and the limits of its uniform prior.
3. **Why D1's adaptive inflation is smaller** (`fulltest_steps.md` D1: U mean 1.053 against 1.098 at 01:00). The correction doesn't enter the inflation update (Sec. 2); the uncorrected sample correlations, noisier at 5 members, and the different innovations could both matter. Not examined.
4. **Rank histograms** from the `obs_seq.final` files (50 prior members per observation), for the surface and radar types; run 5's 5 members give only 6 bins.
5. **The clear-air misfit** (Sec. 4): maps.
