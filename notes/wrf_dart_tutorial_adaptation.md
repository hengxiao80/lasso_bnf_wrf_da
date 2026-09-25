# Adapting the WRF-DART tutorial workflow to BNF

Written 2026-09-24 after going through the WRF-DART tutorial
(<https://docs.dart.ucar.edu/en/stable/models/wrf/tutorial/README.html>, "Manhattan", 2024-05-19
Great Plains case) and reading the scripts it runs, in our checkout
`../software/DART/models/wrf/shell_scripts/` (DART v11.25.3). Statements about script behavior
come from reading that code. Items marked **(verified)** were also checked on our files or
executables. Moist/dry theta is set aside for now (`theta_m0` setup, per the user).

Related: `dart_input_nml_comparison.md`, `dart_namelist_discussion_log.md`, and plan Phases 3-4 in
`initial_plan_from_codex/LASSO_BNF_DA_Detailed_Implementation_Plan_rev2.md`.

## 1. The tutorial workflow in one table

| Step | Script(s) | What it does | Tutorial setting |
| --- | --- | --- | --- |
| Setup | `param.sh`, `setup.sh` | Paths, ensemble size, PBS settings; creates `rundir/`, `output/`, `perts/`, ... and copies executables and `input.nml` | 20 members, 2 domains, 6-h cycles, Derecho/PBS |
| Mean IC/BC | `gen_retro_icbc.sh` (+ `real.sh`) | For each cycle: WPS on GFS, then `real.exe` twice. Writes `output/<YYYYMMDDHH>/wrfinput_d0?_<gday>_<gsec>_mean` at the start and end of the window, plus `wrfbdy_d01_<gdayf>_<gsecf>_mean` | GFS 0.25, 6-hourly |
| Perturbation bank | `gen_pert_bank.sh` | One PBS job per draw, each running `da_wrfvar.exe` (RANDOMCV, CV3 `be.dat`); `ncdiff` of U,V,THM,QVAPOR,MU gives `pert_bank_mem_N.nc` | 3 x ensemble size = 60 draws |
| Initial ensemble + spin-up | `init_ensemble_var.sh`, `add_bank_perts.ncl`, `first_advance.sh`, `new_advance_model.sh` | Adds a bank perturbation to the mean (scaled 1.3 for U/V/THM/QV, 0.6 for MU); `ndown` for d02; one PBS WRF job per member, 6 h | 6-h spin-up |
| Inflation init | `fill_inflation_restart` | Writes `input_priorinf_*.nc` (mean 1.0, sd 0.6) | by hand, once |
| Cycling | `driver.sh` -> `prep_ic.sh`, `assimilate.sh` (filter), `diagnostics_obs.sh`, `assim_advance.sh` -> `new_advance_model.sh` (`add_bank_perts.ncl` + `pert_wrf_bc`) | A long-running shell loop on the login node: `qsub` filter, poll for flag files, `qsub` one advance per member, poll, archive | 2 analyses |
| Forecast mode | same driver | Evaluate-only obs, inflation off, perturbation scales 0 | 12 h |
| Diagnostics | `obs_diag`, `obs_seq_to_netcdf`, MATLAB scripts | obs-space RMSE, spread, QC | |

Observations are pre-staged as `obs_seq.out` (from PREPBUFR). The tutorial only describes the
converter chain (`prepbufr.csh` -> `create_real_obs`).

## 2. What changes for us

### 2.1 Scheduler and job structure (largest change)

- The tutorial submits one PBS job per member per cycle and waits on flag files from a `driver.sh`
  running on the login node. For us that would be 50 jobs x 96 cycles/day, each waiting in the queue.
  `batch_all` has 128 nodes (128 cores each; **(verified)** `sinfo`: ~98 allocated and 13 idle at the time
  of checking), so queue wait would dominate.
- Replace this with **one Slurm allocation per cycle, or per block of cycles**. Inside it, launch the
  members as concurrent `srun --exclusive -N k ...` steps in the background and `wait`, then run
  `filter` in the same allocation. Run the driver itself as a chain of Slurm jobs (`--dependency`),
  not on a login node. This is the `cycle_driver.py` of plan Step 4A.
- Add the UCX settings (`UCX_TLS=self,sm,ud`, `UCX_UD_MLX5_RX_QUEUE_LEN=16384`) and the
  `SUCCESS COMPLETE WRF` check to every job; `new_advance_model.sh` already greps for it.
- Rough cost from the baseline run (16 nodes, ~4 h for 72 h): ~50 s wall on 16 nodes per 15-min
  segment, about 13 node-minutes per member-cycle. For 50 members that is ~11 node-hours per cycle
  (~1,070 node-hours per model day) for WRF alone, with ideal scaling. Every segment is also a cold start
  (read `wrfinput`, physics initialization, Thompson tables), which may cost as much as the 900 s of
  integration. Measure one segment before choosing nodes per member (plan Step 5A).

### 2.2 15-minute cycling instead of 6-hourly

- `driver.sh`, `gen_retro_icbc.sh`, `first_advance.sh`, `init_ensemble_var.sh`, `gen_pert_bank.sh` and
  `diagnostics_obs.sh` use `ASSIM_INT_HOURS` and `YYYYMMDDHH` directory names throughout.
  `diagnostics_obs.sh` computes `half_bin = ASSIM_INT_HOURS/2`, which is integer hours.
  `ASSIM_INT_MINUTES` exists in `param.sh`, but only `assim_advance.sh` uses it. Its own header says
  "ASSIM_INT_MINUTES support needs to be added".
- **(verified)** `advance_time` already handles this: `2025052000 15m` -> `202505200015`, `-15m`
  works, `-g` gives `155002 900`, and 12-digit inputs (`YYYYMMDDHHMM`) are accepted. The tool is
  fine; the scripts need editing. Use `YYYYMMDDHHMM` directory names.

### 2.3 Mean IC/BC: reuse our HRRR pipeline, don't run `gen_retro_icbc.sh`

- We already have 73 hourly HRRR `met_em` files and a working `real.exe` setup
  (`cases/20250520/theta_m0/`). `gen_retro_icbc.sh` is GFS-specific (it exits unless `GRIB_SRC=GFS`)
  and reruns WPS for every cycle.
- What we need is a **mean `wrfinput` at every hour** plus the hourly `wrfbdy`. Get these from a loop
  of `real.exe` runs, one per hour, in a single Slurm job. They are inputs for building the member
  boundary files (2.12) and the initial ensemble; the cycle itself no longer reads them.
