# Hand-off: "Filter exit hang" (branched off "Adding more obs part 7")

Written 2026-10-21 during session "Adding more obs part 7", which is running the 1-hour runs 1–4 of
`notes/obs_expansion.md` Sec. 9 and keeps going in parallel. This session is a side investigation: **why DART's
`filter` sometimes doesn't exit after it has finished**, and whether there is a fix better than the exit guard.

Repo: `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` (WRF-DART for LASSO BNF, case 2025-05-20, `theta_m0`).
- Read `CLAUDE.md` first (Gotchas: the filter exit hang, filter job shape).
- Background: `notes/obs_expansion.md` Sec. 9, the paragraphs "First scaling test (job 1054410)", "Scaling test,
  `conv` (job 1054411)", "Diagnostic (job 1054413)" and "Decisions (user, 2026-10-20)".
- The guard: `run_filter` in `scripts/da/cycle_lib.sh` (lines ~47–91).

## The symptom

`filter` writes every output, prints "Finished ... at" in `filter.log`, and then all ranks keep spinning at ~99 % CPU
and the `srun` step never ends. Outputs are complete and correct (analyses bit-identical to runs that exited).
`ptrace` is not permitted on the compute nodes, so no gdb or py-spy stacks (tried 2026-10-20).

Where it must be: "Finished ... at" is printed by `finalize_utilities`, called from `finalize_mpi_utilities`
(`../software/DART/assimilation_code/modules/utilities/mpi_utilities_mod.f90:348`), which then runs, in this order:
`task_sync()` (an `MPI_Barrier` on DART's private communicator), `MPI_Comm_free(my_local_comm)` and
`MPI_Finalize`. Which of the three spins is not known.

DART's `filter` here is built with `mpi_utilities_mod.f90` (`use mpi`) and `win_mod.f90`
(`../software/DART/models/wrf/work/quickbuild_fp_precise.log`). `win_mod.f90` uses MPI one-sided communication:
`mpi_win_create` on the state copies and the mean (lines 81, 119), passive-target `mpi_win_lock(MPI_LOCK_SHARED, ...)`
in `get_state` (`mpi_utilities_mod.f90:1893, 1918`), `mpi_win_free` (lines 153, 169). This is a lead, not a finding.

## Every multi-node and gate filter run so far

All with the same `filter` binary (built 2026-10-01, DART v11.25.3 `7bbd35a09` + local patches, `-fp-model precise`).
"Hung" = still running after "Finished" (cancelled by hand or by the guard). 512-GB nodes: cirrus57–64, 121–128;
all others 256 GB.

| date | job.step | layout (nodes × ranks/node) | nodes | 512-GB nodes in step | outcome |
|---|---|---|---|---|---|
| 10-02 | 1047795.1, 1047796.1/.3, 1047801.1/.3/.5 (step 11 gate) | 1 × 128 | cirrus63 | yes (single node) | exited (1047795.1 cancelled after 9 s for another reason) |
| 10-02/03 | 1047814, 1047842, 1047843, 1047844 (step 13), steps .11/.27/.43/.59 each | 8 × 16 | within cirrus77–116 | no | all 16 exited |
| 10-20 | 1054410.0 | 8 × 16 (job shaped 128 × 1, no `OMP_*`) | cirrus61–68 | yes | **hung** |
| 10-20 | 1054411.0 / .1 / .2 | 8 × 16 / 40 × 16 / 40 × 32 | cirrus61–68 / 61–100 / 61–100 | yes | **all 3 hung** (guard) |
| 10-20 | 1054413.0 | 8 × 16 | cirrus49–56 | no | exited |
| 10-21 | 1054795.6 (run 1, 00:15) | 40 × 32 | cirrus1–4, 17–52 | no | exited (57 s) |
| 10-21 | 1054795.22 (run 1, 00:30) | 40 × 32 | same nodes | no | **hung** (guard, 30 s after "Finished") |
| 10-21 | 1054795.38 (run 1, 00:45) | 40 × 32 | same nodes | no | exited |
| 10-21 | 1054795.54 (run 1, 01:00) | 40 × 32 | same nodes | no | exited |
| 10-21 | 1054799.0–.3 (MRMS scaling test: 40x32, 40x32:283x144, 40x64, 40x64:283x144) | 40 × 32, 40 × 64 | cirrus1–4, 17–52 | no | **all 4 hung** (guard) |
| 10-21 | 1054801.11/.27/.43/.59 (run 2, 00:15–01:00) | 40 × 32 | cirrus1–4, 17–52 | no | **all 4 hung** (guard) |
| 10-21 | run 3 `_madis_mrms1p` (job 1054809): 00:15 / 00:30 / 00:45 / 01:00 | 40 × 32 | cirrus1–4, 17–52 | no | exited / **hung** / **hung** / exited |

**`wrf.exe` hangs too (2026-10-21, run 3, job 1054809).** Member 005's segment 00:45 → 01:00 (step 1054809.51, 8 nodes
cirrus34–41, 16 × 8 ranks × 8 threads) printed "SUCCESS COMPLETE WRF" at 14:37:22 EDT and wrote complete `wrfout`
and `wrfrst` (same size as the other members'), then the step kept running; cancelled by hand at 15:04:50 (27 min
later), after which the cycle went on normally (`run_wrf_segment.sh` runs `srun ... || true` and judges success by
the SUCCESS line). The other four members exited normally. This is the first `wrf.exe` hang seen; ~170 cycling
`wrf.exe` steps exited normally before (step 13: 100, runs 1–2: 50, run 3: 19), besides the long WRF runs. WRF uses no MPI one-sided
communication, so DART's windows (`win_mod.f90`) can't be the whole story; common to both programs: Open MPI 4.0.4
with UCX 1.14 and hcoll, the same `UCX_TLS=self,sm,ud` and `UCX_UD_MLX5_RX_QUEUE_LEN=16384`, Slurm 25.11.8. Not checked
whether the ranks were spinning (no `top` taken). `wrf.exe` has no exit guard; the cycle scripts would need one.

