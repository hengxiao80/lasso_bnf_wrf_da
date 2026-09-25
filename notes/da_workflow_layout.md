# DA workflow template: directory layout and file inventory

Written 2026-09-25 as the plan for setting up the template WRF-DART cycling workflow for case
`20250520` (`theta_m0`: `hybrid_opt = 0`, `use_theta_m = 0`). The observation side is left out for now:
converters, `obs_seq.out`, forward-operator settings, localization cutoffs and obs diagnostics. It builds
on the decisions in `wrf_dart_tutorial_adaptation.md`:
- 2.11: members restart from their own `wrfout`, with `iofields` adding the missing fields.
- 2.12: precomputed member boundary files, and `update_wrf_bc` before each 15-min segment.
- 2.7: the `THM` patch.

Execution model (from `prompts/software_management.md`): the workflow **driver runs on a login node**
and submits Slurm jobs. For cycling, that means one Slurm allocation per cycle, which runs the members
as packed `srun` steps and then `filter`. The driver waits for it, checks the results, and moves on. This
replaces the "Slurm job chain" suggestion in note 2.1.

Status legend:
- **ready**: exists and works as is.
- **patch**: existing upstream code that needs a local patch (recorded in `patches/`) and a rebuild.
- **adapt**: start from a tutorial script or file and rewrite for our setup.
- **modify**: start from one of our existing files.
- **new**: write from scratch.
- **generated**: a data product that a script creates.
- **deferred**: observation side, not in this round.

## 1. Directory layout

Principle, following CLAUDE.md: reusable scripts are tracked in `scripts/da/`; per-experiment
configuration is tracked in the experiment directory's `config/`; everything large is untracked
(`.gitignore` allowlist gets entries for `config/`). Executables are linked in from `../software`, never
copied.

```
bnf_wrf_da/
├── scripts/
│   ├── env_wrf.sh                     modify  (+ nco module for the few NCO calls)
│   └── da/                            new directory, tracked, generic across cases
│       ├── setup_experiment.sh        adapt   (tutorial setup.sh)
│       ├── make_mean_icbc.sh          adapt   (tutorial gen_retro_icbc.sh → hourly real.exe loop)
│       ├── gen_pert_bank.sh           adapt   (tutorial gen_pert_bank.sh → Slurm array)
│       ├── wrfda_bank_diff.py         new     (bank file = WRFDA output − fg, replaces ncdiff step)
│       ├── assign_perturbations.py    new     (fixed member → bank draws, seed, centering record)
│       ├── make_initial_members.py    new     (replaces add_bank_perts.ncl + init_ensemble_var.sh IC part)
│       ├── build_member_bdy.py        new     (per-member 72-h wrfbdy files, note 2.12)
│       ├── advance_member.sh          adapt   (new_advance_model.sh + first_advance.sh + assim_advance.sh)
│       ├── cycle_job.sh               new     (one Slurm allocation: packed srun members, then filter)
│       ├── driver.sh                  adapt   (tutorial driver.sh; login node, 15-min, resumable)
│       ├── prep_filter.sh             adapt   (tutorial prep_ic.sh + parts of driver.sh)
│       ├── post_filter.sh             adapt   (driver.sh post_da_diags, inflation file handoff)
│       ├── mean_increment.py          new     (port of mean_increment.ncl)
│       └── check_cycle.py             new     (per-cycle health checks: files, times, SUCCESS, NaNs)
├── patches/
│   ├── dart_update_wrf_bc_thm.patch            new   (read THM for T_B*, note 2.7)
│   └── dart_update_wrf_bc_untouched_fields.patch  new  (advance B of fields it doesn't recompute, note 2.6)
└── cases/20250520/
    ├── wps/, theta_m0/, ...           existing (met_em files are the input to make_mean_icbc.sh)
    └── da_theta_m0/                   new experiment directory
        ├── config/                    tracked
        │   ├── experiment.sh          new     (replaces tutorial param.sh: paths, NUM_ENS, times, resources)
        │   ├── input.nml              modify  (from dart/mmc/input.nml + tutorial template)
        │   ├── namelist.input.real    modify  (from theta_m0 real namelist, 1-h windows)
        │   ├── namelist.input.wrf     modify  (from theta_m0 namelist.input, 900-s member segments)
        │   ├── namelist.input.3dvar   adapt   (tutorial template_nest, rebuilt for our grid)
        │   └── iofields_cycle.txt     new     (+:h:0: the 65 fields, note 2.11)
        ├── mean/                      generated: hourly wrfinput_d01 (73) + wrfbdy_d01 (72 h)
        ├── perts/
        │   ├── bank/                  generated: pert_bank_NNN.nc (150)
        │   ├── work/                  scratch for da_wrfvar.exe runs
        │   └── assignment.txt         generated: member → bank draw, seed (tracked copy in config/)
        ├── bdy/                       generated: wrfbdy_d01_memNNN (50 × 9.3 GB ≈ 460 GB)
        ├── run/                       working area
        │   ├── bin/                   links: filter, advance_time, fill_inflation_restart,
        │   │                                 update_wrf_bc, wrf.exe, real.exe, da_wrfvar.exe
        │   ├── wrf_tables/            links: WRF run-time tables (from software/WRF/run)
        │   ├── memNNN/                one directory per member, kept across cycles
        │   └── filter/                filter working directory (input.nml, file lists, inflation)
        ├── output/YYYYMMDDHHMM/       generated per cycle: priors, analyses, inflation, logs, status
        └── logs/                      driver and job logs
```

