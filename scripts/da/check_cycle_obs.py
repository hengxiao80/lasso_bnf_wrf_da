"""Check the per-cycle observation directories of an observation set for analysis times first..last (15-min steps).

Usage: .venv/bin/python scripts/da/check_cycle_obs.py <obs set dir> <first YYYYMMDDHHMM> <last YYYYMMDDHHMM>
           [--rawin-dir DIR] [--loop-log LOG]

For sets made by make_cycle_obs.sh with MESONET and MRMS set (e.g. da_common_theta_m0/obs_meso_a_calmkeep_mrms/;
written for A7, notes/fulltest_steps.md). Per time t: every file present; every obs time in obs_seq.out and
obs_seq.joint inside the window (t - 450 s, t + 450 s] (the first and last obs time obs_sequence_tool printed in
counts.log and joint.log; filter stops at an obs after the window, D2's 02:00 cycle, 2026-11-13); the MRMS valid
time in the window; the time slices' bounds equal to it; the totals equal in counts.*, the
preprocessor's and the MRMS converter's logs, joint.log (type by type) and the three files' num_obs; radiosonde
status as expected from the obs time stamps in the hourly radiosonde files (--rawin-dir, default
<case>/obs/obs_seq_madis/rawin, two levels above the set); no error-like log line beyond the known ones (boundary
error inflation, the slices' bounds, the radiosonde slice's "all obs excluded" where expected). With --loop-log
(a log of make_obs_loop.sh, or of A7's a7_loop.sh, which wrote the same lines): its three lines for t (33 MRMS
levels, the MRMS and window/screened totals). Then a table of counts per family per time, per-type ranges, and the problems found.
"""
import argparse
import glob
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("obs_dir")
ap.add_argument("first")
ap.add_argument("last")
ap.add_argument("--rawin-dir")
ap.add_argument("--loop-log")
args = ap.parse_args()
obs_dir, first, last, loop_log = args.obs_dir, args.first, args.last, args.loop_log
rawin_dir = args.rawin_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(obs_dir))),
                                           "obs", "obs_seq_madis", "rawin")
FMT = "%Y%m%d%H%M"
HALF = timedelta(seconds=450)
EPOCH = datetime(1601, 1, 1)  # DART gregorian day 0

FILES = ["obs_seq.out", "obs_seq.mrms", "obs_seq.joint", "counts.window", "counts.out", "counts.mrms",
         "counts.log", "preprocess.log", "mesonet.log", "mrms.log", "joint.log",
         "slice.metar.log", "slice.acars.log", "slice.marine.log"]

ERRLIKE = re.compile(r"error|warn|fail|fatal|abort|exclud|\bstop\b|\bnan\b|infinit", re.I)
ALLOWED = [re.compile(p) for p in (
    r"Increasing the Observation Error Near the Lateral Boundary",
    r"error inflated near the boundary for \d+",
    r"Excluding observations (before|\s?after): day=\d+, sec=\d+",
)]
RAWIN_EXCLUDED = "All input files are empty or all obs excluded"


def dart_time(day, sec):
    return EPOCH + timedelta(days=int(day), seconds=int(sec))


def read_counts(path, ncol):
    """Type -> count from 'TYPE N' (ncol 2) or 'family TYPE N' (ncol 3) lines; other lines returned apart."""
    d, other = {}, []
    for line in open(path):
        w = line.split()
        if len(w) == ncol and w[-1].isdigit():
            d[w[-2]] = d.get(w[-2], 0) + int(w[-1])
        elif line.strip():
            other.append(line.strip())
    return d, other


def header_num_obs(path):
    with open(path) as f:
        for _ in range(200):
            m = re.search(r"num_obs:\s*(\d+)", f.readline())
            if m:
                return int(m.group(1))
    return None


def tool_types(path):
    """Per-type counts of obs_sequence_tool's last 'obs' table in a log."""
    d = {}
    for line in open(path):
        m = re.match(r"\s*([A-Z0-9_]+)\s+(\d+) obs\s*$", line)
        if m:
            d[m.group(1)] = int(m.group(2))
    return d


def family(typ):
    for p, f in (("METAR_", "metar"), ("ACARS_", "acars"), ("LAND_SFC_", "mesonet"), ("MARINE_SFC_", "marine"),
                 ("RADIOSONDE_", "rawin"), ("RADAR_REFLECTIVITY", "refl"), ("RADAR_CLEARAIR", "clear")):
        if typ.startswith(p):
            return f
    return "other"


# Radiosonde hourly files: obs time stamps (seconds days) per file.
rawin = {}
for f in sorted(glob.glob(os.path.join(rawin_dir, "obs_seq.rawin.*"))):
    stamps = defaultdict(int)
    for line in open(f):
        m = re.match(r"^\s*(\d+)\s+(15[45]\d\d\d)\s*$", line)
        if m:
            stamps[dart_time(m.group(2), m.group(1))] += 1
    rawin[os.path.basename(f).split(".")[-1]] = dict(stamps)
