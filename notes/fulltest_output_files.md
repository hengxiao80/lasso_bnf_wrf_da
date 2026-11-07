# Full test: output files kept per cycle

What the 50-member cycling keeps per cycle in the 1-h and 6-h gates, why each file is kept, and how large it is. Written 2026-11-06 in session "fulltest: initial setup", from decisions made with the user that day.

## 1. Decisions (user, 2026-11-06)

- **Keep everything listed in Sec. 3 for the 1-h and 6-h gates.** The thinning for the 12-h and 30-h runs is decided at the 6-h gate, including which members' full states are kept for the LES window (05-20 12Z to 05-21 05Z, the period of the 500-m runs).
- **Member `wrfout`: the start-of-segment history instead of the end-of-segment forecast.** `write_hist_at_0h_rst = .true.` in `config/namelist.input.wrf`, so WRF writes the history file from the restart it has just read, before the first step. `history_interval` stays 15 min and the end-of-segment `wrfout` is deleted. Not yet implemented.
  - `history_interval` must not be lengthened instead: WRF sets `diag_flag` only on steps where the history alarm rings (or on every step with `nwp_diagnostics = 1`; `dyn_em/solve_em.F`), and Thompson computes `REFL_10CM` only on those steps. Without a history alarm at t + 15 min, the `REFL_10CM` in that time's `wrfrst`, filter's reflectivity prior, would be stale.
- **The member `wrfout` holds WRF's default history stream only.** `iofields_filename` and `ignore_iofields_warning` come out of `config/namelist.input.wrf`, and `run_wrf_segment.sh` stops copying `config/iofields_cycle.txt`, so its 65 added fields are no longer written. They were added in pilot step 7 so that a `wrfout` could restart WRF; the members restart from `wrfrst` now. `ndown` needs only the default stream: sey's 500-m run forced by the free run was made from `rund1`'s history, whose namelist adds no fields. bnf_wrf_eval reads none of the 65. Saves 0.44 of the 4.39 GB per file. Not yet implemented.
- **Filter's per-member files for all 50 members:** `num_output_state_members = 50`, and `num_output_obs_members = 50` for `obs_seq.final`.

## 2. What each file holds

- **`prior_d01.nc`**: the forecast as filter sees it. `prep_filter.sh` extracts each member's `wrfrst` into `run<RUN>/memNNN/dart_d01.nc` (`wrfrst_dart.py extract`) and copies it here before filter runs. With the end-of-segment `wrfout` gone, it is the only record of each cycle's forecast, in the DART state fields only.
- **`analysis_d01.nc`**: a copy of filter's in-place output `dart_d01.nc` (after `wrfrst_dart.py qnrain`), the file `insert` reads (`post_filter.sh`). Not exactly the state WRF starts from: its T is still the prior THM (T is not in the DART state), its PH is DART's (with `HYDROSTATIC_PH=1`, `insert` writes the hydrostatic PH increment instead), AL, ALT, P and P_HYD are not in it, and the `NO_COPY_BACK` fields keep their prior values. DART's clamp has set negative moisture to 0.
- **`wrfout_d01_<t>`** (start of segment, once implemented): the state WRF starts from, after `insert`. Analyzed U, V, PH (hydrostatic), THM, MU, QVAPOR, QCLOUD, QRAIN, QSNOW, QGRAUP; QNRAIN from `qnrain`; T = THM and AL, ALT, P, P_HYD recomputed by `insert`; plus all other history fields. The `NO_COPY_BACK` fields (W, T2, Q2, U10, V10, PSFC, `REFL_10CM`) and everything outside the DART state (soil, TSK, TKE, ...) are the forecast's, so its `REFL_10CM` is not consistent with the analyzed hydrometeors. WRF's default history stream, 222 variables (the 5-member runs also wrote the 65 fields of `config/iofields_cycle.txt`, 287 in all; dropped, Sec. 1). Of the history fields, only U10E, V10E (special 10-m winds of the MYJ surface scheme) and four scalar flags are not stored in the restart file, so everything else in this file is the state WRF actually read.
- **`wrfbdy_d01`**: the member's boundary file refit to its analysis (`refit_member_bdy.sh` → `update_wrf_bc`, from `start_d01.nc`, a fresh extract of the updated `wrfrst`).
- **`postassim_member_NNNN.nc`**: the posterior straight after the update, before clamping. The only place with each member's analyzed `NO_COPY_BACK` fields and its unclamped moisture. Checked for member 1 at 01:00 in run 5: U and THM identical to `analysis_d01.nc`; moisture different only where `analysis_d01.nc` has 0 and the posterior is negative (QVAPOR at 3,632 points, hydrometeors at 0.2–0.56 million points, down to −9.5 g/kg QRAIN); W, T2, PSFC and `REFL_10CM` analyzed here, prior values in `analysis_d01.nc`.
- **`preassim_member_NNNN.nc`**: the prior after prior inflation, just before the update. In principle recomputable from `prior_d01.nc` with filter's prior mean and inflation fields.
- **Filter's mean, sd and inflation files** at the `input`, `preassim`, `postassim` and `output` stages, and **`obs_seq.final`** (ASCII).

