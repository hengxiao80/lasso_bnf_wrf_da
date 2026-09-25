# WRFDA RANDOMCV/CV3 IC and LBC Ensemble Generation for WRF-DART

## Purpose

This note summarizes the WRFDA `RANDOMCV` / CV3 procedure discussed for generating initial-condition (IC) and lateral-boundary-condition (LBC) perturbations for the LASSO BNF WRF-DART ensemble.

The intended use is a 2.5-km WRF-DART ensemble centered on HRRRv4 hourly analyses, with the resulting 2.5-km analyses supplying initial and boundary forcing for higher-resolution LES domains.

The key conceptual distinction is:

- **CV3 defines a static background-error covariance model** used to generate the initial perturbations.
- **WRFDA RANDOMCV samples from that covariance model** without performing a variational minimization.
- After WRF integration begins, the ensemble covariance evolves dynamically and is no longer simply the CV3 covariance.
- For LBCs, the stock WRFDA/DART workflow perturbs complete WRF states at successive boundary times and reconstructs WRF boundary values and tendencies from those states.

## 1. Mathematical interpretation of RANDOMCV

In ordinary incremental 3D-Var,

\[
J(\delta x)
=
\frac{1}{2}\delta x^T B^{-1}\delta x
+
\frac{1}{2}[d-H\delta x]^T R^{-1}[d-H\delta x],
\]

where

\[
d = y-H(x_b),
\]

and:

- \(x_b\) is the background / first-guess state,
- \(y\) is the observation vector,
- \(H\) is the observation operator,
- \(B\) is the background-error covariance matrix,
- \(R\) is the observation-error covariance matrix.

WRFDA introduces a control-variable transform

\[
\delta x = Uv,
\]

such that approximately

\[
B = UU^T.
\]

In control-variable space,

\[
v \sim N(0,I)
\]

corresponds to a physical-space perturbation

\[
\delta x = Uv
\]

with

\[
E[\delta x]=0,
\]

and

\[
\operatorname{Cov}(\delta x)=UIU^T=B.
\]

Thus, for ensemble member \(m\),

\[
\boxed{\delta x_m = B_{\rm CV3}^{1/2}\xi_m},
\qquad
\xi_m\sim N(0,I),
\]

and

\[
\boxed{x_m=x_b+\delta x_m}.
\]

There is no observational cost-function minimization in RANDOMCV mode. For the BNF application, \(x_b\) is the unperturbed HRRR-centered WRF state at the applicable IC or boundary time.

## 2. CV3 control variables

The CV3 control vector is approximately

\[
v = [\psi,\;\chi_u,\;T_u,\;RH_s,\;P_{s,u}]^T,
\]

where:

- \(\psi\): streamfunction,
- \(\chi_u\): unbalanced velocity potential,
- \(T_u\): unbalanced temperature,
- \(RH_s\): pseudo-relative-humidity control variable,
- \(P_{s,u}\): unbalanced surface pressure.

The subscript \(u\) denotes an unbalanced component. Conceptually,

\[
\chi=\chi_b(\psi)+\chi_u,
\]

\[
T=T_b(\psi)+T_u,
\]

\[
P_s=P_{s,b}(\psi)+P_{s,u}.
\]

Wind is reconstructed from streamfunction and velocity potential, schematically as

\[
u=-\frac{\partial\psi}{\partial y}+\frac{\partial\chi}{\partial x},
\]

\[
v=\frac{\partial\psi}{\partial x}+\frac{\partial\chi}{\partial y},
\]

with grid metrics/map factors handled by the actual implementation.

Therefore RANDOMCV does not independently add noise to WRF `U`, `V`, `T`, `Q`, etc. It generates random control-space perturbations and transforms them into a correlated, multivariate WRF-state perturbation.

## 3. CV3 covariance structure

A useful conceptual factorization is

\[
B=D_\sigma C D_\sigma,
\]

where \(D_\sigma\) contains background-error standard deviations and \(C\) is the correlation operator.

For the temperature control variable,

\[
B_T=D_{\sigma_T}C_TD_{\sigma_T}.
\]

Here

\[
D_{\sigma_T}=\operatorname{diag}(\sigma_{T,1},\sigma_{T,2},\ldots)
\]

controls amplitude, while

