# WRF–DART tutorial: summary of a discussion with Codex

Summary written by Codex, revised 24 September 2026 by Heng Xiao. Converted for Typora on 2026-10-25 from `codex.WRF_DART_Discussion_and_Branches_Summary_v1.md`: math in LaTeX with numbered equations, a notation table, the widest table turned into a list, light edits for readability. The content is Codex's; a check against the pinned DART code is in `codex_wrf_dart_summary_check.md`.

**Scope.** The WRF–DART tutorial discussion in one Codex chat, plus two branches the user asked for: (1) the control flow of the Step 4 scripts, and (2) how the EAKF builds its analysis ensemble, compared with the EnKF, EnSRF, ETKF and LETKF. It replaces an earlier summary that mixed in other project conversations by mistake. It is a technical summary, not a transcript; some branch material came from retrieved summaries.

## Notation

| Symbol | Meaning |
|---|---|
| $n$, $N$, $p$ | state size, ensemble size, number of observations |
| $x_i^f$, $x_i^a$ | prior (forecast) and posterior (analysis) state of member $i$ |
| $x_{j,i}$ | state element $j$ of member $i$ |
| $\bar x$ | ensemble mean (an overbar is always the ensemble mean) |
| $\mathcal H$ | forward operator |
| $y_i^f$ | predicted observation of member $i$, $\mathcal H(x_i^f)$ |
| $y_o$ | observed value |
| $R=\sigma_o^2$ | observation-error variance |
| $d=y_o-\bar y^f$ | innovation |
| $s^2$ | prior variance of the predicted observation |
| $\lambda$ | multiplicative inflation |
| $\gamma$ | inflation damping (`inf_damping`) |
| $\rho_{jo}$ | localization weight between element $j$ and observation $o$¹ |

¹ In Eq. (2) only, $\rho$ is air density.

## 1. Step 4: which script runs WRF

**Question.** The perturbed initial conditions are made and advanced by `first_advance.sh`, yet `new_advance_model.sh` also seems to run. Is the model integrated twice?

**Answer.** No. The call order is:

```
init_ensemble_var.sh
  v
member job (one per member, submitted to the scheduler)
  v
first_advance.sh
  v
new_advance_model.sh
  v
wrf.exe
```

| Script or program | Role in the tutorial |
|---|---|
| `init_ensemble_var.sh` | Loops over the members and submits a scheduler job for each |
| `add_bank_perts.ncl` | Adds perturbation-bank fields to build each member's initial conditions |
| `ndown.exe` | Optional: prepares a nested domain in the member job |
| `first_advance.sh` | Writes the control information (`wrf.info`, `filter_control`), calls the advance engine, and organizes the resulting priors |
| `new_advance_model.sh` | Does the model advance: prepares the run and calls `wrf.exe` |
| `wrf.exe` | Integrates the model |

So `first_advance.sh` and `new_advance_model.sh` are two cooperating layers of one advance, and calling both does not mean two spin-up integrations. (An earlier answer in the chat had `first_advance.sh` run WRF and put `new_advance_model.sh` above it; the branch corrected that.)

Missing `filter_restart_*` files are expected at initialization: there is no earlier DART posterior to insert, so the advance uses the prepared perturbed `wrfinput` states. Later cycles advance the analyzed ensemble.

These statements describe the tutorial scripts of that DART version. File names and control conventions differ between WRF–DART workflows.

## 2. Steps 5–6: observations, types, quantities and forward operators

For the conventional-observation example the processing path is

```
PREPBUFR -> prepbufr.x (run by prepbufr.csh) -> intermediate ASCII
         -> create_real_obs -> obs_seq.out
```

`&prep_bufr_nml` controls the PREPBUFR stage, and `&ncepobs_nml` controls conversion and selection in `create_real_obs`. The observation sequence carries, for each observation, its value, location, time, type, error variance and QC metadata. It contains no model ensemble and no precomputed gain.

A radiosonde example is `RADIOSONDE_TEMPERATURE` → `QTY_TEMPERATURE` → WRF `model_interpolate`.

- The **type** distinguishes the observing category.
- The **quantity** names the physical field requested from the model interface.
- `&obs_kind_nml` selects the types to assimilate or evaluate.
- `preprocess` generates the compiled observation-definition and type code.