- **How a 15-min segment fits an hourly boundary record** (discussed 2026-09-24; details in 2.12).
  The record-end time lives in the character variable
  `md___nextbdytimee_x_t_d_o_m_a_i_n_m_e_t_a_data_` (start time:
  `md___thisbdytimee_x_t_d_o_m_a_i_n_m_e_t_a_data_`), one entry per record. **(verified)** In our
  `wrfbdy_d01`, record 1 runs 00:00 → 01:00, record 2 runs 01:00 → 02:00, and so on. For a member at
  00:15, the DART boundary tools:
  - pick the record containing 00:15 (`find_time_index`: the last record with `Times` ≤ 00:15);
  - set its start time to 00:15;
  - put the member's own state there as the start value `B`;
  - set the tendency to (target at 01:00 − `B`) / 2700 s.
  
  WRF runs 900 s of that record. **(verified)** WRF uses the rewritten times itself:
  `share/input_wrf.F:1182–1192` picks the record with `this ≤ current < next` from those metadata,
  and `mediation_integrate.F:1536` sets `dtbc = 0` when current = this. No 15-min mean files are
  needed. Resetting `B` to the analysis is not specific to 15 min; the tutorial does it every cycle.
  What is new is that three of every four segments start partway through a record.
- `pert_wrf_bc` stops unless its target file's time equals the record end ("Times in wrfinput_next and
  wrfbdy_this are not same"), because it always divides by (record end − current time). Keep that check.
  Separately, `new_advance_model.sh` links the target to the mean at the *segment end*
  (`wrfinput_d01_${targdays}_${targsecs}_mean`). That is right in the tutorial, where segment end = record
  end. For us it would look for a 00:30 file that doesn't exist. On the `pert_wrf_bc` route it would have to
  link the record end (`${iday}_${isec}`) instead. The precomputed route in 2.12 removes the question.

### 2.4 Perturbation draws must be fixed, not random per call

- `add_bank_perts.ncl` picks a bank member by seeding from the wall clock (`date -u +%N`) every time it
  runs. Consequences for us:
  - The initial members can draw the same bank entry (nothing enforces uniqueness), and runs are
    not reproducible.
  - With 15-minute cycles, the same hourly boundary endpoint is perturbed four times, by four
    different draws. The boundary target jumps every 15 minutes.
- Use a saved member-to-bank assignment, with the same draw for a member at a shared endpoint (plan
  Steps 3C and 3D). The perturbation added to `wrfinput_next` should be identical in all four
  segments that end at the same hour.
- Note on terms: the "mean" file is the unperturbed HRRR `real.exe` state, which is never modified. The
  boundary target is a per-member copy with that member's bank perturbation added
  (`new_advance_model.sh` lines 511–537: `fg` → `wrfvar_output` → `add_bank_perts.ncl` → `wrfinput_next`).
- With the precomputed member boundary files in 2.12, draws are made once when the files are built.
  So this problem, and `add_bank_perts.ncl` in the cycle, go away. The initial members still need the
  saved assignment.

### 2.5 Carry the full member state forward

- The "mean file" (`output/<date>/wrfinput_d01_<gday>_<gsec>_mean`) is the unperturbed `real.exe`
  analysis from `gen_retro_icbc.sh`. It is named "mean" only because the ensemble was built by
  perturbing it; nothing ever averages the members. EAKF does update each member individually. The
  issue is what WRF restarts from. Each cycle, `driver.sh` deletes `advance_temp$n` and links the mean
  file in as `wrfinput_d01`. `prep_ic.sh` then copies in `cycle_vars_a` from the member's prior, `filter`
  updates that file (via `input_list_d01.txt`), and `new_advance_model.sh` copies `increment_vars_a` back
  from `filter_restart_d01.NNNN` before running WRF. Any field not on those lists is reset to the
  unperturbed `real.exe` value, identical for every member, every cycle. For our physics (Thompson aerosol-aware, `mp_physics = 28`) the list
  is missing `W`, `QNCLOUD`, `QNWFA`, `QNIFA` and `QNBCA` (and `T`; see 2.7). These would be put back to
  the mean every 15 minutes, while `QCLOUD` and the others stay member-specific.
- **(verified)** A `wrfout` cannot simply replace `wrfinput`. It lacks `T_INIT`, `*_BASE`, `LANDUSEF`,
  `STEP_NUMBER`, lake and urban fields, and others (65 variables). Keep the mean hourly `wrfinput` as the
  static template, but copy **all time-varying fields** from the member's own `wrfout`, then overwrite
  the variables DART updated. This is plan Step 4C's "complete native member backing state".
  (Superseded by 2.11: restart from the member's own `wrfout`, with the missing fields added to the
  history output.)

### 2.6 Field coverage of `pert_wrf_bc` / `update_wrf_bc`

- Both update the same 12 3-D fields (`U V W PH T QVAPOR QCLOUD QRAIN QICE QSNOW QGRAUP QNICE`) plus
  `MU`, all coupled with (μ + μ_b). **(verified)** Our `wrfbdy` also has `QNRAIN`, `QNCLOUD`, `QNWFA`,
  `QNIFA`, `QNBCA`, `LIGHTNING_*`, `HT_SHAD` and `PC`.
- **Why that matters only with mid-record starts.** For a field neither tool touches, the record's start
  time is still moved to 00:15, but `B` stays the 00:00 value and `tend` the hourly one. WRF then reads it
  as 15 min late: a field going 0 → 4 over the hour shows 0 at 00:15 instead of 1, and reaches only 3 at
  01:00 instead of 4. The lag is 15, 30 or 45 min depending on where the segment starts. In the tutorial
  (segments start at record starts) it never arises.
- **Proposed fix (local patch in `patches/`).** For every boundary field the tool doesn't recompute, move
  `B` forward along the original line, `B + tend × (udtime − old thisbdytime)`, and keep `tend`. This is
  exact for those fields and needs no per-field list. Adding the Thompson number and aerosol fields to the
  recomputed list, with coupling, is the alternative if we want them fitted to the member state too.

### 2.7 `T` versus `THM` in the boundary step (a naming issue, not the moist/dry conversion)

- **Which field is integrated. (verified, WRF Registry `Registry.EM_COMMON` lines 210–212)**
  - `state real t ikjb dyn_em 2 ... "thm"`: symbol `t`, two time levels (`t_1`, `t_2`; `t_2` is the one
    advanced and written), file name `THM`. Moist or dry perturbation theta depending on `use_theta_m`.
    The `b` in `ikjb` gives it boundary arrays, named after the symbol: `T_BXS`, `T_BTXS`, ... So the
    boundary arrays called `T_*` belong to `THM`.
  - `state real th_phy_m_t0 ikj dyn_em 1 ... "t"`: file name `T`. Always dry perturbation theta,
    recomputed from `t` during the run (`module_big_step_utilities_em.F:5727`, `:5739`). No boundary
    arrays.
  - Both are read from `wrfinput`. `THM` seeds the integration; `T` is overwritten.
  - In our `theta_m0` files `T == THM` exactly.