\[
(C_T)_{ij}=\operatorname{Corr}(T'_{u,i},T'_{u,j})
\]

defines spatial correlation.

The earlier shorthand \(\sigma_T(k,\phi)\) was conceptual notation for a standard deviation varying with vertical level \(k\) and possibly latitude \(\phi\); it should not be interpreted as a literal WRFDA array name.

The full 3-D correlation operator can be thought of schematically as

\[
C_T\approx C_z C_y C_x,
\]

where \(C_x\), \(C_y\), and \(C_z\) represent directional correlation/filter operators. In the actual code these are applied numerically; WRFDA does not construct the full explicit covariance matrix.

## 4. Operator view of the CV3 transform

A useful schematic factorization is

\[
\delta x=U_pU_bU_vU_hU_s\xi,
\]

where:

- \(U_s\): variance / amplitude scaling,
- \(U_h\): horizontal correlation transform,
- \(U_v\): vertical correlation transform,
- \(U_b\): balance / multivariate transform,
- \(U_p\): conversion into the WRF state representation.

Thus RANDOMCV can be viewed as

\[
\xi
\rightarrow
\text{amplitude scaling}
\rightarrow
\text{spatial filtering} \\
\rightarrow
\text{balance transform}
\rightarrow
\text{WRF perturbation}.
\]

This factorization is conceptual; the exact grouping of operations among WRFDA routines is implementation-specific.

## 5. WRFDA code path for RANDOMCV

The relevant execution path is approximately:

```fortran
call da_random_seed

do i = 1, n_randomcv
   call da_set_randomcv(cv_size, cvt)
   call da_transform_vtox(grid, cv_size, xbx, be, grid%ep, cvt, grid%vv, grid%vp)
   call da_transform_xtoxa(grid)
   call da_transfer_xatoanalysis(...)
   call da_update_firstguess(grid, 'wrfvar_output_randomcv.e' // trim(ci))
   ! restore the original background
end do
```

### `da_set_randomcv`

This routine fills the control vector with Gaussian random numbers,

\[
\xi_i\sim N(0,1).
\]

The raw random vector is therefore uncorrelated unit Gaussian noise. Meteorological structure appears only after the control-variable transform.

### `da_transform_vtox`

This is the control-variable-to-model-space transform,

\[
x'=Uv.
\]

For `cv_options = 3`, the path includes routines conceptually corresponding to

```fortran
call da_apply_be(...)
call da_transform_bal(...)
```

where the CV3 amplitude/correlation structure and multivariate balance relationships are applied.

## 6. Meaning of `as1`-`as5`

For CV3, the scaling parameters correspond approximately to:

- `as1`: streamfunction,
- `as2`: unbalanced velocity potential,
- `as3`: unbalanced temperature,
- `as4`: pseudo-relative humidity,
- `as5`: unbalanced surface pressure.

Each group has components controlling variance/amplitude scaling and horizontal/vertical correlation scales.

A caution: the WRFDA documentation describes the first component in terms of variance scaling, so a value such as `as3(1)=0.5` should not automatically be interpreted as “halve the temperature standard deviation.” The safer approach is to tune against the resulting physical-space ensemble spread and correlation scales.

## 7. Initial ensemble covariance

For an ensemble

\[
x_m(t_0)=\bar x(t_0)+\delta x_m,
\]

the sample covariance is

\[
\boxed{P_0=\frac{1}{N-1}\sum_{m=1}^{N}(x_m-\bar x)(x_m-\bar x)^T}.
\]

If the perturbations are drawn from CV3, then in expectation

\[
E[P_0]\approx B_{\rm CV3},
\]

and in the large-ensemble limit

\[
P_0\rightarrow B_{\rm CV3}.
\]

For \(N=50\), sampling error means \(P_0\neq B_{\rm CV3}\) exactly.

## 8. Finite-sample mean centering

Even though

\[
E[\delta x]=0,
\]

the sample mean perturbation from 50 members is generally nonzero:

\[
\bar{\delta x}=\frac{1}{N}\sum_{m=1}^{N}\delta x_m.
\]

Define centered perturbations

\[
\delta x_m^*=\delta x_m-\bar{\delta x}.
\]

Then construct

\[
x_m=x_{\rm HRRR}+\delta x_m^*.
\]

This preserves the HRRR state as the exact finite-ensemble mean before any later nonlinear clipping or constraints.

