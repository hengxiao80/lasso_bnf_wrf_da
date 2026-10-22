# Filter (and `wrf.exe`) exit hang

Side investigation started 2026-10-21 from `notes/handoffs/2026-10-21_filter_exit_hang.md` (symptom, every run so
far, environment, hypotheses). Question: which call spins after `filter` prints "Finished ... at", and why; a setting
that stops it with analyses unchanged and no loss of speed; then keep or drop the exit guard and the 512-GB exclusion.

## Facts established (2026-10-21, before any test job)

- **All ranks were alive in every hung step.** In the guard-cancelled steps whose `filter.log` was kept
  (`output_meso_a/*/filter/filter.log`, `output_madis/202505200030`, `output_madis_mrms1p/202505200045`), srun's
  "Killed" lines cover all 1,280 tasks: no rank had exited.
- **After SUCCESS, `wrf.exe` has only `MPI_FINALIZE` left.** `wrf_finalize` closes all I/O (`med_shutdown_io`) before
  it prints "wrf: SUCCESS COMPLETE WRF", then calls `wrf_shutdown` → `wrf_dm_shutdown` → `MPI_FINALIZE`
  (`../software/WRF/main/module_wrf_top.F:2113-2116`, `external/RSL_LITE/module_dm.F:2725`). So the run 3 `wrf.exe`
  hang (member 005, 00:45 → 01:00) was in `MPI_FINALIZE` or the process exit, not in writing output.
- **WRF output writes slowed a little between 10-02/03 and 10-21, but the hung segment's writes were normal.** The
  user reported (2026-10-21) that a colleague saw WRF output slow down recently. From the saved `rsl.error.0000`
  (25 segments per run, 5 members × 5 segments):

  | runs | `wrfout` write, mean / max | `wrfrst` write, mean / max | model step, median |
  |---|---|---|---|
  | step 13 `_hph` (10-02/03) | 6.5 / 6.7 s | 18.5 / 19.2 s | 0.345 s |
  | runs 1–3 (10-21) | 6.8–6.9 / 8.3 s | 19.5–19.6 / 23.6 s | 0.350 s |

  ~5 % slower on average, worst cases ~25 % slower. Member 005's hung segment wrote `wrfout` in 6.8 s and the
  restart in 19.3 s, then printed SUCCESS; the 27 min came after. A common system cause for the slowdown and the
  hangs (fabric or GPFS load since mid-October) is not excluded.
- **MPI stack** (Open MPI 4.0.4, spack build; system packages from MLNX OFED 5.8, installed 09-04): UCX 1.14.0,
  hcoll 4.8.3220, SHARP 3.1.1, pmix 2.2.5. Slurm 25.11.8 with `MpiDefault = pmi2`, so Open MPI uses its `s2`
  (PMI-2) component. No `OMPI_MCA_*`, `UCX_*` or `HCOLL_*` set by the modules; `openmpi-mca-params.conf` empty.
  Defaults that matter: `coll_hcoll_enable = 1`, `coll_hcoll_priority = 90`, `coll_hcoll_np = 2` (hcoll on every
  communicator of 2+ ranks, including DART's duplicate of `MPI_COMM_WORLD` and WRF's); `pml_ucx_priority = 51`;
  `osc_rdma_priority = 101` and `osc_ucx_priority = 60` (which one DART's windows get at run time is not checked;
  without an RDMA-capable BTL, probably `osc ucx`).
- **Where the time could go after "Finished"** (filter): `task_sync` (`MPI_Barrier` on DART's duplicate
  communicator, via hcoll), `MPI_Comm_free` of it (hcoll context destroyed), then `MPI_Finalize`. In Open MPI
  4.0.4, `MPI_Finalize` with a PMI-2 component (no non-blocking fence) does a barrier on `MPI_COMM_WORLD`, a blocking
  PMI-2 fence, frees the communicators and windows, and the UCX PML's `del_procs` (endpoint disconnects, then
  another fence while progressing the UCX worker). A rank in a blocking fence or in the file system would sleep (state
  `S`/`D`); ~99 % CPU means a progress loop.

