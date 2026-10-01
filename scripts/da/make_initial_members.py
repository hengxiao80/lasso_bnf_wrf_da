"""Write the initial ensemble members (pilot step 5).

Usage: .venv/bin/python scripts/da/make_initial_members.py <exp_dir> [--time 2025-05-20_00:00:00]
                                                          [--nmem 5]

For each member m, writes exp_dir/run/memNNN/wrfinput_d01 = mean wrfinput at --time
(exp_dir/mean/wrfinput_d01_<time>) + exp_dir/perts/members/pert_memNNN.nc for U, V, THM, QVAPOR, MU
(already scaled and centered by assign_perturbations.py). Then sets T = THM (theta_m0: the boundary
tools read T; see notes/da_5member_pilot_steps.md step 2) and clips QVAPOR >= 0. All other fields are
copied unchanged. Replaces the tutorial's add_bank_perts.ncl and the IC part of init_ensemble_var.sh.

Prints, per member, the number of clipped QVAPOR points, and then the ensemble spread by level
compared with the spread of the perturbation files, and writes exp_dir/run/initial_members.txt.
"""

import argparse
import os
import shutil

import netCDF4
import numpy as np

FIELDS = ["U", "V", "THM", "QVAPOR", "MU"]


def write_member(mean_path, pert_path, out_path):
    tmp = out_path + ".tmp"
    shutil.copyfile(mean_path, tmp)
    with netCDF4.Dataset(pert_path) as pert, netCDF4.Dataset(tmp, "a") as out:
        if out["Times"][:].tobytes() != pert["Times"][:].tobytes():
            raise SystemExit(f"time mismatch: {mean_path} vs {pert_path}")
        if out.getncattr("USE_THETA_M") != 0:
            raise SystemExit(f"{mean_path}: USE_THETA_M != 0, T = THM does not hold")
        nclip = 0
        for name in FIELDS:
            field = np.asarray(out[name][:], np.float64) + np.asarray(pert[name][:], np.float64)
            if name == "QVAPOR":
                nclip = int((field < 0).sum())
                field = np.maximum(field, 0.0)
            out[name][:] = field.astype(np.float32)
            if name == "THM":
                out["T"][:] = field.astype(np.float32)
        info = {"draw": int(pert.getncattr("bank_draw")), "centered": int(pert.getncattr("centered"))}
    os.replace(tmp, out_path)
    return nclip, info


def spread_by_level(paths, mean_path, pert_paths):
    """Ensemble std by level from the member files, and from the perturbation files."""
    with netCDF4.Dataset(mean_path) as mean:
        nlev = len(mean.dimensions["bottom_top"])
    print("ensemble spread (std over members, RMS over the horizontal): members | perturbation files")
    levels = [0, 5, 10, 20, 40, 60, 80, 100, 120, nlev - 1]
    for name in FIELDS:
        mem = np.array([np.asarray(netCDF4.Dataset(p)[name][0], np.float64) for p in paths])
        prt = np.array([np.asarray(netCDF4.Dataset(p)[name][0], np.float64) for p in pert_paths])
        sm = np.sqrt(mem.var(axis=0, ddof=1))
        sp = np.sqrt(prt.var(axis=0, ddof=1))
        if mem.ndim == 3:
            print(f"   {name:7s} {np.sqrt((sm ** 2).mean()):9.3g} | {np.sqrt((sp ** 2).mean()):9.3g}")
            continue
        rm = np.sqrt((sm ** 2).mean(axis=(1, 2)))
        rp = np.sqrt((sp ** 2).mean(axis=(1, 2)))
        print(f"   {name:7s} level " + " ".join(f"{k:9d}" for k in levels))
        print("           members " + " ".join(f"{rm[k]:9.3g}" for k in levels))
        print("           perts   " + " ".join(f"{rp[k]:9.3g}" for k in levels))
        print(f"           max |members - perts| over levels: {np.abs(rm - rp).max():.2g}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("exp_dir")
    p.add_argument("--time", default="2025-05-20_00:00:00")
    p.add_argument("--nmem", type=int, default=5)
    args = p.parse_args()

    mean_path = os.path.join(args.exp_dir, "mean", "wrfinput_d01_" + args.time.replace(":", "_"))
    pert_paths = [os.path.join(args.exp_dir, "perts", "members", f"pert_mem{m:03d}.nc")
                  for m in range(1, args.nmem + 1)]
    out_paths = []
    lines = [f"# member bank_draw centered clipped_qvapor   (mean {mean_path})"]
    for m, pert_path in enumerate(pert_paths, start=1):
        mem_dir = os.path.join(args.exp_dir, "run", f"mem{m:03d}")
        os.makedirs(mem_dir, exist_ok=True)
        out_path = os.path.join(mem_dir, "wrfinput_d01")
        nclip, info = write_member(mean_path, pert_path, out_path)
        print(f"mem{m:03d}: draw {info['draw']}, {nclip} QVAPOR points clipped to 0 -> {out_path}")
        lines.append(f"{m:3d} {info['draw']:3d} {info['centered']} {nclip}")
        out_paths.append(out_path)
    with open(os.path.join(args.exp_dir, "run", "initial_members.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    spread_by_level(out_paths, mean_path, pert_paths)


if __name__ == "__main__":
    main()
