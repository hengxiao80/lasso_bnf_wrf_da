# DA cycle: how the member files are made and changed

Which script creates, changes or reads each file that carries a member's state, from the hourly HRRR-based mean states to the next cycle's restart file. Written 2026-11-06 in session "fulltest: initial setup", from the scripts as they are for the 5-member runs (`theta_m0`, one-pass MRMS since run 5, `HYDROSTATIC_PH=1`), before any changes for the 50-member full test. One planned change is marked: the start-of-segment `wrfout` (`notes/fulltest_output_files.md` Sec. 1).

Not covered: the observation pipeline that writes `obs<OBS_NAME>/<t>/` (`make_cycle_obs.sh` and the converters; `notes/obs_expansion.md` Sec. 7–8), the two-pass MRMS path (`run<RUN>/filter_mrms/`, unused since run 5), and test jobs (`slurm.filter_gate`, `tests/`). The older `notes/da_workflow_layout.md` (2026-09-25) is the original plan and predates the true restarts.

## Abbreviations

In the diagrams and lists:

- `E/` = `cases/20250520/da_theta_m0/` (the experiment directory; since 2026-11-06 a link to `da_theta_m0_n5/`, whose `mean/`, `perts/bank/`, `perts/work/` and `obs*/` are links into `da_common_theta_m0/`, shared with `da_theta_m0_n50/`; `CLAUDE.md`, Layout)
- `R/` = `E/run<RUN>/memNNN/` (one member's working files)
- `F/` = `E/run<RUN>/filter/` (filter's run directory)
- `O/` = `E/output<RUN>/<t>/` (the cycle's saved output)
- `<t>` = the analysis time; the first segment starts at `FIRST_CYCLE` (05-20 00:00)

Every Python script writes its output under a `.tmp` name and renames it when done (`extract`, `make_initial_members.py`, the boundary subset), except where a diagram says "in place".

## 1. Built once per experiment

The mean states, the perturbations and filter's grid file. All runs (`RUN_NAME`s) share them.

```
 WPS met_em, hourly (cases/20250520/wps/)
   |
   | make_mean_icbc.sh (slurm.make_mean_icbc): real.exe for one
   |   time level per hour, in E/mean/work_real/, logs in
   |   E/mean/logs/<t>/
   v
 E/mean/wrfinput_d01_<YYYY-MM-DD_HH>_00_00     73 hourly mean states
 E/mean/wrfbdy_d01 -> theta_m0/real/wrfbdy_d01 (link; real.exe, 72 h)
   |
   +-> run_wrfda_draw.sh (slurm.pert_draw, one job per draw), in
   |     E/perts/work/draw_NNN/: fg -> mean 00Z wrfinput,
   |     be.dat -> WRFDA's be.dat.cv3, namelist.input from
   |     config/namelist.input.3dvar with the seeds;
   |     da_wrfvar.exe (RANDOMCV) writes wrfvar_output = fg + pert
   |   wrfda_bank_diff.py: wrfvar_output - fg for U V THM QVAPOR MU
   |     -> E/perts/bank/pert_bank_NNN.nc (unscaled)
   |   assign_perturbations.py: pick NUM_ENS draws (fixed seed),
   |     scale (1.3 U V THM QVAPOR, 0.6 MU), center
   |     -> E/perts/members/pert_memNNN.nc, E/perts/assignment.txt
   |
   +-> make_grid_file.py: mean 00Z wrfinput + REFL_10CM defined
         as in a wrfrst of the patched WRF (zeros; only its shape
         is read) -> E/mean/dart_wrfinput_d01_2025-05-20_00_00_00
         = GRID_FILE in experiment.sh; prep_filter.sh links it
         into F/ as wrfinput_d01 every cycle, and filter and
         fill_inflation_restart read it for the static grid and
         as the template for every state variable's dimensions
         and attributes (Sec. 4.1)
```

In the cycle, `GRID_FILE` is read only through that link. The observation scripts take the grid from files with the same grid and terrain: `make_cycle_obs.sh` sets its own `GRID_FILE` to the plain mean 00Z `wrfinput` and links that into its work directory as `wrfinput_d01` for `wrf_dart_obs_preprocess`, and `make_cycle_mesonet.sh` passes `experiment.sh`'s `GRID_FILE` to `select_mesonet_cycle.py` for the terrain height and the projection.

## 2. The members' cold-start files

Also built once and shared by all runs. Neither file is ever changed afterwards.

```
 E/mean/wrfinput_d01_2025-05-20_00_00_00
 E/perts/members/pert_memNNN.nc
   |
   | make_initial_members.py (on a .tmp copy of the mean file):
   |   U V THM QVAPOR MU + the member's perturbation; T = THM;
   |   QVAPOR clipped at 0; PH + hydrostatic increment from the
   |   perturbed MU THM QVAPOR; everything else as in the mean file
   v
 E/run/memNNN/wrfinput_d01                 (+ E/run/initial_members.txt)
```

```
 E/mean/wrfbdy_d01, E/mean/wrfinput_d01_<hour>, pert_memNNN.nc
   |
   | build_member_bdy.py (slurm.member_bdy):
   |   1. the records from --start (05-20 00Z), --hours of them
   |      -> E/bdy/wrfbdy_d01_mean_<start>_<N>h (made once)
   |   2. per member, in E/bdy/work/memNNN/ (removed at the end):
   |      wrfbdy_this = copy of the subset; for each record h,
   |      wrfinput_this / wrfinput_next = small states
   |      mean_h + pert / mean_h+1 + pert (T = THM, QVAPOR >= 0,
   |      hydrostatic PH); pert_wrf_bc refits record h of
   |      wrfbdy_this (log pert_wrf_bc_HH.log)
   v
 E/bdy/wrfbdy_d01_memNNN                   pristine member boundaries
```

## 3. The first segment (cold start)

At `FIRST_CYCLE` there is no analysis; `cycle_job.sh` only advances the members.

```
 E/run/memNNN/wrfinput_d01     E/bdy/wrfbdy_d01_memNNN
   |
   | advance_member.sh -> run_wrf_segment.sh, in R/wrf/:
   |   wrfinput_d01 and wrfbdy_d01 linked in, restart = .false.,
   |   RESTART_INTERVAL = 15 min; WRF's run-time tables and
   |   wrf.exe linked in; config/iofields_cycle.txt copied
   |   (planned: dropped, default history stream only);
   |   namelist.input from config/namelist.input.wrf
   | wrf.exe 00:00 -> 00:15 (cold start: start_em.F derives AL,
   |   P, ... from the input)
   v
 R/wrf/wrfrst_d01_<00:15>  --mv-->  R/wrfrst_d01_<00:15>
 R/wrf/wrfout_d01_<00:00>, wrfout_d01_<00:15>  --mv-->  O/memNNN/
   (O at 00:00; a cold start always writes history at its start)
   (planned: keep only wrfout_d01_<00:00>, delete the 00:15 one)
 R/wrf/rsl.*.0000, namelist.input  --cp-->  O/memNNN/
```

## 4. One analysis cycle at t (from 00:15)

### 4.1 Prior extraction and filter

```
 R/wrfrst_d01_<t>                         the forecast (prior)
   |
   | prep_filter.sh, one 1-node srun step per member:
   |   wrfrst_dart.py extract --extra QCLOUD QRAIN QSNOW QGRAUP
   |   REFL_10CM QNRAIN (reads only): U V W PH THM MU from time
   |   level _2; QVAPOR PSFC T2 Q2 U10 V10 MUB MAPFAC_*; T = THM
   v
 R/dart_d01.nc  --cp-->  O/memNNN/prior_d01.nc
```

`prep_filter.sh` then builds `F/` from scratch:

```
 F/input.nml            config/input.nml.filter_joint with
                        tasks_per_node and the INF_* settings
 F/wrfinput_d01         -> GRID_FILE (static grid, state template)
 F/sampling_error_correction_table.nc -> DART's table (SEC_TABLE)
 F/obs_seq.out          -> E/obs<OBS_NAME>/<t>/obs_seq.joint
 F/obs_impact_joint.txt copy of config/obs_impact_joint.txt
 F/input_list_d01.txt   R/dart_d01.nc of every member;
 F/output_list_d01.txt  the same list (filter works in place)
 F/input_priorinf_{mean,sd}.nc   prior inflation filter starts from
     first analysis (00:15): made by fill_inflation_restart,
       lambda = 1.0 and sd = 0.6 everywhere (template: mem001's
       dart_d01.nc, linked in and removed after; log
       F/fill_inflation.log, moved to O/filter/ by save)
     every later cycle: unchanged copies of the previous cycle's
       output<RUN>/<t - 15 min>/filter/postassim_priorinf_{mean,sd}.nc
       (postassim, not output_priorinf: the output stage holds
       only the UPDATE variables); filter applies the damping
       (inf_damping in input.nml)
 O/filter/inflation_source.txt is just one line: which of the two
   sources above
```

```
 run_filter (cycle_lib.sh): filter on FILTER_NODES x
   FILTER_TASKS_PER_NODE ranks, hcoll off, exit guard
   (F/filter.log; F/filter_exit_guard.txt if it fires)
   |
   | changes every R/dart_d01.nc IN PLACE: UPDATE fields analyzed,
   |   moisture clamped at 0; NO_COPY_BACK fields not written
   | writes in F/: {input,preassim,postassim,output}_{mean,sd}.nc,
   |   {preassim,postassim}_member_NNNN.nc,
   |   {preassim,postassim,output}_priorinf_{mean,sd}.nc,
   |   obs_seq.final, dart_log.out, dart_log.nml
   v
 post_filter.sh save: those files, input.nml, filter.log and
   input_priorinf_* moved (mv) to O/filter/, so O/filter/ keeps
   the inflation the cycle started from (input_priorinf_*) and
   the one it ended with (postassim_priorinf_*);
   O/filter/obs_seq.out.path; then O/filter.done
```

### 4.2 Members: analysis into the restart file, boundary refit

`post_filter.sh members` runs `post_filter.sh member` for each member as a 1-node `srun` step, all at once:

```
 R/dart_d01.nc                            filter's analysis
   |
   | wrfrst_dart.py qnrain (in place): QNRAIN by Thompson's 1-mm
   |   rule where QRAIN differs from O/memNNN/prior_d01.nc
   v
 R/dart_d01.nc  --cp-->  O/memNNN/analysis_d01.nc
   |
   | wrfrst_dart.py insert, into R/wrfrst_d01_<t> IN PLACE
   |   (log O/memNNN/insert.log):
   |   U V THM MU QVAPOR QCLOUD QRAIN QSNOW QGRAUP QNRAIN;
   |     two-level fields into both _1 and _2; Q* clipped at 0
   |   PH = prior PH + hydrostatic increment from the new MU THM
   |     QVAPOR (prior from O/memNNN/prior_d01.nc), not DART's PH
   |   AL ALT P P_HYD recomputed; T = THM
   v
 R/wrfrst_d01_<t>                         now the analysis
   |
   | wrfrst_dart.py extract (no --extra; reads only)
   v
 R/start_d01.nc
   |
   | refit_member_bdy.sh, in R/bdy/:
   |   wrfbdy_d01 = fresh copy of E/bdy/wrfbdy_d01_memNNN;
   |   wrfinput_d01 -> R/start_d01.nc (link, removed after);
   |   input.nml (&utilities_nml only); update_wrf_bc makes the
   |   record holding t start from start_d01.nc at t, with
   |   tendencies to the record's end (logs update_wrf_bc.log,
   |   dart_log.*)
   v
 R/bdy/wrfbdy_d01  --cp-->  O/memNNN/wrfbdy_d01
   (and update_wrf_bc.log); then O/memNNN/update.done
```

### 4.3 Advance and checks

```
 R/wrfrst_d01_<t>       R/bdy/wrfbdy_d01
   |
   | advance_member.sh -> run_wrf_segment.sh, in R/wrf/ (old
   |   wrfout and wrfrst removed first): wrfrst_d01_<t> and
   |   wrfbdy_d01 linked in, restart = .true.; tables, wrf.exe,
   |   iofields and namelist as at the cold start
   | wrf.exe t -> t + 15 min (exit guard: R/wrf/wrf_exit_guard.txt,
   |   hang_snapshot* if it fires)
   v
 R/wrf/wrfrst_d01_<t+15>  --mv-->  R/                -> next cycle
 R/wrf/wrfout_d01_<t+15>  --mv-->  O/memNNN/
   (planned: write_hist_at_0h_rst = .true., so the segment also
   writes wrfout_d01_<t>, the analysis; keep that one and delete
   wrfout_d01_<t+15>, which is still written because the history
   alarm must ring at t + 15 for REFL_10CM in the restart)
 R/wrf/rsl.*.0000, namelist.input  --cp-->  O/memNNN/;
   O/memNNN/cfl_count.txt; O/memNNN/advance.done
 R/wrfrst_d01_<t> deleted (not at FIRST_CYCLE)
   |
   | check_cycle.py reads O/ -> O/check_cycle.log
   v
 O/status = complete
```

## 5. Summary

- **Files WRF reads that hold a member's state are changed in two places only:** `make_initial_members.py` creates `E/run/memNNN/wrfinput_d01` once, and `wrfrst_dart.py insert` changes `R/wrfrst_d01_<t>` in place once per cycle. Otherwise `wrf.exe` writes a new restart file each segment; every other step only reads these files.
- **`R/dart_d01.nc` is changed twice per cycle before `insert` reads it:** by filter, then by `qnrain`. `O/memNNN/prior_d01.nc` is a copy taken before filter; `O/memNNN/analysis_d01.nc` a copy taken after `qnrain`.
- **The pristine member boundaries `E/bdy/wrfbdy_d01_memNNN` are never modified.** Each cycle refits a fresh copy in `R/bdy/`.
- **Overwritten every cycle:** `R/dart_d01.nc`, `R/start_d01.nc`, `R/bdy/`, `R/wrf/` and `F/`. Only the latest `R/wrfrst_d01_<t>` is kept. What is saved per cycle is in `O/` (sizes: `notes/fulltest_output_files.md` Sec. 3).