## Method: stacks without ptrace

`ptrace` is blocked (`kernel.yama.ptrace_scope = 2`), but `perf` only needs the weaker read permission, and
`kernel.perf_event_paranoid = 2` allows user-space sampling of one's own processes. Checked on the login node:
`perf record --call-graph dwarf -p <pid>` gives full stacks (Fortran main → `PMPI_BARRIER` → `opal_progress` →
`ucp_worker_progress` → ...) for an Intel Fortran + Open MPI test program.

- `scripts/da/hang_snapshot.py <outdir> <program>`: run as one task per node next to the hung step (`srun --overlap`).
  Per thread: state, CPU % and context switches over 1 s, kernel wait channel, MPI rank (from `SLURM_PROCID`); then
  perf stacks for 3 s (49 Hz, DWARF), folded per rank and thread. Works for `wrf.exe` too.
- `scripts/da/hang_summary.py <outdir>`: ranks found or missing, states, threads in `D` state with wait channels,
  busy helper threads; main threads grouped by MPI call and shared stack.
- `cases/20250520/da_theta_m0/slurm.filter_exit_test`: the conv replay of `slurm.filter_scaling` (step 13's `_hph`
  00:30 analysis, 3,492 obs) repeated `EXIT_REPEATS` times (default 4) on 40 × 32 with `slurm.cycle`'s shape and
  environment; a step not exited 20 s after "Finished" gets a snapshot on every node and is then cancelled; each
  repeat's analyses compared with step 13's. `EXIT_TEST_ENV` passes settings to the filter step only (for the
  component tests later). Output: `tests/filter_exit/<label>_<job>/rep<N>/`.
  Tested on the login node with stand-ins (normal exit, hang with a real snapshot and cancel, crash).

## Tests

### Job 1054828 (2026-10-21, `base`: current settings, 40 × 32, cirrus1–4, 17–52, 4 repeats)

**Repeat 1 hung, and the snapshot shows where** (`tests/filter_exit/base_1054828/rep1/snapshot_summary.txt`;
perf worked on all 40 nodes):
- All 1,280 ranks alive; every main thread in state `R` at 98–101 % CPU, no voluntary context switches, nothing in
  `D` state (so not the file system).
- **1,279 ranks** are in `MAIN__` → `finalize_mpi_utilities` → `PMPI_FINALIZE` → `ompi_mpi_finalize` →
  `mca_pml_ucx_del_procs` → `opal_common_ucx_mca_pmix_fence` → `ucp_worker_progress`: the last fence of
  `MPI_Finalize`, which waits for every rank. So `task_sync`, `MPI_Comm_free` and the first part of `MPI_Finalize`
  (barrier, fence, freeing the communicators) had completed on them.
