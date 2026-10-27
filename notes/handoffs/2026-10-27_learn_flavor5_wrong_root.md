# Hand-off: "learn: flavor-5 wrong root": the wrong root in DART's flavor-5 inflation update

Written 2026-10-27 during session "learn: inflation Q&A", which goes on with the Q&A on `notes/dart_adaptive_inflation.md` (this is a branch off it). No jobs running.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0` setup, 5-member pilot, 50 members planned). Read `CLAUDE.md` first, then `notes/dart_adaptive_inflation.md` Sec. 3.5, 4.1, 5.2 and 5.3.

## The task

**Look into the wrong-root problem of flavor 5** (note Sec. 5.3). What the user wants from it is open: ask at the start. Possible directions:
1. **Understand it fully:** when it happens, why the root rule fails, whether flavor 2 can ever fail the same way.
2. **A correct root rule:** test it against the exact posterior mode and against DART's own pick in all ordinary cases (see "Found since the note" below for a candidate).
3. **How often it matters in our runs:** run 5 counted only candidate observations (below), not actual wrong-root updates of (observation, element) pairs.
4. **A patch** to `adaptive_inflate_mod.f90` (`patches/`, with `patches/README.md`), and possibly a report upstream.
5. **Whether it changes the flavor decision** (flavor 2 is proposed; the choice is the user's).

## What the note already has (Sec. 5.3)

- **Mode equation:** flavor 5's new $\lambda$ solves the quadratic (18) (G18 (38); code `:1169–1171`), or in $\delta = \lambda - \bar\lambda$ form (19). The derivation is written out step by step since this session (log-derivative, clearing denominators, prior's mode).
- **The code's rule:** take the root closest to $\bar\lambda$ (`enh_linear_bayes`, `adaptive_inflate_mod.f90:1176–1181`), kept from flavor 2's `linear_bayes` (`:1109–1114`). A root $\le 0$ or NaN keeps $\bar\lambda$ (`:1188–1189`).
- **When it fails:** for $0 < q < 2\bar\lambda/(\alpha+1)$, i.e. a steep, rising likelihood (threshold 0.25 at $\bar\lambda = 1$, $\sigma_\lambda = 0.6$). The closer root then lies where the linearized likelihood $\ell + \ell'\delta$ is negative.
- **Reproduced with DART's routines compiled stand-alone** (float32 and float64): $\sigma_p^2 = 1$, $\sigma_o^2 = 0.2$, $\gamma = 1$, $\bar\lambda = 1$, $\sigma_\lambda = 0.6$, $N = 5$. At $d^2/(\sigma_y^2+\sigma_o^2)$ = 8, 9, 12, DART gives 0.6315, 0.6469, 0.6748 against exact modes 1.508, 1.579, 1.792.
- **Threshold table:** the innovation ratio above which the wrong root is taken, against $\sigma_o^2/\sigma_p^2$, for $\sigma_\lambda$ = 0.6 and 0.3 (6.3–9.8 and 12.7–20.3). The outlier check passes ratios up to 9.
- **Effects:** with `inf_lower_bound = 1` and $\bar\lambda = 1$ the push is lost; with $\bar\lambda > 1$, $\lambda$ goes down; with a lower bound of 0 it would deflate.
- **Sec. 8 item 6:** G18's claim that the IG needs no positivity check, against this.

## Found since the note (in the Q&A session, not yet in the note)

**A candidate rule: take the root with the sign of $q$**, as flavor 2's rule effectively does. Sketch, to be checked and written up:
- With $c = \bar\lambda/\beta = 1/(\alpha+1)$, (18) in $\delta$ is $(1-c)\,\delta^2 + (q - 2c\bar\lambda)\,\delta - c\,\bar\lambda^2 = 0$.
- The roots have opposite signs (product $-c\bar\lambda^2/(1-c) < 0$). The one closer to 0 has the sign of $q - 2c\bar\lambda$, which is why the rule fails for $0 < q < 2c\bar\lambda$.
- The quadratic at $\delta = -q$ equals $-c\,(q-\bar\lambda)^2 \le 0$, so $-q$ always lies between the roots. Where $\ell + \ell'\delta > 0$ is $\delta > -q$ for $q > 0$ and $\delta < -q$ for $q < 0$. So the valid root is always the one with the sign of $q$, and the other is always spurious.
- Checked numerically on the note's cases (scratch script, not in the repo): the value at $-q$ matches $-c(q-1)^2$, and the sign-of-$q$ root gives 1.3901, 1.4072, 1.4420 at ratios 8, 9, 12 (exact modes 1.508, 1.579, 1.792; the rest is linearization error). At ratios 4 and 6 it is DART's own pick (1.2532, 1.3406).
- Edge case: $q = \bar\lambda$ makes $-q$ a root, where the posterior is zero.

## Run-5 numbers (`notes/obs_expansion.md` Sec. 9, run 5)

- **Candidates:** radar observations with DART QC 0, $\sigma_o^2/\sigma_p^2 \le 0.2$ and $d^2/(\sigma_p^2+\sigma_o^2) > 7$: 19 / 32 / 55 at 00:30 / 00:45 / 01:00 in `_conv_refl_f5` (0.04–0.11 % of the radar observations), and 24 / 30 / 49 in `_conv_refl_f2`. The defect exists but hardly matters here, at least while it's counted this way.
- **Output:** `cases/20250520/da_theta_m0/output_conv_refl_f5/` and `output_conv_refl_f2/`; inflation fields `<t>/filter/{preassim,postassim}_priorinf_{mean,sd}.nc`, observations `<t>/filter/obs_seq.final`, summaries in `check_cycle.log`.

## Tools

- **Python translation** of the update: `notes/checks/inflation_checks.py`. Section 8 is the wrong-root table; reuse its functions (`enh_linear_bayes`, `lik_and_deriv`, `change_GA_IG`, `update_varying`). New checks go in as a new numbered section (11 is the next free one; the Q&A session may also want 11 for a perfect-ensemble toy, so agree on numbers with the user). Run: `uv run --no-project --with numpy python -I notes/checks/inflation_checks.py [n ...]`.
- **DART's own routines compiled stand-alone:** `bash notes/checks/inflation_fortran_check.sh` copies `adaptive_inflate_mod.f90:763–1262` from `../software/DART`, compiles with `inflation_fortran_driver.f90` at float32 (our `r8 = r4`) and float64. A patched routine can be tested the same way before touching the real build.
- **Papers:** `notes/papers/` (A09 Appendix A, G18 Sec. 3). Read equations from the rendered page (pymupdf; command in `notes/handoffs/2026-10-27_learn_inflation_qa.md`), not from extracted text.
- **Upstream:** the local DART clone (`../software/DART`) has no commits after `7bbd35a09`. Whether a later upstream version changed `enh_linear_bayes` hasn't been checked.

## Rules for this session

- **Two sessions share the inflation note.** The Q&A session keeps editing `notes/dart_adaptive_inflation.md`. Put this work in Sec. 5.3 (and Sec. 8) only, or in a separate note with a pointer from Sec. 5.3; tell the user before larger edits. Commit only this session's own files and hunks.
- **Patches and builds:** a DART change goes in `patches/` with a README entry; rebuilding filter changes the software outside the repo (`software_lock.json`). Ask first.
- **Outward-facing steps** (a GitHub issue or PR upstream): only with the user's go-ahead.
- **Jobs:** none without the user's go-ahead.
- **Namelist choices** (flavor, bounds): dated entry in `notes/dart_namelist_discussion_log.md`.
- **Writing for the user:** derivations go in the Markdown note (the user reads it in Typora or VS Code; LaTeX in terminal replies is unreadable to them). Typora rules: `\tag`/`\notag` on every `$$` block, narrow equations and tables, no hard-wrapped prose, and `$$` blocks inside a list item indented under it.
- **Commit** only when the user says so, on `main`.

## Starting the session

Name it `learn: flavor-5 wrong root` (it files into the `learn` group), and name this file in the first prompt (`notes/handoffs/2026-10-27_learn_flavor5_wrong_root.md`).
