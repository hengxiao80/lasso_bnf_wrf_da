"""Build per-member lateral boundary files (pilot step 6).

Usage: .venv/bin/python scripts/da/build_member_bdy.py <exp_dir> [--start 2025-05-20_00:00:00]
           [--hours 2] [--nmem 5] [--members 1 2 ...] [--jobs 5] [--zero-pert]
           [--pert-template perts/members/pert_mem{mem:03d}.nc] [--pert-wrf-bc PATH]

1. Subset: copies the records starting at --start, --start + 1 h, ... (--hours of them) from
   exp_dir/mean/wrfbdy_d01 into exp_dir/bdy/wrfbdy_d01_mean_<start>_<hours>h (created once).
2. For each member and each record h: writes small temporary states (only the fields pert_wrf_bc
   reads) for mean_h + pert and mean_(h+1) + pert, with T = THM and QVAPOR >= 0, and runs the
   patched pert_wrf_bc on that record of a copy of the subset. Record h then runs from the
   perturbed mean at h to the perturbed mean at h+1. Output: exp_dir/bdy/wrfbdy_d01_memNNN.
   Fields pert_wrf_bc doesn't refit (hydrometeors, aerosol numbers, ...) stay as in the mean file.

The perturbation for member m at hour index h (0 = --start) is read from
exp_dir/<pert-template>.format(mem=m, hour=h); the default uses the same file for every hour
(option A of Q5). --zero-pert writes exp_dir/bdy/wrfbdy_d01_refit_mean from the unperturbed mean
states instead, to test the builder: it should reproduce the subset of the real.exe file.
See notes/da_5member_pilot_steps.md step 6.
"""

import argparse
import datetime as dt
import os
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor

import netCDF4
import numpy as np

PERT_FIELDS = ["U", "V", "THM", "QVAPOR", "MU"]
STATE_FIELDS = ["Times", "U", "V", "W", "PH", "T", "QVAPOR", "MU", "MUB",
                "MAPFAC_U", "MAPFAC_V", "MAPFAC_M"]
PERT_WRF_BC = "/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/software/DART/models/wrf/work/pert_wrf_bc"
FMT = "%Y-%m-%d_%H:%M:%S"


def times(ds):
    return [b"".join(t).decode() for t in np.asarray(ds["Times"][:])]


def make_subset(src_path, out_path, start, hours):
    """Copy records start .. start + hours - 1 h of a wrfbdy file (all variables, same storage)."""
    with netCDF4.Dataset(src_path) as src:
        all_times = times(src)
        first = all_times.index(start)
        recs = slice(first, first + hours)
        if len(all_times[recs]) != hours:
            raise SystemExit(f"{src_path} has only {len(all_times) - first} records from {start}")
        tmp = out_path + ".tmp"
        with netCDF4.Dataset(tmp, "w", format=src.data_model) as out:
            out.setncatts({a: src.getncattr(a) for a in src.ncattrs()})
            for name, dim in src.dimensions.items():
                out.createDimension(name, None if dim.isunlimited() else len(dim))
            for name, var in src.variables.items():
                filt = var.filters() or {}
                chunks = var.chunking()
                v = out.createVariable(name, var.dtype, var.dimensions,
                                       zlib=bool(filt.get("zlib")), complevel=filt.get("complevel") or 4,
                                       shuffle=bool(filt.get("shuffle")),
                                       chunksizes=None if chunks == "contiguous" else chunks)
                v.setncatts({a: var.getncattr(a) for a in var.ncattrs()})
                v[:] = var[recs] if var.dimensions[0] == "Time" else var[:]
    os.replace(tmp, out_path)
    print(f"subset: records {first}..{first + hours - 1} ({start}, {hours} h) -> {out_path}")


def write_state(mean_path, pert_path, out_path):
    """Small wrfinput-like file with the fields pert_wrf_bc reads; T = THM, QVAPOR >= 0."""
    with netCDF4.Dataset(mean_path) as mean, \
         netCDF4.Dataset(out_path, "w", format="NETCDF3_64BIT_OFFSET") as out:
        out.setncatts({a: mean.getncattr(a) for a in mean.ncattrs()})
        dims = set()
        for name in STATE_FIELDS:
            dims.update(mean[name].dimensions)
        for d in sorted(dims):
            out.createDimension(d, None if mean.dimensions[d].isunlimited() else len(mean.dimensions[d]))
        # The perturbation's own Times (the bank date) is not checked: under option A the same
        # perturbation is added at every hour.
        pert = netCDF4.Dataset(pert_path) if pert_path else None
        for name in STATE_FIELDS:
            v = out.createVariable(name, mean[name].dtype, mean[name].dimensions)
            v.setncatts({a: mean[name].getncattr(a) for a in mean[name].ncattrs()})
            if name == "T":
                continue
            field = mean[name][:]
            if pert is not None and name in ("U", "V", "QVAPOR", "MU"):
                field = np.asarray(field, np.float64) + np.asarray(pert[name][:], np.float64)
            if name == "QVAPOR":
                field = np.maximum(field, 0.0)
            v[:] = field
        thm = np.asarray(mean["THM"][:], np.float64)
        if pert is not None:
            thm = thm + np.asarray(pert["THM"][:], np.float64)
        out["T"][:] = thm
        if pert is not None:
            pert.close()


