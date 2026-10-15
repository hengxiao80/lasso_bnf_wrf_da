# Project review, 2026-10-15

A stock-take while waiting for nodes for the first observation-expansion runs. It summarizes what has been done since
2026-09-17, what the 5-member pilot set up and found, and where the observation expansion stands, then lists every
script, patch, note, simulation and observation dataset in the project (Sec. 6). The detail lives in the linked notes;
this file only points to it. Links are relative to `notes/`. Data directories are not in git, but the links work on
Cirrus. Sizes are `du -sh` on 2026-10-15 (GPFS allocation, which can be below the byte count the notes quote).

## 1. At a glance

| Area | State on 2026-10-15 |
|---|---|
| Software | WRF v4.8.0 (`06d4240a`), WPS v4.6.0, WRFDA, DART v11.25.3 (`7bbd35a09`) built; 2 WRF patches, 1 WPS build fix, 7 DART patches ([`patches/README.md`](../patches/README.md), [`software_lock.json`](../software_lock.json)) |
| Case | 2025-05-20 (LASSO BNF), 2.5 km, 550 × 390 × 150, 05-19 00Z → 05-22 00Z, HRRR-driven |
| Free runs | `baseline` (θm = 1), `hybrid2` (hybrid_opt = 2), `theta_m0` (θm = 0): all 72 h, done; evaluated in `../bnf_wrf_eval` |
| DA setup | `theta_m0` (temporary; target is `use_theta_m = 1`), 5 members, 15-min EAKF cycling with true WRF restarts |
| Pilot | Steps 1–13 done: 1-hour pilot (00:00 cold start + 4 analyses) passed 2026-10-03 in four variants |
| Observations | MADIS METAR/ACARS/radiosonde (+ marine, unused) in use; METAR and mesonet errors set to NCEP values; mesonet and MRMS reflectivity built and wired in, **not yet run** |
| Next | Runs 1–4 of the test matrix ([`obs_expansion.md`](obs_expansion.md) §9), waiting for 40 free nodes; then step 14, the extension |
| Git | Everything committed (43 commits, latest `1a26194`); only the two Dowell PDFs in `notes/` untracked |

## 2. Timeline

| Dates | Work | Where recorded |
|---|---|---|
| 09-12 | Plan written (Codex) | [`initial_plan_from_codex/`](../initial_plan_from_codex/LASSO_BNF_DA_Detailed_Implementation_Plan_rev2.md) |
| 09-17 → 09-20 | Builds (WRF TEMPO fix, WPS link fix), WPS + `real.exe` pipeline, comparison with sey's files (bit-identical), I/O and decomposition tests, the three free runs | [`patches/README.md`](../patches/README.md), [`CLAUDE.md`](../CLAUDE.md), [`cases/20250520/iotest/`](../cases/20250520/iotest) |
| 09-21 | Decision: develop DA with `theta_m0` first (stock DART needs `USE_THETA_M = 0`) | [`CLAUDE.md`](../CLAUDE.md) |
| 09-22 → 09-25 | DART namelist walkthrough, tutorial read and adapted, workflow layout, `r8 = r4` and ACARS-humidity patches (radiosonde converter patch 09-29), MADIS data downloaded | [`dart_namelist_discussion_log.md`](dart_namelist_discussion_log.md), [`wrf_dart_tutorial_adaptation.md`](wrf_dart_tutorial_adaptation.md), [`da_workflow_layout.md`](da_workflow_layout.md) |
| 09-29 → 10-01 | Pilot steps 1–7: mean ICs, perturbation bank, members, member boundaries, restart tests; hydrostatic-PH fix; `-fp-model precise` DART | [`da_5member_pilot_steps.md`](da_5member_pilot_steps.md) |
| 10-02 → 10-03 | Steps 8–13: boundary refit, MADIS conversion, per-cycle obs, filter namelist + gate, cycle scripts, 1-hour pilot (4 runs); `HYDROSTATIC_PH=1` default | same |
| 10-03 | Observation expansion begins: HRRRDAS inventory, error comparison, METAR errors → NCEP, radial-velocity groundwork | [`obs_expansion.md`](obs_expansion.md) §1–6, [`obs_error_diagnostics.md`](obs_error_diagnostics.md) |
| 10-12 → 10-14 | Mesonet: profile, how HRRR/HRRRDAS/RRFS select stations, per-cycle selection, RAP/RRFS errors, wired in | [`obs_expansion.md`](obs_expansion.md) §7, [`mesonet_station_selection.md`](mesonet_station_selection.md) |
| 10-14 → 10-15 | MRMS: HRRR converter read and ported to Python, `REFL_10CM` into `wrfrst` (WRF patch), two-pass and one-pass filter wiring, QNRAIN rule, run plan, filter timing and scaling test | [`obs_expansion.md`](obs_expansion.md) §8–9, hand-offs in [`handoffs/`](handoffs) |

## 3. Before DA: software, pipeline and free runs

