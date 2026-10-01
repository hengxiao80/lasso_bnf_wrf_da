"""Check one WRFDA RANDOMCV draw against its first guess (pilot step 3 gate).

Usage: .venv/bin/python scripts/da/check_wrfda_draw.py <draw_dir> [--every N]

Reads <draw_dir>/fg and <draw_dir>/wrfvar_output and reports:
- which variables differ between the two files (expected: the CV3-analyzed fields only);
- whether T and THM are consistent in the output (they should be equal at use_theta_m = 0);
- the perturbation (output - fg) RMS by model level for U, V, THM, QVAPOR, with the level's mean
  height, plus the MU RMS;
- a horizontal correlation length for U, THM and QVAPOR at a few levels: the distance where the
  isotropic autocorrelation of the perturbation (from its 2-D FFT power spectrum) first drops below 1/e.
"""

import argparse
import os

import netCDF4
import numpy as np

G = 9.81


def read(ds, name):
    return np.asarray(ds[name][0], dtype=np.float64)


def destagger(a, name):
    if name == "U":
        return 0.5 * (a[..., :-1] + a[..., 1:])
    if name == "V":
        return 0.5 * (a[..., :-1, :] + a[..., 1:, :])
    return a


def corr_length(field2d, dx_km):
    """Distance (km) where the isotropic autocorrelation first falls below 1/e."""
    f = field2d - field2d.mean()
    ny, nx = f.shape
    spec = np.abs(np.fft.fft2(f, s=(2 * ny, 2 * nx))) ** 2  # zero-padded: non-periodic
    acf = np.real(np.fft.ifft2(spec))
    acf /= acf[0, 0]
    iy = np.minimum(np.arange(2 * ny), 2 * ny - np.arange(2 * ny))
    ix = np.minimum(np.arange(2 * nx), 2 * nx - np.arange(2 * nx))
    r = np.sqrt(iy[:, None] ** 2 + ix[None, :] ** 2)
    rbin = np.rint(r).astype(int)
    nmax = min(ny, nx) // 2
    mask = rbin < nmax
    sums = np.bincount(rbin[mask], weights=acf[mask], minlength=nmax)
    counts = np.bincount(rbin[mask], minlength=nmax)
    prof = sums / np.maximum(counts, 1)
    below = np.nonzero(prof < np.exp(-1.0))[0]
    return below[0] * dx_km if below.size else np.nan


def main():
    p = argparse.ArgumentParser()
    p.add_argument("draw_dir")
    p.add_argument("--every", type=int, default=10, help="print every N-th level")
    args = p.parse_args()

    fg = netCDF4.Dataset(os.path.join(args.draw_dir, "fg"))
    an = netCDF4.Dataset(os.path.join(args.draw_dir, "wrfvar_output"))
    dx_km = fg.DX / 1000.0

    print("== Variables that differ (max |output - fg|):")
    for name, var in an.variables.items():
        if name not in fg.variables or var.dtype.kind not in "fi" or var.ndim < 2:
            continue
        d = np.abs(np.asarray(var[:], np.float64) - np.asarray(fg[name][:], np.float64))
        if np.nanmax(d) > 0:
            print(f"   {name:12s} {np.nanmax(d):.4g}")

    print("\n== T vs THM in the output (use_theta_m = 0: should be equal)")
    t_an, thm_an = read(an, "T"), read(an, "THM")
    print(f"   max |T - THM| output = {np.abs(t_an - thm_an).max():.4g} K;"
          f"  fg = {np.abs(read(fg, 'T') - read(fg, 'THM')).max():.4g} K")
    print(f"   max |T_out - T_fg| = {np.abs(t_an - read(fg, 'T')).max():.4g} K;"
          f"  max |THM_out - THM_fg| = {np.abs(thm_an - read(fg, 'THM')).max():.4g} K")

    z = (read(fg, "PH") + read(fg, "PHB")) / G
    zmass = 0.5 * (z[:-1] + z[1:]) - read(fg, "HGT")[None]
    zmean = zmass.mean(axis=(1, 2))

    pert = {}
    for name in ["U", "V", "THM", "QVAPOR"]:
        pert[name] = destagger(read(an, name) - read(fg, name), name)
    qv_fg = read(fg, "QVAPOR")

    print("\n== Perturbation RMS by level (output - fg)")
    print("   lev   z_agl(m)   U(m/s)   V(m/s)  THM(K)  QV(g/kg)  QV/QV_fg(%)")
    nz = zmean.size
    levels = sorted(set(list(range(0, nz, args.every)) + [nz - 1]))
    for k in levels:
        rms = {n: np.sqrt(np.mean(pert[n][k] ** 2)) for n in pert}
        rel = 100 * np.sqrt(np.mean(pert["QVAPOR"][k] ** 2)) / max(qv_fg[k].mean(), 1e-12)
        print(f"   {k:3d} {zmean[k]:10.0f} {rms['U']:8.3f} {rms['V']:8.3f} {rms['THM']:7.3f}"
              f" {1000 * rms['QVAPOR']:9.4f} {rel:11.2f}")
    for n in pert:
        print(f"   column-max RMS {n}: {max(np.sqrt(np.mean(pert[n][k] ** 2)) for k in range(nz)):.4g}")
    dmu = read(an, "MU") - read(fg, "MU")
    print(f"   MU RMS = {np.sqrt(np.mean(dmu ** 2)):.4g} Pa, max |dMU| = {np.abs(dmu).max():.4g} Pa")

    print(f"\n== Horizontal correlation length (1/e), km (dx = {dx_km:g} km)")
    print("   lev   z_agl(m)      U    THM     QV")
    for k in [k for k in (5, 30, 60, 90, 120) if k < nz]:
        print(f"   {k:3d} {zmean[k]:10.0f} " + " ".join(
            f"{corr_length(pert[n][k], dx_km):6.0f}" for n in ("U", "THM", "QVAPOR")))


if __name__ == "__main__":
    main()
