# Lateral boundary fields for the DA runs: what WRF uses and what the DART tools must refit

Written 2026-09-30 while reviewing step 2 of `da_5member_pilot_steps.md` (DART boundary-tool patches). It records what our HRRR-based `wrfbdy_d01` contains, how WRF uses each group of boundary fields, and what that means for `update_wrf_bc` / `pert_wrf_bc` in 15-min cycling. It refines 2.6, 2.7 and 2.12 of `wrf_dart_tutorial_adaptation.md`.

Code references: WRF = `../software/WRF` (commit `06d4240a`), DART = `../software/DART/models/wrf/WRF_BC/` (v11.25.3). Files checked: `cases/20250520/da_theta_m0/mean/wrfinput_d01_2025-05-20_00_00_00` and `mean/wrfbdy_d01` (a link to `theta_m0/real/wrfbdy_d01`, the file the `theta_m0` free run used).

## 1. What our files contain (verified)

**`wrfinput` (05-20 00Z): HRRR hydrometeors are present.**

| Field | max | nonzero points |
|---|---|---|
| QCLOUD | 3.97e-3 kg/kg | 511,405 |
| QRAIN | 5.89e-3 | 2,190,109 |
| QSNOW | 5.72e-3 | 2,300,847 |
| QGRAUP | 1.11e-2 | 673,655 |
| QICE | **0** | **0** |
| QNICE | 1.65e6 /kg | 1,502,685 |
| QNRAIN, QNCLOUD | nonzero | |
| QNWFA, QNIFA, QNBCA | nonzero at every point | |

Side finding: `QICE` is zero everywhere while `QNICE` is not. The `met_em` files carry `QC QR QS QG QNI QNC QNR QNWFA QNIFA` but no `QI`, so HRRR cloud ice doesn't come through our WPS setup (`cases/20250520/wps/Vtable`). All three free runs started this way. Not pursued yet.

**`wrfbdy_d01` (all 72 records, all four sides):**

