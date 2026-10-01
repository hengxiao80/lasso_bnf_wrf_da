"""Turn WRFDA RANDOMCV draws into perturbation-bank files (pilot step 4).

Usage: .venv/bin/python scripts/da/wrfda_bank_diff.py <perts_dir> [draw ...]

For each draw N (default: every perts_dir/work/draw_NNN with a wrfvar_output), writes
perts_dir/bank/pert_bank_NNN.nc = wrfvar_output - fg for U, V, THM, QVAPOR, MU (the tutorial's
fields; notes/da_5member_pilot_steps.md Q16), unscaled. Scaling and centering are done later, when
perturbations are assigned to members. Replaces the tutorial's ncks/ncdiff step in gen_pert_bank.sh.

The file keeps the source dimensions and variable attributes, adds the draw number and the seeds
(read from the draw's namelist.input), and is written as compressed netCDF-4.
"""

import argparse
import glob
import os
import re

import netCDF4
import numpy as np

FIELDS = ["U", "V", "THM", "QVAPOR", "MU"]


def seeds(draw_dir):
    text = open(os.path.join(draw_dir, "namelist.input")).read()
    return {k: int(re.search(rf"{k}\s*=\s*(-?\d+)", text).group(1))
            for k in ("seed_array1", "seed_array2")}


def make_bank_file(draw_dir, out_path):
    fg = netCDF4.Dataset(os.path.join(draw_dir, "fg"))
    an = netCDF4.Dataset(os.path.join(draw_dir, "wrfvar_output"))
    tmp = out_path + ".tmp"
    with netCDF4.Dataset(tmp, "w", format="NETCDF4") as out:
        dims = set()
        for name in FIELDS + ["Times"]:
            dims.update(fg[name].dimensions)
        for d in sorted(dims):
            out.createDimension(d, len(fg.dimensions[d]))
        out.createVariable("Times", fg["Times"].dtype, fg["Times"].dimensions)[:] = fg["Times"][:]
        for name in FIELDS:
            src = fg[name]
            v = out.createVariable(name, "f4", src.dimensions, zlib=True, complevel=2, shuffle=True)
            v.setncatts({a: src.getncattr(a) for a in src.ncattrs()})
            v.description = f"WRFDA RANDOMCV perturbation (wrfvar_output - fg) of {name}"
            d = np.asarray(an[name][:], np.float64) - np.asarray(src[:], np.float64)
            if not np.all(np.isfinite(d)):
                raise ValueError(f"{draw_dir}: non-finite values in {name}")
            v[:] = d.astype(np.float32)
        out.draw_dir = os.path.abspath(draw_dir)
        out.fg = os.path.realpath(os.path.join(draw_dir, "fg"))
        for k, val in seeds(draw_dir).items():
            out.setncattr(k, val)
        out.fields = " ".join(FIELDS)
        for a in ("DX", "DY", "MAP_PROJ", "TRUELAT1", "TRUELAT2", "STAND_LON", "CEN_LAT", "CEN_LON"):
            if a in fg.ncattrs():
                out.setncattr(a, fg.getncattr(a))
    os.replace(tmp, out_path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("perts_dir")
    p.add_argument("draws", nargs="*", type=int)
    args = p.parse_args()

    if args.draws:
        draw_dirs = [os.path.join(args.perts_dir, "work", f"draw_{n:03d}") for n in args.draws]
    else:
        draw_dirs = sorted(glob.glob(os.path.join(args.perts_dir, "work", "draw_[0-9][0-9][0-9]")))
    bank = os.path.join(args.perts_dir, "bank")
    os.makedirs(bank, exist_ok=True)

    for draw_dir in draw_dirs:
        n = int(draw_dir[-3:])
        out = os.path.join(bank, f"pert_bank_{n:03d}.nc")
        if not os.path.exists(os.path.join(draw_dir, "wrfvar_output")):
            print(f"draw {n}: no wrfvar_output, skipped")
            continue
        if os.path.exists(out):
            print(f"draw {n}: {out} exists, skipped")
            continue
        make_bank_file(draw_dir, out)
        print(f"draw {n}: wrote {out} ({os.path.getsize(out) / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
