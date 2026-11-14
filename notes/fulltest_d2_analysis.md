# D2 analysis: radar reflectivity in observation space

Written 2026-11-13 in session "fulltest: D2 analysis". It covers the first 6 h of the 50-member production run `_conv_refl_f2` (`cases/20250520/da_theta_m0_n50/output_conv_refl_f2/`), analyses 05-20 00:15–06:00 (24 cycles: D1's 4 and D2's 20), for **radar reflectivity only**; the conventional types and the clear-air obs are still to do. It records what `obs_diag` showed and the discussion with the user about it. The spin-up options that came out of it are in `refl_spinup_options.md`. The 6-h gate decisions were taken earlier, in session "fulltest: D3 run" (`fulltest_steps.md` D3: everything kept, 2 nodes per member; a free ensemble and a spin-up variant would be separate runs).

**Typora.** Display equations are `$$` blocks. Inline math (`$...$`) needs *Preferences → Markdown → Inline Math*.

## Summary

- **The radar fit improves over the 6 h and levels off after about 03:00** (Sec. 4.1). Over all radar obs with a valid prior, outliers included, the prior rmse peaks at 17.6 dBZ (00:30–00:45) and is 10.2–11.4 dBZ from 03:00 on; the bias (observation minus model) falls from +9.4 to +2.6–4.0 dBZ; the prior spread rises from 2.8 to about 6 dBZ by 01:30.
- **The outlier share falls from 31–33 % (00:15–00:30) to about 7 % by 03:00** and stays at 6–9 % (Sec. 4.1, 5).
- **The ensemble is still underdispersive when the outliers are counted**: total spread / rmse rises from 0.37 to about 0.75 (Sec. 4.1). On the assimilated obs alone it reaches about 1.0 from 03:00, but that set leaves the outliers out by construction.
- **The posterior fits the assimilated radar obs to 3.2–3.5 dBZ from 03:00 on**, below the assigned error of 5 dBZ, so the posterior ratios are not a consistency test (Sec. 4.1).
- **The 11-km level stands out**: 29 % outliers and a bias of +13.5 dBZ, pooled over the 24 cycles (Sec. 4.2).
- **The outliers are mostly not extreme reflectivity** (Sec. 5.3). 37–64 % per cycle are obs where no member has any echo; most of the rest are weak echoes (median 14 dBZ) where only a few members have one. Only the "all members have an echo" group has strong obs (median 23–30 dBZ), and part of it, early on, is the model being too strong; this group falls from 38 % of the outliers at 00:15 to 2–6 % after 03:00.
- **The number of outliers where no member has an echo falls** from 8,800–10,100 per cycle (00:15–01:00, 11–13 % of the radar obs) to about 3,000 (3.5–4 %) after 02:45, with a rise to 4,600–5,000 at 04:45–05:00 (Sec. 5.3). **These obs can't be assimilated**: with every member at the −10 dBZ floor the prior spread is zero, so the outlier test rejects them, and even without the test the EAKF would give them zero weight (Sec. 5.2).
- `obs_diag` was set up for this, checked against an independent recomputation, and a DART bug in its humidity rank histograms was found and fixed (Sec. 1).

## 1. How the numbers were made

### 1.1 `obs_diag`

DART's `obs_diag` (`../software/DART/models/wrf/work/obs_diag`) ran for the first time in this project, on the 24 `obs_seq.final` files of 00:15–06:00:

