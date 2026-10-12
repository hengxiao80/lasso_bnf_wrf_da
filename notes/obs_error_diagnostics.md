# Observation-error diagnostics from `obs_seq.final`: the implied error and Desroziers' estimate

Written 2026-10-12. Explains the two estimates `scripts/da/innovation_stats.py` reports, used in `obs_expansion.md` §5 to compare our assigned errors with what the pilot's innovations support. References: Desroziers, Berre, Chapnik and Poli (2005, *QJRMS* 131, 3385–3396); for the innovation-variance identity, any DA text (e.g. Daley 1991).

## 1. Notation

For one observation i of a given type:

| Symbol | Meaning | Where it comes from in `obs_seq.final` |
|---|---|---|
| y | observed value | the observation copy (e.g. "NCEP BUFR observation" / "MADIS observation") |
| H(x_b) | the observation as the prior (15-min forecast) sees it: the forward operator applied to each member, averaged over members | "prior ensemble mean" |
| s_b | prior ensemble spread in observation space: sd of H(x_b,j) over members j | "prior ensemble spread" |
| H(x_a) | same, for the analysis | "posterior ensemble mean" |
| σ_o | assigned observation-error sd | square root of the error variance stored with the observation |
| d_b = y − H(x_b) | innovation (observation minus prior) | computed |
| d_a = y − H(x_a) | analysis residual (observation minus analysis) | computed |

In our setup, s_b is the spread **after** prior inflation (DART inflates the prior, `filter_mod.f90:829`, before computing the prior forward operators, `:853`). σ_o includes the boundary inflation of `wrf_dart_obs_preprocess` (up to ×2.07 in sd at the innermost kept row).

The truth in observation space is H(x_t). Write the two errors as
- ε_b = H(x_b) − H(x_t): prior (background) error, with variance σ_b² (the true one, unknown);
- ε_o = y − H(x_t): observation error, with variance σ_o,true². It includes both instrument error and representativeness error (what the model grid and the forward operator cannot represent), plus any forward-operator error.

So d_b = ε_o − ε_b.

"mean" below is the average over all observations of one type in the sample (`innovation_stats.py` pools all cycles of a run).

## 2. The innovation-variance identity

Square d_b and average:

  mean(d_b²) = mean(ε_o²) + mean(ε_b²) − 2 mean(ε_o ε_b).

Assume:
- **(A1) Unbiased errors.** mean(ε_o) = mean(ε_b) = 0. Otherwise the squared biases also enter mean(d_b²).
- **(A2) Observation and prior errors uncorrelated.** mean(ε_o ε_b) = 0. Reasonable: the prior was not made from this observation. It fails if the same observation was already assimilated (e.g. a report used twice), or if both errors share a cause (e.g. a station whose siting matches a model terrain error).

Then

  **mean(d_b²) = σ_b² + σ_o,true².**   (1)

The innovations are the only thing measured against reality. Equation (1) says their variance must be split between prior error and observation error; the data alone don't say how. Every estimate below is a way of deciding that split.

## 3. The implied observation error

Take the ensemble spread as the prior error:

- **(A3) The spread is right.** σ_b² = mean(s_b²).

Then (1) gives

  **σ_o,implied = sqrt( mean(d_b²) − mean(s_b²) )**,   (2)

and `innovation_stats.py` reports it divided by the rms assigned error, sqrt(mean σ_o²).

Two related numbers in the same table:
- the **consistency ratio** mean(d_b²) / mean(s_b² + σ_o²): 1 if the assigned errors and the spread together account for the innovations, < 1 if they allow more variance than is seen (errors or spread too large), > 1 if less;
- the **rms innovation** sqrt(mean d_b²) and the **bias** mean(d_b), to check (A1).

**How (A3) fails, and in which direction.** With few members the ensemble is usually underdispersive: σ_b > s_b. Then (2) assigns to the observation error what really belongs to the prior error, so σ_o,implied > σ_o,true. **The implied error is an upper bound when the spread is too small.** A prior bias also inflates mean(d_b²) and therefore σ_o,implied.

## 4. Desroziers' estimate

### 4.1 Scalar derivation (one observation, or observations far apart)

The analysis moves the prior toward the observation by the gain

  k = σ_b,used² / (σ_b,used² + σ_o,used²),

where "used" are the variances the filter assumed (in DART: σ_b,used² = s_b², the inflated spread; σ_o,used² = the assigned error variance). Then

  H(x_a) = H(x_b) + k d_b,   so   d_a = y − H(x_a) = (1 − k) d_b = σ_o,used² / (σ_b,used² + σ_o,used²) · d_b.

Multiply by d_b and average:

  mean(d_a d_b) = σ_o,used² / (σ_b,used² + σ_o,used²) · mean(d_b²).   (3)