- **One rank (576)** is still freeing the communicators: `ompi_attr_delete_impl` → `hcoll_comm_attr_del_fn` →
  `hcoll_context_free` → `hmca_bcol_ucx_p2p_disconnect` → `ucp_worker_progress`. hcoll's own UCX point-to-point
  layer (`bcol ucx_p2p`, a separate UCX context and worker from the PML's) is closing its endpoints
  (`ucp_ep_close_nb`) and waiting for the closes to complete; they never do. Everyone else waits for it in the fence.
- Hot code on all ranks is in `libuct_ib` (UD over the HCA), `ucp_worker_progress`, `pthread_spin_lock`.
- Analyses bit-identical to step 13's.

**Whole job: 2 of 4 repeats hung (1 and 3), 2 exited 1.0 and 0.5 s after "Finished".** All analyses bit-identical
to step 13's. Phases (s, from `filter.log`, 1-s resolution): read 2–3, H(x) 3–4, assimilation 12, rest 11–14 in every
repeat; wall 40–41 s when filter exited. The snapshot step took ~2.7 min (`perf script` unwinding ~5,000 samples per
node).

| repeat | outcome | stuck rank | node |
|---|---|---|---|
| 1 | hung | 576 | cirrus31 |
| 2 | exited 1.0 s after "Finished" | – | – |
| 3 | hung, same stacks; rank 672's full stack: `ompi_mpi_finalize` → `ompi_comm_finalize` → `ompi_attr_delete_all` → `hcoll_comm_attr_del_fn` → `hcoll_context_free` → `hmca_bcol_ucx_p2p_disconnect` | 672 | cirrus34 |
| 4 | exited 0.5 s after "Finished" | – | – |

So the filter hang is **hcoll's teardown in `MPI_Finalize` on one rank**, not DART's barrier, `MPI_Comm_free` or its
one-sided windows. `ompi_comm_finalize` (communicators freed, hcoll contexts with them) runs before the PML's
`del_procs` and its fence, which is where everyone else waits.
- **The stuck rank was each time the first rank on its node** (576 = 18 × 32, 672 = 21 × 32). hcoll is hierarchical:
  ranks on a node share memory, and one leader per node talks to the other nodes over hcoll's own UCX connections.
  So one of the 40 node leaders didn't finish closing its inter-node connections.
- UCX's UD settings: `UCX_UD_TIMEOUT` 30 s and `UCX_UD_LINGER_TIMEOUT` 300 s (defaults); hangs have lasted 4–27 min,
  so the stuck close is not just waiting out a timeout.
- **`wrf.exe`** also tears down hcoll contexts (its communicators) in `MPI_FINALIZE`; the run 3 hang (8 nodes, so 8
  node leaders) fits the same mechanism but had no snapshot.
- **Scale rather than date?** Filter at 8 × 16 (128 ranks, 8 node leaders) never hung on 256-GB nodes (16 steps in
  step 13, job 1054413); every 40-node run (since 10-20) hung often. All 40-node runs are from 10-20 on, so "it started
  in mid-October" and "it happens at 40 nodes" can't be told apart from the record; the 8 × 16 hangs on 10-20 were all
  on the 512-GB nodes.

### Job 1054833 (2026-10-21, `nohcoll`: `OMPI_MCA_coll_hcoll_enable=0` on the filter step, 40 × 32, same nodes, 8 repeats)

**8 of 8 exited**, each 0.5 s after "Finished"; all 40 analyses bit-identical to step 13's (the collective algorithm
doesn't change DART's results here). With hcoll: 2 of 4 hung in job 1054828, 11 of 16 at 40 × 32 in runs 1–3 and the
MRMS scaling test; if the rate were still 1 in 2, 0 of 8 would happen by chance 0.4 % of the time.

Speed, conv case (3,492 obs), s from `filter.log` (1-s resolution):

| | read | H(x) | assimilation | rest | wall (exited steps) |
|---|---|---|---|---|---|
| hcoll on (1054828, 4 repeats) | 2–3 | 3–4 | 12 | 11–14 | 40–41 |
| hcoll off (1054833, 8 repeats) | 2–3 | 7–8 | 13–14 | 10–12 | 40–42 |

H(x) doubles and the observation loop gains 1–2 s, though the step's wall time is about the same. The MRMS pass
(85,551 obs, one `MPI_Bcast` over all ranks per observation) is where the cost could matter; not measured yet.

