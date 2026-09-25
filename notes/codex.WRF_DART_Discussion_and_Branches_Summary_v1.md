# WRF–DART tutorial: this chat and its explicit branches

Revised 24 September 2026 — Heng Xiao

**Scope:** The WRF–DART tutorial discussion in this chat, plus the explicitly requested branches on (1) the Step 4 script control flow and (2) EAKF analysis-ensemble construction compared with EnKF, EnSRF, ETKF and LETKF. This replaces the previous summary, which mistakenly incorporated separate project conversations. It is a technical summary, not a verbatim transcript; some branch material was available as retrieved summaries.

## 1. Step 4 and the script-control-flow branch

The question was why `new_advance_model.sh` appeared to run after perturbed initial conditions and an initial advance through `first_advance.sh`: was the model being integrated twice?

The branch corrected the original explanation of the script hierarchy. The reported call order was:

`init_ensemble_var.sh` → member job → `first_advance.sh` → `new_advance_model.sh` → `wrf.exe`.

| Script or program | Role in the tutorial flow discussed |
|---|---|
| `init_ensemble_var.sh` | Loops over ensemble members and submits a scheduler job for each member |
| `add_bank_perts.ncl` | Applies perturbation-bank fields to construct member initial conditions within that setup |
| `ndown.exe` | Optional nested-domain preparation in the tutorial member job |
| `first_advance.sh` | Prepares first-advance control information, including `wrf.info`/`filter_control`, calls the advance engine, and organizes the resulting priors |
| `new_advance_model.sh` | Performs the model-advance work, including preparing the run and invoking `wrf.exe` |
| `wrf.exe` | Integrates the atmospheric model |

Thus `first_advance.sh` and `new_advance_model.sh` are cooperating layers in one advance workflow. Calling both does not by itself mean two separate spinup integrations. The earlier explanation that assigned WRF execution to `first_advance.sh` and placed `new_advance_model.sh` above it was corrected in the branch.

The branch also explained that missing `filter_restart_*` files can be expected at initialization: there is no preceding DART posterior to insert, so the advance engine uses the prepared perturbed `wrfinput` states. Later cycles have an analyzed ensemble to advance.

These statements summarize the tutorial-script investigation. Exact filenames and control conventions should be interpreted for that tutorial version, rather than assumed universal across all WRF–DART workflows.

## 2. Steps 5–6: observations, types, quantities and forward operators

For the conventional-observation example, the processing path was

`PREPBUFR → prepbufr.x / prepbufr.csh → intermediate ASCII → create_real_obs → obs_seq.out`.

`&prep_bufr_nml` controls the PREPBUFR processing stage; `&ncepobs_nml` controls conversion/selection in `create_real_obs`. The observation sequence carries the measurement, location, time, observation type, observation-error variance and QC metadata. It does not contain a replacement for the model ensemble or a precomputed universal gain.

A radiosonde example is

`RADIOSONDE_TEMPERATURE → QTY_TEMPERATURE → WRF model_interpolate`.

The **type** distinguishes the observing category. The **quantity** identifies the physical field requested from the model interface. `&obs_kind_nml` selects types to assimilate or evaluate. `preprocess` generates the compiled observation-definition/type infrastructure.

For member \(i\), the forward operator computes

\[
y_i^f=\mathcal H(x_i^f).
\]

Temperature involves thermodynamic conversion and interpolation. Radar reflectivity instead depends on a microphysics-related operator, schematically

\[
Z=\mathcal H(q_r,q_s,q_g,\rho,T,\ldots).
\]

The radar `obs_def_radar_mod` path requests atmospheric quantities from the model interface. The discussion used this contrast to explain why the reflectivity operator and required model quantities must be identified explicitly.

For a single radiosonde temperature measurement, `obs_seq.out` supplies the observed value and error variance \(R=\sigma_o^2\), while `filter` obtains the ensemble of predicted temperatures. The assimilation then combines

\[
y_o,\quad R,\quad\{\mathcal H(x_i)\}_{i=1}^{N}.
\]

The observation type does not restrict increments to temperature alone. Winds, moisture and other state variables can also change through their ensemble covariance with predicted temperature, subject to localization and configured update restrictions.

## 3. `preprocess`, thinning and superobbing

**DART `preprocess` is a build-time source-generation program.** It assembles observation definitions and type/quantity machinery. It neither reads an observation sequence to thin it nor averages radar observations.