## 9. Evolution after WRF spinup

Immediately after RANDOMCV generation,

\[
P_0\approx B_{\rm CV3}.
\]

After WRF integration,

\[
x_m(t)=M_{t_0\rightarrow t}[x_m(t_0)].
\]

For small perturbations,

\[
\delta x_m(t)\approx M'\delta x_m(t_0),
\]

so

\[
P(t)\approx M'P_0M'^T.
\]

For convection-permitting WRF, nonlinear moist dynamics quickly make this linear view incomplete. The DART forecast covariance is the flow-dependent sample covariance

\[
\boxed{P^f(t)=\frac{1}{N-1}\sum_{m=1}^{N}[x_m^f(t)-\bar x^f(t)][x_m^f(t)-\bar x^f(t)]^T}.
\]

Keep the following distinct:

- \(B_{\rm CV3}\): static seed covariance,
- \(P_{\rm spinup}\): dynamically evolved covariance after spinup,
- \(P_{\rm DART}^f\): forecast covariance used by the EAKF.

## 10. Convective-scale limitation of CV3

CV3 is a generic static background-error model, historically based on coarser-scale NWP statistics. It does not directly provide a realistic 2.5-km convective-scale ensemble covariance.

In particular, initial spread in quantities such as vertical velocity, hydrometeors, reflectivity, cold-pool structure, and storm position must largely be generated dynamically during WRF spinup.

This matters because multiplicative inflation cannot create variance where the ensemble has essentially zero spread.

Therefore pre-DA WRF spinup is an important part of the BNF design.

## 11. Diagnostics before radar DA

The initial perturbation bank should be checked for:

- ensemble-mean residual relative to HRRR,
- \(u\), \(v\), temperature, moisture, and surface-pressure spread,
- vertical profiles of spread,
- horizontal and vertical correlation scales,
- balanced wind/temperature/pressure relationships,
- moisture extrema and supersaturation,
- negative water species,
- domain-edge behavior.

After spinup, add diagnostics of:

- vertical-velocity spread,
- hydrometeor spread,
- composite-reflectivity spread,
- CAPE/CIN spread,
- cold-pool spread,
- low-level convergence spread,
- storm-position spread,
- boundary-zone artifacts.

## 12. Stock WRFDA/DART LBC perturbation procedure

The stock `da_perturb_wrf_bc.ksh` workflow does **not** simply add a perturbation directly to an existing `wrfbdy` file.

Instead, for each member it:

1. generates a perturbed complete WRF state at the beginning of a boundary interval,
2. generates another perturbed complete WRF state at the end of the interval,
3. passes those two states plus the original `wrfbdy` file to `pert_wrf_bc`,
4. reconstructs boundary values and boundary tendencies from the two perturbed endpoint states.

For

\[
t_0\rightarrow t_1,
\qquad
\Delta t_{\rm LBC}=t_1-t_0,
\]

RANDOMCV generates

\[
x_m(t_0)=x_b(t_0)+\delta x_m(t_0),
\]

\[
x_m(t_1)=x_b(t_1)+\delta x_m(t_1).
\]

Then `pert_wrf_bc` constructs

\[
\boxed{b_m(t_0)=\mathcal B[x_m(t_0)]},
\]

and

\[
\boxed{\dot b_m(t_0)=\frac{\mathcal B[x_m(t_1)]-\mathcal B[x_m(t_0)]}{\Delta t_{\rm LBC}}}.
\]

Here \(\mathcal B\) denotes extracting the WRF boundary slab and converting it into the coupled form required by `wrfbdy`.

## 13. Endpoint perturbations in `da_perturb_wrf_bc.ksh`

The script identifies two endpoint times

\[
t_0
\]

and

\[
t_1=t_0+\texttt{LBC\_FREQ}.
\]

At each time it invokes WRFDA in RANDOMCV mode using the unperturbed WRF state at that time as the first guess:

\[
x_m(t_0)=x_b(t_0)+U\xi_{m,0},
\]

\[
x_m(t_1)=x_b(t_1)+U\xi_{m,1}.
\]

The stock script changes the random seed with member and time. Thus the two endpoint perturbations are generally different RANDOMCV realizations rather than a dynamically propagated perturbation trajectory.

## 14. Inputs to `pert_wrf_bc.f90`

