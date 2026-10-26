# Hand-off: "learn: EAKF in DART": a detailed walk-through of the EAKF's theory, math and implementation

Written 2026-10-25 at the end of session "DART workflow review" (DART workflow walk-through, sampling-error correction note, paper references). Commit `bfe7568` has the notes from that session; this hand-off comes in the commit after it if the user agreed; check `git status`. The PDFs in `notes/` stay untracked. No jobs running.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup, 5-member pilot, 50 members planned). Read `CLAUDE.md` first.

## The task

A detailed walk-through of the **theory, math and implementation of the EAKF in DART**, as a note in `notes/` (suggested name `notes/dart_eakf.md`, next to `dart_adaptive_inflation.md` and `dart_sampling_error_correction.md`).

**The user will give detailed instructions at the start of the session on what they need. Wait for them before writing.** Reading the papers and the code beforehand is fine.

## What already exists (link to it, don't repeat it)

- `notes/dart_workflow_walkthrough.md`:
  - Sec. 2: filter's order of operations, with `filter_mod.f90` line numbers.
  - Sec. 3: the sequential observation loop (`assim_tools_mod.f90:585–836`). The rank that owns an observation broadcasts its prior H(x) ensemble and QC; **every rank then computes the same observation increment itself**; each state element gets `final_factor` × regression × increment; then the λ update and `OBS_UPDATE` of the observations not yet used.
  - Sec. 5: the forward operators.
- `notes/dart_sampling_error_correction.md`: the regression step (A03 (6), A12 (1)–(2)), and the sampling-error correction that multiplies it.
- `notes/dart_adaptive_inflation.md`: inflation flavors 2 and 5, and where inflation sits in filter.
- `notes/dart_namelist_discussion_log.md`: namelist decisions, with dated entries. Add an entry if the session settles a namelist question.

## Papers in `notes/` (PDFs, untracked)

| label | paper | for the EAKF note |
|---|---|---|
| A01 | Anderson (2001), MWR 129, 2884–2903 | the EAKF itself |
| A03 | Anderson (2003), MWR 131, 634–642 | two steps: observation increment, then regression |
| A+09 | Anderson et al. (2009), BAMS 90, 1283–1296 | DART overview |
| G+25 | Gharamti et al. (2025), BAMS, E2328ff | DART overview, current |
| GC99 | Gaspari and Cohn (1999), QJRMS 125, 723–757 | localization, Eq. (4.10) |
| A07b | Anderson (2007b), Physica D 230, 99–111 | localization and sampling error |
| A12 | Anderson (2012), MWR 140, 2359–2371 | sampling-error correction |
| A07a | Anderson (2007a), Tellus 59A, 210–224 | inflation |
| A09 | Anderson (2009), Tellus 61A, 72–83 | inflation |
| G18 | El Gharamti (2018), MWR 146, 623–640 | inflation, flavor 5 |

The labels are those of the two theory notes (A07a and A07b as in A09's reference list).

**Not in `notes/`:** the QCEFF papers, which DART's guide cites for the generalization of the EAKF that the current code is built on (`guide/important-capabilities-dart.rst`, refs. 11–13):
- Anderson (2022), "A quantile-conserving ensemble filter framework. Part I: Updating an observed variable", MWR 150, 1061–1074, doi:10.1175/MWR-D-21-0229.1.
- Anderson (2023), "... Part II: Regression of observation increments in a probit and probability integral transformed space", MWR 151, 2759–2777, doi:10.1175/MWR-D-23-0065.1.
- Anderson et al. (2024), "... Part III: Data assimilation for mixed distributions ...", MWR 152, 2111–2127, doi:10.1175/MWR-D-23-0255.1.

Ask the user whether they want them, if the note covers more than the plain EAKF.

## Code map (DART `7bbd35a09`, `../software/DART/assimilation_code/modules/assimilation/`)

`assim_tools_mod.f90`:
- `filter_assim` `:309`, with the sequential loop at `:585–836`.
- `obs_increment` `:912`: picks the method per observation type through `obs_inc_info` (`algorithm_info_mod.f90`). Our `qceff_table_filename = ''`, so every type gets the defaults: EAKF, with normal distributions, i.e. the probit transform is the identity (`dart_adaptive_inflation.md` Sec. 2, step 3).
- `obs_increment_eakf` `:1113–1133`: `var_ratio = obs_var/(prior_var + obs_var)`, `new_mean = var_ratio*(prior_mean + prior_var*obs/obs_var)`, `a = sqrt(var_ratio)`, `obs_inc = a*(ens - prior_mean) + new_mean - ens`.
- The other methods in the same file, for comparison: `obs_increment_enkf` `:1307`, `obs_increment_rank_histogram` `:1635`, `obs_increment_bounded_norm_rhf` `:1136`, `obs_increment_kernel` `:1385`, `obs_increment_particle` `:1238`, `obs_increment_gamma` `:1071`.
- `update_from_obs_inc` `:1472`: regression, with the sampling-error correction at `:1534`.
- `obs_updates_ens` `:2005`.

Elsewhere:
- `cov_cutoff_mod.f90`: the Gaspari–Cohn weight (GC99 Eq. (4.10)).
- `filter_mod.f90`: the steps around `filter_assim` (walk-through Sec. 2).
- **Precision:** our DART has `r8 = r4` (`types_mod.f90:85`), so all of this runs in float32.

Our settings (`cases/20250520/da_theta_m0/config/input.nml.filter`, `input.nml.filter_joint`):
- `&assim_tools_nml`: `cutoff = 0.0235` (weight 0 at 300 km; the radar types use a smaller one in the joint file); `sort_obs_inc = .false.`; `spread_restoration = .false.`; `sampling_error_correction = .true.`.
- `&algorithm_info_nml`: `qceff_table_filename = ''`.

## How the two theory notes were written

- **Opening:**
  - A **Sources** list: labelled papers with full references and whether the PDF is in `notes/`, the code paths with the DART commit, and where checked numbers come from.
  - **Related notes**, and the Typora line about inline math.
- **Body:**
  - Sec. 0, a summary; Sec. 1, a notation table with the code's variable names.
  - The math, with the papers' equation numbers ("A01 (n)").
  - The implementation, step by step, with line numbers.
  - A "paper against code" section.
  - Worked numbers for our settings (N = 5 and N = 50).
  - What it means for our runs.
- **Checking:** the numbers were checked by re-implementing the routines (Python, and DART's Fortran compiled stand-alone with our ifort).
- **PDF text:** the project `.venv` has no `pypdf`. Use `uv run --no-project --with pypdf python -I <script>` and keep the extracted text in the session scratchpad.
- **Format:** the Typora rules in `~/.claude/rules/typora-markdown.md` (loaded automatically) apply:
  - `\tag`/`\notag` on every `$$` block;
  - narrow equations and tables;
  - no hard-wrapped prose;
  - ASCII diagrams of at most 72 characters.
- **Commits:** only when the user says so, on `main`.

## Starting the session

Name it `learn: EAKF in DART` (it then files into the `learn` group), and name this file in the first prompt (`notes/handoffs/2026-10-25_learn_eakf_in_dart.md`). The session index matches a hand-off to a session by its title only for names without a colon, so here the link comes from the first prompt.