`wrf_dart_obs_preprocess` is a separate runtime utility. The discussion identified domain/boundary/elevation selection and superobbing for aircraft and satellite-wind observations. Its existence should not be interpreted as a general radar-superobbing implementation.

For BNF, the intended MRMS sampling belongs in the converter or a radar-specific observation-processing stage before `filter`.

| Method | Meaning |
|---|---|
| Thinning | Retain selected actual observations; discard others according to a reproducible rule |
| Superobbing | Combine multiple observations into representative observations with corresponding locations, times and error treatment |

The discussion distinguished retaining selected radar samples from constructing averaged observations. The aircraft/satellite-wind superobbing documented for the WRF utility does not establish that it performs the intended MRMS radar sampling.

## 4. Step 7: inflation initialization, application and adaptation

### 4.1 Multiplicative inflation

For an ensemble mean \(\bar x\) and anomalies \(x_i-\bar x\),

\[
\widetilde x_i=\bar x+\sqrt\lambda(x_i-\bar x).
\]

A uniform \(\lambda\) multiplies covariance by \(\lambda\) while preserving the mean. For spatially/variable-dependent values, with \(D=\operatorname{diag}(\sqrt{\lambda_j})\), covariance becomes \(DPD\), not one global scalar times \(P\).

### 4.2 Step 7 initializes fields

The tutorial example used `fill_inflation_restart` with initial prior inflation mean 1.0 and SD 0.6, with posterior-file generation disabled. WRF input files supply state geometry. This is initialization, not an observation-based optimization.

Representative files are `input_priorinf_mean_d01.nc` and `input_priorinf_sd_d01.nc`. The first contains the inflation estimate; the second describes uncertainty in that estimate, **not atmospheric ensemble spread**. The tutorial also illustrated files for a second WRF domain.

### 4.3 Adaptive estimation

The illustrative scalar argument uses an innovation \(d=y_o-\bar y^f\), an uninflated predicted-observation variance \(s^2\), and error variance \(R\):

\[
p(d\mid\lambda)\propto(\lambda s^2+R)^{-1/2}
\exp\left[-\frac{d^2}{2(\lambda s^2+R)}\right],
\qquad
p(\lambda\mid d)\propto p(\lambda)p(d\mid\lambda).
\]

This explains why innovations inform inflation. It is **not the full DART implementation formula** for spatially varying adaptive inflation. Local influence, correlations, finite ensembles and the algorithm’s treatment of already applied inflation matter. In particular, do not take an already inflated variance and multiply it by the same inflation again in this illustrative expression.

Flavor 2 uses the Gaussian adaptive formulation; flavor 5 uses an inverse-gamma formulation. These should not be conflated. The discussion used flavor 2 to explain the tutorial; the exact flavor and bounds in the tutorial configuration were identified for follow-up inspection.

For prior inflation, the documented sequence is: read → damp → inflate the prior → assimilate and adapt the inflation estimate → write the estimate for subsequent cycling. The damping expression discussed was

\[
\lambda_d=\left[1+\gamma(\sqrt\lambda-1)\right]^2.
\]

