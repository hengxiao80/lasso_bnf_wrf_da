# Radar spin-up: storms the ensemble doesn't have

Written 2026-11-13 in session "fulltest: D2 analysis", at the user's request, as a record to come back to. Nothing here is decided or tested. The numbers come from `fulltest_d2_analysis.md` (the first 6 h of the 50-member run `_conv_refl_f2`), Sec. 5 there. At the 6-h gate the user decided that a spin-up variant, if any, would be a separate run (`fulltest_steps.md` D3).

**Typora.** Display equations are `$$` blocks. Inline math (`$...$`) needs *Preferences → Markdown → Inline Math*.

## 1. The problem

A radar reflectivity obs (MRMS at least 10 dBZ) where **no member has an echo** can't be assimilated:

- every member's H(x) is the forward operator's floor, −10 dBZ, so the prior mean is −10 and the prior spread in observation space is 0;
- filter's outlier test (`fulltest_d2_analysis.md` Sec. 5.1) rejects an obs when its innovation exceeds 3 times $\sqrt{s^2 + \sigma_o^2}$; with $s = 0$ and $\sigma_o$ = 5 dBZ the cut-off is 15 dBZ, and every such obs (innovation at least 20 dBZ) gets QC 7; only near the lateral boundary, where the error is inflated up to 9.3 dBZ, can obs up to 17.9 dBZ pass;
- even without the test it would change nothing: in DART's EAKF (`obs_increment_eakf` in `assim_tools_mod.f90`) the weight on the obs is $s^2/(s^2 + \sigma_o^2)$, zero for $s = 0$, so every increment is zero;
- multiplicative inflation (our adaptive prior inflation) and relaxation to prior spread can't help either: both scale the members' deviations from the mean, and there are none.

