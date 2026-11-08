# Hand-off: "fulltest: initial setup part 3"

Written 2026-11-07 at the end of session "fulltest: initial setup part 2". Everything from that session is committed and pushed (A2 `f84c658`, A3 `8f36090`, A4 `61a6935`, then A5 and A6 with the notes and this hand-off); check `git status`. No jobs running.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20). Read `CLAUDE.md` first, then `notes/fulltest_steps.md` (Sec. 0 scope, Sec. 1 steps with every result of this session).

## Where things stand

Part A (inputs) is complete for the 1-h gate. Experiment directory `cases/20250520/da_theta_m0_n50/`; shared inputs in `da_common_theta_m0/`.

- **A2** `da_theta_m0_n50/config/`: `experiment.sh` (`NUM_ENS=50`, `BDY_RECORDS=2`), `input.nml.filter_joint` (`ens_size` and `num_output_*` 50), `obs_impact_joint.txt`, `namelist.input.wrf`, `iofields_cycle.txt` (the last two unchanged so far, B1 changes them). One-pass files only. The configs that make shared inputs (`namelist.input.real`, `namelist.input.3dvar`, `input.nml.obs_preprocess`, `iofields_real.txt`) live in `da_common_theta_m0/config/`, linked into both experiments.
- **A3** bank of 150 WRFDA draws in `da_common_theta_m0/perts/bank/` (36 GB), checked by `scripts/da/check_bank.py`; `wrfvar_output` files deleted (draws are reproducible bit for bit with 16 ranks).
- **A4** `GRID_FILE` is the plain mean 00Z `wrfinput`, into which `real.exe` now writes `REFL_10CM` (`iofields_real.txt`); `make_grid_file.py` and the `dart_wrfinput` file are gone.
- **A5** 50 initial members `run/mem001…050/wrfinput_d01` (61 GB), perturbations `perts/members/` (15 GB), assignment in `perts/assignment.txt` and `config/assignment.txt`. `assign_perturbations.py` and `make_initial_members.py` now handle one member at a time (bit-identical to the pilot on its case).
- **A6** member boundaries `bdy/wrfbdy_d01_mem001…050`, 32 records each (05-20 00Z to 05-21 07Z, ~4.1 GB), 228 GB with the mean subset and the zero-perturbation refit. **Decided (user): option A with 2-record copies**: each cycle's refit copy holds only the record of the analysis time and the next one, extracted by `scripts/da/subset_bdy.py` inside `refit_member_bdy.sh` when its 4th argument (`BDY_RECORDS`, passed by `post_filter.sh`) is > 0; the 5-member experiment leaves it unset (whole-file copy). Build job 1194808 and check job 1194825 passed (details and numbers in `fulltest_steps.md` A6). The extraction is tested on the login node only; **its first use in a cycle is B3**.
- **A7** moved (user): the first hour's four analyses are already in `obs_meso_a_calmkeep_mrms/`; the other 116 (01:15 to 05-21 06:00) are made alongside Parts B–C or before D2 (20 of them before the 6-h gate).

## Proposed job structure (B2), not decided