For \(\lambda=1.44\), \(\gamma=0.9\), this gives 1.3924. Updated prior inflation carries information forward; it does not retroactively reinflate the original prior using the final estimate from that same cycle. See the [DART inflation guide](https://docs.dart.ucar.edu/en/latest/guide/inflation.html).

### 4.4 Controls and code map

| Control | Role |
|---|---|
| `inf_flavor` | Inflation algorithm; first entry prior, second posterior |
| `inf_initial_from_restart` | Read inflation estimate from a restart |
| `inf_sd_initial_from_restart` | Read its uncertainty from a restart |
| `inf_initial`, `inf_sd_initial` | Initialization when not reading those fields |
| `inf_lower_bound`, `inf_upper_bound` | Bounds on the estimate |
| `inf_sd_lower_bound`, `inf_sd_max_change` | Controls on uncertainty evolution |
| `inf_damping` | Relaxation toward unity |
| `inf_deterministic` | Deterministic versus stochastic inflation application |

The code map is `fill_inflation_restart`, `filter`/`filter_mod`, `assim_tools_mod`, and `adaptive_inflate_mod`. Exact update routines and arguments were identified as a next source-tracing task, not fully traced in the main discussion. Stage-dependent output filenames should be taken from the pinned version rather than assumed to always start with `output_`.

If every member has \(q_r=0\), its variance remains zero under multiplicative inflation. More generally, zero variance in predicted reflectivity prevents a covariance regression from supplying the missing storm information. Environmental spread, spinup, operator floors and any additional perturbation strategy therefore need separate diagnosis.

## 5. Where localization happens

Localization happens inside `filter` during covariance-based state and observation-equivalent updates. It is not part of the physical forward operator and is not the same operation as observation thinning.

For EAKF, its core role is

\[
\Delta x_{j,i}=\rho_{jo}\frac{\operatorname{cov}(x_j,y)}{s^2}\Delta y_i.
\]

The code map discussed was `assim_tools_mod`, model/location `get_close` routines, three-dimensional spherical `location_mod`, and `cov_cutoff_mod`. Nearby-observation searches also support serial updating of observation equivalents; their role is broader than adaptive localization or inflation alone.

For Gaspari–Cohn, DART’s `cutoff` is a half-width and zero influence occurs at twice that value. Horizontal distance is angular; vertical distance requires a compatible coordinate and normalization. `horiz_dist_only=.true.` removes vertical separation from the metric. See [DART assimilation/localization documentation](https://docs.dart.ucar.edu/en/latest/assimilation_code/modules/assimilation/assim_tools_mod.html).

The main chat used an 18-km horizontal zero-influence distance as an example: its corresponding horizontal half-width is 9 km. Vertical localization additionally requires consistent vertical coordinates and an appropriate normalization. A radiosonde pressure location and a WRF model-level location must be made compatible before a three-dimensional distance is meaningful.

Adaptive inflation also depends on local observation influence, but the main discussion’s expression “inflation increment proportional to a localization taper” was conceptual, not a verified complete update equation.

## 6. EAKF comparison branch: basic EnKF mathematics

This section consolidates the actual EAKF comparison branch and makes the matrix dimensions explicit.

Let \(n\) be the state dimension, \(N\) the ensemble size, and \(p\) the number of observations. Use unnormalized anomaly matrices:

\[
X^f=[x_1^f,\ldots,x_N^f]\in\mathbb R^{n\times N},\qquad
A^f=X^f-\bar x^f\mathbf1^T,
\]

\[
Y^f=[\mathcal H(x_1^f),\ldots,\mathcal H(x_N^f)],\qquad
D^f=Y^f-\bar y^f\mathbf1^T\in\mathbb R^{p\times N}.
\]

Then

\[
P_{xy}=\frac{A^f(D^f)^T}{N-1},\qquad
P_{yy}=\frac{D^f(D^f)^T}{N-1},
\]

\[
K=P_{xy}(P_{yy}+R)^{-1},\qquad
\bar x^a=\bar x^f+K(y_o-\bar y^f).
\]

An ensemble filter computes these covariances from member predictions; it does **not require a tangent-linear observation Jacobian**. For nonlinear operators, generally \(\overline{\mathcal H(x)}\ne\mathcal H(\bar x)\).

For the unlocalized linear Kalman problem, the target covariance is

\[
P^a=P^f-P_{xy}(P_{yy}+R)^{-1}P_{yx}.
\]

Constructing \(X^a\) means obtaining both the updated mean and an anomaly matrix with the desired covariance. Many square roots can produce that covariance, so identical means/covariances do not in general imply identical members.

In the perturbed-observation EnKF,

\[
x_i^a=x_i^f+K[y_o+\epsilon_i-\mathcal H(x_i^f)],\qquad
\epsilon_i\sim\mathcal N(0,R).
\]

EAKF, EnSRF and ETKF avoid this observation-perturbation sampling noise through deterministic anomaly adjustments.

## 7. How EAKF constructs the analysis ensemble

For one scalar observation, define

\[
y_i^f=\mathcal H_o(x_i^f),\qquad
s^2=\frac1{N-1}\sum_i(y_i^f-\bar y^f)^2,
\qquad d=y_o-\bar y^f.
\]

The scalar posterior mean and variance are

\[
\bar y^a=\bar y^f+\frac{s^2}{s^2+R}d,\qquad
s_a^2=\frac{Rs^2}{s^2+R}.
\]

Set

\[
\alpha=\sqrt{\frac{R}{s^2+R}},\qquad
y_i^a=\bar y^a+\alpha(y_i^f-\bar y^f).
\]

Thus

\[
\Delta y_i=\frac{s^2}{s^2+R}d+(\alpha-1)(y_i^f-\bar y^f).
\]

This is a mean shift plus spread contraction, not simply the member innovation \(y_o-y_i^f\).

For a state element \(j\),

\[
c_j=\frac1{N-1}\sum_i(x_{j,i}^f-\bar x_j^f)(y_i^f-\bar y^f),
\qquad
x_{j,i}^a=x_{j,i}^f+\rho_{jo}\frac{c_j}{s^2}\Delta y_i.
\]

The division is the mathematical expression for \(s^2>0\); zero-variance cases require explicit handling.

### What is computed once, and what varies with state element?

- The observation mean, variance, scalar posterior adjustment and vector of member observation increments are computed once for that scalar assimilation step.
- Each nearby state element has its **own** \(c_j=\operatorname{cov}(x_j,y)\) and localization weight.
- The cross-covariances can be evaluated together as a matrix–vector operation, but they are not one common covariance reused for all state variables.
- The algorithm does not construct or invert the full \(n\times n\) state covariance.

This resolves an ambiguous branch statement that covariance was “not independently recalculated per state element”: the shared quantity is the observation variance/scalar adjustment; state–observation cross-covariance still varies with \(j\).

In DART’s serial observation processing, nearby unassimilated observation equivalents also receive regression updates. They are not necessarily freshly recomputed by calling the nonlinear forward operator after every scalar observation. Consequently the current predicted-observation ensemble later in the serial loop should not automatically be equated with a fresh evaluation of \(\mathcal H\) on the current state.

### Numerical example from the main chat

For predicted observations \([6,8,10,12,14]\), the ensemble mean is 10 and the sample variance is 10. With observation \(y_o=10\) and error variance \(R=2\),

\[
\bar y^a=10,\qquad s_a^2=\frac{20}{12}\approx1.667,\qquad
\alpha=\sqrt{\frac{2}{12}}\approx0.408.
\]

The adjusted predicted-observation ensemble is approximately

\[
[8.37,9.18,10,10.82,11.63],
\]

so the increments are approximately

\[
[+2.37,+1.18,0,-1.18,-2.37].
\]

The mean stays fixed because the observation equals the prior mean, but uncertainty decreases. If the observation were 12, the ensemble would both shift toward 12 and contract. These member-specific observation-space increments are then regressed onto each affected state element.

## 8. EAKF versus EnSRF, ETKF and LETKF

### 8.1 Scalar EnSRF and its equivalence to the EAKF construction above

For one observation, let \(c=P_{xy}\), \(K=c/(s^2+R)\), and let \(a_y\) be the row vector of predicted-observation anomalies. EnSRF uses

\[
\bar x^a=\bar x^f+Kd,
\qquad
A^a=A^f-\widetilde K a_y,
\qquad
\widetilde K=\frac{K}{1+\alpha}.
\]

The EAKF anomaly equation is

\[
A^a=A^f+\frac{c}{s^2}(\alpha-1)a_y.
\]

Since

\[
\frac{1-\alpha}{s^2}=\frac{1}{(s^2+R)(1+\alpha)},
\]

the two scalar updates are **algebraically identical**, including their member increments, when they use the same ensemble, scalar observation statistics and localization treatment. This is stronger than merely equal posterior means and covariances.

An earlier broad statement that EAKF and EnSRF necessarily use different member transforms was too strong for this serial scalar construction. Differences can arise from additional algorithm choices, localization implementations, inflation, observation handling or ordering. Nonlinearity alone does not undo the scalar algebraic identity if both methods receive the same predicted-observation ensemble and apply the same update.

### 8.2 ETKF: a simultaneous ensemble-space square root

Using the unnormalized anomalies defined above, define

\[
C=(N-1)I+(D^f)^TR^{-1}D^f\in\mathbb R^{N\times N},
\]

\[
\bar w=C^{-1}(D^f)^TR^{-1}(y_o-\bar y^f),
\qquad
\bar x^a=\bar x^f+A^f\bar w,
\]

\[
T=[(N-1)C^{-1}]^{1/2},\qquad
A^a=A^fT,
\qquad
X^a=\bar x^a\mathbf1^T+A^a.
\]

The usual symmetric square root preserves the ensemble-mean constraint. The main decomposition is in ensemble space, rather than state space. Actual implementations use matrix solves/factorizations rather than explicitly forming inverses wherever possible.

A global ETKF and an unlocalized serial square-root filter can agree on the linear Kalman posterior mean/covariance while differing in individual members because their square-root choices differ. Do not extend the specific scalar EAKF–EnSRF identity into a claim that all deterministic ensemble filters produce the same members.

### 8.3 LETKF: a different local transform at each analysis location

LETKF applies the ensemble-space construction to a local subset/weighting of observations around each analysis location. It obtains local weights \(\bar w_\ell\) and transform \(T_\ell\), then applies them to the state rows belonging to that location or local analysis region.

Localization commonly acts by selecting observations and reducing their precision with distance, for example \(R_{oo}^{-1}\mapsto\rho_{\ell o}R_{oo}^{-1}\) for diagonal errors. This is not generally identical to multiplying each serial state-regression increment by a taper. There is generally no single global transform \(T\) reproducing every LETKF local update.

| Method | Construction of analysis ensemble | Typical organization |
|---|---|---|
| Stochastic EnKF | Gain update with perturbed observations | Ensemble covariances plus random observation perturbations |
| Serial EAKF | Scalar deterministic adjustment followed by regression | Sequential observations; parallel state updates |
| Serial EnSRF | Mean gain plus reduced anomaly gain | Equivalent scalar construction under matched choices |
| ETKF | Ensemble-space mean weights and square root | Joint observation update with a global transform |
| LETKF | Local ensemble-space weights and square roots | Many local analyses that can run independently |

For a scalar EAKF update, covariance/regression work scales roughly with \(N\) times the number of affected state elements, plus updates to affected observation equivalents and communication. LETKF repeatedly forms/factorizes ensemble-sized local systems. Neither “serial” nor “an \(N\times N\) matrix” alone establishes which implementation will be cheaper for the BNF radar workload.

## 9. How the pieces fit together

| Stage | Inputs | Main operation | Outputs |
|---|---|---|---|
| First model advance | Perturbed member initial states and boundary data | Tutorial advance scripts run WRF | Prior ensemble at the first analysis time |
| Observation conversion | PREPBUFR or another observation source | Convert values, locations, times, types, errors and QC | DART observation sequence |
| Observation processing | Converted observations and domain information | Selection/QC and supported thinning or superobbing | Observations supplied to `filter` |
| Prior inflation | Prior ensemble and inflation restart fields | Dampen the inflation estimate and scale anomalies | Spread-adjusted prior |
| Forward operators | Member model states and observation definitions | Compute predicted observations | Observation-space ensemble |
| Scalar EAKF | Predicted ensemble, actual observation and error variance | Shift the scalar mean and contract anomalies | Member-specific observation increments |
| Regression and localization | Observation increments, cross-covariances and distances | Update nearby state elements and observation equivalents | Updated ensemble during serial assimilation |
| Inflation adaptation and output | Prior information and observation evidence | Update inflation estimates and save results | Posterior states and inflation restart fields |

The forward operator answers “what would this member predict at the observation?” Inflation changes available spread; the EAKF computes the information supplied by a measurement; regression transfers that information to state variables; localization controls its spatial reach.

## 10. Clarifications retained in this summary

- The script-control-flow branch corrected the initial explanation of which script calls which.
- Inflation restart generation initializes estimates and their uncertainty; it does not optimize them against observations.
- Inflation uncertainty is distinct from atmospheric ensemble spread.
- The scalar EAKF adjustment is a mean shift plus anomaly contraction, rather than simply observation minus member prediction.
- The observation variance is shared within one scalar update; state–observation cross-covariances vary with the state element.
- The standard scalar EAKF regression construction and EnSRF reduced-gain construction are algebraically identical under matched choices. This mathematical clarification corrects an overly broad earlier distinction between them.
- Nearby-observation updates are part of serial assimilation, not solely an adaptive-localization or inflation operation.
- DART `preprocess` and `wrf_dart_obs_preprocess` are different programs.

The main chat left the exact tutorial inflation namelist and the detailed adaptive-inflation routine call path as follow-up source checks. The Bayesian likelihood presented here is explanatory, not a substitute for that source-level trace.

## 11. References used in this discussion

These documentation links are reference entry points, not a claim that every page corresponds to one pinned source commit.

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

The ensemble-filter equations are a consolidation of the explicitly requested mathematics branch. They describe the algorithms without implying that DART explicitly allocates every displayed matrix.
