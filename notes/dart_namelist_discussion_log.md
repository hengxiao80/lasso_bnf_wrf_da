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