The DART boundary utility reads:

```text
wrfinput_this
wrfinput_next
wrfbdy_this
```

where:

- `wrfinput_this` = perturbed state at \(t_0\),
- `wrfinput_next` = perturbed state at \(t_1\),
- `wrfbdy_this` = boundary file whose values and tendencies are modified.

It checks the endpoint and boundary-file times for consistency.

## 15. Boundary variable names

The four boundary directions are:

```text
_BXS   west
_BXE   east
_BYS   south
_BYE   north
```

The corresponding tendencies are:

```text
_BTXS
_BTXE
_BTYS
_BTYE
```

For a generic field \(q\), \(q_{\rm BXS}\) is the west-boundary value while \(q_{\rm BTXS}\) is its west-boundary tendency.

## 16. Example: `MU`

For the west boundary,

\[
MU_{\rm west}^{(0)}=\mathcal B_{\rm west}[MU_m(t_0)],
\]

\[
MU_{\rm west}^{(1)}=\mathcal B_{\rm west}[MU_m(t_1)].
\]

The code calculates

\[
\boxed{MU_{\rm BTXS}=\frac{MU_{\rm west}^{(1)}-MU_{\rm west}^{(0)}}{\Delta t_{\rm LBC}}},
\]

and writes

\[
MU_{\rm BXS}=MU_{\rm west}^{(0)}.
\]

WRF then effectively linearly evolves the boundary between the endpoint values. At

\[
t=t_0+\alpha\Delta t,
\]

\[
MU_b(t)\approx(1-\alpha)MU_b(t_0)+\alpha MU_b(t_1).
\]

## 17. 3-D variables handled by `pert_wrf_bc`

The code processes, if present:

```text
U
V
W
PH
T
QVAPOR
QCLOUD
QRAIN
QICE
QSNOW
QGRAUP
QNICE
```

For `U`, `V`, and `W`, it reads the state plus `MU`, `MUB`, and map factors and calls

```fortran
couple_uvw(...)
```

before extracting boundary slabs.

For scalar-like 3-D variables the code explicitly multiplies by

\[
MU+MUB
\]

before writing the coupled boundary representation:

\[
q_{\rm coupled}=q(MU+MUB).
\]

Thus `pert_wrf_bc` is not simply copying raw `wrfinput` values into `wrfbdy`.

## 18. Boundary-zone extraction

The full lateral boundary relaxation zone is extracted from the perturbed WRF states. For example, on the west side,

\[
q_{\rm BXS}(j,k,l)=q(l,j,k),
\]

where \(l\) indexes distance inward from the boundary. The east, south, and north boundaries are handled analogously.

## 19. Moisture clipping

For moisture variables, the code applies non-negativity at both endpoints before computing tendencies:

\[
q^{(0)}\leftarrow\max(0,q^{(0)}),
\]

\[
q^{(1)}\leftarrow\max(0,q^{(1)}).
\]

Then

\[
\dot q=\frac{q^{(1)}-q^{(0)}}{\Delta t}.
\]

Clipping can therefore slightly alter ensemble means and covariances, especially where hydrometeors are close to zero.

## 20. Temporal structure implied by the stock LBC method

For hourly HRRR forcing,

\[
x_m(t_0)=x_{\rm HRRR}(t_0)+\delta x_m^0,
\]

\[
x_m(t_1)=x_{\rm HRRR}(t_1)+\delta x_m^1.
\]

The member boundary tendency is approximately

\[
\frac{x_m(t_1)-x_m(t_0)}{\Delta t}
=
\frac{x_{\rm HRRR}(t_1)-x_{\rm HRRR}(t_0)}{\Delta t}
+
\frac{\delta x_m^1-\delta x_m^0}{\Delta t}.
\]

Therefore it contains both the deterministic HRRR evolution and the member-specific perturbation tendency.

If \(\delta x_m^0\) and \(\delta x_m^1\) are nearly independent RANDOMCV realizations, then

\[
\frac{\delta x_m^1-\delta x_m^0}{\Delta t}
\]

can be relatively large.

The stock method is therefore approximately

\[
\boxed{\text{new CV3 perturbation at each LBC endpoint} \\ + \\\text{linear interpolation between endpoints}},
\]

not a dynamically propagated perturbation trajectory.