## 2. File inventory

### 2.1 Executables and fixed data (from `../software`)

| Item | Source | Status | Note |
|---|---|---|---|
| `wrf.exe`, `real.exe` | `software/WRF/main` | ready | used by all three comparison runs |
| WRF run-time tables (`RRTMG_*`, Thompson tables, `*.TBL`) | `software/WRF/run` | ready | linked as in `theta_m0/` |
| `da_wrfvar.exe` | `software/WRFDA/var/build` | ready (built), untested | first use is the one-draw test |
| `be.dat` (= `be.dat.cv3`) | `software/WRFDA/var/run` | ready | generic CV3; amplitude and scales tuned in `namelist.input.3dvar` |
| `filter` | `software/DART/models/wrf/work` | ready | rebuild only if `&preprocess` obs types change (deferred) |
| `advance_time` | same | ready | **verified**: handles `15m`, `-15m`, `YYYYMMDDHHMM` |
| `fill_inflation_restart` | same | ready | |
| `update_wrf_bc` | same | **patch** | `THM` + untouched fields (notes 2.6, 2.7) |
| `pert_wrf_bc` | same | not used | kept for reference; replaced by 2.12 route |
| `sampling_error_correction_table.nc` | `DART/assimilation_code/programs/gen_sampling_err_table/work` | ready | only if `sampling_error_correction = .true.` |
| `obs_diag`, `obs_seq_to_netcdf`, `obs_sequence_tool` | DART `work` | ready | deferred (obs diagnostics) |
| NCO | `module load nco/4.9.3` | ready (module) | not loaded by `env_wrf.sh`; only needed if we keep NCO steps |
| NCL | `module load ncl/6.6.2-py3-serial` | not used | tutorial's `.ncl` scripts are ported to Python |

### 2.2 Configuration (tracked, `cases/20250520/da_theta_m0/config/`)

