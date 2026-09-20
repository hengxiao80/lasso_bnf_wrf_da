We will have quite a few large software packages to compile and customize for this project: WRF (including WPS) and WRFDA and DART. The repos for these large packages will live outside of the current project directory (`/ccsopen/home/hengxiao80/bnf_wrf_da`). So the executables needed for the whole workflow will be linked in. All the runtime configuration files for WRF and DART should live in the project directory. And all the driver, diagnostic and visualization scripts should also be here. All the data (input, output) will live here as well (we are allowed to stage all data here for now).

We will run WRF and DART with MPI and SLURM. But the driver script for the whole workflow will be run from a login node.

For the modules we need to load for WRF, WRFDA and DART to work, I think we have them all installed on this system. Just need to load them and make sure they work together okay.



