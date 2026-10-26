# Check of the Codex WRF–DART summary

Written 2026-10-25. This note checks `codex_wrf_dart_summary.md`, the Typora conversion of `codex.WRF_DART_Discussion_and_Branches_Summary_v1.md`; section and equation numbers called "summary Sec. n" and "summary Eq. (n)" are the conversion's. It was checked against the pinned DART (commit `7bbd35a09`, `../software/DART`), including the WRF tutorial's scripts (`models/wrf/shell_scripts/`) and files (`models/wrf/tutorial/`), and against this repo's notes. DART paths are relative to `../software/DART`, and a bare line reference such as `:543` refers to the file named just before it.

**Result.** One statement is wrong (C1, the inflation damping). The rest is right as far as it goes. C2–C13 fill in what it leaves out or keeps vague, and Sec. 3 lists the statements that were confirmed.

| Item | Summary Sec. | Finding |
|---|---|---|
| C1 | 4.3 | Damping: the code damps $\lambda$, not $\sqrt\lambda$ (**error**) |
| C2 | 1 | The advance also perturbs the lateral boundaries |
| C3 | 2 | What the temperature operator needs from WRF |
| C4 | 2 | Reflectivity: our $\mathcal H(x)$ is interpolated `REFL_10CM` |
| C5 | 3 | `wrf_dart_obs_preprocess` does more |
| C6 | 4.3, 5 | DART's actual inflation likelihood |
| C7 | 4.3 | The tutorial's inflation namelist |
| C8 | 4.4 | Flavors, file names, routines |
| C9 | 4.4, 7 | What DART does with zero spread |
| C10 | 5 | Other factors on the increment; the vertical |
| C11 | 7 | $\mathcal H(x)$ is computed once per filter run |
| C12 | 8 | One observation: the symmetric ETKF gives the EAKF's members |
| C13 | 9 | Steps missing from the order of a filter run |

## 1. Error

### C1. Inflation damping (summary Sec. 4.3, Eq. 6)

The summary gives $\lambda_d=[1+\gamma(\sqrt\lambda-1)]^2$, which damps $\sqrt\lambda$. The code damps $\lambda$ itself (`assimilation_code/modules/assimilation/filter_mod.f90:824–827`):

$$
\lambda_d=1+\gamma\,(\lambda-1).
\tag{1}
$$

- For $\lambda=1.44$ and $\gamma=0.9$ this gives 1.396, not 1.3924.
- **Where the summary's form comes from:** Gharamti (2018) Sec. 3d and the note "Order of (prior) inflation operations" in DART's inflation guide damp $\sqrt\lambda$. The guide's `inf_damping` entry describes what the code does.
- **How much it matters:** little. For $\gamma=0.9$, $\lambda$ = 2 and 3 become 1.900 and 2.800 in the code, against 1.885 and 2.752 with the $\sqrt\lambda$ form.
- Only the inflation mean is damped; the sd carries over undamped.
- The same bracket $[1+\gamma(\sqrt\lambda-1)]^2$ does appear in DART's adaptive inflation, but with a different $\gamma$ and a different meaning (C6).
- More detail: `dart_adaptive_inflation.md` Sec. 2 (step 2) and Sec. 8 (item 1).

## 2. Incomplete or vague

### C2. The advance also perturbs the lateral boundaries (summary Sec. 1)

- **Boundaries.** For each boundary interval of the advance, `new_advance_model.sh` takes the mean `wrfinput` at the interval's end and adds the member's bank perturbation with `add_bank_perts.ncl`, the same script as for the initial conditions (`:511–536`). It then builds the member's `wrfbdy` with `pert_wrf_bc` (`:543`). Tutorial Step 3 says so too. So `add_bank_perts.ncl` runs once in the member job and again in every advance.
- **The bank.** It is made in tutorial Step 3 (`gen_pert_bank.sh`: WRFDA random-CV option 3, 60 perturbations for 20 members). `add_bank_perts.ncl` adds a perturbation to U, V, THM, QVAPOR and MU, scaled by 1.3 (MU by 0.6) (`:21–25`, `:58–60`).
- **Why the tutorial seems to run WRF in `first_advance.sh`.** `first_advance.sh` writes the `mpiexec ... ./wrf.exe` command into `wrf.info` (`:43–64`). `new_advance_model.sh` reads it back as `ADV_MOD_COMMAND` (`:360`) and runs it. The tutorial's Step 4 calls this "the mpi run command within `first_advance.sh`" (`models/wrf/tutorial/README.rst:654`), which is probably where the first, wrong explanation in the chat came from.
- **Our pilot** does the same job with its own scripts: a WRFDA perturbation bank and a patched `pert_wrf_bc` (`da_5member_pilot_steps.md`).

