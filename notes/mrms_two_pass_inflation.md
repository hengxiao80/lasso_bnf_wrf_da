# Two-pass MRMS assimilation: inflation and the impact table

Written 2026-10-22 (session "Adding more obs part 8") from runs 3, 4 and 4b (`obs_expansion.md` Sec. 9) and a walk
through DART's code (v11.25.3, `7bbd35a09`). How DART's adaptive prior inflation and the observation impact table
behave in our one- and two-pass MRMS setups, what still differs between the two, and a plan for further two-pass
tests (Sec. 8, proposed, not decided). Design of the two setups: `obs_expansion.md` Sec. 8.4 (two passes) and 8.5
(one pass); namelist decisions: `dart_namelist_discussion_log.md`.

## 1. The runs

All 1-hour, 5 members, cold start 00:00, analyses 00:15–01:00, observation set `obs_madis_mrms/` (MADIS + MRMS),
`INF_FLAVOR=2`, `INF_DAMPING=0.9`, sd fixed at 0.6, filter 40 × 32.

| run | `RUN_NAME` (job) | filter | impact tables |
|---|---|---|---|
| 3 | `_madis_mrms1p` (1054809) | one pass, `input.nml.filter_joint` | `obs_impact_joint.txt` |
| 4 | `_madis_mrms2p` (1054932) | two passes, `MRMS_INFLATION=both`, `MRMS_PASS2_DAMPING=1` | none |
| 4b | `_madis_mrms2p_imp` (1054977) | as run 4 | `obs_impact_mrms.txt` in the MRMS pass |

| | run 3 | run 4 | run 4b |
|---|---|---|---|
| post-analysis max \|dpsfc/dt\|, steps 2–4, hPa/3h: 00:15 / 00:30 / 00:45 / 01:00 | 308 / 500 / 632 / 732 | 307 / 569 / 949 / 1,119 | 307 / 570 / 939 / 1,114 |
| same, minutes 5–15 at 01:00 | 89–90 | 100–101 | 100 |
| MU inflation, max, 01:00 | 2.66 | 3.96 | 2.18 |
| U prior spread (conventional pass, after inflation), 01:00 | 1.35 m/s | 1.51 | 1.51 |
| reflectivity QC 7 / posterior RMS / bias, 01:00 | 36 % / 6.73 / +2.76 dBZ | 33 % / 6.54 / +2.66 | 33 % / 6.53 / +2.65 |

Two passes fit the radar slightly better, with more spread and fewer outliers, but the initial shock is ~50 % larger
from 00:45 on, and the minutes-5–15 value rises over the cycles for the first time. The impact table (4b) removed the
radar-driven MU inflation of run 4 but not the larger shock.

## 2. What one filter pass does with the inflation (`inf_flavor = 2`)

