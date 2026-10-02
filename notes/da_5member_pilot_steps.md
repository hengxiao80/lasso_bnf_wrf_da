# 5-member, 15-min cycling pilot: detailed steps

Written 2026-09-29. This expands Sec. 3 of `wrf_dart_tutorial_adaptation.md` into an ordered, checkable list for the first working DA cycle, using the decisions made since (2.10–2.13 there) and the layout in `da_workflow_layout.md`. The choices still open are collected in Sec. 4.

## 0. Scope of the pilot

| Item | Setting |
|---|---|
| Case, setup | 2025-05-20 case, single 2.5-km domain (550 × 390 × 150), `theta_m0` (`hybrid_opt = 0`, `use_theta_m = 0`) |
| Ensemble | **5 members** |
| Start | **2025-05-20 00Z.** Initial members = HRRR-based mean state + bank perturbations. The 15-min EAKF cycling **is the spin-up**; there is no separate free-forecast spin-up. |
| Cycle | 900 s. First analysis at 00:15, using the 15-min forecast from the perturbed initial members. |
| Observations | **Public MADIS only**, files in `cases/20250520/obs/madis/` (05-19 to 05-21): METAR, ACARS (with the WVSS humidity patch), radiosondes, marine, and mesonet if chosen (Q1). Not in the pilot: radar, GOES winds, VAD winds, GPS PW. |
| Model restart | **True WRF restart** (`restart = .true.`) from each member's own `wrfrst` file, decided 2026-10-01 after the step 7 tests; the first segment (00:00) is a cold start from the initial members. DART works on a small DART-facing file extracted from the restart file (step 7). Replaces the earlier plan to cold-start from `wrfout` with the 65 extra `iofields` fields (2.11), which loses W, TKE and canopy water every cycle. |
| Boundaries | Precomputed per-member `wrfbdy` files; `update_wrf_bc` before each segment (2.12). Both tools patched to keep hydrometeor boundaries at zero, as in the free runs, and to shift the aerosol-number boundaries (`lateral_boundary_fields_for_da.md`); `T = THM` kept in every file we write instead of a `THM` patch |
| Job rules | `batch_all`; UCX settings by job type (`real`: `rc,xpmem,self`; `wrf`: `self,sm,ud` + queue length); no submission without the user's go-ahead, one step at a time |

## 1. What happens in time

| Time | Action |
|---|---|
| 00:00 | Initial members written (step 5). No observations. |
| 00:00 → 00:15 | First advance of every member (no `filter`). The boundary record is refitted to each member's own initial state. |
| 00:15 | **Analysis 1:** `filter` on the 5 forecasts with the observations valid around 00:15, then advance to 00:30. |
| every 15 min | Analysis → member files updated → boundary refit → 900-s advance → next analysis |

So `cycle(t)` = [filter if t > start] + advance(t → t+900 s). Roughly 4 cycles per hour of spin-up.

**Expected cost** (estimates only, scaled from the baseline run: 16 nodes, ~50 s of wall time per 15-min segment including output; linear scaling assumed; the cold start is unmeasured, step 9 measures it): with 8 nodes per member, a segment takes ~100–130 s; the 5 members run at the same time on 40 nodes, so a cycle is ~3–5 min with `filter` and file handling. 1 h of cycling (the pilot) ≈ 4 cycles ≈ 15–20 min; 3 h ≈ 12 cycles ≈ 1 h; 12 h ≈ 3–4 h. **Disk:** a `wrfout` is ~3.8 GB, so 5 members write ~19 GB per cycle. The pilot keeps every member's prior and analysis (Q10): about 40 GB per cycle, ~160 GB for the 1-hour pilot.

## 2. Steps

Each step lists what it does, what it needs, the script and its status, and the check that must pass before the next step. Job types: **L** = login node, **S** = Slurm job. "Ready" and "new" are as in the layout note.

### Part A: inputs

**Step 1. Hourly mean `wrfinput` files.** (S, **done**)
- Job 1046870 (`slurm.make_mean_icbc`, finished 2026-09-29) wrote `mean/wrfinput_d01_YYYY-MM-DD_HH_00_00` for hours 0–72. `mean/wrfbdy_d01` links to `theta_m0/real/wrfbdy_d01`. The pilot needs only 05-20 00Z onward (hours 24+).
- **Gate (passed 2026-09-30):** 73 files, all 73 `real.exe` logs end in `SUCCESS COMPLETE REAL_EM`, 0 failures; hour 0 byte-identical to `theta_m0/real/wrfinput_d01`. A time manifest (file ↔ valid time) is not written; the file names carry it.

**Step 2. DART boundary-tool patch and rebuild.** (L, **done**) Revised 2026-09-30; details and reasons in `lateral_boundary_fields_for_da.md`.
- Patch (source edited, `patches/dart_7bbd35a09_wrf_bc_hydrometeors_aerosol_shift.patch`):
  - both tools: `nmoist = 1`, so `QCLOUD QRAIN QICE QSNOW QGRAUP QNICE` are no longer refitted and keep the `real.exe` zeros, as in the free runs;
  - `update_wrf_bc`: the boundary values of `QNWFA QNIFA QNBCA` are moved forward along their tendency to the segment start, so they don't lag 15–45 min.
- No `THM` patch for `theta_m0`: it isn't a one-line change (`var3d` also builds the `T_BXS` names). Instead, every file we write keeps `T = THM` (steps 5, 6, 12). Patch when we move to `use_theta_m = 1`.
- Rebuilt 2026-09-30 in `models/wrf/work` (`./quickbuild.sh WRF_BC/update_wrf_bc`, `./quickbuild.sh WRF_BC/pert_wrf_bc`); stock executables kept in `stock_20260918/`.
- **Gate (passed 2026-09-30):** both programs build cleanly. The behavior is checked in step 8.
- **Verified:** `update_wrf_bc` needs no `wrfinput_mean` and no standard input (it only prompts for `infl` if that optional file exists).

