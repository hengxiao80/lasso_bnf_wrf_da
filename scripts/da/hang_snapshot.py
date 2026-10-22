#!/usr/bin/env python3
"""Snapshot of a hung MPI program's processes on this node (exit hang investigation, notes/filter_exit_hang.md).

Per thread of every process of the program owned by the user: kernel state, CPU use and context switches
over 1 s, kernel wait channel, the MPI rank (SLURM_PROCID from /proc/<pid>/environ). Then, if perf works,
call stacks sampled for a few seconds (user space only, DWARF unwinding), folded per rank and thread.
ptrace is not permitted on the nodes (kernel.yama.ptrace_scope = 2), so no gdb; perf needs only the
weaker read check, and kernel.perf_event_paranoid = 2 allows user-space sampling of one's own processes.

Run as one task per node, inside the job, alongside the hung step:
    srun --overlap -N <nodes> --ntasks-per-node=1 -c 4 .venv/bin/python scripts/da/hang_snapshot.py <outdir> filter

Writes <outdir>/<node>.proc.txt (one line per thread) and <outdir>/<node>.folded
(rank thread samples stack, stack outermost frame first, ';'-separated); summarize with hang_summary.py.
"""

import argparse
import collections
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time


def find_procs(name):
    uid = os.getuid()
    pids = []
    for p in os.listdir('/proc'):
        if not p.isdigit():
            continue
        try:
            if os.stat(f'/proc/{p}').st_uid != uid:
                continue
            with open(f'/proc/{p}/comm') as f:
                if f.read().strip() != name:
                    continue
        except OSError:
            continue
        pids.append(int(p))
    return sorted(pids)


def rank_of(pid):
    try:
        with open(f'/proc/{pid}/environ', 'rb') as f:
            env = f.read().split(b'\0')
    except OSError:
        return -1
    env = dict(e.split(b'=', 1) for e in env if b'=' in e)
    for k in (b'SLURM_PROCID', b'OMPI_COMM_WORLD_RANK', b'PMI_RANK'):
        if k in env:
            return int(env[k])
    return -1


def read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return '?'


def threads(pid):
    """{tid: dict(comm, state, ticks, cpu, vcsw, nvcsw, wchan)}"""
    res = {}
    try:
        tids = os.listdir(f'/proc/{pid}/task')
    except OSError:
        return res
    for t in tids:
        stat = read(f'/proc/{pid}/task/{t}/stat')
        if stat == '?':
            continue
        f = stat[stat.rindex(')') + 2:].split()      # f[0] is field 3 (state)
        status = read(f'/proc/{pid}/task/{t}/status')
        sw = dict(re.findall(r'^(\w+ctxt_switches):\s+(\d+)', status, re.M))
        res[int(t)] = dict(comm=stat[stat.index('(') + 1:stat.rindex(')')], state=f[0],
                           ticks=int(f[11]) + int(f[12]), cpu=f[36],
                           vcsw=int(sw.get('voluntary_ctxt_switches', 0)),
                           nvcsw=int(sw.get('nonvoluntary_ctxt_switches', 0)),
                           wchan=read(f'/proc/{pid}/task/{t}/wchan') or '0')
    return res


def proc_snapshot(pids, ranks):
    hz = os.sysconf('SC_CLK_TCK')
    t0 = {p: threads(p) for p in pids}
    w0 = time.time()
    time.sleep(1.0)
    t1 = {p: threads(p) for p in pids}
    dt = time.time() - w0
    lines = ['rank pid tid thread state cpu% vcsw/s nvcsw/s core wchan']
    for p in pids:
        for tid, b in sorted(t1[p].items()):
            a = t0[p].get(tid, b)
            lines.append(f'{ranks[p]} {p} {tid} {b["comm"].replace(" ", "_")} {b["state"]} '
                         f'{100 * (b["ticks"] - a["ticks"]) / hz / dt:.0f} '
                         f'{(b["vcsw"] - a["vcsw"]) / dt:.0f} {(b["nvcsw"] - a["nvcsw"]) / dt:.0f} '
                         f'{b["cpu"]} {b["wchan"]}')
    return lines