This temporal structure should be explicitly evaluated for the BNF system.

## 21. Recommended BNF IC sequence

1. Generate the unperturbed 2.5-km WRF state from the HRRRv4 analysis.
2. Run WRFDA RANDOMCV/CV3 to generate a perturbation bank, preferably larger than the active 50-member ensemble if practical.
3. Recover perturbations relative to the HRRR-centered WRF state.
4. Remove the finite-sample mean perturbation.
5. Construct the 50 IC members:
   \[
   x_m=x_{\rm HRRR}+\delta x_m^*.
   \]
6. Run several hours of WRF spinup.
7. Diagnose environmental and convective spread.
8. Begin DART/EAKF radar assimilation once sufficient dynamically generated convective spread exists.

## 22. Recommended BNF LBC considerations

At each hourly HRRR boundary time \(t_j\), the simplest stock construction is

\[
x_m(t_j)=x_{\rm HRRR}(t_j)+\delta x_{m,j}^{\rm CV3}.
\]

Before adopting this unchanged, diagnose:

- temporal correlation across successive LBC times,
- magnitude of member-specific boundary tendencies,
- gravity-wave adjustment near the lateral boundaries,
- artificial precipitation near the relaxation zone,
- ensemble-mean preservation after coupling/clipping,
- compatibility with the WRF hybrid vertical coordinate.

It may be preferable to impose temporal coherence on the perturbation sequence rather than using effectively independent CV3 samples at each hourly endpoint.

## 23. Hybrid-coordinate caveat

The standard DART/WRF `pert_wrf_bc` workflow has known limitations with WRF hybrid vertical coordinates. This is directly relevant because the planned BNF configuration uses

```text
hybrid_opt = 2
```

rather than the older terrain-following-only configuration.

The stock workflow should therefore not be adopted without verification or modification. Particular attention should be paid to:

- geopotential / `PH`,
- pressure-related boundary variables,
- near-terrain behavior,
- mass-coupled variable consistency,
- boundary stability.

This remains an implementation gate for the BNF DA system.

## 24. Key distinctions

### Static covariance

\[
B_{\rm CV3}
\]

is the prescribed static covariance used to generate perturbations.

### Initial ensemble covariance

\[
P_0=\frac{1}{N-1}\sum_m(x_m-\bar x)(x_m-\bar x)^T
\]

is the finite-ensemble realization of that covariance.

### Spinup covariance

\[
P_{\rm spinup}
\]

is the covariance after nonlinear WRF evolution.

### DART forecast covariance

\[
P_{\rm DART}^f
\]

is the flow-dependent forecast covariance used by the EAKF.

These quantities should not be treated as interchangeable.

## 25. Compact summary

For ICs,

\[
\boxed{x_m(t_0)=x_{\rm HRRR}(t_0)+B_{\rm CV3}^{1/2}\xi_m}
\]

followed by finite-sample mean centering and WRF spinup.

For an LBC endpoint \(t_j\),

\[
\boxed{x_m(t_j)=x_{\rm HRRR}(t_j)+B_{\rm CV3}^{1/2}\xi_{m,j}},
\]

and `pert_wrf_bc` constructs

\[
\boxed{b_m(t_j)=\mathcal B[x_m(t_j)]},
\]

\[
\boxed{\dot b_m(t_j)=\frac{\mathcal B[x_m(t_{j+1})]-\mathcal B[x_m(t_j)]}{t_{j+1}-t_j}}.
\]

WRF then linearly evolves the boundary between endpoint values.

The overall BNF sequence is

\[
\boxed{
\text{HRRR} \\
\rightarrow
\text{CV3/RANDOMCV perturbations}\\
\rightarrow
\text{50-member WRF ensemble} \\
\rightarrow
\text{WRF spinup} \\
\rightarrow
\text{flow-dependent covariance}\\
\rightarrow
\text{15-min DART radar DA}
}.
\]

## 26. Relevant source-code locations discussed

WRFDA:

```text
var/da/da_main/da_solve.inc
var/da/da_tools/da_set_randomcv.inc
var/da/da_vtox_transforms/da_transform_vtox.inc
scripts/da_perturb_wrf_bc.ksh
```

DART WRF boundary utility:

```text
models/wrf/WRF_BC/pert_wrf_bc.f90
```

