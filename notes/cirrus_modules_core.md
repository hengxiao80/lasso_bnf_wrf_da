# Cirrus module change of 2026-10-30: `Core` modules

Written 2026-10-30 in the session "software: module env changes on cirrus". OLCF has published no documentation or notice about this change yet (nothing in `/etc/motd`), so everything below comes from the files on the system. How permanent it is is not known.

## 1. Symptom

On 2026-10-30, after the `module purge` in `~/.bashrc`, `module load intel/20.0.4` failed. Lmod now says the module "exist[s] but cannot be loaded as requested" and suggests `module load Core/26.10 intel/20.0.4` or `module load Core/A100 intel/20.0.4`. The same happens to `openmpi/4.0.4`, `netcdf-wrf/0.1`, `hdf5` and `jasper`, i.e. to every module in `scripts/env_wrf.sh`, so every job script of this repo would have failed. There is no way to load them without a `Core` module.

## 2. What changed

- `/etc/profile.d/olcf-env.sh` (dated 2026-10-30 09:38) now sources `/sw/cirrus/nsp/init/profile`, which starts a new, Ansible-managed Lmod 9.4.3 under `/sw/cirrus/nsp/lmod/` (its files are dated 2026-10-20).
- The default MODULEPATH is now only `/sw/cirrus/nsp/modulefiles`: `Core/*`, `DefApps`, `gcc`, `oneapi`, `cuda`, `nvhpc`, `miniforge3`.
- The old software (the 2021-era Spack stack: intel 20.0.4, openmpi 4.0.4 and 4.1.4, netcdf-wrf, hdf5, jasper) is still on disk, unchanged, but its module directories are reached only through a `Core` module.
- At login, `DefApps` runs `try_load("Core/A100")` (file dated 13:25 the same day, so the admins were still adjusting things). `module purge` unloads it again, which is why a `.bashrc` or script that purges first no longer finds `intel/20.0.4`.
- `/sw/cirrus/nsp/lmod/etc/rc.lua` names `Core/26.10` (`module_version('Core/26.10')`). The site hook `/sw/cirrus/nsp/lmod/hooks/NSPHierarchyHook.lua` labels the old directories "A100 Base" and "A100 Core" and the new ones "H200 Base".
- Slurm has a new partition `gpu_h200` (2 nodes, 2 H200 each) next to `gpu` (1 node, 4 A100). The CPU partitions (`batch_all` and the others) are unchanged.

Our reading, not confirmed by OLCF: a new software stack was built for the H200 nodes, and the module tree was split so that the old and the new stack can be chosen separately. "26.10" is probably the year and month of the release.

## 3. The three `Core` modules

All three are in `/sw/cirrus/nsp/modulefiles/Core/` (dated 2026-10-29). `Core/A100` and `Core/H200` are in the Lmod family `core`, so loading one swaps out the other; `Core/26.10` is not in it.

| module | adds to MODULEPATH |
|---|---|
| `Core/A100` | old stack only |
| `Core/H200` | new stack only |
| `Core/26.10` | both, with priorities |

- Old stack: `/sw/cirrus/spack-envs/base/modules/spack/linux-rhel8-x86_64/Core`, `/sw/cirrus/spack-envs/base/modules/site/Core` and `/sw/cirrus/modulefiles/core` (which has `netcdf-wrf`).
- New stack: `/sw/cirrus/nsp/spack/modules/Core` (built 2026-10-27/28): oneapi 2026.0.0, gcc, CUDA, nvhpc, `openmpi/4.1.4-gpu` and newer tools (git 2.48.1). It has no intel 20, `netcdf-wrf`, hdf5 or jasper.

"A100" names the old stack, not the GPUs. This project uses no GPUs, and `Core/A100` is the stack WRF, WPS, WRFDA and DART were built with.

## 4. Why not `Core/26.10`

`Core/26.10` prepends its paths with Lmod priorities: 20 for the old Spack `Core` and `site/Core`, 15 for `modulefiles/core`, 10 for the new stack. Lmod keeps priority paths in front of ordinary ones, so the compiler directory that `module load intel/20.0.4` prepends (no priority) lands behind all of them. The order after `module load Core/26.10 intel/20.0.4`, with `B` = `/sw/cirrus/spack-envs/base/modules`:

