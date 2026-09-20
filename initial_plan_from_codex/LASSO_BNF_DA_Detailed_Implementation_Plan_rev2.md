# LASSO BNF DA detailed implementation plan

WRF DART development work packages for 2.5 km analyses and LES forcing

12 September 2026

Updated 17 September 2026, incorporating the 16 September decision: require `use_theta_m=1` in every project WRF integration; analyze dry theta in DART and reconstruct moist theta before WRF continuation, following the MPAS–DART separation of analysis and dynamical variables. This supersedes the earlier proposed dry-theta WRF configuration. The 13 September conventional-observation update, including source-dependent use in 15-minute cycles, remains in force.

The implementation will use a continuously cycled, 50-member WRF-DART EAKF ensemble with analyses every 15 minutes, combining MRMS three-dimensional reflectivity with an HRRRv4-based conventional-observation stream. New conventional reports are eligible for each 15-minute cycle according to their actual sampling, averaging period, quality and availability; there is no blanket hourly restriction. The reflectivity-only pilot remains an engineering milestone and scientific control. The scientific endpoint is improved initial and boundary forcing for the 500-m BNF simulations relative to direct hourly HRRRv4 analyses. Improvement over the existing free-running 2.5-km parent is a useful intermediate result; the direct-HRRR comparison determines whether the added DA system is worthwhile.

This document expands the six phases in `LASSO_BNF_DA_Implementation_Plan.docx` into executable work packages. Each step specifies its inputs, software or scripts, output, automated agent evaluation, and human scientific evaluation. The final two sections cover observation extensions and production. Script names marked DEVELOP are proposed implementation specifications; they are not claims that working BNF software has already been written or compiled.