- **One λ per state element.** Spatially varying adaptive prior inflation: a mean (and an sd) for every grid point of
  every level of every state variable, in files shaped like the state (`*_priorinf_mean.nc`, `*_priorinf_sd.nc`;
  U's λ is 149 × 389 × 550, like U). U and THM at the same point have separate λ. With `inf_sd_lower_bound = 0.6`
  = the initial sd, the sd stays 0.6.
- **Steps** (`filter_mod.f90:820-830`, `assim_tools_mod.f90:760-830`, `adaptive_inflate_mod.f90`):
  1. read λ (`input_priorinf_mean.nc`);
  2. **damp** the whole field: λ ← 1 + `inf_damping` (λ − 1);
  3. **inflate** every state element, `UPDATE` or not: each member's deviation from the mean × √λ; then compute
     H(x) for all observations from the inflated members;
  4. **assimilate**, one observation at a time: for each state element within the localization radius, weight =
     localization (Gaspari–Cohn) × impact factor; if 0, skip the element; otherwise update its values and its λ
     (the λ update is weighted by γ = weight × |correlation of the element with the obs prior|); then update the
     priors of the observations still to come (Sec. 3);
  5. **write**: the member files get only the `UPDATE` fields (a `NO_COPY_BACK` field keeps the values read in);
     `postassim_priorinf_mean/sd.nc` get the updated λ of **all** state fields; `output_priorinf_*` only the
     `UPDATE` fields (hence `prep_filter.sh` hands on `postassim_priorinf_*`); the `preassim_*`/`postassim_*`
     diagnostic files hold all fields, including the discarded analyses of the `NO_COPY_BACK` ones.
- **λ only changes where the element has spread.** With zero spread the correlation is 0, so γ = 0. At 00:30
  (run 4b) QCLOUD has spread at 2 % of the points and its λ changed at exactly those; QRAIN 8 %, QGRAUP 7 %,
  REFL_10CM 16 %. λ also stays as damped outside every observation's localization radius.
- **Damping removes 10 % of the excess, not 10 % of λ**: 1.5 → 1.45, 3.0 → 2.8. It sets how fast λ fades from
  cycle to cycle (e-folding ~2.4 h at 15-min cycles for 0.9). It does little to the size of any single application.
  So under `both` the MRMS pass applies about the same λ as the conventional pass. The earlier statement that pass-2
  damping "partly offsets" inflating twice (hand-off part 8, discussion-log entry of 2026-10-21) overstated it.

## 3. The impact table

- **Setting it up:** `&assim_tools_nml` `adjust_obs_impact = .true.`, `obs_impact_filename = '<file>'`,
  `allow_any_impact_values = .false.` (factors in [0, 1]). The file has one line per pair, `<obs type> <QTY_*> <factor>`;
  pairs not listed are 1 (`obs_impact_mod.f90`, `allocate_impact_table`). Column 1 is the specific type of the
  observation being assimilated, column 2 a quantity. The table is directional: radar → MU = 0 says nothing about
  conventional obs → MU. DART's documented syntax also has groups (`obs_impact_tool.rst`); ours are plain lines.
- **Where it acts** (`cov_and_impact_factors`, `assim_tools_mod.f90:2065-2100`), for each observation:
  1. **state update**: the column-2 quantity is the state field's (from `wrf_state_variables`); factor 0 →
     `cycle STATE_UPDATE` (`:787`): neither the values **nor the λ** of that element change; a factor in (0, 1)
     scales both;
  2. **obs-prior update** (`OBS_UPDATE`, `:806-830`): filter computes every observation's H(x) once, before the
     loop. After each observation it updates the prior ensembles of the observations later in the sequence by the
     same regression it uses for the state, so each observation sees what the earlier ones already did and nothing
     is counted twice. Here the column-2 quantity is the other observation's. Factor 0 → that observation's prior
     isn't changed by this one.
- **It works by quantity**, so one row acts on every state field and every observation of that quantity:

  | quantity | state fields | observation types |
  |---|---|---|
  | `QTY_RADAR_REFLECTIVITY` | REFL_10CM | RADAR_REFLECTIVITY, RADAR_CLEARAIR_REFLECTIVITY |
  | `QTY_SURFACE_PRESSURE` | PSFC | METAR_ALTIMETER, LAND_SFC_ALTIMETER |
  | `QTY_PRESSURE` | MU | – |
  | `QTY_GEOPOTENTIAL_HEIGHT`, `QTY_VERTICAL_VELOCITY` | PH, W | – |
  | `QTY_U_WIND_COMPONENT` | U and U10 | ACARS_U_WIND_COMPONENT, METAR_U_10_METER_WIND, ... |
  | `QTY_TEMPERATURE` | T2 (THM is `QTY_POTENTIAL_TEMPERATURE`) | METAR_TEMPERATURE_2_METER, ACARS_TEMPERATURE, ... |
  | `QTY_VAPOR_MIXING_RATIO` | QVAPOR and Q2 | – (METAR humidity is `QTY_SPECIFIC_HUMIDITY`) |

  Two state fields of the same quantity (U and U10) can't be told apart.
- **Not affected:** the forward operators (the radar operator still reads MU and PH to locate the observation
  vertically), the damping and the inflation applied in step 3, the outlier check, and whether the observation
  itself is assimilated.
- **Our tables:**
  - `obs_impact_joint.txt` (run 3) makes one pass behave like the two passes:
    - radar types → MU, PH, PSFC, W = 0 (8 rows);
    - each assimilated conventional type → QRAIN, QSNOW, QGRAUP = 0 (the conventional pass doesn't write them back);
    - each assimilated conventional type → `QTY_RADAR_REFLECTIVITY` = 0: REFL_10CM is not updated, and neither are
      the radar obs priors, which keep the background H(x), as in the MRMS pass of a two-pass run.
  - `obs_impact_mrms.txt` (since 2026-10-21, run 4b on): the 8 radar rows, in the MRMS pass.
  - The conventional pass of the two-pass runs had **no table** up to run 4b; since 2026-10-23 it has
    `obs_impact_conv.txt` (`input.nml.filter`, so every run's first pass): the conventional rows of the joint table.

## 4. Flags per pass, λ adaptation, and what reaches WRF (run 4b)

Both passes list the same 17 variables, which is required for handing λ from one pass to the other (2026-10-15
decision). "λ changed" = share of the points where the observations changed λ at 00:30 (preassim → postassim).
"Into WRF" = the fields `post_filter.sh` passes to `wrfrst_dart.py insert`.

| variable | conventional pass | λ changed | MRMS pass | λ changed | spread ≠ 0 | into WRF |
|---|---|---|---|---|---|---|
| U, V | UPDATE | 53, 52 % | UPDATE | 18 % | 100 % | yes |
| W | NO_COPY_BACK | 52 % | NO_COPY_BACK | 0 (table) | 100 % | no |
| PH | UPDATE | 51 % | NO_COPY_BACK | 0 (table) | 100 % | yes, recomputed hydrostatically |
| THM | UPDATE | 53 % | UPDATE | 18 % | 100 % | yes |
| MU | UPDATE | 86 % | NO_COPY_BACK | 0 (table) | 100 % | yes |
| QVAPOR | UPDATE | 52 % | UPDATE | 18 % | 100 % | yes |
| U10, V10, T2, Q2 | NO_COPY_BACK | 90 % | NO_COPY_BACK | 26 % | 100 % | no |
| PSFC | NO_COPY_BACK | 86 % | NO_COPY_BACK | 0 (table) | 100 % | no |
| QCLOUD | UPDATE | 2 % | UPDATE | 2 % | 2 % | yes |
| QRAIN | NO_COPY_BACK | 8 % | UPDATE | 8 % | 8 % | yes (+ QNRAIN from it) |
| QSNOW | NO_COPY_BACK | 13 % | UPDATE | 9 % | 15 % | yes |
| QGRAUP | NO_COPY_BACK | 6 % | UPDATE | 6 % | 7 % | yes |
| REFL_10CM | NO_COPY_BACK | 15 % | NO_COPY_BACK | 14 % | 16 % | no |

- U, V, THM, QVAPOR, QCLOUD: both passes write them, so the MRMS pass starts from the conventional analysis.
- MU, PH: from the conventional pass only.
- QRAIN, QSNOW, QGRAUP: from the MRMS pass only, which starts from the background.
- W, the 2-m and 10-m fields, PSFC, REFL_10CM: never written; they are in the state for the forward operators and the
  vertical localization. Their λ still matters where it sets an observation prior's spread (T2, U10 etc. for the
  METARs, PSFC for the altimeters, REFL_10CM for the radar).

## 5. How the inflation carries through

**Hand-over** (`prep_filter.sh`; checked bit for bit in run 4b: conventional 00:30 → MRMS 00:30, MRMS 00:30 →
conventional 00:45): a pass's `postassim_priorinf_{mean,sd}.nc` becomes the next pass's `input_priorinf_*`. The λ
handed on already includes that pass's damping.

- **Run 3 (one pass):** read the previous cycle's λ → damp once → inflate all → conventional and radar obs update
  state and λ (within the joint table's limits) → hand on.
- **`both` (runs 4, 4b):**
  1. conventional pass: reads the previous MRMS pass's λ → damps → inflates all fields, but only the inflation of
     U V THM QVAPOR QCLOUD MU PH survives (hydrometeors discarded) → conventional obs update every field's λ, the
     hydrometeors' and REFL_10CM's included (no table);
  2. MRMS pass: reads that λ → damps again (`MRMS_PASS2_DAMPING=1`) → inflates again: U V THM QVAPOR QCLOUD for the
     **second** time (on the conventional analysis), QRAIN QSNOW QGRAUP for the first time (on the background), and
     REFL_10CM, so the radar H(x) come from an inflated background → radar obs update λ (not MU PH W PSFC since 4b);
  3. the next cycle reads the MRMS pass's λ.
- **`pass1`:** the conventional pass as above, but reading the previous *conventional* pass's λ. The MRMS pass has
  `inf_flavor = 0`: no damping, no inflation, no λ update, and the radar H(x) come from the uninflated background.

Inflations that reach the model per cycle, and who adapts λ:

| fields | run 3 | `both` (4b) | `pass1` |
|---|---|---|---|
| U V THM QVAPOR QCLOUD | 1 | **2** | 1 |
| MU PH | 1 | 1 | 1 |
| QRAIN QSNOW QGRAUP | 1 | 1 | **0** |
| REFL_10CM (radar H(x)) | 1 | 1 | **0** |
| λ of the dynamics adapted by | conventional + radar | conventional + radar | conventional |
| λ of the hydrometeors, REFL_10CM adapted by | radar | **conventional + radar** | conventional (never applied) |

## 6. Measurements (run 4b against run 3)

"Domain RMS of the sd" = square root of the domain mean of the ensemble variance, all grid points and levels weighted
equally. The ratio "after inflation / before" is a variance-weighted average of √λ, dominated by the regions where
spread and λ are large (λ > 1.1 at only ~13 % of the points; locally up to 3.5–3.9).

**λ applied to U** (mean / max): 00:45 run 3 1.046 / 3.38, 4b conventional pass 1.044 / 3.27, 4b MRMS pass 1.048 /
3.15; 01:00 1.066 / 3.88, 1.062 / 3.77, 1.065 / 3.50. The MRMS pass applies about the same λ again.

**Spread through the passes, 01:00** (domain RMS of the sd: before inflation → after → after assimilation):

| | U (m/s) | THM (K) | QRAIN (g/kg) |
|---|---|---|---|
| run 3 | 1.21 → 1.35 (×1.12) → 1.16 | 0.99 → 1.01 (×1.02) → 0.97 | 0.087 → 0.113 (×1.30) → 0.080 |
| 4b conventional pass | 1.33 → 1.51 (×1.13) → 1.36 | 1.02 → 1.05 (×1.03) → 1.01 | (inflated and updated, discarded) |
| 4b MRMS pass | 1.36 → 1.57 (×1.16) → 1.39 | 1.01 → 1.04 (×1.03) → 1.02 | 0.098 → 0.133 (×1.37) → 0.090 |

At 00:45: U run 3 1.10 → 1.18 → 1.07; 4b 1.14 → 1.23 → 1.18, then 1.18 → 1.29 → 1.19.

- U is inflated ×1.13 × ×1.16 ≈ ×1.31 per cycle in 4b, against ×1.12 in run 3: variance ×1.72 against ×1.25. The
  product is approximate, since the two ratios are averages with different weights.
- **The 4b analysis ends with more spread than its forecast** (U 1.33 → 1.39 at 01:00, 1.14 → 1.19 at 00:45); run 3
  ends with less (1.21 → 1.16). The forecast spread grows cycle by cycle in 4b (00:45 1.14, 01:00 1.33).
- **Conventional obs adapt the hydrometeor λ in 4b** (absent in run 3): QRAIN mean change +0.03 to +0.07 at the
  changed points (2/3 up; extremes +1.44 / −1.08), against +0.18 to +0.20 from the radar obs; QSNOW, QGRAUP +0.02 to
  +0.04 against +0.11 to +0.16 (00:30–01:00).

**Routine since 2026-10-22 (plan step 0).** `check_cycle.py` prints these numbers in a "spread by stage" section of
every `check_cycle.log`, for each pass: U V THM QVAPOR QCLOUD QRAIN QSNOW QGRAUP MU, sd before inflation
(`input_sd`), after (`preassim_sd`) and after assimilation (`postassim_sd`), and the applied λ
(`preassim_priorinf_mean`: mean, share > 1.1, max; `*` marks fields the pass doesn't write back), over all points and
over the echo columns. It ends with forecast → analysis over the cycle (first pass `input_sd` → `postassim_sd` of the
last pass that writes the field). Echo columns: the background mean REFL_10CM ≥ 10 dBZ at some level, or an MRMS
precipitation ob in the column or next to it (the obs are thinned to every other point). At 01:00 that is 21 % and
32 % of the columns, 34.5 % together. Runs 3, 4 and 4b are backfilled with `--spread-only` into
`output<RUN_NAME>/<t>/spread_by_stage.log`; the U numbers above are reproduced exactly.

**Forecast → analysis spread over the cycle** (domain RMS of the sd; ratio analysis / forecast):

| cycle | U all, run 3 | U all, 4b | U echo, run 3 | U echo, 4b | THM echo 3 / 4b | QVAPOR echo 3 / 4b | QRAIN echo 3 / 4b |
|---|---|---|---|---|---|---|---|
| 00:15 | 0.830 → 0.749 (×0.90) | 0.830 → 0.758 (×0.91) | 0.989 → 0.890 (×0.90) | 0.989 → 0.906 (×0.92) | ×0.96 / ×0.96 | ×0.89 / ×0.90 | ×0.84 / ×0.87 |
| 00:30 | 0.974 → 0.911 (×0.94) | 0.983 → 0.949 (×0.97) | 1.29 → 1.21 (×0.94) | 1.31 → 1.28 (×0.98) | ×0.97 / ×0.99 | ×0.91 / ×0.97 | ×0.91 / ×0.94 |
| 00:45 | 1.10 → 1.07 (×0.97) | 1.14 → 1.19 (×1.04) | 1.52 → 1.49 (×0.98) | 1.60 → 1.72 (×1.08) | ×0.99 / ×1.02 | ×0.97 / ×1.09 | ×0.96 / ×0.99 |
| 01:00 | 1.21 → 1.16 (×0.96) | 1.33 → 1.39 (×1.05) | 1.70 → 1.64 (×0.97) | 1.92 → 2.06 (×1.08) | ×0.99 / ×1.01 | ×0.90 / ×1.02 | ×0.93 / ×0.92 |

- **From 00:45 on, the two-pass analysis ends with more U, V, THM and QVAPOR spread than its forecast**, most in the
  echo columns (U ×1.08, QVAPOR ×1.09 at 00:45). Run 3 reduces the spread of every field in every cycle. Run 4's ratios
  are within 0.01 of 4b's except for MU (its radar-adapted MU λ).
- The forecast spread grows faster in 4b: U in the echo columns 1.52 / 1.70 m/s (run 3) against 1.60 / 1.92 (4b) at
  00:45 / 01:00.
- 00:45 has few surface obs (32 METAR altimeters, against 139–313 in the other cycles: the routine METARs fall into
  the 01:00 window), so the conventional pass removes little spread there (MU ×0.97 in both runs, against ×0.68–0.73
  in the other cycles). 4b turns to spread growth at that cycle.
- The applied λ is about twice as far from 1 in the echo columns as over all points, in both setups (U at 01:00: mean
  1.15–1.16 with 30–31 % of the points > 1.1, against 1.06–1.07 and 13–14 %).
- QRAIN, inflated once in both setups, falls over every cycle in both, by similar factors.

## 7. Conclusions so far

1. **The MU λ leak (run 4) is fixed** by `obs_impact_mrms.txt`; replay (job 1054969) and run 4b confirm it. It did
   not cause the larger shock.
2. **The double inflation of U, V, THM, QVAPOR, QCLOUD** is the leading explanation of the larger shock: it gives the
   radar obs ~15–20 % more wind spread to act on, and leaves more analysis spread for the next cycle. It is not shown
   to be the cause.
3. **Remaining difference in λ handling** between 4b and run 3: the conventional obs adapt the hydrometeor and
   REFL_10CM λ (no table in the conventional pass). Small, and those fields are inflated only once anyway. Removed
   from 2026-10-23 on by `obs_impact_conv.txt` (plan step 1).
4. **`pass1` is not a clean test of conclusion 2.** Besides the second inflation it removes all inflation of the
   precipitation hydrometeors and REFL_10CM, and any radar adaptation of λ.

## 8. Plan for further two-pass tests (proposed 2026-10-22, not decided)

Each run changes one thing against a reference, 1 hour (00:00–01:00, `obs_madis_mrms/`) unless noted. Cost per
two-pass run: ~50 min on 40 nodes, ~550 GB (`output*/` 474 GB, `run*/` 77 GB). Runs 1–4b use ~2.2 TB: decide what
to trim first.

| step | what | job | reference | question |
|---|---|---|---|---|
| 0 | spread-by-stage diagnostics in `check_cycle.py` (done 2026-10-22) | none | backfill 3, 4, 4b | make Sec. 6 routine |
| 1 | impact table in the conventional pass + replay check (done 2026-10-23) | ~5 min | 4b | λ handling as in run 3 |
| 2 | `MRMS_INFLATION=pass1` | 1-hour run | 4b(c) | bound: no MRMS-pass inflation |
| 3 | new mode "inflate once" | coding, replay, 1-hour run | run 3, 4b(c) | does the double inflation cause the shock? |
| 4 | RTPS in both passes (HRRRDAS-like) | coding, 1-hour run | best of 2–3 | inflation design for the extension |
| 5 | damping / flavor-5 variants | 1-hour runs | chosen design | tuning |
| 6 | 3-hour runs of the best one- and two-pass setups | obs for 01:15 on, ~2.5 h each | each other | do the shock and spread level off? |

0. **Diagnostics first (no job).** Add a block to `check_cycle.py` per pass: domain RMS of the sd of U, V, THM,
   QVAPOR, QCLOUD, QRAIN, QSNOW, QGRAUP before inflation, after inflation and after assimilation, and the applied λ
   (mean, share > 1.1, max). Also restricted to echo regions (model or MRMS reflectivity ≥ 10 dBZ), where the radar
   increments and the shock are. Backfill runs 3, 4 and 4b. **Done 2026-10-22** (end of Sec. 6; the user chose the
   order 0 → 1 → 2, with 3 coded while 2 runs, and approves each step).
1. **Conventional-pass impact table.** `config/obs_impact_conv.txt` with the conventional rows of
   `obs_impact_joint.txt` (each conventional type → QRAIN, QSNOW, QGRAUP, `QTY_RADAR_REFLECTIVITY` = 0) in
   `input.nml.filter`. The rows must cover every assimilated conventional type, including `LAND_SFC_*` for the
   mesonet sets. A group (all types except the two radar types) would be more robust, if filter's reader accepts
   groups (to check). Expected, to verify by a replay like `slurm.mrms_impact_test`: member files bit-identical,
   λ different only in QRAIN, QSNOW, QGRAUP, REFL_10CM. Harmless for conventional-only runs, which never write those
   fields. Not a separate cycling run: it becomes part of every later two-pass run ("4c" = 4b with it, needed only
   if a clean reference is wanted). After it, the only differences from run 3 are the second inflation and the
   order of the observations.
   **Done 2026-10-23.** Filter's reader takes no groups (plain `type quantity factor` lines only; groups are expanded
   by the separate `obs_impact_tool`), so the table is the 88 non-radar rows of `obs_impact_joint.txt`, covering
   exactly the 22 assimilated types of `input.nml.filter`. Replay `slurm.conv_impact_test` (job 1056509; run 4b's
   first pass at 01:00, `tests/conv_impact/202505200100_1056509/`):
   - the no-table replay reproduces run 4b's first pass bit for bit (postassim members, mean, λ mean and sd);
   - with the table: member files and `obs_seq.final` bit-identical; filter read all 88 entries;
   - λ (`postassim_priorinf_mean`) differs only in QRAIN (9 % of the points, max 1.08), QSNOW (15 %, 1.18), QGRAUP
     (7 %, 1.23), REFL_10CM (16 %, 1.23); the λ sd, the applied λ and the prior mean are identical; the posterior
     mean and sd differ only in those 4 fields (the discarded analyses: max QRAIN 4.8 g/kg, REFL_10CM 47 dBZ);
   - filter 56 s against 64 s (same observation loop, 25 / 24 s).
2. **`pass1`** (`RUN_NAME=_madis_mrms2p_p1`; no code). Expect a smaller shock, more radar outliers, smaller radar
   increments and hydrometeor spread decaying over the cycles. Read it as a bound, not as proof of conclusion 2.
3. **"Inflate once"** (new `MRMS_INFLATION` value, name to decide). The MRMS pass applies λ only to the fields the
   conventional pass doesn't write back: QRAIN, QSNOW, QGRAUP, REFL_10CM. Its input λ is the conventional pass's,
   with λ = 1 for all other fields. The next cycle's λ is combined:
   - the MRMS pass's λ for QRAIN, QSNOW, QGRAUP, REFL_10CM;
   - the conventional pass's λ for the rest, either alone or times the radar's relative change (the MRMS pass's λ
     for those fields, which started at 1), to keep the radar's adaptation as in run 3. Which of the two: to decide.

   Every field that reaches the model is then inflated exactly once per cycle, as in run 3, with λ adapted by both
   families. This is the clean test of conclusion 2. Code: a small Python helper called from `prep_filter.sh`
   (build the MRMS input; compose the next cycle's input), settings recorded in `settings.txt`; test on the login
   node, then a replay, then a run.
4. **RTPS in both passes** (HRRRDAS: no prior inflation, RTPS after each pass, `analpertwt` 1.08 on its 3-km domain;
   `obs_expansion.md` Sec. 1). DART: posterior `inf_flavor` 4, the relaxation factor α in `inf_initial(2)` (posterior
   spread → (1 − α) × analysis spread + α × prior spread), prior flavor 0, no inflation files, no damping
   (`guide/inflation.rst`, `adaptive_inflate_mod.f90:476-500`). DART's guide recommends α between 0 and 1;
   `validate_inflate_options` doesn't reject more, but whether α = 1.08 behaves as in GSI is to be checked. No λ to
   carry or compose. RTPS restores spread
   only where a pass's obs reduced it, so there is no double inflation by construction. Open: whether RTPS alone keeps
   enough spread with 5 members and 15-min cycles. Needs a new setting in `experiment.sh` and `prep_filter.sh`.
5. **Damping and flavor 5** (`MRMS_PASS2_DAMPING=0`, `INF_DAMPING=0.9956`, flavor 5 with `INF_SD_LOWER_BOUND` < 0.6),
   only once the structure is chosen. Under `both` they mostly change the size of the double inflation.
6. **Longer runs.** Four analyses show trends (in 4 and 4b the shock grows every cycle), not where they level off.
   The best one-pass and two-pass setups need ~3 hours (12 analyses). That requires the observation sets for 01:15
   onward (`make_cycle_obs.sh` with MRMS; MADIS hours for 05-20/21 are converted) and disk at ~0.45–0.55 TB per hour
   of cycling, or trimmed outputs.

Run 3 (one pass) stays the reference and a candidate. So far two passes fit the radar slightly better but shock the
model more.