- **Scripts** (new, 2026-11-13): `scripts/da/run_obs_diag.sh <output dir> <first> <last> <assim|all> <diag dir>` writes the file list and `input.nml` (the run's filter namelist plus the `&obs_diag_nml` template `cases/20250520/da_theta_m0_n50/config/input.nml.obs_diag`) and runs `obs_diag`; `scripts/da/check_obs_diag.py <diag dir>` recomputes everything from the `obs_seq.final` files; `scripts/da/plot_obs_diag.py` makes the figures.
- **Bins** (`config/input.nml.obs_diag`): 15-min time bins centred on the analysis times, each bin [t − 449 s, t + 450 s] equal to the cycle's observation window; radar in 9 height bins centred on the MRMS heights (Sec. 2); ACARS in 100-hPa layers; the surface types on one level; the whole domain as the only region.
- **Two QC selections** (user, 2026-11-13). *assim*: DART's default, prior statistics over DART QC 0–3 and posterior over QC 0–1, rank histogram without outliers. *all*: every type listed in `trusted_obs`, which adds QC 7 (outliers) to both, rank histogram with outliers; its prior statistics use the selection of `fulltest_d1_analysis.md` Sec. 3.1 (QC 0 or 7). For radar reflectivity only QC 0, 4 (prior forward operator failed, at most a few per cycle) and 7 occur, so *all* means QC 0 or 7 and *assim* means QC 0.
- **Output**: `cases/20250520/da_theta_m0_n50/diag_conv_refl_f2/obs_diag/all_202505200015-202505200600/` and `assim_202505200015-202505200600/` (3.4 MB each: `obs_diag_output.nc`, logs, `check_obs_diag.log`). Test figures: `diag_conv_refl_f2/figures/test_refl_time.png`, `test_refl_height.png`, `test_rank.png`. Not in git (data under `cases/`).
- **Cost**: 76–83 s and 126 MB per selection on a login node (one 213-MB file: 3.6 s, 111 MB).
- **Checks**: `check_obs_diag.py` gives the same counts in every bin (exactly) and the same statistics within 1.4·10⁻⁵ relative (`obs_diag` sums in single precision under `r8 = r4`); the *all* prior statistics at 00:15 equal `obs_space_stats.py`'s. The rank histograms' totals match, and their shapes agree with ranks recomputed from the members, except for specific humidity.
- **DART bug, fixed**: `obs_diag` added noise with the observation-error sd in g/kg to members in kg/kg, so its humidity rank histograms were wrong; `patches/dart_7bbd35a09_obs_diag_rank_hist_units.patch` (README entry there), rebuilt 2026-11-13. Everything else in the output is bit-identical before and after.
- **Sign**: `obs_diag` stores the bias as H(x) − y; this note, like the D1 note, uses the innovation sign y − H(x).

### 1.2 The outlier split

Sec. 5.3 comes from an exploratory script, `/tmp/claude-2001929/-gpfs-wolf2-arm-cli120-proj-shared-hengxiao80-bnf-wrf-da/7fd5183c-4c92-46ba-9155-3a624c8d2b9d/scratchpad/outlier_split.py` (session scratchpad, lost at the next reboot; the method is defined in Sec. 5.3). It reads each cycle's `obs_seq.final` with all 50 prior members. Keeping it would mean adding the split to `scripts/da/refl_innovation_split.py` (not done).

## 2. The reflectivity observations

The obs come from `scripts/da/mrms_to_obs_seq.py` (HRRRDAS settings; `obs_expansion.md` Sec. 8):

- **Precipitation obs** (`RADAR_REFLECTIVITY`): only where the MRMS reflectivity, interpolated to the WRF mass point, is at least 10 dBZ; every third MRMS level up to 11 km, i.e. the 9 heights 0.5, 1.25, 2, 2.75, 4, 5.5, 7, 8.5 and 11 km; every second grid point (5 km). At 06:00 the observed values run from 10.0 to 56.1 dBZ.
- **Clear-air obs** (`RADAR_CLEARAIR_REFLECTIVITY`): where MRMS has coverage but no echo (0 dBZ or less), set to −10 dBZ, at 4 and 8.5 km only, every sixth grid point. Not part of this note.
- **Between 0 and 10 dBZ there are no obs.**
- **Errors**: 5 dBZ (variance 25) for most obs, inflated near the lateral boundary up to 9.3 dBZ (variance 86.2).
- **Forward operator**: H(x) is the member's `REFL_10CM` interpolated to the obs, floored at −10 dBZ (`&obs_def_radar_mod_nml`: `apply_ref_limit_to_fwd_op = .true.`, `reflectivity_limit_fwd_op = -10`). A member with no echo at an obs gives exactly −10 dBZ.

So the statistics below measure the model at observed echoes. A storm the model misses enters them; a storm the model has and MRMS doesn't is seen only by the clear-air obs. The floor makes the bias positive where the model misses echoes.

## 3. What the statistics are

For one cycle, take the $n$ radar obs of the selection (Sec. 1.1), at all 9 heights and the whole domain. For obs $i$: $y_i$ the MRMS value, $\bar h_i$ and $s_i$ the mean and standard deviation over the 50 members of $H(x)$ (DART's sample sd, divided by $N-1$), $\sigma_i$ the assigned error sd. Then

$$
\begin{aligned}
\mathrm{rmse} &= \Big[\tfrac{1}{n}\textstyle\sum_i (\bar h_i - y_i)^2\Big]^{1/2}\\
\mathrm{bias} &= \tfrac{1}{n}\textstyle\sum_i (y_i - \bar h_i)\\
\mathrm{spread} &= \Big[\tfrac{1}{n}\textstyle\sum_i s_i^2\Big]^{1/2}\\
\mathrm{total\ spread} &= \Big[\tfrac{1}{n}\textstyle\sum_i (s_i^2 + \sigma_i^2)\Big]^{1/2}
\end{aligned}
\tag{1}
$$

- **Prior**: the members' 15-min forecasts after prior inflation (filter applies the forward operator to the inflated prior). At 00:15 the forecasts start from the 00:00 cold start. **Posterior**: the members after the analysis (posterior inflation is off).
- **Total spread vs rmse**: against observations the rmse contains the observation error, so for a consistent ensemble (and correctly assigned errors) total spread / rmse ≈ 1 for the prior; spread / rmse < 1 even then.
- **Pooling over heights**: `obs_diag` writes the statistics per height bin; the figures and tables pool the 9 bins weighted by count (mean squares for rmse, spread and total spread, a plain mean for the bias), which gives exactly the statistic over all the cycle's obs.
- **Outliers** (QC 7) are defined in Sec. 5.1; "outlier share" is QC 7 over the obs with a valid prior (QC 0 or 7).

## 4. Results over the 6 h

### 4.1 Time series

Prior, all obs with a valid prior (QC 0 or 7). rmse, bias, spread and total spread in dBZ:

| Time | n | rmse | bias | spread | total | outliers |
|---|---|---|---|---|---|---|
| 00:15 | 76,961 | 16.0 | +8.2 | 2.8 | 5.9 | 31.4 % |
| 00:45 | 80,180 | 17.6 | +9.4 | 5.3 | 7.5 | 30.2 % |
| 01:30 | 81,055 | 15.4 | +7.6 | 6.2 | 8.1 | 19.7 % |
| 02:15 | 80,050 | 13.5 | +5.2 | 6.6 | 8.3 | 11.7 % |
| 03:00 | 79,713 | 11.3 | +3.2 | 6.8 | 8.6 | 6.9 % |
| 04:00 | 87,012 | 10.7 | +3.2 | 6.5 | 8.3 | 6.6 % |
| 05:00 | 94,068 | 11.4 | +4.0 | 5.9 | 7.9 | 8.7 % |
| 06:00 | 94,793 | 10.9 | +2.6 | 6.2 | 8.1 | 6.9 % |

Prior, assimilated obs only (QC 0):

| Time | n | rmse | bias | spread | total |
|---|---|---|---|---|---|
| 00:15 | 52,800 | 9.5 | +3.9 | 3.1 | 6.1 |
| 00:45 | 55,936 | 11.6 | +4.6 | 6.1 | 8.0 |
| 01:30 | 65,061 | 10.4 | +3.2 | 6.8 | 8.6 |
| 02:15 | 70,645 | 9.3 | +2.2 | 6.9 | 8.6 |
| 03:00 | 74,201 | 8.6 | +1.5 | 7.0 | 8.7 |
| 04:00 | 81,241 | 8.2 | +1.5 | 6.7 | 8.5 |
| 05:00 | 85,871 | 7.8 | +1.7 | 6.2 | 8.1 |
| 06:00 | 88,299 | 8.5 | +1.0 | 6.4 | 8.3 |

Posterior. rmse for both selections; spread and bias for QC 0:

| Time | rmse, QC 0 or 7 | rmse, QC 0 | spread, QC 0 | bias, QC 0 |
|---|---|---|---|---|
| 00:15 | 14.6 | 6.9 | 2.0 | +2.7 |
| 00:45 | 14.6 | 5.6 | 3.4 | +2.1 |
| 01:30 | 12.3 | 4.5 | 3.5 | +1.4 |
| 02:15 | 10.4 | 3.6 | 3.3 | +1.0 |
| 03:00 | 7.9 | 3.3 | 3.2 | +0.9 |
| 04:00 | 7.5 | 3.2 | 3.2 | +0.8 |
| 05:00 | 9.1 | 3.3 | 3.2 | +0.7 |
| 06:00 | 7.7 | 3.5 | 3.3 | +0.4 |

Ratios of the prior. Columns: spread / rmse and total spread / rmse, for QC 0 or 7 ("all") and for QC 0:

| Time | s/rmse, all | total/rmse, all | s/rmse, QC 0 | total/rmse, QC 0 |
|---|---|---|---|---|
| 00:15 | 0.17 | 0.37 | 0.33 | 0.64 |
| 00:45 | 0.30 | 0.43 | 0.53 | 0.69 |
| 01:30 | 0.40 | 0.53 | 0.65 | 0.82 |
| 02:15 | 0.49 | 0.62 | 0.74 | 0.92 |
| 03:00 | 0.61 | 0.76 | 0.81 | 1.01 |
| 04:00 | 0.61 | 0.78 | 0.82 | 1.03 |
| 05:00 | 0.52 | 0.69 | 0.79 | 1.04 |
| 06:00 | 0.57 | 0.74 | 0.75 | 0.97 |

Posterior ratios: with QC 0, spread / rmse goes from 0.29 to 0.95–0.99 and total spread / rmse from 0.81 to about 1.8–1.9 (from 03:00 on); with QC 0 or 7, 0.14 → 0.43 and 0.38 → 0.80.

Reading:

- **The prior improves for about 3 h and then holds.** On all obs, rmse and bias fall and the outlier share drops to about 7 % by 03:00; after that they stay level, with a small setback at 04:45–05:00 when the observed echo area grows (radar obs from 87,000 to 96,000 per cycle; Sec. 5.3).
- **Counting the outliers, the prior is still underdispersive** at 06:00 (total spread / rmse 0.74). On the assimilated obs it looks consistent from 03:00 (0.97–1.07), but the QC-0 set leaves out exactly the obs that are far from the ensemble, so this flatters it.
- **The improvement isn't only a consequence of the outlier test**, whose cut-off grows with the spread: the rmse and bias over QC 0 or 7 don't depend on the test, and they fell (17.6 → 10.9 dBZ, +9.4 → +2.6 dBZ). See also Sec. 5.4.
- **The posterior fits the assimilated obs closer than their assigned error** (3.2–3.5 dBZ against 5 dBZ), which is why its total spread / rmse is about 1.8–1.9. The analysis has used these obs, so posterior ratios aren't a consistency test; the fit fits D1's finding that dense radar obs reinforce each other (realized gains 1.6–1.9 times the isolated-observation gain, `fulltest_d1_analysis.md` Sec. 3.5).

### 4.2 By height

Prior, QC 0 or 7, pooled over the 24 cycles (`obs_diag`'s `_VPguess` and `_VPanaly`). n in thousands; outliers as QC 7 over all obs in the bin; rmse, bias and spread in dBZ:

| Height | n (k) | outliers | rmse | bias | spread | rmse post |
|---|---|---|---|---|---|---|
| 0.5 km | 31 | 7.4 % | 12.8 | +2.6 | 6.7 | 8.6 |
| 1.25 km | 133 | 7.6 % | 12.7 | +3.7 | 6.8 | 8.6 |
| 2 km | 184 | 8.9 % | 13.4 | +4.3 | 7.2 | 9.6 |
| 2.75 km | 228 | 10.8 % | 13.7 | +4.5 | 7.6 | 10.2 |
| 4 km | 297 | 14.5 % | 13.9 | +2.6 | 7.2 | 10.7 |
| 5.5 km | 335 | 10.5 % | 11.8 | +2.3 | 5.6 | 9.5 |
| 7 km | 339 | 10.2 % | 11.3 | +3.8 | 5.1 | 9.2 |
| 8.5 km | 311 | 14.1 % | 12.3 | +7.2 | 4.7 | 10.2 |
| 11 km | 186 | 28.9 % | 16.0 | +13.5 | 5.1 | 13.7 |

The upper levels are the problem: from 8.5 km up the bias grows to +7 and +13.5 dBZ, the spread is smallest, and at 11 km 29 % of the obs are outliers. Upper-level echo (anvils, high tops) that the model doesn't produce is the obvious candidate; not examined further.

### 4.3 Rank histograms

Prior rank histograms (`test_rank.png`; each member plus noise with the obs-error sd, as `obs_diag` does), pooled over the 24 cycles and the heights: with QC 0 or 7, 15.9 % of the radar obs rank above every member (8 times the uniform 1/51) and 1.6 % below every member; with QC 0, 4.8 % and 1.1 %. Most of the top-rank excess is the outliers of Sec. 5.

## 5. Outliers

### 5.1 The outlier test

Filter's outlier test (`check_outlier_threshold` in DART's `quality_control_mod.f90`) runs for every obs before it is assimilated. With the prior mean $\bar h$ and variance $s^2$ of $H(x)$ (after prior inflation) and the error variance $\sigma_o^2$,

$$
r = \frac{|\bar h - y|}{\sqrt{s^2 + \sigma_o^2}}
\tag{2}
$$

and the obs gets DART QC 7 and is not assimilated when $r > 3$ (`outlier_threshold = 3.0` in `&quality_control_nml`, the same for all types; `enable_special_outlier_code = .false.`). In words: an obs is rejected when its innovation exceeds 3 times its own total spread. Checked on the 00:15 and 06:00 files: QC 7 is exactly the set of radar obs with $r > 3$.

### 5.2 Where no member has an echo

If all 50 members have no echo at an obs, every member gives −10 dBZ, so $\bar h = -10$ and $s = 0$, and $r = (y + 10)/\sigma_o$. With $\sigma_o = 5$ dBZ, $r \ge 4$ for every obs (all have $y \ge 10$): **all such obs are rejected**, except near the lateral boundary, where the inflated error (up to 9.3 dBZ) lets obs up to 17.9 dBZ pass.

Even an obs that passed would change nothing: in DART's EAKF (`obs_increment_eakf`) the weight on the obs is $s^2/(s^2 + \sigma_o^2)$, zero when $s = 0$, so every member's increment is zero. Inflation can't help either, since there is no spread to inflate. These obs can only be "reached" through nearby obs that pass the test or through the model developing the storm itself.

### 5.3 Split by member echo

Each cycle's radar obs with QC 0 or 7 were split by how many of the 50 prior members have an echo at the obs (H(x) above −10 dBZ): **none**, **some** (1–49) or **all**. Counts per cycle:

| Time | radar obs | QC 7 | none | some | all |
|---|---|---|---|---|---|
| 00:15 | 76,961 | 24,161 | 8,830 | 6,219 | 9,112 |
| 00:45 | 80,180 | 24,244 | 10,149 | 8,757 | 5,338 |
| 01:30 | 81,055 | 15,994 | 8,392 | 6,255 | 1,347 |
| 02:15 | 80,050 | 9,405 | 5,005 | 3,755 | 645 |
| 02:45 | 78,679 | 6,100 | 3,032 | 2,675 | 393 |
| 03:00 | 79,713 | 5,512 | 3,172 | 2,015 | 325 |
| 04:00 | 87,012 | 5,771 | 3,017 | 2,579 | 175 |
| 04:45 | 92,833 | 7,273 | 4,623 | 2,478 | 172 |
| 05:00 | 94,068 | 8,197 | 4,986 | 3,068 | 143 |
| 06:00 | 94,793 | 6,494 | 3,359 | 2,790 | 345 |

As shares of the outliers, at 00:15 and per cycle from 03:00 on: none 37 % → 52–64 %, some 26 % → 34–45 %, all 38 % → 2–6 %. As shares of all radar obs, the "none" outliers are 11.5–12.7 % at 00:15–01:00 and 3.5–5.3 % after 02:45.

Medians (and 90th percentile of the obs value), in dBZ; $r$ from Eq. 2. Early, 00:15–01:00:

| Group | y | y p90 | prior mean | spread | r |
|---|---|---|---|---|---|
| QC 0 | 18.7 | 32.4 | 15.4 | 3.3 | 1.18 |
| QC 7, none | 13.3 | 23.1 | −10.0 | 0.0 | 4.50 |
| QC 7, some | 14.4 | 30.5 | −9.0 | 2.2 | 4.11 |
| QC 7, all | 22.9 | 42.3 | 16.0 | 2.4 | 3.81 |

Late, 03:00–06:00:

| Group | y | y p90 | prior mean | spread | r |
|---|---|---|---|---|---|
| QC 0 | 19.2 | 34.9 | 20.2 | 4.1 | 0.61 |
| QC 7, none | 15.0 | 29.3 | −10.0 | 0.0 | 4.80 |
| QC 7, some | 14.2 | 30.8 | −9.3 | 2.8 | 3.98 |
| QC 7, all | 29.8 | 47.8 | 17.6 | 3.8 | 3.40 |

Further:

- **"Some"**: a median of 12 members (early) and 4 (late) have an echo; the obs is above the ensemble mean in every case.
- **"Some" and "all" together**, per cycle: the obs is above the mean for 76–99 %, above every member for 74–90 %, and 48–58 % have $r$ between 3 and 4, i.e. only just over the threshold.
- **"All"**: the obs is above the mean for 61 % (early) and 71 % (late); the rest is the model being too strong. Early that is 10,012 obs with a model mean of 50 dBZ against an observed 21 dBZ (medians, median height 4 km), most likely storms carried over from the cold start; late only 937.
- **Heights**: 30–37 % of the "none" outliers are at or below 4 km, against 42–45 % of the assimilated obs, so the no-echo outliers lean to the upper levels (cf. Sec. 4.2).

### 5.4 Reading

The user asked whether the outliers other than the no-echo ones are simply strong echoes cut off by the threshold of 3. Mostly not. The "some members" outliers are weak echoes (median 14 dBZ, weaker than the assimilated obs) at places where most members have nothing; they fail because the ensemble has almost no spread there (about 2–3 dBZ around a mean near −9 dBZ, so a cut-off of about 3 × √(2.5² + 5²) ≈ 17 dBZ of innovation, while a 14-dBZ obs is about 23 dBZ away). Only the "all members" group has strong obs, and it is small after 03:00.

The drop in the no-echo outliers is a good sign that isn't produced by the test or by inflation, neither of which can act where all members are at the floor (Sec. 5.2): the ensemble now has echoes in many more of the places where MRMS has them. The caveats: the count stops falling after about 02:45 at about 3,000 per cycle, and it rises when the observed echo area grows (04:30–05:00), most likely with new cells the ensemble doesn't have yet. Such obs can't start those cells themselves; a residual of this kind should be expected whenever new convection forms in the 12-h and 30-h runs. Options: `refl_spinup_options.md`.

## 6. Open points

1. Spin-up options: `refl_spinup_options.md` (nothing decided).
2. The outlier split (Sec. 5.3) lives in the session scratchpad; to keep it, add it to `scripts/da/refl_innovation_split.py` and make a per-cycle figure of the three groups.
3. Only test figures exist (`diag_conv_refl_f2/figures/test_*.png`); the full set (conventional time series, ACARS profiles, clear air, a time–height view of the radar statistics) waits for the user.
4. Upper levels (Sec. 4.2): why 8.5 and 11 km have the largest bias and outlier share.
5. ACARS specific humidity: in its rank histogram 5.7 % (QC 0 or 7) and 3.5 % (QC 0) of the obs rank below every member (`test_rank.png`, 1/51 = 2 % if uniform); not looked at.
6. Clear-air obs: not analysed here; in D1 their misfit grew each cycle (`fulltest_d1_analysis.md` Sec. 4).