Written into `fulltest_steps.md` B2, C1, C2 and Sec. 0 Layout (user agreed to record it as the proposal). Run 5 timings per member and cycle: prior extraction ~85 s, update (insert, `qnrain`, extraction, refit) 97–147 s, each as a one-node `srun` step; WRF segment 127–135 s on 8 nodes (member 1 at 00:30: restart read 22 s, 180 steps 72 s, boundary read 3 s, `wrfout` 6 s, restart write 18 s). A member job holding 8 nodes through all of it would use them for WRF only ~35–40 % of the time. Proposal: the **filter job** (40 nodes) does extraction of all members → filter → insert and refit for all members → submits the **WRF array** (one task per member, `wrf.exe` only) → next filter job (`afterany`). Still two jobs per cycle. Settled by **C1** (WRF on 1, 2, 4, 8 nodes: node-time per segment, members per wave; 50 × 8 = 400 nodes > 116) and **C2** (how many members' Python steps a node can run side by side). The user said they think 8 nodes per member; the reasons to measure anyway are in C1. The user sets the order of B and C.

## Next steps (each with the user's go-ahead)

1. **B1, output settings** (`fulltest_output_files.md` Sec. 1): `write_hist_at_0h_rst = .true.` in the 50-member `namelist.input.wrf` (`history_interval` stays 15); keep the start-of-segment `wrfout`, delete the end-of-segment one; drop `iofields_filename`, `ignore_iofields_warning` and the copy of `iofields_cycle.txt` for the 50-member experiment only. `run_wrf_segment.sh` copies `config/iofields_cycle.txt` unconditionally and is shared with the 5-member experiment, whose namelist still names it: make the copy depend on the namelist (as `make_mean_icbc.sh` does for `iofields_real.txt`).
2. **B2, job structure**: decide with the user whether C1/C2 come first. A small test job first: whether `sbatch` works from a compute node. Each job type keeps its MPI settings (WRF: `UCX_TLS=self,sm,ud`, hcoll on, exit guard; filter: `slurm.cycle`'s shape and `OMP_*` settings, hcoll off, exit guard). Resumable from the last complete cycle; stops at the run's end time.
3. **B3**, test of the chain (form to agree, e.g. the 00:00 advance and the 00:15 analysis on a few members): the first cycle with `BDY_RECORDS=2`.

## Facts found this session

- **Login nodes: 32 GB per user** (cgroup; the OOM killer stops the largest process), and files in `/tmp` (tmpfs, incl. the scratchpad) count against it. Netcdf4-python keeps a chunk cache per variable until the file closes: a wrfbdy read in full reached 15–17 GB, 100 open files 26 GB. Use one file at a time and `set_var_chunk_cache(size=0)` where chunks are read once; `OMP_NUM_THREADS=1` for numpy on the login node. (`CLAUDE.md` gotcha.)
- **Claude Code ends a session's background commands on `/exit`** (A5's first try was killed). Long login-node runs go detached (`setsid nohup bash -c '…' > log 2>&1 < /dev/null &`), with a separate watcher.
- **Python in batch jobs buffers stdout**: a job cut off at its limit loses everything. Use `python -u` or `flush=True` (`check_member_bdy.py` does now).
- **Slurm QOS outage (2026-11-07, ~04:00–15:10):** every `cli120` submission failed with "Invalid qos specification" because the user's association had lost its default QOS (`sacctmgr show assoc account=cli120 user=hengxiao80` showed an empty QOS); it came back on its own or by the user's request. Check that first if it recurs.
- Compute nodes (`batch_all`) have the same CPU as the login node (AMD EPYC 7713, 2 × 64 cores).
- `pert_wrf_bc` reads and writes only the record matching its state time; segments link the boundary file (`run_wrf_segment.sh`), so the cold start reads the 32-record pristine file directly.
- The observation scripts (`make_cycle_obs.sh`, `make_cycle_mesonet.sh`, `download_mrms.sh`) still source the 5-member `experiment.sh` through the `da_theta_m0` link and write into the shared sets; that is intended.

## Working rules

- **No quantitative guesses** (times, memory, data volumes, job limits): derive from a measured run of the same script, show the basis, or say "unknown" and measure first. Never put a guessed number into a script (project memory `no-unfounded-estimates`; the A6 check's guessed 2-h limit wasted a run).
- **Status lines before tool calls are full sentences** that say what is done, on what and why (shared rule `~/.claude/rules/answer-style.md`, updated in `claude_config` commit `5b56b81`, not pushed).
- Jobs: the user's go-ahead before every `sbatch`; one step at a time; report each result. Commits only after the user has reviewed and said so; on `main`, only the session's own files; push only when asked.
- Don't change files a running job uses. Notes per `~/.claude/rules/typora-markdown.md` (no hard-wrapped prose; editing a hard-wrapped note means unwrapping all its prose, as done for `obs_expansion.md`). No LaTeX in chat.
- Environment: `source scripts/env_wrf.sh` before DART or WRF tools; Python is `.venv/bin/python`; `ls` is aliased with `-F` (use `command ls` or `find`).

## Starting the session

Name it `fulltest: initial setup part 3`, and name this file in the first prompt (`notes/handoffs/2026-11-07_fulltest_initial_setup_part_3.md`).