print("radiosonde files:", {k: {str(t): n for t, n in v.items()} for k, v in rawin.items()})

# Loop log: lines per time.
loop = defaultdict(list)
cur = None
for line in open(loop_log) if loop_log else []:
    m = re.match(r"=== (\d{12}) start", line)
    if m:
        cur = m.group(1)
        continue
    if re.match(r"(A7 )?LOOP (DONE|FAILED)", line):
        print("loop log:", line.rstrip())
        cur = None
    elif cur:
        loop[cur].append(line.rstrip())

t, t_end = datetime.strptime(first, FMT), datetime.strptime(last, FMT)
rows, ranges, problems, span = [], defaultdict(list), [], defaultdict(list)
while t <= t_end:
    s = t.strftime(FMT)
    d = os.path.join(obs_dir, s)
    bad = []
    missing = [f for f in FILES if not os.path.isfile(os.path.join(d, f)) or os.path.getsize(os.path.join(d, f)) == 0]
    if missing:
        problems.append(f"{s}: missing or empty {missing}")
        t += timedelta(minutes=15)
        continue

    win, win_other = read_counts(os.path.join(d, "counts.window"), 3)
    out, _ = read_counts(os.path.join(d, "counts.out"), 2)
    mrms, _ = read_counts(os.path.join(d, "counts.mrms"), 2)
    n_out, n_mrms = sum(out.values()), sum(mrms.values())

    # MRMS valid time and output path.
    mlog = open(os.path.join(d, "mrms.log")).read()
    m = re.search(r"analysis ([\d-]+ [\d:]+), MRMS valid ([\d-]+ [\d:]+)", mlog)
    ta, tv = (datetime.strptime(x, "%Y-%m-%d %H:%M:%S") for x in m.groups())
    off = (tv - t).total_seconds()
    if ta != t or not (-450 < off <= 450):
        bad.append(f"MRMS analysis {ta} valid {tv} (offset {off:+.0f} s)")
    m = re.search(r"wrote (\d+) obs to (\S+)", mlog)
    if int(m.group(1)) != n_mrms:
        bad.append(f"mrms.log wrote {m.group(1)} != counts.mrms {n_mrms}")
    if os.path.realpath(os.path.dirname(m.group(2))) != os.path.realpath(d):
        bad.append(f"mrms.log path {m.group(2)}")

    # Totals across logs and headers.
    m = re.search(r"Total number of observations:\s*(\d+)", open(os.path.join(d, "preprocess.log")).read())
    if not m or int(m.group(1)) != n_out:
        bad.append(f"preprocess total {m and m.group(1)} != counts.out {n_out}")
    joint = tool_types(os.path.join(d, "joint.log"))
    if joint != {**out, **mrms}:
        bad.append("joint.log types != counts.out + counts.mrms")
    if "Finished successfully" not in open(os.path.join(d, "joint.log")).read():
        bad.append("joint.log not finished")
    for f, n in (("obs_seq.out", n_out), ("obs_seq.mrms", n_mrms), ("obs_seq.joint", n_out + n_mrms)):
        h = header_num_obs(os.path.join(d, f))
        if h != n:
            bad.append(f"{f} header num_obs {h} != {n}")

    # Every obs time inside the window: first and last obs time of obs_seq.out and obs_seq.joint.
    for f, log in (("obs_seq.out", "counts.log"), ("obs_seq.joint", "joint.log")):
        m = re.search(r"Processing sequence file \S*%s\s.*?First obs time: day=\s*(\d+),\s*sec=\s*(\d+)"
                      r".*?Last obs time: day=\s*(\d+),\s*sec=\s*(\d+)" % re.escape(f),
                      open(os.path.join(d, log)).read(), re.S)
        if not m:
            bad.append(f"{log}: no first/last obs time of {f}")
            continue
        o1 = (dart_time(*m.groups()[:2]) - t).total_seconds()
        o2 = (dart_time(*m.groups()[2:]) - t).total_seconds()
        span[f].append((o1, o2))
        if not (-HALF.total_seconds() < o1 <= o2 <= HALF.total_seconds()):
            bad.append(f"{f}: obs times {o1:+.0f} to {o2:+.0f} s from t, outside the window")

    # Slice bounds = the window (t - 450 s, t + 450 s].
    for fam in ("metar", "acars", "marine", "rawin"):
        p = os.path.join(d, f"slice.{fam}.log")
        if not os.path.isfile(p):
            continue
        txt = open(p).read()
        b = re.search(r"Excluding observations before: day=(\d+), sec=(\d+)", txt)
        a = re.search(r"Excluding observations\s+after: day=(\d+), sec=(\d+)", txt)
        if not (b and a and dart_time(*b.groups()) == t - HALF + timedelta(seconds=1)
                and dart_time(*a.groups()) == t + HALF):
            bad.append(f"slice.{fam}.log bounds")

    # Radiosondes: expected from the hourly files of t - 1 h, t, t + 1 h and their stamps in the window.
    files = [(t + timedelta(hours=dh)).strftime("%Y%m%d_%H00") for dh in (-1, 0, 1)]
    files = [f for f in files if f in rawin]
    exp_n = sum(n for f in files for ts, n in rawin[f].items() if t - HALF < ts <= t + HALF)
    exp = "no hourly file" if not files else ("0 in window" if exp_n == 0 else exp_n)
    got_n = sum(n for k, n in win.items() if family(k) == "rawin")
    got = ("no hourly file" if "rawin: no hourly file" in win_other else
           "0 in window" if "rawin: 0 in window" in win_other else got_n)
    if got != exp:
        bad.append(f"radiosonde {got!r}, expected {exp!r}")
    rawin_status = got if isinstance(got, str) else f"{got} obs"

    # Error-like lines.
    logs = glob.glob(os.path.join(d, "*.log")) + glob.glob(os.path.join(d, "*", "dart_log.out"))
    for p in logs:
        for line in open(p, errors="replace"):
            if not ERRLIKE.search(line) or any(a.search(line) for a in ALLOWED):
                continue
            if (os.path.basename(p) == "slice.rawin.log" and got == "0 in window"
                    and (RAWIN_EXCLUDED in line or line.strip() == "ERROR FROM:")):
                continue  # DART's error block for "all obs excluded" (the expected case)
            if os.path.basename(p) == "dart_log.out" and RAWIN_EXCLUDED in line:
                continue  # slice/dart_log.out repeats the last family's message
            bad.append(f"{os.path.relpath(p, d)}: {line.strip()[:120]}")

    # Loop log lines for t.
    ll = loop.get(s, [])
    want = [r"download_mrms\.sh: %s: 33 levels at \d{8}-\d{6} in \S+" % s,
            r"make_cycle_obs\.sh: %s: MRMS %d obs \(\S+ \S+\)" % (s, n_mrms),
            r"make_cycle_obs\.sh: %s: window %d, screened %d obs" % (s, sum(win.values()), n_out)]
    if loop_log and (len(ll) != 3 or not all(re.fullmatch(w, l) for w, l in zip(want, ll))):
        bad.append(f"loop log lines: {ll}")

    for k, n in {**out, **mrms}.items():
        ranges[k].append((n, s))
    fam = defaultdict(int)
    for k, n in out.items():
        fam[family(k)] += n
    rows.append((s, off, sum(win.values()), n_out, fam["metar"], fam["acars"], fam["mesonet"], fam["marine"],
                 fam["rawin"], mrms.get("RADAR_REFLECTIVITY", 0), mrms.get("RADAR_CLEARAIR_REFLECTIVITY", 0),
                 n_out + n_mrms, rawin_status))
    problems += [f"{s}: {b}" for b in bad]
    t += timedelta(minutes=15)

