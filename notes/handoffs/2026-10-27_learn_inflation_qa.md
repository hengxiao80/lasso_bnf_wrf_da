# Hand-off: "learn: inflation Q&A": questions and answers on adaptive prior inflation (`notes/dart_adaptive_inflation.md`)

Written 2026-10-27 at the end of session "Adaptive prior inflation in DART" (the inflation note and its discussion-log entry, commit `15d442c`, 2026-10-23; the check scripts, moved into `notes/checks/`, are committed together with this hand-off). No jobs running.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup, 5-member pilot, 50 members planned). Read `CLAUDE.md` first.

## The task

A **question-and-answer session on `notes/dart_adaptive_inflation.md`**: DART's adaptive prior inflation, flavor 2 (Anderson 2009) and flavor 5 (El Gharamti 2018), the math and the code. The user reads the note and asks questions; there is no implementation work planned. Wait for the questions.

How to answer:
- **Start from the note, then check the source.** The note cites code lines (DART `7bbd35a09`) and paper equations (A09, G18); re-read that source before answering rather than answering from memory.
- **Equations: look at the rendered page, not only the extracted text.** pypdf garbles math in both papers (G18's text comes out with `5` for `=`, `2` for `−`, `/C229` for Σ).
- **Numbers: rerun the routines rather than estimating.** See "Check scripts" below.
- **If an answer shows the note is wrong, unclear or incomplete,** say so, propose the edit (or make it, saying so), and keep the Typora rules (`~/.claude/rules/typora-markdown.md`: `\tag`/`\notag` on every `$$` block, narrow equations and tables, no hard-wrapped prose).
- **If a question settles a namelist choice** (flavor, sd floor, lower bound, damping, RTPS), add a dated entry to `notes/dart_namelist_discussion_log.md`. Its inflation entries are dated 2026-10-02, 10-03, 10-15, 10-22 and 10-23 (two on 10-23: run-5 settings, and the pointer to this note).
- **Commit only when the user says so,** on `main`, and only the session's own files.

## What the note contains

| sec. | topic |
|---|---|
| 0–1 | summary; notation with the code's names |
| 2 | where inflation sits in a filter run: read, damp, inflate, H(x), sequential update; cycle recursion |
| 3 | the likelihood shared by both flavors: innovation statistics, γ, removing this cycle's λ from σ_y², linearization |
| 4 | flavor 2: mode quadratic (A09 App. A), step bound, small-step form, sd ratio method |
| 5 | flavor 5: −1/N term, IG conversion (cubic, closed form), mode quadratic, sd update, bounds, deflation |
| 6 | code map, one table per source file |
| 7 | worked numbers: linearization check, one observation, identical-observation runs, constant gain |
| 8 | papers and guide against code |
| 9 | expectations for run 5 (written before the run) |

Main results:
- **Same pipeline, different Bayesian update.** The two flavors share damping, inflating, γ = localization × impact × \|r\| and the bounds. Only the update of one (λ, sd) pair by one observation differs (`bayes_cov_inflate`).
- **Flavor 5 takes smaller steps.** Its mode equation is flavor 2's with σ_λ² replaced by λ²/(α+1), the IG's curvature variance: 0.126 against 0.36 at λ = 1, sd 0.6. So each observation moves λ ~0.35–0.45 times as far. Its −1/N term raises the target by 1/N (0.2 at 5 members).
- **The flavor-2 sd can only shrink; the flavor-5 sd can also grow.** Growth larger than `inf_sd_max_change` per observation is rejected, not clipped, and nothing bounds the sd itself. Either flavor's sd stays fixed when `inf_sd_initial = inf_sd_lower_bound`.
- **A fixed sd floor means λ never settles.** It acts like a constant gain: λ fluctuates by ~σ_λ/√2 around its target, with a memory of ~1/(σ_λ² I) observations.
- **With 5 members, inflation adapts noisily.** E\|r\| = 0.42 even for unrelated variables, and the inflation takes r before the sampling-error correction.
- **Code findings, reproduced with DART's own routines compiled stand-alone:**
  - **Wrong root.** In flavor 5 the "root closest to λ̄" rule picks the wrong root for steep likelihoods (q = ℓ/ℓ′ < 2λ̄/(α+1)) and lowers λ after a large innovation.
  - **Float32 overflow.** Under `r8 = r4`, β^α overflows and flavor 5's sd silently freezes where sd/λ ≲ 0.22–0.27.
  - **Damping acts on λ in the code**, while G18 and the guide's "order of operations" note damp √λ.
  - **A09 differs from the code twice:** A09's γ uses the signed r (the code \|r\|), and A09's sd method may raise the sd, which the code forbids.

## What run 5 showed since (not yet in the note)

Run 5 (2026-10-23, `_conv_refl_f2` against `_conv_refl_f5` with sd floor 0.3, lower bound 1.0) passed. The results are in `notes/obs_expansion.md` Sec. 9, run 5, and `CLAUDE.md` "Current state". The note's Sec. 9 still gives only the expectations from before the run.
- **The flavor-5 sd grew more often than it fell.** For U, V, THM and QVAPOR at 01:00, 16–17 % of the points had sd above 0.6 (max 9–10) and 4–6 % were at the 0.3 floor. MU was 35 % at the floor. This is case 3 of the note's Sec. 9, not the "sd falls where obs are dense" expected beforehand.
- **λ: less on average, a longer tail.** 16,681 U points (0.05 %) were at the cap 5 at 01:00, growing about tenfold per cycle, at model levels 0–64. The fit to observations was nearly the same as flavor 2.
- **Wrong-root candidates are rare.** Radar obs with QC 0, σo²/σp² ≤ 0.2 and d²/(σp²+σo²) > 7 were 0.04–0.11 % of the radar obs, as many as in flavor 2. So the defect exists but hardly matters here.
- **Open, for the user:** which flavor to keep (flavor 2 proposed), RTPS or a longer flavor-5 run, deflation (`inf_lower_bound = 0`, needs a new per-run setting), then the larger ensemble. If the Q&A settles any of these, record it (discussion log, and `obs_expansion.md` if it changes the run plan).

If the user wants it, the note could get a short "what run 5 showed" paragraph in Sec. 9. Ask first.

## How solid each kind of claim is

- **Checked by running DART's routines:**
  - `adaptive_inflate_mod.f90:763–1262` was copied verbatim into a stand-alone module and compiled with our ifort at float32 and float64. That gave the wrong-root table (Sec. 5.3), the float32 freeze table (Sec. 5.4) and the sd update at small sd.
  - A line-by-line Python translation agrees with the compiled routines on every case run in both, and gave the rest of Sec. 7.
- **Checked against exact solutions:** the flavor-2 linearization against the exact posterior mode on a grid (Sec. 7.1); `change_GA_IG` against the cubic (residual 10⁻¹³); the IG-posterior modes in the wrong-root table.
- **Toys (directions, not sizes for WRF):**
  - Sec. 7.3: identical observations at one element, and 2000 random innovations at one element.
  - Sec. 7.4: the constant-gain rule, confirmed for γ = 1 (0.43 against 0.42 and 0.21 against 0.21) but noisier than predicted for γ = 0.5.
  - None of them cycle, damp or re-apply λ.
- **From reading the code only:**
  - λ⁰ of the element being updated stands in for the λ of the whole forward-operator support (Sec. 3.3).
  - The outlier check bounds d²/θ²(λ⁰) ≤ 9 at the start of the cycle's updates (Sec. 3.4).
  - Inflation in "probit space" is the identity with no QCEFF table.
- **From the papers:** G18's derivation of −1/N (its footnote 2 calls the assumption biased); A09's and G18's remarks on radar and on deflation; G18's Lorenz-96 and GCM results.

## Likely questions and where to look

- What γ does and why \|r\|: Sec. 3.2; A09 (9)–(10); G18 (13)–(14); code `adaptive_inflate_mod.f90:729`.
- Why divide σ_y² by s(λ⁰)²: Sec. 3.3; A09 Sec. 3, "second algorithm", step 5b(iii).
- How the mode quadratic comes out, and why the closest root: Sec. 4.1 and 5.3; A09 (A.7)–(A.8); G18 (38).
- Why flavor 5 moves λ less: Sec. 5.3, Eq. (19)–(20) and the τ² column of the table in Sec. 5.2.
- Why the flavor-5 sd grew in run 5: Sec. 5.4 "Why the sd can grow"; Sec. 7.3; `obs_expansion.md` Sec. 9, run 5.
- What the sd floor means in practice: Sec. 7.4 (memory and noise), Sec. 9.
- Damping, λ vs √λ: Sec. 2 and 8; `filter_mod.f90:824–827`; G18 Sec. 3d; the guide's `inf_damping` entry.
- Deflation and `inf_lower_bound`: Sec. 5.5; G18 Sec. 4c and 5; A09 Sec. 5.
- RTPS instead: not in this note. See `dart_eakf.md` Sec. 10–11 (HRRRDAS's RTPS 1.08), WH12 in `notes/papers/`, and `adaptive_inflate_mod.f90:524–596` (`inflate_ens`), `filter_mod.f90:838–841`, `:956–975`.
- Posterior inflation (`inflate_only`): only touched in Sec. 3.3; A09 Sec. 5 and G18's limitations discuss why it is harder.

## Sources at hand

- **Papers:** `notes/papers/` (not in git): A07a (Anderson 2007, adaptive inflation), A09, G18, A+09 (DART 2009), G+25 (DART 2025), WH12, A12 (SEC), A01, A03, GC99 and more.
- **G18's 2017 EnKF-workshop slides** (same algorithm, simpler figures): `https://www.image.ucar.edu/pub/DART/2017/gharamti-enkf-talk.pdf`; not kept locally.
- **Code:** DART `7bbd35a09` (`../software/DART/assimilation_code/modules/assimilation/`); the guide at `../software/DART/guide/inflation.rst`.
- **Run output for run-5 questions:** `cases/20250520/da_theta_m0/output_conv_refl_f2/` and `output_conv_refl_f5/`. The inflation fields are `<t>/filter/{preassim,postassim}_priorinf_{mean,sd}.nc`; the per-cycle summaries are in `check_cycle.log`.
- **Related notes:** `dart_workflow_walkthrough.md`, `mrms_two_pass_inflation.md`, `dart_sampling_error_correction.md`, `dart_eakf.md`.

## Check scripts

In `notes/checks/` (note Sec. 7 describes them):

| script | what |
|---|---|
| `inflation_checks.py` | Python translation of the routines (`update_varying_state_space_inflation`, `update_inflation`, `bayes_cov_inflate` and helpers), double precision; sections 1–10 give the numbers of note Sec. 3.2, 5.2–5.4, 7 and 8 (list at the top of the script) |
| `inflation_fortran_check.sh` | copies `adaptive_inflate_mod.f90:763–1262` from `../software/DART` into a stand-alone module in a temporary directory, compiles it with `inflation_fortran_driver.f90` in float32 (our `r8 = r4`) and float64, runs both |
| `inflation_fortran_driver.f90` | the cases for the compiled routines: the wrong-root table (Sec. 5.3), the sd update at small sd (Sec. 5.4) |

The functions in `inflation_checks.py` can be reused for new worked examples when a question needs one. Add a numbered section rather than a separate script, and give its section number in the note.

Commands:
- Python checks (a few seconds; section numbers run only those): `uv run --no-project --with numpy python -I notes/checks/inflation_checks.py [n ...]`
- Compiled DART routines (a few seconds; sources `scripts/env_wrf.sh` itself): `bash notes/checks/inflation_fortran_check.sh`
- PDF text: `uv run --no-project --with pypdf python -I <script>` (the project `.venv` has no pypdf); keep the text in the session scratchpad.
- PDF page as an image, for equations (`pdftoppm` isn't installed): `uv run --no-project --with pymupdf python -I <script>` with `pymupdf.open(pdf)[page-1].get_pixmap(dpi=170).save(png)`, then read the PNG.

## Starting the session

Name it `learn: inflation Q&A` (it then files into the `learn` group), and name this file in the first prompt (`notes/handoffs/2026-10-27_learn_inflation_qa.md`).