- **Builds** in `../software/{WRF,WPS,WRFDA,DART}`, dm+sm Intel 19.1.3 / OpenMPI 4.0.4 ([`scripts/env_wrf.sh`](../scripts/env_wrf.sh)). Pins, checksums and patch list: [`software_lock.json`](../software_lock.json), written by [`scripts/audit_configuration.py`](../scripts/audit_configuration.py).
- **WPS pipeline** on HRRR native-level analyses: GRIB links, ungrib in time chunks, metgrid, level reversal ([`cases/20250520/wps/`](../cases/20250520/wps)); 73 hourly `met_em` files. Ungrib and metgrid outputs identical to sey's; our `hybrid_opt = 2` `wrfinput`/`wrfbdy` bit-identical to his.
- **I/O tests** A–K ([`cases/20250520/iotest/`](../cases/20250520/iotest), [`scripts/make_wrf_iotest.py`](../scripts/make_wrf_iotest.py), [`scripts/summarize_wrf_timing.py`](../scripts/summarize_wrf_timing.py)): settled on 16 nodes, 16 × 16 decomposition, `io_form_history = 2` with classic netCDF, no quilting, and the wrf.exe UCX settings.
- **Free runs** (72 h, 15-min history, 289 files each): `baseline`, `hybrid2`, `theta_m0`; layer-thickness comparison [`figures/layer_thickness_20250520_1200.png`](../cases/20250520/figures/layer_thickness_20250520_1200.png). Their evaluation against GOES/MRMS/HRRR is in `../bnf_wrf_eval`, not here.

## 4. The 5-member pilot (`cases/20250520/da_theta_m0/`)

Full record: [`da_5member_pilot_steps.md`](da_5member_pilot_steps.md) (steps 1–14, monitoring list, decisions Q1–Q18).

### 4.1 What the system is

| Piece | Setup | Built by |
|---|---|---|
| Mean states | Hourly `wrfinput` from `real.exe` for hours 0–72; mean `wrfbdy` = `theta_m0`'s | [`make_mean_icbc.sh`](../scripts/da/make_mean_icbc.sh), [`slurm.make_mean_icbc`](../cases/20250520/da_theta_m0/slurm.make_mean_icbc) |
| Perturbations | 15 WRFDA RANDOMCV CV3 draws (seeds `MMDDHH`, 10 × draw; 16 ranks for reproducibility); 5 drawn at random, scaled 1.3 (U V THM QVAPOR) / 0.6 (MU), centered | [`run_wrfda_draw.sh`](../scripts/da/run_wrfda_draw.sh), [`wrfda_bank_diff.py`](../scripts/da/wrfda_bank_diff.py), [`assign_perturbations.py`](../scripts/da/assign_perturbations.py), [`config/assignment.txt`](../cases/20250520/da_theta_m0/config/assignment.txt) |
| Initial members (00Z 05-20) | Mean + perturbation, `T = THM`, QVAPOR ≥ 0, **hydrostatic PH increment** | [`make_initial_members.py`](../scripts/da/make_initial_members.py) |
| Member boundaries | Patched `pert_wrf_bc` per member and hour (same draw every hour, option A), hydrostatic PH; refitted each cycle by patched `update_wrf_bc` | [`build_member_bdy.py`](../scripts/da/build_member_bdy.py), [`refit_member_bdy.sh`](../scripts/da/refit_member_bdy.sh) |
| Restarts | **True WRF restarts**; DART works on a ~0.9-GB file extracted from `wrfrst` and written back (AL, ALT, P, P_HYD recomputed, hydrostatic PH) | [`wrfrst_dart.py`](../scripts/da/wrfrst_dart.py) |
| Filter (as run in the pilot, step 13) | EAKF, 5 members, 900-s window; U V THM QVAPOR PH MU updated; W, T2, Q2, U10, V10, PSFC in state, not written back (`NO_COPY_BACK`); localization 300 km / 0.5 scale height (zero-influence); adaptive prior inflation flavor 2, damping 0.9. Since 10-14/15 (not yet run): QCLOUD `UPDATE`, QRAIN QSNOW QGRAUP `REFL_10CM` `NO_COPY_BACK` added for the MRMS work (Sec. 5.3) | [`config/input.nml.filter`](../cases/20250520/da_theta_m0/config/input.nml.filter) (current); the pilot's copy is in `output_hph/<t>/filter/input.nml` |
| Observations | MADIS hourly files → per-family `obs_seq` → per-cycle slice (t − 450 s, t + 450 s] → `wrf_dart_obs_preprocess` (5-row boundary drop, error inflation to 15 rows, 300-m elevation check) | [`convert_madis_hour.sh`](../scripts/da/convert_madis_hour.sh), [`make_cycle_obs.sh`](../scripts/da/make_cycle_obs.sh), [`config/input.nml.obs_preprocess`](../cases/20250520/da_theta_m0/config/input.nml.obs_preprocess) |
| Cycle | One 40-node job: 5 members × 8 nodes concurrently, filter on 8 × 16 ranks; resumable per cycle; settings recorded in `settings.txt` | [`slurm.cycle`](../cases/20250520/da_theta_m0/slurm.cycle) → [`driver.sh`](../scripts/da/driver.sh) → [`cycle_job.sh`](../scripts/da/cycle_job.sh) ([`prep_filter.sh`](../scripts/da/prep_filter.sh), [`post_filter.sh`](../scripts/da/post_filter.sh), [`advance_member.sh`](../scripts/da/advance_member.sh), [`check_cycle.py`](../scripts/da/check_cycle.py)); settings in [`config/experiment.sh`](../cases/20250520/da_theta_m0/config/experiment.sh) |

### 4.2 Main findings