**Navigation:** [Moist/dry theta work package](#step-1b1-implement-moist-and-dry-theta-conversion) · [Software inventory](#software-acquisition-and-ownership) · [Phase 1](#phase-1-establish-the-model-and-comparison-framework) · [Phase 2](#phase-2-build-the-radar-and-conventional-observation-pipelines) · [Phase 3](#phase-3-construct-and-spin-up-the-ensemble) · [Phase 4](#phase-4-implement-repeated-15-minute-cycling) · [Phase 5](#phase-5-measure-cost-and-evaluate-the-da-configuration) · [Phase 6](#phase-6-demonstrate-the-benefit-for-les-forcing) · [Code backlog](#implementation-backlog-and-first-milestones) · [Sources](#sources-and-decision-provenance)

## Baseline and current decisions

| Item | Implementation baseline and status |
| --- | --- |
| Existing model | WRFv4.8.0, user-reported commit 06d4240a. Pin the full commit and local patches. |
| Active DA grid | One active domain: e_we=550, e_sn=390, e_vert=150; dx=dy=2500 m; time_step=5 s; model top 1800 Pa. Additional namelist columns are inactive because max_dom=1. |
| Physics | Retain mp_physics=28 and the established physics. Resolve the CONUS suite selectors from the actual executable and run logs. Preserve the aerosol, tracer and dynamic-lightning state required for continuation. |
| Vertical coordinate | Adopt hybrid_opt=0 for the initial standard DART boundary-perturbation workflow, following the user's authorization on 12 September. The supplied configuration used hybrid_opt=2. Regenerate IC/LBC files and run a matching free-parent control. |
| Temperature representation | User decision, 16 September: WRF uses `use_theta_m=1`; DART analyzes dry perturbation potential temperature plus vapor. Use an explicit conversion interface to reconstruct native moist `THM` after analysis. This requires project code and a patched/recompiled DART WRF interface; it is not supported by the unmodified tutorial. See Step 1B1. |
| Ensemble and forcing | 50 continuously cycled members. Hourly HRRRv4 analyses supply the initial ensemble center and ongoing LBC mean; WRFDA CV3 perturbations supply IC/LBC uncertainty. HRRR does not recenter the interior every hour. |
| Radar sampling | 5 km in precipitation; 15 km in valid no echo; retained heights approximately 0.5–1 km apart where coverage supports them; nearest usable volume within ±2.5 min. |
| Localization | Gaspari–Cohn zero influence at 18 km horizontally and 6 km vertically. Verify the actual three-dimensional distance metric and half-width conversion. |
| Starting observation load | Approximately 200,000–300,000 reflectivity observations per representative cycle is a planning estimate, not a quota or hard cap. |
| Conventional observations | Target the in-domain conventional families used by HRRRv4, auditing HRRR deterministic GSI and HRRRDAS subtype usage separately. Recover actual reports, QC, errors and time support; PREPBUFR alone is not proof of complete coverage. |
| Conventional cadence | Eligible new reports enter the 15-minute cycle. Use actual timestamps and source-specific sampling/error rules. Hourly or less frequent products enter only when a new report exists; do not repeat or interpolate reports to populate intervening cycles. |
| Observation-set evaluation | Compare radar only, conventional only, and their combination. An hourly-conventional comparison measures the benefit of using eligible conventional reports every 15 minutes. |
| Later comparisons | DA50 dense at 3/9 km, DA80 at baseline sampling, optional 5/12-km no-echo test, and radial velocity after its separate pipeline passes evaluation. |

The original plan fixes these starting choices while leaving error encoding, perturbation amplitudes, inflation details and export conventions to implementation. The review clarified that these require explicit configuration and consistency checks; a separate calibration study for each parameter is not a prerequisite to starting. Proposed first-run settings below are distinguished from the established baseline. [Original project plan][P1], [Saved review record][P2], [Model configuration and current update][P3]

## Software acquisition and ownership

DOWNLOAD AND COMPILE means obtain a pinned upstream source and build it on the target HPC system. ADAPT means reuse an upstream or existing project script with documented edits. DEVELOP means write a BNF-specific component. CONFIGURE means supply data, namelists or runtime settings without changing the algorithm. A Fortran change requires rebuilding its executable; Python, shell and NCL scripts require their runtime but no separate compilation.

| Component | Obtain or build | Project responsibility |
| --- | --- | --- |
| WRF `real.exe` and `wrf.exe` | Reuse verified existing build or DOWNLOAD AND COMPILE pinned WRF. | CONFIGURE `use_theta_m=1`, the DA coordinate, I/O and restart pathway; preserve physics. Recompile only if the validated continuation path needs a targeted initialization/diagnostic hook. |
| WRF `ndown.exe` | DOWNLOAD AND COMPILE from the same WRF source if absent. | ADAPT the current downscaling scripts and validate the selected forcing trajectory. |
| WPS `geogrid.exe`, `ungrib.exe`, `metgrid.exe` | Reuse compatible build or DOWNLOAD AND COMPILE pinned WPS. | ADAPT the existing HRRR preprocessing, Vtable, static geography and vertical interpolation. |
| WRFDA `da_wrfvar.exe` | DOWNLOAD AND COMPILE WRFDA with compatible compiler, MPI and NetCDF. | CONFIGURE RANDOMCV/CV3 and its be.dat. It generates perturbations; DART performs the radar analysis. |
| DART filter and utilities | DOWNLOAD pinned source; ADAPT the WRF interface and RECOMPILE filter and all executables linking that interface. | Implement the explicit dry-theta analysis-field contract while native WRF states retain moist `THM`; configure radar/conventional types, EAKF, localization, inflation and diagnostics. |
| Moist/dry theta conversion | DEVELOP `theta_conversion.py`, `wrf_to_dart.py`, `analysis_to_wrf.py` and `thermodynamic_contract.yaml`; Python needs no separate compilation. | Convert each member before filtering and reconstruct native moist `THM` after final posterior adjustments; audit constants, units, metadata and every continuation path. MPAS supplies a design precedent, not a WRF drop-in converter. |
| DART pert_wrf_bc | DOWNLOAD with DART; ADAPT thermodynamic endpoint handling and RECOMPILE where Fortran changes are needed. | Retain the separately chosen `hybrid_opt=0` coordinate pathway. Validate moist-theta boundary values, coupling and tendencies; stock dry-theta assumptions do not satisfy this plan. |
| DART shell and NCL workflow | DOWNLOAD with DART; no separate compilation. | ADAPT the scheduler, input source, member indexing, timestamps, file staging and failure handling. |
| MRMS reader and converter | Reuse/adapt a suitable documented reader; DEVELOP the missing product adapter and observation writer. | Decode the actual 2025 product; apply BNF QC/sampling; write DART observations through its supported API. |
| Conventional BUFR/PREPBUFR conversion | DOWNLOAD AND COMPILE DART's NCEP decoder and `create_real_obs`, with the required BUFR support. | ADAPT subtype selection, QC, errors and timestamp handling; DEVELOP adapters for unhandled report codes. |
| MADIS and GPS precipitable-water conversion | DOWNLOAD AND COMPILE applicable DART MADIS/GPSPW converters. | ADAPT the actual archive schema and preserve native report time/support; validate model operators independently of converter success. |
| Mixed observation scheduling | Reuse DART `obs_sequence_tool` and compatible WRF preprocessing. | DEVELOP one-use report ledger, per-source 15-minute assignment, cross-feed deduplication and mixed-stream validation. |
| Analysis consistency and diagnostic refresh | Use existing WRF/DART capabilities where verified; DEVELOP targeted adapters if necessary. | Preserve all restart fields, enforce the chosen bounds, reconcile mass/number treatment, and regenerate physical reflectivity. |
| Evaluation and reports | INSTALL Python NetCDF/GRIB/scientific libraries; optionally use an existing MET installation. | DEVELOP BNF colocation, storm/LES metrics, cycle reports and provenance checks. |
| Dependencies | Use HPC modules or INSTALL compiler, MPI, NetCDF-C/Fortran, GRIB support, NCO and NCL as required. | Pin versions and keep builds ABI-compatible. Do not port all NCL code merely to remove a dependency. |

The core download locations are WRF, WPS and DART official repositories. DART supplies the ensemble filter and WRF workflow templates; it does not supply a fully configured BNF MRMS application. No new EnKF algorithm, WRF dynamical core, GSI system, LETKF or JEDI integration is required for this baseline. A custom WRF–DART thermodynamic interface and validation are required before scientific cycling; successful compilation of unmodified DART is not completion of that work. [WRF source][D1], [DART WRF tutorial][D2], [DART WRF interface][D3], [WPS source][D4], [DART build guide][D5]

## Phase 1 Establish the model and comparison framework

**Entry data:** the supplied namelist, existing WRF source/build and preprocessing scripts, representative HRRR input files, one existing WRF initial state, and the candidate cases on 2 May, 20 May and 17 September 2025.

### Step 1A Freeze a reproducible configuration

**Work and code.** ADAPT an environment/build script as `build_stack.sh` and DEVELOP `audit_configuration.py`. Record the full WRF/WPS/WRFDA/DART commits, patches, compiler flags, precision, MPI/NetCDF versions, executable checksums, resolved namelists and input-file hashes in `software_lock.json` and `experiment.yaml`. Record the actual CONUS physics selections rather than leaving the audit at “-1”. Preserve the supplied 5-s timestep, domain, vertical-level generation and physics as the initial settings.

**Agent evaluation.** Check that max_dom=1, input dimensions match the configuration, mandatory variables exist, and all executable/version records are complete. Compile a small DART tutorial or controlled test to establish the toolchain before using the full BNF grid. A successful tutorial establishes installation only.

**Human evaluation and output.** The model lead reviews the resolved physics and all departures from the supplied namelist. The output is one versioned baseline and a change ledger with the reason for each change. Exact HPC account, scheduler and resource settings are filled from the target machine; no resource estimate in this document implies an allocation already exists.

### Step 1B Regenerate native moist-theta states and establish continuation

**Work and code.** CONFIGURE `hybrid_opt=0` and explicitly `use_theta_m=1`. ADAPT `prepare_hrrr_mean.sh` around the existing WPS/real.exe pipeline and regenerate native wrfinput and wrfbdy from the same hourly HRRR analyses. A change of vertical-coordinate option requires regenerating the files, not editing a global attribute in old states. Keep a free-parent control with the same moist-theta configuration alongside the existing hybrid_opt=2 parent. The coordinate choice is separate from the temperature requirement. All project WRF integrations, including deterministic controls, ensemble spinup, DA advances and LES runs, retain moist theta. A historical upstream dry-theta tutorial may serve as an installation fixture only; it is not the BNF model configuration.

**Data and I/O checks.** The supplied namelist has io_form_history=11 and io_form_restart=11, which WRF documents as parallel NetCDF, while input and boundary I/O use 2. Test the actual output with the NetCDF library linked into DART. Convert or change the format only if that concrete compatibility test fails. Its restart_interval=7200 is in minutes, or 120 h; it does not provide 15-minute checkpoints. Establish dedicated 15-minute analysis states and the restart checkpoints required by the chosen continuation path. [DART WRF tutorial][D2], [WRF namelist documentation][D6]

**Agent evaluation.** Compare an uninterrupted WRF integration with an otherwise identical segmented integration crossing several hourly boundary changes. Test zero analysis increment, then a small known increment. Verify all prognostic, surface, aerosol, tracer and dynamic-lightning fields needed for continuation; field omission must not cause silent reinitialization. Record exact agreement or differences relative to a declared numerical tolerance.

**Human evaluation and output.** Inspect temperature, surface pressure, vertical motion, precipitation and inflow near boundaries for restart shocks. The output is a documented WRF-to-DART-to-WRF file contract and a stable deterministic control. The supported coordinate change is accepted only with this regenerated and tested state.

### Step 1B1 Implement moist and dry theta conversion

**Decision and scope.** Preserve WRF's moist-theta dynamics while presenting dry theta to DART. The MPAS precedent is the separation of variables: DART analyzes dry theta, vapor and other state components; MPAS's DA restart path reconstructs moist and density-coupled fields before integration. Implement the corresponding WRF-specific handoff. Do not install MPAS or add `config_do_DAcycling` to WRF; that option belongs to MPAS. This is the selected design, superseding both the earlier `use_theta_m=0` starting recipe and the alternative proposal to analyze moist theta directly. [MPAS–DART state and operator][T2], [MPAS DA restart][T3], [MPAS thermodynamic reconstruction][T4]

**Data and constants.** Obtain complete native WRF states at one valid time for quiet, humid, convective and stratiform columns, together with matching boundary endpoints and a short uninterrupted moist-theta integration. Include an initial file and the exact restart/history format selected for cycling; they are not interchangeable. Record `USE_THETA_M`, variable metadata, staggering, precision, all required time levels, and the pinned WRF constants in `thermodynamic_contract.yaml`. Let `qv` denote `QVAPOR`, the mixing ratio per unit dry-air mass; it is not specific humidity. Set `alpha = Rv/Rd` and `theta0` from the pinned WRF definition, normally 300 K for this perturbation field. The namelist `base_temp=290` describes a different base-state setting and must not replace `theta0`.

The per-member transformations are

\[
\theta_d = \frac{\mathrm{THM}+\theta_0}{1+\alpha q_v},
\qquad
\mathrm{THETA\_DRY\_PERT}=\theta_d-\theta_0,
\]

\[
\mathrm{THM}^{a}=\bigl(\mathrm{THETA\_DRY\_PERT}^{a}+\theta_0\bigr)
                    \bigl(1+\alpha q_v^{a}\bigr)-\theta_0.
\]

Here superscript `a` means the final accepted posterior after prescribed bounds and physical adjustments. Any later change to vapor or dry theta invalidates the preceding reconstruction and requires another reconstruction. Use member-specific posterior values; do not use prior humidity or ensemble-mean humidity.

**File and state contract.** Use two explicitly identified representations:

| Representation | Thermal field and metadata | Permitted consumer |
| --- | --- | --- |
| Native WRF prior/analysis/history/restart | Physical moist `THM`; native `USE_THETA_M=1`; consistent diagnostic `T` where applicable; complete carried-forward state. | WRF, native boundary preparation and LES export after validation. |
| DART analysis workspace | New project field `THETA_DRY_PERT` in K, plus `QVAPOR` and other declared analysis fields; explicit `BNF_STATE_REPRESENTATION=dry_theta_analysis_v1`; retain truthful source WRF metadata and member/time identity. | The project-patched DART interface and conversion/diagnostic tools only. |

`THETA_DRY_PERT` is a proposed project field, not an upstream WRF or DART default. Bind it to `TYPE_T` and `QTY_POTENTIAL_TEMPERATURE` using the existing WRF-interface convention of storing perturbation theta and restoring the reference inside the relevant operators. Do not simultaneously analyze diagnostic `T`, native moist `THM` and the dry-theta field as independent thermal variables. Carried native fields in the workspace, if present, are backing data rather than extra analyzed copies. Never relabel dry values as native moist `THM`, change `USE_THETA_M` to bypass a guard, or send an analysis workspace directly to `wrf.exe`.

**Code ownership and implementation.** These are planned work products, not completed software:

| Component | Obtain/build action | Concrete responsibility |
| --- | --- | --- |
| `theta_conversion.py` | DEVELOP; use installed NumPy/NetCDF runtime; no compilation. | Shared, versioned forward/inverse algebra with explicit constants, units, finite-value and shape checks; no hidden clipping. Process fields in slabs to bound memory. |
| `wrf_to_dart.py` | DEVELOP; no compilation. | Preserve immutable complete native backing files, compute the dry field for each member, check valid native diagnostic `T` against it, write the marked analysis workspace and conversion manifest. |
| DART `models/wrf/model_mod.f90` and linked tools | ADAPT pinned source and RECOMPILE. | Add an explicit project representation mode; bind `type_t` to the named dry field; replace the stock THM-only/`USE_THETA_M=0` checks with positive validation of this mode, its schema and native source metadata. Keep fail-fast behavior for unsupported combinations. Audit all hard-coded T/THM accesses, potential/sensible/virtual temperature, pressure/density, vertical-coordinate conversions and localization dependencies. |
| `analysis_to_wrf.py` | DEVELOP; no compilation unless it calls a new compiled WRF adapter. | Apply declared posterior repairs in dry-theta space, merge declared analyzed fields into each complete native backing state, reconstruct moist `THM`, synchronize required diagnostic fields and validate the native continuation file. |
| WRF thermodynamic/continuation adapter | REUSE verified WRF routines; DEVELOP a narrow Fortran hook or offline utility only if required; COMPILE changed executables. | Rebuild required diagnostics/coupled fields and time-level relationships using the actual WRF initialization/restart path. This is not a new dynamical core or a claim that WRF already has MPAS's DA restart hook. |
| `check_theta_handoff.py` and `thermodynamic_contract.yaml` | DEVELOP; no compilation. | Record tolerances, constants, representation/schema version, field dependency rules, round-trip residuals, diagnostic differences and acceptance evidence. |

For the patched mode, the intended thermal state-table entry is conceptually `'THETA_DRY_PERT','QTY_POTENTIAL_TEMPERATURE','TYPE_T','UPDATE','999'`; validate exact syntax against the selected DART release. Stock DART rejects this representation. Retain its guard until the new explicit mode is implemented; simply deleting the guard does not implement the conversion. The dry-theta operators should consume the dry field throughout inflation, filtering and posterior diagnostics. Their moisture factors must not be applied to native moist `THM`. [Audited WRF–DART source][T1]

The numerical kernel specification is deliberately small. File preservation, metadata validation, physical repairs and restart reconciliation are separate required work:

```python
# Proposed mathematical kernel; not a complete file converter.
def native_to_dry_pert(thm, qv, *, theta0, alpha):
    return (thm + theta0) / (1.0 + alpha * qv) - theta0

def dry_pert_to_native(dry_pert, qv_final, *, theta0, alpha):
    return (dry_pert + theta0) * (1.0 + alpha * qv_final) - theta0
```

**Exact operation order.** Save and validate the native prior; derive the dry analysis workspace; run DART on that workspace; complete prescribed posterior bounds and microphysical repairs; reconstruct moist `THM` using the final paired theta/vapor fields; reconcile required WRF fields; diagnose the resulting native state; validate and atomically commit it; construct consistent native boundary data; advance WRF with `use_theta_m=1`. Separate raw filter diagnostics, repaired dry-theta diagnostics and final native-state diagnostics so each alteration is attributable. If a repair changes temperature through latent heating or saturation adjustment, it must update dry theta as well as moisture before reconstruction.

**Continuation audit.** Identify every native input/restart variable and time level that the selected WRF path actually reads. A `wrfinput` cold-start path and a full `wrfrst` continuation may initialize fields differently. Use the verified path and document any changed WRF initialization routines. Refresh diagnostic `T`, pressure/density and microphysics diagnostics as required by that path; retain analyzed mass/geopotential and nonhydrostatic structure rather than silently imposing a new hydrostatic state. Do not declare success merely because one reconstructed THM array is correct. All required surface, aerosol, tracer and dynamic-lightning memory must survive. A WRF-side change, if necessary, is limited to consistent state ingestion/diagnosis; document and rebuild it.

**Agent evaluation and pass evidence.** Use the actual pinned constants and target file precision; record numerical tolerances before the pilot. Float64 kernel tests should approach floating-point round-off; complete file tests use measured, precision-appropriate absolute/relative bounds rather than a universal guessed threshold.

| Test | Required evidence |
| --- | --- |
| Analytic conversion and no-update round trip | Dry and humid columns, zero and nonzero vapor, both supported storage precisions; forward/inverse residuals below declared tolerances; source files unchanged. Invalid/mislabeled representations fail. |
| Controlled increments | Theta-only, vapor-only and joint updates reconstruct the expected moist field. At fixed dry theta, a vapor change must change THM by `alpha * theta_d * delta_qv`; the combined update includes the nonlinear cross term. |
| Posterior adjustments | Test a vapor bound and a thermodynamic/moisture repair. Reconstruct from the accepted final values and verify that no later write leaves stale THM. Separate repair effects from assimilation increments. |
| Operator agreement | Compare WRF and DART dry theta, sensible/virtual temperature, pressure/density and vertical placement at collocated columns; then compare radar and conventional observation equivalents under their separate operator contracts. |
| Conversion replay and recovery | Repeated staging from the immutable native prior reproduces the same dry workspace. Reject double conversion, stale member/time manifests and partial writeback; resume without applying increments or observations twice. |
| Native restart identity | Compare uninterrupted moist-theta integration, segmented native integration, and segmented integration with a zero-update DART round trip. Establish segmentation error first; show the conversion adds no unexplained drift or restart impulse. |
| Increments surviving continuation | A small ensemble and controlled temperature/moisture observations produce intended increments that survive the first WRF step and a 900-s advance. Check both prior and posterior inflation/writeback paths. |
| Boundaries and perturbations | Pass the Step 3C/3D dry-to-moist perturbation and native coupled-endpoint tests before bank expansion or full cycling. |
| Multi-cycle physical behavior | Inspect pressure tendencies, divergence, vertical motion, water/temperature budgets and restart/boundary disturbances relative to the matching moist-theta control over several cycles. |

**Human evaluation and outputs.** The DA lead checks state-variable and operator interpretation; the WRF/modeling lead checks continuation, acoustic adjustment and boundary behavior; the microphysics lead checks any physical repair. Deliver the source/namelist diffs, adapter specifications and implemented code, constants/schema record, sample native/workspace/posterior files, and a concise test report with measured residuals and figures. Completion means the implemented handoff passed these checks, not that this plan or the small algebraic kernel alone proves compatibility.

**Blocking gate.** No scientific BNF cycling or ensemble expansion proceeds with an unvalidated temperature handoff. The small perturbation and boundary engineering tests specified in Steps 3C/3D are brought forward to close this gate; they do not require constructing the full bank or ensemble. Observation preparation can proceed independently. Failure of this gate requires correcting the interface; switching project WRF runs to `use_theta_m=0` is not an authorized fallback. The coordinate decision `hybrid_opt=0` remains separate.

### Step 1C Define the analyzed state and observation operator

**Work and code.** CONFIGURE wrf_state_variables and wrf_state_bounds for the pinned DART version; DEVELOP `state_contract.yaml` and `audit_wrf_state.py`. For every relevant field record its WRF name, dimensions/staggering, units, DART quantity, analyzed or carried-forward status, bounds, dependencies and writeback rule. Audit U, V, W, native moist THM, the project dry-theta analysis field, pressure/mass and geopotential fields, vapor and all microphysics fields. Use the Step 1B1 representation contract; physical THM is reconstructed rather than independently analyzed. Inspect actual rain/ice number and aerosol variable names in mp_physics=28 rather than guessing them from another microphysics scheme.

**Operator implementation.** Use the WRF-calculated three-dimensional reflectivity associated with the selected microphysics as the first integration candidate, mapping the actual diagnostic to QTY_RADAR_REFLECTIVITY when supported. If the required field is absent or stale, DEVELOP a minimal extraction/refresh adapter or a compatible forward-operator implementation. DART's built-in Kessler/Lin-style choices do not establish a match to mp_physics=28, and do_radar_ref=1 alone does not establish the DART mapping. [DART WRF interface][D3], [DART radar operator][D7]

**Agent evaluation.** Compare WRF and DART observation equivalents for sampled clear, rain, melting-layer and ice columns, checking the same location, height, interpolation and floor. Use a small ensemble and a single-observation update to show that intended physical fields receive increments. Verify T/THM conversion and the actual temperature reference; base_temp=290 is not a general instruction to add 290 to THM.

**Human evaluation and output.** The DA/microphysics lead reviews a short field/operator report and adopts one explicit mass–number treatment for the first experiment. A possible HRRR precedent is analyzed rain mass with a diagnosed rain-number adjustment; that is not an automatic Thompson/DART default. The output is an operator and state contract that can be exercised without running an entire ensemble case. Extend that contract to conventional temperature, moisture, wind, pressure and column-water quantities using Step 2F; identify their state-update and diagnostic requirements before their first analysis. [Dowell 2020 supplied report][A1]

### Step 1D Define comparisons and development windows

**Work and code.** DEVELOP `case_manifest.yaml` and `collocation_config.yaml`. Inventory radar and conventional coverage, HRRR availability, storm passage at BNF and independent observations for the three candidate cases. Reserve verification stations/profiles or independent instruments before including conventional data; record whether each verification stream is locally assimilated, withheld or potentially inherited through HRRR. Select one development interval containing substantial precipitation and retain other case/windows for evaluation. Include a quiet or weak-echo interval for clear-air behavior. Do not assign storm-regime labels solely from the calendar date.

**Agent evaluation.** Produce synchronized coverage maps and a time inventory. Verify that the HRRR fields used for the benchmark are hourly analyses, consistent with the user's established provenance. Preserve the existing composite-reflectivity comparison; use three-dimensional reflectivity for assimilation.

**Human evaluation and output.** The science lead defines the time/region of interest, independent metrics and tolerances for material degradation before seeing experiment rankings. The output is the case manifest and three forcing-system definitions: direct HRRR, free parent, and DA parent.

**Phase 1 completion:** reproducible patched builds, a validated moist-WRF/dry-DART handoff under Step 1B1, a working state/continuation contract, verified single-observation behavior, and explicit comparison windows. Work on radar decoding can proceed in parallel with the build, but full cycling waits for the state/operator gate.

## Phase 2 Build the radar and conventional observation pipelines

**Entry data:** exact MRMS three-dimensional files, conventional reports and source/QC metadata for the development interval, and the Phase 1 model/operator contract. Steps 2A–2D build reflectivity; Steps 2E–2H build conventional ingestion and the merged stream. Composite reflectivity is an evaluation product, not a substitute for volumetric observations.

### Step 2A Acquire and decode the actual MRMS product

**Work and code.** DEVELOP `stage_mrms.py` and `decode_mrms.py`, using installed GRIB/NetCDF libraries as appropriate. Start from the NOAA MRMS product catalog and the archive's actual MergedReflectivityQC height products or supplied equivalent. Assemble the altitude slices into a volume while retaining each slice's valid time and source identifier. Do not assume a timestamp-named volume is perfectly simultaneous or that a historic archive has every requested slice. [NOAA MRMS product inventory][R1], [NOAA MRMS archive][R2]

**Required data record.** Save product/version, exact object/file identifier, checksum, valid time, height and vertical datum, horizontal coordinates, reflectivity units, missing and no-echo codes, and the usable-coverage mask. Record what quality information really exists for that archived product. A two-dimensional quality indicator, such as a precipitation-quality field, must not silently become a three-dimensional reflectivity coverage mask.

**Agent evaluation.** Check known decoded points and maps against the native product. Exercise missing files, duplicate times, reversed latitude, below-terrain levels and invalid coverage. Verify a complete bounded window before staging an entire case.

**Human evaluation and output.** A radar scientist or experienced DA scientist reviews several elevation maps/columns for clutter, blocked beams, bright-band behavior and high-altitude coverage. Output: a validated decoded volume and an availability/QC report. Archive existence is a source lead; exact 2025 completeness remains a data-stage check.

### Step 2B Freeze classification and error encoding

**Work and code.** CONFIGURE `obs_policy.yaml` and DEVELOP `classify_reflectivity.py`. The following is a concrete proposed first-run recipe based on the reference configuration discussed in the review. It is a proposal for BNF, not a recovered decision that these values have already been adopted.

| Quantity | Proposed initial configuration | Where it is implemented |
| --- | --- | --- |
| Observation error | Standard deviation 5 dBZ; write variance 25 (dBZ)^2. | Converter observation definition. |
| Precipitation | Valid reflectivity at least 10 dBZ. | Classification and 5-km sampling mask. |
| Valid no echo | Valid reflectivity at most 0 dBZ; encode as -10 dBZ. | Classification and 15-km sampling mask; radar clear-air type. |
| Intermediate echoes | Omit 0–10 dBZ from this initial two-category recipe. | Explicit converter rejection reason. |
| Simulated lower limit | Enable the forward-operator floor and replace values below -10 dBZ with -10 dBZ. | DART radar operator settings. |
| Incoming QC | Emit QC=1 for retained, upstream-valid observations; omit unusable records. Set the accepted threshold consistently. | Converter plus DART input-QC setting. |
| Innovation screening | Start from the pinned WRF-DART example's documented rule; if using its standard threshold 3, record it explicitly. | DART quality-control configuration. |

The reviewed HRRR configuration is the basis for the numerical error/classification example; DART documentation is the basis for the encoding and controls. Keep these attributions separate. A threshold of 3 for incoming QC is a categorical acceptance cutoff. A threshold of 3 for innovations is a normalized departure test. Neither is the -10-dBZ operator floor. Inspect innovations and rejection codes for missed storms; an extreme departure need not be a bad observation. [Saved review record][P2], [DART radar operator][D7], [DART quality control][D8]

**Agent evaluation.** Test boundary values at 0 and 10 dBZ, invalid coverage, observation-error squaring, active floor flags and the distinction between input and output QC. Check that a valid weak-echo observation and a nearly clear model column do not acquire an artificial large innovation solely from mismatched encoding.

**Human evaluation and output.** The DA lead reviews and accepts one frozen recipe, including any radar-specific outlier exception. The output is a short policy record and deterministic tests. Subsequent tuning is driven by a diagnosed problem or a planned controlled experiment.

### Step 2C Apply reproducible spatial and temporal sampling

**Work and code.** DEVELOP `thin_reflectivity.py` and `select_volume.py`. Use fixed target grids anchored to the model projection, choosing a QC-passed native point near each target. Use 5-km spacing for precipitation and 15 km for valid no echo. Define a reproducible tie-breaker and an explicit retained-height list from the actual MRMS levels. Store native indices and the realized distance from each target. Start with point selection; averaging in linear Z or dBZ is a different observation definition requiring its own operator/error treatment.

Choose the nearest usable volume within ±150 s of each analysis. Record source times, offsets, and unique observation IDs. For a synchronous first implementation, the model state represents the analysis time: document that approximation. Configure DART's processing bounds to include the selected true-time records, or, if that version requires a common effective assimilation time, preserve the true time in the canonical observation archive and record the explicit conversion. Never rely on a default six-hour window. Retrospective use of a future-offset volume is allowed by this symmetric window and must remain visible in latency accounting.

**Agent evaluation.** Prove repeatability, category-specific spacing, height support, absence of duplicates, and correct behavior at midnight and hour boundaries. Report retained counts by height/category and every rejection reason. Do not pad a quiet cycle to the planning observation count.

**Human evaluation and output.** Review coverage maps for loss of narrow convective lines, oversampling of one radar footprint and unsupported no-echo constraints. Output: a canonical sampled-observation file and one compact sampling report per cycle.

### Step 2D Write and validate DART observation sequences

**Work and code.** DEVELOP or ADAPT `mrms_to_obs_seq.f90` using DART observation/location/time APIs; compile against the pinned DART modules. A Python reader can write an intermediate NetCDF table, with a small Fortran writer responsible for DART serialization. Audit existing converters before choosing an adapter; do not assume any legacy radar/mosaic converter decodes the current MRMS product unchanged. Compile/configure RADAR_REFLECTIVITY and RADAR_CLEARAIR_REFLECTIVITY support through the release's preprocess/build procedure.

**Agent evaluation.** Read the result with obs_sequence_tool or obs_seq_to_netcdf. Check record counts, longitude convention, MSL/AGL handling, seconds/days, type mapping, observation value, error variance and QC. Exercise an intentionally empty window. Compare filter observation equivalents and departure statistics with the independently collocated checks from Step 1C.

**Human evaluation and output.** The DA lead reviews one report linking native product to sampled point to DART record and model equivalent. Output: validated obs_seq input, canonical source-observation archive and a traceable converter build.

### Step 2E Define the HRRRv4 conventional target and obtain the reports

**Scope.** Use the HRRRv4 CONUS conventional observation families as the target. This is a data-selection and observation-processing reference; the BNF assimilation algorithm remains WRF-DART EAKF. Dowell et al. identifies aircraft, rawinsonde, GPS precipitable water, surface, buoy/ship, profiler and satellite winds, and adds TCVitals for HRRRv4. HRRRDAS and deterministic HRRR have different analysis methods and can have different active subtypes; maintain separate columns for their documented use. [HRRR Part I][A2]

CONUS HRRRv4 does not assimilate satellite radiances. Satellite wind retrievals belong in this inventory, while radar reflectivity, Level-II radial velocity, lightning latent-heating initialization and the separate cloud/hydrometeor analysis retain their own work packages. METAR temperature/wind/moisture/pressure reports do not automatically reproduce the use of METAR ceilings and visibility in HRRR cloud analysis. [HRRR Part I][A2]

| Observation family | BNF data and variable target | Cadence and implementation requirement |
| --- | --- | --- |
| Radiosondes and other supported upper-air reports | Temperature, humidity and horizontal wind profiles; pressure/height and level position/time metadata. | Assimilate a newly available profile once under a documented level/profile-time rule. Frequent cycle availability does not imply frequent launches. Audit pibal/dropsonde subtypes separately. |
| Aircraft including ACARS/AMDAR-type reports | Horizontal wind, temperature and humidity where measured. | Candidate for new reports in successive 15-minute cycles. Retain flight/track identifiers, level/time and ascent/descent information; thin correlated along-track samples. |
| METAR and other land surface networks | Near-surface temperature, moisture, wind and station-pressure/altimeter reports. | Use new METAR/SPECI or other distinct reports when present. Higher-frequency mesonet or surface feeds are candidates where their 2025 archive retains those reports. |
| Marine surface reports | Ship/buoy winds and pressure, with other variables only when supported by the actual HRRR subtype and source. | Retain in-domain reports at their native reporting times; record ship/buoy height and exposure. |
| Wind profilers and radar-derived VAD winds | Horizontal wind profiles; temperature-related profiler products only if actually present and enabled. | Check both output frequency and averaging duration. VAD is a retrieved wind profile, distinct from Level-II radial velocity; give it a separate report type and error/support rule. |
| GNSS precipitable water | Column-integrated water vapor with station elevation, retrieval QC and averaging period. | Use the actual retrieval cadence. Frequent delivery of overlapping retrievals does not establish independent 15-minute information. |
| Satellite atmospheric motion vectors | Retrieved horizontal wind and assigned pressure/height, quality, imagery/track time support. | Use newly generated vectors when available; high image frequency does not guarantee equally frequent independent wind vectors. These retrieved winds are distinct from radiances. |
| TCVitals when relevant | Storm location and minimum pressure within an applicable case/domain. | Inventory as an HRRRv4 addition; implement a compatible storm/pressure treatment only for relevant cases. Record a documented deferral if no validated WRF-DART path is available. |

**Data and code.** DEVELOP `inventory_conventional.py` and `hrrr_conventional_inventory.yaml`. Prefer archived RAP/HRRR observation inputs and associated `convinfo`/error/QC configuration when obtainable. The inspected 2022 HRRR scripts stage PREPBUFR plus a separate satellite-wind feed; copying just one PREPBUFR file does not reproduce the whole target. Inspect the active report/subtype flags and, where available, accepted-observation diagnostics; a staged file or a namelist entry alone is not proof that each subtype was assimilated. [HRRR 2022 analysis script][C1]

For each family record: HRRR GSI status, HRRRDAS status, source/product and archive access, actual 2025 coverage, native sampling, product averaging/derivation interval, archive packaging frequency, report availability time if known, converter/operator readiness, and BNF inclusion or documented gap. The NCEP operational PREPBUFR archive at NCAR GDEX and archived MADIS streams are candidate data routes. A generic global PREPBUFR archive is not guaranteed to include every regional mesonet, aircraft, VAD, GNSS or satellite-wind report used by HRRR. Supplement missing or time-thinned streams from their native archive where available, subject to cross-feed deduplication. [NCEP observation archive][C2], [MADIS][C3]

**Agent evaluation.** Inventory distinct reports and inter-report intervals per station/track, not just files per hour. Test one complete development day including non-synoptic hours. Count reports before/after each decode/selection stage and expose missing subtypes, stripped timestamps and archive gaps.

**Human evaluation and output.** The DA lead accepts the HRRR target-versus-obtainable-data matrix and per-source cadence. The instrument/data lead checks which apparent high-frequency streams carry new information. Output: a source manifest and explicit coverage gaps; “HRRR-like conventional data” must never silently mean whatever the first converter happens to retain.

### Step 2F Convert conventional reports and validate their operators

**Existing software to download and compile.** DART provides a two-stage NCEP pathway: `observations/obs_converters/NCEP/prep_bufr/install.sh` builds the decoder/BUFR utilities, including `prepbufr.x`; `observations/obs_converters/NCEP/ascii_to_obs/work/quickbuild.sh` builds `create_real_obs`. The first stage writes intermediate reports and the second writes DART observation sequences. Adapt the compiler and input-format handling to the actual archive; do not apply legacy byte swapping blindly. [DART PREPBUFR decoder][C4]

DART also supplies MADIS converters including `convert_madis_metar`, `convert_madis_mesonet`, `convert_madis_acars`, `convert_madis_marine`, `convert_madis_profiler`, `convert_madis_rawin` and `convert_madis_satwnd`, plus a separate GPSPW converter directory. Use these as source-specific starting points when native archives retain observations absent from PREPBUFR. Adapt schemas, fixed filenames and script windowing rather than assuming a turnkey pipeline. [DART MADIS converters][C6], [DART GPSPW converter][C7]

**Project code.** ADAPT these converters through `convert_conventional.sh`; DEVELOP missing BUFR-subtype adapters, a canonical report table and `audit_conventional_conversion.py`. Audit decoder report-code coverage for VAD/profiler, modern aircraft/moisture, mesonet and satellite products. A successful conversion of common radiosondes does not establish full subtype coverage. Preserve actual times: `create_real_obs` supports `obs_time=.true.`. Configure field/type switches explicitly; `select_obs=0` means all recognized input observations, so a false selection flag elsewhere is not by itself evidence that a field is disabled. [DART create_real_obs][C5]

**Operator contract.** Extend Phase 1's single-observation tests to each included quantity/platform. Verify dry versus virtual temperature, specific humidity versus mixing ratio/RH/dewpoint, pressure versus altimeter setting, pressure/height coordinates, and earth-relative wind components. Do not assimilate several algebraic representations of one humidity or pressure report as independent observations. Test 2-m temperature/moisture and 10-m wind using a supported surface operator and terrain/exposure treatment; do not silently substitute the lowest model-level value. Preserve any HRRR-derived elevation or bias adjustment in provenance so it is not applied twice.

For GNSS PW, verify a station-to-model column integral with correct units, surface elevation, vertical extent and column localization; GPS radio-occultation operators are not substitutes. For VAD, profilers and AMVs, document horizontal/vertical/temporal support and height-assignment uncertainty. DEVELOP a targeted operator or diagnostic adapter and compile if the pinned WRF-DART interface lacks the needed support. A converter's existence alone does not prove model-operator compatibility.

**Agent evaluation.** Compare decoded values, QC and error variances with selected native reports; require reconciliation of counts by platform, subtype and variable. Test analytic temperature/wind/pressure cases and independent column integration for PW. Verify all observation types survive DART preprocessing and appear in the intended assimilate/evaluate lists.

**Human evaluation and output.** The DA/model lead reviews surface-elevation effects, profile interpolation, wind retrieval support and PW consistency. Output: validated per-family converters/operators, an explicit code-gap list, and observation definitions with units and error rules.

### Step 2G Schedule new conventional data in the 15 minute cycles

**Work and code.** DEVELOP `assign_conventional_cycles.py`, `deduplicate_reports.py` and `conventional_policy.yaml`. The driver offers every 15-minute analysis to each enabled stream. Report availability and the stream's validated time-support/error policy determine inclusion; an hourly file container does not restrict its subhourly reports to an hourly update. Sources with only hourly or occasional new reports simply contribute to the appropriate subset of cycles.

**Proposed retrospective starting rule.** For an instantaneous report with sufficiently precise native time, assign it to the nearest 15-minute analysis using half-open windows `[T-7.5 min, T+7.5 min)`, with ties assigned consistently. This is a new BNF implementation proposal, not an HRRR operational window. Keep the established MRMS volume-selection window at ±2.5 minutes. Preserve actual time and offset in both streams, and retain the synchronous observation-operator approximation explicitly. A later real-time configuration must additionally enforce report arrival/latency and cannot assume future observations are already available.

For profiles, retain per-level times and drift positions where available. Decide explicitly whether levels are assigned individually or a profile remains together at a reference time; preserve profile identity and exclude levels outside the accepted time policy. For averaged or retrieved observations, record the full averaging/imagery interval and select one declared reference time. An hourly mean remains an hourly-support observation even if delivered every few minutes. If the archive preserves only nominal hourly times, use that honest precision or obtain a better source; never reconstruct finer timestamps by interpolation.

**Temporal correlation and density.** Begin with a reproducible per-platform rule for temporal thinning or superobbing. For dense station streams, a candidate is one representative report per station/variable/15-minute window; for aircraft use a track/time/height-aware rule. Evaluate overlapping averages, GNSS retrieval smoothing, repeated AMV tracks and persistent station bias before treating consecutive reports as independent. Independent new records can still have correlated errors. Record the selected mitigation—thinning, nonoverlapping averaging, appropriate errors, or an explicitly tested correlated-error method—and do not automatically divide errors by the square root of sample count.

**One-use identity.** Build an identifier from platform/report identity, native time, location/level, variable and provenance, with a rule for amended reports. Recognize the same physical report arriving via PREPBUFR, MADIS or another feed; file hashes alone do not identify these duplicates. Select the preferred corrected version before a retrospective run, and do not assimilate both versions. Keep identities through merged sequences, restarts and replay. Distinct 5-minute reports from one station are not duplicates merely because the station is unchanged.

**Agent evaluation.** Test consecutive 15-minute bins, midnight, duplicate feeds, corrections, low-precision time, overlapping products and late delivery. Compare unique physical reports against all assigned cycles and show temporal coverage/counts by family. Test that broad conventional input-file windows cannot accidentally broaden MRMS selection or reintroduce already used reports.

**Human evaluation and output.** The DA lead approves per-source assignment, averaging, error/correlation and latency assumptions from a short inventory and innovation report. Output: a deterministic per-cycle conventional sequence, report ledger and cadence policy. An hourly-conventional schedule remains a comparison experiment, not the default restriction on high-frequency data.

### Step 2H Set conventional errors and complete a mixed observation test

**Work and code.** DEVELOP `conventional_error_qc.yaml` and ADAPT the merged observation builder around `obs_sequence_tool` and the verified WRF preprocessing path. Import documented source/HRRR nominal errors as a starting reference where applicable, converting to DART's observation-error variance and the actual assimilated variable. Audit source QC meaning and all error adjustments; radar's 5-dBZ error and categorical encoding are not a conventional-data policy.

Use family-specific gross checks, station/aircraft bias handling where warranted, and terrain/height/representativeness rules. Record when source QC was obtained using a model background, especially the same HRRR system used for initialization. The baseline EAKF does not automatically reproduce HRRR GSI's variational QC, PBL pseudo-innovations, soil adjustment or cloud analysis; these remain separately identified algorithmic differences, with targeted development only if required by the scientific objective.

**Agent evaluation.** Run manufactured and small real-data conventional-only updates, then a merged radar/conventional update. Verify source-specific error, QC and localization, consistent type definitions, and deterministic ordering. Test a cycle containing conventional observations but no radar; it must still assimilate. Diagnose increments and innovations separately by family, level, station/track and time offset, including the next 15-minute prior.

**Human evaluation and output.** The DA lead reviews environmental wind/temperature/moisture/pressure changes and whether near-surface or column observations produce plausible vertical responses. Output: a validated combined input stream and one fixed starting configuration. Broad parameter optimization is not required to finish this step.

**Phase 2 completion:** validated radar sequences plus a traceable, per-family conventional pipeline with data coverage, conversion, errors/QC, time/correlation policy and operator checks. Radar-only testing may proceed first; promotion of the combined system requires the conventional steps as well.

## Phase 3 Construct and spin up the ensemble

The ensemble is built in three distinct operations: generate a reusable bank of correlated atmospheric perturbations; apply selected perturbations to HRRR-centered initial and boundary states; integrate the resulting members long enough to develop model-consistent flow-dependent spread. WRFDA provides the perturbation generator. WRF develops the perturbations dynamically. DART subsequently analyzes the ensemble.

### Step 3A Prepare HRRR mean states at the required endpoints

**Data.** Use hourly HRRRv4 analyses spanning ensemble initialization, spinup, cycling and any forecast tail. Include an extra boundary endpoint beyond the last integration time. Prefer the already working BNF HRRR preprocessing with its complete surface/soil and atmospheric fields; do not substitute a pressure-level-only subset that cannot reproduce the established initialization. [NOAA HRRR archive][R3]

**Work and code.** ADAPT `prepare_hrrr_mean.sh` or the DART `gen_retro_icbc.sh` template to the BNF source/grid, `hybrid_opt=0` and `use_theta_m=1`. Native mean/endpoints must carry physical moist THM and consistent dry diagnostic T; derive separate dry workspaces only for analysis or perturbation-generation tools. Generate the deterministic mean endpoint states and boundary templates needed by pert_wrf_bc. Separate the hourly meteorological input interval from the 900-s analysis/advance interval. Cache reusable geogrid and decoded inputs.

**Agent evaluation.** Verify valid times, interpolation brackets, coordinate metadata, endpoint consistency, mandatory moisture/scalar fields and file completeness. Check the first and last endpoint used by every 15-minute advance.

**Human evaluation and output.** Inspect the unperturbed environmental profiles and boundary evolution near the BNF inflow region. Output: mean wrfinput/wrfbdy products with a time-to-file manifest. These define the initial/LBC mean, not an instruction to reset analyzed interior members each hour.

### Step 3B Generate the correlated perturbation bank

**Work and code.** DOWNLOAD AND COMPILE `da_wrfvar.exe`; ADAPT DART `gen_pert_bank.sh` and its WRFDA namelist. Supply the matching CV3 be.dat and a representative WRF mean state. RANDOMCV draws random control-space perturbations and transforms them through the prescribed covariance to physical-variable increments. This is not 50 independent white-noise fields and does not require a radar observation file for generating the bank.

For the first draw, stage the mean state as `fg`, set `analysis_type='RANDOMCV'`, `cv_options=3`, `put_rand_seed=.true.` and the two recorded seed integers, and set the analysis date to the state's valid time. `da_wrfvar.exe` writes a complete perturbed state as `wrfvar_output`; the bank generator then differences selected fields against `fg`. Verify this one draw before launching the bank-generation jobs.

The inspected stock DART script extracts differences in U, V, THM, QVAPOR and MU into pert_bank_mem_*.nc using NCO; its dry-THM assumption must be adapted. DEVELOP `wrfda_bank_adapter.py` to identify the actual WRFDA background/output thermodynamic conventions, convert both complete states to dry theta, and store explicitly named dry-theta increments together with vapor and other increments. Do not infer the physical meaning from a field name. Verify the pinned WRFDA RANDOMCV input/writeback path on one draw; any required dry generator workspace must be explicitly converted and documented as an offline statistical input, never used for a WRF integration. All native model inputs and integrations remain moist-theta. Do not difference moist THM and label the result a dry-theta increment. Its bank size is three times the ensemble size: 150 perturbations for a 50-member implementation. Those 150 files are candidate perturbations, not 150 model members. Retain the exact generation seeds, WRFDA namelist, be.dat checksum, input mean state and output hashes. [DART perturbation-bank script][D9]

**Agent evaluation.** Verify nonzero, spatially correlated increments and distinct seeds. Compute variable RMS, extrema, horizontal spectra/correlation scales and vertical profiles. Inspect the actual WRFDA cv_options/as* settings and the later application scaling; some shell variables named as perturbation controls are unused in the inspected default script. A configuration audit must follow the values reaching the executable.

**Human evaluation and output.** Review wind, temperature, moisture and pressure spread against plausible uncertainty and available observations. Choose one starting amplitude/scale configuration; the tutorial values are a traceable first test, not established BNF uncertainty. Output: a reproducible perturbation bank and a concise scale/amplitude report.

### Step 3C Assemble 50 centered initial members

**Work and code.** ADAPT `add_bank_perts.ncl` and `init_ensemble_var.sh`; DEVELOP `assign_perturbations.py` and `recenter_perturbations.py`. The inspected stock application script uses wall-clock-based random selection and additional scaling: 1.3 for U, V, THM and QVAPOR; 0.6 for MU. In the adapted workflow the thermal scale applies to the explicitly identified dry-theta increment, not directly to native moist THM. These are reference-script values, not established BNF amplitudes. Replace that selection with a saved member-to-bank assignment, and record both generator and application scales. Select 50 distinct draws and subtract their sample mean in the chosen physical perturbation representation before applying them to the common HRRR-centered state. [DART bank-application script][D10]

Apply the centered/scaled dry-theta and vapor increments to each corresponding HRRR-centered endpoint, complete prescribed adjustments, and then reconstruct that member's native moist THM through the shared conversion kernel. Use the same procedure for initial conditions and target boundary endpoints. For unadjusted increments the exact relation is `delta_theta_m = (1 + alpha*qv)*delta_theta_d + alpha*theta_d*delta_qv + alpha*delta_theta_d*delta_qv`; adding a dry-theta bank perturbation directly to moist THM omits terms.

Centering means that the mean of the applied perturbations is zero in the specified dry-theta/vapor representation. Their covariance can produce a nonzero mean moist-theta perturbation even before bounds, because the transformation is nonlinear; diagnose it rather than silently recentering moist THM and changing the intended dry-theta ensemble. It does not imply that nonlinear bounds, saturation adjustments or later WRF spinup leave the ensemble mean identical to HRRR. Measure and report those changes separately. Preserve each member ID throughout the run; never swap identities to follow the storm that happens to look best.

For conventional assimilation, document the initialization observation overlap: the HRRR analysis already contains observational information. Do not deliberately count an identified initialization report again as a new independent observation. Define the first eligible report times and known exclusions, and label unresolved overlap honestly if the exact HRRR used-observation list is unavailable. Continuing HRRR analysis LBCs also introduce shared information; a one-use local ledger prevents local repeats but cannot make the local prior and observation errors fully independent of HRRR.

**Agent evaluation.** Verify unique initial files, reproducible assignments, zero pre-adjustment sample mean to numerical tolerance, intended post-scaling spread, and absence of NaNs/unphysical moisture. Check that all unchanged restart fields remain present. Require the shared moist/dry conversion rather than a name-only T/THM synchronization. Verify that reconstructed THM, diagnostic T and QVAPOR describe the same thermodynamic state; audit dry-theta and moist-theta mean/spread separately and retain the covariance contribution.

**Human evaluation and output.** Inspect a subset of perturbation sections and ensemble environmental soundings; accept or adjust the one starting recipe. Output: 50 complete initial member states, an assignment/seed manifest, and pre/post-adjustment centering diagnostics.

### Step 3D Generate member boundary values and tendencies

**Work and code.** ADAPT and compile DART pert_wrf_bc for native moist-theta endpoints with `hybrid_opt=0`; the coordinate support does not establish temperature support. DEVELOP `prepare_moist_boundaries.py` around the audited utility, or a narrowly modified Fortran boundary writer if required by the pinned field/coupling path. ADAPT `new_advance_model.sh`/prep_ic.sh and DEVELOP `audit_boundaries.py`. At each advance, the utility and wrapper must use the correct member state at the beginning and a perturbed target boundary state at the end. Preserve the HRRR mean and member-specific uncertainty through successive target times; record the bank draw/weights used for each member and endpoint. [DART boundary utility][D11]

Use the same saved perturbation realization for a shared endpoint wherever adjacent intervals meet. Do not independently redraw both sides of the same endpoint. Implement the temporal behavior explicitly in the adapted script: retain the verified upstream rule as a starting point, or use a documented correlated/interpolated sequence if the upstream rule produces unacceptable jumps. Do not invent a decorrelation time merely to populate a namelist.

For the first engineering pilot, a concrete proposed policy is to retain each member's assigned bank pattern through the pilot and apply it to successive hourly HRRR reference states. This makes the imposed perturbation time dependence explicit; it is not a claim that time-constant boundary error is optimal. A later evolving sequence can be tested if boundary/spread diagnostics justify it. Reusing a prescribed target endpoint does not require erasing a legitimate analysis jump: if the next interval starts from the posterior member boundary, record its difference from the preceding predicted endpoint separately from unintended redraw or time-interpolation errors.

First construct the accepted native moist-theta state at each endpoint from its own dry theta and vapor. Then use the exact WRF boundary representation, reference subtraction, coordinate/mass coupling and staggering to form boundary values and tendencies. Do not multiply an already-computed dry-theta tendency by a moisture factor; endpoint moisture and mass can change. Boundary arrays named T_B* may retain that historical name while requiring the formulation appropriate to `use_theta_m=1`; establish their semantics from pinned WRF read/write code and sample files, not their names.

Boundary tendencies must reproduce the intended end value when integrated over the file's actual interval. Test the WRF stored representation, including staggered wind and mass coupling, rather than applying an uncoupled difference formula to arbitrary variables. Audit the utility's field list against have_bcs_moist=.true. and have_bcs_scalar=.true.; hydrometeor/aerosol/tracer fields that are unperturbed still need a valid continuation/boundary treatment.

**Agent evaluation.** Start with zero perturbation and dry-theta-only, vapor-only and joint perturbation cases. Include a humidity-changing interval and verify the moisture contribution and any mass-coupling changes. Reconstruct boundary endpoints from values and tendencies, check shared-endpoint continuity, verify ensemble-mean offsets and compare interior-edge temperature with the temperature used by the boundary utility. Examine several hourly HRRR transitions and 15-minute restarts. Apply only targeted source/adaptor fixes demonstrated necessary by these tests.

**Human evaluation and output.** Inspect pressure/vertical-velocity wave packets, artificial boundary precipitation and incoming environmental spread. The HRRRDAS report documents difficulties with direct small-scale boundary perturbations, which motivates this gate but does not establish a BNF failure. Output: a validated member-boundary recipe and a boundary audit. [Dowell 2020 supplied report][A1]

### Step 3E Spin up the members and diagnose useful spread

**Work and code.** ADAPT `first_advance.sh` and `init_ensemble_var.sh` to the scheduler and target time. Integrate all 50 members without local radar or conventional assimilation to the first analysis, maintaining common physics and member-specific LBCs. A six-hour spinup is a reasonable first trial from the tutorial workflow; its suitability for BNF must be assessed from the case evolution, not treated as a recovered fixed duration.

**Agent evaluation.** Produce time series and maps of wind, temperature, humidity, pressure, hydrometeor and reflectivity spread; track precipitation, mass/water adjustments, CFL/stability indicators and boundary-distance dependence. Compare spread with innovations where observations exist. Save the start and final states and enough intermediate output to diagnose adjustment.

**Human evaluation and output.** Check whether members represent uncertainty in storm initiation, position and environment without destroying the large-scale HRRR constraint. A dry, zero-variance prior in every member cannot acquire convective covariance through multiplicative inflation alone. If this occurs, diagnose spinup, IC/LBC perturbations and operator behavior before adding a separate storm-initiation treatment.

**Phase 3 completion:** a stable, restartable 50-member ensemble at the first radar-analysis time; documented useful spread; reproducible IC/LBC assignments; and no unexplained boundary-generated disturbances. Review progress through Phase 3 is not evidence that these computational tests have already been run.

## Phase 4 Implement repeated 15 minute cycling

**Entry data:** all 50 members at the same first-analysis time, the member boundary recipe, validated radar/conventional sequences, report ledger and the frozen state/operator contracts. Use a small ensemble only for engineering tests; the scientific pilot uses the full baseline ensemble.

### Step 4A Adapt the driver to seconds and explicit cycle states

**Work and code.** ADAPT DART `driver.sh`, `assimilate.sh`, `assim_advance.sh` and `new_advance_model.sh`; DEVELOP `cycle_driver.py` with site batch templates. Use UTC timestamps containing minutes and seconds and one integer cycle_interval_seconds=900 throughout. Audit every date calculation, directory name, WRF stop time, DART window and boundary interval. Setting an hourly tutorial variable to 0.25 is not sufficient proof that the script chain supports subhourly cycles. [DART member-advance script][D12]

The driver tracks these states: native inputs validated, 50 moist-theta priors ready, dry-theta workspaces validated, observations ready, filter completed, posterior repairs completed, native moist-theta analyses reconstructed and validated, analysis/inflation checkpoint committed, and next advance completed. Record representation, conversion version and native-backing hashes at each transition. Native and analysis-only files must not share mutable paths. Generate explicit input/output file lists in member order. Build the radar and conventional selections independently under their own time policies, merge only validated records with consistent DART type definitions, and retain source identities in the committed report ledger. All required members must finish before filtering; do not silently replace a failed member with a copy of another member or reduce ensemble size.

**Agent evaluation.** Exercise a no-observation cycle, one real-volume analysis, the next 900-s advance, midnight, an hourly LBC transition and one interrupted run. Only an empty combined set is a no-observation cycle; an empty radar set with valid conventional data still runs filter. A valid empty combined set is logged explicitly; missing required model/LBC inputs are failures. Specify whether the no-observation path runs filter or passes through the prior and how inflation restarts are preserved.

**Human evaluation and output.** The workflow/HPC lead reviews failure and resume behavior. Output: a driver that can stop and resume from the last complete checkpoint without applying the same observations twice. The science lead reviews the first real increments and subsequent model response before a longer run.

### Step 4B Configure EAKF localization and adaptive inflation

**Work and code.** CONFIGURE the EAKF using the selected DART version's syntax. Recent DART versions expose per-quantity algorithms through QCEFF tables; older filter_kind=1 examples are version dependent. Record the effective EAKF and normal-variable-space configuration rather than pasting an older namelist without inspection. Use the supported distributed-state/MPI configuration for the full model. [DART QCEFF configuration][D13]

For height-based localization, configure the vertical coordinate and normalization explicitly. DART's cutoff is a half-width: an 18-km horizontal zero-weight distance corresponds to a 9-km half-width divided by DART's Earth radius in radians. For the same normalized metric, choose the height normalization so that 6 km at zero horizontal separation reaches zero weight. Verify the joint three-dimensional taper; its support is not necessarily a rectangular horizontal-radius/vertical-depth box. [DART localization][D14]

**Conventional localization.** Keep the preceding distances as radar settings. Define a separate conventional type/quantity policy covering environmental profiles, near-surface observations, AMVs and column PW. Table 5 of Dowell et al. reports a 300-km horizontal localization full width for HRRRDAS conventional observations and 18 km for radar, illustrating the different spatial scales. Those reported widths and its scale-height vertical localization are reference conventions, not values to paste directly into DART's radian half-width/height normalization. Resolve the intended physical support and the pinned release's per-type cutoff/vertical-handling capability before the first combined test. [HRRR Part I][A2]

DEVELOP `conventional_localization.yaml` and extend the one-observation test to at least one profile, surface and column-integrated type. Confirm that environmental horizontal influence, surface vertical influence and column-water responses follow the intended rule, and audit which state variables are updated by each type. Diagnose interactions between broad conventional and local radar increments. Do not automatically shrink all conventional influence to the radar footprint or apply a point-height interpretation to a full-column observation. Recheck DART observation-location caching when mixing cutoff distances.

Compile/use fill_inflation_restart and CONFIGURE adaptive prior inflation from a documented WRF example. Freeze initial mean/spread, damping, bounds and observation/region exclusions in `inflation_policy.yaml`. Save the evolving inflation mean and uncertainty fields at every committed cycle. Temperature inflation and its restart metadata refer to the dry-theta analysis quantity; do not relabel a moist-theta inflation state as compatible. Record the state schema and reset/rederive incompatible experimental inflation files explicitly before a new run. Do not reinitialize them unintentionally at each scheduler job.

**Agent evaluation.** Test the localization response with one controlled observation at several horizontal/vertical separations, including outside both support distances. Check the effective algorithm in logs, persistent inflation fields, field positivity where required, and changes across a restart. Count outlier rejections and operator failures separately from incoming-QC rejection.

**Human evaluation and output.** The DA lead accepts one coherent starting inflation configuration and reviews regional inflation growth/collapse against prior spread and innovations. Output: a verified EAKF/localization/inflation record. A parameter sweep is deferred until a specific diagnostic or planned sensitivity motivates it.

### Step 4C Return a usable physical analysis to WRF

**Work and code.** Implement `analysis_to_wrf.py` and `post_analysis_diagnostics.py` under Step 1B1. Finalize the prescribed bounds and mass–number/thermodynamic treatment in the dry-theta analysis representation; then merge declared updates into each complete native member backing state and reconstruct moist THM from final dry theta and QVAPOR. Reconcile required WRF diagnostic/coupled/time-level fields and preserve all carried-forward fields. A subsequent moisture or temperature repair must trigger reconstruction again. Persist `USE_THETA_M=1` in native outputs and refuse to advance from an analysis-only workspace. Count changed points and mass/water changes caused by repairs separately from the EAKF increments. Clipping negative hydrometeors alone is not a conservative or complete microphysical adjustment.

For the diagnostic reflectivity route, compare the statistically analyzed diagnostic with reflectivity independently recalculated from the physical analyzed state. Check consistency after prior inflation as well. NO_COPY_BACK controls writeback; it does not refresh microphysics. Standard serial DART computes initial observation equivalents and statistically updates remaining observation priors during the scalar loop; it does not normally rerun nonlinear microphysics after every scalar observation. This plan therefore requires a verified diagnostic/physical-state interface, not a rewrite of the EAKF loop. [DART WRF interface][D3], [DART filter flow][D15]

**Agent evaluation.** Confirm that intended dry-theta/wind/moisture/hydrometeor increments and the reconstructed native THM survive model continuation. Convert the native analysis back to dry theta and compare with the accepted posterior; evaluate posterior-minus-prior changes in both thermal representations. Check finite fields, temperature convention, pressure/geopotential consistency, reset diagnostics and water/mass repair budgets. Recompute physical observation equivalents after bounds and adjustments; do not interpret filter-only posterior diagnostics as proof that the continued WRF state has the same reflectivity.

**Human evaluation and output.** The microphysics and DA leads review representative increments and immediate adjustment for clear, convective and stratiform regions. Output: complete physical analysis files, raw-versus-repaired increment summaries, and regenerated diagnostic fields for restart and later downscaling.

### Step 4D Complete a multi-hour pilot and checkpoint recovery

**Work and code.** DEVELOP `cycle_health.py` and `make_phase_report.py` around DART obs_diag/obs_seq_to_netcdf and WRF logs. Run several hours spanning the development event, preserving prior and posterior states and enough subcycle output to expose adjustment. Freeze random draws and file hashes. Intentionally interrupt one cycle after partial output, then resume using only its last fully committed predecessor.

**Agent evaluation.** Report observation counts, accepted/rejected categories, prior/posterior innovations, observation-space spread plus observation error, inflation, increments, repair budgets and next-prior behavior by height and regime. Compare resumed and uninterrupted outputs within the declared numerical tolerance. Inspect surface-pressure tendency, divergence/vertical motion and boundary-origin disturbances relative to the no-update control.

**Human evaluation and output.** Review whether smaller posterior departures persist into the next prior and short forecasts, and whether spread remains informative. He et al. motivates separate balance diagnostics because forecast scores and imbalance can change differently; it does not validate 15-minute WRF cycling or prescribe IAU here. [He et al. 2020][A3]

**Phase 4 completion:** first a reproducible multi-hour, 50-member reflectivity-only engineering pilot; then a conventional-only smoke test and a combined pilot using the approved per-source cadence. The combined pilot must span subhourly conventional arrivals and pass continuation, one-use report accounting, per-family diagnostics and recovery checks. Persistent missing storms or underdispersion trigger perturbation/operator diagnosis; additive perturbations, latent-heating initialization or cloud clearing are separate documented developments if needed.

## Phase 5 Measure cost and evaluate the DA configuration

### Step 5A Profile the complete 50 member cycle

**Work and code.** DEVELOP `profile_cycle.py` using scheduler accounting, member logs and stage timers. Measure sparse-convection and widespread-precipitation intervals on the actual BNF grid. Separate HRRR/LBC preparation, radar and conventional decoding/QC/selection, WRF advance across all member batches, prior operators by family, EAKF updates, native-to-dry conversion, physical-state repair, dry-to-native reconstruction, diagnostics, I/O and orchestration. Measure the extra workspace storage and conversion memory explicitly; avoid retaining redundant full-state copies beyond the documented checkpoint policy. Rebenchmark the combined case: broadly localized conventional observations can have substantial update cost even when their count is much smaller than the radar count. Report overlapped stages with the actual elapsed critical path as well as their individual costs.

**Agent evaluation.** Record member concurrency, nodes/tasks/threads, precision, observation count, median and high-percentile elapsed times, peak memory, bytes read/written and core- or node-hours per simulated day. Include queue waiting and data arrival separately when relevant. Fifteen minutes of model time is the analysis interval; a 900-s wall-clock deadline is an additional requirement only if production needs it.

**Human evaluation and output.** The HPC lead identifies the measured bottleneck and available resource budget. The DA lead reviews whether any proposed sampling reduction changes scientific coverage. Output: a reproducible cost table and one justified optimization at a time. Do not lower the timestep, change precision, or alter sampling merely to make an unmeasured cost estimate look feasible.

The nominal mass-grid dimensions are approximately 549 × 389 × 149, or 31.82 million cells per three-dimensional scalar field; read the actual NetCDF dimensions for budgeting. Fifty members of one such field occupy about 12.7 GB at eight bytes/value. Twelve fields written at four bytes/value occupy about 76 GB per ensemble snapshot; saving both prior and posterior at all 96 daily cycles would be about 14.7 TB/day before additional fields, compression and metadata. These are arithmetic illustrations, not measured peak RAM or a storage-retention recommendation.

### Step 5B Run the controlled configuration comparisons

**Work and code.** DEVELOP `run_experiment_matrix.py` and `compare_experiments.py`. Use the baseline first, then change one factor per initial comparison. Keep physics, periods, error encoding, localization, verification and perturbation provenance matched.

| Experiment | Changed factor | What it answers |
| --- | --- | --- |
| DA50 | Radar only; 50 members; 5/15-km sampling; 15-minute cycle | Original radar baseline and attribution control. |
| C50 | Conventional only; per-source use of the 15-minute cycle | Environmental constraints supplied by conventional data. |
| DA50 conv | Radar plus conventional data, including eligible high-frequency reports every 15 minutes | Added value of the combined system. |
| DA50 conv hourly | Same radar cycling; conventional updates restricted to hourly analyses | Added value of subhourly conventional updates. |
| DA50 dense | 3/9-km sampling | Whether extra radar sampling adds useful information. |
| DA80 | 80 members at 5/15-km sampling | Whether improved covariance sampling/spread justifies ensemble cost. |
| DA50 clear12 | 5/12-km sampling, if needed | Sensitivity to additional no-echo constraints. |
| DA50 velocity | Add validated radar-specific radial velocity later | Incremental value of direct wind observations. |

Run the observation-set comparisons before a full combined-system density/member-size sweep. Explicitly label whether each dense/DA80/velocity test uses radar only or the selected combined observation suite; hold that suite fixed within the comparison. For the cadence test, first assign the same unique conventional report set to hourly versus 15-minute updates so the information set is controlled; preserve actual times and diagnose the larger offsets in the hourly run. If hourly preprocessing retains fewer reports, report that as a second practical comparison that changes both cadence and data volume.

Use the same raw random draws for the first 50 members where possible in the DA80 comparison, but record that recentering an 80-member set can change those members' final increments. Preserve a reproducible relationship; do not claim exact paired initial members if that is false. Benchmark additional real-observation workloads approaching 0.5 and 1 million observations if available; these are cost tests and do not mandate those counts in every cycle.

**Agent evaluation.** Produce configuration diffs proving what changed. Run the same masks, times and metrics on all experiments. Report quality gain alongside incremental node-hours, elapsed time and storage. Separate any later retuning from the first one-factor comparison.

**Human evaluation and output.** The DA and science leads select the observation suite, source-dependent cadence, and simplest ensemble/sampling configuration with defensible benefit at acceptable cost. Examine conventional innovation autocorrelation, station bias, profile consistency, spread/error and rejection rates alongside storm scores. Compare common held-out observations across suites; relabel assimilated conventional measurements as fit diagnostics. A denser posterior fit alone does not justify retaining more observations. Output: a ranked experiment report with reasons for retaining 50 or moving to 80 members, and for the chosen sampling.

### Step 5C Evaluate sustained analysis and forecast quality

**Data and code.** DEVELOP `verify_parent.py` and `collocate_observations.py`. Use full-resolution MRMS as a radar-fit/generalization diagnostic, withheld space/time blocks with documented separation, and available ARM/other independent measurements. Inventory soundings, surface pressure/T/q/winds, precipitation, cloud structure and wind profiles by case. Account for observation information already inherited through HRRR analyses; “not locally assimilated” is not proof of full independence. [Dowell et al. 2022][A2], [Hu et al. 2025][A4]

**Agent evaluation.** Compute consistent composite and height-resolved reflectivity comparisons, neighborhood scores, storm-object location/arrival/propagation, rainfall timing/amount, environmental wind and thermodynamic errors, and observed cold-pool signals. Score next-cycle priors and independent 30–60-minute forecasts from selected analyses with no further local DA. Label forecast tails that continue to use later HRRR analysis boundaries as retrospective boundary-constrained forecasts.

Use common plotting scales, observation support and terrain/coverage masks. Show results by event and regime, not only one pooled score. Quantify uncertainty by case or storm/time blocks; millions of correlated radar pixels do not supply millions of independent samples. Cloud-resolving fields without direct measurements remain physical plausibility diagnostics, not verified truth.

**Human evaluation and output.** Review matched movies, profiles and score distributions, prioritizing storm timing/placement and BNF inflow thermodynamics relevant to LES. Define the acceptable trade-offs before choosing the winner. The three cases support a pilot conclusion; wider regime coverage is needed for a broad production claim.

**Phase 5 completion:** a measured resource budget and a scientifically justified observation suite, cadence and ensemble/sampling configuration, evaluated on held-out periods/cases. This phase can reject DA configurations that run correctly but provide little persistent benefit.

## Phase 6 Demonstrate the benefit for LES forcing

### Step 6A Specify the parent trajectory and export convention

**Work and code.** DEVELOP `select_forcing_member.py` and `export_da_trajectory.py`. The original plan proposes one fixed member chosen by a rule set before the verification interval, with a small multi-member sensitivity and ensemble-mean diagnostics. A concrete simple pilot rule is a predeclared member ID; a representative-member rule may also be used if defined from permitted pre-evaluation information. Do not pick the best member retrospectively or switch member identities at successive export times.

Specify whether each exported analysis-time state is prior or posterior. Proposed first trial: posterior at the cycle timestamp, with the selected member advanced to provide the following interval. Archive both sides of the analysis jump so this convention can be evaluated. A fixed member still has DA insertion jumps; an ensemble mean can smooth displaced storms and is not automatically a dynamically consistent trajectory.

**Agent evaluation.** Check member identity, strictly ordered timestamps, duplicate handling, field completeness and agreement between prognostic fields and regenerated diagnostics. Compute prior-to-posterior jumps in wind, temperature, pressure, vapor and hydrometeors at every boundary-export time. Ensure restart and analysis labels cannot silently overwrite each other.

**Human evaluation and output.** The LES/modeling lead chooses the pilot trajectory and export-time convention before skill evaluation. Output: a complete, documented 2.5-km forcing sequence and a jump report. If the first convention drives excessive adjustment, test a dedicated reconstruction or short-forecast forcing strategy as a controlled alternative.

### Step 6B Generate matched 500 m inputs and boundaries

**Work and code.** Compile/reuse WRF `ndown.exe` and ADAPT the existing BNF preparation workflow as `make_les_forcing.sh`. DEVELOP `audit_les_forcing.py`. Export only the validated native moist-theta trajectory. Generate all history and auxiliary fields needed by the downscaling path from the same physical state; a compact DART state or observation-diagnostic file is not an ndown-ready parent history file. Match child grid, terrain, vertical coordinate, physics, surface initialization, start times and output/verification periods as closely as the forcing comparison permits. Record unavoidable differences. Explicitly set `use_theta_m=1` for H500, F500, D500 and any later 100-m WRF runs; audit THM/T/QVAPOR and boundary coupling after downscaling. Source HRRR/native field conventions must be converted through the verified preparation path rather than inferred from variable names.

| 500-m experiment | Forcing source | Role |
| --- | --- | --- |
| H500 | Hourly HRRRv4 analyses through the validated input preparation path, with no intervening 2.5-km integration. | Primary benchmark. |
| F500 | Free-running 2.5-km parent with hourly HRRR analysis LBCs and approximately 15-minute output. | Secondary comparison; include the DA-compatible coordinate control. |
| D500 | Selected radar-plus-conventional 2.5-km member/trajectory with approximately 15-minute forcing, if supported by Phase 5. | Candidate DA system. |
| D500 radar only | Original radar-only parent trajectory on a matched subset. | Attribution of the added conventional constraints. |

Do not force a 2.5-km integration into H500 merely to make file staging look uniform. A nonintegrated remapping/preparation step is compatible with the intended benchmark; adding a free WRF parent changes the question. The direct-HRRR route is an explicit implementation work package. [Original project plan][P1]

If a direct-HRRR child-preparation route is available, reuse and verify it. Otherwise, DEVELOP that route using WPS/real.exe on the 500-m target grid or an explicitly validated nonintegrated remapping into the required ndown input convention. Verify required atmospheric, soil, hydrometeor and aerosol fields and vertical coverage. The existing free-parent-to-ndown workflow does not itself establish that this direct preparation step is complete.

**Agent evaluation.** Check all IC/LBC dimensions, units, vertical levels, times, scalar coverage and boundary values/tendencies. Compare normal mass, moisture and heat transport and temporal jumps across the fine-domain boundaries. Run a short child continuation across several updates; verify no gaps or duplicate states.

**Human evaluation and output.** The LES lead reviews inflow sections, spinup and boundary-adjacent precipitation. Output: reproducible H500/F500/D500 input datasets and a preparation report. Coordinate changes in the parent must remain explicit in attribution; match the child's vertical configuration across the main comparisons.

### Step 6C Evaluate LES response and scientific value

**Data and code.** DEVELOP `verify_les.py` using the Phase 5 colocation/metric framework and BNF observations actually available for each case. Run the paired 500-m simulations with common verification windows. Carry the selected conventional cadence into D500 and keep a radar-only forcing comparison on a matched subset. Conventional-data assimilation is useful only if its environmental improvements help the BNF analysis/LES objectives at acceptable cost; selection is not automatic merely because HRRR used the source family. Score storm passage, organization, precipitation, cold-pool arrival/strength, cloud occurrence/vertical structure and environmental winds/thermodynamics. Add resolved turbulence or budget diagnostics when relevant, distinguishing observed evaluation from model-only plausibility checks.

**Agent evaluation.** Produce synchronized H500/F500/D500 movies, profiles and time series. Examine response immediately after forcing updates, spectra/tendencies around the 15-minute cadence, boundary-crossing storm propagation and persistence of early improvements. On a limited subset, compare more than one fixed DA member to gauge trajectory sensitivity. If necessary, add an hourly-output DA-forcing sensitivity to separate cadence from analysis-content effects. Interpolating HRRR hourly fields does not supply observed subhourly evolution.

**Human evaluation and output.** The science/LES leads judge D500 against H500 on the predeclared BNF objectives, with F500 as a secondary reference. A gain only over F500 does not meet the primary objective. Improvement in radar appearance must be weighed with thermodynamic, precipitation and adjustment behavior. Output: a case-based benefit assessment, limitations, and the selected forcing strategy.

**Phase 6 completion:** evidence that DA forcing improves relevant 500-m outcomes over direct hourly HRRR analyses without unacceptable adjustment artifacts, or a clear finding that it does not yet justify production. Extend the validated preparation and evaluation pathway to 100 m only after this gate, with its own resolution-appropriate spinup and turbulence assessment.

## Extend the observations and prepare production

### Extension A Add radar specific radial velocity

**Data.** Use NEXRAD Level-II or another identified radar-specific source containing radial velocity, radar position/altitude, range, azimuth/elevation, ray/gate time, Nyquist velocity and quality information. MRMS three-dimensional reflectivity does not provide the geometry needed to interpret a generic merged value as a radial-velocity observation. Keep overlapping radars distinct. [NCEI NEXRAD data][R4]

**Code.** INSTALL a maintained radar reader; ADAPT existing dealiasing/QC routines; DEVELOP `radar_velocity_qc.py`, `superob_velocity.py` and a DART observation writer. Reuse DART's radial-velocity observation type and operator after testing geometry, wind rotation, sign convention and reflectivity-weighted terminal fall speed. A Thompson reflectivity diagnostic alone does not prove that the required fall-speed diagnostic is available; a compatible diagnostic/operator adapter may require Fortran development and compilation. [DART radar operator][D7]

**Agent evaluation.** Use manufactured wind fields and known beam directions, including vertical-velocity/fall-speed checks, then compare raw/dealiased/retained real sweeps. Test superob support, timing and error variance and preserve per-radar provenance. **Human evaluation:** a radar expert reviews dealiasing failures, clutter, range effects, beam-height representativeness and the velocity operator. Output: a validated Vr pipeline followed by the controlled DA50 velocity experiment.

### Extension B Add ARM and research observations

**Data and code.** Inventory actual BNF datastream operation dates, instrument calibration, processing levels and Data Quality Reports. ADAPT the reader/converter for each instrument's scan geometry and metadata; reuse common observation policy and diagnostics where appropriate. Availability for a particular 2025 case is checked, not assumed. [ARM data inventory task][R5]

**Agent evaluation.** Test time/height/geolocation, units, calibration flags and independent provenance; preserve a defined verification subset as instruments are added. **Human evaluation:** the instrument/radar lead reviews attenuation, clutter, calibration and representativeness, and the DA lead approves the added error/QC policy. Output: one instrument-specific validation record and an incremental-value experiment per addition.

### Production package

**Code and data.** DEVELOP `archive_case.py` and a reproducibility report. Archive source manifests/hashes, the HRRR target-versus-implemented conventional matrix, native timestamps/averaging support, report corrections/deduplication and cycle-assignment ledger, resolved configurations, executable provenance, seeds and member assignments, observation selections/rejections, inflation checkpoints, cycle status, important increments/repairs, the selected forcing identity, final forcing files and cost summaries. Set full-ensemble retention from measured storage costs; retain sufficient completed checkpoints to reproduce intervening analysis and forcing output.

**Agent evaluation.** Restore one archived pilot and reproduce a selected cycle and forcing interval from its records. Check the resume policy for unavailable observations and failed members, and test production filename/time conventions. **Human evaluation:** the project lead accepts the scientific scope, resource/retention budget and documented limitations. No broad production claim follows merely from a successful pilot.

## Implementation backlog and first milestones

The following consolidated inventory makes the principal code commitments easy to assign. Names for new files are proposed; upstream scripts keep their original names in the vendor/source tree and are adapted in a versioned project copy.

| Work package | Existing starting point | New or adapted project deliverable |
| --- | --- | --- |
| Build and configuration | WRF/WPS builds; DART `quickbuild.sh` and mkmf.template | ADAPT `build_stack.sh`; DEVELOP `audit_configuration.py`, `software_lock.json` and `experiment.yaml`. |
| Mean IC/LBC preparation | Existing BNF WPS scripts; DART `gen_retro_icbc.sh` | ADAPT `prepare_hrrr_mean.sh`; DEVELOP endpoint/time manifest checks. |
| Model interface | DART WRF model_mod and radar module | ADAPT/RECOMPILE the explicit dry-theta state mode; DEVELOP `state_contract.yaml` and `audit_wrf_state.py`. |
| Thermodynamic conversion | MPAS–DART architecture; native WRF input/restart routines | DEVELOP `theta_conversion.py`, `wrf_to_dart.py`, `analysis_to_wrf.py`, `check_theta_handoff.py` and `thermodynamic_contract.yaml`; ADAPT/COMPILE a WRF continuation hook only if needed. |
| Reflectivity ingestion | Product reader libraries; DART observation APIs | DEVELOP `stage_mrms.py`, `decode_mrms.py`, `classify_reflectivity.py`, `thin_reflectivity.py`, `select_volume.py` and `mrms_to_obs_seq.f90`. |
| Conventional acquisition | HRRR/RAP dumps, NCEP PREPBUFR, MADIS and source-specific archives | DEVELOP `inventory_conventional.py` and source/cadence manifests; reconcile subtype coverage. |
| Conventional conversion | DART `prepbufr.x`, `create_real_obs`, MADIS and GPSPW converters | DOWNLOAD/COMPILE; ADAPT `convert_conventional.sh`; DEVELOP missing subtype/operator adapters and conversion audits. |
| Conventional scheduling and QC | Native report metadata and DART observation utilities | DEVELOP `assign_conventional_cycles.py`, `deduplicate_reports.py`, `conventional_policy.yaml` and error/QC rules. |
| Perturbation generation | WRFDA `da_wrfvar.exe`; `gen_pert_bank.sh`; NCO | ADAPT generation namelist/script; DEVELOP `wrfda_bank_adapter.py`, explicitly dry-theta increments, seed/bank manifest and statistics. |
| Initial ensemble | `add_bank_perts.ncl`; `init_ensemble_var.sh` | ADAPT application/scaling; DEVELOP `assign_perturbations.py` and `recenter_perturbations.py`. |
| Member boundaries | DART pert_wrf_bc and `new_advance_model.sh` | ADAPT/RECOMPILE moist endpoint and native tendency handling; DEVELOP `prepare_moist_boundaries.py` and `audit_boundaries.py`. |
| Cycling | `driver.sh`, `assimilate.sh`, `assim_advance.sh` | ADAPT scheduler/advance routines; DEVELOP `cycle_driver.py` with transactional checkpoints. |
| Physical analysis | DART state bounds; verified WRF diagnostics | DEVELOP `analysis_to_wrf.py` and `post_analysis_diagnostics.py` as required by the interface contract. |
| Diagnostics and performance | DART obs_diag, obs_seq_to_netcdf; scheduler logs | DEVELOP `cycle_health.py`, `profile_cycle.py`, `run_experiment_matrix.py` and `make_phase_report.py`. |
| Parent and LES evaluation | Existing comparison scripts and observations | DEVELOP common colocation, `verify_parent.py`, `verify_les.py` and experiment comparison reports. |
| Downscaling | Existing BNF preparation; WRF `ndown.exe` | ADAPT `make_les_forcing.sh`; DEVELOP member selection/export and `audit_les_forcing.py`. |

**Recommended execution order.** First complete one regenerated moist-theta deterministic control, the explicit patched dry-theta DART interface, and the Step 1B1 conversion/continuation tests. Then complete one model/operator update test. The temperature handoff is on the critical path; native integration with `use_theta_m=0` is not a substitute milestone. In parallel, decode and validate one MRMS volume and inventory conventional report cadence, validating one report from each initial family. Next verify one WRFDA perturbation draw and one member-boundary interval before generating the full bank and 50 members. Then run one complete 50-member analysis/advance, followed by the multi-hour pilot and interruption/recovery test. Then add the conventional-only and combined pilot checks, including several distinct subhourly reports and mixed/empty stream cases. Measure the selected suite’s cost, make a small 500-m forcing demonstration, and only then expand the sensitivity matrix and case set.

This order prevents a boundary, timestamp or state-variable error from being replicated through a large ensemble. It is an engineering sequence; it does not introduce a requirement to optimize every scientific parameter before the first pilot.

For each completed work package, the agent supplies code/configuration diffs, the exact command or job, input/output identities, checks with measured results, and a short figure set where physical judgment is required. The human reviewer records the scientific decision and rationale. A passed automated check means the specified test passed; it does not replace scientific evaluation.

## Configuration and driver contracts

The example below is a project configuration sketch, not a drop-in WRF or DART namelist. Items marked null require a documented implementation choice or a value read from the real files. The driver should reject unresolved required fields before launching a scientific experiment.

```yaml
experiment_id: bnf_da50_pilot
software:
  wrf_commit: 06d4240a  # expand to full SHA and record patches
  dart_commit: null    # select, freeze, and use matching syntax
domain:
  max_dom: 1
  e_we: 550
  e_sn: 390
  e_vert: 150
  dx_m: 2500
  dy_m: 2500
  model_timestep_s: 5
  hybrid_opt: 0
  use_theta_m: 1       # required for every project WRF integration
thermodynamics:
  design: dry_theta_analysis_moist_theta_dynamics
  native_temperature_field: THM
  dart_temperature_field: THETA_DRY_PERT  # project field; patched interface required
  dart_temperature_quantity: QTY_POTENTIAL_TEMPERATURE
  analysis_schema: dry_theta_analysis_v1
  conversion_contract: thermodynamic_contract.yaml
  theta_reference_k: null  # read/verify pinned WRF definition; not base_temp
  rv_over_rd: null        # exact pinned WRF constants
  dart_interface_patch: null
  continuation_path: null  # verified wrfinput or full-restart contract
  reconstruct_after_final_repairs: true
  native_use_theta_m_required: 1
  validation_report: null  # must pass Step 1B1 before scientific cycling
ensemble:
  members: 50
  perturbation_method: WRFDA_RANDOMCV_CV3
  bank_size: 150
  experiment_seed: null
  member_assignment_manifest: null
  spinup_start_utc: null
  lbc_temporal_policy: fixed_member_bank_pattern  # proposed pilot policy
cycling:
  interval_seconds: 900
  first_analysis_utc: null
  last_analysis_utc: null
  prior_inflation_policy: null
observations:
  radar: MRMS_3D_reflectivity
  conventional_enabled: true
  conventional_target: HRRRv4_CONUS_families
  conventional_inventory: hrrr_conventional_inventory.yaml
  conventional_policy: conventional_policy.yaml
  conventional_cycle_opportunity_seconds: 900
  conventional_instantaneous_assignment: nearest_cycle_half_open_15min
  conventional_max_offset_seconds: 450  # proposed; averaging products differ
  preserve_native_time_and_support: true
  assimilate_each_physical_report_once: true
  volume_window_seconds: 150
  sample_precip_km: 5
  sample_noecho_km: 15
  retained_heights_msl_m: null
  error_and_qc_policy: null
  time_approximation: synchronous_nearest_volume
localization:
  radar:
    horizontal_zero_weight_km: 18
    vertical_zero_weight_km: 6
  conventional_type_specific_policy: null  # define before combined filtering
forcing:
  selected_member: null
  exported_state: posterior  # proposed first trial
  interval_seconds: 900
```

The main driver contract is deliberately explicit about restart and observation reuse. These are high-level calls to the work packages above, not implemented function definitions.

```python
for analysis_time in configured_analysis_times:
    if analysis_checkpoint_is_complete_and_verified(analysis_time):
        physical_analysis = load_committed_analysis(analysis_time)
        inflation = load_committed_inflation(analysis_time)
    else:
        native_priors = obtain_all_member_priors(analysis_time)
        assert_native_moist_states_member_ids_fields_and_times(native_priors)
        dry_priors = wrf_to_dart(native_priors, thermodynamic_contract)
        validate_dry_analysis_schema_and_conversion(dry_priors, native_priors)
        radar = obtain_validated_radar_selection(analysis_time)
        conventional = select_new_conventional_reports(
            analysis_time, source_time_support_and_qc_policies
        )
        obs = merge_and_validate_type_definitions(radar, conventional)
        assert_physical_reports_not_previously_assimilated(obs)
        inflation_in = obtain_previous_inflation_or_initial_policy(analysis_time)

        if obs.is_empty:
            dry_analysis, inflation = apply_documented_no_obs_policy(
                dry_priors, inflation_in
            )
        else:
            dry_analysis, inflation = run_patched_dart_filter(
                dry_priors, obs, inflation_in
            )

        accepted_dry_analysis = apply_recorded_bounds_and_consistency_rules(
            dry_analysis  # finalize paired dry theta and vapor here
        )
        physical_analysis = analysis_to_wrf(
            accepted_dry_analysis, native_priors, thermodynamic_contract
        )  # reconstruct moist THM and reconcile the native continuation state
        validate_native_to_dry_round_trip(physical_analysis, accepted_dry_analysis)
        assert_native_use_theta_m_is_one(physical_analysis)
        report = evaluate_cycle(native_priors, physical_analysis, obs, inflation)
        require_engineering_checks_pass(report)
        commit_analysis_atomically(
            physical_analysis, inflation, obs.identities, report
        )

    next_time = analysis_time + timedelta(seconds=900)
    if next_time <= configured_last_analysis:
        if not advance_is_complete_and_verified(analysis_time, next_time):
            assert_native_moist_state_contract(physical_analysis)
            boundaries = prepare_member_boundaries(
                physical_analysis, analysis_time, next_time, thermodynamic_contract
            )
            advance_all_members(physical_analysis, boundaries, next_time)
            verify_and_commit_next_priors(next_time)
```

Checkpoint recovery must use the committed native moist-theta physical state, dry-analysis schema/conversion version, compatible inflation and observation identities. Keep the accepted dry posterior or a reproducible reconstruction record as specified by the diagnostic-retention policy. Never resume WRF from a dry analysis workspace. Export/verification jobs can consume committed cycles asynchronously; they must never consume half-written filter output.


## Sources and decision provenance

Project decisions, upstream software behavior and scientific precedent have different roles. The numerical baseline comes from the original project plan and current user direction. Upstream documentation/source establishes how software components work. Papers motivate diagnostics or supply examples; they do not establish that the complete BNF configuration has been validated.

### P1 Original plan

**LASSO_BNF_DA_Implementation_Plan.docx**, created 10 September 2026, six pages. Baseline configuration on page 1; Phases 1–6 on pages 2–5; unresolved implementation choices on page 6. This detailed plan retains that sequence and primary direct-HRRR comparison.

### P2 Review record

**lasso_bnf_da_chat_transcript.md**, saved 11 September 2026. Records the user-supplied WRF commit/configuration, clarification that starting sampling choices remain unchanged, explanation of the five radar configuration items, and correction of incorrectly attached Honda citations. The reviewed numerical HRRR example referred to HRRR snapshot `44728d00`; it is used here as a recorded precedent and proposed recipe, not asserted as a BNF decision or a newly verified operational HRRR configuration.

### P3 Model configuration and current update

**namelist.input.rund1-dynlit**, supplied 11 September 2026, read directly for the domain, physics, coordinate, I/O and boundary settings. On 12 September the user authorized switching to the WRF-DART-supported coordinate if necessary; this implementation adopts `hybrid_opt=0`. The user also requested Markdown for this detailed plan. On 16 September the user explicitly required `use_theta_m=1` in WRF and selected the MPAS-style approach of dry-theta analysis followed by moist-theta reconstruction. This supersedes the former proposed `use_theta_m=0` baseline and selects conversion rather than direct moist-theta analysis as the implementation design. The supplied `theta_m_chat.md` clarifies upstream history; the user’s current instruction establishes this project decision. The conversion/interface code and validation remain work to implement. The 13 September update adds an HRRRv4-based conventional observation target and the user’s direction to exploit high-frequency sources in 15-minute cycles; this supersedes the briefly proposed blanket hourly-conventional schedule.

### Software sources

The following links were checked as implementation references on 12 September 2026. DART documentation pages may display differing release labels. The reviewed source snapshot `7bbd35a0995726b0274dc73a1b5783979d0f42d9` provides a reproducible reference for the cited ensemble scripts; the production DART version still needs to be selected and frozen. Do not combine release-specific syntax without checking the selected source.

| ID | Source | Supported use in this plan |
| --- | --- | --- |
| D1 | [Official WRF source](https://github.com/wrf-model/WRF) | Source/build provenance; use the user's pinned source and patches. |
| D2 | [DART WRF tutorial, version 11.25.2](https://docs.dart.ucar.edu/en/v11.25.2/models/wrf/tutorial/README.html) | Installation/template workflow and upstream limitations. Its dry-theta temperature recipe is superseded by this project’s Step 1B1 requirement. It was tested with a different WRF configuration. |
| D3 | [DART WRF interface](https://docs.dart.ucar.edu/en/latest/models/wrf/readme.html) | Model-state mappings, bounds and WRF interface constraints. |
| D4 | [Official WPS source](https://github.com/wrf-model/WPS) | Preprocessing software acquisition. |
| D5 | [DART build guide](https://docs.dart.ucar.edu/en/latest/guide/quickbuild.html) | Building the pinned DART executables. |
| D6 | [WRF namelist documentation](https://www2.mmm.ucar.edu/wrf/users/wrf_users_guide/build/html/namelist_variables.html) | I/O formats, restart interval units and model configuration meanings. |
| D7 | [DART radar observation module](https://docs.dart.ucar.edu/en/latest/observations/forward_operators/obs_def_radar_mod.html) | Reflectivity/fall-speed diagnostics, floor controls and radial-velocity metadata/operator. |
| D8 | [DART quality-control module](https://docs.dart.ucar.edu/en/latest/assimilation_code/modules/assimilation/quality_control_mod.html) | Input QC versus innovation screening and rejection diagnostics. |
| D9 | [Pinned gen_pert_bank.sh](https://github.com/NCAR/DART/blob/7bbd35a0/models/wrf/shell_scripts/gen_pert_bank.sh) | WRFDA RANDOMCV bank generation and extraction of increments. |
| D10 | [Pinned add_bank_perts.ncl](https://github.com/NCAR/DART/blob/7bbd35a0/models/wrf/shell_scripts/add_bank_perts.ncl) | Bank selection and application/scaling; need for deterministic project assignment and centering. |
| D11 | [Pinned pert_wrf_bc.f90](https://github.com/NCAR/DART/blob/7bbd35a0/models/wrf/WRF_BC/pert_wrf_bc.f90) | Boundary utility and field/temperature audit. See also [DART issue 807](https://github.com/NCAR/DART/issues/807). |
| D12 | [Pinned new_advance_model.sh](https://github.com/NCAR/DART/blob/7bbd35a0/models/wrf/shell_scripts/new_advance_model.sh) | Member advance/staging template requiring BNF and subhourly adaptation. |
| D13 | [DART QCEFF documentation](https://docs.dart.ucar.edu/en/v11.25.1/guide/qceff_probit.html) | Version-dependent per-quantity algorithm configuration. |
| D14 | [DART assimilation tools](https://docs.dart.ucar.edu/en/latest/assimilation_code/modules/assimilation/assim_tools_mod.html) | Localization half-width and normalization. |
| D15 | [DART filter execution flow](https://docs.dart.ucar.edu/en/latest/assimilation_code/programs/filter/filter.html#detailed-program-execution-flow) | Observation-equivalent evaluation and serial statistical updates. |

Additional code references for implementation: [initial ensemble script](https://github.com/NCAR/DART/blob/7bbd35a0/models/wrf/shell_scripts/init_ensemble_var.sh), [WRFDA perturbation namelist template](https://github.com/NCAR/DART/blob/7bbd35a0/models/wrf/tutorial/template_nest/namelist.input.3dvar), [DART issue 661 on WRF temperature representation](https://github.com/NCAR/DART/issues/661), and [model_mod_check](https://docs.dart.ucar.edu/en/latest/assimilation_code/programs/model_mod_check/model_mod_check.html).

### Thermodynamic interface sources and decision added 16 September

These pinned sources establish the upstream limitation and MPAS precedent. The proposed `THETA_DRY_PERT` field, interface mode and scripts are BNF development specifications, not existing upstream features. The working design is selected by the user; its implementation has not yet been validated.

| ID | Source | Supported use and limit |
| --- | --- | --- |
| T1 | [DART WRF model_mod at 7bbd35a0][T1] | THM-only and USE_THETA_M=0 guards near lines 700–727; dry-theta pressure calculation near 5056–5099. These checks require an explicit project interface adaptation. |
| T2 | [DART MPAS model_mod at 7bbd35a0][T2] | `theta_to_tk` and `compute_full_pressure` near 7378–7463 consume dry theta, dry density and vapor; design precedent for analysis variables. |
| T3 | [MPAS DA restart at f34984b2][T3] and [DART MPAS documentation](https://docs.dart.ucar.edu/en/latest/models/mpas_atm/readme.html) | MPAS calls coupled-field reconstruction under its DA-cycling option. This option is not a WRF namelist setting. |
| T4 | [MPAS atm_init_coupled_diagnostics at f34984b2][T4] | Reconstructs moist theta and density-coupled/pressure fields from updated uncoupled variables; WRF needs its own corresponding implementation. |
| T5 | [DART v11.8.2 WRF tutorial][T5] | Historical THM requirement still paired with use_theta_m=0; field-name change did not implement moist-theta support. |

### Data sources

| ID | Source | What still needs checking for BNF |
| --- | --- | --- |
| R1 | [NOAA MRMS three-dimensional reflectivity inventory](https://mrms.ncep.noaa.gov/3DRefl/) | Exact product, height semantics and slice/time coverage. |
| R2 | [NOAA MRMS archive catalog](https://registry.opendata.aws/noaa-mrms-pds/) | Exact historical objects and completeness for the selected 2025 windows. |
| R3 | [NOAA HRRR archive catalog](https://registry.opendata.aws/noaa-hrrr-pds/) | Hourly analysis files and all fields required by the established BNF preparation. |
| R4 | [NCEI NEXRAD documentation and historical access](https://www.ncei.noaa.gov/products/radar/next-generation-weather-radar) | Radar-specific Level-II velocity, scan/time geometry and QC. |
| R5 | ARM Data Discovery and instrument Data Quality Reports | Actual BNF datastreams, operation dates, quality and calibration for each case. This is a planned inventory task. |

### Scientific sources inspected

| ID | Source | Specific use and limit |
| --- | --- | --- |
| A1 | Supplied Dowell 2020, **HRRR Data-Assimilation System and HRRRE Forecasts**, especially the IC/LBC perturbation discussion on PDF pages 2–3 and radar/microphysics treatment sections. | Boundary-adjustment and mass–number precedents. HRRRDAS's initialization and member-management recipe is not identical to this CV3/continuous-cycling baseline. |
| A2 | [Dowell et al. 2022, HRRR Part I](https://doi.org/10.1175/WAF-D-21-0151.1), supplied PDF page 2 and pages 10–11, journal pages 1372 and 1380–1381, section 3 and Table 5. | Conventional family inventory, CONUS radiance exclusion, TCVitals addition and differing conventional/radar localization; HRRRDAS context: 36 members, hourly cycling and 6/12-km reflectivity thinning. BNF sizes, sampling and 15-minute source use are project choices. |
| A3 | [He et al. 2020](https://doi.org/10.1029/2020MS002187), supplied PDF pages 11–13. | Motivation to measure imbalance separately from forecast skill. Their idealized/global-model experiments do not validate 15-minute WRF cycling. |
| A4 | [Hu et al. 2025](https://doi.org/10.1002/qj.4933), supplied PDF pages 3–5 and 19. | Verification-reference dependence, correlated errors and displacement-aware assessment. Metric priorities and pass criteria here are BNF implementation choices. |

### Conventional observation implementation sources added 13 September

| ID | Source | Specific use and limit |
| --- | --- | --- |
| C1 | [HRRR deterministic analysis script at the 24 May 2022 snapshot](https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/scripts/conus/exhrrr_analysis.sh) | PREPBUFR and separate satellite-wind staging; VAD and Level-II velocity pathways. Effective subtype use still requires the matching external `convinfo`/error configuration and accepted diagnostics. Staging is not proof of assimilation. |
| C2 | [NCAR GDEX NCEP ADP Global Upper Air and Surface Weather Observations](https://gdex.ucar.edu/datasets/d337000/) | Operational observation/PREPBUFR archive candidate. Check the selected 2025 files and subtype content; it is not an assertion of complete HRRR input parity. |
| C3 | [NOAA MADIS](https://madis.ncep.noaa.gov/) | Integrated conventional-data access and source inventory. Verify archived cadence, observation support and available data streams for BNF cases. |
| C4 | [DART NCEP PREPBUFR decoder](https://docs.dart.ucar.edu/en/latest/observations/obs_converters/NCEP/prep_bufr/prep_bufr.html) | Existing first-stage decoder/build and the need to adapt legacy format/report coverage. |
| C5 | [DART create_real_obs](https://docs.dart.ucar.edu/en/latest/observations/obs_converters/NCEP/ascii_to_obs/create_real_obs.html) | Second-stage conversion, selection semantics, moisture representations and preserving observation times. |
| C6 | [DART MADIS converters](https://docs.dart.ucar.edu/en/latest/observations/obs_converters/MADIS/MADIS.html) | Existing platform-specific converters, example scripting and windowing/field-selection cautions. |
| C7 | [DART GPSPW converter](https://docs.dart.ucar.edu/en/latest/observations/obs_converters/GPSPW/README.html) | Existing GPS precipitable-water converter directory; the actual source schema and WRF column operator still require validation. |

The conventional update uses the HRRRv4 paper for the documented observation families and algorithm distinctions, source code for input-routing details, and DART documentation for converter behavior. The proposed nearest-15-minute assignment, one-use ledger and experiment matrix are BNF implementation choices. Actual high-frequency coverage and error correlation remain measurements to make from the selected archives.

[P1]: #p1-original-plan
[P2]: #p2-review-record
[P3]: #p3-model-configuration-and-current-update
[D1]: https://github.com/wrf-model/WRF
[D2]: https://docs.dart.ucar.edu/en/v11.25.2/models/wrf/tutorial/README.html
[D3]: https://docs.dart.ucar.edu/en/latest/models/wrf/readme.html
[D4]: https://github.com/wrf-model/WPS
[D5]: https://docs.dart.ucar.edu/en/latest/guide/quickbuild.html
[D6]: https://www2.mmm.ucar.edu/wrf/users/wrf_users_guide/build/html/namelist_variables.html
[D7]: https://docs.dart.ucar.edu/en/latest/observations/forward_operators/obs_def_radar_mod.html
[D8]: https://docs.dart.ucar.edu/en/latest/assimilation_code/modules/assimilation/quality_control_mod.html
[D9]: https://github.com/NCAR/DART/blob/7bbd35a0/models/wrf/shell_scripts/gen_pert_bank.sh
[D10]: https://github.com/NCAR/DART/blob/7bbd35a0/models/wrf/shell_scripts/add_bank_perts.ncl
[D11]: https://github.com/NCAR/DART/blob/7bbd35a0/models/wrf/WRF_BC/pert_wrf_bc.f90
[D12]: https://github.com/NCAR/DART/blob/7bbd35a0/models/wrf/shell_scripts/new_advance_model.sh
[D13]: https://docs.dart.ucar.edu/en/v11.25.1/guide/qceff_probit.html
[D14]: https://docs.dart.ucar.edu/en/latest/assimilation_code/modules/assimilation/assim_tools_mod.html
[D15]: https://docs.dart.ucar.edu/en/latest/assimilation_code/programs/filter/filter.html#detailed-program-execution-flow
[R1]: https://mrms.ncep.noaa.gov/3DRefl/
[R2]: https://registry.opendata.aws/noaa-mrms-pds/
[R3]: https://registry.opendata.aws/noaa-hrrr-pds/
[R4]: https://www.ncei.noaa.gov/products/radar/next-generation-weather-radar
[R5]: #data-sources
[A1]: sandbox:/workspace/scratch/3fec62119c37/project_sources/01-Dowell-2020-HRRR-Data-Assimilation-System-HRRRDAS-and-HRRRE-Forecasts.pdf
[A2]: https://doi.org/10.1175/WAF-D-21-0151.1
[A3]: https://doi.org/10.1029/2020MS002187
[A4]: https://doi.org/10.1002/qj.4933
[C1]: https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/scripts/conus/exhrrr_analysis.sh
[C2]: https://gdex.ucar.edu/datasets/d337000/
[C3]: https://madis.ncep.noaa.gov/
[C4]: https://docs.dart.ucar.edu/en/latest/observations/obs_converters/NCEP/prep_bufr/prep_bufr.html
[C5]: https://docs.dart.ucar.edu/en/latest/observations/obs_converters/NCEP/ascii_to_obs/create_real_obs.html
[C6]: https://docs.dart.ucar.edu/en/latest/observations/obs_converters/MADIS/MADIS.html
[C7]: https://docs.dart.ucar.edu/en/latest/observations/obs_converters/GPSPW/README.html

[T1]: https://github.com/NCAR/DART/blob/7bbd35a0995726b0274dc73a1b5783979d0f42d9/models/wrf/model_mod.f90
[T2]: https://github.com/NCAR/DART/blob/7bbd35a0995726b0274dc73a1b5783979d0f42d9/models/mpas_atm/model_mod.f90
[T3]: https://github.com/MPAS-Dev/MPAS-Model/blob/f34984b2c89353cf31c235b08d3b4acd96b37bb3/src/core_atmosphere/mpas_atm_core.F#L515-L530
[T4]: https://github.com/MPAS-Dev/MPAS-Model/blob/f34984b2c89353cf31c235b08d3b4acd96b37bb3/src/core_atmosphere/dynamics/mpas_atm_time_integration.F#L7538-L7649
[T5]: https://github.com/NCAR/DART/blob/v11.8.2/models/wrf/tutorial/README.rst#L23-L29