**hcoll parameters** (`hcoll_info -a` on a compute node, `tests/filter_exit/nohcoll_1054833/hcoll_info.txt`), among
them: `HCOLL_BCOL = basesmuma,basesmuma,ucx_p2p`, `HCOLL_SBGP = basesmsocket,basesmuma,p2p` (shared memory within a
socket and a node, hcoll's own UCX between node leaders); **`HCOLL_BCOL_UCX_P2P_PRECONNECT_NP = 1024`, "Preconnect UCX
endpoints up to <int> ranks during hcoll_init"**: at 1,280 ranks filter is above it, so hcoll opens its UCX connections
on first use, while at 128 ranks (step 13's filter, never hung on 256-GB nodes) it connects everything at start. A
connection left half-made at teardown is a plausible thing for the disconnect to wait on. It doesn't explain the rare
hangs at 128 ranks (`wrf.exe` in run 3; filter on the 512-GB nodes). Also `HCOLL_ENABLE_MCAST = 2` (IB multicast),
`HCOLL_ENABLE_SHARP = 0`, `HCOLL_FINALIZE_CTX_CLEANUP = 0`.

`slurm.filter_exit_test` now also has `EXIT_CASE=mrms` (the MRMS scaling test's 40x32:283x144 config, with its
analyses as the reference) and `EXIT_VARIANTS` (settings taken in turn over the repeats, for comparisons on the same
nodes in one job); the snapshot samples less (2 s at 29 Hz) to take ~1 min instead of ~2.7.

### Job 1054839 (2026-10-21, `mrms3`: MRMS case, 40 × 32, cirrus2–4, 17–53, 9 repeats, 3 settings in turn)

The MRMS scaling test's 40x32:283x144 config replayed (85,551 radar obs, run 1's priors at 00:15, its `input.nml`).
All 45 analyses bit-identical to that test's (job 1054799, hcoll on). Seconds, from `filter.log` (1-s resolution) and
the step's wall time:

| setting | repeats | outcome | wall (exited) | read | H(x) | assimilation | ms/ob | rest |
|---|---|---|---|---|---|---|---|---|
| hcoll on (as now) | 1, 4, 7 | **1 of 3 hung** (4) | 54, 53 | 3–4 | 8–9 | 12–13 | 0.14–0.15 | 18–19 |
| `OMPI_MCA_coll_hcoll_enable=0` | 2, 5, 8 | 0 of 3 | 51, 52, 52 | 4 | 9–10 | 14–15 | 0.16–0.18 | 17–18 |
| `HCOLL_BCOL_UCX_P2P_PRECONNECT_NP=2048` | 3, 6, 9 | 0 of 3 | 55, 55, 55 | 3 | 8 | 13 | 0.15 | 18–19 |

- **Repeat 4's hang has the same signature**: rank 1024 (first rank on cirrus46) in `ompi_comm_finalize` →
  `hcoll_comm_attr_del_fn` → `hcoll_context_free` → `hmca_bcol_ucx_p2p_disconnect`, 1,279 ranks in the final fence.
  Three hangs, three different node leaders (cirrus31, 34, 46): not one bad node.
- **Speed with hcoll off**: the observation loop is ~1.5 s slower (~10 %), but the step's wall time is 1–2 s *shorter*
  (no hcoll setup at start and teardown at the end), as in the conv case (40–42 s against 40–41 s).
- Preconnect: no hang in 3, but hcoll on hung only 1 in 3 here, so 3 repeats say little; the step is ~1–2 s slower
  (connections made at start).

## Summary and recommendation (2026-10-21)

**Cause.** At the end of `MPI_Finalize`, one rank (each time the first rank on its node, i.e. an hcoll node leader)
never finishes closing hcoll's own UCX connections to the other nodes (`hcoll_context_free` →
`hmca_bcol_ucx_p2p_disconnect`), and all other ranks wait for it in the last fence. Not DART (its barrier,
`MPI_Comm_free` and one-sided windows complete), not the file system, not one node. Why the close never completes
is inside hcoll 4.8 / UCX 1.14 (not open to inspection); hcoll opening its connections lazily above 1,024 ranks is a
candidate for why 40-node filters hang so often.

**Fix for filter: `OMPI_MCA_coll_hcoll_enable=0` on the filter step.** With hcoll off, 0 hangs in 11 runs at 40 × 32
(8 conv, 3 MRMS); with it on, 3 of 7 in these tests and 11 of 16 before. Analyses bit-identical; step wall time the
same or 1–2 s shorter. Simpler than tuning hcoll (preconnect is untested beyond 3 runs and costs 1–2 s).

## Changes made (user's decisions, 2026-10-21; no run going; not committed yet)

- **Filter with hcoll off**: `run_filter` (`scripts/da/cycle_lib.sh`) launches filter as
  `env OMPI_MCA_coll_hcoll_enable=0 srun ...` (cycle and `slurm.filter_scaling`). Stand-in test: the setting reaches
  the program, normal exit unchanged.