### C3. What the temperature operator needs (summary Sec. 2)

- **One more layer.** WRF's `model_mod` adds a layer between the quantity and the WRF field: each state variable in `wrf_state_variables` has a WRF "TYPE" (`TYPE_T2`, `TYPE_T`, ...). An observation counts as a surface observation only if its vertical coordinate is `VERTISSURFACE` (tutorial Step 6).
- **Upper-air temperature.** `RADIOSONDE_TEMPERATURE` (quantity `QTY_TEMPERATURE`) needs THM, QVAPOR, MU and PH: the temperature comes from the potential temperature and the pressure, followed by horizontal interpolation on levels k and k+1 and vertical interpolation (tutorial Step 6 table).
- **2-m temperature.** `METAR_TEMPERATURE_2_METER` (`QTY_2M_TEMPERATURE`) is only a horizontal interpolation of T2.
- **Dry theta.** The conversion takes THM to be the dry potential temperature: `models/wrf/model_mod.f90:716–719` stops unless `use_theta_m = 0`. This is why our DART runs use the `theta_m0` setup for now.

### C4. The reflectivity operator (summary Sec. 2, Eq. 2)

- **The state first.** `obs_def_radar_mod` first asks the model for `QTY_RADAR_REFLECTIVITY` (`observations/forward_operators/obs_def_radar_mod.f90:1125`). It computes $Z$ from $q_r$, $q_s$, $q_g$, $\rho$ and $T$ (summary Eq. 2) only if the state has no reflectivity. Its comment warns that this computation "is accurate only for the simple single-moment microphysics schemes (e.g., Kessler or Lin)" (`:1119–1122`).
- **Our runs** use `microphysics_type = 5` with `REFL_10CM` in the state as `NO_COPY_BACK` (`cases/20250520/da_theta_m0/config/input.nml.filter_joint`), as HRRRDAS does. $\mathcal H$ is then just an interpolation of WRF's own diagnosed reflectivity, which is consistent with WRF's microphysics. The hydrometeors change only through their ensemble covariance with it.
- **Floors.** The observations and $\mathcal H(x)$ are floored at `lowest_reflectivity_obs` and `lowest_reflectivity_fwd_op` (−10 dBZ for us). This matters for C9.

### C5. `wrf_dart_obs_preprocess` does more (summary Sec. 3)

Besides domain, boundary and elevation selection and the superobbing of aircraft and satellite winds (`superob_aircraft`, `superob_sat_winds`), its namelist `&wrf_obs_preproc_nml` (`models/wrf/WRF_DART_utilities/wrf_dart_obs_preprocess.f90`) also controls these steps:

- merging extra observation files by family (`sonde_extra`, `metar_extra`, ...);
- dropping observations above `obs_pressure_top` or `obs_height_top`;
- keeping or dropping radiosonde significant levels (`include_sig_data`);
- overwriting observation times with the analysis time (`overwrite_obs_time`) and overwriting NCEP QC;
- removing sondes near a tropical cyclone (`tc_sonde_radii`);
- inflating observation errors near the lateral boundary (`increase_bdy_error`, `maxobsfac`, `obsdistbdy`).

It also skips a surface observation whose location is already in the sequence (`original_observation`, `:866–883`). Under our single precision that test reaches ~2 km, and it dropped METARs behind mesonet sites (`obs_expansion.md` Sec. 7.2). The summary is right that the utility does no radar sampling; ours is done in `scripts/da/mrms_to_obs_seq.py`.

### C6. DART's adaptive-inflation likelihood (summary Sec. 4.3, Eq. 5; Sec. 5, last paragraph)

