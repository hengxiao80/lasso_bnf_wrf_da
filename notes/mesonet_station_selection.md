# Mesonet station and provider selection in HRRR, HRRRDAS, RRFS v1 and RRFS v2

Written 2026-10-13 (session "Adding more obs part 2") for the mesonet step of `obs_expansion.md` (Sec. 7).
What each reference system does to choose which MADIS/prepbufr mesonet stations (report types 188
mass, 288 wind; 195/295 where noted) it assimilates, which list files it reads, and how our "kept"
counts were made. Everything here is read from code at the commits below; nothing was run.

## 1. Reference code (all in `../software/`, full clones unless noted)

| Name | Upstream | Branch / commit | What it represents |
|---|---|---|---|
| `HRRR` | NOAA-EMC/HRRR | `develop` `40ee6058` (2026-05-01) | HRRRv4 operational code: deterministic HRRR (`scripts/conus`, `parm/conus`) and HRRRDAS (`scripts/hrrrdas`, `parm/hrrrdas`). Carries its own GSI source in `sorc/hrrr_gsi.fd`. |
| `GSI` | NOAA-EMC/GSI | `develop` `124138df0` (2026-09-01); also contains `db90edf` | GSI source. `db90edf` is the hash RRFS v1 pins (`RRFSv1/sorc/Externals.cfg` `[GSI]`). |
| `RRFSv1` | NOAA-EMC/rrfs-workflow | `release/v1.0` `d228600e` (2026-10-07) | RRFS v1 (FV3 + GSI hybrid EnVar and GSI-observer EnKF). Was cloned as `rrfs-workflow`, renamed 2026-10-13. |
| `RRFSv2` | NOAA-EMC/rrfs-workflow | `rrfs-mpas-jedi` `08eee4ce` (2026-10-09) | RRFS v2 (MPAS + JEDI), in development, not operational. |
| `GSI-fix_subset` | NOAA-EMC/GSI-fix | `0ba656b6`, single files only (`SOURCE.txt`) | GSI fix files: convinfo/errtables (Sec. 5 of `obs_expansion.md`) and the public mesonet lists below. |

**The mesonet selection code is the same in all three GSI versions.** `apply_gsd_sfcuselist` (`src/gsi/sfcobsqc.f90`)
is identical (no diff) in GSI `develop`, RRFS v1's `db90edf` and HRRR's `sorc/hrrr_gsi.fd`; all three read the same
two file names with the same columns, call it under `i_gsdsfc_uselist == 1` for kx 188/195/288/295, and have the same
`i_gsdqc == 2` checks (`read_prepbufr`: GSI `develop` `.F90` 2067–2124, `db90edf` 2069–2117, HRRR `.f90` 1886–1905).

## 2. List files found

IDs as used in this note and in the session. "Used in kept" refers to Sec. 5.

**Provider lists** (a provider, optionally a subprovider; GSI format: provider in columns 1–8, subprovider in 9–16 or `allsprvs`)