print(f"\n{'time':12} {'mrms':>5} {'window':>6} {'screen':>6} {'metar':>5} {'acars':>5} {'meso':>5} {'marin':>5}"
      f" {'raob':>5} {'refl':>6} {'clear':>5} {'joint':>6}  radiosonde")
for r in rows:
    print(f"{r[0]:12} {r[1]:+5.0f} {r[2]:6d} {r[3]:6d} {r[4]:5d} {r[5]:5d} {r[6]:5d} {r[7]:5d} {r[8]:5d}"
          f" {r[9]:6d} {r[10]:5d} {r[11]:6d}  {r[12]}")
print(f"\n{len(rows)} times checked")
print("\nper type after screening (min at, max at, times present):")
for k in sorted(ranges):
    v = ranges[k]
    lo, hi = min(v), max(v)
    print(f"  {k:34} {lo[0]:6d} {lo[1]}  {hi[0]:6d} {hi[1]}  {len(v)}")
for c, i in (("window", 2), ("screened", 3), ("refl", 9), ("clear", 10), ("joint", 11)):
    v = [r[i] for r in rows]
    print(f"{c}: {min(v)}-{max(v)}")
offs = sorted({int(r[1]) for r in rows})
print("MRMS offsets (s):", offs)
for f, v in span.items():
    print(f"{f}: obs times from {min(o for o, _ in v):+.0f} to {max(o for _, o in v):+.0f} s around t")
print("\nPROBLEMS:" if problems else "\nno problems found")
for p in problems:
    print("  " + p)
