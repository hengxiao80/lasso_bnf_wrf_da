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
| P4 | `hrrr_gsd_sfcobs_provider.txt` (HRRR, HRRRDAS: `${FIXhrrr}`) and `gsd_sfcobs_provider.txt` (RRFS v1: `${FIX_GSI}` = `${FIXrrfs}/gsi`) | named in the scripts only | **no** (not in either repo, 404 in GSI-fix) | unknown | no (P1 stands in for it) |

**Station lists** (station IDs; GSD use-list format: ID in columns 1–10, then one-character flags for wind (11–12), T (13–14), Td (15–16), then provider and statistics)

| ID | File | Where | Public? | Contents | Used in kept |
|---|---|---|---|---|---|
| S1 | `fix/jedi/current_mesonet_uselist.yaml` | `RRFSv2` (added `9c295a2d`, 2026-08-25, with `workflow/tools/convert_mesonet_uselist_to_yaml.py`) | yes | GSL's `current_mesonet_uselist.txt` converted to YAML, stations with flag 1 per variable: `temperature` 32,197 entries (31,642 unique IDs), `dewpoint` 13,061 (12,756), `wind` 1,518 (1,493). IDs repeat because the source has one line per station and provider; the YAML drops the provider. A 2026 snapshot. | `temperature` → T, `dewpoint` → q; `wind` **not** used |
| S2 | 42 "accept back selected stations" filters inside `parm/observers/msonet_uv288.yaml` | `RRFSv2` (and the baseline YAML) | yes | 4,214 (provider, station) pairs: AWS 1,378, RAWS 826, APRSWXNET 659, MesoWest 454, UrbaNet 356, Maritime 108, … Only 98 of them are on S1 `wind`. | yes, wind |
| S3 | `nam_mesonet_stnuselist.txt` (byte-identical to `rtma_ruc2_wind-uselist-noMETAR.dat`) | `GSI-fix_subset` | yes | 4,414 stations with wind statistics from 2007-10 (5-character IDs) | no |
| S4 | `rtma_w_rejectlist`, `rtma_p_rejectlist` (reject lists) | `GSI-fix_subset` | yes | 2,311 / 3,357 lines | no |
| S5 | `hrrr_current_mesonet_uselist.txt` (HRRR, HRRRDAS: `${FIXhrrr}`); RRFS v1: first readable of `current_mesonet_uselist.txt`, `YYYY-MM-DD_meso_uselist.txt` (previous day), `gsd_sfcobs_uselist.txt` in `${SFCOBS_USELIST}` | named in the scripts only | **no** | GSL daily station use-lists (RRFS v1's `SFCOBS_USELIST` points to `/lfs4/BMC/amb-verif/rap_ops_mesonet_uselists` at GSL, `FIX_RRFS/gsi` in operations) | no (S1 stands in for it) |

S1's source file has the same name as RRFS v1's first choice (`current_mesonet_uselist.txt`), so it is probably the same GSL product, at a later date. Not verified.

Other GSI-fix files seen in its file listing but not fetched: `rtma_{t,q}_rejectlist`, `rtma_{t,q}_{day,night}_rejectlist`, `rtma_wbinuselist`, `rtma_mesonet_vis_uselist.txt`, `urma2p5_*` lists, `rejectlist_global.txt`.

## 3. How GSI applies the lists (HRRR, HRRRDAS, RRFS v1)

GSI chooses a mode with `&RAPIDREFRESH_CLDSURF i_gsdsfc_uselist` (`read_prepbufr`, `sfcobsqc.f90`):

**Mode 1, "GSD" (`apply_gsd_sfcuselist`).** Used by all three GSI systems here. Applied to kx 188, 195, 288, 295; each report and variable separately:
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

**Other modes, for context (not used by the systems here).** Mode 2: RTMA-style `sfcobs_uselist.txt`. Default (NAM, RTMA; `get_usagerj`): T, q, ps only through reject lists; mesonet wind rejected unless its provider is in `mesonetuselist` (P2-type), its station in `mesonet_stnuselist` (S3-type) or it passes `wbinuselist`.

`convinfo` still decides whether type 188/288 is assimilated at all (`iuse`), its time window and gross checks; the lists only act on reports that convinfo uses.

## 4. Summary per system

| | Deterministic HRRR | HRRRDAS (EnKF observer, members and mean) | RRFS v1 (analysis and EnKF observer) | RRFS v2 (MPAS-JEDI) |
|---|---|---|---|---|
| Where set | `parm/conus/hrrr_gsiparm.anl.sh` 185, 189; `scripts/conus/exhrrr_analysis.sh` 222–223, 235–236 | `parm/hrrrdas/hrrrdas_gsiparm.anl[.mean]` 175, 179; `scripts/hrrrdas/exhrrr_analysis.sh` 236–237, 249–250 | `ush/gsiparm.anl.sh` 221, 225 (sourced for both OBSERVER and ANALYSIS, `scripts/exrrfs_analysis_gsi.sh` 983); lists staged at 796–825 | `parm/observers/msonet_{t188,q188,ps188,uv288}.yaml`, all four in `parm/observers/obslist.txt` |
| Selection | GSI mode 1, `i_gsdqc = 2` | GSI mode 1, `i_gsdqc = 2` | GSI mode 1, `i_gsdqc = 2` | JEDI filters |
| Provider list | P4 `hrrr_gsd_sfcobs_provider.txt` | P4 `hrrr_gsd_sfcobs_provider.txt` | P4 `gsd_sfcobs_provider.txt` | P1, **wind only** |
| Station list | S5 `hrrr_current_mesonet_uselist.txt` | **none**: the copy is commented out (`exhrrr_analysis.sh:249`) | S5, daily GSL list | S2, **wind only**; S1 is in the repo but **not referenced by any observer or YAML** |
| T, q | listed providers + stations flagged for T / Td | **listed providers only** | listed providers + stations flagged for T / Td | **all providers**; prepbufr quality marker 4–15 rejected, domain and bounds checks |
| Wind | listed providers + stations flagged for wind; calm rejected | listed providers only; calm rejected | listed providers + stations flagged for wind; calm rejected | reject all, accept P1 providers, accept S2 stations |
| Surface pressure | listed providers only | listed providers only | listed providers only | all providers (quality marker as for T) |
| convinfo | `hrrr_*` (not public) | `hrrrdas_regional_convinfo.15km.txt` (not public) | `convinfo.rrfs` from `${FIX_GSI}` (not in the repo; GSI-fix's `convinfo.rrfs`: 188/288 `iuse = 1`, ±0.1 h) | n/a (JEDI YAML: T error 4.0 K, GSI-style inflation, 200-km localization lengthscale) |

So: every GSI system restricts mesonet by **provider**; deterministic HRRR and RRFS v1 add **stations** from GSL's daily list for T, q and wind; HRRRDAS uses providers only; RRFS v2 restricts **only the wind**. The provider list that HRRR, HRRRDAS and RRFS v1 rely on (P4) and their station lists (S5) are not public.

## 5. Our "kept" counts (05-20 18Z) and how they were made

Not any one system's selection. A stand-in for GSI mode 1 (HRRR / RRFS v1) built from the public RRFS v2 files, except for wind, which follows RRFS v2's own filter:

- **Usable station, per variable:** in the domain box, at least one report in the hour with MADIS QCR = 0 for that variable (q: dewpoint and T; wind: speed and direction, and speed ≥ 0.01 m/s). A station counts once.
- **Kept:**
  - T: provider in P1, or station ID in S1 `temperature`.
  - q: provider in P1, or station ID in S1 `dewpoint`.
  - wind: provider in P1, or (provider, station) pair in S2 (RRFS v2's actual wind rule). Using S1 `wind` instead (the mode-1 analogue) keeps 944 instead of 950.
  - altimeter: provider in P1 only (mode 1 has no station path for pressure).

| Variable | usable | kept via P1 | kept via station list | kept | dropped |
|---|---|---|---|---|---|
| T | 2,953 | 1,175 (MesoWest 826, RAWS 237, HADS 61, KSDOT 25, MOComAgNet 22) | 1,369 (APRSWXNET 1,251, NonFedAWOS 93, OHDOT 17, CRN 8) | 2,544 | 409 (APRSWXNET 376, NonFedAWOS 29) |
| q | 2,553 | 838 (MesoWest 538, RAWS 236, KSDOT 23, MOComAgNet 22, HADS 19) | 339 (APRSWXNET 262, NonFedAWOS 65, OHDOT 12) | 1,177 | 1,376 (APRSWXNET 1,314, NonFedAWOS 57) |
| wind | 2,572 | 928 (MesoWest 597, RAWS 224, HADS 58, KSDOT 25, MOComAgNet 22) | 22 (APRSWXNET 16, OHDOT 4, NonFedAWOS 2) | 950 | 1,622 (APRSWXNET 1,498, NonFedAWOS 115) |
| altimeter | 1,715 | 296 (MesoWest 274, MOComAgNet 19, NOS 3) | — | 296 | 1,419 (APRSWXNET 1,296, NonFedAWOS 123) |

For comparison, RRFS v2 as it is would keep all 2,953 T, 2,553 q and 1,715 pressure stations, and the same 950 wind stations.

**Limits.** P1 for T/q/pressure is an assumption: the real P4 could include or leave out APRSWXNET or NonFedAWOS and change every row. S1 is a 2026 snapshot, not the May 2025 list. Station IDs were matched exactly, not by GSI's prefix rule. One hour, per hour rather than per 15-min cycle; the 44 NonFedAWOS stations that duplicate METAR are not removed.