| ID | File | Where | Public? | Contents | Used in kept |
|---|---|---|---|---|---|
| P1 | `AcceptProvidersRaws` filter inside `parm/observers/msonet_uv288.yaml` (not a separate file) | `RRFSv2` (also in the generated `parm/baseline_jedi_yamls/jedivar_3denvar.yaml`, section `msonet_winds_288`) | yes | 20 providers: RAWS, NEDOR, SFWMD, MOComAgNet, UDFCD, CAIC, CODOT, KSDOT, IADOT, MEDOT, MNDOT, NDDOT, OK-Meso, MesoWest, WT-Meso, WYDOT, NOS-PORTS, NOS-NWLON, GoMOOS, HADS | yes, all variables |
| P2 | `nam_mesonet_uselist.txt` | `GSI-fix_subset` | yes | 21 entries: P1 + FL-Meso/FAWN | no |
| P3 | `rtma_mesonet_uselist.txt` | `GSI-fix_subset` | yes | 17 entries: FL-Meso/FAWN, SFWMD, CAIC, OK-Meso, WT-Meso, WYDOT, NOS-PORTS, NOS-NWLON, GoMOOS, LSU-JSU, NYSM, NJWxNet, WxFlow, UrbaNet, NonFedAWOS, ARLFRD, RAWS | no |
| P4 | `hrrr_gsd_sfcobs_provider.txt` (HRRR, HRRRDAS: `${FIXhrrr}`) and `gsd_sfcobs_provider.txt` (RRFS v1: `${FIX_GSI}` = `${FIXrrfs}/gsi`) | not in the current trees, but **in the git history**: `HRRR` `hrrr.v3/fix/conus/hrrr_gsd_sfcobs_provider.txt` (added 2018-02-15, removed 2019-12-18; last at `14181fb1`; also `hrrr.v2/fix/`, `hrrr_cray/fix/`) and `RRFSv1` `fix/gsi/gsd_sfcobs_provider.txt` (added `260b9c1a` 2021-09-17, removed from the v1 line by `200d8eca` 2025-04-03 "preparing for production"; last at `4aa5a48d`) | yes, historical copies; the HRRRv4 and current RRFS v1 operational copies are in their external fix directories | **The same blob (`c6ff7d9c`) in HRRRv3 and in RRFS v1 throughout 2021–2025**: 9 entries: FL-Meso/FAWN, SFWMD, CAIC, OK-Meso, WT-Meso, WYDOT, NOS-PORT(S), NOS-NWLO(N), GoMOOS. No MesoWest, RAWS, HADS, APRSWXNET, NonFedAWOS or state DOTs except WYDOT. | Sec. 5 option (b) |
| P5 | `fix/jedi/mesonet_trusted_provider.yaml` | `RRFSv2` (added `9c295a2d`, 2026-08-25) | yes | P4's 9 providers in YAML (`subprovider: all` / `FAWN`) | **not referenced** by any observer or YAML (like S1); no |

**Station lists** (station IDs; GSD use-list format: ID in columns 1–10, then one-character flags for wind (11–12), T (13–14), Td (15–16), then provider and statistics)

| ID | File | Where | Public? | Contents | Used in kept |
|---|---|---|---|---|---|
| S1 | `fix/jedi/current_mesonet_uselist.yaml` | `RRFSv2` (added `9c295a2d`, 2026-08-25, with `workflow/tools/convert_mesonet_uselist_to_yaml.py`) | yes | GSL's `current_mesonet_uselist.txt` converted to YAML, stations with flag 1 per variable: `temperature` 32,197 entries (31,642 unique IDs), `dewpoint` 13,061 (12,756), `wind` 1,518 (1,493). IDs repeat because the source has one line per station and provider; the YAML drops the provider. A 2026 snapshot. | `temperature` → T, `dewpoint` → q; `wind` **not** used |
| S2 | 42 "accept back selected stations" filters inside `parm/observers/msonet_uv288.yaml` | `RRFSv2` (and the baseline YAML) | yes | 4,214 (provider, station) pairs: AWS 1,378, RAWS 826, APRSWXNET 659, MesoWest 454, UrbaNet 356, Maritime 108, … Only 98 of them are on S1 `wind`. | yes, wind |
| S3 | `nam_mesonet_stnuselist.txt` (byte-identical to `rtma_ruc2_wind-uselist-noMETAR.dat`) | `GSI-fix_subset` | yes | 4,414 stations with wind statistics from 2007-10 (5-character IDs) | no |
| S4 | `rtma_w_rejectlist`, `rtma_p_rejectlist` (reject lists) | `GSI-fix_subset` | yes | 2,311 / 3,357 lines | no |
| S5 | `hrrr_current_mesonet_uselist.txt` (HRRR, HRRRDAS: `${FIXhrrr}`); RRFS v1: first readable of `current_mesonet_uselist.txt`, `YYYY-MM-DD_meso_uselist.txt` (previous day), `gsd_sfcobs_uselist.txt` in `${SFCOBS_USELIST}` | current copies named in the scripts only. `RRFSv1`'s `fix/gsi/gsd_sfcobs_uselist.txt` (2021–2025) was **always a symlink** (git mode 120000) to `../.agent/gsi/gsd_sfcobs_uselist.txt`, outside the repo | **no** | GSL daily station use-lists (RRFS v1's `SFCOBS_USELIST` points to `/lfs4/BMC/amb-verif/rap_ops_mesonet_uselists` at GSL, `FIX_RRFS/gsi` in operations) | no (S1 or S6 stand in for it) |
| S6 | `hrrr.v3/fix/conus/hrrr_current_mesonet_uselist.txt` | `HRRR` git history (added 2018-02-15, removed 2019-12-18; last at `14181fb1`) | yes, historical | A dated GSL use-list, **mesonet data 2017-10-30 18Z to 2017-11-07 22Z**: 20,996 entries (20,914 unique IDs), wind = 1 for 2,730, T = 1 for 20,369, Td = 1 for 15,843; includes METAR stations (3,099). Providers: APRSWXNET 8,289, METAR 3,099, AWS 2,492, MesoWest 2,008, RAWS 1,828, … Its header gives the selection rule (below). | Sec. 5, as an alternative to S1 |