| File | Status | Starting point | What changes |
|---|---|---|---|
| `experiment.sh` | new | tutorial `param.sh` | Paths; `NUM_ENS = 50`; first/last analysis time; `CYCLE_SECONDS = 900`; nodes/tasks per member; filter resources; UCX settings; `batch_all` |
| `input.nml` | modify | `dart/mmc/input.nml` (our `theta_m0` `model_mod_check` setup) + `tutorial/template/input.nml.template` | `ens_size = 50`; state variables (open: include `W`? HRRRDAS doesn't, note 2.10); `stages_to_write` and output volume; inflation flavor, damping for 15-min cycles (note 2.9); input/output file lists; `&fill_inflation_restart_nml`. Obs blocks (`&obs_kind_nml`, localization cutoffs) deferred |
| `namelist.input.real` | modify | `theta_m0/real/namelist.input` | 1-h start/end window per call; same physics and grid; `hybrid_opt = 0`, `use_theta_m = 0` |
| `namelist.input.wrf` | modify | `theta_m0/namelist.input` | Start/end filled per segment; `run_seconds = 900`; `history_interval = 15`, one frame per file; `iofields_filename`, `ignore_iofields_warning`; no restart output; `nproc_x/y` for the per-member node count; keep `nocolons`, classic netCDF |
| `namelist.input.3dvar` | adapt | `tutorial/template_nest/namelist.input.3dvar` | Our grid (550 × 390 × 150, 2.5 km, projection), `max_dom = 1`, `RANDOMCV`, `cv_options = 3`, seeds, `as1..as4` (tutorial values as first test; plan 3B) |
| `iofields_cycle.txt` | new | field list in adaptation note 2.11 | `+:h:0:` + 65 names |
| `assignment.txt` (copy) | generated | `assign_perturbations.py` | tracked for reproducibility |

### 2.3 Scripts (tracked, `scripts/da/`)

Grouped by pipeline step. Each step runs one at a time and gets reviewed before the next (CLAUDE.md).

| Step | Script | Status | Starting point | Job type |
|---|---|---|---|---|
| 0 Setup | `setup_experiment.sh` | adapt | tutorial `setup.sh` | login node |
| 1 Mean IC/BC | `make_mean_icbc.sh` | adapt | tutorial `gen_retro_icbc.sh`, our `slurm.real` | one Slurm job looping `real.exe` over 73 hours (+ the 72-h `wrfbdy`) |
| 2 Perturbation bank | `gen_pert_bank.sh`, `wrfda_bank_diff.py` | adapt, new | tutorial `gen_pert_bank.sh` | Slurm array, 150 tasks; one-draw test first |
| 3 Assignment | `assign_perturbations.py` | new | plan 3C | login node |
| 4 Initial members | `make_initial_members.py` | new | `add_bank_perts.ncl`, `init_ensemble_var.sh` | login or small job |
| 5 Member boundaries | `build_member_bdy.py` | new | note 2.12 | Slurm job (I/O heavy, ~460 GB written) |
| 6 Inflation init | (in `setup_experiment.sh` or driver) | adapt | tutorial step 7 | login node, `fill_inflation_restart` |
| 7 Spin-up | none separate: cycling (step 8) starts 6–12 h before 05-20 00Z; the EAKF cycling is the spin-up (adaptation note 2.13). An optional short free advance before the first analysis uses the same cycle job without `filter` | — | `init_ensemble_var.sh`, `first_advance.sh` | same cycle job |
| 8 Cycling | `driver.sh` → `cycle_job.sh` → `advance_member.sh`, `prep_filter.sh`, `post_filter.sh` | adapt/new | tutorial `driver.sh`, `new_advance_model.sh`, `assimilate.sh`, `prep_ic.sh` | login-node driver, one allocation per cycle |
| 9 Diagnostics | `mean_increment.py`, `check_cycle.py` | new | `mean_increment.ncl`, driver checks | inside cycle job / login node |
| — | `diagnostics_obs.sh` | deferred | tutorial | obs side |

What each cycling script does:
- **`advance_member.sh`** (per member, per segment):
  1. Copy the untouched `bdy/wrfbdy_d01_memNNN` into the member directory.
  2. Run `update_wrf_bc` against the member's analyzed file.
  3. Fill in the times in `namelist.input.wrf`.
  4. Run `srun wrf.exe` with the UCX settings.
  5. Check for `SUCCESS COMPLETE WRF`.
  6. Rename the new `wrfout` to the member's `wrfinput_d01` for the next cycle. There is no mean template (note 2.11).
- **`prep_filter.sh`:** write `input_list_d01.txt`/`output_list_d01.txt` pointing at `run/memNNN/wrfinput_d01`, so the analysis is written in place, as in HRRRDAS. Stage inflation files and `obs_seq.out` (deferred).
- **`post_filter.sh`:** move `output_priorinf_*` to the next cycle's inflation input, compute the increments, and archive the preassim/postassim mean and sd.
- **`cycle_job.sh`:** one `sbatch`. It runs every member segment as background `srun --exclusive -N k` steps and `wait`s, checks all of them, then runs `srun filter`. A member failure stops the cycle; no member is ever replaced by a copy of another (plan 4A).
- **`driver.sh`:** a loop over analysis times. For each it submits `cycle_job.sh`, waits (via `squeue`/`sacct` plus a status file), verifies, and records completion in `output/<time>/status`. It restarts from the last complete cycle.

### 2.4 Generated data (untracked)

| Product | Made by | Size (estimate) |
|---|---|---|
| `mean/wrfinput_d01_<YYYYMMDDHH>` × 73, `mean/wrfbdy_d01` | step 1 | 73 × 1.19 GB ≈ 87 GB + 9.3 GB (compressed) |
| `perts/bank/pert_bank_NNN.nc` × 150 | step 2 | U, V, THM, QVAPOR, MU only: ~0.5 GB each uncompressed → ~75 GB; compress |
| `run/memNNN/wrfinput_d01` × 50 (initial) | step 4 | 50 × ~1.2 GB |
| `bdy/wrfbdy_d01_memNNN` × 50 | step 5 | ≈ 460 GB |
| `input_priorinf_mean/sd.nc` | step 6 | small |
| per-cycle `output/` | steps 7–8 | set by the `stages_to_write`/member-output choice; decide retention before long runs |

### 2.5 Observation side (being planned; conventional source chosen: public MADIS, adaptation note 2.13)

`obs_seq.out` per cycle (MRMS + PREPBUFR converters), `&obs_kind_nml`, `&obs_def_radar_mod_nml`,
per-type localization, `&preprocess_nml` obs types (and the `filter` rebuild that follows),
`wrf_dart_obs_preprocess`, `obs_diag`/`obs_seq_to_netcdf` diagnostics. Until then, engineering tests of
the cycle can use a no-obs or synthetic `obs_seq.out` (e.g. from `create_obs_sequence`) so that `filter`
runs end to end.

## 3. Open choices to settle while building (not blocking the layout)

- Nodes per member and members per allocation (cold-start cost vs 900 s of integration, note 2.1);
  `batch_all` has 128 nodes.
- `W` in the DART state vector or not (`mmc/input.nml` has it; HRRRDAS doesn't analyze it).
- Cycling start time (6 or 12 h before 05-20 00Z) and when the spin-up counts as done (from spread, rejection and inflation diagnostics; note 2.13).
- Output retention per cycle.