These are the principal code paths to inspect when implementing or modifying the IC/LBC perturbation workflow.

## 27. Main implementation questions still open for BNF

1. How should `as1`-`as5` be tuned for the 2.5-km, ~150-level BNF WRF configuration?
2. How much WRF spinup is required before sufficient spread develops in \(w\), hydrometeors, and reflectivity?
3. Should successive hourly LBC perturbations be independent CV3 samples or temporally correlated?
4. How should the stock `pert_wrf_bc` algorithm be modified for `hybrid_opt=2`?
5. How should boundary perturbations be mean-centered after nonlinear coupling and clipping?
6. Which diagnostics should be used to reject amplitudes/correlation scales that generate unrealistic boundary adjustment?

These issues should be resolved before full production cycling.

# 28. Hydrometeor perturbations: what CV3 does and does not perturb

A key clarification is that standard WRFDA CV3 `RANDOMCV` does **not** directly perturb the prognostic hydrometeor mixing ratios.

The conventional CV3 control variables are

\[
\psi,\qquad
\chi_u,\qquad
T_u,\qquad
RH_s,\qquad
P_{s,u}.
\]

Therefore `QVAPOR` is affected through the moisture control variable, but variables such as

```text
QCLOUD
QRAIN
QICE
QSNOW
QGRAUP
```

are not independent CV3 control variables. Immediately after a standard CV3 RANDOMCV perturbation,

\[
\delta q_v \neq 0
\]

in general, while ideally

\[
\delta q_c =
\delta q_r =
\delta q_i =
\delta q_s =
\delta q_g = 0
\]

in the raw `wrfinput` mixing-ratio fields, unless those fields have been modified by some additional procedure.

## Why `pert_wrf_bc` still handles hydrometeors

`pert_wrf_bc` is a generic WRF boundary-construction utility. It processes hydrometeor variables if they exist in the endpoint `wrfinput` and `wrfbdy` files. This does **not** mean that CV3 perturbed them.

For a hydrometeor field such as `QCLOUD`, if RANDOMCV did not modify the raw mixing ratio, then approximately

\[
QCLOUD_m(t_j)=QCLOUD_b(t_j).
\]

However, `pert_wrf_bc` mass-couples scalar variables before writing them to `wrfbdy`:

\[
q_{\rm coupled}=q(MU+MUB).
\]

Because CV3 perturbs `MU`, a hydrometeor boundary field can differ among members even if the underlying mixing ratio does not. For example,

\[
QCLOUD_{{\rm coupled},m}
=
QCLOUD_b\left(MU_b+\delta MU_m+MUB\right),
\]

so

\[
\delta QCLOUD_{\rm mixing\ ratio}=0
\]

but generally

\[
\delta\left[QCLOUD(MU+MUB)\right]\neq0.
\]

This is an **indirect mass-coupling effect**, not a hydrometeor perturbation generated by CV3.

If the endpoint `wrfinput` files have already undergone model integration, hydrometeor fields can of course differ among members dynamically. In that case `pert_wrf_bc` simply carries those dynamically generated differences into the boundary file.

---

# 29. WRFDA hydrometeor control variables and the CV3 limitation

WRFDA contains machinery for hydrometeor control variables through `cloud_cv_options`. For non-CV3 background-error configurations, cloud-control options can add control variables associated with hydrometeor species such as

\[
q_c,\quad q_r,\quad q_i,\quad q_s,\quad q_g.
\]

Internally these correspond to additional control-variable groups (`v6`-`v10`).

However, in the current WRFDA implementation, cloud control variables are not implemented for

```text
cv_options = 3
```

and the code disables them for CV3.

Therefore the following combination cannot be used to obtain native CV3-plus-hydrometeor RANDOMCV perturbations:

```text
cv_options       = 3
cloud_cv_options = 2 or 3
analysis_type    = "randomcv"
```

The practical consequence for BNF is

\[
\boxed{
\text{retain CV3 for environmental perturbations}
\\+\\
\text{add a separate hydrometeor perturbation stage}
}
\]

if explicit hydrometeor spread is desired before WRF spinup.

---

# 30. Separate hydrometeor perturbation operator

A general two-stage ensemble construction can be written as

\[
\boxed{
x_m=x_b+\delta x_m^{\rm CV3}+\delta x_m^{\rm hydro}
}
\]