What this says:
- **The 512-GB-node explanation is refuted** by 1054795.22: it hung on 256-GB nodes only, on the same nodes where
  .6 and .38 exited. `slurm.cycle` and `slurm.filter_scaling` still `--exclude` those nodes; whether to keep that
  is for the user to decide after this investigation.
- **It is intermittent**: same nodes, same binary, same layout, different outcome from one cycle to the next.
- **Time:** 0 hangs in 21 runs on 10-02/03, 15 hangs in 21 multi-node filter runs since 10-20 (the MRMS test and run 2: 8 of 8; run 3: 2 of 4), and one `wrf.exe` hang (below). Between them: `slurmd` was
  restarted on all nodes 2026-10-14 09:20 (reason unknown); no library changes found (Open MPI 2021 build, UCX
  1.14 2024-12, Slurm 25.11.8 and MLNX OFED 5.8 installed 09-04, same kernel; `obs_expansion.md` Sec. 9). Only
  single-node runs before 10-20 used a 512-GB node.
- **Not the job shape alone**: hung with 128 × 1 per node without `OMP_*` (1054410) and with 16 × 8 with `OMP_*`.
- Not checked: whether hung steps used more nodes than ever before (step 13 used 8; 1054411.1/.2 and run 1 use 40).
  1054411.0 and 1054410.0 hung on 8 nodes, though.
- One number: sacct MaxRSS of 1054795.22 was 1.99 GB, of .6 0.40 GB and of .38 (see sacct). Probably sampling
  (the hung step lived longer), not checked.

## Environment of the filter step

- Modules (`scripts/env_wrf.sh`): intel/20.0.4, openmpi/4.0.4, netcdf-wrf/0.1, hdf5, jasper. Open MPI 4.0.4 is built
  `--with-ucx=/usr` (UCX 1.14.0), `--with-hcoll=/opt/mellanox/hcoll`, `--with-ofi` (libfabric 1.8.0), `--with-pmi=/usr`,
  `--with-slurm`; components include pml ucx/ob1/cm, osc ucx/rdma/pt2pt/sm, btl self/tcp/vader. `filter` links
  `libhcoll`, `libucp`, `libucs`.