Such a storm enters the ensemble only through nearby obs that do pass (with spread, at the storm's edge or where a few members have echo), or by the model developing it in some members on its own.

In D1 and D2 (`fulltest_d2_analysis.md` Sec. 5.3):

| Period | outliers, no member echo | share of radar obs |
|---|---|---|
| 00:15–01:00 | 8,800–10,100 per cycle | 11.5–12.7 % |
| 02:45–04:30 | about 3,000–3,700 | 3.5–4.2 % |
| 04:45–05:00 | 4,600–5,000 | 5.0–5.3 % |
| 06:00 | 3,359 | 3.5 % |

The first hour is the cold start (members start at 00Z from the mean state plus perturbations, with no storms of their own). The later residual of about 3,000 per cycle, rising when the observed echo area grows (04:45–05:00), is most likely new cells the ensemble doesn't have yet; it should be expected whenever new convection forms in the 12-h and 30-h runs. These obs lean to the upper levels (30–37 % at or below 4 km, against 42–45 % of the assimilated obs).

A second, smaller group behaves almost the same: outliers where only a few members have an echo (a median of 4 of 50 after 03:00; prior mean about −9 dBZ, spread 2–3 dBZ; 2,000–3,400 per cycle after 03:00). About half of them are only just over the threshold (ratio 3–4).

## 2. What HRRRDAS does

From Dowell (2020; `notes/papers/Dowell - 2020 - HRRR Data-Assimilation System (HRRRDAS) and HRRRE Forecasts.pdf`) and Dowell et al. (2022, Sec. 3d and Table 5; `notes/papers/Dowell et al. - 2022 - The High-Resolution Rapid Refresh (HRRR) ... Par.pdf`), both read 2026-11-13:

- **36 members, hourly, EnSRF** (GSI-EnKF with OU's radar extensions); conventional obs, then MRMS reflectivity in a second update (localization 18 km horizontally, 0.5 scale height; updates U, V, T, QVAPOR, QCLOUD, QRAIN, QSNOW, QGRAUPEL; QNRAIN is then set from QRAIN, as `wrfrst_dart.py qnrain` does here). Clear-air obs are −10 dBZ, with the same floor on the model reflectivity, as here.
- **Spread sources** (2022 paper): initial-condition perturbations from the GDAS ensemble; random, spatially correlated boundary perturbations (a WRF-Var perturbation bank, as here); hourly relaxation to prior spread (RTPS; factor 1.08 on the 3-km grid after the radar update, 2020 document); and hourly cloud clearing in each member.
- **Rolling re-initialization**: half the members are replaced every 12 h. Odd members are re-initialized at 09Z and even ones at 21Z, from the RAP analysis plus perturbations from the GDAS 9-h ensemble forecast (T, U, V, QVAPOR, MU; GSI's `enspreproc` and `initialens`), and each member is cycled for about a day (23 h in 2020, 24 h in 2022). Soil is perturbed by stochastic physics during a new member's first hour (2020). In the HRRR code these steps are `exhrrrdas_prep_enkf.sh` and `exhrrr_makeguess.sh` (`../software/HRRR/scripts/hrrrdas/`; `initialens` also applies a column inflation factor of 2.0 at the lowest level falling to 1.0 at level 26).
- **No reflectivity-targeted perturbations** are described in either paper.
- **The deterministic HRRR** spins storms up differently: a 1-h pre-forecast with latent heating derived from the 3D MRMS reflectivity (and lightning) at 15-min intervals (Weygandt et al. 2022, cited in the 2022 paper). HRRRDAS's members don't use it.

## 3. Options

### A. Additive noise where echoes are observed

DART has a WRF tool for this, already built: `../software/DART/models/wrf/work/add_pert_where_high_refl` (source `models/wrf/WRF_DART_utilities/add_pert_where_high_refl.f90`, D. Dowell 2007; the header cites Caya et al. 2005, MWR 133, 3081–3094). Read 2026-11-13:

- **What it does**: adds random, spatially smooth perturbations to a WRF netCDF file at and near listed grid points: Gaussian noise of given sd at those points, smoothed with horizontal and vertical length scales `lh`, `lv`. Perturbed: U, V, W, T, and QVAPOR (through dewpoint noise, `td_sd`, or mixing-ratio noise, `qv_sd`). Not the hydrometeors.
- **Inputs** (13 command-line arguments): the list file, the WRF file, `lh`, `lv`, `u_sd`, `v_sd`, `w_sd`, `t_sd`, `td_sd`, `qv_sd`, the member number (seeds the random numbers) and the analysis time (days, seconds). It reads PHB, PH, MU, MUB, DNW from the file.
- **The list of points**: the companion tool `grid_refl_obs` (also built) extracts reflectivity obs at or above a threshold `refl_min` in a time range from an `obs_seq` file and maps them to WRF mass grid points.
- **Why it would help**: perturbing wind, temperature and moisture where storms are observed lets some members develop convection there within a cycle or two, so the next prior has echo and spread at those obs. It targets exactly the residual of Sec. 1. The standard reference for additive noise in storm-scale EnKF is Dowell and Wicker (2009, J. Atmos. Oceanic Technol. 26, 911–927; not in `notes/papers`, not read in this session).

Open questions before any test:

1. Which file: our members restart from `wrfrst`, and DART works on a file extracted from it (`wrfrst_dart.py`); whether the extracted file has everything the tool reads (PHB, DNW, MUB, …) and where the noise would be inserted is unchecked.
2. When: after filter and before the advance is the usual place; every cycle or only some.
3. Where: all obs at or above a threshold, or only the obs no member (or few members) has.
4. Parameters (`lh`, `lv`, the sds): to be chosen from the literature; no values here.
5. Side effects: noise in W and T may add to the post-analysis shock (watch the per-member |dpsfc/dt| that `check_cycle.py` reports); cost unknown, measure first.

### B. Relax the outlier test for radar

- **How**: `outlier_threshold` in `&quality_control_nml` applies to all types. A radar-only threshold needs `enable_special_outlier_code = .true.` and code in `failed_outlier` (`quality_control_mod.f90`, a per-type `select case` meant to be customized), i.e. a DART patch and a rebuild of `filter`.
- **What it would do**: admit obs where members have some spread. A threshold of 4 would admit about half of the "few members echo" outliers (ratio 3–4).
- **What it can't do**: the no-echo obs get zero weight whatever the threshold (Sec. 1).
- **Risk**: assimilating innovations of 15–25 dBZ where the spread is 2–3 dBZ; the effect on the analysis and the shock is unknown without a test.

### C. A free spin-up or a short free advance before cycling

Already listed in `fulltest_steps.md` Sec. 0: start the members from 05-19 18Z (or advance them freely for a while) so that they develop their own convection and spread before the first analysis. It addresses the first-hour peak, including the cold-start storms the model has too strongly (10,012 outliers at 00:15–01:00 with a model mean of 50 dBZ against an observed 21 dBZ, `fulltest_d2_analysis.md` Sec. 5.3), but not the new cells later.

### D. HRRRDAS-style spread maintenance

Rolling re-initialization of part of the ensemble, and RTPS (raised before as an alternative to adaptive inflation, `CLAUDE.md` "Current state"). RTPS has the same limitation as any inflation where all members agree (Sec. 1); re-initialization from perturbed analyses brings in new members without storms at first. Neither targets the no-echo obs; both are about overall spread.

### E. Radar-derived latent heating in the members

The deterministic HRRR's approach (Sec. 2) applied in each member's advance. A large change on the WRF side (it lives in HRRR's WRF fork; whether our WRF 4.8 has an equivalent is unchecked); listed for completeness.

## 4. How to judge an option

- **Main measure**: the number of radar outliers with no member echo per cycle, and as a share of the radar obs (`fulltest_d2_analysis.md` Sec. 5.3), especially after new cells appear; also the "few members echo" group.
- **Fit**: prior rmse and bias over all radar obs with a valid prior (QC 0 or 7), which don't depend on the outlier test; total spread / rmse on the same set.
- **Side effects**: the clear-air obs (spurious echo), the conventional types, the post-analysis shock (|dpsfc/dt|), cost.
- **A test** would be a short variant run against the existing first hours of `_conv_refl_f2`; it needs the user's go-ahead for `sbatch`.