def fold(text, pids, ranks):
    """perf script output (comm pid/tid header, tab-indented frames innermost first) -> Counter."""
    stacks = collections.Counter()
    head, frames = None, []
    for line in text.splitlines() + ['']:
        if line.startswith('\t'):
            parts = line.strip().split(None, 1)
            rest = parts[1] if len(parts) > 1 else '[unknown]'
            m = re.match(r'(.*?)\s+\((.*)\)$', rest)
            sym, dso = (m.group(1), m.group(2)) if m else (rest, '')
            sym = re.sub(r'\+0x[0-9a-f]+$', '', sym)
            if sym == '[unknown]':
                sym = f'[{os.path.basename(dso) or "?"}]'
            frames.append(sym.replace(' ', '_'))
        elif not line.strip():
            if head:
                stacks[head + (';'.join(reversed(frames)) or '-',)] += 1
            head, frames = None, []
        else:
            m = re.match(r'^\s*(.*?)\s+(\d+)/(\d+)\s*$', line)
            if m:
                pid, tid = int(m.group(2)), int(m.group(3))
                kind = 'main' if pid == tid else 'thr:' + m.group(1).replace(' ', '_')
                head = (ranks.get(pid, -1), kind)
    return stacks


def perf_stacks(pids, ranks, secs, freq):
    perf = shutil.which('perf')
    if not perf:
        return None, 'perf not found'
    env = dict(os.environ)
    env.pop('DEBUGINFOD_URLS', None)       # no internet on the nodes
    with tempfile.TemporaryDirectory(prefix='hang_perf_') as tmp:
        data = os.path.join(tmp, 'perf.data')
        cmd = [perf, 'record', '-q', '-F', str(freq), '--call-graph', 'dwarf,16384',
               '-p', ','.join(map(str, pids)), '-o', data, '--', 'sleep', str(secs)]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=secs + 120)
        if not os.path.exists(data):
            return None, f'perf record failed (status {r.returncode}): {r.stderr.strip()[-800:]}'
        r = subprocess.run([perf, 'script', '-i', data, '-F', 'comm,pid,tid,ip,sym,dso'],
                           capture_output=True, text=True, env=env, timeout=900)
        if r.returncode:
            return None, f'perf script failed (status {r.returncode}): {r.stderr.strip()[-800:]}'
        return fold(r.stdout, pids, ranks), 'ok'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('outdir')
    ap.add_argument('program', help='process name as in /proc/<pid>/comm, e.g. filter or wrf.exe')
    ap.add_argument('--secs', type=int, default=3, help='perf sampling time (default 3 s)')
    ap.add_argument('--freq', type=int, default=49, help='perf samples per second (default 49)')
    ap.add_argument('--no-perf', action='store_true')
    a = ap.parse_args()

    node = socket.gethostname().split('.')[0]
    os.makedirs(a.outdir, exist_ok=True)
    pids = find_procs(a.program)
    ranks = {p: rank_of(p) for p in pids}
    t = time.strftime('%Y-%m-%dT%H:%M:%S')
    head = [f'# {node} {t} {a.program}: {len(pids)} processes, ranks '
            f'{sorted(ranks.values())[:1]}..{sorted(ranks.values())[-1:]}',
            f'# perf_event_paranoid {read("/proc/sys/kernel/perf_event_paranoid")}, '
            f'ptrace_scope {read("/proc/sys/kernel/yama/ptrace_scope")}, perf {shutil.which("perf")}']
    lines = proc_snapshot(pids, ranks) if pids else []
    if pids and not a.no_perf:
        stacks, msg = perf_stacks(pids, ranks, a.secs, a.freq)
        head.append(f'# perf: {msg}')
        if stacks is not None:
            with open(os.path.join(a.outdir, f'{node}.folded'), 'w') as f:
                for (rank, kind, stack), n in sorted(stacks.items()):
                    f.write(f'{rank} {kind} {n} {stack}\n')
    with open(os.path.join(a.outdir, f'{node}.proc.txt'), 'w') as f:
        f.write('\n'.join(head + lines) + '\n')
    print(head[0])


if __name__ == '__main__':
    main()
