# D1 against run 5: sampling-error correction and innovation statistics

Written 2026-11-12 in session "fulltest: D1 analysis". Compares D1, the first gate of the 50-member run `_conv_refl_f2` (`cases/20250520/da_theta_m0_n50/output_conv_refl_f2/`, analyses 00:15–01:00), with run 5 `_conv_refl_f2` of the 5-member experiment (`da_theta_m0_n5/output_conv_refl_f2/`). It continues `fulltest_steps.md` D1 ("D1 against run 5", from both runs' `check_cycle.log`), which it doesn't repeat. Background: `dart_sampling_error_correction.md` (the correction's math, table and code path; its notation is used here) and `obs_error_diagnostics.md` (the implied error and Desroziers' estimate).

**Typora.** Display equations are `$$` blocks. Inline math (`$...$`) needs *Preferences → Markdown → Inline Math*.

## Summary

- **The filter namelists differ only in `ens_size`** (and the number of members written). Both runs use the sampling-error correction, which multiplies each observation-to-state regression by a factor $S(\hat r, N)$: at a sample correlation $\hat r$ = 0.5, $S$ = 0.12 for 5 members and 0.89 for 50; at 0.9, 0.49 and 0.98 (`dart_sampling_error_correction.md` Sec. 7). That note's Sec. 8 expected the 5-member results not to carry over to 50 members for this reason alone. D1 shows the effect (Sec. 2, 3.2).
- **At 00:15 the forecasts are the same and the analyses are not** (Sec. 3.2). Both priors are 15-min forecasts from the cold start; their rms O−F agrees within 2 % for every type. D1's analysis fits closer for 13 of 15 types (posterior rms 2–15 % smaller), also where its spread is smaller (METAR T2, ACARS T). That difference comes from the analysis step, not from the spread.
- **From 00:30 on the forecasts diverge** (Sec. 3.3): D1's are better for the surface types and reflectivity (at 01:00 mesonet q −17 %, reflectivity −10 %, METAR T2 −9 % in rms O−F), worse for clear-air reflectivity (+7 % at 00:45, +15 % at 01:00).
- **The error diagnosis keeps its direction** (Sec. 3.5): the conventional errors we assign are generous (mesonet T and wind most), the reflectivity error is too small and the clear-air error too large, in both runs. The implied errors are 2–11 % smaller in D1, because its forecasts fit better. Desroziers' estimates are smaller by more for several types (reflectivity −15 %, ACARS q −14 %): they depend on the gain as well as on the observations, and a damped gain raises them (Eq. 2).
- **Not known yet**: how much of D1's larger increments is the correction and how much the less noisy covariances; why D1's adaptive inflation is smaller; where the clear-air misfit grows. Next steps in Sec. 5.

## 1. What differs between the runs

- **Namelist**: the diff of the two runs' 00:30 `filter/input.nml` shows only `ens_size` (5, 50), `num_output_state_members` and `num_output_obs_members` (5, 50), and the comment block naming the 50-member file's origin.
- **Initial perturbations**: 50 of the 150 bank draws against 5 of the pilot's 15 (`fulltest_steps.md` D1).
- **The same**: the observations (identical counts per type and cycle), `settings.txt`, the mean states and the boundary recipe. At 00:15 both runs had prior inflation 1 everywhere (`fill_inflation_restart`, `prior_inf_mean = 1.00`), so the 00:15 spreads are the raw ensemble spreads.

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
- **What `fulltest_steps.md` D1 found on the analysis side follows**: larger increments in D1 (MU, U, QRAIN, QGRAUP, `REFL_10CM`) and a closer analysis fit (reflectivity posterior rms 5.0 against 6.7 dBZ at 01:00). Sec. 3.2 shows the same at 00:15, where the priors are the same.
- **The inflation** adapts with the uncorrected $\hat r$, so the correction doesn't explain D1's smaller adaptive inflation directly.
- **The post-analysis shock**: A12 found the correction made analyses more unbalanced (Sec. 8 item 4 there). Both of our runs have it on, so D1 doesn't test that; D1, with the less damped and larger increments, had the larger first-minute adjustment through 00:45.
- **Even at 50 members** the correction is not small for weak correlations: 0.28 at $\hat r$ = 0.1, 0.60 at 0.2.
- **Not known**: the distribution of sample correlations in our analyses, so how much of the increment difference is the correction and how much the other effect of size, the noise in $\hat b$ itself. A one-cycle test would measure it (Sec. 5).

## 3. Innovation statistics

### 3.1 How they were computed

- Pooled over 00:15–01:00: `scripts/da/innovation_stats.py`. D1's output directory also holds D2's cycles (01:15 on), so the script was given a directory of links to D1's four `obs_seq.final` files. Per file: 3.6 s, 1.2 GB peak memory (login node).
- Per cycle: the same statistics from a short script (session scratchpad, not kept) that uses `check_filter_gate.read_obs_seq`.
- Selections as in `innovation_stats.py` (`obs_error_diagnostics.md` Sec. 7): O−F, spread and the implied error over DART QC 0 and 7 (assimilated, and rejected as outliers); the posterior rms and Desroziers' estimate over QC 0. Because outliers are included, reflectivity's rms O−F here (16–19 dBZ) is larger than in `check_cycle.log` (~11 dBZ, QC 0 and 1).
- Specific humidity in g/kg. The assigned error $\sigma_o$ includes the preprocessor's boundary inflation, so the ratios to it are comparable between the runs, not the absolute values with the base errors.
- The mesonet altimeter is evaluated only (QC 1), so its rows would cover only its rejected outliers; it is left out.

### 3.2 00:15: the same forecasts, different analyses

Rms observation minus prior (O−F) and minus analysis, at 00:15:

| type | O−F D1 | O−F run 5 | analysis D1 | analysis run 5 |
|---|---|---|---|---|
| METAR T2 (K) | 1.04 | 1.05 | 0.766 | 0.865 |
| METAR q2 (g/kg) | 1.26 | 1.26 | 1.12 | 1.09 |
| METAR U10 (m/s) | 1.50 | 1.50 | 1.28 | 1.33 |
| METAR V10 (m/s) | 1.77 | 1.78 | 1.06 | 1.15 |
| METAR altimeter (hPa) | 1.54 | 1.53 | 0.697 | 0.824 |
| mesonet T (K) | 1.28 | 1.28 | 1.08 | 1.11 |
| mesonet q (g/kg) | 1.72 | 1.69 | 1.19 | 1.31 |
| mesonet U (m/s) | 1.59 | 1.60 | 1.48 | 1.51 |
| mesonet V (m/s) | 2.27 | 2.28 | 1.88 | 1.94 |
| ACARS T (K) | 1.01 | 1.01 | 0.665 | 0.741 |
| ACARS q (g/kg) | 0.791 | 0.789 | 0.735 | 0.788 |
| ACARS U (m/s) | 3.49 | 3.50 | 2.45 | 2.58 |
| ACARS V (m/s) | 3.10 | 3.10 | 2.18 | 2.31 |
| reflectivity (dBZ) | 16.0 | 16.0 | 6.92 | 7.50 |
| clear air (dBZ) | 4.62 | 4.64 | 1.79 | 1.77 |

Prior spread and Desroziers' estimate at 00:15:

| type | spread D1 | spread run 5 | Desroziers D1 | Desroziers run 5 |
|---|---|---|---|---|
| METAR T2 (K) | 0.742 | 0.765 | 0.824 | 0.919 |
| METAR q2 (g/kg) | 0.773 | 0.711 | 1.06 | 1.12 |
| METAR U10 (m/s) | 0.588 | 0.567 | 1.36 | 1.39 |
| METAR V10 (m/s) | 0.775 | 0.773 | 1.09 | 1.17 |
| METAR altimeter (hPa) | 0.806 | 0.658 | 0.852 | 0.913 |
| mesonet T (K) | 0.749 | 0.767 | 1.11 | 1.13 |
| mesonet q (g/kg) | 0.781 | 0.709 | 1.31 | 1.43 |
| mesonet U (m/s) | 0.558 | 0.537 | 1.53 | 1.54 |
| mesonet V (m/s) | 0.719 | 0.762 | 2.03 | 2.08 |
| ACARS T (K) | 0.578 | 0.627 | 0.749 | 0.802 |
| ACARS q (g/kg) | 0.251 | 0.166 | 0.762 | 0.788 |
| ACARS U (m/s) | 0.898 | 0.911 | 2.59 | 2.67 |
| ACARS V (m/s) | 0.939 | 0.872 | 2.33 | 2.44 |
| reflectivity (dBZ) | 2.77 | 2.69 | 7.70 | 8.13 |
| clear air (dBZ) | 1.20 | 1.19 | 1.98 | 1.94 |

- The ensemble means of the two 00:15 forecasts are close: the same mean state, 15 min of integration, and rms O−F within 2 % for every type (within 1 % for all but mesonet q).
- D1's analysis fits closer for 13 of 15 types, by 2–15 % in rms (METAR altimeter −15 %, METAR T2 −11 %, ACARS T −10 %, mesonet q −9 %, reflectivity −8 %); METAR q2 (+3 %) and clear air (+1 %) are the exceptions.
- **The spread doesn't explain it.** For METAR T2, ACARS T and mesonet V, D1's spread is smaller than run 5's, yet its analysis fits closer: the gain realized in observation space was larger with less spread. That points to the analysis step: the correction of Sec. 2 and the sampling noise in the covariances. For the METAR altimeter (spread 0.81 against 0.66 hPa, from the larger MU perturbations) and the moisture types, the larger spread may add to it.

### 3.3 00:30–01:00: the forecasts diverge

Rms O−F of D1 relative to run 5 (negative: D1's forecast fits better):

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

Rms O−F and prior spread:

| type | O−F D1 | O−F run 5 | spread D1 | spread run 5 |
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

Implied error and Desroziers' estimate, each divided by the assigned $\sigma_o$ (rms; the same in both runs):

| type | implied D1 | implied run 5 | Desroziers D1 | Desroziers run 5 |
|---|---|---|---|---|
| METAR T2 | 0.70 | 0.76 | 0.69 | 0.77 |
| METAR q2 | 0.85 | 0.91 | 0.84 | 0.87 |
| METAR U10 | 0.83 | 0.86 | 0.74 | 0.82 |
| METAR V10 | 0.97 | 1.04 | 0.73 | 0.78 |
| METAR altimeter | 0.96 | 1.03 | 0.76 | 0.84 |
| mesonet T | 0.33 | 0.35 | 0.34 | 0.36 |
| mesonet q | 0.78 | 0.88 | 0.73 | 0.84 |
| mesonet U | 0.48 | 0.50 | 0.49 | 0.50 |
| mesonet V | 0.61 | 0.65 | 0.60 | 0.64 |
| ACARS T | 0.84 | 0.86 | 0.66 | 0.71 |
| ACARS q | 0.68 | 0.67 | 0.58 | 0.67 |
| ACARS U | 1.06 | 1.10 | 0.88 | 0.93 |
| ACARS V | 0.97 | 1.01 | 0.83 | 0.88 |
| reflectivity | 3.13 | 3.33 | 1.35 | 1.58 |
| clear air | 0.83 | 0.80 | 0.41 | 0.41 |

The assigned $\sigma_o$ (rms, with the boundary inflation): METAR T2 1.36 K, q2 1.32 g/kg, wind 1.72 m/s, altimeter 1.08 hPa; mesonet T 3.27 K, q 1.56 g/kg, wind 3.26 m/s; ACARS T 1.10 K, q 1.26 g/kg, wind 2.69 m/s; reflectivity 5.24 dBZ, clear air 5.35 dBZ.

- D1's prior spread is about the same for temperature and larger for moisture (ACARS q +55 %, METAR q2 +11 %, mesonet q +12 %) and wind (+4–15 %), as the state-space spreads in `fulltest_steps.md` D1 (QVAPOR 13–20 % larger from 00:30).
- D1 rejected 15 % fewer reflectivity observations as outliers (96,017 against 112,656 over the four cycles) and assimilated 8 % more (220,740 against 204,101).

### 3.5 What changes in the error diagnosis

**The implied error** depends only on O−F and the spread (`obs_error_diagnostics.md` Sec. 3). It is 2–11 % smaller in D1 for 13 of 15 types (not ACARS q, +1 %, nor clear air, +4 %), mostly because D1's forecasts fit better from 00:30 on.

**Desroziers' estimate** also depends on the gain. In the scalar picture of `obs_error_diagnostics.md` Sec. 4.1 the analysis takes the fraction $k = s_b^2 / (s_b^2 + \sigma_o^2)$ of the innovation $d_b$. If the gain realized in observation space is $c\,k$ instead ($c < 1$: damped), then

$$
\begin{aligned}
\operatorname{mean}(d_a d_b) &= (1 - c\,k) \, \operatorname{mean}(d_b^2) \\
&= \sigma_o^2 + (1 - c) \, \sigma_b^2
\end{aligned}
\tag{2}
$$

where the second line holds when the assumed variances are the true ones ($\sigma_b^2$ the true prior error variance in observation space, $\sigma_o^2$ the true observation error variance); $c = 1$ is the case of `obs_error_diagnostics.md` Sec. 4.1. A damped gain raises the estimate by $(1 - c)\,\sigma_b^2$, independently of the observation error. In the EAKF, $c$ is an effective factor: the correction of Sec. 2, localization and the updates by nearby observations all enter it, so it is not a table value.

- At 00:15, where the innovations of the two runs are the same, Desroziers' estimate is already 1–10 % lower in D1 for 14 of 15 types (METAR T2 0.82 against 0.92 K; clear air +2 %). That part is the gain.
- Pooled, Desroziers falls by clearly more than the implied error for METAR U10 (−9 % against −3 %), ACARS T (−7 % against −2 %), ACARS q (−14 % against 0 %) and reflectivity (−15 % against −6 %); for the other 11 types the two fall by amounts within 4 percentage points of each other.
- So Desroziers' estimates from the 5-member runs are biased high by the damped gain, by at most the prior error variance. That bound is not small: for METAR T2 at 00:15 the spread gives $s_b^2 \approx$ 0.55–0.59 K², against $\sigma_{o,D}^2$ = 0.68 K² in D1 and 0.84 K² in run 5; the difference between the runs, 0.17 K², lies within it.

**The direction of `obs_expansion.md` Sec. 5 holds at 50 members.** METAR T2's implied and Desroziers errors are 0.69–0.70 of the assigned error in D1 (≈ 0.95 K), mesonet T 0.33–0.34 and mesonet wind 0.48–0.61. Reflectivity's Desroziers estimate stays above the assigned 5.2 dBZ (7.1 dBZ in D1), clear air's far below its 5.35 dBZ (2.2 dBZ). One hour of one case, as in the pilot; no change to the errors is proposed here. Sec. 5 of `obs_expansion.md` already asked for a recheck on a longer run, by time of day, and D2's six hours could give it.

## 4. Clear-air reflectivity

From 00:45 on, D1's clear-air O−F grows faster than run 5's: 5.31 against 4.96 dBZ at 00:45 and 5.87 against 5.09 at 01:00 (QC 0 and 7). The spread grows with it (3.30 against 2.82 dBZ at 01:00). In `check_cycle.log`'s subset (QC 0 and 1) the forecast rms is 3.59 / 4.18 dBZ against 3.24 / 3.79, with the bias (observation − forecast) −0.98 / −1.25 against −0.80 / −0.98 (`fulltest_steps.md` D1): the forecasts put more reflectivity than observed into clear air, by more each cycle, and more in D1. Whether that is spurious echo and where it is would need maps (`REFL_10CM` of the priors against the MRMS clear-air points); not done.

## 5. Open questions and next steps

1. **The correction's share of the increment difference**, from one analysis at 00:15 (no cycling), compared with the existing 00:15 analyses: (a) run 5's 00:15 prior with `sampling_error_correction = .false.`; or (b) 5-member subsets of D1's 00:15 prior, with the correction on and off. Run 5's extraction plus filter took 220 s on 40 nodes at 00:15, so about 2.4 node-hours per analysis if it needs 40 nodes; a 5-member filter on fewer nodes is not measured. A test, with the user's go-ahead.
2. **Whether to keep the correction at 50 members.** It still damps weak correlations (0.28 at $\hat r$ = 0.1, 0.60 at 0.2), on top of the localization. A design question for D2 and after; nothing changed. `dart_sampling_error_correction.md` Sec. 8 items 4–5 have A12's results on it and the limits of its uniform prior.
3. **Why D1's adaptive inflation is smaller** (`fulltest_steps.md` D1: U mean 1.053 against 1.098 at 01:00). The correction doesn't enter the inflation update (Sec. 2); the uncorrected sample correlations, noisier at 5 members, and the different O−F could both matter. Not examined.
4. **Rank histograms** from the `obs_seq.final` files (50 prior members per observation), for the surface and radar types; run 5's 5 members give only 6 bins.
5. **The clear-air misfit** (Sec. 4): maps.