- **Filter exit guard kept** as a safety net (unchanged).
- **512-GB nodes allowed again**: `--exclude` removed from `slurm.cycle`, `slurm.filter_scaling` and
  `slurm.filter_exit_test`.
- **`wrf.exe` exit guard** in `scripts/da/run_wrf_segment.sh` (used by `advance_member.sh` and the restart and
  boundary tests): `wrf.exe` runs in the background as a step named `wrf.exe_<member>_<pid>`; once SUCCESS is in
  `rsl.out.0000`, it gets `WRF_EXIT_GRACE` s (30) to exit; if it hasn't and no rsl, wrfout or wrfrst file has
  changed for 30 s, `hang_snapshot.py` runs on that step's nodes (into `hang_snapshot/`, summary
  `hang_snapshot_summary.txt`; `WRF_HANG_SNAPSHOT=0` skips it), the step is cancelled (srun killed 60 s later if
  needed), the segment counts as complete, a line "wrf exit guard: ..." is logged and `wrf_exit_guard.txt` written.
  "wrf.exe finished, N s" says "(exit guard fired)" when it did. Stand-in test on the login node (fake srun,
  squeue, scancel, scontrol, `wrf.exe`): normal exit, exit 5 s after SUCCESS (no firing), hang (fired ~30 s after
  SUCCESS, snapshot taken, step cancelled, status 0, 38 s in all), crash (fails as before).
- `CLAUDE.md`'s gotcha rewritten (cause, fix, tools).

### Job 1054907 (2026-10-21, `slurm.wrf_hcoll_test`: `wrf.exe` with hcoll on and off, 8 nodes cirrus1–4, 17–20)

Run 1's (`_madis`) member 001 segment 01:15 → 01:30 (its `wrfrst` at 01:15, the last restart kept, and its 01:00
refit `wrfbdy`, copied first; the 1-hour runs end with the advance 01:00 → 01:15), 4 times through the new
`run_wrf_segment.sh` as a cycling member (16 × 8 ranks × 8 threads), hcoll on, off, on, off. Seconds; WRF's timings
from `rsl.error.0000`; exit = SUCCESS to the end of `run_wrf_segment.sh` (polled every 2 s):

| repeat | hcoll | wall | exit | start-up | 180 steps | wrfout | wrfrst | vs repeat 1 |
|---|---|---|---|---|---|---|---|---|
| 1 | on | 152 | 1 | 35.9 | 76.3 | 8.2 | 23.3 | reference |
| 2 | off | 172 | 1 | 35.6 | 99.5 | 8.2 | 23.4 | wrfout, wrfrst identical |
| 3 | on | 150 | 1 | 35.7 | 75.7 | 8.3 | 23.2 | wrfout, wrfrst identical |
| 4 | off | 173 | 1 | 35.8 | 98.8 | 8.2 | 23.4 | wrfout, wrfrst identical |

- **Outputs byte-identical** in all four: WRF is reproducible run to run (3 vs 1), and hcoll doesn't change it.
- **hcoll off makes `wrf.exe` ~30 % slower in the integration** (76 → 99 s for the 180 steps, ~0.13 s per step;
  +20 s per segment, 151 → 172 s); start-up and writes unchanged. Not analysed further (WRF's per-step collectives).
- No hang in the 4 (expected: 1 `wrf.exe` hang in ~190 segments so far). The guard's step lookup worked in the real
  job (steps named `wrf.exe_rep<N>_<pid>`); it didn't need to fire.
- Writes today were slower than in earlier runs on other nodes (wrfout 8.2 s and wrfrst 23.3 s against 6.5–6.9 and
  18.5–19.6 s); one more data point for the colleague's output slowdown, not analysed.

**So for `wrf.exe`, hcoll stays on**: hcoll off would cost ~20 s in every segment, while the guard costs ~1–2 min
(30 s wait, snapshot, cancel) in the rare segment that hangs (~1 in 190 so far), and takes a snapshot when it does.
