# 50-member DA workflow: layout, jobs and files (D1 setup)

Written 2026-11-08 in session "fulltest: initial setup part 4", after B3 and the tidy-up of the experiment directory, for the 1-h production run D1 (`fulltest_steps.md` D1). It describes the setup as it is, in the place of `da_workflow_layout.md`, the plan of 2026-09-25, which stays as it was written. Companion notes: `da_cycle_file_flow.md` (which script makes or changes each member file, step by step), `fulltest_output_files.md` (what a cycle keeps, with sizes), `fulltest_steps.md` (how each choice was reached; the section names below, A1–D1, are its steps).

What differs from the 2026-09-25 plan:

- **Restarts**: members continue from true WRF restarts (`wrfrst`), not from `wrfout` with extra `iofields`. DART works on a small file extracted from the restart (`wrfrst_dart.py extract`), and the analysis is inserted back into it (`insert`).
- **Boundaries**: each member has a pristine boundary file built once from perturbed hourly states (`build_member_bdy.py`, patched `pert_wrf_bc`); each cycle refits a 2-record copy of it to the analysis (patched `update_wrf_bc`).
- **Jobs**: no driver on a login node. Two jobs per cycle, a WRF array and a filter job, and each filter job submits the next two (`chain_submit.sh`). The 5-member runs used one allocation per cycle (`slurm.cycle` → `driver.sh` → `cycle_job.sh`), still in the code.
- **Observations**: MADIS conventional observations, mesonet and MRMS reflectivity, assimilated in one filter pass.
- **Not written, not needed**: `setup_experiment.sh`, `gen_pert_bank.sh`, `mean_increment.py`.

## 1. Directory layout

Reusable scripts are tracked in `scripts/da/`, each experiment's configuration and job scripts in its directory (`.gitignore` allows `config/*`, `slurm.*`, `setup/slurm.*`, `tests/slurm.*`); data and logs are not tracked. Executables are used in place from `../software`. Layout of the 50-member experiment since 2026-11-08 (`fulltest_steps.md` A1):

```
cases/20250520/
|-- da_common_theta_m0/      inputs shared by the theta_m0 experiments
|   |-- config/              files that make the shared inputs
|   |-- mean/                hourly mean wrfinput (GRID_FILE), wrfbdy
|   |-- perts/bank/, work/   WRFDA draws (150)
|   `-- obs*/<t>/            observation sets, one directory per time
`-- da_theta_m0_n50/         the 50-member experiment
    |-- config/              experiment.sh, namelists, filter files
    |-- mean, obs*           links into da_common_theta_m0/
    |-- perts/               members/, assignment.txt; bank, work
    |-- init/                initial members memNNN/wrfinput_d01
    |-- bdy/                 pristine boundaries wrfbdy_d01_memNNN
    |-- slurm.wrf_member     the WRF array of a cycle
    |-- slurm.filter_step    the filter job of a cycle
    |-- setup/               job scripts that built the inputs, logs/
    |-- tests/               test job scripts, logs/, kept results
    |-- run_<name>/          a run's working files (Sec. 1.1)
    `-- output_<name>/       a run's saved output (Sec. 1.2)
```

Every run has a name (`RUN_NAME`, e.g. `_d1`; `chain_submit.sh` refuses an empty one), and all runs start from the same `init/` and `bdy/`. The 5-member experiment `da_theta_m0_n5/` has the older layout: initial members in `run/`, which was also its first run's directory, and job scripts and logs at its top.

### 1.1 A run's working files

Replaced cycle by cycle; only the latest state is kept. 826 GB in B3 (769 GiB).

```
run_<name>/
|-- memNNN/
|   |-- wrfrst_d01_<t>       the member's latest restart (13.1 GB)
|   |-- dart_d01.nc          DART-facing extract; filter updates it
|   |-- start_d01.nc         extract of the updated restart (refit)
|   |-- bdy/                 refit copy wrfbdy_d01 (2 records), logs
|   `-- wrf/                 WRF's run directory: links, tables, rsl
`-- filter/                  filter's run directory, rebuilt per cycle
```

### 1.2 A run's saved output

One directory per cycle; cycle t is the analysis at t (none at 00:00) and the advance from t to t + 15 min. B3: 551 GB for an analysis cycle, 198 GB for the 00:00 cold start, as written (`fulltest_output_files.md` Sec. 3).

```
output_<name>/
|-- settings.txt             the run's settings; a resume must match
|-- chain.log                every submission of the chain
`-- <t>/
    |-- status               running, then complete
    |-- cycle.log            log of the filter job F(t)
    |-- slurm.filter_step.<job>.out
    |-- filter.done, filter/ filter's output files and inflation
    |-- check_cycle.log      the check of cycle t, written by F(t + 15)
    |-- retries              only if members were retried
    `-- memNNN/
        |-- prior_d01.nc, analysis_d01.nc, insert.log,
        |   wrfbdy_d01, update_wrf_bc.log, update.done      F(t)
        `-- wrfout_d01_<t>, rsl.*.0000, namelist.input,
            cfl_count.txt, slurm.wrf_member.*.out,
            advance.done                                    A(t)
```