```
1  $B/spack/linux-rhel8-x86_64/Core          (has gcc builds)
2  $B/site/Core
3  /sw/cirrus/modulefiles/core
4  /sw/cirrus/nsp/spack/modules/Core         (new stack)
5  $B/spack/linux-rhel8-x86_64/intel/20.0.4  (intel builds)
6  /etc/scl/modulefiles
7  /sw/cirrus/nsp/modulefiles
```

With `Core/A100` the intel directory comes first, as before 2026-10-30. Directory 1 has its own gcc-8.3.1 builds of several libraries under the same names and versions, and under `Core/26.10` they win over the intel ones. Tested in fresh login shells, the module set of `env_wrf.sh` resolves as follows:

| module | `Core/A100` | `Core/26.10` |
|---|---|---|
| openmpi/4.0.4 | intel | gcc |
| hdf5/1.10.7 | intel | gcc |
| netcdf-wrf/0.1 | same | same |
| jasper/2.0.32 | gcc¹ | gcc¹ |

¹ jasper is a gcc build either way, as it was before (`software_lock.json`).

Under `Core/26.10`, `ldd wrf.exe` shows `libhdf5hl_fortran.so.100 => not found` and takes the rest of HDF5 from the gcc build, so `wrf.exe` would not start. MPI is still the intel build there only because `wrf.exe` carries an RPATH to it; `filter` gets the intel HDF5 the same way. A rebuild in that environment would compile with ifort against a gcc-built MPI.

The interactive set in `~/.bashrc` (`intel/20.0.4 openmpi/4.1.4 netcdf-fortran/4.5.3 netcdf-c/4.8.1`) has the same problem: under `Core/26.10`, `netcdf-fortran/4.5.3` is the gcc build, whose `.mod` files ifort can't read; `openmpi` and `netcdf-c` are intel. Under `Core/A100` all are intel. The user is switching `~/.bashrc` to `Core/A100` too (the only loss is git 2.31.1 instead of 2.48.1).

## 5. What was changed in the repo

- `scripts/env_wrf.sh` loads `Core/A100` right after `module purge`. Every Slurm script of the repo sources this file, so they all pick it up.
- `CLAUDE.md` has a gotcha that points here.

Checked after the change, on the login node in a fresh login shell with `source scripts/env_wrf.sh`: it loads `Core/A100 intel/20.0.4 openmpi/4.0.4 netcdf-wrf/0.1 hdf5/1.10.7 jasper/2.0.32`, `mpif90` is the intel-20.0.4 openmpi 4.0.4, and `ldd` finds every library of `wrf.exe`, `real.exe`, `metgrid.exe` and `filter`, none from a gcc-8.3.1 build. Not yet checked on a compute node.

## 6. If it changes again

To see the current setup:

```
cat /etc/profile.d/olcf-env.sh
module -t avail Core
module show Core/A100
```

To check the build environment (no output means fine):

```
source scripts/env_wrf.sh
ldd ../software/WRF/main/wrf.exe | grep -e 'not found' -e gcc-8.3.1
```

If `Core/A100` is removed, the old stack has been retired, and the software would need to be rebuilt on the new one.

## 7. Side finding: `software_lock.json`

`scripts/audit_configuration.py` resolves each `module load` line of `env_wrf.sh` with a separate `bash -lc "module show <module>"`, i.e. in the login environment set up by `~/.bashrc`, not in the one `env_wrf.sh` builds. So its `modules_resolved` entries can differ from what the jobs load. For example, its `hdf5` entry is `.../openmpi/4.1.4-64cfg5a/intel/20.0.4/hdf5/1.10.7.lua`, a directory that only `~/.bashrc`'s `openmpi/4.1.4` puts on the path, while `env_wrf.sh` gets `.../intel/20.0.4/hdf5/1.10.7.lua`. The lock was not regenerated for this change; making the script resolve the modules inside `env_wrf.sh`'s environment is left open.