def build_member(args, mem, subset_path, hour_times):
    """Run pert_wrf_bc for every record of one member's copy of the subset."""
    tag = "refit_mean" if mem == 0 else f"mem{mem:03d}"
    out_path = os.path.join(args.exp_dir, "bdy", f"wrfbdy_d01_{tag}")
    work = os.path.join(args.exp_dir, "bdy", "work", tag)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    shutil.copyfile(subset_path, os.path.join(work, "wrfbdy_this"))
    # DART's initialize_utilities reads &utilities_nml; pert_wrf_bc has no namelist of its own.
    with open(os.path.join(work, "input.nml"), "w") as f:
        f.write("&utilities_nml\n   termlevel = 1,\n   logfilename = 'dart_log.out',\n"
                "   nmlfilename = 'dart_log.nml',\n   write_nml = 'file',\n/\n")
    log = []
    for h in range(args.hours):
        states = []
        for k in (h, h + 1):
            mean_path = os.path.join(args.exp_dir, "mean",
                                     "wrfinput_d01_" + hour_times[k].replace(":", "_"))
            pert_path = None if mem == 0 else \
                os.path.join(args.exp_dir, args.pert_template.format(mem=mem, hour=k))
            states.append((mean_path, pert_path))
        write_state(*states[0], os.path.join(work, "wrfinput_this"))
        write_state(*states[1], os.path.join(work, "wrfinput_next"))
        res = subprocess.run([args.pert_wrf_bc], cwd=work, capture_output=True, text=True)
        with open(os.path.join(work, f"pert_wrf_bc_{h:02d}.log"), "w") as f:
            f.write(res.stdout + res.stderr)
        if res.returncode != 0 or "Finished successfully" not in res.stdout + res.stderr:
            raise RuntimeError(f"{tag} record {hour_times[h]}: pert_wrf_bc failed, see {work}")
        log.append(f"{tag} {hour_times[h]} -> {hour_times[h + 1]}: "
                   + ", ".join(os.path.basename(p) if p else "mean" for _, p in states))
    os.replace(os.path.join(work, "wrfbdy_this"), out_path)
    shutil.rmtree(work)
    return log


def main():
    p = argparse.ArgumentParser()
    p.add_argument("exp_dir")
    p.add_argument("--start", default="2025-05-20_00:00:00")
    p.add_argument("--hours", type=int, default=2)
    p.add_argument("--nmem", type=int, default=5)
    p.add_argument("--members", type=int, nargs="+")
    p.add_argument("--jobs", type=int, default=5)
    p.add_argument("--zero-pert", action="store_true")
    p.add_argument("--pert-template", default="perts/members/pert_mem{mem:03d}.nc")
    p.add_argument("--pert-wrf-bc", default=PERT_WRF_BC)
    args = p.parse_args()

    t0 = dt.datetime.strptime(args.start, FMT)
    hour_times = [(t0 + dt.timedelta(hours=h)).strftime(FMT) for h in range(args.hours + 1)]
    bdy_dir = os.path.join(args.exp_dir, "bdy")
    os.makedirs(bdy_dir, exist_ok=True)
    subset_path = os.path.join(bdy_dir, f"wrfbdy_d01_mean_{args.start[:13].replace(':', '_')}_{args.hours}h")
    if not os.path.exists(subset_path):
        make_subset(os.path.join(args.exp_dir, "mean", "wrfbdy_d01"), subset_path, args.start, args.hours)

    members = [0] if args.zero_pert else (args.members or list(range(1, args.nmem + 1)))
    with ProcessPoolExecutor(max_workers=min(args.jobs, len(members))) as pool:
        futures = [pool.submit(build_member, args, m, subset_path, hour_times) for m in members]
        for fut in futures:
            for line in fut.result():
                print(line)


if __name__ == "__main__":
    main()