### Part B: build the ensemble

**Step 3. One WRFDA RANDOMCV draw.** (L for setup, S for the run, minutes; **done 2026-10-01**)
- Build `config/namelist.input.3dvar` from `tutorial/template_nest/namelist.input.3dvar` and our domain section (`e_we/e_sn/e_vert`, `dx`, projection, `max_dom = 1`). Keep `analysis_type = RANDOMCV`, `cv_options = 3`, `put_rand_seed = .true.`, and record `seed_array1/2`. The `PERT_SCALING…` lines in the template sit outside any namelist and are ignored, so the effective amplitudes are `as1`–`as5` in `&wrfvar7`.
- `fg` = mean `wrfinput` at 2025-05-20_00, `be.dat` = `be.dat.cv3`, `analysis_date` = the same time.
- **Gate:** `wrfvar_output` exists; U, V, THM, QVAPOR, MU differ from `fg`; check whether WRFDA writes `T` and `THM` consistently (it should, at `use_theta_m = 0`); RMS by level and horizontal correlation scale printed.
- **Decision here:** whether the tutorial's `as1–as5` values give plausible spread (Q3).
- **Done.** `config/namelist.input.3dvar` (our model sections, minus 6 entries WRFDA's Registry lacks, + the tutorial's `&wrfvar*`), `scripts/da/run_wrfda_draw.sh`, `slurm.pert_draw` (1 node, 16 ranks), `scripts/da/check_wrfda_draw.py`. Draw 1 (job 1047186): 1 min 47 s, 7.1 GB max per rank.
- **Results of draw 1** (before the ×1.3/×0.6 scaling):
  - changed fields: `U V PH T THM MU P PSFC QVAPOR`; W and hydrometeors unchanged; `T == THM` in the output;
  - RMS: U/V 0.4–0.9 m/s, THM 0.4–0.9 K in the troposphere (up to 1.5 K above 20 km), QVAPOR 4–9 % of the mean, MU 66 Pa;
  - horizontal correlation length (1/e) about 150–220 km in the troposphere.
- **Seeds.** WRFDA seeds the 2-element ifort generator with (`seed_array1`, `seed_array2 × seed_array1 + rank × 10⁷`) (`da_random_seed.inc`). The tutorial's `seed_array1 = YYYYMMDDHH` overflows that product, so we use `seed_array1 = MMDDHH` (52000) and `seed_array2 = 10 × draw` (user, 2026-10-01). The rank enters the seed, so the bank must always use 16 ranks to be reproducible. Draw 1 rerun with the new seeds (job 1047356, 2026-10-01): `seed_array(2)` = 520000 on rank 0 and 50,520,000 on rank 5, so no overflow. RMS and correlation lengths are similar to the first run (U/V up to 1.0 m/s, MU 74 Pa, correlation length about 130–300 km).