The run's last job, F(last + 15), writes its log into `<last>/`.

## 2. Jobs

### 2.1 The chain

```
login node: chain_submit.sh <experiment.sh> <first> <last>
  |
  v
A(00:00)  WRF array: 50 tasks x 2 nodes, at most 40 at once
  |  afterany
  v
F(00:15)  filter job, 40 nodes:
  |         1. A(00:00) all advanced? (else one retry)
  |         2. check_cycle.py of 00:00 in the background
  |         3. extraction (2 per node) -> filter -> save
  |         4. the check's result (failed: stop)
  |         5. qnrain, insert, extraction, refit (2 per node)
  |         6. chain_submit.sh: A(00:15) afterok F(00:15),
  |                             F(00:30) afterany A(00:15)
  v
A(00:15) -> F(00:30) -> ... -> A(last)
  |
  v
F(last + 15)  1 node: A(last) all advanced? its check; stop
```

- **WRF array A(t)** (`slurm.wrf_member`, job name `n50w<name>`): one task per member not yet advanced, `--array=<members>%40`. Each task runs `advance_member.sh` → `run_wrf_segment.sh` → `wrf.exe` on 2 nodes, 8 × 4 ranks × 8 threads (16 ranks per node, `-c 8`, threads bound to cores), hcoll on, `UCX_TLS=self,sm,ud`, with an exit guard for a hang after `SUCCESS`. Job shape 16 tasks × 8 CPUs per node, `--exclusive`.
- **Filter job F(t)** (`slurm.filter_step` → `filter_step.sh`, job name `n50f<name>`): 40 nodes, job shape and `OMP_*` settings of the 5-member `slurm.cycle` (16 × 8 per node; a job shaped 128 × 1 without the `OMP_*` settings made filter's observation loop 27 % slower, `CLAUDE.md`). Filter runs 32 ranks of 1 CPU per node with hcoll off and its own exit guard. The per-member steps run as 1-node `srun` steps with 64 CPUs each (`env -u SLURM_CPUS_PER_TASK`, so srun doesn't warn), at most 2 per node. `check_cycle.py` of cycle t − 15 runs in 8 processes on the first node, beside the extraction and filter.
- **Dependencies**: A(t) waits until F(t) has ended successfully (`afterok`), so the two never hold nodes at the same time; F(t + 15) waits until A(t) has ended in any state (`afterany`), and then looks for each member's `advance.done`. At most 80 nodes are in use at a time.
- **Time limits**: 30 min for both (D1; B3's longest: WRF task 6:14, filter job 6:19).

### 2.2 Measured times (B3, 2026-11-08)

| part | B3 |
|---|---|
| WRF segment, one member | 308–370 s |
| WRF array (29, then 21 at once)¹ | 10.6–11.0 min |
| filter job F(00:15) | 6.3 min |
| – prior extraction | 22 s |
| – filter, 40 × 32 | 187 s |
| – member updates | ~168 s |
| `check_cycle.py`, 8 processes² | 80 s |
| cycle, without queue waits | ~17 min |

¹ 59 nodes were free; with 80 free, 40 members would run at once, then 10 (not measured). ² On the login node, on B3's 00:15 cycle (474 s in B3 with the old serial script); not yet measured beside filter.

## 3. Running

The production run is one continuous run, `_conv_refl_f2` (user, 2026-11-09), stopped at each gate D1–D4 (`fulltest_steps.md` Part D). D1 is started from the repository root; with `--dry-run` added, the command prints the `sbatch` commands and writes nothing:

```
RUN_NAME=_conv_refl_f2 OBS_NAME=_meso_a_calmkeep_mrms \
  MRMS_FILTER=one_pass scripts/da/chain_submit.sh \
  cases/20250520/da_theta_m0_n50/config/experiment.sh \
  202505200000 202505200100
```

Each later gate is the same command with the next first and last analysis times (D2: `202505200115 202505200600`).

- **What `chain_submit.sh` checks first**: a non-empty `RUN_NAME`; `run_preflight` (`cycle_lib.sh`): observation files for every analysis time, the cycle before `<first>` complete, and the settings against `output_<name>/settings.txt` (written on the first start); no job of the run already queued or running.
- **What it submits**: from the markers of the first cycle t0 ≥ `<first>` not `complete`: every member advanced → F(t0 + 15); analysis done or t0 = 00:00, some members not advanced → A(t0) for those members and F(t0 + 15) after it; otherwise F(t0).
- **Resume**: the same command; it continues from the markers.
- **Failures**: a WRF task that fails leaves no `advance.done`; the next F job resubmits A for the missing members and a new F once per cycle (`<t>/retries`), then stops. A failed filter, member update or check stops the chain; nothing more is submitted.
- **Stop by hand**: `scancel` the jobs named `n50f<name>` and `n50w<name>`; the start command resumes.
- **Settings recorded per run** (`settings.txt`): `HYDROSTATIC_PH`, `INF_DAMPING`, `INF_FLAVOR` (and `INF_SD_LOWER_BOUND` when not 0.6), the observation set and its contents, `MRMS_FILTER`. Run 5 `_conv_refl_f2`, the reference for D1: `hydrostatic_ph=1 inf_damping=0.9 inf_flavor=2 obs=obs_meso_a_calmkeep_mrms mesonet=a_calmkeep mrms=hrrrdas mrms_filter=one_pass`.

## 4. Settings

In `config/experiment.sh` (resources are not recorded in `settings.txt`; the analyses don't depend on them):

- `NUM_ENS=50`, `FIRST_CYCLE=202505200000`, `CYCLE_MINUTES=15`.
- WRF: `MEMBER_NODES=2`, `NPROC_X=8`, `NPROC_Y=4` (C1), `MEMBER_MAX=40` (80 nodes; user), `WRF_TASK_TIME=00:30:00`.
- Filter job: `FILTER_NODES=40`, `FILTER_TASKS_PER_NODE=32` (C3), `MEMBER_STEP_CPUS=64` (C2), `CHECK_WORKERS=8`, `FILTER_JOB_TIME=00:30:00`.
- `BDY_RECORDS=2` (A6), `HYDROSTATIC_PH=1`, `INF_FLAVOR=2`, `INF_DAMPING=0.9`, `INF_SD_LOWER_BOUND=0.6`.
- `GRID_FILE`: the mean 00Z `wrfinput`, with `REFL_10CM` (A4).

`config/namelist.input.wrf`: 550 × 390 × 150 at 2.5 km, `time_step = 5`, `hybrid_opt = 0`, `use_theta_m = 0`, `mp_physics = 28` (Thompson aerosol-aware), `spec_bdy_width = 10` (1 + 4 zone, `CLAUDE.md`), `history_interval = 15` with `write_hist_at_0h_rst = .true.` and WRF's default history stream (B1), restarts every 15 min, classic netCDF, `nocolons`. `nproc_x`, `nproc_y` and the restart interval are filled in per segment.

`config/input.nml.filter_joint`: run 5's one-pass namelist with `ens_size = 50` and `num_output_state_members = num_output_obs_members = 50` (A2); impact table `config/obs_impact_joint.txt`; `outlier_threshold = 3`.

## 5. Inventory

### 5.1 Executables (`../software`)

- `wrf.exe` (WRF 4.8, patched so `REFL_10CM` is in the restart file); `real.exe` (mean states, setup only).
- DART: `filter`, `fill_inflation_restart` (first analysis only), `update_wrf_bc` (patched: hydrometeor and aerosol boundaries, record shift), `pert_wrf_bc` (same patch; setup only); every DART program built with `r8 = r4`. Sampling-error-correction table from `gen_sampling_err_table/work`.
- WRFDA `da_wrfvar.exe` with `be.dat.cv3` (perturbation bank; setup only).
- Patches and their reasons: `patches/README.md`.

### 5.2 Configuration (tracked)

- `da_theta_m0_n50/config/`: `experiment.sh`, `namelist.input.wrf`, `input.nml.filter_joint`, `obs_impact_joint.txt`, `assignment.txt` (copy of `perts/assignment.txt`).
- Links to `da_common_theta_m0/config/`: `namelist.input.real`, `iofields_real.txt`, `namelist.input.3dvar`, `input.nml.obs_preprocess`.

### 5.3 Scripts (`scripts/da/`)

- **Chain**: `chain_submit.sh`; `cycle_lib.sh` (time helpers, `run_preflight`, `filter_pass`, `run_filter`).
- **A(t)**: `advance_member.sh` → `run_wrf_segment.sh` (on a hang: `hang_snapshot.py`, `hang_summary.py`).
- **F(t)**: `filter_step.sh` → `prep_filter.sh` (`wrfrst_dart.py extract`; `fill_inflation_restart` at the first analysis), `run_filter`, `post_filter.sh save` and `members` (`wrfrst_dart.py qnrain`, `insert`, `extract`; `refit_member_bdy.sh` → `subset_bdy.py`, `update_wrf_bc`); `check_cycle.py` (with `check_filter_gate.py` and `restart_increment_test.py`).
- **Inputs, done once** (job scripts in `setup/`): `make_mean_icbc.sh`; `run_wrfda_draw.sh`, `wrfda_bank_diff.py`, `check_wrfda_draw.py`, `check_bank.py`; `assign_perturbations.py`, `make_initial_members.py` (`--init-subdir init`), `check_hydrostatic_balance.py`; `build_member_bdy.py`, `check_member_bdy.py`.
- **Observations, before a run** (shared sets in `da_common_theta_m0/obs*/`): `make_cycle_obs.sh`, `convert_madis_hour.sh`, `make_cycle_mesonet.sh`, `select_mesonet_cycle.py`, `download_mrms.sh`, `mrms_to_obs_seq.py`; `make_obs_loop.sh` runs `download_mrms.sh` and `make_cycle_obs.sh` over a range of times (detached, login node), `check_cycle_obs.py` checks a set's times (A7).
- **5-member only**: `driver.sh`, `cycle_job.sh` (with `slurm.cycle`).
- **Diagnostics after a run** (read `obs_seq.final`; not part of the chain): `innovation_stats.py` (pooled), `obs_space_stats.py` (per cycle and pooled, one run or two; since 2026-11-13), `refl_innovation_split.py` (since 2026-11-13); definitions in `fulltest_d1_analysis.md` Sec. 3.1.

### 5.4 Inputs (measured 2026-11-08; GB = 10⁹ bytes)

| what | size |
|---|---|
| `mean/` (shared) | 95.4 GB |
| `perts/bank/` (shared) | 38.3 GB |
| `perts/members/` | 15.5 GB |
| `init/`, 50 × 1.30 GB | 64.8 GB |
| `bdy/`¹ | 244.3 GB |
| observations 00:15–01:00 | 0.1 GB |

¹ 50 member files of 4.75 GB, the 32-record mean subset and the zero-perturbation refit A6 checked the tools with (4.13 GB each; no cycle reads either).

## 6. Before and after D1

- Observations exist for 00:15–01:00 only; D2 needs 01:15–06:00 (A7).
- `summarize_cycle_timing.py` reads the 5-member `cycle.log`; the chain's logs are split over `cycle.log`, `chain.log` and the WRF tasks' Slurm output (E2).
- Not measured yet: 40 WRF members at once; the 50-member filter at 00:30–01:00; the check beside filter on a compute node.
- The target configuration (`use_theta_m = 1`, `hybrid_opt = 2`, 1 + 9 zone) comes with a separate work package (`fulltest_steps.md` Sec. 2).
