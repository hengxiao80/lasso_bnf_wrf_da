"""Assign perturbation-bank draws to ensemble members (pilot step 4).

Usage: .venv/bin/python scripts/da/assign_perturbations.py <perts_dir> [--nmem 5] [--seed 20250520]
                                                          [--no-center]

- Picks nmem distinct draws at random from perts_dir/bank/pert_bank_NNN.nc with a fixed seed
  (the tutorial picks at random too, but per call and with possible repeats; here the pick is made
  once and saved, so it is reproducible and the same for the initial state and every boundary hour).
- Scales them as the tutorial's add_bank_perts.ncl: 1.3 for U, V, THM, QVAPOR and 0.6 for MU (Q3).
- Centers them (subtracts the mean of the nmem scaled perturbations, Q4) unless --no-center.
- Writes perts_dir/members/pert_memNNN.nc and perts_dir/assignment.txt, and prints per-member RMS.
See notes/da_5member_pilot_steps.md step 4.
"""

import argparse
import os

import netCDF4
import numpy as np

SCALE = {"U": 1.3, "V": 1.3, "THM": 1.3, "QVAPOR": 1.3, "MU": 0.6}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("perts_dir")
    p.add_argument("--nmem", type=int, default=5)
    p.add_argument("--seed", type=int, default=20250520)
    p.add_argument("--no-center", action="store_true")
    args = p.parse_args()

    bank_dir = os.path.join(args.perts_dir, "bank")
    draws = sorted(int(f[10:13]) for f in os.listdir(bank_dir)
                   if f.startswith("pert_bank_") and f.endswith(".nc"))
    rng = np.random.default_rng(args.seed)
    picked = [int(d) for d in rng.choice(draws, size=args.nmem, replace=False)]
    center = not args.no_center

    srcs = [netCDF4.Dataset(os.path.join(bank_dir, f"pert_bank_{d:03d}.nc")) for d in picked]
    out_dir = os.path.join(args.perts_dir, "members")
    os.makedirs(out_dir, exist_ok=True)
    outs = []
    for m, (d, src) in enumerate(zip(picked, srcs), start=1):
        path = os.path.join(out_dir, f"pert_mem{m:03d}.nc")
        out = netCDF4.Dataset(path + ".tmp", "w", format="NETCDF4")
        for name, dim in src.dimensions.items():
            out.createDimension(name, len(dim))
        out.createVariable("Times", src["Times"].dtype, src["Times"].dimensions)[:] = src["Times"][:]
        out.setncatts({a: src.getncattr(a) for a in src.ncattrs()})
        out.setncatts({"member": m, "bank_draw": d,
                       "scale_factors": " ".join(f"{k}={v}" for k, v in SCALE.items()),
                       "centered": int(center), "assignment_seed": args.seed})
        outs.append((path, out))

    print(f"members <- draws {picked} (seed {args.seed}, centered={center})")
    print("RMS per member (after scaling" + (" and centering)" if center else ")"))
    for name, fac in SCALE.items():
        stack = np.array([np.asarray(s[name][:], np.float64) * fac for s in srcs])
        mean = stack.mean(axis=0)
        if center:
            stack -= mean
        for (path, out), field, src in zip(outs, stack, srcs):
            v = out.createVariable(name, "f4", src[name].dimensions, zlib=True, complevel=2, shuffle=True)
            v.setncatts({a: src[name].getncattr(a) for a in src[name].ncattrs()})
            v[:] = field.astype(np.float32)
        rms = np.sqrt((stack ** 2).mean(axis=tuple(range(1, stack.ndim))))
        print(f"   {name:7s} " + " ".join(f"{r:9.3g}" for r in rms)
              + f"   |sum over members| max {np.abs(stack.sum(axis=0)).max():.2g}")

    for path, out in outs:
        out.close()
        os.replace(path + ".tmp", path)

    with open(os.path.join(args.perts_dir, "assignment.txt"), "w") as f:
        f.write(f"# member bank_draw   (seed {args.seed}; scale "
                + " ".join(f"{k}={v}" for k, v in SCALE.items())
                + f"; centered={int(center)})\n")
        for m, d in enumerate(picked, start=1):
            f.write(f"{m:3d} {d:3d}\n")
    print(f"wrote {out_dir}/pert_memNNN.nc and {args.perts_dir}/assignment.txt")


if __name__ == "__main__":
    main()