**Step 4. Bank and member assignment.** (S array, then L)
- 15 draws (3 × 5, the tutorial's rule), distinct seeds, run as a Slurm array (`gen_pert_bank.sh` adapted). `wrfda_bank_diff.py` writes `perts/bank/pert_bank_NN.nc` = (WRFDA output − `fg`) for U, V, THM, QVAPOR, MU, as in the tutorial (Q16).
- `assign_perturbations.py`: choose 5 distinct draws with a fixed seed, apply the scale factors (tutorial: 1.3 for U, V, THM, QVAPOR and 0.6 for MU; Q3), subtract the mean of the 5 (Q4), and save `assignment.txt` and 5 centered member perturbation files.
- **Gate:** no NaNs, distinct seeds, RMS by level and scales reported; the 5 centered perturbations sum to zero.
- **Done 2026-10-01.**
  - Draws 2–15 ran as array job 1047357, 1 min 40 s each. All 15 seeds are distinct and none overflows.
  - `scripts/da/wrfda_bank_diff.py` wrote `perts/bank/pert_bank_001…015.nc` (255 MB each, 3.6 GB), with no NaNs.
  - Correlations between draws average about 0. Single pairs reach 0.79 at one level, which is a sampling effect of the 200–300 km scales. A direct test of ifort's `random_number` with these seeds showed independent streams (max \|corr\| 0.002 over 2×10⁶ numbers).
  - Selection follows the tutorial (user): 5 distinct draws picked at random with a fixed seed (20250520), no similarity screening.
  - `scripts/da/assign_perturbations.py`: members 1–5 ← draws 4, 14, 5, 8, 7 (`perts/assignment.txt`, tracked copy `config/assignment.txt`), scaled 1.3/0.6, centered; `perts/members/pert_memNNN.nc` (1.4 GB). Sum over members ≈ 1e-14.
  - RMS per member after scaling and centering: U 0.52–0.66 m/s, V 0.60–0.73 m/s, THM 0.98–1.06 K, QVAPOR 0.30–0.34 g/kg, MU 33–53 Pa (domain and column averages). Centering 5 members reduces the variance by about 4/5, i.e. the amplitude by about 0.89.

**Step 5. Initial members at 05-20 00Z.** (L or small S)
- `make_initial_members.py`: member state = mean 00Z `wrfinput` + that member's perturbation (U, V, THM, QVAPOR, MU; Q16); set `T = THM`; clip `QVAPOR ≥ 0`. Write `run/memNNN/wrfinput_d01`.
- **Gate:** all other fields unchanged, no NaNs, QVAPOR non-negative, member-to-member spread by level as intended.
- **Done 2026-10-01** (login node, 2 min). The centered perturbations are kept (Q4, user); the uncentered tutorial version can be tested later.
  - `scripts/da/make_initial_members.py` copies the mean 00Z `wrfinput` (compressed netCDF-4) and rewrites U, V, THM, QVAPOR, MU and `T = THM` in place. Output: `run/mem001…005/wrfinput_d01` (1.28 GB each) and `run/initial_members.txt` (member, draw, clipped points).
  - Gate passed: the variable list, global attributes and every other variable are identical to the mean file; no NaNs; `T == THM` exactly; QVAPOR ≥ 0.
  - The spread by level of the members equals the perturbations' spread (differences ≤ 1e-6 relative, from float32 rounding and clipping). Examples: U 0.8 m/s at the surface and 1.07 m/s at level 10; THM 0.95–1.1 K at low levels and 2.6 K at the top level; MU 52 Pa.
  - Clipping: 14–25 thousand QVAPOR points per member (≈ 0.05 % of 32 M) fall below 0 and are set to 0. They lie between 2 and 17 km, mostly near the tropopause (~15.7 km, where the mean q is ~3e-6) and in dry layers aloft. The removed mass is 1e-6 to 1e-5 of the column total, so the ensemble mean is unchanged to that level. WRFDA does not perturb QVAPOR above level ~110 (spread 0 there).
  - **Regenerated 2026-10-01 with a hydrostatic PH increment** (now the default; `--no-hydrostatic-ph` gives the earlier version). PH = mean PH + (PH integrated hydrostatically from the member's MU, THM, QVAPOR − the same from the mean), because the bank has no PH and an unperturbed PH causes a large vertical adjustment (Sec. 4, "Initial adjustment in the fake-increment test"). PH increment 6.8–8.8 m RMS per member, listed in `run/initial_members.txt`. Checked with `check_hydrostatic_balance.py` (mean file as static and prior): p_nh change 0.0 Pa for members 1 and 4. Only U, V, PH, T, THM, MU and QVAPOR differ from the mean file; spread and clipping are unchanged.

**Step 6. Member boundary files.** (S, I/O heavy but small for a short pilot)
- Extract the records needed (05-20 00Z through the pilot end plus one hour; for the 1-hour pilot, records 00→01 and 01→02) from the mean `wrfbdy_d01` into a subset file, so each member file is small, not 9.3 GB.
- For each member and each hourly record h: build temporary states mean_h + perturbation and mean_(h+1) + perturbation (`T = THM`), and run the patched `pert_wrf_bc` on that record. This reuses the tutorial's tested coupling and moisture clipping in place of a new Python re-implementation (Q6). Record h then runs from the perturbed mean at h to the perturbed mean at h+1. Delete the temporary states as you go.
- Store `bdy/wrfbdy_d01_memNNN`. They are never modified after this step: each cycle copies the member's file into `run/memNNN/`, `update_wrf_bc` refits that copy in place from the member's analysis (start time, boundary values, tendency toward the same perturbed hourly target), and WRF uses it for one segment. Every cycle starts from a fresh copy, so it depends only on the stored file and the current analysis. The used copy is saved per cycle during the pilot (Q10).
- **Gate:** for one member, reconstruct the boundary at record start and end from `B` and tendency and compare with the perturbed states; members' mean offset from the mean `wrfbdy` is ~0 (centering); moisture non-negative.

- **Done 2026-10-01** (job 1047474, 1 node, 5 min; the first attempt, 1047472, stopped because DART tools need an `input.nml` with `&utilities_nml` in the working directory, which the builder now writes).
  - `scripts/da/build_member_bdy.py`, `scripts/da/check_member_bdy.py`, `slurm.member_bdy`. Temporary states hold only the fields `pert_wrf_bc` reads (U V W PH T QVAPOR MU MUB MAPFAC_*), with `T = THM`; each `pert_wrf_bc` call takes ~5 s.
  - Outputs: `bdy/wrfbdy_d01_mean_2025-05-20_00_2h` (records 24–25 of the mean file, 260 MB), `bdy/wrfbdy_d01_mem001…005` (~305 MB each), and `bdy/wrfbdy_d01_refit_mean` (test file).
  - **Tool test:** `--zero-pert` (refit from the unperturbed hourly states) reproduces the `real.exe` records to float32 rounding: T, QVAPOR, MU, PH, W boundary values identical; U, V within 3 ulp; tendencies within 7 ulp of the boundary values. Reason: `pert_wrf_bc` couples in double precision and rounds once (U, V coupling has several steps), and computes tendencies from unrounded values.
  - **Gate passed:** all non-refit variables (hydrometeors, aerosol numbers, ...) identical to the mean file; no refit variable left unchanged; consecutive records join up (B₀₀ + 3600 s × BT₀₀ = B₀₁ to 3e-7 relative); member mean offset from the mean file ≤ 0.4 % of the member spread (coupled quantities are nonlinear, so not exactly 0).
  - Moisture: boundary values ≥ 0. Where a member's target is clipped to exactly 0, start + 3600 s × tendency ends at −4e-5 or above (coupled units, ~1 ulp of start values of ~500), which is rounding. W boundaries are 0 in the mean file and stay 0.

### Part C: model-side tests (one member first, then all five)

**Step 7. Restart test (2.11).** (S, minutes)
- `config/namelist.input.wrf` (from `theta_m0/namelist.input`): `run_seconds`, `history_interval = 15`, one frame per file, `iofields_filename = iofields_cycle.txt` (`+:h:0:` + the 65 names) and `ignore_iofields_warning`, no restart output, `nocolons`, classic netCDF, `nproc_x/nproc_y` for the chosen node count, `rebalance` left at its default 0 (Q17).
- Run 30 min from the mean 00Z `wrfinput` with 15-min history; restart a second run from the 00:15 `wrfout` (renamed `wrfinput_d01`) for 15 min; compare its 00:30 state with the continuous run's.
- **Gate:** all 65 fields present in `wrfout`; no missing-field warnings in `rsl`; 00:30 states close (not bit-identical); cold-start overhead and wall time per segment recorded, which sets the nodes per member (Q7).
- **Done 2026-10-01; outcome: use true WRF restarts.** Scripts: `config/namelist.input.wrf` (single-domain template with placeholders for times, `nproc_x/y`, `restart`, `restart_interval`; `io_form_restart = 2`; `diag_print = 1`), `config/iofields_cycle.txt`, `scripts/da/run_wrf_segment.sh` (one segment in its own directory; `RESTART`, `RESTART_INTERVAL`), `scripts/da/compare_restart.py`, `scripts/da/wrfrst_dart.py`, `scripts/da/restart_increment_test.py`, `slurm.restart_test`, `slurm.true_restart_test`, `slurm.restart_increment_test`. Runs in `tests/{restart,true_restart,restart_increment}/`. All on 8 nodes, 16 × 8 ranks.
  - **Cold start from `wrfout` (job 1047480).** All 65 `iofields` fields are written and read back, and 222 variables are unchanged. But the start is a full cold start: W is discarded (`use_input_w` defaults to `.false.`; RMS 0.92 → 0.009 m/s), MYJ `TKE_PBL` is reset to 0.2 everywhere (`MYJPBLINIT` always does this when `restart = .false.`), Noah `CANWAT` → 0, accumulations → 0, surface fluxes/UST/PBLH re-initialized. By 00:30 the restarted run differs from the continuous one by 20–25 % of the 15-min change (≈ 50 % for PBLH, RAINNC). WRF's `cycling` and `hrrr_cycling` options don't avoid this (they affect only W and stochastic physics).
  - **True restart (job 1047492).** 00:30 state within 0–4 % of the 15-min change for all key fields (PBLH 14 %); 190 of 286 variables bit-identical. Not bit-identical, although two cold-start runs are (some physics state isn't in the restart file); small enough to proceed, cause not investigated.
  - **Restart file:** 13.1 GB per member (classic 64-bit offset, 657 variables), vs 4.4 GB for a `wrfout` with the 65 fields. It stores both RK time levels as `U_1/U_2`, `V_*`, `W_*`, `PH_*`, `THM_*`, `MU_*`, so there is no `U`, `THM`, `MU`, … for DART or `update_wrf_bc`. `_2` is the current state (equal to `wrfout`); `_1` is overwritten by `_2` at the start of the first step (`small_step_prep`, `rk_step == 1`) and before that read only by implicit vertical advection (unused). `T` (= THM), P, AL, ALT, P_HYD, P_HYD_W, PB, ALB, PHB, C3F/C4F/C3H/C4H, P_TOP, TKE_PBL, CANWAT, RTHRATEN are all present.
  - **DART-facing file (`wrfrst_dart.py`).** `extract`: U V W PH THM MU from `_2` under their wrfinput names, QVAPOR, PSFC, T2, Q2, U10, V10, `T = THM`, MUB, MAPFAC_* (0.9 GB, 16 s per member). `filter` updates it; `update_wrf_bc` can use it as `wrfinput_d01`. `insert`: writes the fields back into both time levels, clips QVAPOR ≥ 0, and recomputes AL (hypsometric, `hypsometric_opt = 2`), ALT, P (equation of state, `use_theta_m = 0`), P_HYD and sets `T = THM`, as `start_em.F` does on a cold start (a restart takes them from the file). WRF itself rederives ALT (`rk_step_prep`) and P_HYD, P_HYD_W, T (`phy_prep`) every step; P and AL are recomputed at the start of the acoustic steps (`calc_p_rho`, step 0). On the unmodified file the float64 recompute matches WRF's stored AL to 3e-5 and P to 0.6 Pa RMS (max 6 Pa): float32 rounding in WRF's own `calc_p_rho_phi` (LOG of a pressure ratio ≈ 1.003); a float32 recompute reduces it 3× and matches half the points exactly. `insert --hydrostatic-ph` (opt-in, added 2026-10-01) replaces DART's PH increment with the hydrostatic one (Sec. 4).
  - **Modified restart (job 1047496)**, with member 1's initial perturbation (`pert_mem001.nc`, domain-wide U 0.5 m/s, THM 1 K, QVAPOR 0.34 g/kg, MU 33 Pa RMS, PH unchanged) as a stand-in increment, a worst case compared with a real 15-min analysis increment:
    - Round trip without change (B0) ≈ plain restart (U 0.001 m/s, P 0.8 Pa, PBLH 28 m RMS at 00:30: rounding growth).
    - With vs without the P/AL recompute (B2 vs B1): same to rounding growth (U 0.0016 m/s, MU 0.06 Pa), same noise to 1 %. Kept anyway: cheap, consistent file, like a cold start.
    - Adjustment: domain-mean |dpsfc/dt| 4,690 hPa/3h at step 2, 1,520 at step 8, 223 over minutes 1–5 (93 without the increment), back to 94 vs 90 over minutes 5–15. |dμ/dt| only 10–15 % above the unperturbed run. `diag_print` step 1 is meaningless on a restart (uninitialized previous PSFC).
    - Cause of the adjustment: the unchanged PH, i.e. hydrostatic imbalance, not the MU scaling. See "Initial adjustment in the fake-increment test" in Sec. 4.
  - **Timing (8 nodes, 16 × 8):** 0.34–0.40 s per 5-s step (`theta_m0` on 16 nodes: 0.24 s), so halving the nodes costs only 1.4–1.6× per step. Cold-start segment from `wrfout`: 92 s (6.7 s input, 10.8 s first step, 6.4 s per `wrfout`). True-restart segment: 128 s (22.6 s reading `wrfrst`, 5.4 s first step, 18.1 s writing `wrfrst`, 6.4 s `wrfout`). Q7 still open.

**Step 8. Boundary test (2.12).** (S, minutes; can share the job with step 7)
- One member, one segment starting at 00:15: `update_wrf_bc` (patched) on that member's file, then WRF for 900 s.
- **Gate:** boundary values at 00:15 and 01:00 rebuilt from `B` and tendency match the member state and its perturbed target; `T_BXS` follows `THM`; hydrometeor boundaries still zero; `QNWFA/QNIFA/QNBCA` on their original line (no lag); no boundary-generated artifacts (pressure/w waves, spurious precipitation) after 15–60 min.

### Part D: observations (MADIS only)

**Step 9. Convert the hourly MADIS files.** (L)
- `convert_madis_hour.sh` (new): per family and hour, symlink the file as `<family>_input.nc`, run the converter in its own work directory (converters append to a fixed-name output, so isolate each run), and write `obs_seq.<family>`. Families: `metar`, `acars` (patched), `rawin`, `marine`, and `mesonet` if chosen. `rawin` reads its namelist now (patched), so there is no terminal prompt.
- Merge per family and trim to the domain with `obs_sequence_tool`.
- **Gate:** counts per type per hour match the earlier test (e.g. 18Z 05-20: METAR 3,611, ACARS 14,927 + 735 humidity, radiosondes 2,893 in the box).

**Step 10. Screening and 15-min files.** (L)
- `wrf_dart_obs_preprocess` (new namelist): domain/boundary trim (`obs_boundary`), `sfc_elevation_check` (300 m), pressure/height top, `include_sig_data`, and aircraft superobbing if chosen (Q9).
- `obs_sequence_tool` by time to one `obs_seq.out` per analysis time. Each report is used once; DART's own window (`assimilation_period_seconds = 900` in `&model_nml`, changed from the 21600 in the `mmc` file) is centered on the model time and should agree with this slicing (check in step 13).
- **Radiosondes at 00Z:** HRRR's 00Z analysis already used them, so drop or keep is Q11.
- **Gate:** one file per cycle from 00:15 on; counts per type per file logged. For the 1-hour pilot that is four files (00:15 to 01:00).

### Part E: filter and the cycle

**Step 11. `input.nml` for 5 members.** (L)
- Start from `dart/mmc/input.nml` plus `tutorial/template/input.nml.template`. Set:
  - `ens_size = 5`; `assimilation_period_seconds = 900`;
  - state variables and which are updated (Q8); `wrf_state_bounds` for QVAPOR;
  - the assimilated obs types (the compiled `METAR_*`, `ACARS_*`, `RADIOSONDE_*`, `MARINE_SFC_*`);
  - localization (Q12), `sampling_error_correction = .true.` (recommended for 5 members; the table exists);
  - inflation (Q13); `outlier_threshold = 3`; `stages_to_write` and output volume (Q10).
- `fill_inflation_restart` for the initial inflation files. **Gate:** `filter` starts on a synthetic no-obs sequence.

**Step 12. Cycle scripts.** (L, written; tested in step 13)
- `advance_member.sh`: copy the pristine member boundary file; run `update_wrf_bc` with the member's DART-facing file as `wrfinput_d01`; `run_wrf_segment.sh` (restart from the member's `wrfrst`, writing the next `wrfrst` at the end; cold start for the first segment). *(Revised 2026-10-01 for true restarts; was: rename the new `wrfout` to `wrfinput_d01`.)*
- Around `filter`: `wrfrst_dart.py extract` each member's `wrfrst` → DART-facing file (`input_list_d01.txt`/`output_list_d01.txt` point at these); after `filter`, `wrfrst_dart.py insert` writes the updated fields back and recomputes AL, ALT, P, P_HYD and `T = THM`. This replaces the tutorial-style `ncks -A` merge and the separate `T = THM` step below.
- `prep_filter.sh`: file lists (`input_list_d01.txt`, `output_list_d01.txt`), inflation files, the cycle's `obs_seq.out`.
- `cycle_job.sh`: 5 background `srun` member steps and `wait`, then `filter`, then the merge (`ncks -A` of the updated variables from the `filter` output into each member file, as the tutorial does; NCO must work with the `env_wrf.sh` modules or use Python).
- After the merge, set `T = THM` in each member file before `update_wrf_bc` (DART updates only `THM`; the boundary tools read `T`; see step 2).
- `post_filter.sh` (saves the cycle's files to `output/<time>/` as decided in Q10: member priors and analyses, the refit boundary copies, mean/sd, `obs_seq.final`, inflation), `check_cycle.py`, `driver.sh` (resumable, records `output/<time>/status`). A member failure stops the cycle: never replace a member with a copy of another.

**Step 13. Engineering test and 1-hour pilot: 4 cycles (00:00 → 01:00).** (S)
- Runs the whole chain on 5 members. **Gate**, per stage: `filter` reads the right files and window; `obs_seq.final` written; analysis increments nonzero and confined to the expected region and variables; members updated; WRF restarts from the updated files; boundaries refit; inflation files passed on; no NaNs; no blown members.

**Step 14. Extension.** (S)
- After the 1-hour pilot (step 13) looks sane, extend to the next length (Q1), watching the diagnostics in Sec. 3 each cycle. Restart from the last complete cycle if interrupted.

## 3. Monitoring during the pilot (the spin-up controls)

Per cycle, from `obs_seq.final`, `obs_diag` (15-min bins) and the member files:
- **Observation space:** prior RMSE and bias per type and level; total spread (prior spread + observation error) against RMSE; number assimilated / rejected by DART QC code (outlier, forward-operator failure); ACARS humidity innovations in particular (no instrument QC; note 2.13).
- **State space:** ensemble spread by level for U, V, T, QVAPOR; mean increments; surface pressure tendency and any divergence spike after each update; boundary-edge disturbances.
- **Inflation:** mean and spread fields, and whether they grow, collapse or reset between cycles.
- **Hydrometeors:** spread and rain amounts (starts near zero; matters when radar joins).
- **Stability:** WRF CFL/`blown` messages, `rsl` warnings.
- **When the spin-up counts as done:** criteria to be set from the first cycles (for example, spread ≈ RMSE within a factor, rejection rates stable, no inflation drift). Not fixed in advance.

## 4. Decisions

| # | Decision | Needed by | My recommendation |
|---|---|---|---|
| Q1 | Pilot length | step 13 | **Decided (user, 2026-09-29): 1 hour (4 cycles: 00:15, 00:30, 00:45, 01:00), then extend** |
| Q2 | Bank size | step 4 | 15 (3 × 5, the tutorial's rule) |
| Q3 | Perturbation amplitude and scale factors | steps 3–4 | **Decided (user, 2026-10-01): tutorial values for now** (`as1–as5`; 1.3 U/V/THM/QVAPOR, 0.6 MU). Draw 1 gives somewhat weak wind spread; revisit from the pilot's spread vs error |
| Q4 | Center the 5 perturbations (zero sample mean) | step 4 | **Decided (user, 2026-10-01): centered for now**, for both initial and boundary states; the tutorial's uncentered version (`--no-center`) can be tested later |
| Q5 | Boundary perturbation pattern over time | step 6 | **Decided (user, 2026-09-29): settle by experiment.** The 1-hour pilot uses option A (same bank draw for every hour, the plan's pilot policy). The builder takes a member × hour → bank-draw table, so option B (5 distinct draws per hour from the 15, centered per hour) needs no new code. Experiment after the pilot: see below |
| Q6 | Member-boundary builder | step 6 | Loop the patched `pert_wrf_bc` over records; not a new Python re-implementation |
| Q7 | Nodes per member and job structure | steps 7, 12 | **Decided (user, 2026-09-29): after the step 7 timing.** Options then: one long allocation (about 40–48 nodes) with the cycle loop inside, or one allocation per cycle from a login-node driver |
| Q8 | State vector and which variables update | step 11 | **Partly decided (user, 2026-10-01): T2, Q2, U10, V10 and PSFC in the state with `NO_COPY_BACK`** for now; may be switched to `UPDATE` in later tests. Hydrometeors: follow HRRRv4, worked out later. Still open: whether MU and PH are written back (needed for surface-pressure obs to change the column mass) and W. See "Q8: how DART uses the state variables" below; for PH, the hydrostatic check in "Initial adjustment in the fake-increment test" |
| Q9 | Aircraft superobbing | step 10 | Off at first, since with 5 members and ~1,400 ACARS reports per 15 min the cost is small |
| Q10 | Output retention and `stages_to_write` | steps 11–12 | **Decided (user, 2026-10-01): the pilot and its first extensions keep everything per cycle** in `output/<time>/`: each member's prior (the 15-min forecast) and analysis, each member's refit boundary copy, ensemble mean and sd at all stages, `obs_seq.final`, inflation files. For 5 members ≈ 40 GB per cycle (≈ 160 GB for the 1-hour pilot). Reason: member increments can be inspected, single segments rerun and failures debugged; the analyses can't be recovered otherwise, since `filter` writes them in place into `run/memNNN/wrfinput_d01` and the next segment overwrites it. **Long and 50-member runs: decide later** (≈ 18 TB/day for member analyses alone at 50 members × 96 cycles), e.g. members only hourly, DART state variables only, or `nccopy` compression. The earlier recommendation (only the latest member file, mean/sd at all stages) is one of those options. **Note (2026-10-01, true restarts):** a member `wrfrst` is 13.1 GB (vs 4.4 GB `wrfout`), so full priors + analyses would be ≈ 130 GB per cycle (≈ 520 GB for the pilot); the 0.9-GB DART-facing files (prior and analysis) plus the 15-min `wrfout` are the cheaper record, with the latest `wrfrst` per member kept for restarting. To settle before step 12 |
| Q11 | 00Z radiosondes (already in HRRR's analysis) | step 10 | Drop those launched at or before 00Z; check the time span of the 00Z soundings first |
| Q12 | Localization | step 11 | About 300 km full width horizontally and 0.5 scale height vertically, like HRRRDAS conventional observations; needs converting to DART's radian and normalization units |
| Q13 | Inflation with only 5 members | step 11 | Adaptive inflation is noisy at N = 5; start with the tutorial's adaptive prior setting with damping matched to the 15-min cycle, and watch it, or fall back to a fixed value |
| Q14 | Which MADIS families | step 9 | **Decided (user, 2026-09-29): METAR + ACARS + radiosondes + marine.** Mesonet is a second round with station selection and thinning |
| Q15 | Free advance before the first analysis | step 13 | None: analysis at 00:15, and watch the first cycles for adjustment noise (a 30–60 min free advance is the fallback) |
| Q16 | Fields carried in the bank and the members | steps 4–5 | **Decided (user, 2026-10-01): U, V, THM, QVAPOR, MU, as in the tutorial.** Carrying PH, P, PSFC (decided earlier the same day) was reverted; to explore if we see noise (see below) |
| Q17 | WRF `rebalance` at each member start | steps 7, 12 | **Decided (user, 2026-10-01): not set (default 0) in the first tests.** `rebalance = 1` (decided earlier the same day) was reverted; to explore if we see noise (see below) |

### Q16/Q17: pressure-related fields, scaling and `rebalance` (to explore if we see initialization or restart noise)

What the code does (checked 2026-10-01):
- **WRFDA** draws `xa%psfc` together with the wind, temperature and humidity increments. It derives the column-mass increment (→ `MU`) and the pressure increment `xa%p` (→ `P`) from them, and recomputes `PH` hydrostatically from the perturbed `MU`, θ and q (`var/da/da_transfer_model/da_transfer_xatowrf.inc`, lines ~96–166 and 283–307). So `PH`, `P` and `PSFC` in `wrfvar_output` are consistent with the other perturbations. The tutorial's bank drops them.
- **WRF**, on a cold start from `wrfinput` (`dyn_em/start_em.F`, ~lines 797–858):
  - keeps `PH` as read, unless `rebalance = 1`, in which case `rebalance_cycl` recomputes `PH` and `P` hydrostatically;
  - always derives the inverse density from `PH` and `MU` and then `P` from the equation of state, so the file's `P` is overwritten;
  - rediagnoses `PSFC` in the surface driver (`phys/module_surface_driver.F:2048`).

So a member with perturbed `MU`/θ/q but unperturbed `PH` (the tutorial's way) starts with inconsistent density and pressure.

Two kinds of balance are involved:
- **Hydrostatic** (`MU`, θ, q ↔ `PH`, `P`): a diagnostic relation that can always be restored by recomputing `PH`/`P`, either ourselves or with WRF's `rebalance = 1`.
- **Wind–mass:** CV3 ties part of the temperature and surface-pressure perturbations to the streamfunction through regressions (`be%reg_psi_t`, `be%reg_psi_ps`; `da_transform_vptox.inc:111–119`). Scaling all fields by one factor keeps that linear relation. The tutorial's scaling (winds/θ/q ×1.3, `MU` ×0.6) weakens the surface-pressure perturbation by about 2.2 relative to the winds, which recomputing `PH`/`P` can't fix. The tutorial gives no reason for the 0.6.

History: on 2026-10-01 the user first chose to carry `PH`, `P` and `PSFC` in the bank and to set `rebalance = 1`. Later the same day, after the balance discussion above, both were reverted: the first tests follow the tutorial (5-field bank, 1.3/0.6 scaling, `rebalance = 0`). Members therefore start with unperturbed `PH`, and after each `filter` update `PH` isn't updated either (Q8).

**Options to explore if we see noise** in the first segments after the initial members or after an analysis (surface-pressure tendency, vertical velocity, gravity waves):
- carry `PH` (and `P`, `PSFC`) from WRFDA in the bank, or recompute them after scaling;
- `rebalance = 1` in the member WRF runs (first check what `rebalance_cycl` does, including side effects such as its treatment of `PSFC`);
- one scale factor for all fields (e.g. 1.3), or no post-scaling with the amplitude set through `as1`–`as5` (×1.3 in amplitude = ×1.69 in variance), to keep CV3's wind–mass balance.

### Initial adjustment in the fake-increment test: hydrostatic imbalance from the unchanged PH (checked 2026-10-01)

**Question.** The modified-restart test (step 7, job 1047496) showed a large initial surface-pressure adjustment. Was the cause the tutorial's MU scaling (×0.6 vs ×1.3), or the missing PH/P perturbation (Q16/Q17)?

**The increment used.** `perts/members/pert_mem001.nc` (draw 4), already scaled (1.3 U/V/THM/QVAPOR, 0.6 MU) and centered (file attributes `scale_factors`, `centered = 1`). RMS versus the raw draw: U 0.52 vs 0.48 m/s, THM 0.98 vs 0.89 K, MU 33 vs 77 Pa, i.e. the scale factor times the centering reduction. PH was not perturbed.

**Diagnostic:** `scripts/da/check_hydrostatic_balance.py <static> <prior> <state> ...` (22 s on the login node). Run on the test's input, with the 00:15 restart file as both static file and prior: `tests/true_restart/continuous/wrfrst_d01_2025-05-20_00_15_00` and `tests/restart_increment/B2_recompute/input/dart_d01.nc`. It computes the non-hydrostatic pressure departure p_nh = p from the equation of state (density from PH and MU, hypsometric form as in `wrfrst_dart.py`) − moist hydrostatic pressure from MU and QVAPOR:

| State | p_nh RMS, all levels | RMS at k = 0 / 10 / 30 / 60 | Change from unperturbed |
|---|---|---|---|
| Unperturbed WRF state at 00:15 | 25 Pa | 44 / 43 / 41 / 19 | — |
| Fake increment, PH unchanged (as tested) | 205 Pa | 406 / 445 / 256 / 104 | 205 Pa |
| Fake increment + hydrostatic PH increment | 25 Pa | 43 / 43 / 41 / 19 | 0.1 Pa |

The 25-Pa baseline is partly discretization in the diagnostic; the change is what matters. "Hydrostatic PH increment" = PH recomputed hydrostatically from the perturbed state minus PH recomputed from the unperturbed state, added to the model's PH, so the model's own non-hydrostatic part is kept. It is 7.7 m RMS (max 31 m, 11.5 m RMS at the top).

**Interpretation.**
- With PH (so density) fixed, +1 K of THM raises the EOS pressure by γ·δθ/θ·p ≈ 4 hPa at low levels. The lowest-level pressure changes by 399 Pa RMS from the EOS, against 30 Pa from the hydrostatic MU change. The vertical pressure-gradient error is removed by vertical acoustic adjustment within seconds to minutes. That matches the spike (4,690 hPa/3h ≈ 2 hPa per 5-s step at step 2) and the small |dμ/dt| response: the adjustment is non-hydrostatic, not a column-mass one.
- Recomputing P alone doesn't help: WRF rederives P from PH, MU and THM at the first acoustic step (`calc_p_rho`), which is why B1 and B2 matched. PH is what has to change.
- **The MU scaling** (×0.6 vs ×1.3) affects wind–mass (CV3) balance, not hydrostatic balance. Its whole hydrostatic signal (30 Pa) is small next to the PH effect, so it is not the cause here. It may still add slower gravity-wave noise; test a single factor once PH is handled (Q16/Q17 options).

**Confirmed in WRF (job 1047521, 2026-10-01): case `B3_hydroph`** = B2 plus the hydrostatic PH increment (`restart_increment_test.py perturb --hydrostatic-ph`; `wrfrst_dart.py insert` unchanged). Same 8 nodes and 15-min restart segment. Domain-mean |dpsfc/dt| in hPa/3h (from `diag_print`):

| Case | Steps 2–8 | Minute 0–1 | Minutes 1–5 | Minutes 5–15 | \|dμ/dt\| (same windows) |
|---|---|---|---|---|---|
| B0 (no increment) | 95 … 95 | 95 | 93 | 90 | 44, 40, 35 |
| B2 (PH unchanged) | 4,640 3,754 2,550 2,931 2,417 1,614 1,521 | 2,131 | 223 | 94 | 51, 44, 37 |
| B3 (hydrostatic PH) | 231 340 254 288 259 199 152 | 200 | 97 | 91 | 50, 44, 37 |

- The spike drops about 20× and is gone after the first minute. Minutes 1–5 are back at the B0 level. What remains in the first minute (about 2× B0) is presumably the horizontal (wind–mass) part of the increment, e.g. the MU scaling. That's untested.
- |dμ/dt| is unchanged, as expected for a vertical adjustment.
- The 00:30 states of B2 and B3 are the same: RMS difference from B0 is equal for U V W T QVAPOR MU PSFC T2 PBLH, with PH 51.5 vs 51.4 and RAINNC 0.074 vs 0.076. In this test the vertical shock is transient and doesn't change the 15-min forecast. In cycling it would still put acoustic noise into the first minute of every segment, and it costs nothing to avoid.

**Consequences.**
- **Initial members (cold start at 00:00): fix needed.** They start with unperturbed PH, and with `rebalance = 0` WRF keeps PH as read (`start_em.F:797–807`), so the first segment gets the same imbalance. WRFDA's own PH perturbation fits only the unscaled draw, not the scaled and centered one. **Done 2026-10-01:** `make_initial_members.py` adds the hydrostatic PH increment, and the members were regenerated (step 5).
- **Member boundary files (step 6): same gap, open.** `build_member_bdy.py` writes the temporary states for `pert_wrf_bc` with the mean PH, so the PH boundary values and the record-end targets of `update_wrf_bc` are unperturbed while T and MU are perturbed. WRF relaxes PH toward them in the 10-row boundary zone. Fix: the same hydrostatic PH increment in `write_state`, then rebuild (one ~5-min job).
- **Cycling: check first.** PH is a required DART state variable (`model_mod.f90:7669`, "PH is always a required field"). It is `UPDATE` in the tutorial template and in our draft (`dart/mmc/input.nml`), and `wrfrst_dart.py insert` writes it back by default. So DART's PH moves with the analysis, and the imbalance should be much smaller than in this test. It is hydrostatic only as far as the ensemble covariances carry the relation (vertical localization, 5-member sampling noise, EOS nonlinearity). `rebalance` can't fix it: it acts only on cold starts (inside `IF (.not. config_flags%restart)`, `start_em.F:655`), and we cycle with true restarts.
- **Check at the first real `filter` (step 13):** compare DART's PH increment with the hydrostatic PH increment from the analyzed MU, THM and QVAPOR, and compute the p_nh change as above: `check_hydrostatic_balance.py <member wrfrst> <prior DART file> <analysis DART file>` (it prints both increments and their difference). If it is small next to the ~25-Pa baseline, keep DART's PH. If not, switch on `wrfrst_dart.py insert --hydrostatic-ph`, which replaces DART's PH increment with the hydrostatic one (what WRFDA does in `da_transfer_xatowrf`). Added 2026-10-01 as an opt-in option, off by default until this check. Tested on a copy of the 00:15 restart file with the fake increment: p_nh change 0.1 Pa, `PH_1 = PH_2`. This would also settle the PH part of Q8.

### Q8: how DART uses the state variables (checked 2026-10-01)

- **Every state variable is updated by every observation** within the localization radius, whatever the observation type: the EAKF regresses the observation-space increment onto each state element with the ensemble covariance (Δx = cov(x, H(x)) / var(H(x)) × ΔH). MU, PH and PSFC are no exception; any balance between them is what the ensemble covariances carry, to linear order. To restrict which observation types may change which quantities, `&assim_tools_nml obs_impact_filename` (an impact table) exists in our version.
- **`UPDATE` vs `NO_COPY_BACK`** (4th column of `wrf_state_variables`) only decides whether the analysis is written into the member files (`output` stage, `force_copy = .false.` in `filter_mod.f90`). `NO_COPY_BACK` variables are still in the state, used by the forward operators and updated, and their analysis values are written to the diagnostic files of `stages_to_write` (`preassim`/`postassim`/`analysis` mean, sd and members; `force_copy = .true.`) and used for the posterior values in `obs_seq.final`.
- **Surface observations need the 2-D fields.** For an observation with a `SURFACE` vertical coordinate (METAR, marine), `model_mod.f90` uses only T2, Q2, U10/V10 and PSFC (or MU + MUB + p_top for surface pressure). If T2, Q2 or U10/V10 is not in the state, the forward operator returns missing and the observation is rejected (DART QC 4); there is no fallback to the lowest model level.
- **They affect the 3-D update only through the forward operator:** the prior ensemble of T2 etc. sets the innovation, the outlier check and the regression of every 3-D variable on the observed quantity. DART computes all forward operators before assimilating, so the updated T2 itself does not feed back. WRF's surface layer recomputes T2, Q2, U10, V10 and PSFC every step, so writing them back has no effect on the forecast either way.
- **Pressure in DART** comes from its own state, never from WRF's `P`: density from PH and MU (`model_rho_t`), full pressure from the equation of state with THM and QVAPOR (`model_pressure_t`), heights from PH. So PH and MU must be in the state even if not written back.
- Current draft list (`cases/20250520/dart/mmc/input.nml`, for `model_mod_check`): U, V, W, PH, THM, MU, QVAPOR, PSFC, all `UPDATE`; no hydrometeors and no 2-m/10-m fields (the tutorial template has both, all `UPDATE`).

### Q5 experiment: boundary perturbation pattern (after the 1-hour pilot)

Both options give the same across-member spread at each hour. Option B adds temporal variability: each member's boundary tendency gains (p_{h+1} − p_h)/3600 s (variance up to 2σ² per hour, zero for A), inflow air carries decorrelated patterns, and the bank is sampled more. That can help (more realistic boundary uncertainty) or hurt (gravity waves, spurious edge precipitation, as HRRRDAS saw when perturbing 3-km boundaries directly).
- **Build:** two sets of member boundary files from the two assignment tables (A: one draw per member for all hours; B: 5 distinct draws per hour from the 15, centered each hour). Keep the initial members identical.
- **Compare, in order:** (1) a free 5-member ensemble forecast without observations for 6–12 h: spread against distance from the boundary and against time, surface pressure tendency, vertical velocity, edge precipitation; (2) cycling with observations: innovation statistics and spread against error.