For member $i$ the forward operator computes

$$
y_i^f=\mathcal H(x_i^f).
\tag{1}
$$

For temperature this means a thermodynamic conversion and interpolation. Radar reflectivity instead needs a microphysics-dependent operator, schematically

$$
Z=\mathcal H(q_r,q_s,q_g,\rho,T,\ldots).
\tag{2}
$$

The radar module `obs_def_radar_mod` requests these atmospheric quantities from the model interface. The contrast shows why the reflectivity operator and the model quantities it needs have to be identified explicitly.

For one radiosonde temperature, `obs_seq.out` supplies the observed value $y_o$ and the error variance $R=\sigma_o^2$, while `filter` computes the ensemble of predicted temperatures. The assimilation combines

$$
y_o,\qquad R,\qquad \{\mathcal H(x_i)\}_{i=1}^{N}.
\tag{3}
$$

The observation type does not restrict the increments to temperature. Winds, moisture and other state variables also change through their ensemble covariance with the predicted temperature, subject to localization and any configured update restrictions.

## 3. `preprocess`, thinning and superobbing

**DART's `preprocess` is a build-time source generator.** It assembles the observation definitions and the type and quantity code. It does not read an observation sequence, thin it, or average radar observations.

`wrf_dart_obs_preprocess` is a separate run-time utility. The discussion identified its domain, boundary and elevation selection and its superobbing of aircraft and satellite-wind observations. It is not a general radar superobbing tool.

For BNF, the MRMS sampling belongs in the converter or in a radar-specific processing stage before `filter`.

| Method | Meaning |
|---|---|
| Thinning | Keep selected actual observations and discard the rest by a reproducible rule |
| Superobbing | Combine several observations into representative ones, with their own locations, times and errors |

Keeping selected radar samples is not the same as building averaged observations, and the aircraft and satellite-wind superobbing of the WRF utility does not do the intended MRMS sampling.

## 4. Step 7: inflation — initialization, application and adaptation

### 4.1 Multiplicative inflation

With ensemble mean $\bar x$ and anomalies $x_i-\bar x$,

$$
\widetilde x_i=\bar x+\sqrt\lambda\,(x_i-\bar x).
\tag{4}
$$

A uniform $\lambda$ multiplies the covariance by $\lambda$ and keeps the mean. If $\lambda_j$ varies with the state element, then with $D=\operatorname{diag}(\sqrt{\lambda_j})$ the covariance becomes $DPD$, not one scalar times $P$.

### 4.2 Step 7 only initializes the inflation fields

The tutorial runs `fill_inflation_restart` with prior inflation mean 1.0 and sd 0.6, and writes no posterior inflation files. The WRF input files supply the state's shape. This is initialization, not an estimate from observations.

The files are `input_priorinf_mean_d01.nc`, the inflation estimate, and `input_priorinf_sd_d01.nc`, the uncertainty of that estimate (**not the atmospheric ensemble spread**). The tutorial also shows files for a second domain.

### 4.3 Adaptive estimation

A scalar illustration: with innovation $d=y_o-\bar y^f$, uninflated predicted-observation variance $s^2$ and error variance $R$,

$$
\begin{aligned}
p(d\mid\lambda)&\propto(\lambda s^2+R)^{-1/2}\exp\left[-\frac{d^2}{2(\lambda s^2+R)}\right],\\
p(\lambda\mid d)&\propto p(\lambda)\,p(d\mid\lambda).
\end{aligned}
\tag{5}
$$

This shows why innovations carry information about the inflation. It is **not DART's full formula** for spatially varying adaptive inflation: localized influence, correlations, finite ensembles and the treatment of inflation already applied all matter. In particular, do not put an already inflated variance into Eq. (5) and multiply it by the same inflation again.

Flavor 2 uses a Gaussian prior for $\lambda$, flavor 5 an inverse-gamma prior, and the two should not be conflated. The discussion used flavor 2 to explain the tutorial and left the tutorial's exact flavor and bounds to be checked.

For prior inflation the documented order is: read → damp → inflate the prior → assimilate and update the inflation estimate → write the estimate for the next cycle. The damping discussed was

