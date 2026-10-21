"""Filter's wrfinput_d01 (GRID_FILE in experiment.sh): a wrfinput plus state fields it lacks.

Usage: .venv/bin/python scripts/da/make_grid_file.py <wrfinput> <wrfrst> <out> [--add REFL_10CM ...]

DART's WRF model_mod takes the static grid fields from wrfinput_d01 and also uses it as the template
for the state: add_domain('wrfinput_d01', ...) (model_mod.f90:778) reads every state variable's
dimensions and attributes from it. real.exe's wrfinput has no REFL_10CM (a diagnostic, written to
wrfrst only by the patched WRF, patches/wrf_06d4240a_refl_10cm_restart.patch), so filter and
fill_inflation_restart stop with "inq_varid REFL_10CM: NetCDF: Variable not found" (run 1, job
1054633, 2026-10-21). <out> = <wrfinput> unchanged plus each --add variable defined as in <wrfrst>
(dimensions, type, attributes), filled with zeros: only its shape is read, never its values.
"""
import argparse
import os
import shutil

import netCDF4


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wrfinput")
    ap.add_argument("wrfrst", help="restart file from the patched wrf.exe, for the definitions")
    ap.add_argument("out")
    ap.add_argument("--add", nargs="+", default=["REFL_10CM"])
    args = ap.parse_args()

    tmp = args.out + ".tmp"
    shutil.copyfile(args.wrfinput, tmp)
    with netCDF4.Dataset(args.wrfrst) as rst, netCDF4.Dataset(tmp, "a") as out:
        for name in args.add:
            if name in out.variables:
                raise SystemExit(f"{args.wrfinput} already has {name}")
            src = rst[name]
            for d in src.dimensions:
                if d not in out.dimensions or len(out.dimensions[d]) != len(rst.dimensions[d]):
                    raise SystemExit(f"{name}: dimension {d} differs between {args.wrfrst} and {args.wrfinput}")
            v = out.createVariable(name, src.dtype, src.dimensions, zlib=out.data_model == "NETCDF4")
            v.setncatts({a: src.getncattr(a) for a in src.ncattrs()})
            v[:] = 0
            print(f"{name}{src.dimensions} added (zeros)")
    os.replace(tmp, args.out)


if __name__ == "__main__":
    main()
