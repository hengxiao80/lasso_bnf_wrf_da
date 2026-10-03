# CLAUDE.md

Guidance for working in this repo (WRF-DART data assimilation for LASSO BNF LES forcing).

## Purpose and plan

A 50-member, 15-minute-cycled WRF-DART EAKF system at 2.5 km over BNF (MRMS reflectivity
plus HRRR-type conventional observations), to test whether it gives better initial and
boundary forcing for 500-m LES than hourly HRRRv4 analyses. The big picture is in
`initial_plan_from_codex/` (the `.md` is the more detailed and more current one). Treat those
documents as direction, not as finished implementation details. Implementation proceeds a
piece at a time with trial and error.

Decisions from the plan that still hold: `hybrid_opt = 0` and `use_theta_m = 1` for project
WRF runs, with DART analyzing dry theta and a conversion back to moist `THM` (still to be
implemented, following MPAS).

Temporary deviation, decided by the user on 2026-09-21: the DART workflow is being developed first
with the `theta_m0` setup (`hybrid_opt = 0`, `use_theta_m = 0`). Stock DART requires `USE_THETA_M = 0`
(`model_mod.f90` errors otherwise), so this avoids the moist/dry conversion while the rest of the
workflow is worked out. The conversion comes back once that workflow works. The target
configuration is still `use_theta_m = 1`; do not treat `theta_m0` as the final choice.

## Current state

- All software is built (WRF, WPS, WRFDA, DART); versions and patches are in `software_lock.json`
  and `patches/README.md`.
- Case `2025-05-20` (LASSO BNF, 2025-05-19 00Z to 05-22 00Z, 2.5 km, 550x390x150, dt = 5 s):
  WPS and `real.exe` pipeline done. `baseline` (hybrid_opt=0, use_theta_m=1), `hybrid2`
  (hybrid_opt=2) and `theta_m0` (use_theta_m=0) WRF runs are all complete (289 history files each,
  15-min output, ~1.1 TB per run; `theta_m0` ran on `batch_all` in 3 h 54 min).
- Verified against sey's runs: ungrib and metgrid outputs identical, and our `hybrid_opt=2`
  `wrfinput`/`wrfbdy` bit-identical to his.
- 5-member DA pilot (`theta_m0` setup) in `cases/20250520/da_theta_m0/`, scripts in `scripts/da/`, step
  list and all results/decisions in `notes/da_5member_pilot_steps.md`. Done (2026-10-01): hourly mean
  `wrfinput`, WRFDA perturbation bank (15 draws), 5 centered initial members, per-member `wrfbdy`
  (patched `pert_wrf_bc`), restart tests. Members cycle with **true WRF restarts**; DART works on a
  small file extracted from `wrfrst` (`scripts/da/wrfrst_dart.py`). Boundary refit test (step 8)
  passed 2026-10-02 (`scripts/da/refit_member_bdy.sh`). Steps 9-10 (MADIS conversion, all hours of 05-20/05-21,
  `scripts/da/convert_madis_hour.sh` → `cases/20250520/obs/obs_seq_madis/`; per-cycle `obs_seq.out` for 00:15-01:00 by `scripts/da/make_cycle_obs.sh`) done 2026-10-02. Step 11
  (filter `input.nml`, `cases/20250520/da_theta_m0/config/input.nml.filter`; gate `slurm.filter_gate` on the
  00Z initial members) done 2026-10-02. Step 12 (cycle scripts: `slurm.cycle` → `scripts/da/driver.sh` → `cycle_job.sh`, `prep_filter.sh`, `post_filter.sh`, `advance_member.sh`, `check_cycle.py`) written 2026-10-02. Step 13 (1-hour pilot, 00:00 cold start + 4 analyses, ~32 min on 40 nodes) passed 2026-10-02/03 in four runs side by side (`RUN_NAME`: `run*/`, `output*/`): DART's PH, hydrostatic PH (`_hph`; removes most of the post-analysis shock; `HYDROSTATIC_PH=1` is the default since 2026-10-03), and two quick inflation looks (`_hph_d9956`, `_hph_f5`); fuller inflation tests postponed by the user. Next: step 14, the extension.
