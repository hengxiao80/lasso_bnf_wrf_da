# Hand-off: "learn: EAKF Q&A": questions and answers on the EAKF walk-through (`notes/dart_eakf.md`)

Written 2026-10-25 at the end of session "learn: EAKF in DART" (EAKF walk-through note, check script, commit `ec424e1`). A correction found while writing this hand-off (A01's Appendix A transpose, note Sec. 8 and check 1 of the script) is committed together with this note if the user agreed; check `git status`. The 26 paper PDFs in `notes/` stay untracked. No jobs running.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup, 5-member pilot, 50 members planned). Read `CLAUDE.md` first.

## The task

A **question-and-answer session on `notes/dart_eakf.md`**. The user reads the note and asks questions; there is no implementation work planned. Wait for the questions.

How to answer:
- **Start from the note, then check the source.** Every claim in the note cites a paper equation or a code line; re-read that source before answering rather than answering from memory.
- **Equations: look at the rendered page, not only the extracted text.** pypdf garbles math (transposes, inverses, superscripts). The A01 transpose slip (note Sec. 8) was missed in the text and only seen on the rendered page.
- **Numbers: use the check script.** Its functions (DART's EAKF and regression, GSI's EnSRF, LETKF, ETKF, Gaspari–Cohn) can be reused for small worked examples when a question needs one.
- **If an answer shows the note is wrong, unclear or incomplete,** say so, propose the edit (or make it, saying so), rerun the script if numbers change, and keep the Typora rules (`~/.claude/rules/typora-markdown.md`).
- **If a question settles a namelist choice,** add a dated entry to `notes/dart_namelist_discussion_log.md` (its 2026-10-25 entries cover the EAKF and SEC).
- **Commit only when the user says so,** on `main`.

## What the note contains

| sec. | topic |
|---|---|
| 0–1 | summary; notation with the code's names |
| 2 | Bayes on the joint state; the Kalman target |
| 3 | one observation: product, shift and shrink, examples |
| 4 | regression; proof that it gives the Kalman mean and covariance |
| 5 | Gaspari–Cohn localization, DART's 3-D distance, our cutoffs |
| 6 | sequential vs parallel algorithm (AC07); order dependence |
| 7 | the code step by step, with line numbers |
| 8 | papers against code (incl. A01 App. A) |
| 9 | EnKF, EnSRF, ETKF, LETKF; literature comparisons |
| 10 | HRRRDAS's EnKF next to ours |
| 11 | what it means for our runs |
| 12 | the checks |

Main results:
- DART's EAKF and GSI's serial EnSRF (what HRRRDAS runs) are identical member by member, with localization too.
- Serial processing reproduces the Kalman filter exactly without localization; with localization it depends on the observation order and is weakest for accurate, dense observations (Nerger 2015), i.e. MRMS in convection.
- The LETKF localizes R, which damps accurate observations less at the same radius; it is not in DART.
- HRRRDAS differs from us around the update: RTPS 1.08 vs adaptive prior inflation, no SEC, separable 3-D localization, two passes, 36 members.
- A01's Appendix A as printed updates members with $\mathbf A^T$, inconsistent with $\mathbf\Sigma_u = \mathbf A\mathbf\Sigma\mathbf A^T$; with $\mathbf A$ the covariance is right but the members differ; with a trailing $\mathbf U^T$ it matches DART.

## How solid each kind of claim is

- **Checked numerically** (`notes/checks/eakf_checks.py`, checks 1–10): the identities (EAKF = EnSRF = symmetric ETKF for one observation; serial = Kalman without localization), the A01 readings, the WH02 scalar numbers, $k$ and $a$, float32 round-off, DART's Gaspari–Cohn = GSI's taper, the 3-D weight table, the worked examples.
- **Checked numerically, but a toy:** check 4 (localized single analysis, 1-D periodic, 40 points, Gaussian covariance, one Gaspari–Cohn width for every method, not tuned, no cycling) and check 9 (nonlinear H, 6 variables). They show directions, not sizes for WRF.
- **Implementations that are mine, not the original code:** the LETKF (H07 Eqs. (20)–(25) with GSI's R-localization, not GSI's `letkf.f90` itself); the batch B-localized update; the float32 emulation (numpy, not compiled Fortran). The DART translations leave out SEC and inflation; the GSI translation follows the HRRR copy of `enkf.f90`.
- **From reading the code only, not run:**
  - HRRRDAS's `numiter = 6` giving the result of `numiter = 1` (no satellite bias correction, `varqc = .false.`);
  - DART's RTPS not rejecting α > 1 (nothing found in `validate_inflate_options`);
  - GSI updating the H(x) of observations already assimilated;
  - the vertical coordinates ($\ln p$ in GSI, $-\ln(p/p_{\rm sfc})$ in DART's WRF `model_mod`).
- **From the papers:** the literature comparisons (A01, WH02, G11, HW13, N15, HZ16). N15's cycled results are more nuanced than the toy (note Sec. 6.2).

## Likely questions and where to look

- Why the regression gives the Kalman filter: note Sec. 4.2; A03 (14), (20)–(27).
- EAKF vs EnSRF, and why localization doesn't break the identity: Sec. 9.3; GSI `enkf.f90:463–470`, `:652–656`.
- What "B-" and "R-localization" do differently: Sec. 9.5; G11; HW13 Sec. 2.
- Why the order matters only with localization: Sec. 6.2; WH02 p. 1919; N15 Sec. 2c.
- What changes at 50 members: Sec. 11 item 7; `dart_sampling_error_correction.md` Sec. 7.
- RTPS against our adaptive inflation: Sec. 10.1, 11 item 1; `dart_adaptive_inflation.md`; WH12.
- QCEFF: note Sec. 7.6 only. The QCEFF papers aren't in `notes/` (DOIs in the note's Sources); ask the user if a question needs them.

## Sources at hand

- **Papers:** PDFs in `notes/`, labels as in the note's Sources (A01, A03, AC07, A+09, G+25, GC99, A12, A07a/b, A09, G18, B98, HM98, HM01, B01, WH02, T03, H07, G11, WH12, HW13, N15, HZ16, B17, D20, D22).
- **Code:** DART `7bbd35a09` (`../software/DART`); GSI-EnKF as in the HRRR repo `40ee6058` (`../software/HRRR/sorc/hrrr_gsi.fd/src/enkf/`); GSI `124138df0` (`../software/GSI`, for `letkf.f90`); HRRRDAS scripts in `../software/HRRR/scripts/hrrrdas/` and `parm/hrrrdas/`.
- **Related notes:** `dart_workflow_walkthrough.md`, `dart_sampling_error_correction.md`, `dart_adaptive_inflation.md`, `obs_expansion.md` ("EnKF" table), `codex.WRF_DART_Discussion_and_Branches_Summary_v1.md` Sec. 7–8 (an earlier summary).

Commands:
- Check script (about 2 minutes; `4` and `5` skip the slow checks): `uv run --no-project --with numpy python -I notes/checks/eakf_checks.py [4] [5]`
- PDF text: `uv run --no-project --with pypdf python -I <script>` (the project `.venv` has no pypdf); keep the text in the session scratchpad.
- PDF page as an image, for equations (`pdftoppm` isn't installed): `uv run --no-project --with pymupdf python -I <script>` with `pymupdf.open(pdf)[page-1].get_pixmap(dpi=170).save(png)`, then read the PNG.

## Starting the session

Name it `learn: EAKF Q&A` (it then files into the `learn` group), and name this file in the first prompt (`notes/handoffs/2026-10-25_learn_eakf_qa.md`): the session index links a hand-off to a session by its title only for names without a colon, so here the link comes from the first prompt.