| Boundary field | `B` and tendency |
|---|---|
| `QCLOUD QRAIN QICE QSNOW QGRAUP QNICE QNRAIN QNCLOUD` | exactly 0 |
| `HT_SHAD`, `PC` | exactly 0 |
| `QVAPOR` | nonzero |
| `QNWFA`, `QNIFA`, `QNBCA` | nonzero |
| `LIGHTNING_*` | not checked (don't matter for us) |
| `U V W PH T MU` | not checked here (the dynamics fields) |

Why the hydrometeor boundaries are zero: `real.exe` computes moisture boundaries only for `QVAPOR`. Every `stuff_bdy` call on `moist` in `main/real_em.F` is for `P_QV` (e.g. lines 956, 1374), and the other species' arrays are written as zeros. That's standard WRF behavior, not specific to HRRR input.

`HT_SHAD` is the height of the orographic shadow (`Registry.EM_COMMON:1427`), used only with `topo_shading`, which we don't set (default 0). `PC` is the perturbation dry-air column mass of the hybrid coordinate (`registry.hyb_coord:56`); no WRF Fortran code reads `pc_1`, `pc_2` or `pc_bxs`. Neither matters.

## 2. How WRF uses these boundary fields (verified, `dyn_em/solve_em.F`)

**Hydrometeor masses (`moist` array).** Lines 2311–2345 (`relax_bdy_scalar`, `spec_bdy_scalar`) and 4793–4810 (`spec_bdy_final`) take the boundary from `wrfbdy` if

```fortran
im .EQ. P_QV .OR. config_flags%nested .OR. ( config_flags%specified .AND. config_flags%have_bcs_moist )
```

Otherwise (line 2498) every species except `QVAPOR` gets `flow_dep_bdy`.

**Number concentrations and aerosols (`scalar` array: `QNRAIN QNCLOUD QNICE QNWFA QNIFA QNBCA`).** Lines 2964–2967 take the boundary from `wrfbdy` if

`nested` **or** (`specified` **and** `have_bcs_scalar`) **or** (field is `QNWFA`/`QNIFA`/`QNBCA` **and** `aer_init_opt > 0`).

Lines 3065–3069 use `flow_dep_bdy` if (aerosol **and** `aer_init_opt = 0`) **or** (not aerosol **and not** `have_bcs_scalar`). The code comments include the truth table. `spec_bdy_final` for scalars (4862–4882) runs only for nested domains.

**`aer_init_opt`** is derived, not a namelist entry (`share/module_check_a_mundo.F:2533–2544`): for `mp_physics = 28`, `use_aero_icbc = .true.` gives 1 (climatological aerosol IC/BC) and `use_rap_aero_icbc = .true.` gives 2. All our runs set `use_aero_icbc = .true.`, so `aer_init_opt = 1`.

**`flow_dep_bdy`** (`share/module_bc.F:2335`): on the outermost row only (`spec_zone = 1`), inflow points are set to 0 and outflow points copy the first interior value (zero gradient). There's no relaxation zone.

**Our namelists** (`baseline`, `hybrid2`, `theta_m0`, lines 112–113; copied from sey's setup): `have_bcs_moist = .true.`, `have_bcs_scalar = .true.`, `spec_bdy_width = 10`.

**Consequences:**
- **Free runs:** all hydrometeor masses and numbers were forced to the file's zeros. The outer row was set to 0, and rows 2–10 were relaxed toward 0, both inflow and outflow.
- **Aerosols:** with `aer_init_opt = 1` they always come from `wrfbdy`, whatever `have_bcs_scalar` is set to.
- **The two flags must be set together.** With only `have_bcs_moist = .false.`, masses would flow out freely while their numbers are still forced to 0.

## 3. What this means for the DART boundary tools in 15-min cycling

`update_wrf_bc` and `pert_wrf_bc` refit 12 3-D fields (`U V W PH T QVAPOR QCLOUD QRAIN QICE QSNOW QGRAUP QNICE`) plus `MU`: `B` is set to the member state and the tendency is recomputed toward the record-end target.

**(1) Fields the tools don't refit: the mid-record lag (2.6).** When a segment starts partway through an hourly record, `update_wrf_bc` moves the record's start time (shared by all fields) but leaves `B` and the tendency of unlisted fields at their 00:00 values. WRF then reads those fields 15, 30 or 45 min late, as a sawtooth: each segment restarts from the hour's starting value. Of the unlisted fields, only `QNWFA`, `QNIFA` and `QNBCA` have nonzero boundary values. `QNRAIN` and `QNCLOUD` are zero, `HT_SHAD` and `PC` are zero and unused, and `LIGHTNING_*` doesn't matter. **So with `have_bcs_* = .true.`, the lag fix is needed only for the three aerosol numbers.** The fix moves `B` forward along the original line, `B + tend × (new start − old start)`, keeping the tendency. The effect is small, since aerosols change slowly, but the fix is simple and exact.

**(2) Hydrometeor masses the tools do refit (new finding).** This is a separate issue from (1). With the stock tools:
- **`update_wrf_bc`** sets `B` for `QCLOUD`…`QNICE` to the member's own values at the segment start, and the record-end target recovered from the untouched record is 0. Boundary hydrometeors would ramp from the member value to 0 over the rest of the hour. The free runs had 0 throughout.
- **`pert_wrf_bc`** (building member files, step 6) reads the hydrometeors from both hourly `wrfinput` states, which carry HRRR clouds. The member files would get nonzero, time-varying hydrometeor boundaries.
- **The numbers stay 0.** `QNRAIN` and `QNCLOUD` aren't in either tool's list, so the boundary zone would get rain and cloud mass with zero number. With `have_bcs_* = .true.`, WRF would impose that.

Options (decided 2026-09-30: (a); see Sec. 5):
- **(a) Keep `have_bcs_* = .true.`,** identical to the free runs, and patch both tools to stop refitting `QCLOUD QRAIN QICE QSNOW QGRAUP QNICE`, so these stay at the file's zeros.
- **(b) Set `have_bcs_moist = have_bcs_scalar = .false.`** in the DA runs. WRF then ignores whatever the tools write for hydrometeors and numbers and uses `flow_dep_bdy` (0 on inflow, zero gradient on outflow, no relaxation zone). The aerosols still come from `wrfbdy`. This needs no hydrometeor patch, but it differs from the free runs at the boundary.

Either way the aerosol lag fix in (1) still applies.

## 4. `T` versus `THM` (correction to 2.7)

The `THM` patch is not a one-line change. In both tools, `var3d(n)` is used both to read the model field (`get_var_3d_real_cdf(..., var3d(n), ...)`) and to build the boundary names (`var_name = trim(var3d(n)) // trim(bdyname(m))` → `T_BXS`, `T_BTXS`, …; `update_wrf_bc.f90` lines 453–516, `pert_wrf_bc.f90` 436–567). Setting `var3d(5) = 'THM'` would look for `THM_BXS`, which doesn't exist. A patch needs a separate "read from" name.

For the `theta_m0` pilot the patch isn't needed if every file we write keeps `T = THM`: initial members (step 5), the temporary states for `pert_wrf_bc` (step 6), and the member files after each `filter` update (step 12). It becomes necessary with `use_theta_m = 1`.

## 5. Decisions and status

**Decision (user, 2026-09-30): option (a), for simplicity.** Keep `have_bcs_moist = have_bcs_scalar = .true.` as in the free runs, and patch both tools to stop refitting the six hydrometeors. Together with the aerosol shift, the patch is `patches/dart_7bbd35a09_wrf_bc_hydrometeors_aerosol_shift.patch` (README entry there):
- both tools: `nmoist = 1` (only `QVAPOR` refitted among the moisture fields);
- `update_wrf_bc`: `B` of `QNWFA`, `QNIFA` and `QNBCA` moved forward along the tendency to the segment start.

Result: in the DA runs, the hydrometeor masses and numbers have zero boundaries throughout, as in the free runs, so there's no mass/number mismatch. The six hydrometeors now count as unrefitted fields, but their `B` and tendency are zero, so the record-time shift doesn't affect them. Members keep their own hydrometeors in the interior; only the 10-row boundary zone is driven to zero.

**Revisit later.** Zero hydrometeor boundaries with `have_bcs_* = .true.` is a choice inherited from sey's setup, kept so the DA runs match the free runs. It removes cloud and precipitation at the edge on outflow as well as inflow. We may want to revisit it later, for example by setting both flags `.false.` (option (b), flow-dependent hydrometeor boundaries) in all runs, or by supplying real boundary hydrometeors. The patch should then be reconsidered.

**Status:**
- **Done:** source edited in `../software/DART/models/wrf/WRF_BC/`.
- **Not yet:** compiled or tested. Test in pilot step 8.
- **Still open:** whether to patch for `THM` now or keep the `T = THM` rule until `use_theta_m = 1` (Sec. 4; for now, the rule), and the missing `QICE` in the initial state (Sec. 1).