- Not started: DART `model_mod_check` smoke test (deferred by the user), moist/dry theta
  conversion, and the NCEP/prepbufr conventional-observation
  pipeline (DART's `prepbufr`/`create_real_obs` converters, `&prep_bufr_nml`/`&ncepobs_nml`) —
  already called for in `initial_plan_from_codex/` Phase 2 Steps 2E-2H to bring in the
  HRRRv4-CONUS conventional-observation families, reconfirmed by the user on 2026-09-22.
  Comparison of the three runs (OLR brightness temperature and
  reflectivity vs GOES/MRMS/HRRR, differences between runs) is being done in the `bnf_wrf_eval` repo, in a
  separate session, not here.

## Layout

- `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da` is this repo; `/ccsopen/home/hengxiao80/bnf_wrf_da`
  is a link to it.
- Source and builds live **outside** the repo in `../software/{WRF,WPS,WRFDA,DART}`. Executables are
  linked in, and runtime configs, scripts and data are kept here. Never commit software trees or data.
- `scripts/`: `env_wrf.sh` (module environment), `audit_configuration.py` (writes `software_lock.json`),
  `link_hrrr_gribfiles.py`, `setup_ungrib_chunks.py`, `merge_ungrib_chunks.py`, `reverse_metgridlevs.py`
  (WPS pipeline), `make_wrf_iotest.py` and `summarize_wrf_timing.py` (I/O tests),
  `plot_layer_thickness.py`.
- `cases/20250520/`: `geog/` (copied `geo_em.d01.nc`), `wps/` (ungrib/metgrid/reverse, 73 `met_em`
  files), `baseline/` (`real.exe` outputs in place), `hybrid2/` and `theta_m0/` (`real.exe` run in a
  `real/` subdirectory, then linked up), `iotest/`, `figures/`, and `DATA_SOURCES.md`.
- `patches/`: local deviations from the pinned upstream code, with the reasons.

## Environment and conventions

- Builds and runs need `source scripts/env_wrf.sh` (intel/20.0.4 = ifort 19.1.3, openmpi/4.0.4,
  netcdf-wrf/0.1, hdf5, jasper). This is a dm+sm build (MPI ranks x OpenMP threads).
- Python is managed by `uv` (3.11, `uv run ...`). The system `python3` is 3.6 and too old. In Slurm
  jobs call `.venv/bin/python` directly, since compute nodes have no internet. `UV_CACHE_DIR` is on
  proj-shared (set in `~/.bashrc`) because home is nearly full.
- Slurm: account `cli120`. Submit to `batch_all` (5-day limit) by default; do not use `priority_long`
  unless a run needs more than 5 days, and the user will say when to switch queue. (The existing
  `cases/` job scripts say `priority_long` because they were copied from sey's setup and are kept as
  a record of what ran; do not copy that into new scripts.) Get the user's go-ahead before submitting
  jobs, run multi-step pipelines one step at a time, and report each result.
- Commit messages end with the `Co-Authored-By: Claude ...` trailer. The repo has no remote.
  `.gitignore` allowlists only small config files under `cases/`; new small files there need adding to it.

## Gotchas learned the hard way

- The user's shell aliases `ls` with `-F`, so `ls` output has `@`/`*` suffixes. Use `find` or
  `command ls` in scripts. This once created dozens of broken symlinks.
- Claude Code replays a shell snapshot taken at session start, so `~/.bashrc` edits do not apply
  mid-session; export explicitly or restart.
- `make -i` (WRF, WPS) hides compile and link errors ("Error 1 (ignored)"). Read the log for real errors.
  Two known fixes are in `patches/`.
- Slurm reports a job `COMPLETED` even when `srun` was killed, since the script's last commands still
  ran. Check the logs (`SUCCESS COMPLETE WRF` / `REAL_EM INIT`).
- Keep each job type's UCX setting, copied from the existing scripts, and don't mix them. `wrf.exe`
  jobs (`slurm.wrf`): `UCX_TLS=self,sm,ud` and `UCX_UD_MLX5_RX_QUEUE_LEN=16384`; without them the
  larger 500-m runs fail on MPI communication (no speed difference at 2.5 km). `real.exe` jobs
  (`slurm.real`): `UCX_TLS=rc,xpmem,self`, as in sey's real.exe job.
- PnetCDF is compiled in but troublesome. Quilting with PnetCDF crashes at startup, and quilting with
  plain netCDF gives no overlap. Use `io_form_history = 2` with `use_netcdf_classic = .true.`.
  Compressed netCDF-4 output costs ~45 s per write (single-threaded deflate) versus ~5 s for classic.
  Compress afterwards if disk matters: `nccopy -k nc4 -d 2 -s in out` (lossless, ~3x smaller).
- `nocolons = .true.` is needed so output names (`wrfout_d01_YYYY-MM-DD_HH_MM_SS`) match what
  `bnf_wrf_eval` expects.
- Baseline settings: 16 nodes, 256 ranks x 8 threads, `nproc_x = nproc_y = 16`, ~4 h wall for 72 h
  of model time (15-min history, ~1.1 TB). A 16x32 automatic decomposition performed worse.
- `spec_bdy_width = 10` alone gives WRF's default `spec_zone = 1`, `relax_zone = 4` (rows 5–10 of
  `wrfbdy` unused), not the intended 1 + 9; inherited from sey's setup. All runs so far and the 5-member
  pilot use 1 + 4; the 50-member DA switches to 1 + 9 (Q18 in `notes/da_5member_pilot_steps.md`).
- `real.exe` with `use_netcdf_classic` unset writes compressed netCDF-4 input files, which is fine.

## External data and other repos

- Inputs come from `sey`'s directories, referenced in place and read-only: HRRR analyses under
  `/gpfs/wolf2/arm/cli120/proj-shared/sey/bnf/wrf/forcing/hrrr`, plus a few files copied from his case.
  Never modify anything under `sey/`. `cases/20250520/DATA_SOURCES.md` lists every dependency.
- `../bnf_wrf_eval` evaluates WRF runs against HRRR, GOES, MRMS and lightning. It has its own
  `CLAUDE.md`, its own `uv` environment, and expects `wrfout_d01_YYYY-MM-DD_HH_MM_SS` run directories.