For an observation and a state element with inflation $\lambda$, DART takes the innovation as $d\sim\mathcal N(0,\theta^2)$ (Anderson 2009; Gharamti 2018). For flavor 2,

$$
\theta^2=\left[1+\gamma(\sqrt\lambda-1)\right]^2\sigma_p^2+R,
\tag{2}
$$

and for flavor 5,

$$
\theta^2=\left(\left[1+\gamma(\sqrt\lambda-1)\right]^2-\frac1N\right)\sigma_p^2+R.
\tag{3}
$$

- **$\gamma$** is the localization × impact weight times $|r|$, the absolute sample correlation between the element and the predicted observation (`assimilation_code/modules/assimilation/adaptive_inflate_mod.f90:729`). This makes the summary's "inflation increment proportional to a localization taper" precise: inflating the element is taken to scale the predicted observation's sd by $1+\gamma(\sqrt\lambda-1)$. That factor runs from 1 (unrelated, $\gamma=0$) to $\sqrt\lambda$ (the observation is the element, $\gamma=1$).
- **$\sigma_p^2$** is the variance of $\mathcal H(x)$ from the inflated ensemble, with this cycle's inflation divided back out (`:732–737`). The summary's warning not to inflate twice is therefore exactly what the code does.
- **Summary Eq. (5)** is flavor 2 with $\gamma=1$, which is the observation-space case of Anderson (2007).
- **Flavor 5's $-1/N$** comes from Gharamti's building the innovation statistics from the member innovations (G18 (16)–(26)).
- More detail: `dart_adaptive_inflation.md` Secs. 3–5.

### C7. The tutorial's inflation namelist (summary Sec. 4.3)

The summary left the tutorial's flavor and bounds open. They are in `models/wrf/tutorial/template/input.nml.template:36–45`:

| Item | Prior | Posterior |
|---|---|---|
| `inf_flavor` | 2 | 0 (off) |
| `inf_initial` | 1.0 | 1.12 |
| `inf_sd_initial` | 0.6 | 0.50 |
| `inf_lower_bound` | 1.0 | 1.0 |
| `inf_upper_bound` | 10000 | 10000 |
| `inf_damping` | 0.9 | 1.0 |
| `inf_sd_lower_bound` | 0.6 | 0.10 |
| `inf_sd_max_change` | 1.05 | 1.05 |

- **The sd never changes.** `inf_sd_lower_bound` equals `inf_sd_initial`, and the flavor-2 sd can only shrink. The code exits early when the sd is at its floor (`adaptive_inflate_mod.f90:862–864`). So the tutorial adapts $\lambda$ with a fixed $\sigma_\lambda=0.6$.
- **Damping is per cycle**, and the tutorial cycles every 6 h.
- **Our `input.nml.filter`** has the same prior values except `inf_upper_bound = 5`. At our 15-min cycles the same 0.9 relaxes $\lambda$ toward 1 24 times faster in time.

### C8. Flavors, file names and routines (summary Sec. 4.4)

- **Flavors** (`adaptive_inflate_mod.f90:58–66`):
  - 0: none.
  - 1: observation-space (deprecated).
  - 2: spatially varying, state-space (Anderson 2009).
  - 3: one spatially constant value.
  - 4: RTPS, posterior only (`:465–468`).
  - 5: enhanced, inverse-gamma prior (Gharamti 2018).
- **File names.** The files are `<stage>_priorinf_mean.nc` and `<stage>_priorinf_sd.nc`, with `_d01`, `_d02`, ... before `.nc` only when there are several domains. The stage is `input`, `forecast`, `preassim`, `postassim`, `analysis` or `output` (`stages_to_write`). `preassim_priorinf_mean` is the damped $\lambda$ that was applied, and `output_priorinf_mean` is the updated estimate, which becomes the next cycle's `input_priorinf_mean`.
- **Routines** (the summary left them open):
  - damping: `filter_mod.f90:824–827`;
  - inflation: `filter_ensemble_inflate` → `inflate_ens`;
  - adaptation for each observation–element pair: `update_varying_state_space_inflation` (`adaptive_inflate_mod.f90:707–756`), which calls `linear_bayes` (flavor 2) or `enh_linear_bayes` (flavor 5) for the mean and `bayes_cov_inflate` for the sd.
  - Full map: `dart_adaptive_inflation.md` Sec. 6.
