"""Profile one hourly public-MADIS mesonet file inside the domain's lat/lon box.

Usage: profile_madis_mesonet.py <mesonet.nc or .gz> [<metar.nc or .gz>]

Prints, for the records in the box (the box of convert_madis_hour.sh): stations and reports per
provider, MADIS QC (DD summary and QCR bits) per variable and provider, the minute-of-hour spread,
reports per station inside the two cycle windows (t +- 7.5 min) centred in the hour (HH:15, HH:30)
and, with a METAR file of the same hour, the mesonet stations that are also METAR stations.
A QCR of 0 is what convert_madis_mesonet accepts (use_input_qc = .true.).
"""
import collections
import gzip
import os
import sys
import tempfile

import netCDF4 as nc
import numpy as np

MIN_LAT, MAX_LAT, MIN_LON, MAX_LON = 30.36, 39.37, 262.52, 278.38
VARS = ["temperature", "dewpoint", "windSpeed", "windDir", "altimeter"]


def open_madis(path):
    if path.endswith(".gz"):
        tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        with gzip.open(path) as src:
            tmp.write(src.read())
        tmp.close()
        f = nc.Dataset(tmp.name)
        os.unlink(tmp.name)  # the open handle keeps the data readable
    else:
        f = nc.Dataset(path)
    f.set_auto_mask(False)
    return f


def strings(f, name):
    return np.array([b"".join(r).decode(errors="replace").strip() for r in f[name][:]])


def in_box(f):
    lat = f["latitude"][:]
    lon = f["longitude"][:] % 360.0
    return (lat >= MIN_LAT) & (lat <= MAX_LAT) & (lon >= MIN_LON) & (lon <= MAX_LON)


def main():
    f = open_madis(sys.argv[1])
    box = in_box(f)
    sid = strings(f, "stationId")[box]
    prov = strings(f, "dataProvider")[box]
    minute = (f["observationTime"][:][box] % 3600) / 60.0
    print(f"records {box.size}, in box {box.sum()}, stations {len(set(sid))}")
    n = np.array(list(collections.Counter(sid).values()))
    print(f"reports per station in the hour: 10/50/90 % {np.percentile(n, [10, 50, 90])}, max {n.max()}")

    stations = collections.defaultdict(set)
    for p, s in zip(prov, sid):
        stations[p].add(s)
    print("\nprovider      reports stations")
    for p, k in collections.Counter(prov).most_common():
        print(f"  {p:12s} {k:7d} {len(stations[p]):7d}")

    ok = {}
    print("\nvariable    present  QCR=0  DD counts / QCR bits set (bit 1 = master)")
    for v in VARS:
        present = f[v][:][box] != f[v].getncattr("_FillValue")
        qcr = f[v + "QCR"][:][box]
        ok[v] = present & (qcr == 0)
        dd = f[v + "DD"][:][box].astype("U1")
        bits = {b + 1: int(((qcr[present] >> b) & 1).sum()) for b in range(10)}
        print(f"  {v:10s} {present.sum():7d} {ok[v].sum():6d}  "
              f"{dict(collections.Counter(dd[present]).most_common())}  "
              f"{ {b: k for b, k in bits.items() if k} }")
        by = {p: (int((present & (prov == p)).sum()), int((ok[v] & (prov == p)).sum()))
              for p in stations}
        top = sorted(by.items(), key=lambda kv: -kv[1][0])[:6]
        print("    present / QCR=0 by provider:", ", ".join(f"{p} {a}/{b}" for p, (a, b) in top))

    print("\nminute-of-hour of QCR=0 temperature reports (5-min bins), main providers:")
    for p, _ in collections.Counter(prov).most_common(5):
        h = np.histogram(minute[ok["temperature"] & (prov == p)], bins=np.arange(0, 61, 5))[0]
        print(f"  {p:12s} {h}")

    print("\nQCR=0 temperature reports per station in a cycle window:")
    for centre in (15.0, 30.0):
        for half in (7.5, 6.0):
            w = (minute > centre - half) & (minute <= centre + half) & ok["temperature"]
            per = collections.Counter(collections.Counter(sid[w]).values())
            print(f"  HH:{centre:02.0f} +-{half} min: reports {w.sum()}, stations "
                  f"{sum(per.values())}, stations by reports {dict(sorted(per.items()))}")

    if len(sys.argv) > 2:
        m = open_madis(sys.argv[2])
        metar_ids = set(strings(m, "stationName")[in_box(m)])
        dup = sorted({s for s in sid if s in metar_ids})
        dup_prov = collections.Counter(p for p, s in set(zip(prov, sid)) if s in metar_ids)
        print(f"\nMETAR stations in box {len(metar_ids)}; mesonet stations with a METAR id: "
              f"{len(dup)} {dict(dup_prov)}")


if __name__ == "__main__":
    main()
