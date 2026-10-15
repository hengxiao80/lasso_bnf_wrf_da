#!/usr/bin/env python3
"""Per-cycle timing of a cycling run (slurm.cycle -> driver.sh), with the filter cost broken down.

From output<RUN_NAME>/<t>/cycle.log (cycle_job.sh, post_filter.sh) and each pass's filter.log
(output<RUN_NAME>/<t>/filter/ and, in two-pass runs, filter_mrms/; DART's "TIME:" lines), per cycle:
  filter   per pass: wall (cycle_job.sh: prep_filter + srun filter), and from filter.log the
           phases read (restart files in), H(x) (prior observation values), assim (the serial
           observation loop) with the number of obs and ms per obs, and the rest (state output,
           posterior H(x), obs_seq.final); one-pass/no-MRMS runs have one pass.
  update   post_filter members (insert, qnrain, boundary refit), from the filter's end
  advance  wrf.exe for all members (concurrent), from "members updated"
  total    cycle_job.sh's "complete in"
With --slurm-out slurm.cycle.<job>.out: each filter step's Elapsed and MaxRSS (peak per task) from
the sacct table at its end, in order (a resumed run has several job logs; give the one to look at).

Usage:
    .venv/bin/python scripts/da/summarize_cycle_timing.py cases/20250520/da_theta_m0/output_hph \
        [--slurm-out cases/20250520/da_theta_m0/slurm.cycle.1047842.out]
"""

import argparse
import datetime as dt
import os
import re
import sys

ISO = re.compile(r'^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d) (.*)$')
FILTER_DONE = re.compile(r'filter (?:\((\w+)\) )?done in (\d+) s')
COMPLETE = re.compile(r'complete in (\d+) s')
DART_TIME = re.compile(r'^\s*(.*?)\s+TIME: (\d{4}/\d\d/\d\d \d\d:\d\d:\d\d)')
NOBS = re.compile(r'Processing observation\s+\d+ of\s+(\d+)')
SACCT = re.compile(r'^\s*\d+\.\d+\s+filter\s+(\S+)\s+\d+\s+\d+\s+(\S+)\s+(\S+)')


def secs(a, b):
    return (b - a).total_seconds()


def cycle_log(path):
    ev = {'filter': {}}
    for line in open(path, errors='replace'):
        m = ISO.match(line)
        if not m:
            continue
        ts, msg = dt.datetime.fromisoformat(m.group(1)), m.group(2)
        f = FILTER_DONE.search(msg)
        if f:
            ev['filter'][f.group(1) or 'conv'] = int(f.group(2))
            ev['filter_end'] = ts
        elif 'members updated' in msg:
            ev['updated'] = ts
        elif 'members advanced' in msg:
            ev['advanced'] = ts
        elif COMPLETE.search(msg):
            ev['total'] = int(COMPLETE.search(msg).group(1))
            ev['complete'] = ts
    return ev


def filter_phases(path):
    """read / H(x) / assim / rest seconds and the obs count from DART's TIME lines."""
    t, nobs = {}, None
    for line in open(path, errors='replace'):
        m = DART_TIME.match(line)
        if m:
            t.setdefault(m.group(1), dt.datetime.strptime(m.group(2), '%Y/%m/%d %H:%M:%S'))
        m = NOBS.search(line)
        if m:
            nobs = int(m.group(1))
    try:
        p = {'read': secs(t['Before reading in ensemble restart files'], t['After  reading in ensemble restart files']),
             'hx': secs(t['Before computing prior observation values'], t['After  computing prior observation values']),
             'assim': secs(t['Before observation assimilation'], t['After  observation assimilation']),
             'dart': secs(t['Filter start'], t['Filter done'])}
    except KeyError:
        return None
    p['rest'] = p['dart'] - p['read'] - p['hx'] - p['assim']
    p['nobs'] = nobs
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('output_dir')
    ap.add_argument('--slurm-out')
    a = ap.parse_args()

    cycles = sorted(d for d in os.listdir(a.output_dir) if re.fullmatch(r'\d{12}', d))
    print(f'{a.output_dir}')
    print(f'{"cycle":>12} {"pass":>5} {"filter":>6} {"read":>5} {"H(x)":>5} {"assim":>6} {"nobs":>7} '
          f'{"ms/ob":>6} {"rest":>5} {"update":>6} {"advance":>7} {"total":>6}')
    for c in cycles:
        log = os.path.join(a.output_dir, c, 'cycle.log')
        if not os.path.exists(log):
            continue
        ev = cycle_log(log)
        upd = adv = '-'
        if 'updated' in ev and 'filter_end' in ev:
            upd = f'{secs(ev["filter_end"], ev["updated"]):.0f}'
        start = ev.get('updated') or (ev['complete'] - dt.timedelta(seconds=ev['total']) if 'complete' in ev else None)
        if start and 'advanced' in ev:
            adv = f'{secs(start, ev["advanced"]):.0f}'
        tot = ev.get('total', '-')
        passes = ev['filter'] or {'-': None}
        for i, (ps, wall) in enumerate(passes.items()):
            sub = 'filter' if ps in ('conv', '-') else 'filter_mrms'
            fl = os.path.join(a.output_dir, c, sub, 'filter.log')
            p = filter_phases(fl) if ps != '-' and os.path.exists(fl) else None
            row = f'{c:>12} {ps:>5} {wall if wall is not None else "-":>6} '
            if p:
                mspo = f'{1000 * p["assim"] / p["nobs"]:.1f}' if p['nobs'] else '-'
                row += (f'{p["read"]:5.0f} {p["hx"]:5.0f} {p["assim"]:6.0f} {p["nobs"] or "-":>7} {mspo:>6} '
                        f'{p["rest"]:5.0f} ')
            else:
                row += f'{"-":>5} {"-":>5} {"-":>6} {"-":>7} {"-":>6} {"-":>5} '
            last = i == len(passes) - 1
            row += f'{upd if last else "":>6} {adv if last else "":>7} {tot if last else "":>6}'
            print(row)
    print('seconds; filter = prep_filter + srun filter (cycle_job.sh); read/H(x)/assim/rest from filter.log; '
          'update = post_filter members; advance = wrf.exe, all members')

    if a.slurm_out:
        steps = [SACCT.match(l) for l in open(a.slurm_out, errors='replace')]
        steps = [m.groups() for m in steps if m]
        print(f'\n{a.slurm_out}: filter steps in order (Elapsed, MaxRSS per task, State)')
        for i, (el, rss, st) in enumerate(steps, 1):
            print(f'{i:>3} {el:>9} {rss:>10} {st}')


if __name__ == '__main__':
    sys.exit(main())