- **`inf_sd_max_change`** limits increases of the sd. The flavor-2 sd never increases, so in practice the setting matters only for flavor 5. It applies to each observation's update, not to each cycle as the guide says (`dart_adaptive_inflation.md` Sec. 8, item 2).

### C9. What DART does with zero spread (summary Sec. 4.4, last paragraph; Sec. 7)

- **No update.** DART handles zero spread by doing nothing. With zero prior variance of $\mathcal H(x)$ the observation increments are zero (`assimilation_code/modules/assimilation/assim_tools_mod.f90:977–994`; it stops if $R$ is also zero), and the regression coefficient is set to 0 (`:1498–1500`). Zero correlation also leaves the inflation alone ($\gamma=0$, C6).
- **Reflectivity.** With the −10 dBZ floor (C4), members with no echo all give exactly −10 dBZ. Where every member is clear, neither a clear-air observation nor an observed echo changes anything. This is the reflectivity case of the summary's point that multiplicative inflation cannot create spread.

### C10. Other factors on the increment, and the vertical (summary Sec. 5)

- **Impact factor.** The weight in summary Eq. (7) is the Gaspari–Cohn factor times the observation-impact factor (`cov_and_impact_factors`, `assim_tools_mod.f90:2065` ff.). Our `obs_impact_*.txt` tables set the impact to 0 for some pairs.
- **Sampling-error correction.** With `sampling_error_correction = .true.` (ours), the regression coefficient is also scaled by a factor that depends on the sample correlation (`:1512–1540`; `dart_sampling_error_correction.md`).
- **Per-type cutoffs.** The cutoff can differ by observation type (`special_localization_obs_types` and `special_localization_cutoffs` in `&assim_tools_nml`).
- **Vertical.**
  - The coordinate is chosen in WRF's `&model_nml` (`vert_localization_coord`; ours is 4, scale height).
  - Observation and state verticals are converted to it (`convert_all_obs_verticals_first`, `convert_all_state_verticals_first`).
  - `&location_nml` scales it (`vert_normalization_*`, and per type `special_vert_normalization_*`).
  - The distance is $\sqrt{\Delta h^2+(\Delta z/v)^2}$, with $\Delta h$ in radians and $v$ the vertical normalization.
- **The 18-km example.** A 9-km half-width is `cutoff` = 9/6371 ≈ 0.001413 rad, the value our one-pass namelist uses for the radar types. DART's `earth_radius` is 6370 km (`assimilation_code/modules/utilities/types_mod.f90:125`), a negligible difference.

### C11. $\mathcal H(x)$ is computed once per filter run (summary Sec. 7)

The summary says the observation equivalents are "not necessarily" recomputed after each observation. In fact they never are:

- Within one filter run, DART computes every $\mathcal H(x)$ once, from the inflated prior, before the observation loop.
- After that, the loop changes them only by regression, and only for observations not yet assimilated (`assim_tools_mod.f90:808–817`).
- This is the parallel algorithm of Anderson and Collins (2007), which equals the sequential one for linear $\mathcal H$ (`dart_eakf.md` Sec. 6).

### C12. ETKF and EAKF members (summary Secs. 8.2–8.3)

**One observation.** For a single observation the symmetric ETKF gives exactly the EAKF's members. With $D^f$ a single row $a_y$, $\lVert a_y\rVert^2=(N-1)s^2$ and $A^fa_y^T=(N-1)c$, summary Eqs. (22) and (24) give

$$
\begin{aligned}
T&=I+(\alpha-1)\frac{a_y^Ta_y}{\lVert a_y\rVert^2},\\
A^fT&=A^f+\frac{c}{s^2}(\alpha-1)\,a_y,
\end{aligned}
\tag{4}
$$

which is summary Eq. (20).

**Several observations.** The members differ only when several observations are assimilated at once. In `dart_eakf.md` check 2 (serial EAKF against ETKF, several observations), the means and covariances agreed to 3e-15 while the members differed by 0.11. So the summary's warning holds, but only for more than one observation.