- **Restart strategy.** Cold-starting members from `wrfout` resets W, MYJ TKE, canopy water and accumulations (20–25 % of the 15-min change after 15 min). A true restart stays within 0–4 %. Restart file 13.1 GB per member. (Step 7)
- **Hydrostatic balance.** An increment without a matching PH change causes a vertical acoustic shock (|dpsfc/dt| ~4,700 hPa/3h). Adding the hydrostatic PH increment removes it. In real cycling, DART's own PH increment is not hydrostatic (p_nh change 33 Pa vs 0 Pa). The hydrostatic write-back makes the first minute 4–6× quieter and changes nothing else, so it has been the default since 10-03. (Steps 7, 11, 13)
- **Boundaries.** With DART built `-fp-model precise`, a zero-perturbation refit reproduces `real.exe` bit for bit. The per-cycle refit removes the edge shock that a stale boundary gives. Hydrometeor boundaries stay zero; aerosol-number boundaries are shifted to the segment start. Rows 5–10 of `wrfbdy` are unused (1 + 4 zone; Q18: 1 + 9 for the 50-member DA). (Steps 2, 6, 8)
- **Observation handling.** Windows match filter's exactly. The 00Z soundings fall in the 00:00 window, which has no analysis. Marine stations are all outside the domain or in its boundary zone. METAR routine reports fall in the HH:00 cycle. (Steps 9–10)
- **Inflation files.** Use `postassim_priorinf_*`, not `output_priorinf_*`: the latter lacks `NO_COPY_BACK` variables. (Step 11)
- **Flavor 5 needs `inf_sd_lower_bound` < `inf_sd_initial`.** Otherwise the sd never moves. `INF_SD_LOWER_BOUND` is now a run setting. (Step 13, 10-15)
- **1-hour pilot:** ~32 min on 40 nodes (cold start 135 s, analysis cycles 420–510 s; filter 100–170 s at ~28 ms per observation). The ensemble is under-dispersive at aircraft levels and getting more so (ACARS T spread 0.63 → 0.38 K vs RMS 0.8–0.9 K); adaptive inflation rises in response. (Step 13)
- **Innovation statistics** ([`innovation_stats.py`](../scripts/da/innovation_stats.py) on `output_hph`, 4 analyses pooled; method in [`obs_error_diagnostics.md`](obs_error_diagnostics.md)). The METAR errors DART's converter assigns by default (T2 2.5 K, 10-m wind 3.5 m/s, RH 0.2) are larger than the innovations support. The implied and Desroziers estimates give T2 0.95–1.1 K, wind 1.3–1.7 m/s and q2 5.8–6.4 % RH, so the defaults are ~2.3–2.6× too large in sd for T2 and wind and ~3.3× for q2. Separately, these estimates land near NCEP's regional tables (NAM T 1.26 K, RAP wind 1.59 m/s, RAP RH 5.9 %). That independent agreement is why the METAR errors were set to the NCEP values on 10-03 rather than tuned from one hour of data ([`obs_expansion.md`](obs_expansion.md) §5). Caveats: one hour, one time of day, 5 members, correlated surface errors ignored; the implied estimate is an upper bound when the spread is too small.

### 4.3 Pilot runs kept

| Run (`RUN_NAME`) | Job | Settings | Kept |
|---|---|---|---|
| (none) `output/`, `run/` | 1047814 | DART's PH, damping 0.9, flavor 2 | trimmed (14 G); `run/` = initial members only (7.7 G) |
| `_hph` | 1047842 | hydrostatic PH | **complete** `output_hph/` (185 G), 01:15 `wrfrst` in `run_hph/` (38 G); the timing baseline |
| `_hph_d9956` | 1047843 | + damping 0.9956 | trimmed (17 G), `run_hph_d9956/` (38 G) |
| `_hph_f5` | 1047844 | + flavor 5 (sd stuck at 0.6) | trimmed (17 G), `run_hph_f5/` (38 G) |