## 3. Sizes

Measured from run 5 `_conv_refl_f2` at 01:00 (`output_conv_refl_f2/202505200100/`, 2026-11-06) and scaled to 50 members. "Nominal" is the file size, "disk" what GPFS uses (`du`); GB = 10⁹ bytes.

### 3.1 Per member

In `output<RUN>/<t>/memNNN/`, 50 of each.

| file | nominal | disk | 50, disk |
|---|---|---|---|
| `wrfout_d01_<t>`¹ | 3.95 | ~2.5 | ~125 |
| `prior_d01.nc` | 1.67 | 1.04 | 52 |
| `analysis_d01.nc` | 1.67 | 1.04 | 52 |
| `wrfbdy_d01` | 0.33 | 0.33 | 17 |
| logs, markers | ~0 | ~0 | ~0 |
| subtotal | 7.62 | ~4.9 | ~245 |

¹ From run 5's end-of-segment `wrfout` (4.39 GB nominal, 2.77 GB on disk) without the 65 dropped fields (0.44 GB nominal); the disk size is scaled by the same ratio, so it is an estimate. The start-of-segment file has the same fields.

The `wrfbdy_d01` row holds only if each cycle's refit file keeps one or two hourly records, as in run 5 (2 records). A member file with all 31 records of the 30-h run is ~4.5 GB (~0.15 GB per record), which would add ~200 GB per cycle (`fulltest_steps.md` A6).

### 3.2 Filter, per member

In `output<RUN>/<t>/filter/`, 50 of each.

| file | nominal | disk | 50, disk |
|---|---|---|---|
| `preassim_member_NNNN.nc` | 1.54 | 1.02 | 51 |
| `postassim_member_NNNN.nc` | 1.54 | 1.03 | 52 |
| subtotal | 3.09 | 2.05 | 103 |

### 3.3 Filter, one set per cycle

File names are `<stage>_<kind>.nc`, e.g. `preassim_priorinf_sd.nc`. The `output` stage files are smaller (1.28 GB nominal): they hold only the `UPDATE` variables.

| kind | stages | files | disk |
|---|---|---|---|
| `mean`, `sd` | input, preassim, postassim | 6 | 6.2 |
| `mean`, `sd` | output | 2 | 1.8 |
| `priorinf_mean`, `priorinf_sd` | input, preassim, postassim | 6 | 2.9 |
| `priorinf_mean`, `priorinf_sd` | output | 2 | 0.9 |
| `obs_seq.final`² | | 1 | ~0.15 |
| logs, `input.nml` | | | ~0 |
| subtotal | | | ~12 |

² Estimate. 21 MB on disk with 5 members, when each observation carries 15 copies (value; prior and posterior mean and spread; 5 prior and 5 posterior members). With 50 members it carries 105, so roughly 7× larger.

### 3.4 Totals

| what | disk |
|---|---|
| one analysis cycle | ~360 GB |
| 00Z cold start³ | ~125 GB |
| 1-h gate (00Z + 4 analyses) | ~1.6 TB |
| 6-h gate (00Z + 24 analyses)⁴ | ~8.8 TB |

³ Only the 50 initial-state `wrfout` files.
⁴ Includes the first hour if the 6-h run continues the 1-h run.

One analysis cycle is ~560 GB nominal. Not counted above: the current restarts in `run<RUN>/memNNN/` (`wrfrst` 13.1 GB nominal, plus `dart_d01.nc`, `start_d01.nc` and the boundary work files), about 0.5 TB for 50 members, overwritten every cycle.