**R- versus B-localization.** The summary says only that they are "not generally identical". At the same weight $\kappa$, the LETKF's gain $c/(s^2+R/\kappa)$ is larger than the serial filter's $\kappa c/(s^2+R)$. R-localization therefore damps less, and the more accurate the observation, the less it damps (`dart_eakf.md` Sec. 9.5).

### C13. Steps missing from the order of a filter run (summary Sec. 9)

Summary Sec. 9 leaves out filter's outlier check and the posterior inflation. The full order within one filter run:

```
read the prior inflation (lambda, sd)
  v
damp lambda (mean only)
  v
inflate the prior ensemble
  v
H(x) for every observation, from the inflated members
  v
outlier check; QC 4 where the forward operator failed
  v
serial loop over the observations: EAKF increment,
regression onto the state and the later H(x), inflation update
  v
posterior inflation (off in the tutorial and in our runs)
  v
write the posterior states and output_priorinf_{mean,sd}
```

- **Outlier check.** An observation is rejected (DART QC 7) when $|\bar y^f-y_o|>$ `outlier_threshold` $\times\sqrt{s^2+R}$ (`assimilation_code/modules/assimilation/quality_control_mod.f90:241–285`). Ours is 3 for all types.
- **Failed forward operators.** An observation whose forward operator failed gets QC 4 (`:203`) and is not assimilated.
- The full list of steps is in `dart_workflow_walkthrough.md` Sec. 2.

## 3. Confirmed

- **Script chain (summary Sec. 1).**
  - `init_ensemble_var.sh` writes one job script per member and submits it with `qsub` (`:250`).
  - The job runs `add_bank_perts.ncl`, then `ndown.exe` if there is a nest, then `first_advance.sh` (`:246`).
  - `first_advance.sh` writes `wrf.info` and `filter_control<n>` and calls `new_advance_model.sh` (`:85`). It then moves the priors to `output/<date>/PRIORS` (`:88–96`).
  - So there is no double integration.
- **Missing `filter_restart_*` at initialization.** `new_advance_model.sh:281–284` copies fields from `filter_restart_d0N.<n>` into `wrfinput_d0N` only if that file exists.
- **PREPBUFR path.** It is a two-stage conversion (tutorial Step 5). `&prep_bufr_nml` is read by `prepbufr.f`, and `&ncepobs_nml` by `create_real_obs.f90`.
- **Type and quantity.** `RADIOSONDE_TEMPERATURE` maps to `QTY_TEMPERATURE` (`observations/forward_operators/obs_def_reanalysis_bufr_mod.f90:17`).
- **`preprocess`** is a build-time step that writes `obs_kind_mod.f90` and `obs_def_mod.f90` (tutorial Step 6).
- **`fill_inflation_restart`.** The tutorial uses mean 1.0 and sd 0.6, writes no posterior files, uses the `wrfinput` files only as templates, and needs one pair of files per domain (`models/wrf/tutorial/README.rst:949–1015`).
- **Order of prior inflation.** The code runs read → damp → inflate → assimilate and adapt → write (with $\mathcal H(x)$ between inflate and assimilate, C13).
- **Gaspari–Cohn.** `cutoff` is the half-width, and the weight is zero from twice the cutoff on (`cov_cutoff_mod.f90:150–161`).
- **Scalar EAKF.** Summary Eqs. (13)–(16) are `obs_increment_eakf` (`assim_tools_mod.f90:1113–1133`), and Eq. (17) is `update_from_obs_inc` (`:1498`). The numerical example recomputes to 8.37, 9.18, 10, 10.82 and 11.63.
- **EAKF–EnSRF identity.** It also holds with localization, and it was checked against GSI's EnSRF code to round-off (`dart_eakf.md` Secs. 9.3 and 10.2, check 1).
- **ETKF and LETKF equations.** They match Hunt et al. (2007), including R-localization by $\rho_{\ell o}R^{-1}_{oo}$.
- **Updating observation equivalents.** Only observations not yet assimilated are updated (`assim_tools_mod.f90:816–817`).
