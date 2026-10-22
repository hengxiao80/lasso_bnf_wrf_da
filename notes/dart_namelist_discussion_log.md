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

## Two-pass filter for MRMS: `config/input.nml.filter_mrms`, state, inflation, radar operator — 2026-10-14

Follows the entry "MRMS reflectivity ... (nothing changed yet)" above; design in `notes/obs_expansion.md` Sec. 8.4.

- **Decided (user, 2026-10-14): two filter passes per cycle, as HRRRDAS** (Dowell 2020 pp. 5–6;
  `scripts/hrrrdas/exhrrr_analysis.sh`, `exhrrr_enkf.sh`): conventional obs first, then MRMS on the result. HRRRDAS
  computes every H(x), radar ones too, once from the background (GSI observer per member) and never updates
  reflectivity, so its radar pass regresses the conventional analysis on background-reflectivity priors. Ours does
  the same: `REFL_10CM` is `NO_COPY_BACK` in both passes, so the MRMS pass reads the background's.
- **First pass, `input.nml.filter` (changed):** `QCLOUD` added as `UPDATE` (HRRRDAS's conventional pass analyses
  U, V, T, QVAPOR, QCLOUD), and `QRAIN`, `QSNOW`, `QGRAUP`, `REFL_10CM` as `NO_COPY_BACK`, so both passes have the
  same variables (needed if inflation is passed between them). `wrf_state_bounds` 0 / `CLAMP` for the four
  hydrometeors. This is also the conventional pass of runs without MRMS (the new `_madis` reference), so a run with
  MRMS differs from its reference only by the second pass. It needs restarts with `REFL_10CM` (patched `wrf.exe`), so
  the step 13 runs (`run*/`) can't be resumed with it.