All four used `obs/` (DART's default METAR errors). None can be continued with the new observation setup: new runs need `REFL_10CM` in the restarts, so they start again from the 00Z cold start.

## 5. Observation expansion

Main note: [`obs_expansion.md`](obs_expansion.md). Namelist and error decisions: [`dart_namelist_discussion_log.md`](dart_namelist_discussion_log.md) (entries 10-03 to 10-15).

### 5.1 Inventory and order

- **What HRRRDAS assimilated**, checked in the HRRR source (`../software/HRRR` `40ee6058`), against what is obtainable for 2025-05-20 (§1–3). Of the HRRRDAS observation families, METAR, ACARS, radiosondes, marine, mesonet and MRMS come from public data. Satellite winds need a new GOES reader, VAD winds need two `prepbufr` patches, and GPS PW is parked. Radial velocity is not in HRRRDAS but is being prepared (§4).
- **Order decided 10-13** (§6): mesonet → MRMS → radial velocity → GOES winds → VAD.
- **Errors** (§5): DART's MADIS defaults compared with RAP/NAM/RRFS tables (`../software/GSI-fix_subset`). METAR set to NCEP values; ACARS q kept at 20 % RH for now. Radiosonde and ACARS errors are still DART's.

### 5.2 Mesonet (built and wired in 10-14, not run)

- Public MADIS mesonet, ~2,450 stations per cycle in the domain (~15× METAR). APRSWXNET is ~60 % of it ([`profile_madis_mesonet.py`](../scripts/da/profile_madis_mesonet.py)).
- Per-cycle selection ([`select_mesonet_cycle.py`](../scripts/da/select_mesonet_cycle.py), [`make_cycle_mesonet.sh`](../scripts/da/make_cycle_mesonet.sh)):
  - one record per site, closest to t;
  - provider/station options **a** (RRFS v2, used first), **b1** (GSD method, HRRR/RRFS v1) and **c** (HRRRDAS: almost nothing in our domain), from the reference lists in [`mesonet_station_selection.md`](mesonet_station_selection.md);
  - sites dropped within 4 km of a same-window METAR (the preprocessor's duplicate test is ~2 km under `r8 = r4`) and where the reported elevation is in feet;
  - calm winds kept.
- T, q and wind are assimilated; the altimeter is evaluated only. Errors are RAP/RRFS: 3.0 K, 7 % RH, 3.0 m/s, 1.0 hPa.
- Known gap: mesonet q needs an altimeter, so ~700 sites per cycle lose q.

### 5.3 MRMS reflectivity (built and wired in 10-14/15, not run)

- **Converter:** [`mrms_to_obs_seq.py`](../scripts/da/mrms_to_obs_seq.py), a Python port of HRRR's `process_NSSL_mosaic_to_dart_and_netcdf.f90` with HRRRDAS settings. It also applies the preprocessor's boundary trim and error inflation, and stamps each ob with the MRMS valid time. Data from [`download_mrms.sh`](../scripts/da/download_mrms.sh). The result is ~77–81 k precipitation obs + ~8.5 k clear-air obs per cycle (vs ~3–5 k conventional obs).
- **Model side:** WRF patched so `REFL_10CM` is in `wrfrst` ([`wrf_06d4240a_refl_10cm_restart.patch`](../patches/wrf_06d4240a_refl_10cm_restart.patch); tested, job 1051956). `microphysics_type = 5` and the −10 dBZ floor are set. QCLOUD, QRAIN, QSNOW, QGRAUP, QNRAIN and `REFL_10CM` are extracted.
- **Two filter options per run:**
  - `MRMS_FILTER=two_pass` (HRRRDAS-like). Pass 2 is [`input.nml.filter_mrms`](../cases/20250520/da_theta_m0/config/input.nml.filter_mrms): 18 km / 0.5 scale height; updates U, V, THM, QVAPOR and the hydrometeors; H(x) is the background `REFL_10CM`. `MRMS_INFLATION` (pass1 | both) is **undecided**.
  - `MRMS_FILTER=one_pass`: [`input.nml.filter_joint`](../cases/20250520/da_theta_m0/config/input.nml.filter_joint) + impact table [`obs_impact_joint.txt`](../cases/20250520/da_theta_m0/config/obs_impact_joint.txt).
- **QNRAIN** is reset by Thompson's 1-mm rule where QRAIN changed (`wrfrst_dart.py qnrain`).

### 5.4 Radial velocity, GOES winds, prepbufr (groundwork only)

- **Radial velocity** (§4): 29 WSR-88Ds in the domain. pyOPAWS is cloned in `../software/pyOPAWS` but not installed. The fall-speed option is chosen tentatively (`REFL_10CM`-based, low tilts).
- **GOES winds:** one test download in `obs/goes_dmw_test/`; there is no reader yet.
- **GDAS prepbufr** (`prepnr`, `prep48h`) is on disk for VAD and GPS PW, and for the NCEP conventional pipeline from the plan (Phase 2, Steps 2E–2H). That pipeline has not been started.

### 5.5 Runs waiting for nodes ([`obs_expansion.md`](obs_expansion.md) §9)

| # | Observations (`OBS_NAME`) | Filter | Proposed `RUN_NAME` | Blocker |
|---|---|---|---|---|
| 1 | MADIS, NCEP METAR errors (`_madis`) | conventional | `_madis` | nodes; also first test of the new pass-1 namelist |
| 2 | + mesonet a, calm kept (`_meso_a_calmkeep`) | conventional | `_meso_a` | nodes |
| 3 | + MRMS (`_madis_mrms`) | one pass | `_madis_mrms1p` | nodes; longer time limit (~85 k obs/cycle) |
| 4 | + MRMS (`_madis_mrms`) | two pass | `_madis_mrms2p` | `MRMS_INFLATION` choice |
| 5 | everything | to decide | to decide | after 1–4 |

Also ready: [`slurm.filter_scaling`](../cases/20250520/da_theta_m0/slurm.filter_scaling) to time filter at other rank counts and `&location_nml` box sizes, and [`summarize_cycle_timing.py`](../scripts/da/summarize_cycle_timing.py) to fill §9's timing table after each run.

### 5.6 Open questions

These are collected from the hand-off and the notes:
- Inflation: `MRMS_INFLATION`, `INF_DAMPING` 0.9 vs 0.9956, flavor 5 with which `INF_SD_LOWER_BOUND`.
- `outlier_threshold = 3` for radar obs: check the QC-7 counts at the first MRMS cycle.
- Impact table: conventional → reflectivity 0 or 1.
- Clear-air obs at echo edges.
- Mesonet q without an altimeter.
- ACARS q and radiosonde errors.
- Q5: the boundary perturbation pattern experiment.
- Q9: aircraft superobbing.
- `model_mod_check`: interpolation test done 09-22 (`dart/mmc/`); the fuller tests are deferred.
- The θm = 1 conversion.
- The 50-member layout on ~110 nodes (Q7).
- The 1 + 9 boundary zone, with a matching free control run (Q18).

### 5.7 Loose ends noticed while writing this

- ~~`patches/README.md` titled its WPS section `wps_configure_ldflags_qopenmp.patch`, a file that never existed.~~ Fixed 2026-10-15: the section is now titled after [`wps_335c76a1_configure.wps.reference`](../patches/wps_335c76a1_configure.wps.reference), says why it is a full copy and that only `LDFLAGS` should differ from a generated file, and lists the alternatives.
- ~~[`cases/20250520/DATA_SOURCES.md`](../cases/20250520/DATA_SOURCES.md) did not list the observation downloads.~~ Fixed 2026-10-15: it now lists the MADIS, MRMS, GDAS prepbufr and GOES downloads with their sources, and the reference files used from `../software/`.
- `cases/20250520/dart/mmc/` holds an early `model_mod_check` setup with an old state list (all `UPDATE`, no surface fields). It is superseded by `config/input.nml.filter` but is still referred to in the notes as the draft source. Decided 2026-10-15: it stays in the case (it is our run, not upstream reference code); `input.nml` and `run_mmc.sh` are now tracked in git, and `CLAUDE.md` records that the interpolation test was run (09-22) while the fuller tests are deferred.

## 6. Roster

### 6.1 Scripts

**General** (`scripts/`)

| Script | Purpose |
|---|---|
| [`env_wrf.sh`](../scripts/env_wrf.sh) | Module environment for building and running WRF/WPS/WRFDA/DART |
| [`audit_configuration.py`](../scripts/audit_configuration.py) | Writes `software_lock.json` (commits, patches, compilers, checksums) |
| [`link_hrrr_gribfiles.py`](../scripts/link_hrrr_gribfiles.py) | `GRIBFILE.AAA…` links to HRRR analyses for ungrib |
| [`setup_ungrib_chunks.py`](../scripts/setup_ungrib_chunks.py), [`merge_ungrib_chunks.py`](../scripts/merge_ungrib_chunks.py) | Split ungrib into time chunks, then merge the outputs |
| [`reverse_metgridlevs.py`](../scripts/reverse_metgridlevs.py) | Reverse the vertical order of HRRR native-level `met_em` files |
| [`make_wrf_iotest.py`](../scripts/make_wrf_iotest.py), [`summarize_wrf_timing.py`](../scripts/summarize_wrf_timing.py) | Generate and summarize the WRF I/O and decomposition tests |
| [`plot_layer_thickness.py`](../scripts/plot_layer_thickness.py) | Layer-thickness comparison between runs |
| [`transcript_to_md.py`](../scripts/transcript_to_md.py) | Session transcript → `notes/transcripts/` (hooks) |

**DA: ensemble construction** (`scripts/da/`)

| Script | Purpose |
|---|---|
| [`make_mean_icbc.sh`](../scripts/da/make_mean_icbc.sh) | Hourly unperturbed `wrfinput` files (step 1) |
| [`run_wrfda_draw.sh`](../scripts/da/run_wrfda_draw.sh), [`check_wrfda_draw.py`](../scripts/da/check_wrfda_draw.py) | One WRFDA RANDOMCV draw and its check (step 3) |
| [`wrfda_bank_diff.py`](../scripts/da/wrfda_bank_diff.py), [`assign_perturbations.py`](../scripts/da/assign_perturbations.py) | Perturbation bank; draws → scaled, centered members (step 4) |
| [`make_initial_members.py`](../scripts/da/make_initial_members.py) | Initial members with hydrostatic PH (step 5) |
| [`build_member_bdy.py`](../scripts/da/build_member_bdy.py), [`check_member_bdy.py`](../scripts/da/check_member_bdy.py) | Per-member `wrfbdy` and its gate (step 6) |

**DA: model-side tools and tests**

| Script | Purpose |
|---|---|
| [`run_wrf_segment.sh`](../scripts/da/run_wrf_segment.sh) | One WRF segment (cold start or restart) |
| [`wrfrst_dart.py`](../scripts/da/wrfrst_dart.py) | `extract` / `insert` (hydrostatic PH, P/AL recompute) / `qnrain` between `wrfrst` and the DART-facing file |
| [`refit_member_bdy.sh`](../scripts/da/refit_member_bdy.sh), [`check_boundary_refit.py`](../scripts/da/check_boundary_refit.py) | Boundary refit with `update_wrf_bc`, and its checks (step 8) |
| [`compare_restart.py`](../scripts/da/compare_restart.py), [`restart_increment_test.py`](../scripts/da/restart_increment_test.py) | Restart tests (step 7) |
| [`check_hydrostatic_balance.py`](../scripts/da/check_hydrostatic_balance.py) | p_nh departure; DART vs hydrostatic PH increment |
| [`check_refl_restart.py`](../scripts/da/check_refl_restart.py) | Check of the `REFL_10CM`-in-restart patch |

**DA: observations**

| Script | Purpose |
|---|---|
| [`convert_madis_hour.sh`](../scripts/da/convert_madis_hour.sh) | Hourly MADIS family → `obs_seq` in the lat/lon box (step 9) |
| [`make_cycle_obs.sh`](../scripts/da/make_cycle_obs.sh) | Per-cycle observation set: slice, mesonet, MRMS, screening, joint file (step 10 onward) |
| [`profile_madis_mesonet.py`](../scripts/da/profile_madis_mesonet.py) | Profile a mesonet hour |
| [`select_mesonet_cycle.py`](../scripts/da/select_mesonet_cycle.py), [`make_cycle_mesonet.sh`](../scripts/da/make_cycle_mesonet.sh) | Mesonet per-cycle selection and conversion |
| [`download_mrms.sh`](../scripts/da/download_mrms.sh), [`mrms_to_obs_seq.py`](../scripts/da/mrms_to_obs_seq.py) | MRMS download (HRRRDAS minute rule) and conversion |
| [`innovation_stats.py`](../scripts/da/innovation_stats.py) | Innovation, implied and Desroziers error statistics per type |

**DA: filter and cycling**

| Script | Purpose |
|---|---|
| [`driver.sh`](../scripts/da/driver.sh) | Cycle loop inside one allocation; resumable; `settings.txt` |
| [`cycle_job.sh`](../scripts/da/cycle_job.sh), [`cycle_lib.sh`](../scripts/da/cycle_lib.sh) | One cycle; shared helpers |
| [`prep_filter.sh`](../scripts/da/prep_filter.sh), [`post_filter.sh`](../scripts/da/post_filter.sh) | Before and after filter (conventional and MRMS passes) |
| [`advance_member.sh`](../scripts/da/advance_member.sh) | Member boundary refit + WRF advance |
| [`check_filter_gate.py`](../scripts/da/check_filter_gate.py), [`check_cycle.py`](../scripts/da/check_cycle.py) | Filter gate and per-cycle checks |
| [`summarize_cycle_timing.py`](../scripts/da/summarize_cycle_timing.py), [`compare_dart_members.py`](../scripts/da/compare_dart_members.py) | Timing breakdown; compare analyses (scaling test) |

### 6.2 Job scripts and configuration (`cases/20250520/`)

| File | Purpose |
|---|---|
| [`wps/`](../cases/20250520/wps): `namelist.wps`, `Vtable.hrrrv4rap`, `slurm.{ungrib,ungrib_array,metgrid,reverse}` | WPS pipeline |
| [`baseline/`](../cases/20250520/baseline), [`hybrid2/`](../cases/20250520/hybrid2), [`theta_m0/`](../cases/20250520/theta_m0): `namelist.input`, `slurm.real`, `slurm.wrf` | The three free runs (scripts say `priority_long`, kept as the record of what ran) |
| [`iotest/`](../cases/20250520/iotest) A–K + `submit_chain*.sh` | I/O and decomposition tests |
| [`da_theta_m0/config/experiment.sh`](../cases/20250520/da_theta_m0/config/experiment.sh) | All DA settings (paths, nodes, `RUN_NAME`, `OBS_NAME`, `MESONET`, `MRMS*`, inflation, `HYDROSTATIC_PH`) |
| [`config/namelist.input.wrf`](../cases/20250520/da_theta_m0/config/namelist.input.wrf), [`namelist.input.real`](../cases/20250520/da_theta_m0/config/namelist.input.real), [`namelist.input.3dvar`](../cases/20250520/da_theta_m0/config/namelist.input.3dvar), [`iofields_cycle.txt`](../cases/20250520/da_theta_m0/config/iofields_cycle.txt) | Member WRF template, mean-IC `real.exe`, WRFDA draws, extra history fields |
| [`config/input.nml.filter`](../cases/20250520/da_theta_m0/config/input.nml.filter), [`input.nml.filter_mrms`](../cases/20250520/da_theta_m0/config/input.nml.filter_mrms), [`input.nml.filter_joint`](../cases/20250520/da_theta_m0/config/input.nml.filter_joint), [`obs_impact_joint.txt`](../cases/20250520/da_theta_m0/config/obs_impact_joint.txt) | Filter: conventional pass, MRMS pass, one-pass with impact table |
| [`config/input.nml.obs_preprocess`](../cases/20250520/da_theta_m0/config/input.nml.obs_preprocess), [`config/assignment.txt`](../cases/20250520/da_theta_m0/config/assignment.txt) | Observation screening; member ↔ draw table |
| `da_theta_m0/slurm.*`: [`make_mean_icbc`](../cases/20250520/da_theta_m0/slurm.make_mean_icbc), [`pert_draw`](../cases/20250520/da_theta_m0/slurm.pert_draw), [`member_bdy`](../cases/20250520/da_theta_m0/slurm.member_bdy), [`restart_test`](../cases/20250520/da_theta_m0/slurm.restart_test), [`true_restart_test`](../cases/20250520/da_theta_m0/slurm.true_restart_test), [`restart_increment_test`](../cases/20250520/da_theta_m0/slurm.restart_increment_test), [`boundary_test`](../cases/20250520/da_theta_m0/slurm.boundary_test), [`filter_gate`](../cases/20250520/da_theta_m0/slurm.filter_gate), [`refl_restart_test`](../cases/20250520/da_theta_m0/slurm.refl_restart_test), [`cycle`](../cases/20250520/da_theta_m0/slurm.cycle), [`filter_scaling`](../cases/20250520/da_theta_m0/slurm.filter_scaling) | One job script per pilot step; `slurm.*.<job>.out` logs beside them (untracked) |

### 6.3 Patches ([`patches/README.md`](../patches/README.md))

| Patch | What | Since |
|---|---|---|
| [`wrf_06d4240a_tempo_error_stop_ifort_fix.patch`](../patches/wrf_06d4240a_tempo_error_stop_ifort_fix.patch) | TEMPO `error stop` that ifort 19 can't compile | 09-17 |
| [`wrf_06d4240a_refl_10cm_restart.patch`](../patches/wrf_06d4240a_refl_10cm_restart.patch) | `REFL_10CM` into the restart stream (Registry `hdu` → `hdur`) | 10-14 |
| [`wps_335c76a1_configure.wps.reference`](../patches/wps_335c76a1_configure.wps.reference) | `LDFLAGS = -qopenmp` for geogrid/metgrid linking | 09-17 |
| [`dart_7bbd35a09_types_mod_r8_as_r4.patch`](../patches/dart_7bbd35a09_types_mod_r8_as_r4.patch) | DART in single precision (`r8 = r4`) | 09-22 |
| [`dart_7bbd35a09_madis_acars_wvss_humidity.patch`](../patches/dart_7bbd35a09_madis_acars_wvss_humidity.patch) | ACARS converter reads WVSS humidity | 09-25 |
| [`dart_7bbd35a09_madis_rawin_use_namelist.patch`](../patches/dart_7bbd35a09_madis_rawin_use_namelist.patch) | Radiosonde converter honours its namelist | 09-29 |
| [`dart_7bbd35a09_wrf_bc_hydrometeors_aerosol_shift.patch`](../patches/dart_7bbd35a09_wrf_bc_hydrometeors_aerosol_shift.patch) | `update_wrf_bc`/`pert_wrf_bc`: hydrometeor boundaries left at zero; aerosol-number boundaries shifted | 09-30 |
| [`dart_7bbd35a09_mkmf_fp_model_precise.patch`](../patches/dart_7bbd35a09_mkmf_fp_model_precise.patch) | DART built `-fp-model precise` (bit-identical boundary refit) | 10-01 |
| [`dart_7bbd35a09_madis_metar_obs_errors.patch`](../patches/dart_7bbd35a09_madis_metar_obs_errors.patch) | METAR errors → NCEP (1.26 K, 1.59 m/s, 5.9 % RH) | 10-03 |
| [`dart_7bbd35a09_madis_mesonet_obs_errors.patch`](../patches/dart_7bbd35a09_madis_mesonet_obs_errors.patch) | Mesonet errors → RAP/RRFS (3.0 K, 3.0 m/s, 7 % RH, 1.0 hPa) | 10-14 |

### 6.4 Notes

| Note | Content |
|---|---|
| [`initial_plan_from_codex/…rev2.md`](../initial_plan_from_codex/LASSO_BNF_DA_Detailed_Implementation_Plan_rev2.md) (+ `.docx`) | The overall plan (direction, not implementation) |
| [`wrf_dart_tutorial_adaptation.md`](wrf_dart_tutorial_adaptation.md) | WRF-DART tutorial → BNF: what changes, decisions 2.10–2.13 (restarts, boundaries, spin-up, MADIS) |
| [`da_workflow_layout.md`](da_workflow_layout.md) | Directory layout and file inventory of the DA workflow |
| [`da_5member_pilot_steps.md`](da_5member_pilot_steps.md) | **The pilot record**: steps 1–14, results, decisions Q1–Q18 |
| [`lateral_boundary_fields_for_da.md`](lateral_boundary_fields_for_da.md) | What WRF uses from `wrfbdy`; what the DART boundary tools must refit |
| [`wrfout_restart_fields.md`](wrfout_restart_fields.md) | The 65 fields in `wrfinput` but not `wrfout` (restart-from-`wrfout` plan, superseded by true restarts) |
| [`dart_namelist_discussion_log.md`](dart_namelist_discussion_log.md) | **Why each namelist value is what it is** (running log) |
| [`dart_input_nml_comparison.md`](dart_input_nml_comparison.md), [`dart_all_namelist_blocks.md`](dart_all_namelist_blocks.md) | DART `input.nml` references: stock vs tutorial; every relevant block |
| [`obs_expansion.md`](obs_expansion.md) | **The observation-expansion record**: HRRRDAS inventory, errors, mesonet, MRMS, run plan, filter timing |
| [`obs_error_diagnostics.md`](obs_error_diagnostics.md) | Theory of the implied and Desroziers error estimates |
| [`mesonet_station_selection.md`](mesonet_station_selection.md) | How HRRR, HRRRDAS, RRFS v1/v2 select mesonet stations; list files P1–P5, S1–S6 |
| `codex.*.md` (4 files: [HRRRv4 obs](codex.HRRRv4_observations_and_WRF_DART_reference.md), [HRRRv4 radar](codex.HRRRv4_radar_data_assimilation_summary.md), [WRFDA RANDOMCV](codex.WRFDA_RANDOMCV_CV3_IC_LBC_Summary_v2.md), [tutorial discussion](codex.WRF_DART_Discussion_and_Branches_Summary_v1.md)) | Background summaries written outside this repo's sessions; corrections partly recorded in `obs_expansion.md` |
| [`handoffs/`](handoffs) (parts 3–6, 10-14/15) | Session hand-offs; [part 6](handoffs/2026-10-15_adding_more_obs_part6.md) is the latest |
| Dowell 2020, Dowell et al. 2022 (PDFs, untracked) | HRRRDAS and HRRR references |
| [`prompts/software_management.md`](../prompts/software_management.md), [`CLAUDE.md`](../CLAUDE.md), [`cases/20250520/DATA_SOURCES.md`](../cases/20250520/DATA_SOURCES.md) | Original software-management brief; repo guide; external data dependencies |

### 6.5 Simulations and analyses on disk (`cases/20250520/`)

| Directory | Content | Size |
|---|---|---|
| [`geog/`](../cases/20250520/geog) | `geo_em.d01.nc` (copied) | small |
| [`wps/`](../cases/20250520/wps) | ungrib/metgrid output, 73 `met_em` | 273 G |
| [`baseline/`](../cases/20250520/baseline) | Free run θm = 1, hybrid_opt = 0, 289 `wrfout` | 672 G |
| [`hybrid2/`](../cases/20250520/hybrid2) | Free run hybrid_opt = 2 | 631 G |
| [`theta_m0/`](../cases/20250520/theta_m0) | Free run θm = 0 (the DA's configuration) | 671 G |
| [`iotest/`](../cases/20250520/iotest) | I/O tests (namelists, logs) | 11 M |
| [`dart/mmc/`](../cases/20250520/dart/mmc) | `model_mod_check` run directory (09-21/22): `input.nml` (ancestor of `config/input.nml.filter`), `run_mmc.sh`, logs, interpolation-test output (`mmc_output1.nc`, 0.9 GB) | 0.9 G |
| [`figures/`](../cases/20250520/figures) | Layer thickness; [`mrms/`](../cases/20250520/figures/mrms) MRMS obs at 00:15 | small |
| [`da_theta_m0/mean/`](../cases/20250520/da_theta_m0/mean) | 73 hourly mean `wrfinput` (05-19 00Z → 05-22 00Z), `real.exe` logs | 80 G |
| [`da_theta_m0/perts/`](../cases/20250520/da_theta_m0/perts) | `bank/pert_bank_001…015.nc`, `members/pert_mem001…005.nc`, `assignment.txt` | 24 G |
| [`da_theta_m0/bdy/`](../cases/20250520/da_theta_m0/bdy) | Mean 2-h `wrfbdy` subset, `wrfbdy_d01_mem001…005`, refit test file | 1.9 G |
| [`da_theta_m0/tests/`](../cases/20250520/da_theta_m0/tests) | `restart/`, `true_restart/`, `restart_increment/`, `boundary/`, `filter_gate/` (steps 7, 8, 11; full-size output trimmed; `refl_restart/` deleted 10-14) | 103 G |
| [`da_theta_m0/run/`](../cases/20250520/da_theta_m0/run) | Initial members `mem00N/wrfinput_d01` (start of every run) | 7.7 G |
| `da_theta_m0/run_hph{,_d9956,_f5}/` | 01:15 `wrfrst` per member for the step-13 runs (no `REFL_10CM`) | 38 G each |
| [`da_theta_m0/output_hph/`](../cases/20250520/da_theta_m0/output_hph) | Complete 1-hour pilot: per cycle member priors/analyses, `wrfout`, filter stages, `obs_seq.final`, inflation, logs | 185 G |
| `da_theta_m0/output{,_hph_d9956,_hph_f5}/` | Trimmed step-13 runs (logs, `obs_seq.final`, mean/sd, inflation) | 14–17 G each |

### 6.6 Observation datasets

Raw (`cases/20250520/obs/`):

| Directory | Content | Size |
|---|---|---|
| [`madis/{metar,acars,raob,marine,mesonet}/`](../cases/20250520/obs/madis) | Public MADIS hourly files, 05-19 → 05-21 (72 per family; 53 raob) | 2.3 G |
| [`mrms/20250520/`](../cases/20250520/obs/mrms/20250520) | MRMS `MergedReflectivityQC`, 33 levels × 4 times (00:15–01:00) | 131 M |
| [`gdas_prepbufr/{prepnr,prep48h}/`](../cases/20250520/obs/gdas_prepbufr) | GDAS prepbufr, 6-hourly, 05-19 → 05-22 (+ test dirs) | 2.0 G |
| [`goes_dmw_test/`](../cases/20250520/obs/goes_dmw_test) | One GOES-19 ABI derived-motion-wind set (6 channels), reader test | 1 M |
| [`madis_test/`](../cases/20250520/obs/madis_test), [`obs_seq_test/`](../cases/20250520/obs/obs_seq_test) | First converter tests (05-20 12/18Z) | 132 M |

Converted (DART `obs_seq`):

| Directory | Content | Size |
|---|---|---|
| [`obs/obs_seq_madis/{metar,acars,rawin,marine}/`](../cases/20250520/obs/obs_seq_madis) | Hourly per-family files, 05-20 + 05-21, NCEP METAR errors; `metar_v1_dart_land_errors/` = the pilot's originals | 231 M |
| [`obs/obs_seq_mesonet/{a_calmkeep,a_calmdrop,b1_calmkeep,c_calmkeep}/`](../cases/20250520/obs/obs_seq_mesonet) | Per-cycle mesonet selections (with `selected.csv`, `selection.log`) | 12 M |
| [`obs/obs_seq_mrms/`](../cases/20250520/obs/obs_seq_mrms) | First converter test at 00:15 (`obs_seq` + gridded netCDF) | 20 M |

Per-cycle observation sets, all for 00:15–01:00 (`da_theta_m0/`; each has `obs_settings.txt` except `obs/`):

| Set | Content | Used by |
|---|---|---|
| [`obs/`](../cases/20250520/da_theta_m0/obs) | MADIS, DART default METAR errors | step-13 runs |
| [`obs_madis/`](../cases/20250520/da_theta_m0/obs_madis) | MADIS, NCEP METAR errors | run 1 (reference) |
| [`obs_meso_a_calmkeep/`](../cases/20250520/da_theta_m0/obs_meso_a_calmkeep) | + mesonet option a | run 2 |
| [`obs_madis_mrms/`](../cases/20250520/da_theta_m0/obs_madis_mrms) | MADIS + `obs_seq.mrms` + `obs_seq.joint` | runs 3, 4 |
| [`obs_meso_a_calmkeep_mrms/`](../cases/20250520/da_theta_m0/obs_meso_a_calmkeep_mrms) | Mesonet + MRMS | run 5 candidate |

Reference code in `../software/` (cloned, not in the repo): `HRRR` (`40ee6058`), `GSI`, `GSI-fix_subset` (`0ba656b6`, error tables), `RRFSv1`, `RRFSv2` (mesonet lists), `pyOPAWS` (`6c14895`). Commits are cited in [`mesonet_station_selection.md`](mesonet_station_selection.md) §1 and [`obs_expansion.md`](obs_expansion.md).