with

\[
\delta x_m^{\rm CV3}=B_{\rm CV3}^{1/2}\xi_m,
\]

and

\[
\delta x_m^{\rm hydro}
=
\left[
\delta q_c,
\delta q_r,
\delta q_i,
\delta q_s,
\delta q_g
\right]_m.
\]

The hydrometeor perturbation operator should be applied **after** RANDOMCV has produced the environmental perturbation and **before** IC/LBC files are finalized.

---

# 31. Option A: multiplicative hydrometeor perturbations

For each hydrometeor species \(q_h\),

\[
q_{h,m}=q_{h,b}\exp(\epsilon_{h,m}),
\]

where \(\epsilon_{h,m}\) is a spatially correlated random field.

For small perturbations,

\[
q_{h,m}\approx q_{h,b}(1+\epsilon_{h,m}).
\]

Advantages are automatic positivity and perturbation amplitude that scales naturally with existing condensate. The main limitation is that if

\[
q_{h,b}=0,
\]

then

\[
q_{h,m}=0
\]

for every member, so this cannot seed new cloudy or precipitating structures where the background hydrometeor field is exactly zero.

---

# 32. Option B: additive correlated perturbations

One can instead generate

\[
\delta q_h=L_h\xi_h,
\]

where

\[
L_hL_h^T=C_h,
\]

and \(C_h\) is a chosen hydrometeor correlation operator. Then

\[
q_{h,m}=\max\left[0,\,q_{h,b}+\delta q_{h,m}\right].
\]

This can generate spread even where the background field is zero, but clipping makes the distribution non-Gaussian and biased near zero, and unrestricted additive noise can generate physically inconsistent condensate in clear air. Independent perturbations of different species can also destroy realistic phase partitioning.

For those reasons, unrestricted additive perturbations everywhere are not a preferred first implementation for BNF.

---

# 33. Option C: conditionally masked hydrometeor perturbations

A more defensible simple approach is to perturb hydrometeors only where the background state is already cloudy, precipitating, or close to saturation.

Define a mask or weighting function

\[
M(x,y,z)
\]

based on, for example, existing condensate, precipitation, relative humidity, temperature/phase, and possibly reflectivity. Then

\[
q_{h,m}
=
\max\left[0,\,q_{h,b}+M\,\delta q_{h,m}\right].
\]

The mask can be binary or smoothly varying. This allows some additive freedom while avoiding arbitrary condensate generation in very dry clear-air regions.

For the BNF application, this is likely a more useful starting point than completely unconstrained additive perturbations.

---

# 34. Cross-species consistency

Hydrometeor species should probably not be perturbed independently with unrelated random numbers.

For example, rain, snow, and graupel often represent related parts of the same precipitating system. A simple strategy is to generate a common precipitation-amplitude random field

\[
a_m(x,y,z)
\]

and use species-dependent mappings such as

\[
q_{r,m}=q_{r,b}f_r(a_m),
\]

\[
q_{s,m}=q_{s,b}f_s(a_m),
\]

\[
q_{g,m}=q_{g,b}f_g(a_m).
\]

This preserves at least some coherent storm-scale structure and reduces the risk of physically implausible phase partitioning. A more sophisticated version could condition the perturbations on temperature so liquid/ice perturbations remain consistent with the local thermodynamic regime.

---

# 35. Spatial correlation scales for hydrometeor perturbations

Hydrometeor perturbations should not necessarily inherit the broad CV3 correlation scales. CV3 is designed primarily for synoptic/mesoscale environmental errors.

For convective-scale hydrometeors, more appropriate scales may be of order several kilometers horizontally and roughly one to a few kilometers vertically, with exact values tuned empirically.

The appropriate scales should be diagnosed using resulting storm and reflectivity spread rather than chosen solely from the raw hydrometeor fields.

---

# 36. Mean centering for hydrometeor perturbations

If explicit hydrometeor perturbations are added, the same mean-centering principle used for the CV3 ensemble should be considered.

For additive perturbations,

\[
\bar{\delta q_h}
=
\frac{1}{N}\sum_{m=1}^{N}\delta q_{h,m},
\]

and

\[
\delta q_{h,m}^*
=
\delta q_{h,m}-\bar{\delta q_h}.
\]

Then

