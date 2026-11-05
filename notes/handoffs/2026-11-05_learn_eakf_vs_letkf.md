# Hand-off: "learn: EAKF vs LETKF": DART's serial EAKF against the LETKF of GSI-EnKF (HRRR repo) and JEDI (RRFSv2)

Written 2026-11-05 at the end of session "learn: EAKF in DART Q&A" (questions on `notes/dart_eakf.md`). That session added a paragraph "Both are serial in the observations" to the note's Sec. 6.1 and changed its paper location to `notes/papers/`; both edits are committed together with this hand-off if the user agreed; check `git status`. No jobs running.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup, 5-member pilot, 50 members planned). Read `CLAUDE.md` first.

## The task

A **learning session on how DART's EAKF differs from the LETKF**, as implemented in GSI-EnKF (the copy in the HRRR repo, and current GSI) and in JEDI's local ensemble DA (RRFSv2's GETKF). No implementation work is planned. Ask the user at the start whether they want questions and answers only, or a walk-through note like `notes/dart_eakf.md`; if a note, propose its outline and file name first.

How to answer:
- **Start from `notes/dart_eakf.md`, then check the source.** Sec. 9.4–9.5 already cover the ETKF and LETKF math, Sec. 6.2 serial against simultaneous, Sec. 9.6 the literature, Sec. 11 item 6 what an LETKF would mean for us. Re-read the paper equation or code line before answering rather than answering from memory.
- **Equations: look at the rendered page, not only the extracted text.** pypdf garbles math (transposes, inverses, superscripts); the A01 transpose slip (note Sec. 8) was seen only on the rendered page.
- **Numbers: use the check script** (`notes/checks/eakf_checks.py`). Its `letkf()` is H07 (20)–(25) with GSI's R-localization, written by Claude, not a translation of `letkf.f90`. A line-by-line translation of GSI's LETKF (or of the gain form, B17) would be new work; say so before writing it.
- **Code first for "as implemented".** The questions are about what the code does, so read `letkf.f90` itself; the H07 math is the reference, not the description of GSI's code.
- **If an answer shows `dart_eakf.md` is wrong or incomplete,** say so and propose the edit (or make it, saying so); keep the Typora rules (`~/.claude/rules/typora-markdown.md`). No LaTeX in chat (`answer-style.md`).
- **If a question settles a namelist choice,** add a dated entry to `notes/dart_namelist_discussion_log.md`.
- **Commit only when the user says so,** on `main`.

## What is already established (`dart_eakf.md`)

- **Without localization** the serial EAKF and an ETKF give the same mean and covariance; for one observation the symmetric-root ETKF is the EAKF member by member (Sec. 9.4, check 1: 7e-16); for many, the members differ (check 2: 0.11 against deviations of 1.2).
- **The LETKF** does an ETKF analysis per grid point with the nearby observations and localizes by weighting $\mathbf R^{-1}$ (Sec. 9.5, Eq. (18)). At the same weight $\kappa$ its gain is $c/(\sigma_y^2+\sigma_o^2/\kappa)$ against the EAKF's $\kappa\,c/(\sigma_y^2+\sigma_o^2)$, so it damps accurate observations less (check 3 table). G11 and HW13: the best R-localization length is shorter than the best B-localization length.
- **Serial against simultaneous** (Sec. 6.2): with localization the serial result depends on the observation order and the covariance update is inconsistent (WH02, N15). Check 4 (toy: 1-D, 40 points, one untuned Gaspari–Cohn width, no cycling): LETKF best at $N$ = 20, worst at $N$ = 5 for accurate observations.
- **DART has no LETKF** (G+25: its serial design "avoids matrix operations central to the LETKF").

## Who runs what (checked 2026-11-05 from the configuration files)

| system | filter | where |
|---|---|---|
| HRRRDAS | serial EnSRF | HRRR repo¹ |
| RRFSv1 | serial EnSRF | `exrrfs_analysis_enkf.sh`² |
| RRFSv2 | JEDI GETKF | `getkf_header.yaml`³ |
| our runs | serial EAKF | DART |

¹ GSI-EnKF with `deterministic = .true.`; `letkf_flag` (default `.false.`, `params.f90:163`) is not set anywhere in `scripts/hrrrdas/` or `parm/hrrrdas/`. The repo carries `letkf.F90`, unused by HRRRDAS.
² `RRFSv1/scripts/exrrfs_analysis_enkf.sh:268–289`: `deterministic=.true.`, no `letkf_flag`, RTPS `analpertwt` 1.10, `paoverpb_thresh=0.98`. GSI is an external (`sorc/Externals.cfg`), not checked out.
³ `RRFSv2/parm/getkf_header.yaml:76–84`: `local ensemble DA`, `solver: Deterministic GETKF`, `use linear observer: true`, vertical localization by modulated ensembles (`fraction of retained variance` 0.850, `lengthscale` 0.50 in `logp`; comment "12 modulated members"), RTPS 0.95. The header says `run as observer only: true`; `ush/yaml_finalize:145–156` sets it to false for the solver step (`GETKF_TYPE`). Horizontal localization per observer in `parm/observers/*.yaml`: `Horizontal Gaspari-Cohn`, `lengthscale` 200e3 for conventional types, 15e3 for `refl10cm`.

So the LETKF family is operational for us to compare against only in RRFSv2; HRRRDAS and RRFSv1 run the same serial square-root update as DART (`dart_eakf.md` Sec. 9.3).

## GSI-EnKF's LETKF: first facts from reading the code (not run)

`../software/GSI/src/enkf/letkf.f90` (`124138df0`, 971 lines); the HRRR copy `../software/HRRR/sorc/hrrr_gsi.fd/src/enkf/letkf.F90` (`40ee6058`, 1036 lines) differs in 283 lines (not yet looked at).
- Header (`:1–80`): H07, in the **gain form** of B17; observations found with a kd-tree; at most `nobsl_max` per local patch (closest first, or by DFS with `dfs_sort`); vertical localization off with `letkf_novlocal`, and off automatically with model-space vertical localization by modulated ensembles (`neigv > 0`, eigenvectors from `vlocal_eig.dat`); no observation-space update of its own (`lupd_obspace_serial = .true.` uses the serial EnSRF for that).
- Options in `params.f90` (HRRR copy `:116–163`, GSI `:150–203`): `nobsl_max`, `modelspace_vloc`, `getkf` (gain form, forced on with `modelspace_vloc`), getkf inflation, `denkf` (DEnKF approximation), `lupd_obspace_serial`, `letkf_novlocal`, `letkf_flag`.
- **3-D weight** (`:413–433`): one taper of a combined normalized distance, `dist = sqrt(sresults(nob)%dis/corrsq+vdist*vdist)` with `vdist = (lnp_chunk - oblnp)/lnsigl` (Δ ln p over the vertical cutoff), skipped if `dist >= one`, then `rloc = taper(dist)` (`:433`), applied to $\mathbf R^{-1}$ (`rrloc = rdiaginv * rloc`, `:741`). That is DART's shape (`dart_eakf.md` Eq. (12)), not the product of a horizontal and a vertical taper that GSI's serial EnSRF uses (Sec. 10.3). Worth confirming.
- Loops over grid points and, with vertical localization, over levels (`verloop`, `:402`): one local analysis per point and level.

## Open questions to start from (the user decides the order)

1. The math in one place: ETKF in ensemble space, the local analysis, R- against B-localization; why the two agree without localization and differ with it. (`dart_eakf.md` Sec. 9.4–9.5; H07 Sec. 2–3; B01; T03.)
2. What GSI's `letkf_update` does step by step: observation search, weights, the gain form (B17), the eigenproblem per patch, how H(x) is treated (linearized as $\bar{\mathbf y}+\mathbf Y\mathbf w$, observation priors not updated), inflation hooks.
3. What the 283 differing lines between the HRRR copy and current GSI change.
4. Model-space vertical localization with modulated ensembles (B17; GSI `modelspace_vloc`; RRFSv2's 12 modulated members), and why it matters for satellite radiances and radar.
5. JEDI's GETKF in RRFSv2: what its `lengthscale` means (half-width or zero-weight distance), how the RTPS 0.95 compares with HRRRDAS's 1.08 and RRFSv1's 1.10. The JEDI source isn't here: `RRFSv2/sorc/RDASApp` is an empty submodule. Cloning JEDI (into `../software/`, own name, full clone, cite the commit) needs the user's go-ahead.
6. For our runs: is an LETKF worth it for MRMS (N15's warning case, `dart_eakf.md` Sec. 11 items 2 and 6), and what a fair comparison needs (retuned R-localization radius).

## Sources at hand

- **Papers** in `notes/papers/` (labels as in `dart_eakf.md` Sources): H07, B01, T03, B17, G11, HW13, N15, HZ16, WH02, WH12, AC07, A01, A03, G+25, D20, D22.
- **Not in `notes/papers/`:** Lei, Whitaker and Bishop (2018, JAMES) on model-space localization in the GETKF, and any JEDI LETKF/GETKF documentation. Ask the user for PDFs if a question needs them; check DOIs against Crossref before citing.
- **Code:** GSI `124138df0` (`../software/GSI/src/enkf/`: `letkf.f90`, `params.f90`, `covlocal.f90`, `enkf_main.f90:207–213` for the `letkf_flag` switch); HRRR copy `40ee6058` (`../software/HRRR/sorc/hrrr_gsi.fd/src/enkf/`); RRFSv1 `d228600e`, RRFSv2 `08eee4ce` (`../software/RRFSv1`, `../software/RRFSv2`); DART `7bbd35a09` (`../software/DART`).
- **Notes:** `dart_eakf.md` (above), `dart_adaptive_inflation.md` (RTPS against our adaptive inflation), `obs_expansion.md` ("EnKF" table: HRRRDAS settings).

Commands:
- Check script (about 2 minutes; `4` and `5` skip the slow checks): `uv run --no-project --with numpy python -I notes/checks/eakf_checks.py [4] [5]`
- PDF text: `uv run --no-project --with pypdf python -I <script>` (the project `.venv` has no pypdf); keep the text in the session scratchpad.
- PDF page as an image, for equations (`pdftoppm` isn't installed): `uv run --no-project --with pymupdf python -I <script>` with `pymupdf.open(pdf)[page-1].get_pixmap(dpi=170).save(png)`, then read the PNG.

## Starting the session

Name it `learn: EAKF vs LETKF` (it then files into the `learn` group), and name this file in the first prompt (`notes/handoffs/2026-11-05_learn_eakf_vs_letkf.md`).
