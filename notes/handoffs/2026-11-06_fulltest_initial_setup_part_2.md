# Hand-off: "fulltest: initial setup part 2"

Written 2026-11-06 at the end of session "fulltest: initial setup". This hand-off is in the same commit as the session's notes and the directory change; check `git status`. No jobs running.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20). Read `CLAUDE.md` first, then `notes/fulltest_steps.md`.

## Where things stand

- **Scope of the 50-member full test agreed with the user** and written up in `notes/fulltest_steps.md` Sec. 0: 05-20 00Z cold start, 15-min cycles, gates at 1, 6, 12 and 30 h (to 05-21 06Z; the 500-m LES window is 05-20 12Z to 05-21 05Z); `theta_m0`, `hybrid_opt = 0`, 1 + 4 boundary zone; other settings as run 5 `_conv_refl_f2`, inflation flavor 2; no free spin-up; 150 bank draws, boundary option A; per-cycle member job array plus a filter job that submits the next cycle; the existing `theta_m0` free run as control.
- **Moved to a separate work package before the production DA runs** (user): moist theta (`use_theta_m = 1`), the hybrid coordinate (`hybrid_opt = 2`) and the 1 + 9 boundary zone (`fulltest_steps.md` Sec. 2). Q18's plan of 1 + 9 for the 50-member DA is reversed; `CLAUDE.md` and the Q18 row now say so.
- **Step list:** `notes/fulltest_steps.md` Sec. 1, Parts A (inputs) to E. **A1 is done** (below); the next step is **A2**.
- **Retention decided** for the 1-h and 6-h gates: `notes/fulltest_output_files.md` (everything per cycle, incl. all 50 members' `preassim`/`postassim` files; ~360 GB per cycle, ~1.6 TB for 1 h, ~8.8 TB for 6 h; thinning decided at the 6-h gate). Not yet implemented (step B1): `write_hist_at_0h_rst = .true.` with the end-of-segment `wrfout` deleted, `history_interval` kept at 15 (the history alarm makes Thompson compute `REFL_10CM` for the restart), the 65 `iofields_cycle.txt` fields dropped, `num_output_state_members = num_output_obs_members = 50`.
- **New note on the current workflow:** `notes/da_cycle_file_flow.md`, diagrams of every file the scripts create, change or read for a member's state, from the mean states to the next restart.

## The directory layout (A1, done 2026-11-06)

In `cases/20250520/`:

- `da_common_theta_m0/`: inputs shared by the `theta_m0` experiments: `mean/`, `perts/bank/`, `perts/work/`, the five `obs*/` sets.
- `da_theta_m0_n5/`: the 5-member experiment, renamed from `da_theta_m0`; **`da_theta_m0` is now a link to it**, so old paths resolve. It links the common inputs back in (`mean`, `obs*`, `perts/bank`, `perts/work`); `EXP_DIR` in its `experiment.sh` names `da_theta_m0_n5`.
- `da_theta_m0_n50/`: the full test; so far only those links (its own `perts/` holds the `bank` and `work` links).

Checked: contents identical through old and new paths; `experiment.sh` paths and paths recorded in finished runs resolve. 83 broken links in `da_theta_m0_n5/` predate the move (links to per-cycle files the workflow deletes). Details: `fulltest_steps.md` A1, `CLAUDE.md` Layout.

## Next steps, in order (each with the user's go-ahead)

1. **A2:** `da_theta_m0_n50/config/` (copied from `da_theta_m0_n5/config/`, then changed) and a grep for 5-member assumptions (`NUM_ENS`, `ens_size`, `num_output_*`, `--nmem`/`--hours` defaults, `slurm.cycle`, `tasks_per_node`). The 5-member experiment must keep working with the shared scripts. `make_cycle_obs.sh`, `make_cycle_mesonet.sh` and `download_mrms.sh` source `da_theta_m0/config/experiment.sh` by absolute path; that still works through the link and writes into the common observation sets.
2. **A3:** bank draws 16–150 (`slurm.pert_draw` array; 16 ranks per draw for reproducibility). Needs `sbatch`: ask first.
3. **A4:** the `GRID_FILE` clean-up, before the members (user): `real.exe` writes `REFL_10CM` itself; steps in `fulltest_steps.md` A4.
4. **A5–A7:** 50 initial members; member boundaries; observations for 120 analyses. **A6 has a design point to settle first:** a member boundary file with all 31 records is ~4.5 GB, and today each cycle copies, refits, reads and saves the whole file (~220 GB written and ~220 GB kept per cycle at 50 members). Proposal: one-record files per hour; test whether WRF needs the next record for the segment ending on the hour.
5. Then Parts B (output settings, job scripts), C (measurements: WRF on 1–8 nodes, the Python steps, filter at 50 members), D (the gated runs).

## Facts found this session worth keeping in mind

- **Filter's `wrfinput_d01` is `GRID_FILE`**, linked in by `prep_filter.sh`; filter and `fill_inflation_restart` read it for the grid and as the template for every state variable. `make_cycle_obs.sh` sets its own `GRID_FILE` (the plain mean 00Z `wrfinput`).
- **`R/dart_d01.nc` and `R/start_d01.nc`** are replaced every cycle; `analysis_d01.nc` is filter's output (T still the prior THM, DART's PH), not the state WRF starts from; `postassim_member_*` is the only per-member record of the analyzed `NO_COPY_BACK` fields and the unclamped moisture.
- **`batch_all`:** 116 nodes; priority by queue age only, counted from eligibility; no per-user limits. All 40-node jobs of 10-20 to 10-23 started within a second.
- **Storage:** quota for `/gpfs/wolf2/arm/cli120` unknown (the user doesn't know; OLCF's docs give 50 TB, 90-day purge, no backups for standard Open project areas, but not this path). Plan without one and show totals at each gate. The older 5-member runs and `tests/` are kept.
- **Not used for the full test:** `notes/da_workflow_layout.md` (the 2026-09-25 plan, outdated, left as is; a new layout note is step E1).

## Working rules

- **Jobs:** the user's go-ahead before every `sbatch`; one step at a time; report each result. A full-size run is a production run: confirm before it, even after a successful test.
- **Commits:** only after the user has reviewed the changes and said so; on `main`, only the session's own files; commits end with `Co-Authored-By: Claude ...`. Push only when asked.
- **Don't change files a running job uses,** nor `GRID_FILE` during a run.
- **Notes:** decisions and results as they come, in `fulltest_steps.md` (Sec. 3 log) and the notes it points to. Typora rules (`~/.claude/rules/typora-markdown.md`): no hard-wrapped prose, narrow tables, diagram lines ≤ 72 characters of plain ASCII. No LaTeX in chat.
- **Environment:** `source scripts/env_wrf.sh` before DART or WRF tools; Python is `.venv/bin/python`; `ls` is aliased with `-F` (use `command ls` or `find`).

## Starting the session

Name it `fulltest: initial setup part 2`, and name this file in the first prompt (`notes/handoffs/2026-11-06_fulltest_initial_setup_part_2.md`).