\[
q_{h,m}=q_{h,b}+\delta q_{h,m}^*.
\]

However, positivity constraints complicate exact mean preservation because clipping can change the sample mean. Therefore

\[
\text{perturb}\rightarrow\text{mean-center}\rightarrow\text{clip}
\]

does not necessarily preserve the mean exactly. The ensemble-mean hydrometeor field should be diagnosed after all constraints are applied.

---

# 37. Application to IC generation

The revised IC workflow is

\[
\text{HRRR}
\rightarrow
\text{HRRR}+\delta x^{\rm CV3}
\rightarrow
\text{HRRR}+\delta x^{\rm CV3}+\delta x^{\rm hydro} \\
\rightarrow
\text{physical constraints}
\rightarrow
\text{WRF spinup}.
\]

For each member,

\[
\boxed{
x_m(t_0)
=
x_{\rm HRRR}(t_0)
+
\delta x_m^{\rm CV3}
+
\delta x_m^{\rm hydro}.
}
\]

The purpose of the explicit hydrometeor term is not to define the final convective covariance, but to avoid starting all ensemble members with identical condensate and reflectivity structures. WRF spinup should then dynamically reorganize both the environmental and hydrometeor perturbations.

---

# 38. Application to LBC generation

If hydrometeor spread is desired in the LBCs, the hydrometeor perturbation stage should be applied to the endpoint `wrfinput` states **before** calling `pert_wrf_bc`.

At boundary time \(t_j\),

\[
x_m(t_j)
=
x_{\rm HRRR}(t_j)
+
\delta x_{m,j}^{\rm CV3}
+
\delta x_{m,j}^{\rm hydro}.
\]

Then `pert_wrf_bc` constructs

\[
b_m(t_j)=\mathcal B[x_m(t_j)],
\]

and

\[
\dot b_m(t_j)
=
\frac{
\mathcal B[x_m(t_{j+1})]
-
\mathcal B[x_m(t_j)]
}{
t_{j+1}-t_j
}.
\]

This means the hydrometeor perturbation algorithm must also address **temporal coherence** between consecutive boundary times. Independent hydrometeor perturbations at successive hourly HRRR times could generate large artificial boundary tendencies, just as independent CV3 endpoint perturbations can.

---

# 39. Reflectivity-space diagnostics

Because the BNF application will assimilate radar reflectivity, hydrometeor perturbations should be evaluated not only in mixing-ratio space but also in observation space.

For each member, compute simulated reflectivity

\[
Z_m=H_Z(x_m),
\]

where \(H_Z\) is the chosen radar-reflectivity observation operator. Then diagnose, for example,

\[
\sigma_Z
=
\sqrt{
\frac{1}{N-1}
\sum_m
\left(Z_m-\bar Z\right)^2
}.
\]

This is important because the relationship between hydrometeor mixing ratios and reflectivity is highly nonlinear. A modest perturbation to rain or graupel can create a much larger relative change in reflectivity than the same fractional perturbation to another species.

Thus the tuning target should be realistic **reflectivity spread**, not merely prescribed \(q_h\) standard deviations.

---

# 40. Updated recommended BNF perturbation architecture

The revised ensemble-generation architecture is

\[
\boxed{
\text{HRRR} \\
\rightarrow
\text{CV3 RANDOMCV environmental perturbations}\\
\rightarrow
\text{explicit hydrometeor perturbation operator} \\
\rightarrow
\text{mean-centering / physical constraints} \\
\rightarrow
\text{50-member IC/LBC ensemble} \\
\rightarrow
\text{WRF spinup} \\
\rightarrow
\text{flow-dependent covariance} \\
\rightarrow
\text{15-min DART radar DA}.
}
\]

The explicit hydrometeor perturbation stage is optional in principle, because WRF spinup can generate hydrometeor spread dynamically from environmental perturbations. However, it may be useful for the BNF radar-DA application if the initial ensemble otherwise has nearly identical convective condensate and reflectivity fields.

The main open design questions are:

- which hydrometeor species should be perturbed,
- multiplicative versus additive/masked perturbations,
- horizontal and vertical correlation scales,
- cross-species correlations,
- phase consistency,
- temporal coherence for LBCs,
- mean preservation after positivity constraints,
- acceptable reflectivity spread after perturbation and spinup.

These should be tested empirically before production use.