S1's source file has the same name as RRFS v1's first choice (`current_mesonet_uselist.txt`), and S6 has the same format, so S1, S5 and S6 are the same GSL product at different dates (2026, operational, 2017).

**How GSL builds the station list (S6 header).** From the table `RR1h_7day` (7 days of 1-h forecast minus observation; "RR" presumably the Rapid Refresh), separately for each variable, a station gets flag 1 if:
- T: N > 20, |bias| < 2.00 K, std < 2.50 K;
- wind: N > 20, speed |bias| < 0.50 m/s and std < 1.50 m/s, direction |bias| < 40° and std < 90°, vector rms < 2.00 m/s;
- Td: N > 20, |bias| < 1.20 K, std < 2.50 K.
So the list is regenerated from recent statistics (RRFS v1 takes the previous day's), and the wind criteria are strict: of the 8,289 APRSWXNET stations in S6, 190 pass for wind and 8,113 for T.

Historical copies are read with `git -C ../software/HRRR show 14181fb1:hrrr.v3/fix/conus/<file>` and `git -C ../software/RRFSv1 show 4aa5a48d:fix/gsi/gsd_sfcobs_provider.txt`.

Other GSI-fix files seen in its file listing but not fetched: `rtma_{t,q}_rejectlist`, `rtma_{t,q}_{day,night}_rejectlist`, `rtma_wbinuselist`, `rtma_mesonet_vis_uselist.txt`, `urma2p5_*` lists, `rejectlist_global.txt`.

## 3. How GSI applies the lists (HRRR, HRRRDAS, RRFS v1)

GSI chooses the method with `&RAPIDREFRESH_CLDSURF i_gsdsfc_uselist`, documented in `rapidrefresh_cldsurf_mod.f90:122–127` as "options for how to use surface observation use or rejection list": `0` "EMC method" (default), `1` "GSD method", `2` "expansion of GSD method to include provider/subprovider based criteria and diurnal accept lists". GSD is NOAA's former Global Systems Division (now the Global Systems Laboratory, GSL), which develops RAP and HRRR; EMC is NCEP's Environmental Modeling Center. Code in `read_prepbufr` and `sfcobsqc.f90`.

**GSD method, `i_gsdsfc_uselist = 1` (`apply_gsd_sfcuselist`).** Used by all three GSI systems here. Applied to kx 188, 195, 288, 295; each report and variable separately:
1. Already rejected (usage ≥ 6): unchanged.
2. Provider path: if the report's provider (first 8 characters) matches a `gsd_sfcobs_provider.txt` entry and its subprovider matches or the entry says `allsprvs`, the report is used, **for every variable, pressure included**.
3. Otherwise it is rejected (usage 6000), unless a use-list file `gsd_sfcobs_uselist.txt` exists; then:
   - T (kx < 200, obstype `t`): used if the station is on the use-list with T flag `1`.
   - q (obstype `q`): used if the station's Td flag is `1`.
   - wind (kx ≥ 200, obstype `uv`): used if the station's wind flag is `1`.
   - surface pressure (`ps`) has no station path: from an unlisted provider it stays rejected.
   Station match: the trimmed station ID equals the list ID, **or, for mesonet types, the station ID starts with the list ID** (prefix match).
4. If neither file exists: every mesonet report is rejected. With only the provider list: only listed providers.

Separately, `i_gsdqc = 2` (set by HRRR, HRRRDAS and RRFS v1) adds: mesonet winds with u = v = 0 rejected (usage 115; kx 288 in HRRR's GSI, 288 and 295 in the GSI repo); 2-m dewpoints rejected if Td < min(−40 °C, T − 10 K), T − Td > 70 K or Td > 32.2 °C (types 180–189). Independently of mode: mesonet pressure is never used when the 8th character of the station ID is `x`.

**Other methods, for context (not used by the systems here).** `= 2`: RTMA-style `sfcobs_uselist.txt`. `= 0`, EMC method (NAM, RTMA; `get_usagerj`): T, q, ps only through reject lists; mesonet wind rejected unless its provider is in `mesonetuselist` (P2-type), its station in `mesonet_stnuselist` (S3-type) or it passes `wbinuselist`.

`convinfo` still decides whether type 188/288 is assimilated at all (`iuse`), its time window and gross checks; the lists only act on reports that convinfo uses.

## 4. Summary per system

| | Deterministic HRRR | HRRRDAS (EnKF observer, members and mean) | RRFS v1 (analysis and EnKF observer) | RRFS v2 (MPAS-JEDI) |
|---|---|---|---|---|
| Where set | `parm/conus/hrrr_gsiparm.anl.sh` 185, 189; `scripts/conus/exhrrr_analysis.sh` 222–223, 235–236 | `parm/hrrrdas/hrrrdas_gsiparm.anl[.mean]` 175, 179; `scripts/hrrrdas/exhrrr_analysis.sh` 236–237, 249–250 | `ush/gsiparm.anl.sh` 221, 225 (sourced for both OBSERVER and ANALYSIS, `scripts/exrrfs_analysis_gsi.sh` 983); lists staged at 796–825 | `parm/observers/msonet_{t188,q188,ps188,uv288}.yaml`, all four in `parm/observers/obslist.txt` |
| Selection | the GSD method, `i_gsdqc = 2` | the GSD method, `i_gsdqc = 2` | the GSD method, `i_gsdqc = 2` | JEDI filters |
| Provider list | P4 `hrrr_gsd_sfcobs_provider.txt` (HRRRv3 copy: the 9 providers) | P4 `hrrr_gsd_sfcobs_provider.txt` (same file) | P4 `gsd_sfcobs_provider.txt` (repo copy 2021–2025: the same 9 providers) | P1, **wind only**; P5 (= P4) is in the repo but not referenced |
| Station list | S5 `hrrr_current_mesonet_uselist.txt` (S6 is its HRRRv3 copy from 2017) | **none**: the copy is commented out (`exhrrr_analysis.sh:249`) | S5, daily GSL list (previous day) | S2, **wind only**; S1 is in the repo but **not referenced by any observer or YAML** |
| T, q | listed providers + stations flagged for T / Td | **listed providers only** | listed providers + stations flagged for T / Td | **all providers**; prepbufr quality marker 4–15 rejected, domain and bounds checks |
| Wind | listed providers + stations flagged for wind; calm rejected | listed providers only; calm rejected | listed providers + stations flagged for wind; calm rejected | reject all, accept P1 providers, accept S2 stations |
| Surface pressure | listed providers only | listed providers only | listed providers only | all providers (quality marker as for T) |
| convinfo | `hrrr_*` (not public) | `hrrrdas_regional_convinfo.15km.txt` (not public) | `convinfo.rrfs` from `${FIX_GSI}` (not in the repo; GSI-fix's `convinfo.rrfs`: 188/288 `iuse = 1`, ±0.1 h) | n/a (JEDI YAML: T error 4.0 K, GSI-style inflation, 200-km localization lengthscale) |

So: every GSI system restricts mesonet by **provider**; deterministic HRRR and RRFS v1 add **stations** from GSL's daily list for T, q and wind; HRRRDAS uses providers only; RRFS v2 restricts **only the wind**. The provider list (P4) is a short list of 9 regional networks (HRRRv3 and RRFS v1 repo copies; HRRRv4's operational copy is not public but has the same file name and role), so **in the GSI systems almost all mesonet data come in through the station list**, and HRRRDAS, which has none, takes only those 9 networks. The current station lists (S5) are not public; S6 (2017) and S1 (2026) are dated copies of the same GSL product.

## 5. Our "kept" counts (05-20 18Z) and how they were made

**Usable station, per variable:** in the domain box, at least one report in the 18Z MADIS hour with QCR = 0 for that variable (q: dewpoint and T; wind: speed and direction, and speed ≥ 0.01 m/s, i.e. calm winds dropped as by `i_gsdqc = 2`). A station counts once. Usable: T 2,953, q 2,553, wind 2,572, altimeter 1,715.

**Kept** under each selection (provider matched on its first 8 characters, as GSI compares `c_prvstg(1:8)`; station IDs matched exactly, not by GSI's prefix rule):

| Option | Rule | T | q | wind | altimeter |
|---|---|---|---|---|---|
| (a) RRFS v2 as it is | T, q, pressure: all providers; wind: P1 providers or S2 stations | 2,953 | 2,553 | 950 | 1,715 |
| (b1) GSD method, deterministic HRRR / RRFS v1, 2026 station list | provider in P4 (9), or station flagged in S1 for that variable; pressure: P4 only | 2,108 | 815 | 41 | 3 |
| (b2) same with the 2017 station list | P4, or station flagged in S6 | 932 | 799 | 160 | 3 |
| (c) HRRRDAS | P4 providers only | 4 | 0 | 2 | 3 |
| (d) earlier stand-in (superseded) | P1 (20) instead of P4 for every variable; S1 for T/q, S2 for wind | 2,544 | 1,177 | 950 | 296 |

Breakdown of (b1): via P4 only NOS-PORTS/NOS-NWLON (T 4, wind 2, altimeter 3); via S1: T 2,104 (APRSWXNET 1,251, MesoWest 470, RAWS 190, NonFedAWOS 93, HADS 41), q 815 (APRSWXNET 262, MesoWest 257, RAWS 184, NonFedAWOS 65), wind 39 (NonFedAWOS 19, RAWS 10, MesoWest 8). 06Z gives T 2,113, q 821, wind 35, altimeter 3. Breakdown of (d), via P1: T 1,175, q 838, wind 928, altimeter 296 (mostly MesoWest and RAWS); via S1/S2: T 1,369, q 339, wind 22.

**Reading.** None of the 9 P4 networks has more than a handful of stations in our domain, so under the GSD method the station list decides everything, and its date matters: the 2017 and 2026 lists keep 932 vs 2,108 T stations (station IDs turn over, APRSWXNET especially). The GSD method keeps very few mesonet winds (41–160) and no mesonet pressure here. HRRRDAS, with providers only, would take essentially no mesonet in our domain, if its HRRRv4 provider list is still the 9-provider one.

**Limits.** Calm winds were dropped for every option; RRFS v2 has no calm-wind check (its wind observer has only bounds, domain, background and quality-marker checks), so (a) would also take the calm reports of its accepted stations. P4 is the HRRRv3/RRFS v1 repo copy; the HRRRv4 and current RRFS v1 operational lists are not public. Neither S1 (2026) nor S6 (2017) is the May 2025 list RRFS v1 would have used. One hour, per hour rather than per 15-min cycle; the 44 NonFedAWOS stations that duplicate METAR are not removed.