If the assumed variances are the true ones, the innovation variance in (3) is mean(d_b²) = σ_b,used² + σ_o,used² by (1), which cancels the denominator:

  **mean(d_a d_b) = σ_o²**   (when the filter's error assumptions are correct).   (4)

So `innovation_stats.py` reports **σ_o,D = sqrt( mean(d_a d_b) )** over assimilated observations (DART QC 0; rejected ones have no analysis influence).

Intuition: the analysis leaves behind the part of each innovation it attributes to observation error. Correlating that residual with the innovation and averaging gives the observation-error variance.

### 4.2 General (matrix) form

With B, R the prior and observation error covariances in observation space (B here meaning H B Hᵀ), the analysis is H x_a = H x_b + HK d_b with HK = B (B + R)⁻¹, so

  d_a = (I − HK) d_b = R (B + R)⁻¹ d_b,
  E[d_a d_bᵀ] = R (B + R)⁻¹ E[d_b d_bᵀ].

With correct statistics, E[d_b d_bᵀ] = B + R, so **E[d_a d_bᵀ] = R**, Desroziers' result. Its diagonal is what we estimate per observation type. Off-diagonal terms between observations would estimate observation-error correlations (not computed by us).

Two companion identities from the same paper, with the same caveat:
- E[(H x_a − H x_b) d_bᵀ] = B (prior error in observation space; a check on the spread, i.e. on assumption A3);
- E[(H x_a − H x_b) d_aᵀ] = H A Hᵀ (analysis error in observation space).

In our filter the analysis is a serial EAKF with localization, sampling-error correction and many observations, so HK is not exactly B(B + R)⁻¹ with one fixed B. The identity still holds approximately, as long as the analysis is close to the optimal linear update for the assumed covariances.

### 4.3 When the assumed errors are wrong: bias toward the assigned value, and iteration

If σ_o,used differs from the truth, (3) still holds but (4) doesn't. Desroziers' estimate is then pulled toward what was assigned. Example, METAR T2 in the 1-hour pilot (`output_hph`): s_b = 0.62 K, σ_o,used = 2.7 K, rms d_b = 1.20 K.

  factor = 2.7² / (0.62² + 2.7²) = 0.95,  σ_o,D = sqrt(0.95 × 1.44) = 1.17 K   (the script gives 1.16 K).

Because the assigned error was far too large, the analysis barely moved (d_a ≈ d_b), and the estimate came out close to the innovation variance itself, i.e. too high.

The remedy (Desroziers et al. 2005, Sec. 3) is to iterate: assign the estimate, run the analysis again, re-estimate. In the scalar case, with σ_b,used fixed:

  σ_o,n+1² = σ_o,n² / (s_b² + σ_o,n²) · mean(d_b²).

- Second pass with σ_o = 1.17 K: factor = 1.37 / (0.38 + 1.37) = 0.78, σ_o = sqrt(0.78 × 1.44) = 1.06 K.
- Fixed point: σ_o² = σ_o² · mean(d_b²) / (s_b² + σ_o²), i.e. s_b² + σ_o² = mean(d_b²), so σ_o = sqrt(1.44 − 0.38) = **1.03 K**, the implied error of Sec. 3.

The iteration converges quickly when the first guess is not wildly off. In practice one or two passes.

## 5. How the two estimates relate

- **Same information, different route.** Both split mean(d_b²) between prior and observation error using the ensemble's spread: the implied error explicitly (A3); Desroziers through the gain, which DART computes from the same inflated spread. In the scalar case, **converged Desroziers equals the implied error.** They are not independent checks of each other.
- **One-pass Desroziers vs implied.** One pass lies between the assigned error and the implied one (exactly so in the scalar case), so starting from errors that are too large gives a one-pass estimate that is somewhat too large. Pilot METAR ratios to the assigned error: implied 0.29–0.48, one-pass Desroziers 0.32–0.47.
- **Both inherit the spread's errors.** If the 5-member spread underestimates the true prior error, both overestimate the observation error. For METAR in the pilot the true errors are therefore probably at or below the estimates (~1 K, ~6 % RH, ~1.5 m/s).
- **What breaks the scalar picture in the EAKF.** Localization, nearby observations of other types updating the same prior, inflation, and sampling error all change the effective gain, so the two estimates differ somewhat in practice. Example from the pilot: ACARS T has implied 0.84 but one-pass Desroziers 0.69, below the implied value, which the scalar picture doesn't allow (there, one pass lies between the implied and the assigned error). Likely cause: thousands of nearby aircraft reports, each pulling the analysis toward the others, so the effective gain for any one report is larger than k. The companion identity E[(H x_a − H x_b) d_b] ≈ B (Sec. 4.2) is the most useful independent check, because it tests the spread directly.

## 6. Assumptions and caveats, all in one place

| Assumption | If it fails | In our data |
|---|---|---|
| (A1) unbiased errors | biases add to mean(d_b²); both estimates go up | `innovation_stats.py` prints mean(d_b); small in the pilot (T2 −0.01 K, V10 −0.5 m/s) |
| (A2) observation and prior errors uncorrelated | cross term ignored | fine unless a report is reused or shares a cause with a model error |
| (A3) spread = prior error (implied); gain built from correct B and R (Desroziers) | estimates too large if the spread is too small; Desroziers pulled toward the assigned error | 5 members, spread ≪ innovations aloft (ACARS wind 0.9 vs 3.1 m/s): upper bounds |
| Observations independent of each other | spatially correlated errors (dense surface networks) don't change the diagonal estimate, but the filter treats correlated observations as independent and overweights them | matters for mesonet; thinning or error inflation then, not a change in these formulas |
| Enough samples, homogeneous sample | statistics mix levels, regimes and times of day | pilot: 1 hour, pooled over levels; bin by pressure and time of day in the extension |
| QC selection | only QC 0 for Desroziers, QC 0 + 7 for the implied error (rejected outliers still have a prior) | excluding outliers would bias mean(d_b²) low |

## 7. In `scripts/da/innovation_stats.py`

- Implied: `sqrt(max(mean(d**2) - mean(spread**2), 0))`, over obs with DART QC 0 or 7; ratio to `sqrt(mean(err_var))`.
- Consistency ratio: `mean(d**2) / mean(spread**2 + err_var)`, same selection.
- Desroziers: `sqrt(mean((y - post_mean) * (y - prior_mean)))`, over QC 0; ratio to `sqrt(mean(err_var))` of those obs.
- Ratios are to the rms assigned error **including** boundary inflation, so they convert to the base (unboosted) error approximately as ratio × base error.
- Not yet computed: the companion estimate of B, binning by pressure and time of day.