- **Second pass, `input.nml.filter_mrms` (new):** a copy of the first pass's file with
  - `assimilate_these_obs_types = 'RADAR_REFLECTIVITY', 'RADAR_CLEARAIR_REFLECTIVITY'`, from `obs_seq.mrms`;
  - `UPDATE` U V THM QVAPOR QCLOUD QRAIN QSNOW QGRAUP (HRRRDAS's radar pass); PH, MU, W `NO_COPY_BACK`;
  - `cutoff = 0.001413` (18 km zero influence) and `vert_normalization_scale_height = 177.0`, which keeps the
    vertical zero at 0.5 scale height (2 × 0.001413 × 177 = 0.5). A pass holds one obs family, so these are the
    global values; no `special_localization_obs_types`;
  - inflation as set by `MRMS_INFLATION` (below); `print_every_nth_obs = 10000`.
- **`&obs_def_radar_mod_nml` (changed, both files):** `microphysics_type = 5` (H(x) = state `REFL_10CM`; if it can't
  be interpolated the obs fails, with no Lin-type fallback). `apply_ref_limit_to_fwd_op = .true.` with the −10 dBZ
  limit and value (HRRRDAS's H(x) floor).
- **QNRAIN (decided, user 2026-10-14):** not in the state; after the MRMS pass `wrfrst_dart.py qnrain` resets it
  wherever QRAIN changed, with Thompson's own rule for rain without a number: exponential, median volume diameter
  1 mm. The other two rules (fixed N0 = 8e6 m⁻⁴; keep the prior mean size) are documented in `obs_expansion.md`
  Sec. 8.4 for later.
- **Inflation in the MRMS pass: open (user researching).** `MRMS_INFLATION` has no default and must be given for a
  two-pass run (`driver.sh` refuses otherwise): `pass1` = no inflation in the MRMS pass (`inf_flavor = 0`, as in the
  file); `both` = the MRMS pass reads the first pass's updated inflation with `inf_damping = 1.0`, applies and
  updates it, and the next cycle starts from the MRMS pass's. DART's prior inflation applies to the whole state, so
  `both` inflates the spread twice per cycle, not only near radar obs.
- **Lateral boundary for MRMS (decided, user 2026-10-14):** the converter copies `wrf_dart_obs_preprocess`'s
  `obs_boundary = 5` trim and `increase_bdy_error` (`obsdistbdy = 15`, `maxobsfac = 2.5`) exactly (checked:
  variances 107.3 dBZ² at the first kept row down to 25 at 15 points).
- **Not yet considered: `&quality_control_nml outlier_threshold = 3`** applies to the radar obs too. A 40-dBZ ob where
  every member is clear (−10 after the floor) has |innovation| = 50 against sqrt(25 + 0) = 5, so it is rejected;
  but zero H(x) spread means it could do nothing anyway. Where spread is small but non-zero, the 3-sigma test may reject
  the obs that would start convection. Look at the DART QC counts of the first MRMS cycle before changing it.

## One-pass MRMS alternative: `config/input.nml.filter_joint`, impact table, per-type localization — 2026-10-14

Asked for by the user after the two-pass entry above; details in `notes/obs_expansion.md` Sec. 8.5. A run on an MRMS
observation set now chooses `MRMS_FILTER = two_pass | one_pass` (no default).

- **`input.nml.filter_joint` (new):** `input.nml.filter` + `RADAR_REFLECTIVITY`, `RADAR_CLEARAIR_REFLECTIVITY` assimilated
  (from `obs_seq.joint`); QRAIN QSNOW QGRAUP `UPDATE`.
- **`&assim_tools_nml`:** `special_localization_obs_types = 'RADAR_REFLECTIVITY', 'RADAR_CLEARAIR_REFLECTIVITY'`,
  `special_localization_cutoffs = 0.001413, 0.001413`; `adjust_obs_impact = .true.`, `obs_impact_filename =
  'obs_impact_joint.txt'`, `allow_any_impact_values = .false.` (factors 0 or 1 only).
- **`&location_nml`:** `special_vert_normalization_obs_types` = the radar types with `_scale_heights = 177.0` (the other
  three at the global values), so their vertical zero is 0.5 scale height with their own cutoff; conventional obs
  keep 10.6 with 0.0235.
- **Impact table (`config/obs_impact_joint.txt`):** radar → MU, PH, PSFC, W quantities 0; conventional → QRAIN, QSNOW,
  QGRAUP and `QTY_RADAR_REFLECTIVITY` 0. The last one is a choice: 0 keeps the radar priors at the background (as
  HRRRDAS and our two-pass); 1 would let conventional obs update them.
- **Inflation:** one adaptive prior inflation, as the first pass; `MRMS_INFLATION` not used.

## Damping in the second (MRMS) pass under `MRMS_INFLATION = both` — 2026-10-15

- **Decided (user, 2026-10-15): a switch, `MRMS_PASS2_DAMPING`, default 1 (on).** With `MRMS_INFLATION = both`,
  `prep_filter.sh mrms` sets pass 2's `inf_damping` to `INF_DAMPING` (1) or 1.0 (0); before, it was always 1.0. With
  the default the inflation read from pass 1 is damped again before pass 2 applies it, i.e. twice per cycle,
  effectively `INF_DAMPING`² per 15-min cycle (0.81 for 0.9, an e-folding time of ~1.2 h instead of ~2.4 h). Ignored
  for `MRMS_INFLATION = pass1` and one-pass runs; `driver.sh` records it in `settings.txt` for `both`.

## Inflation for the MRMS runs: damping, flavor 5 with an evolving sd (`&filter_nml :: inf_*`) — 2026-10-15

Raised by the user as candidates to try, alongside `MRMS_INFLATION` (pass1 | both, still open).

- **`inf_damping`:** still 0.9 per 15-min cycle by default (tutorial value for 6-h cycles; e-folding ~2.4 h instead of
  ~57 h; 0.9956 matches the tutorial's time scale). Already a per-run setting (`INF_DAMPING`); the 1-hour pilot's
  `_hph_d9956` run is the only test so far (2026-10-03 entry above).
- **Flavor 5 with an evolving sd: new per-run setting `INF_SD_LOWER_BOUND`** (`experiment.sh`, default 0.6 = no
  change). `prep_filter.sh` writes it into the first column of `inf_sd_lower_bound` of every pass that inflates
  (conv; mrms under `both`; joint); `driver.sh` accepts 0 < value <= 0.6 and records it in `settings.txt` when not 0.6.
  The initial sd stays 0.6 (`fill_inflation_restart`), so with a bound below 0.6 the sd can evolve: with flavor 5 it
  can grow or shrink, with flavor 2 only shrink. In `bayes_cov_inflate` (GHA2017 branch) an sd update larger than
  `inf_sd_max_change` (1.05) times the old sd is skipped (the old sd kept), not clipped, and this is per observation.
  No value chosen yet (DART's guide: smaller bounds make the inflation vary more slowly; it recommends 0.6 / 0.6 for
  large models). DART's guide also recommends `inf_lower_bound = 0` for flavor 5 (deflation allowed); ours stays 1.0.

## Same state-variable list in both MRMS passes, even with `MRMS_INFLATION = pass1` — 2026-10-15

Follows the two-pass entry (2026-10-14) and `notes/obs_expansion.md` Sec. 8.4.

- `input.nml.filter`, `input.nml.filter_mrms` and `input.nml.filter_joint` list the same 17 variables; only the
  `UPDATE`/`NO_COPY_BACK` flags differ (pass 1: PH, MU `UPDATE`, QRAIN QSNOW QGRAUP `NO_COPY_BACK`; pass 2 the
  reverse; joint: all of them `UPDATE`).
- The identical list is **required only with `MRMS_INFLATION = both`**: DART's adaptive inflation files hold one
  field per state variable, and pass 2 reads and updates pass 1's. With `pass1`, pass 2 doesn't inflate and could
  list other variables (each pass reads only its listed fields from the same member files and writes back only its
  `UPDATE` ones).
- **Decided (user, 2026-10-15): keep the lists the same anyway**, also with `pass1` and in one-pass runs, so the
  inflation choice stays open and every run's conventional pass is the same.
- Comments made precise in all three files. The `&model_nml` comment blocks of `input.nml.filter_mrms` and
  `input.nml.filter_joint` had been copied unchanged from pass 1 and gave pass 1's flags; rewritten to give each file's
  own (the namelist values themselves were right).

## Filter layout 40 × 32 (`&ensemble_manager_nml :: tasks_per_node`) and the filter exit hang — 2026-10-20

Details and numbers: `notes/obs_expansion.md` Sec. 9 (scaling test).

- **Rank count doesn't change the analysis.** Step 13's 00:30 conventional analysis replayed at 8 × 16, 40 × 16 and
  40 × 32 ranks (`layout = 2`, `tasks_per_node` = ranks per node): member analyses bit-identical to each other and to
  step 13's. The observation loop: 97, 18, 10 s (27.8, 5.2, 2.9 ms per ob); memory 1.70, 0.51, 0.50 GB per rank.
- **Decided (user, 2026-10-20): 40 × 32 for runs 1–4.** `tasks_per_node = 16` stays in the three namelists as the
  placeholder `prep_filter.sh` replaces with `FILTER_TASKS_PER_NODE` (32).
- **Not changed:** `&location_nml` `nlon`/`nlat` (71 × 36); the MRMS scaling test will compare ×4 (283 × 144) for the
  radar pass, whose 18-km cutoff searches ~3 × 3 of the current ~19 × 27-km boxes.
- **Exit hang:** filter hung after "Finished" on runs that included 512-GB nodes; those nodes are excluded, and
  `run_filter` cancels a step still running 30 s after "Finished" (no output change for 30 s).

## Radar pass: search boxes (`&location_nml :: nlon, nlat`) and the outlier check (`&quality_control_nml`) — 2026-10-21

Numbers: `notes/obs_expansion.md` Sec. 9 (MRMS scaling test, job 1054799).

- **Boxes:** DART's boxes are longitude × latitude and span the searched locations plus 2 × cutoff on each side
  (`find_box_ranges`), so at 71 × 36 they are ~21 × 29 km for the radar pass and ~29 × 44 km for the conventional
  pass (the 2026-10-20 entry's "~19 × 27 km" left out the margin). 283 × 144 made the MRMS pass's observation loop
  26 % faster (19 → 14 s at 40 × 32) with bit-identical analyses. Proposed for `input.nml.filter_mrms` and
  `input.nml.filter_joint` (in the latter it applies to the conventional obs too, harmlessly); `input.nml.filter`
  unchanged. **Decided (user, 2026-10-21): 283 × 144 in both files** (done).
- **Outlier check:** `outlier_threshold = 3` rejected 32 % of `RADAR_REFLECTIVITY` (24,688 of 76,962) at 00:15:
  almost all observed weak-to-moderate echo (median 14.7 dBZ) where the members are clear (prior mean median −9 dBZ;
  44 % with zero spread); 2 % of the clear-air obs. HRRRDAS's EnKF has no such check (`sprd_tol = 1.e30`). Options:
  keep 3 for all; a separate threshold (or none, `-1`) in `input.nml.filter_mrms` for two-pass runs; per-type
  thresholds in a one-pass run need `enable_special_outlier_code` and code in `quality_control_mod.f90`
  (`failed_outlier`). **Decided (user, 2026-10-21): keep 3 for all types in runs 3–4** (no code change, the one- and
  two-pass runs stay comparable, most rejected obs have zero spread and couldn't act); watch the radar QC-7 fraction
  over the cycles; radar threshold off or ~5 as a later variant.
- **Also decided (user, 2026-10-21):** run 4 uses `MRMS_INFLATION = both` (details when it comes up); the impact
  table keeps conventional → `QTY_RADAR_REFLECTIVITY` at 0, as HRRRDAS.

## Run 4 (two-pass MRMS): pass-2 damping on (`MRMS_PASS2_DAMPING = 1`) — 2026-10-21

- **Decided (user, 2026-10-21):** run 4 uses `MRMS_INFLATION = both` with the default `MRMS_PASS2_DAMPING = 1`: the
  MRMS pass damps the inflation it reads from the conventional pass with `inf_damping = 0.9` again (2026-10-15 entry),
  so it is damped twice per cycle (0.81, e-folding ~1.2 h), which partly offsets inflating the spread twice per
  cycle. Everything else as in runs 1–3 (`inf_flavor` 2, `inf_damping` 0.9, `inf_sd_lower_bound` 0.6), so that run 4
  differs from run 3 only in one pass against two. `MRMS_PASS2_DAMPING = 0`, `MRMS_INFLATION = pass1`, 0.9956 and
  flavor 5 with an evolving sd remain candidates for the inflation tests after run 4.

- **Found in run 4 (2026-10-21): the MRMS pass lets radar obs adapt the inflation of MU, PH, W and PSFC**
  (`notes/obs_expansion.md` Sec. 9, run 4). `NO_COPY_BACK` in `input.nml.filter_mrms` only stops those fields'
  increments from being written back; DART still updates them and their inflation. In the one-pass run the impact
  table's zeros (radar → `QTY_PRESSURE`, `QTY_GEOPOTENTIAL_HEIGHT`, `QTY_SURFACE_PRESSURE`, `QTY_VERTICAL_VELOCITY`)
  skip both (`assim_tools_mod.f90:784-798`). Under `MRMS_INFLATION = both` the radar-adapted MU inflation reaches the
  model through the next cycle's conventional pass (MU max 3.96 at 01:00 against 2.66 in run 3). **Proposed, not
  made:** `&assim_tools_nml` `adjust_obs_impact = .true.` with a table of the 8 radar rows of `obs_impact_joint.txt` in
  `input.nml.filter_mrms`; expected to leave the copied-back fields' analyses bit-identical (to be checked by a replay).
  User to decide, with whether to rerun run 4 with it.
- **Decided (user, 2026-10-21): fix, verify, rerun run 4. Done:** `config/obs_impact_mrms.txt` and in
  `input.nml.filter_mrms` `adjust_obs_impact = .true.`, `obs_impact_filename = 'obs_impact_mrms.txt'`,
  `allow_any_impact_values = .false.`; `prep_filter.sh` copies the table `obs_impact_filename` names. Replay of run 4's
  00:30 MRMS pass without and with it (job 1054969): member files bit-identical, radar QC and fits unchanged, the
  updated inflation different only in W, PH, MU, PSFC. `NO_COPY_BACK` on those fields kept (their prior is still
  inflated in this pass under `both`).
- **Rerun with the table (run 4b `_madis_mrms2p_imp`, 2026-10-22):** the MU inflation stays below run 3's (max 2.18
  at 01:00), but the post-analysis shock is the same as run 4's (01:00 steps 2–4 1,114 against 1,119; run 3 732). The
  table stays (the radar pass now treats MU, PH, W, PSFC as the one-pass run does), but run 4's larger shock comes from
  the two passes themselves, most likely the second inflation per cycle (`MRMS_INFLATION=both`).

## Inflation and the impact table in the one- and two-pass MRMS setups (`&filter_nml :: inf_*`, `&assim_tools_nml :: adjust_obs_impact`) — 2026-10-22

Summary note with tables and the test plan: `notes/mrms_two_pass_inflation.md` (from runs 3, 4, 4b and DART's code).

- **Flavor 2:** one λ (and sd) per state element. Each pass damps it (λ ← 1 + 0.9 (λ − 1): 10 % of the excess),
  inflates every state field (`UPDATE` or not), then updates the values and λ of every field the obs reach. Only
  `UPDATE` fields are written to the members, but `postassim_priorinf_*` holds all fields' λ and is handed on
  (`output_priorinf_*` holds only the `UPDATE` ones). λ can't change where the ensemble has no spread.
- **Correction to the 2026-10-21 run 4 entry:** pass-2 damping does not "partly offset" inflating twice in any useful
  sense; it removes 10 % of the excess, so the MRMS pass applies about the same λ again (U: mean 1.065 / max 3.50
  against 1.062 / 3.77 in the conventional pass at 01:00). U is inflated ~×1.31 per cycle in run 4b against ×1.12 in
  run 3.
- **Impact table:** factor = (obs type being assimilated, quantity being updated); 0 skips the state element's
  update **and its λ update**, and the update of later observations' priors of that quantity; it works by quantity
  (U and U10 share one). It doesn't affect H(x), the damping or the inflation applied at the start of the pass.
- **Remaining λ difference from run 3:** the conventional pass has no table, so the conventional obs adapt the
  hydrometeor and REFL_10CM λ, which the MRMS pass then applies. Proposed: `obs_impact_conv.txt` (conventional rows of
  `obs_impact_joint.txt`) in `input.nml.filter`.
- **`MRMS_INFLATION=pass1`** removes the second inflation but also all inflation of QRAIN, QSNOW, QGRAUP and REFL_10CM
  (the conventional pass discards them, the MRMS pass doesn't inflate), so it isn't a clean test of the double
  inflation. Proposed clean test: an "inflate once" mode; alternative design: RTPS in both passes, as HRRRDAS.

## Filter's order of operations; surface and radar forward operators (`&filter_nml :: compute_posterior`, `&model_nml :: sfc_elev_max_diff, allow_obs_below_vol`, `&obs_def_radar_mod_nml`) — 2026-10-22

Reference note with the cycle diagram, the stage files and code line numbers: `notes/dart_workflow_walkthrough.md`.

- **Order inside filter:** damp λ, inflate every state field (NO_COPY_BACK ones too), H(x) on the inflated ensemble,
  outlier check, sequential observation loop, H(x) again on the analysis (`compute_posterior`), write back the UPDATE
  fields only. `preassim_priorinf_*` is the damped λ actually applied; `postassim_priorinf_*` the adapted one carried
  to the next cycle.
- **Surface operators** (METAR, LAND_SFC): bilinear interpolation of T2, Q2 (then q = r/(1+r)), U10/V10 (turned to
  earth-relative) and PSFC (altimeter, with the model terrain). No vertical interpolation, and the station elevation
  is not used (`sfc_elev_max_diff = -1`); only `wrf_dart_obs_preprocess`'s 300-m elevation check screens them. Their
  increments to the 3-D fields come only from ensemble correlations with these 2-D diagnostics.
- **Posterior fits in `obs_seq.final` are optimistic:** T2, Q2, U10, V10, PSFC and REFL_10CM are updated in memory and
  used for the posterior H(x), but none is written back; WRF rediagnoses them. Not quantified yet (note Sec. 7).
- **MRMS:** the converter interpolates MRMS horizontally onto WRF's mass-point columns at the MRMS heights; DART
  interpolates each member's REFL_10CM only vertically (`height_to_zk`) and floors it at −10 dBZ
  (`apply_ref_limit_to_fwd_op`). An ob below a member's lowest mass level fails for that member
  (`allow_obs_below_vol = .false.`).

