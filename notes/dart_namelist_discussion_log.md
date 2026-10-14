# DART `input.nml` discussion log

A running record of the "help me understand DART's `input.nml`" walkthrough: one entry per
namelist variable or topic discussed, in the order it came up, with cross-references to the
other two notes files and to `initial_plan_from_codex/`. This is the place to look when
refreshing memory on why a namelist value is what it is, or when revising the DA workflow and
wanting to know what was already decided or flagged as open.

Related files:

- `notes/dart_input_nml_comparison.md` — per-block, per-variable diff of `work/input.nml` vs.
  the two WRF-DART tutorial templates.
- `notes/dart_all_namelist_blocks.md` — every namelist block (with all entries) relevant to
  this project, pulled from DART source/`.rst` docs, including blocks not in any of the three
  input.nml files.
- `initial_plan_from_codex/LASSO_BNF_DA_Detailed_Implementation_Plan_rev2.md` — the project plan;
  referenced below by section name since line numbers will drift as it's edited.

Convention: each entry is dated, names the namelist block(s) involved, gives the short answer,
and links sideways to related variables/blocks and to the plan section that bears on it. New
entries get appended at the bottom as the walkthrough continues.

---

## `cutoff` (`&assim_tools_nml`) — 2026-09-22

Horizontal localization half-width, in **radians on the unit sphere** (units used by the
`threed_sphere` location module DART's WRF interface is built on). The EAKF increment multiplier
is 1 at zero distance and reaches exactly 0 at `2*cutoff`; the shape in between is set by
`&cov_cutoff_nml :: select_localization` (Gaspari-Cohn by default).

- `work/input.nml`: `cutoff = 0.05` (~318 km half-width, ~637 km zero-influence — matches the
  file's own comment).
- `template`/`template_nest`: `cutoff = 0.10` (~637 km half-width, ~1274 km zero-influence).
- Both are far broader than the plan's radar target. See **`special_localization_cutoffs`**
  below and the plan's "Conventional localization" section, which cites Dowell et al. Table 5:
  18 km (radar) vs. 300 km (HRRRDAS conventional) horizontal localization for HRRRv4-style
  systems — a reference convention, not a value to paste directly into DART's radian
  half-width/height normalization (unit and full-width-vs-half-width reconciliation is still
  open work).
- Full block: `dart_all_namelist_blocks.md` → "Core assimilation algorithm" → `&assim_tools_nml`.
- Doc source: `assim_tools_mod.rst`.

## `special_localization_obs_types` / `special_localization_cutoffs` (`&assim_tools_nml`) — 2026-09-22

The mechanism for giving individual observation types their own cutoff instead of the single
global `cutoff` above. `special_localization_obs_types` is a list of DART obs-type names (e.g.
`RADAR_REFLECTIVITY`); `special_localization_cutoffs` is a same-length list of per-type cutoff
values in the same radians units as `cutoff`. Types not listed fall back to the plain `cutoff`.
Only implemented for the `threed_sphere` location module (the one this project uses).

- Neither `work/input.nml` nor `template`/`template_nest` sets these — both are absent from all
  three files, so they sit at the DART default (`'null'` / `-888888.0`, i.e. disabled) and
  `cutoff` applies uniformly to every observation type today.
- This is the namelist-level tool for implementing the plan's radar-vs-conventional
  localization split described under `cutoff` above (Dowell et al. Table 5: 18 km radar / 300 km
  conventional) — not yet configured, since the plan's per-type localization design (units,
  full-width-vs-half-width) isn't finalized.
- Same source block as `cutoff`: `assim_tools_mod.rst`, `&assim_tools_nml`.

## `wrf_state_variables` (`&model_nml`): `UPDATE` vs `NO_COPY_BACK`, surface fields — 2026-10-01

Which WRF fields are in DART's state vector and which analyses are written back. Details and code
references in `notes/da_5member_pilot_steps.md`, "Q8: how DART uses the state variables".

- Every state variable is updated by every observation within the localization radius, whatever
  its type (EAKF regression on the observed quantity). MU, PH and PSFC are updated by wind or
  temperature observations too. To restrict this per observation type and state quantity:
  `&assim_tools_nml :: obs_impact_filename` (impact table; not configured).
- 4th column `UPDATE` / `NO_COPY_BACK`: only whether the analysis goes into the member files
  (`output` stage). `NO_COPY_BACK` variables are still updated inside `filter` and appear in the
  `stages_to_write` diagnostic files and in `obs_seq.final` posteriors.
- Surface observations (`SURFACE` vertical coordinate: METAR, marine) use only T2, Q2, U10/V10,
  PSFC (or MU + MUB + p_top). Without T2/Q2/U10/V10 in the state they are rejected (QC 4).
  They shape the 3-D update only through the forward operator (innovation, outlier check,
  regression); WRF rediagnoses them every step, so writing them back doesn't matter.
- DART computes pressure from PH, MU, THM, QVAPOR (never reads WRF's `P`), so PH and MU stay in
  the state even if not written back.
- **Decided (user):** T2, Q2, U10, V10, PSFC in the state with `NO_COPY_BACK` for now, possibly
  `UPDATE` in later tests; hydrometeors to follow HRRRv4, later. Open: MU/PH write-back (surface
  pressure obs can't change column mass without MU), W. Pilot plan Q8.
- Related: `cutoff`, `special_localization_*` above; `wrf_state_bounds` (clamping, applied only
  to the `output` stage); `stages_to_write` (pilot plan Q10).

## `&wrf_obs_preproc_nml` (`wrf_dart_obs_preprocess`): per-cycle screening — 2026-10-02

The WRF-specific observation screening run before `filter`, once per cycle (pilot step 10,
`scripts/da/make_cycle_obs.sh`, namelist in `da_theta_m0/config/input.nml.obs_preprocess`). Full
results in `notes/da_5member_pilot_steps.md`, step 10.

- **No time selection.** The program assumes all its input is valid for one analysis time (given
  on stdin). The 15-min slicing is done beforehand with `obs_sequence_tool` to (t − 450 s, t + 450 s],
  exactly `filter`'s window for `&model_nml :: assimilation_period_seconds = 900`
  (`obs_model_mod.f90`). `overwrite_obs_time = .false.` keeps the real times; the tutorial's `.true.`
  suits its 6-h bins.
- **`obs_boundary = 5`** grid points matches the 1 + 4 boundary zone (`spec_zone`/`relax_zone`,
  pilot Q18); 10 for 1 + 9. The test is asymmetric (5 rows west/south, effectively 6 east/north).
- **`increase_bdy_error = .true.`, `obsdistbdy = 15`, `maxobsfac = 2.5`** (tutorial): the error σ is
  multiplied by up to 2.5 at the edge, falling linearly to 1 at 15 rows (37.5 km); ×2.07 at the
  innermost kept row. Applied to the error variance in the output `obs_seq`, so `filter` and
  `obs_diag` see the inflated value.
- **`sfc_elevation_check = .true.`, `sfc_elevation_tol = 300`** (plan): station elevation vs model
  terrain. Related: `&model_nml :: sfc_elev_max_diff` (−1, off) does a similar check inside `filter`.
- **`obs_pressure_top = 10000` Pa, `obs_height_top = 20000` m** (tutorial; model top 18 hPa).
- **`superob_aircraft = .false.`**: open question Q9, kept open until after the pilot (user,
  2026-10-02). `superob_sat_winds` applies once GOES winds are added (adaptation note 2.13).
- **`include_sig_data = .true.`**: keep radiosonde significant levels, consistent with
  `&convert_madis_rawin_nml` (step 9).
- The program also needs `&model_nml` and `wrfinput_d01` (`static_init_model`, for grid position
  and terrain); the state-variable list is irrelevant here.
- Related: `&obs_kind_nml` (which types `filter` assimilates; step 11), `outlier_threshold`
  (`&filter_nml`), `cutoff`/`special_localization_*` above.


## Filter namelist for the 5-member pilot (`&filter_nml`, `&model_nml`, `&assim_tools_nml`, `&location_nml`) — 2026-10-02

The pilot's `input.nml` for `filter` (step 11): `da_theta_m0/config/input.nml.filter`, one fixed file
for every cycle. Decisions D1–D6 and the gate in `notes/da_5member_pilot_steps.md`, step 11.

- **`wrf_state_variables`** (follows the 2026-10-01 entry above): U, V, THM, QVAPOR, PH, MU `UPDATE`;
  W, T2, Q2, U10, V10, PSFC `NO_COPY_BACK`. W is in the state only to see its increments: in the
  serial EAKF it changes no other variable's update, since no forward operator reads it and inflation
  is per element. The tutorial updates W; drop it for the 50-member cycling if it isn't needed.
  Quantity names from `wrf_state_variables_table` (Q2 is `QTY_VAPOR_MIXING_RATIO`, PSFC
  `QTY_SURFACE_PRESSURE`). PH write-back: DART's own PH unless step 13 shows an imbalance
  (`wrfrst_dart.py insert --hydrostatic-ph`).
- **`cutoff` and `vert_normalization_scale_height`** (follows `cutoff` above): DART's distance
  between an observation and a state element is sqrt(dh² + (dz / vert_normalization)²) radians, dz in
  the `vert_localization_coord` units (4 = scale height, −ln(p/p_sfc) in WRF's `model_mod`); the
  Gaspari-Cohn weight is 1 at 0 and 0 at 2 × `cutoff`. So the normalization is the number of scale
  heights equivalent to 1 radian, the influence region is an ellipsoid, and a pure vertical separation
  reaches 0 at 2 × `cutoff` × normalization. Changing `cutoff` (or a per-type
  `special_localization_cutoffs`) scales the vertical width with it; `special_vert_normalization_*`
  sets it per type. Provisional: 0.0235 and 10.6, HRRRDAS's 300 km and 0.5 scale height as
  zero-influence distances (check the convention in Dowell et al. 2022).
- **Inflation** (`inf_*`): flavor 2 prior, sd 0.6 fixed, no posterior, upper bound 5. `inf_damping`
  is applied once per cycle (λ ← 1 + ρ(λ − 1)), so its time scale depends on the cycle length: the
  tutorial's 0.9 is for 6-h cycles (e-folding ~57 h); every 15 min it is ~2.4 h. Kept at 0.9 for the
  pilot, noted as inherited and untuned; revisit in the extension.
- **`stages_to_write` / `output_members`**: input, preassim, postassim, output; `output_members`
  applies to every listed stage (`filter_mod.f90:2426`), so members are written at all three
  diagnostic stages. Needed for member analyses of the `NO_COPY_BACK` fields.
- **`&obs_kind_nml`**: the 18 types in the step 9 files, all assimilated (ACARS humidity too, relying
  on the outlier check); no evaluate-only types. **`&quality_control_nml`**: `outlier_threshold = 3`;
  `input_qc_threshold = 3` passes all MADIS obs (QC = 1).
- Related: `&fill_inflation_restart_nml` writes the first `input_priorinf_{mean,sd}.nc` from a
  member file; `&ensemble_manager_nml :: tasks_per_node` must match the filter step's ranks per node.

## Inflation sd and `postassim_priorinf` vs `output_priorinf` (`&filter_nml :: inf_*`) — 2026-10-02

Checked in the source after the step 11 gate (`notes/da_5member_pilot_steps.md`, step 11 and Q13).

- **Inflation sd with flavor 2 is fixed at 0.6.** `bayes_cov_inflate` (`adaptive_inflate_mod.f90`)
  leaves the sd unchanged when it equals `inf_sd_lower_bound` (line 863). Above the bound it can only
  shrink (898–899, "Prevent an increase in the sd of lambda"), and `update_inflation` floors it at
  the bound (647–648). Damping (`filter_mod.f90:825–826`) acts on the mean only. `inf_sd_max_change` is
  used only by flavor 5 (Gharamti 2017; lines 960–962), which lets the sd grow by up to that factor
  per observation. Flavor 5 is a candidate for later (user).
- **Next cycle's inflation: `postassim_priorinf_*`.** Nothing touches `PRIOR_INF_COPY` between the
  postassim and output writes (`filter_mod.f90` 936–1108: only posterior inflation, posterior forward
  operators, analysis write, `move_ahead`). The output stage is written with `force_copy = .false.`
  (line 2645; `direct_netcdf_mod.f90:1576`), so it holds only `UPDATE` variables, while diagnostic
  stages use `force_copy = .true.`. Inflation copies are never clamped. So `postassim_priorinf_*` =
  `output_priorinf_*` plus the `NO_COPY_BACK` variables; gate test C showed them identical.

## `inf_damping` and `inf_flavor = 5` in the 1-hour pilot (`&filter_nml :: inf_*`) — 2026-10-03

Quick tests in pilot step 13 (`notes/da_5member_pilot_steps.md`, step 13 and Q13), each a 1-hour run
with hydrostatic PH compared with the same run at `inf_damping = 0.9`, flavor 2. Both are now per-run
settings (`INF_DAMPING`, `INF_FLAVOR` in `config/experiment.sh`, written into each cycle's
`input.nml` by `prep_filter.sh`); `config/input.nml.filter` itself is unchanged. A fuller inflation
test is postponed (user).

- **`inf_damping = 0.9956`** (the tutorial's ~57-h e-folding at 15-min cycles, see the 2026-10-02
  filter entry): inflation keeps more of each gain, and the gap to 0.9 grows every cycle (01:00:
  U domain mean 1.035 vs 1.029). Spread and observation statistics hardly change within an hour;
  the choice needs the extension.
- **`inf_flavor = 5` needs `inf_sd_lower_bound < inf_sd_initial` for its sd to evolve.** Correction
  to the previous entry: flavor 5 lets the sd grow by up to `inf_sd_max_change` per observation, but
  `bayes_cov_inflate` (`adaptive_inflate_mod.f90`, `GHA2017` branch) returns early with the sd
  unchanged when it equals `inf_sd_lower_bound`, exactly like flavor 2. With our 0.6 / 0.6 the sd
  stayed 0.600 everywhere, so the run tested only flavor 5's inverse-gamma update of the mean,
  which gave about half the inflation of flavor 2 (01:00: U mean 1.015, max 2.21 vs 1.029, 2.64)
  and 1–3 % less spread. A floor below 0.6 is still to be chosen (not yet a per-run setting).

## METAR observation errors (converter, not `input.nml`) — 2026-10-03

Not a namelist setting: the MADIS converters set each observation's error from compiled functions
(`obs_error/ncep_obs_err_mod.f90`), and `filter` takes the error variance from `obs_seq.out`.
Recorded here because it changes what `filter` assimilates.

- **Changed (user, 2026-10-03), local patch `patches/dart_7bbd35a09_madis_metar_obs_errors.patch`:**
  METAR T2 2.5 → 1.26 K (NAM), 10-m wind 3.5 → 1.59 m/s (RAP), RH 0.2 → 0.059 (RAP; q error =
  0.059 × q_sat), altimeter 1.0 hPa unchanged. Takes effect from the extension's first cycle (01:15);
  the 1-hour pilot (00:15–01:00) used the old errors.
- **Why:** pilot innovation statistics (consistency ratio 0.11–0.26, implied and Desroziers errors
  2–3× below the assigned ones, close to NCEP's tables). See `notes/obs_expansion.md` Sec. 5.
- **Not changed:** radiosonde, ACARS (statistics suggest ACARS T and q could be somewhat tighter; wind
  is consistent), mesonet (`land_*`, DART defaults; to tune when mesonet is added).
- `wrf_dart_obs_preprocess`'s boundary inflation (`maxobsfac = 2.5`) still multiplies these errors near
  the boundary.

## Mesonet (`LAND_SFC_*`) in `&obs_kind_nml` and the converter errors — 2026-10-13 (proposed)

Profile and full proposal: `notes/obs_expansion.md` Sec. 7. Nothing in `config/input.nml.filter` is
changed yet.

- **Proposed obs types (revised the same day after checking HRRR/RRFS, Sec. 7.3):**
  `LAND_SFC_TEMPERATURE`, `LAND_SFC_SPECIFIC_HUMIDITY`, `LAND_SFC_U_WIND_COMPONENT` and
  `LAND_SFC_V_WIND_COMPONENT` in `assimilate_these_obs_types`, after provider/station selection
  (options (a) P1 + S2, (b1) P4 + S1, (c) P4; (a) for the first tests, user 2026-10-13;
  `mesonet_station_selection.md` Sec. 5), with calm winds kept by default (a switch can drop them;
  DART itself can't); `LAND_SFC_ALTIMETER` in `evaluate_these_obs_types`
  (prior/posterior H(x) in `obs_seq.final`, no update). First version had wind evaluate-only too;
  kept as the alternative. All are compiled into our `filter` (Sec. 2).
- **Localization:** the conventional `cutoff = 0.0235` for these too (no `special_localization_*`
  entry), as HRRRDAS uses one conventional pass.
- **Errors (converter, not namelist):** RAP effective mesonet values T 3.0 K, q 7 % RH, wind
  3.0 m/s, altimeter 1.0 hPa, by patching the `land_*` functions, which only `convert_madis_mesonet`
  uses among our converters. Alternative: DART's defaults (2.5 K, RH 0.2, 3.5 m/s, 1.0 hPa).
- **Per-station selection** (one report per station per cycle, METAR duplicates dropped) is a
  preprocessing step, not a DART setting: DART has no surface thinning.

## Mesonet observation errors (converter, not `input.nml`) — 2026-10-14

Like the METAR errors (2026-10-03 entry), set by the converter's compiled functions, not by a namelist;
`filter` takes the error variance from `obs_seq.out`.

- **Changed (user, 2026-10-14), local patch `patches/dart_7bbd35a09_madis_mesonet_obs_errors.patch`:**
  the `land_*` functions in `ncep_obs_err_mod.f90`, used only by `convert_madis_mesonet` among our
  converters: T 2.5 → 3.0 K, 10-m wind 3.5 → 3.0 m/s, RH 0.2 → 0.07 (q error = 0.07 × q_sat), altimeter
  1.0 hPa unchanged. These are the RAP/RRFS v1 values: NCEP table type 188/288 (4.0 K, 7 %, 3.0 m/s,
  0.54 hPa) clipped to the `convinfo` bounds (T ≤ 3.0 K, pressure ≥ 1.0 hPa).
- **Why not our METAR values:** NAM, RAP and RRFS all give mesonet larger errors than METAR (T 4.0 vs
  2.26 K in RAP/RRFS, wind 3.0 vs 1.59 m/s, q 7 vs 5.9 % RH), and RAP, RRFS v1 and RRFS v2 keep the
  difference. Our METAR T (1.26 K, NAM) came from the pilot's METAR statistics; mesonet has none yet.
  Check against mesonet innovation statistics once it is assimilated.
- `wrf_dart_obs_preprocess`'s boundary inflation (`maxobsfac = 2.5`) still multiplies these errors near
  the boundary. RRFS v2's per-observation error inflation (pressure check, quality marker) has no DART
  counterpart here.
- Details: `notes/obs_expansion.md` Sec. 7.2 item 4.

## MRMS reflectivity: `&obs_def_radar_mod_nml`, error, localization — 2026-10-14 (nothing changed yet)

Came up while making the first MRMS `obs_seq` (`notes/obs_expansion.md` Sec. 8).

- **`microphysics_type`**: `input.nml.filter` has the default 2. `get_expected_radar_ref` always tries
  `QTY_RADAR_REFLECTIVITY` (state `REFL_10CM`) first; if that fails, 1/2 silently fall back to a Lin-type
  Z from qr/qs/qg (not Thompson-consistent), while 3/5 stop with a message. Proposed: **5**, set when
  `REFL_10CM` goes into the state (Sec. 8.4 step 5).
- **`apply_ref_limit_to_fwd_op`** (now `.false.`): `REFL_10CM` reaches −35 dBZ in clear air (Thompson floor) while the
  clear-air obs are −10 dBZ. Checked 2026-10-14: HRRRDAS's GSI observer floors H(x) at `static_gsi_nopcp_dbz = -10`
  (`setupdbz.f90:441`, EnKF runs) and the obs at −10 (`read_dbz_nc.f90:372`). Proposed: `apply_ref_limit_to_fwd_op = .true.`,
  `reflectivity_limit_fwd_op = -10.0`, `lowest_reflectivity_fwd_op = -10.0` (same floor). With it, clear-air obs act only
  where members have echo above −10 dBZ. Not changed yet (`notes/obs_expansion.md` Sec. 8.3).
- **Observation error**: 5 dBZ for both types, as HRRRDAS; set by the converter
  (`scripts/da/mrms_to_obs_seq.py --dbz-error-sd`), not by a namelist.
- **Localization / impact**: HRRRDAS's separate pass, 18-km zero influence → `cutoff` ≈ 0.00141 for
  `RADAR_REFLECTIVITY` and `RADAR_CLEARAIR_REFLECTIVITY` via `special_localization_obs_types`; which
  quantities they update (`obs_impact_tool`) or a second `filter` call. Open (Sec. 8.4 step 6).

## Mesonet wired in: `&obs_kind_nml` types; `&wrf_obs_preproc_nml` duplicate-location test under `r8 = r4` — 2026-10-14

Follows the 2026-10-13 proposal above (`notes/obs_expansion.md` Sec. 7.2, "Wired in").

- **`&obs_kind_nml` (changed, `config/input.nml.filter`):** `LAND_SFC_U_WIND_COMPONENT`, `LAND_SFC_V_WIND_COMPONENT`,
  `LAND_SFC_TEMPERATURE`, `LAND_SFC_SPECIFIC_HUMIDITY` added to `assimilate_these_obs_types`;
  `evaluate_these_obs_types = 'LAND_SFC_ALTIMETER'` (was empty). Nothing else changed: same `cutoff`, no special
  localization. Runs on observation sets without mesonet (`obs/` of step 13) are unaffected.
- **Found: `wrf_dart_obs_preprocess` drops METAR reports near mesonet sites.** `add_supplimental_obs` adds
  `land_sfc_extra` before `metar_extra` (both into the surface sequence) and skips a report whose location is a
  duplicate of one already there (`original_observation`: horizontal `get_dist` <= 1e-5 rad, ~60 m), for all its
  variables, whatever the times. Our DART has `r8 = r4` (`patches/dart_7bbd35a09_types_mod_r8_as_r4.patch`), so
  `get_dist` is float32 `acos` of a sum of sin/cos products: the value next below 1.0 gives 3.45e-4 rad (2.2 km),
  and the products' rounding (~1e-7) blurs the edge. Simulated (2 million pairs at 29–41 N): "duplicate" for ~90 %
  of pairs within 1.25 km, 52 % at 1.5–1.75 km, 20 % at 2.25–2.5 km, 2 % at 3–3.25 km, none beyond 3.7 km. Seen:
  00:15 lost 4 of 139 METAR stations, 01:00 lost 16 of 315, to mesonet sites 0.4–2.5 km away.
- **Decided (user, 2026-10-14): METAR takes precedence, per window.** `select_mesonet_cycle.py` drops mesonet sites
  within 4 km (`--metar-radius-km`, covers the whole band above) of a METAR report of the same cycle window, taken
  from the converted hourly METAR `obs_seq` files, i.e. the reports the preprocessor sees. The hourly METAR-ID check
  stays. Result: METAR counts after screening identical to the MADIS-only set in all four pilot cycles; 10–113 of
  ~2,450 mesonet sites dropped per cycle (113 at 01:00, when the hourly METARs fall in the window; per-variable
  counts in `obs_expansion.md` Sec. 7.2).
- **Wider note:** with `r8 = r4`, every DART great-circle distance below ~2 km is unreliable (0 or ~2.2 km). Harmless
  for localization (weights ~1 there), but any "same location" test in DART tools is effectively a ~2-km test.
  Marine reports are added before land surface too, so mesonet near a marine report would be dropped; none in our domain.