- Job (`cases/20250520/da_theta_m0/slurm.cycle`): `--nodes=40 --ntasks-per-node=16 --cpus-per-task=8 --exclusive`,
  `UCX_TLS=self,sm,ud`, `UCX_UD_MLX5_RX_QUEUE_LEN=16384` (wrf.exe's settings, also used for filter),
  `OMP_NUM_THREADS=8`, `OMP_PLACES=cores`, `OMP_PROC_BIND=true`, `OMP_STACKSIZE=64000000`, `ulimit -s 64000000`.
- Filter step (`scripts/da/cycle_job.sh:42`): `srun -N ${FILTER_NODES} -n $((FILTER_NODES*FILTER_TASKS_PER_NODE))
  --ntasks-per-node=${FILTER_TASKS_PER_NODE} -c 1 --exact .../filter` (40 × 32 now). Slurm 25.11.8.

## Ideas to test (none tried; hypotheses only)

1. Which call spins: e.g. a rebuilt `filter` (in a separate copy, never in `models/wrf/work`) that prints a timestamp
   per rank before `task_sync`, `MPI_Comm_free` and `MPI_Finalize`, or a small MPI test program reproducing DART's
   pattern (`mpi_win_create`, shared `mpi_win_lock`/`mpi_get`/unlock from many ranks, `mpi_win_free`, barrier,
   `MPI_Comm_free`, `MPI_Finalize`) at 40 × 32.
2. Open MPI component choices, one at a time, through environment variables on the filter step: one-sided
   `OMPI_MCA_osc` (e.g. `pt2pt` or `rdma` instead of `ucx`), `OMPI_MCA_coll_hcoll_enable=0`, explicit
   `OMPI_MCA_pml=ucx`, other `UCX_TLS` for filter only (e.g. adding `rc`). Check first which components are
   selected now (`OMPI_MCA_osc_base_verbose`, `OMPI_MCA_pml_base_verbose`). Any change must keep the analyses
   bit-identical (`scripts/da/compare_dart_members.py`) and the speed (observation loop ~10 s at 40 × 32 for 3,492 obs).
3. What spins: while a step hangs, `srun --overlap --jobid=<job> -w <node> top -H -b -n 1` (threads: main thread,
   UCX or hcoll progress threads?) and `/proc/<pid>/task/*/stat`, `/proc/<pid>/status` if readable without ptrace.
4. Because it is intermittent (~1 in 3 recently), one test needs several repeats. A replay costs ~1 min per filter at
   40 × 32 (the conv case of `slurm.filter_scaling`: step 13's `_hph` 00:30 priors, 3,492 obs, reference analyses).

## Rules for this session

- **Don't change anything the running runs use.** The other session is running runs 1–4 with `slurm.cycle` (40
  nodes each) and then the MRMS scaling test with `slurm.filter_scaling`. Do not edit, while that work goes on:
  `scripts/da/{driver,cycle_job,prep_filter,post_filter,advance_member,cycle_lib}.sh`, `scripts/da/check_cycle.py`,
  `scripts/da/wrfrst_dart.py`, `cases/20250520/da_theta_m0/config/*`, `slurm.cycle`, `slurm.filter_scaling`, the
  `run*/`, `output*/`, `obs*/` and `mean/` directories, or `../software/DART/models/wrf/work/`. Each cycle re-reads
  the scripts, so an edit takes effect mid-run. Work in new files: e.g. `cases/20250520/da_theta_m0/slurm.filter_exit_test`
  (copy `slurm.filter_scaling`'s shape and environment), `cases/20250520/da_theta_m0/tests/filter_exit/`, and a note
  `notes/filter_exit_hang.md`. A fix found here goes into `slurm.cycle` / `cycle_lib.sh` between runs, by agreement
  with the user.
- `slurm.filter_scaling` deletes and recreates `tests/filter_scaling/<case>_<t>/` on each submission; don't use its
  directories.
- **Nodes:** the other session's runs take 40 nodes; `batch_all` has ~100 more 256-GB nodes. Keep tests small where
  the question allows (8 nodes reproduced the hang).
- **Jobs:** the user's go-ahead before every `sbatch`; one step at a time, report each result; `sbatch --test-only`
  checks a script without queuing it. Slurm reports `COMPLETED` even when `srun` was killed: read the logs.
- **Environment:** `source scripts/env_wrf.sh` before DART tools; Python is `.venv/bin/python` (`uv`, 3.11); `ls` is
  aliased with `-F` (use `command ls` or `find` in scripts).
- **Locations:** never modify `sey/`; external repos in `../software/` (one per system, full clones).
- **Git:** both sessions commit on `main`. Commit only when the user decides, and only this session's own files
  (`git add <paths>`, never `git add -A` or `commit -a`); messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Record findings in `notes/filter_exit_hang.md` as they come; the other session records run results in
  `obs_expansion.md` Sec. 9, so don't edit that section.

## Goal

Find which call hangs and why, or at least a setting that makes it stop, with analyses unchanged and no loss of
speed. Then a recommendation for the user: keep or drop the exit guard, keep or drop the 512-GB exclusion.