$$
\lambda_d=\left[1+\gamma(\sqrt\lambda-1)\right]^2,
\tag{6}
$$

which gives 1.3924 for $\lambda=1.44$ and $\gamma=0.9$. The updated prior inflation carries information forward; it does not go back and re-inflate this cycle's prior with the cycle's final estimate. See the [DART inflation guide](https://docs.dart.ucar.edu/en/latest/guide/inflation.html).

### 4.4 Controls and code map

| Control | Role |
|---|---|
| `inf_flavor` | Inflation algorithm; first entry prior, second posterior |
| `inf_initial_from_restart` | Read the inflation estimate from a restart file |
| `inf_sd_initial_from_restart` | Read its uncertainty from a restart file |
| `inf_initial`, `inf_sd_initial` | Initial values when not read from files |
| `inf_lower_bound`, `inf_upper_bound` | Bounds on the estimate |
| `inf_sd_lower_bound`, `inf_sd_max_change` | Controls on how the uncertainty evolves |
| `inf_damping` | Relaxation toward 1 |
| `inf_deterministic` | Deterministic or stochastic application of the inflation |

The code map is `fill_inflation_restart`, `filter`/`filter_mod`, `assim_tools_mod` and `adaptive_inflate_mod`. The exact update routines and their arguments were left as a source-tracing task. Take the stage-dependent output file names from the pinned version rather than assuming they always start with `output_`.

If every member has $q_r=0$, its variance stays zero under multiplicative inflation. More generally, zero variance in the predicted reflectivity keeps a covariance regression from supplying the missing storm information. Environmental spread, spin-up, operator floors and any additional perturbation strategy therefore need to be diagnosed separately.

## 5. Where localization happens

Localization happens inside `filter`, during the covariance-based updates of the state and of the observation equivalents. It is not part of the physical forward operator, and it is not the same operation as observation thinning.

For the EAKF, its core role is

$$
\Delta x_{j,i}=\rho_{jo}\,\frac{\operatorname{cov}(x_j,y)}{s^2}\,\Delta y_i.
\tag{7}
$$

The code discussed: `assim_tools_mod`, the model and location `get_close` routines, the three-dimensional spherical `location_mod`, and `cov_cutoff_mod`. The nearby-observation searches also serve the serial update of observation equivalents, so their role is broader than adaptive localization or inflation.

For Gaspari–Cohn, DART's `cutoff` is the half-width, and the weight reaches zero at twice that distance. Horizontal distance is angular; vertical distance needs a compatible coordinate and a normalization. `horiz_dist_only = .true.` removes the vertical separation from the distance. See the [DART assimilation and localization documentation](https://docs.dart.ucar.edu/en/latest/assimilation_code/modules/assimilation/assim_tools_mod.html).

The chat's example was an 18-km horizontal zero-influence distance, which is a 9-km half-width. Vertical localization also needs consistent vertical coordinates and a suitable normalization: a radiosonde's pressure location and a WRF model-level location must be made compatible before a three-dimensional distance means anything.

Adaptive inflation also depends on the local influence of an observation, but the chat's "inflation increment proportional to a localization taper" was a concept, not a verified update equation.

## 6. EAKF comparison branch: basic EnKF mathematics

This section collects the EAKF comparison branch and states the matrix dimensions.

Let $n$ be the state dimension, $N$ the ensemble size and $p$ the number of observations, and let $\mathbf 1$ be the vector of $N$ ones. With unnormalized anomaly matrices,

$$
\begin{aligned}
X^f&=[x_1^f,\ldots,x_N^f]\in\mathbb R^{n\times N},\\
A^f&=X^f-\bar x^f\mathbf 1^T,\\
Y^f&=[\mathcal H(x_1^f),\ldots,\mathcal H(x_N^f)]\in\mathbb R^{p\times N},\\
D^f&=Y^f-\bar y^f\mathbf 1^T.
\end{aligned}
\tag{8}
$$

Then

$$
P_{xy}=\frac{A^f(D^f)^T}{N-1},\qquad
P_{yy}=\frac{D^f(D^f)^T}{N-1},
\tag{9}
$$

$$
K=P_{xy}(P_{yy}+R)^{-1},\qquad
\bar x^a=\bar x^f+K(y_o-\bar y^f).
\tag{10}
$$

An ensemble filter computes these covariances from the members' predictions; it does **not need a tangent-linear observation Jacobian**. For nonlinear operators, in general $\overline{\mathcal H(x)}\ne\mathcal H(\bar x)$.

For the unlocalized linear Kalman problem the target covariance is

$$
P^a=P^f-P_{xy}(P_{yy}+R)^{-1}P_{yx}.
\tag{11}
$$

Building $X^a$ means finding both the updated mean and an anomaly matrix with the desired covariance. Many square roots give that covariance, so equal means and covariances do not in general mean equal members.

In the perturbed-observation EnKF,

$$
x_i^a=x_i^f+K\left[y_o+\epsilon_i-\mathcal H(x_i^f)\right],\qquad
\epsilon_i\sim\mathcal N(0,R).
\tag{12}
$$

The EAKF, EnSRF and ETKF avoid this sampling noise from the perturbed observations by adjusting the anomalies deterministically.

## 7. How the EAKF builds the analysis ensemble

For one scalar observation, define

$$
\begin{aligned}
y_i^f&=\mathcal H_o(x_i^f),\\
s^2&=\frac{1}{N-1}\sum_i\left(y_i^f-\bar y^f\right)^2,\\
d&=y_o-\bar y^f.
\end{aligned}
\tag{13}
$$

The scalar posterior mean and variance are

$$
\bar y^a=\bar y^f+\frac{s^2}{s^2+R}\,d,\qquad
s_a^2=\frac{Rs^2}{s^2+R}.
\tag{14}
$$

Set

$$
\alpha=\sqrt{\frac{R}{s^2+R}},\qquad
y_i^a=\bar y^a+\alpha\left(y_i^f-\bar y^f\right).
\tag{15}
$$

The member increments are then

$$
\Delta y_i=\frac{s^2}{s^2+R}\,d+(\alpha-1)\left(y_i^f-\bar y^f\right).
\tag{16}
$$

This is a mean shift plus a contraction of the spread, not simply the member's innovation $y_o-y_i^f$.

For a state element $j$,

$$
\begin{aligned}
c_j&=\frac{1}{N-1}\sum_i\left(x_{j,i}^f-\bar x_j^f\right)\left(y_i^f-\bar y^f\right),\\
x_{j,i}^a&=x_{j,i}^f+\rho_{jo}\,\frac{c_j}{s^2}\,\Delta y_i.
\end{aligned}
\tag{17}
$$

The division assumes $s^2>0$; zero variance needs explicit handling.

### What is computed once, and what varies with the state element

- The observation's mean and variance, the scalar posterior adjustment and the vector of member increments $\Delta y_i$ are computed **once** per scalar observation.
- Each nearby state element has its **own** $c_j=\operatorname{cov}(x_j,y)$ and its own localization weight.
- The cross-covariances can be computed together as one matrix–vector operation, but they are not one covariance shared by all state variables.
- The algorithm never builds or inverts the full $n\times n$ state covariance.

This resolves an ambiguous statement in the branch that the covariance was "not independently recalculated per state element": what is shared is the observation variance and the scalar adjustment, while the state–observation cross-covariance changes with $j$.

In DART's serial processing, the nearby observation equivalents not yet assimilated are also updated by regression. They are not recomputed with the nonlinear forward operator after each scalar observation. So the predicted-observation ensemble that a later observation sees is not the same as a fresh evaluation of $\mathcal H$ on the current state.

### Numerical example from the chat

For predicted observations $[6,8,10,12,14]$, the ensemble mean is 10 and the sample variance is $s^2=10$. With observation $y_o=10$ and error variance $R=2$,

$$
\bar y^a=10,\qquad
s_a^2=\frac{20}{12}\approx1.667,\qquad
\alpha=\sqrt{\frac{2}{12}}\approx0.408.
\tag{18}
$$

The adjusted members and their increments are approximately:

| $i$ | $y_i^f$ | $y_i^a$ | $\Delta y_i$ |
|---|---|---|---|
| 1 | 6 | 8.37 | +2.37 |
| 2 | 8 | 9.18 | +1.18 |
| 3 | 10 | 10.00 | 0 |
| 4 | 12 | 10.82 | −1.18 |
| 5 | 14 | 11.63 | −2.37 |

The mean stays put, because the observation equals the prior mean, but the spread shrinks. If the observation were 12, the ensemble would both shift toward 12 and contract. These member increments in observation space are then regressed onto each affected state element, Eq. (17).

## 8. EAKF versus EnSRF, ETKF and LETKF

### 8.1 Scalar EnSRF: identical to the EAKF construction above

For one observation, let $c=P_{xy}$ (a column of length $n$), $K=c/(s^2+R)$, and let $a_y$ be the row vector of predicted-observation anomalies. The EnSRF uses

$$
\begin{aligned}
\bar x^a&=\bar x^f+Kd,\\
A^a&=A^f-\widetilde K a_y,\\
\widetilde K&=\frac{K}{1+\alpha}.
\end{aligned}
\tag{19}
$$

The EAKF's anomaly update is

$$
A^a=A^f+\frac{c}{s^2}(\alpha-1)\,a_y.
\tag{20}
$$

Since

$$
\frac{1-\alpha}{s^2}=\frac{1}{(s^2+R)(1+\alpha)},
\tag{21}
$$

the two scalar updates are **algebraically identical**, member increments included, when they use the same ensemble, the same scalar observation statistics and the same localization. This is stronger than equal posterior means and covariances.

An earlier, broad statement in the chat that the EAKF and EnSRF necessarily use different member transforms was too strong for this serial scalar construction. Differences can come from other choices: localization implementation, inflation, observation handling or ordering. Nonlinearity alone does not undo the identity if both methods get the same predicted-observation ensemble and apply the same update.

### 8.2 ETKF: a simultaneous square root in ensemble space

With the unnormalized anomalies of Eq. (8),

$$
C=(N-1)I+(D^f)^TR^{-1}D^f\in\mathbb R^{N\times N},
\tag{22}
$$

$$
\begin{aligned}
\bar w&=C^{-1}(D^f)^TR^{-1}(y_o-\bar y^f),\\
\bar x^a&=\bar x^f+A^f\bar w,
\end{aligned}
\tag{23}
$$

$$
\begin{aligned}
T&=\left[(N-1)C^{-1}\right]^{1/2},\\
A^a&=A^fT,\\
X^a&=\bar x^a\mathbf 1^T+A^a.
\end{aligned}
\tag{24}
$$

The usual symmetric square root keeps the ensemble mean of the anomalies at zero. The main decomposition is in ensemble space, not state space. Real implementations use matrix solves and factorizations rather than forming inverses explicitly.

A global ETKF and an unlocalized serial square-root filter can agree on the linear Kalman posterior mean and covariance and still differ member by member, because they pick different square roots. The scalar EAKF–EnSRF identity does not extend to a claim that all deterministic ensemble filters give the same members.

### 8.3 LETKF: a different local transform at each analysis location

The LETKF applies the ensemble-space construction to a local subset, or local weighting, of the observations around each analysis location. It gets local weights $\bar w_\ell$ and a local transform $T_\ell$, and applies them to the state rows of that location or local region.

Localization usually works by selecting observations and reducing their precision with distance, for example $R_{oo}^{-1}\mapsto\rho_{\ell o}R_{oo}^{-1}$ for diagonal errors. This is in general not the same as tapering each serial regression increment. In general no single global transform $T$ reproduces every local LETKF update.

| Method | How the analysis ensemble is built | Typical organization |
|---|---|---|
| Stochastic EnKF | Gain update with perturbed observations | Ensemble covariances plus random observation perturbations |
| Serial EAKF | Scalar deterministic adjustment, then regression | Observations one at a time; state updates in parallel |
| Serial EnSRF | Mean gain plus reduced anomaly gain | Same as the EAKF under matched choices |
| ETKF | Mean weights and square root in ensemble space | All observations at once, one global transform |
| LETKF | Local weights and square roots in ensemble space | Many local analyses that can run independently |

For one scalar EAKF update, the covariance and regression work scales roughly as $N$ times the number of affected state elements, plus the updates of affected observation equivalents and the communication. The LETKF repeatedly forms and factorizes ensemble-sized local systems. Neither "serial" nor "an $N\times N$ matrix" by itself tells which will be cheaper for the BNF radar workload.

## 9. How the pieces fit together

1. **First model advance.** In: perturbed member initial states and boundary data. The tutorial's advance scripts run WRF. Out: the prior ensemble at the first analysis time.
2. **Observation conversion.** In: PREPBUFR or another observation source. Converts values, locations, times, types, errors and QC. Out: a DART observation sequence.
3. **Observation processing.** In: the converted observations and the domain. Selection, QC, and thinning or superobbing where supported. Out: the observations given to `filter`.
4. **Prior inflation.** In: the prior ensemble and the inflation restart fields. Damps the inflation estimate and scales the anomalies. Out: a prior with adjusted spread.
5. **Forward operators.** In: the members' model states and the observation definitions. Computes the predicted observations. Out: the ensemble in observation space.
6. **Scalar EAKF.** In: the predicted ensemble, the observed value and its error variance. Shifts the scalar mean and contracts the anomalies. Out: one observation increment per member.
7. **Regression and localization.** In: the observation increments, cross-covariances and distances. Updates nearby state elements and observation equivalents. Out: the updated ensemble, observation by observation.
8. **Inflation adaptation and output.** In: the prior inflation and the evidence from the observations. Updates the inflation estimates and saves the results. Out: posterior states and inflation restart fields.

The forward operator answers "what would this member predict at the observation?" Inflation changes the spread available; the EAKF works out what a measurement tells us; regression carries that to the state variables; localization limits how far it reaches.

## 10. Clarifications kept from the chat

- The script-control-flow branch corrected the first explanation of which script calls which.
- Generating the inflation restart files initializes the estimates and their uncertainty; it does not fit them to observations.
- The inflation uncertainty is not the atmospheric ensemble spread.
- The scalar EAKF adjustment is a mean shift plus an anomaly contraction, not simply observation minus member prediction.
- The observation variance is shared within one scalar update; the state–observation cross-covariance varies with the state element.
- The standard scalar EAKF regression and the EnSRF reduced-gain update are algebraically identical under matched choices. This corrects an overly broad distinction drawn earlier in the chat.
- Updating nearby observation equivalents is part of serial assimilation, not only of adaptive localization or inflation.
- DART's `preprocess` and `wrf_dart_obs_preprocess` are different programs.

The chat left two source checks open: the tutorial's exact inflation namelist and the call path of the adaptive-inflation routines. The likelihood in Eq. (5) explains the idea and does not replace that trace.

## 11. References used in the discussion

These links are entry points to the documentation; not every page matches one pinned source commit.

1. [WRF–DART tutorial](https://docs.dart.ucar.edu/en/latest/models/wrf/tutorial/README.html)
2. [DART preprocess](https://docs.dart.ucar.edu/en/latest/assimilation_code/programs/preprocess/preprocess.html)
3. [WRF observation preprocessing utility](https://docs.dart.ucar.edu/en/latest/models/wrf/WRF_DART_utilities/wrf_dart_obs_preprocess.html)
4. [DART inflation guide](https://docs.dart.ucar.edu/en/latest/guide/inflation.html)
5. [Adaptive inflation module](https://docs.dart.ucar.edu/en/latest/assimilation_code/modules/assimilation/adaptive_inflate_mod.html)
6. [Filter module](https://docs.dart.ucar.edu/en/latest/assimilation_code/modules/assimilation/filter_mod.html)
7. [Assimilation tools and localization](https://docs.dart.ucar.edu/en/latest/assimilation_code/modules/assimilation/assim_tools_mod.html)
8. [Covariance cutoff module](https://docs.dart.ucar.edu/en/latest/assimilation_code/modules/assimilation/cov_cutoff_mod.html)
9. [Three-dimensional spherical locations](https://docs.dart.ucar.edu/en/latest/assimilation_code/location/threed_sphere/location_mod.html)
10. [DART source repository](https://github.com/NCAR/DART)

The ensemble-filter equations collect the mathematics branch the user asked for. They describe the algorithms; they do not mean that DART allocates every matrix shown.