- **The problem.** `pert_wrf_bc` and `update_wrf_bc` both read `var3d(5)='T'` (from `wrfinput_this`, and
  `pert_wrf_bc` also from `wrfinput_next`) to write `T_BXS`/`T_BTXS`. With `use_theta_m = 0` that gives
  the right numbers only as long as `T` and `THM` stay equal. In the DART workflow they don't:
  `add_bank_perts.ncl` perturbs only `THM` in the target, and DART updates only `THM` in the member.
  As read from the code (not yet run), the boundary temperature then starts from the unanalyzed `T` and
  heads to an unperturbed target, so **no thermal spread enters at the boundaries**.
- **Why it's there. (verified, DART git history)** The boundary utilities' logic last changed in July 2008
  (`e540ee577`, from Ryan Torn), when WRF 2/3 wrote the integrated temperature as `T`. In April 2024
  DART moved its perturbation scripts to `THM` (`2997de9fd`, "Adding perturbations to WRF THM
  variable"; the tutorial's issue #661) but didn't touch these two utilities. It's an incomplete
  WRF 3 → 4 migration.
- **Decision (2026-09-24).**
  1. Confirm in the first one-member boundary test: compare `T_BXS` after the call with `THM` along the
     boundary rows of the member (analysis) file and the target.
  2. Patch both utilities to read `THM` (`var3d(5)`), recorded in `patches/` with the reason. This is also
     what `use_theta_m = 1` will need later: there `T_BXS` holds moist theta and `T` is dry, so reading
     `T` would be wrong outright.
  3. If the test confirms it, report it to DART on GitHub. The user decides and posts; Claude can
     draft the text.

### 2.8 Smaller items

- Single domain: `NUM_DOMAINS=1`, `tutorial/template/` rather than `template_nest`. Skip the `ndown`
  block in `init_ensemble_var.sh`.
- Tools: `nco/4.9.3`, `ncl/6.6.2-py3-serial` and `cdo` are available as modules, but `env_wrf.sh`
  does not load them. The NCL scripts are short (`add_bank_perts.ncl`, `mean_increment.ncl`), so
  porting them to Python in the project `uv` environment fits the plan and removes the NCL dependency.
  NCO can stay.
- Perturbation bank: 150 draws (3 x 50), run as a Slurm array. Build `namelist.input.3dvar` from our
  grid (550x390x150, 2.5 km, projection), not the tutorial template. Test one draw first (plan 3B). In
  `gen_pert_bank.sh`, `IC_PERT_SCALE` and the related variables are effectively unused; the `as*`
  values in the 3dvar namelist are what take effect.
- Observations: nothing is pre-staged for us. MRMS plus PREPBUFR conversion is its own pipeline
  (plan Phase 2). `driver.sh` aborts if `obs_seq.out` is missing. The plan wants an explicit empty-obs
  path instead.
- Timeline: the tutorial starts at 00Z with 6-h spin-up to the first analysis. Our case runs
  2025-05-19 00Z to 05-22 00Z. **Decided 2026-09-25: spin up by cycling, not by a free forecast** (see 2.13).
- Forecast mode, in which the tutorial zeroes the perturbation scales and uses evaluate-only obs, is not
  needed for the parent trajectory. Keep it as the pattern for the "no local DA" forecasts in plan 5C.
- Diagnostics: `obs_diag`/`obs_seq_to_netcdf` carry over as is (bins become 15 min). Replace the
  MATLAB plots with Python.
- Archiving: the tutorial gzips and tars per cycle. At 96 cycles/day with ~GB-size member files,
  set retention deliberately (plan 5A storage estimate).

### 2.9 Points from `codex.WRF_DART_Discussion_and_Branches_Summary_v1.md`

- **Call chain.** That discussion confirmed the chain `init_ensemble_var.sh` -> member job ->
  `first_advance.sh` -> `new_advance_model.sh` -> `wrf.exe`. It is one advance, not two, and a
  missing `filter_restart_*` is expected on the first advance. The same holds for us: every item in
  2.3-2.7 lands in `new_advance_model.sh` (or our replacement of it), and the first-advance path and
  the cycling path share it. The adapted script must keep the "no posterior yet" branch.
- **Inflation.** That discussion left the tutorial's actual inflation settings as a follow-up; they are now
  checked. **(verified)** `tutorial/template/input.nml.template`: prior `inf_flavor = 2` (Gaussian,
  spatially varying), `inf_damping = 0.9`, `inf_sd_initial = inf_sd_lower_bound = 0.6`,
  `inf_upper_bound = 10000`, `inf_sd_max_change = 1.05`; posterior inflation off.
  - Damping is applied **once per cycle**. At 15-min cycles, 0.9 per cycle is 0.9^24 ≈ 0.08 per 6 h,
    against 0.9 per 6 h in the tutorial. So inflation relaxes toward 1 about 24 times faster in
    physical time. If the intent is the tutorial's time scale, damping near 0.9^(1/24) ≈ 0.996 per cycle
    is the equivalent. Decide this deliberately (plan 4B `inflation_policy.yaml`).
  - Likewise `inf_sd_max_change = 1.05` per cycle allows the inflation uncertainty to grow much faster
    per hour.
  - The inflation files must pass from each 15-min cycle to the next. `driver.sh` renames
    `output_priorinf_*` to `input_priorinf_*` in `output/<date>/Inflation_input/`, with names that
    depend on `stages_to_write`. Use the names the pinned version actually writes. They are not
    necessarily `output_*`.
- **Obs processing.** `wrf_dart_obs_preprocess` does domain, boundary and elevation screening, and
  superobbing for aircraft and satellite winds. It is useful for the conventional stream only. MRMS
  sampling belongs in our radar converter before `filter`. `preprocess` is a build step, unrelated to
  either.
- **Spin-up.** If every member has zero reflectivity or `qr` variance at the first analysis, inflation
  cannot create it. Choose the spin-up length (2.8) by checking hydrometeor and reflectivity spread at
  the first analysis time, not by copying 6 h.
- **Output volume.** The template writes `stages_to_write = 'preassim', 'postassim', 'output'` with
  `output_members`, `output_mean` and `output_sd` all `.true.`. That means three full 50-member state
  copies every 15 min. For routine cycling, keep mean and sd per stage and write members only at
  `output`.

### 2.10 How HRRRDAS (HRRRv4) builds member states, and what it does with `W`

Sources: the NOAA-EMC/HRRR repo, cloned to `../software/HRRR` (`develop` = `40ee6058`, synced
from `hrrr.v4.1.20`; the Codex notes' reference commit `44728d00` is in its history), and the HRRRDAS
documentation (Dowell 2020, "HRRR Data-Assimilation System (HRRRDAS) and HRRRE Forecasts",
<https://rapidrefresh.noaa.gov/internal/pdfs/2020_Spring_Experiment_HRRRE_Documentation.pdf>, pp. 3-6).

- **Each member continues from its own forecast.** **(verified, code)**
  `scripts/hrrrdas/exhrrr_analysis.sh` copies the member's own full 1-h `wrfout`
  (`hrrrdasges/hrrrdas_d01_<t-1h>f01_memNNNN`) to `hrrr.t<cyc>z.wrfinput_d01.memNNNN`.
  `exhrrr_enkf.sh` links that same file as both `firstguess.memNNN` and `analysis.memNNN`, so the
  EnKF writes into it in place. `sorc/.../enkf/gridio_wrf.f90` reads each analysis variable, adds the
  increment and writes it back. `exhrrr_fcst.sh` then starts WRF from that file. Every field that isn't
  analyzed, **including `W`**, is the member's own forecast value. There is no shared template file
  like the tutorial's "mean". A true ensemble mean is computed separately (`hrrr_cal_ensmean`), but
  only for the GSI observer.
- **`W` is not an analysis variable.** (Documentation p. 5-6; the operational `anavinfo` files are in a
  fix directory that isn't in the repo or on the NCO site, so this rests on the 2020 document.) The
  conventional EnKF pass updates `U, V, T, QVAPOR, QCLOUD` (300 km horizontal / 0.5 scale height
  localization, RTPS 1.08 at 3 km). The reflectivity pass adds `QRAIN, QSNOW, QGRAUPEL` (18 km / 0.5
  scale height, RTPS 1.08). Neither pass updates `W`, `MU` or `PH`. The GSI EnKF code *can* update
  `W` and `PH` for ARW (`w_ind`, `ph_ind` in `gridio_wrf.f90`) if `anavinfo` lists them; HRRRDAS
  (as documented) doesn't. So `W` passes through each analysis unchanged: neither analyzed nor
  reset. WRF then adjusts it dynamically to the analyzed winds and temperature.
- **Post-analysis steps.** A fifth step sets `QNRAIN` from the analyzed `QRAIN` (Marshall-Palmer),
  because analyzing `QNRAIN` didn't help. They note `QNCLOUD` could be treated the same way but
  isn't. Before the EnKF, the GSI observer also clears clouds and hydrometeors in each member using
  GOES, METAR and MRMS (non-variational, as in deterministic HRRR).
- **Boundaries.** Member `wrfbdy_d01` files are made four times a day from GFS plus bank perturbations
  of `MU, U, V, T, QVAPOR`. Before each 1-h member forecast, `hrrr_update_bc` fits the boundary file to
  that member's analysis (the equivalent of DART's `pert_wrf_bc`/`update_wrf_bc`). The perturbations
  go on a **15-km outer domain**, whose only purpose is to let them develop before reaching the 3-km
  grid. The documentation says perturbing the 3-km boundaries directly "produced artifacts, such as
  unrealistically heavy precipitation near the boundaries". That applies to our single 2.5-km domain
  (plan Step 3D). Watch for it in the boundary test, and keep an outer domain in mind as a fallback.
- **Cold starts.** New members are built from RAP plus GDAS ensemble perturbations of
  `T, U, V, QVAPOR, MU` (`initialens.x`, with a column inflation factor decreasing from 2.0 at level 1
  to 1.0 by level 26). Half the members are replaced every 12 h ("rolling" retirement at 09 and 21
  UTC). This is an operational robustness feature that a 3-day case study doesn't need.

**What this means for 2.5.** Follow HRRRDAS: take each member's own `wrfout` as its prior and
analysis file, and apply the DART update to it in place. That keeps `W` and all other non-analyzed
fields (`QNCLOUD`, aerosol numbers, land state) continuous. Two caveats:
- A `wrfout` lacks some `wrfinput` fields (2.5). HRRRDAS restarts WRF from a `wrfout` copy, so
  its history output must contain what WRF needs; how it achieves this (e.g. `iofields`, Registry
  changes) is not yet checked. We either add those fields to the history output (`iofields_filename`) or copy them
  from the hourly mean `wrfinput` once per member.
- Whether to add `W` to DART's `wrf_state_variables` is a separate choice. HRRRDAS doesn't, and
  leaving it out is the conservative first setting.

### 2.11 Decision (2026-09-24): restart each member from its own `wrfout`, with the missing fields added

Decided by the user: each cycle, the member's own `wrfout` becomes its prior/analysis file and WRF
restarts from it, as HRRRDAS does (2.10). The fields a `wrfout` lacks are added to the history output
rather than copied in from a template.

- **How HRRR does it.** **(verified, code)** HRRR has no `iofields` file (`parm/hrrrdas/hrrrdas_wrf.nl`)
  and `write_input = .false.`. Instead, its WRF 3.9 Registry (built with `WRF_SMOKE=1`, so
  `Registry.EM_SMOKE` and its includes) adds the `h` flag to **25** of our 65 missing fields:
  `U_BASE V_BASE T_BASE QV_BASE Z_BASE U_FRAME V_FRAME STEP_NUMBER LANDUSEF SOILCTOP SOILCBOT
  TOPOSLPX TOPOSLPY LAKE_DEPTH LAKEFLAG LAKE_DEPTH_FLAG DTS DTSEPS FCX GCX FNDALBSI FNDICEDEPTH
  FNDSNOWH FNDSNOWSI FNDSOILW`. The other **40** stay out of HRRR's history: `T_INIT`, the 32
  `LAT_*`/`LON_*` corner fields, `AL ALB CPLMASK EROD FRC_URB2D UOCE VOCE`. So HRRRDAS restarts
  WRF 3.9 without them. That doesn't prove WRF 4 can. (Corrected 2026-09-25 from "26/39": the first
  comparison mixed in HRRR's chem Registry files, which gave `EROD` an `h` it doesn't have in the
  smoke build.) The full per-field list is in `wrfout_restart_fields.md`.
- **The 32 corner fields** (`LAT|LON` × `LL|UL|UR|LR` × `T|U|V|D` staggering) are scalars that no WRF
  code uses (only the Registry and `run/gribmap.txt` mention them). They are 0.0 in our `wrfinput`. So of
  the 40, only `T_INIT AL ALB CPLMASK EROD FRC_URB2D UOCE VOCE` could matter.
- **Proposed for us: the runtime equivalent, not a Registry edit.** WRF's `iofields_filename`
  (`&time_control`) adds fields to a stream at run time, with no rebuild and no change to the pinned
  WRF. Add **all 65**, a superset of HRRR's list, so we don't depend on which of them WRF 4 actually
  needs. The cost is small: the only 3-D fields are `T_INIT` (150 levels, ~130 MB at 4 bytes) and
  `LANDUSEF`, against ~3.8 GB per `wrfout`. File contents, one line:
  `+:h:0:<comma-separated list of the 65 names>`. Also set `ignore_iofields_warning = .true.`.
- **Test before use** (one short job):
  1. Run WRF 30 min from `wrfinput` with the iofields file, writing history at 15 min.
  2. Restart a second run from the 00:15 `wrfout` (renamed `wrfinput_d01`) for 15 min.
  3. Compare its 00:30 state with the continuous run's 00:30 output.
  
  Expect small differences, not bit-for-bit agreement: a cold start re-initializes physics. Also check
  `ncdump -h` that all 65 fields appear in the `wrfout`, and that `rsl` shows no missing-field warnings
  on the restart.

### 2.12 Proposed LBC design (2026-09-24): precomputed member boundary files + `update_wrf_bc`

Suggested by the user; it is also how HRRRDAS works (2.10: perturbed member `wrfbdy` files built ahead
of time, `hrrr_update_bc` before each forecast).

1. **Once, before cycling.** For each member, build a boundary file for the whole case (72 hourly
   records). Record h runs from (HRRR mean + that member's perturbation) at hour h to the same at
   h+1, with WRF's (μ + μ_b) coupling and tendency = difference / 3600 s. The member-to-bank
   assignment, scaling and any centering are fixed here and saved (plan 3C/3D). The perturbed hourly
   states are only needed while building and can be deleted afterwards.
2. **Before each 15-min segment.** Copy an untouched member boundary file and run `update_wrf_bc` with
   the member's analyzed file (its own `wrfout` with the analysis written in, 2.11). **(verified,
   `update_wrf_bc.f90` lines 170–177, 525, 583)** It:
   - finds the record containing the current time;
   - recovers the record-end value from the untouched record as `tend × bdyfrq_old + B` (the member's
     perturbed state at the next hour);
   - sets `B` to the member's analysis;
   - sets `tend = (end − B) / (record end − now)`.
   
   Its optional `infl` term, read from stdin, stays 0. WRF then runs 900 s.

`new_advance_model.sh` already has this branch: without `WRF_RUN/da_wrfvar.exe` it uses
`wrfbdy_d01_*_${member}` and calls `update_wrf_bc` (lines 334, 421, 553). We adapt it rather than write a
new one.

- **Gains.** Every segment in an hour aims at the same member target (2.4 is solved by construction).
  The boundaries are reproducible and can be inspected before cycling (spread, centering, edge
  artifacts; HRRRDAS saw heavy spurious precipitation when perturbing 3-km boundaries directly). The
  per-cycle step is one small Fortran call: no NCL, no 1.2-GB mean `wrfinput` copies, no mean files
  during cycling.
- **Cost. (verified sizes)** Our `wrfbdy_d01` for 72 h is 9.3 GB (compressed netCDF-4), so 50 member files
  come to about 460 GB. Perturbed hourly `wrfinput` targets would instead be about 4.3 TB
  (1.19 GB × 50 × 73).
- **Still needed.**
  - The `THM` patch (2.7).
  - The patch for fields `update_wrf_bc` doesn't recompute (2.6). The member files must also carry
    those fields.
  - A builder for the member boundary files: new code, run once and checked offline.
  - Each segment must start from an untouched copy of the member file, because the end-value recovery
    assumes the original record.

**Boundary test (first job after the mean files exist).** One member, one segment starting at 00:15:
1. Rebuild the boundary values at 00:15 and 01:00 from `B` and `tend`, and compare with the member's
   analyzed state and its perturbed 01:00 target, for all fields.
2. Check `T_BXS` against `THM` (2.7).
3. Check the fields `update_wrf_bc` doesn't recompute for the 15-min lag (2.6).
4. Time the WRF cold start.

### 2.13 Decisions (2026-09-25): spin-up by 15-min EAKF cycling; first observations from public MADIS

**Spin-up strategy (user's decision).** The 500-m runs need 15-min analyses from **2025-05-20 00Z**
onward. Cycling starts some hours earlier (6 or 12 h; not fixed yet), right after the initial ensemble is
built from HRRR plus bank perturbations. The EAKF cycling is the spin-up, replacing a free-running
ensemble forecast (tutorial: 6 h; plan 3E) for two reasons:
1. It keeps the ensemble from drifting away from the observations, as a free spin-up would.
2. Spread, observation rejection rates and adaptive inflation can be watched and controlled from the first
   cycles.

The spin-up length is to be judged from those diagnostics, not fixed in advance.

Points to handle (for the design, not blocking):
- **Observations already in HRRR.** HRRR at the start time has already used the reports valid then. The
  first cycle (start + 15 min) should take only reports after the start time (plan 3C).
- **Early spread is purely from the bank perturbations.** It isn't yet flow-dependent, and the perturbations
  aren't balanced, so the first segments will carry adjustment noise. Monitor it. A short free advance before
  the first analysis (e.g. 30–60 min) is an option if the first analyses look noisy.
- **Hydrometeor spread starts near zero,** so reflectivity can't do much in the first cycles (2.9). The
  spin-up is naturally conventional-first; radar joins once hydrometeor spread exists.
- **Adaptive inflation adapts during the spin-up.** Its state at 05-20 00Z is part of what the spin-up
  produces.
- **Cost:** 4 cycles per hour, so 12 h of spin-up is 48 extra cycles.

**Conventional observation source: public MADIS** (checked 2026-09-25):
- **No hourly RAP PREPBUFR archive** (what HRRR uses: `rap.tHHz.prepbufr.tm00`, `rap_e` at 00/12Z) was
  found for 2025. Only 6-hourly GDAS `.nr` PREPBUFR exists, on AWS `noaa-reanalyses-pds` and GDEX
  `d337000`.
- **Public MADIS** (`madis-data.ncep.noaa.gov/madisPublic1/data/archive/`) has hourly files for our dates,
  reachable from here without an account. The research archive (403) needs MADIS credentials.
- **DART's converters match the current files.** Every variable they read is present, except ACARS
  `downlinkedRHQCR`, which the converter fills with 0 ("pass"), so ACARS humidity carries no MADIS QC.
  Every type they write is already compiled into our `filter`.
- **Reports per hour in our domain** (18Z 05-20): METAR 744, ACARS 5,732, mesonet 18,941 (public networks
  only), marine 30, radiosondes 8 at 12Z (JAN SHV BMX FFC LZK OHX SGF TOP). 915-MHz profilers: 0 in the
  domain. Satellite winds (`HDW`): none in the public archive for this date.
- **Time coverage per file:** ACARS and mesonet files hold HH:00–HH:59; METAR and marine files hold
  HH−15 min to HH+45 min. Bin by report time into 15-min windows and use each report once.
- **First set:** METAR, ACARS, radiosondes. Then mesonet, with station selection, QC, thinning and
  representativeness errors (HRRR uses a mesonet use-list). Satellite winds (GOES derived motion winds or the
  GDAS PREPBUFR satellite-wind types) and radar come later.
- **Data:** `cases/20250520/obs/madis/<family>/YYYYMMDD_HH00.gz` for 05-19, 05-20 and 05-21, all hours
  (downloaded 2026-09-25, all pass `gzip -t`): acars, marine, mesonet, metar 72 files each; raob 53 (launch
  hours only). About 2.3 GB compressed, mostly mesonet (2.1 GB). Single-hour test files are in
  `cases/20250520/obs/madis_test/`. Not downloaded: the 05-22 00Z METAR/marine files (reports from
  05-21 23:45), needed only if cycling runs past 05-21 23:30.

**Aircraft (ACARS) observations and the humidity QC decision** (2026-09-25):
- **Names.**
  - ACARS: the airline datalink.
  - MDCRS: the US service that collects airline weather reports over ACARS for NWS.
  - AMDAR: the WMO umbrella program for all automated airline reports.
  - TAMDAR: licensed sensors on regional aircraft; empty in public MADIS.
  - WVSS-II: the aircraft water-vapor sensor, the source of aircraft humidity.
  - AIREP/PIREP: manual pilot reports.
- **Labels by source.**
  - MADIS `point/acars`: all automated aircraft reports. In the 18Z 05-20 file (50,869 reports), 17,017 carry
    WVSS test flags (`wvssTest1`).
  - PREPBUFR: `AIRCAR` (133/233) = ACARS/MDCRS; `AIRCFT` (130/230, also 131/231) = other aircraft.
  - DART: `ACARS_*` (133) vs `AIRCRAFT_*` (130/131). Same operators; separate names allow separate errors
    and diagnostics. `convert_madis_acars` writes `ACARS_*`.
- **The humidity QC gap.** `convert_madis_acars` reads the RH QC flag `downlinkedRHQCR`, which is **absent**
  from the 2025 MADIS files. `get_or_fill_QC` fills it with 0 ("pass") and prints a message, so aircraft
  humidity would enter with **no MADIS QC**.
- **Correction after the first conversion test (same day): as-is, no aircraft humidity comes out at all.**
  The converter reads RH from `downlinkedRH` (line 122), which is **empty in all 50,869 reports** (so is
  `relHumidity`). The 18Z 05-20 test produced only `ACARS_U/V_WIND_COMPONENT` and `ACARS_TEMPERATURE`. In the
  2025 files aircraft humidity is in:
  - `waterVaporMR`: WVSS-II mixing ratio, kg/kg. 5,161 valid reports, **1,556 in our domain box that hour**.
  - `RHfromWVMR`: RH computed from it. Its range reaches 29.5, so the units/values are suspect; don't use it.
  
  `waterVaporQC` (codes 0–9: normal, RH > 100%, laser power low, …) is **missing for every WVSS report**, and
  `wvssTest1` = 1 ("Maybe") for 5,055. So there is no instrument QC to use.
  
  **Applied 2026-09-25:** `patches/dart_7bbd35a09_madis_acars_wvss_humidity.patch` (documented in
  `patches/README.md`). Result: 735 `ACARS_SPECIFIC_HUMIDITY` in the domain box at 18Z, 2,356 overall. The
  patch works as planned: When `downlinkedRH` is missing and `waterVaporMR` is
  valid: q = w/(1+w), RH = q/q_sat(T, p), then the existing path writes `ACARS_SPECIFIC_HUMIDITY` with the
  `acars_rel_hum_error` error. Add sanity bounds (w > 0, RH ≤ ~1.1). Record it in `patches/`.
- **Decision (user):** use aircraft humidity anyway (via the patch above), without instrument QC, because aircraft humidity profiles are
  very important for the BNF environment. Remaining protection:
  - `filter`'s `outlier_threshold` (set it, e.g. 3; it is off by default);
  - monitoring aircraft humidity innovations and rejections during the spin-up.
  
  Revisit if they look bad. Options then: stricter bounds, the WVSS test flag (`wvssTest1`), or tighter
  per-type errors.

**First MADIS conversion test (2026-09-25, `cases/20250520/obs/obs_seq_test/`).**
- **Build.** `MADIS/work/quickbuild.sh` built all seven converters plus `advance_time` and `obs_sequence_tool`.
  Running them needs `source scripts/env_wrf.sh` (libnetcdf).
- **Radiosonde converter quirk.** `convert_madis_rawin` ignores `&convert_madis_rawin_nml`: `use_namelist`
  is a compile-time `.false.`. It reads "significant-level winds, temperatures" from stdin, so run it as
  `echo "T T" | convert_madis_rawin`.
- **Results** (in a lat/lon box around the domain; 18Z 05-20 METAR/ACARS, 12Z radiosondes):
  - METAR 3,611: altimeter 772, T2 772, q2 749, U10/V10 659.
  - ACARS 14,927: U/V 5,047, T 4,833, **no humidity** (see above).
  - Radiosondes 2,893: T 1,100, q 1,100, U/V 341, surface altimeter 11.

**QC and thinning available in the DART workflow** (checked 2026-09-25):
1. **Converters.**
   - MADIS: `use_input_qc = .true.` (MADIS QC flags); errors from `obs_converters/obs_error/ncep_obs_err_mod.f90`
     (NCEP-style profiles by pressure), plus `dewpoint_obs_err_mod.f90`. `ecmwf_obs_err_mod.f90` is an
     alternative.
   - PREPBUFR: NCEP errors and quality marks from the file (`qctype_use`).
2. **`wrf_dart_obs_preprocess`** (`models/wrf/WRF_DART_utilities/wrf_dart_obs_preprocess.nml`):
   - Domain and boundary trim: `obs_boundary`; `increase_bdy_error` with `maxobsfac`/`obsdistbdy`.
   - Vertical: `obs_pressure_top`, `obs_height_top`, `sfc_elevation_check`/`sfc_elevation_tol` (300 m).
   - Superobbing, the only thinning: aircraft (36 km × 25 hPa) and satellite winds (100 km × 25 hPa).
   - `include_sig_data`, `overwrite_ncep_sfc_qc`/`overwrite_ncep_satwnd_qc`, and per-family input files.
3. **`obs_sequence_tool`:** subset by time, type, lat/lon box, QC range and value range (used for the
   15-min binning).
4. **`filter`** (`quality_control_mod.f90`):
   - `input_qc_threshold` (default 3).
   - `outlier_threshold` (default −1 = off; 3 recommended): rejects when |y − H(x̄)| > k·sqrt(σ_p² + σ_o²).
   - Forward-operator failures flagged as DART QC 4; `enable_special_outlier_code` for custom rules.

**Missing compared with GSI/HRRR:** general thinning for surface/mesonet, station use/reject lists, buddy
checks, variational QC, bias correction, and GOES-R-specific rules. So mesonet needs our own station
selection and thinning, and GOES winds need QC in our converter.

**GDAS PREPBUFR as the no-account fallback, compared with public MADIS** (2026-09-25):
- **Access.** GDEX `d337000` files download without an account through NCAR's OSDF mirror,
  `https://osdf-director.osg-htc.org/ncar/gdex/d337000/`:
  - `prepnr/2025/prepbufr.gdas.YYYYMMDDHH.nr`: non-restricted, ~65–73 MB.
  - `prep48h/2025/prepbufr.gdas.YYYYMMDD.tHHz.nr.48h`: includes ACARS/AMDAR, ~95–118 MB.
  - `tarfiles/`: daily tar files.
  
  All 13 six-hourly times 05-19 00Z – 05-22 00Z of both are in
  `cases/20250520/obs/gdas_prepbufr/{prepnr,prep48h}/`.
- **Decoding works with DART's bundled BUFRLIB,** built with Intel via
  `observations/obs_converters/NCEP/prep_bufr/install.sh` (`CCOMP=intel FCOMP=intel`) →
  `exe/{prepbufr.x, cword.x, grabbufr.x, prepbufr_03Z.x}`. The input must be blocked (`cword.x`, answer
  `block`) and byte-swapped (`grabbufr.x`) first; read directly, the library aborts with "NOT 'BUFR'".
  `prepbufr.x` writes `prepqm.out` (fixed format 800). One 6-hourly file takes ~15 min. Test runs are in
  `gdas_prepbufr/{test,test48h}/`.
- **Distinct reports in our domain, 05-19 10:00–14:00** (from the 12Z GDAS file vs the MADIS hourly files):

  | Family | GDAS `prepnr` | GDAS `prep48h` | public MADIS |
  |---|---|---|---|
  | Surface land (ADPSFC types 181/187 / METAR) | 3,447 | 3,447 | 3,453 |
  | Aircraft (AIRCAR 133 + AIRCFT 130 / ACARS) | 13 | 13,769 | 20,472 |
  | Radiosondes (ADPUPA 120/220 / raob) | 9 | 9 | 8 |
  | Marine (SFCSHP 180/280 / maritime) | 84 | 80 | 120 |
  | Mesonet (MSONET / LDAD mesonet) | **none** | **none** | 75,847 |
  | Satellite winds (SATWND) | none in domain this window (371,708 globally) | same | none |

  **Correction (same day), from counting BUFR subsets directly** with a small BUFRLIB program
  (`gdas_prepbufr/test/count_subsets.f`, `test48h/dump_special.f`). The table above only shows what DART's
  `prepbufr.x` writes. The selection is hard-coded in `src/prepbufr.f`. It is not controlled by
  `&prep_bufr_nml` (`otype_use`, `qctype_use` and the windows can only narrow it), and BUFRLIB reads every
  subset fine. Two places:
  1. **A fixed list, `filo`** (lines 63–65): ADPUPA AIRCAR AIRCFT SATWND PROFLR VADWND SATBOG SATEMP ADPSFC
     SFCSHP SFCBOG SPSSMI SYNDAT ERS1DA GOESND. Any other subset (e.g. `GPSIPW`, `RASSDA`, `ASCATW`) is
     skipped at line 216 ("no label match", printed only in debug).
  2. **Output branches.** Winds are written only for ADPUPA/AIRCAR/AIRCFT/SATWND (~line 673) and
     ADPSFC/SFCSHP (~line 697). `VADWND` and `PROFLR` pass step 1 and are read, but nothing writes them.
     (Lines 232–253 are just the per-type time windows.)
  
  The next converter, `create_real_obs` (`ascii_to_obs/real_obs_mod.f90`), also has no mapping for report
  types 224 (VAD) or 223/229 (profiler), or for GPS PW. `filter` already has `VADWND_U/V_WIND_COMPONENT`,
  `PROFILER_*` and `GPS_PRECIPITABLE_WATER` (from `obs_def_reanalysis_bufr_mod`).
  - **VAD winds:** two small local patches: add VADWND to the upper-air wind-output condition in `prepbufr.f`,
    and map 224 → `VADWND_*` in `real_obs_mod.f90`.
  - **GPS PW:** needs a `filo` slot, reading of the PW value (the reader only extracts P Q T Z U V), an output
    kind and a type mapping. A small direct BUFR → `obs_seq` tool may be simpler.

  12Z 05-19 subset counts:
  - `prepnr`: ADPUPA 1114, AIRCFT 3009, SATWND 205621, **VADWND 3559**, ADPSFC 179814, SFCSHP 53727,
    RASSDA 186, ASCATW 234283.
  - `prep48h`: the same families, with AIRCAR 234466 and AIRCFT 90939, plus **GPSIPW 354** (only in
    `prep48h`).
  - Neither has **MSONET** (mesonet) or **PROFLR** (wind profilers).

  In a lat/lon box around our domain: **VADWND 1,192 reports from 33 WSR-88D sites**, including KHTX
  (Huntsville, near BNF), KBMX, KOHX, KGWX, KNQA; **GPSIPW 34 stations**. So VAD winds and GPS PW
  *are* available for 2025, in GDAS `prep48h`. Using them needs a decoder that handles those subsets:
  extend `prepbufr.x`, or write our own BUFRLIB/Python reader, plus a DART writer (`GPS_PRECIPITABLE_WATER`
  and `VAD_*` wind types exist in DART).

  Surface land reports match almost exactly. `prep48h` is needed for aircraft (`prepnr` has none), and
  it holds ~2/3 of the MADIS count. The fallback has **no mesonet** at all. GDAS reports carry NCEP QC
  marks and errors; MADIS carries its own QC flags. (Odd, unexplained: the ADPUPA variable-level count
  is 8,646 in `prepnr` vs 4,578 in `prep48h` for the same 9 soundings.)
- **Choice.** Public MADIS gives the most data (aircraft, mesonet) with no account. GDAS `prep48h` is
  the fallback for surface, aircraft and radiosondes, and brings NCEP QC. A MADIS research account
  would add restricted mesonet, but isn't needed for the first set.

**GPS precipitable water: no 2025 source found in the dedicated archives (but see the correction above: it is in GDAS `prep48h` as `GPSIPW`).**
- **NCEI `C00962`** (ESRL GPS-Met IPW) covers 2002-04 – 2016-11 only: "no plans for updating".
- **SuomiNet**, the input to DART's `GPSPW` converter (`CsuPWVh_*.0060_nc`). The old host
  `www.suominet.ucar.edu` no longer resolves. The data moved to `https://data.cosmic.ucar.edu/suominet/`,
  but every product there ends in 2024: the last hourly CONUS file is `CsuPWVh_2024.227.14.00` (2024-08-14).
- **GDAS `prep48h` does have it** (`GPSIPW`, 34 stations near our domain at 12Z; see the correction above).
  Public MADIS has no GPS directory.

GPS PW (and VAD winds) can be added from `prep48h` once a decoder for those subsets exists; not in the first set.

**Satellite winds (AMVs): route and what to borrow from HRRR** (checked 2026-09-25).
- **Sources.** GDAS PREPBUFR `SATWND` has only Himawari (SAID 174) and Meteosat (56/57), nothing over North
  America (05-19 12Z and 05-20 00Z). Public MADIS `HDW` is empty. HRRR doesn't use PREPBUFR winds either:
  `use_prepb_satwnd=.false.`, and it reads the raw `satwndbufr` dump (`parm/*/hrrr_gsiparm.anl.sh`), which
  isn't archived publicly. **The usable source is GOES-19 (East) ABI L2 derived motion winds on AWS**,
  `noaa-goes19/ABI-L2-DMWC/YYYY/DDD/HH/`. The CONUS sector comes every 15 min, per channel, ~0.5 MB per file.
  One 12:01Z set on 05-20 gives 751 winds in our domain, all `DQF = 0`: C02 97 (712–943 hPa), C08 255
  (156–349), C09 40, C10 7, C14 352 (158–845), C07 0. Test files: `cases/20250520/obs/goes_dmw_test/`.
  **DART side, confirmed:**
  - Types `SAT_U/V_WIND_COMPONENT` (`obs_def_reanalysis_bufr_mod.f90` lines 42–43, `COMMON_CODE`: plain U/V
    interpolation at the wind's pressure) are in our `filter` build.
  - `wrf_dart_obs_preprocess` has a satellite-wind path: `sat_wind_extra = 'obs_seq.satwnd'`,
    `superob_sat_winds`, `sat_wind_horiz_int = 100` (km), `sat_wind_pres_int = 2500` (Pa),
    `overwrite_ncep_satwnd_qc`, plus `obs_boundary` and `increase_bdy_error`.
  - Existing converters (MADIS satwnd, SSEC satwnd, NCEP PREPBUFR SATWND types 242–255, GSI2DART, var/GTS)
    don't read GOES-R netCDF. **Only a GOES-R `ABI-L2-DMWC` reader is missing** (read lat, lon, pressure,
    speed, direction, time, `DQF`, zenith angle; HRRR-style QC; write `SAT_U/V`), with superobbing left to
    `wrf_dart_obs_preprocess`.
- **QC borrowable from HRRR's GSI** (`sorc/hrrr_gsi.fd/src/gsi/read_satwnd.f90`, GOES-R block ~lines
  990–1090; `ec_amv_qc` defaults to `.true.` in `convinfo.f90` and HRRR doesn't override it). Types by
  channel: 245 IR-LW (C14), 240 IR-SW (C07), 251 VIS (C02), 246 WV cloud-top, 247 WV clear-sky.
  - Reject local zenith angle > 68° (the netCDF has `local_zenith_angle`).
  - Reject p < 150 hPa (125 hPa without EC QC).
  - VIS only at p ≥ 700 hPa. WV cloud-top only at p ≤ 300 hPa.
  - Reject any AMV over land at p > 850 hPa.
  - **IR winds (240, 245) over land north of 20N are not used at all** when not `twodvar_regional`, which is
    HRRR's case (~line 1150). Our domain is almost all land, so HRRR would keep only VIS (≥700 hPa daytime),
    WV cloud-top (≤300 hPa) and WV clear-sky winds over it. C14, our largest group, would be dropped over land.
  - GSI also uses QI without forecast (≥90 with EC QC), expected-error/speed ≤ 0.9, and cloud-cover `pct1`
    0.04–0.50. **Those fields are not in the AWS netCDF L2 product.** NESDIS's own QI/expected-error check is
    folded into `DQF` (flag "failure of quality indicator and expected error method checks"), so `DQF = 0`
    stands in for them, with NESDIS's thresholds, not GSI's.
- **Not borrowable from the repo.** Observation errors (GSI error table by report type and pressure) and
  thinning (`convinfo` `ithin/rmesh/pmesh`) are in HRRR's fix files, which aren't on GitHub or reachable on
  the NCO site. Public stand-ins: the global/NAM `errtable` and `convinfo` in NOAA-EMC's GSI fix files (not
  yet checked), or DART's `wrf_dart_obs_preprocess` satellite-wind superobbing.
- **Where HRRR's tables come from** (from the file names the scripts load):
  - Both HRRR and HRRRDAS load `OBERROR=${FIXhrrr}/hrrr_nam_errtable.r3dv`
    (`scripts/hrrrdas/exhrrr_analysis.sh:234`), named after NAM's regional `nam_errtable.r3dv`.
  - Deterministic HRRR loads `CONVINFO=${FIXhrrr}/hrrr_nam_regional_convinfo`
    (`scripts/conus/exhrrr_analysis.sh:216`), NAM-derived.
  - HRRRDAS has its own per-domain `convinfo`: `hrrrdas_regional_convinfo.15km.txt` (line 229) and
    `.3km.txt` (line 398). The NAM-derived name is commented out on line 230.
- **Inference (contents not public).**
  - NAM's `nam_errtable.r3dv` should be close to HRRR's errors, including the satellite-wind rows by type
    240/245/246/247/251 and pressure, though local tuning is possible.
  - The global table is less transferable (tuned for a coarser model).
  - Thinning and use flags are the least transferable part: HRRRDAS deliberately has its own `convinfo`.
  - All of them were made for 3–12 km variational/hybrid analyses, so for our 2.5-km, 15-min EnKF they're a
    starting point, to be tuned from innovation statistics during the spin-up.
- **To do when satellite winds are added:** fetch NOAA-EMC's public GSI fix files (`nam_errtable.r3dv`,
  `nam_regional_convinfo`; current location not checked) and extract the rows for types 240–251.

**GPS PW possibilities, parked (decided 2026-09-25: not pursued for now).**
- **DART's converter.** `observations/obs_converters/GPSPW/convert_gpspw.f90` writes
  `GPS_PRECIPITABLE_WATER` (location `VERTISUNDEF`, error floored at 1.5 mm). It reads a SuomiNet-style
  netCDF: `lat`, `lon`, `height`, `pwv(time_offset, station)`, `pwv_err`, `time_offset` (s) and a
  `start_date` global attribute. For 15-min cycling set `obs_window_hr = 0`; otherwise it keeps only times
  that are multiples of the window (line 215). SuomiNet itself ends 2024-08-14.
- **GDAS `prep48h` as input.** `GPSIPW` reports carry `PWO` (PW, mm), `PWQ`, `PWE` and `PWF`. Checked
  (12Z 05-19, `test48h/dump_gpspw.f`): 34 stations in a box around our domain, PW 13–39 mm. But **all at
  DHR = 0** (only at 00/06/12/18Z), with **PWQ = 9** (as I understand it, monitored and not assimilated in
  GFS) and **PWE missing**, so we'd set our own error. An adapter that writes the SuomiNet-style netCDF from
  the BUFR (extending `dump_gpspw.f`) would let `convert_gpspw` do the rest.
- **Value for us:** low. That's 4 of 96 cycles a day, ~34 stations. Worth revisiting only if an hourly or
  sub-hourly 2025 GPS PW source turns up.

## 3. Suggested order of first steps

1. Hourly mean `wrfinput` files for the case (one Slurm job looping `real.exe`), plus a time manifest.
2. One `da_wrfvar.exe` RANDOMCV draw on our grid, then the bank and the saved member assignment.
3. The member boundary-file builder (2.12), first for one member.
4. Patches for `update_wrf_bc` (`THM`, and the fields it doesn't recompute), then the one-member
   boundary test in 2.12, together with the `wrfout`-restart test in 2.11.
5. A small ensemble (e.g. 5 members) run as one Slurm allocation with packed `srun` steps. This tests
   the job structure before scaling to 50.
