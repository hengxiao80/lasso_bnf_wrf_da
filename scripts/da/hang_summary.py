#!/usr/bin/env python3
"""Summary of a hang snapshot directory written by hang_snapshot.py (one <node>.proc.txt and <node>.folded per node).

- Processes and ranks found (ranks missing from 0..max: those had already exited).
- Main-thread kernel state and CPU; threads in D state (blocked in the kernel, e.g. the file system) with
  their wait channel; other threads using CPU.
- Where the main threads are, from the perf stacks: ranks grouped by the frames just above the outermost
  progress call (opal_progress / ucp_worker_progress) in most of their samples, i.e. what they wait for;
  each group with its rank list, the longest stack seen (to show the calling program frames) and the
  hottest innermost functions.

Usage: .venv/bin/python scripts/da/hang_summary.py <snapshot dir> [--frames N]
"""

import argparse
import collections
import glob
import os

PROGRESS = {'opal_progress', 'ucp_worker_progress'}


def ranges(xs):
    xs = sorted(xs)
    out, i = [], 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
            j += 1
        out.append(str(xs[i]) if i == j else f'{xs[i]}-{xs[j]}')
        i = j + 1
    return ','.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('dir')
    ap.add_argument('--frames', type=int, default=16, help='frames of the shared stack to print (default 16)')
    ap.add_argument('--sig-frames', type=int, default=4,
                    help='ranks are grouped by this many frames ending at the outermost progress call (default 4)')
    a = ap.parse_args()

    # --- /proc snapshot
    rows, heads = [], []
    for fn in sorted(glob.glob(os.path.join(a.dir, '*.proc.txt'))):
        node = os.path.basename(fn).split('.')[0]
        for line in open(fn):
            if line.startswith('#'):
                heads.append(line.strip())
            elif not line.startswith('rank '):
                r = line.split()
                rows.append(dict(node=node, rank=int(r[0]), pid=r[1], tid=r[2], thread=r[3], state=r[4],
                                 cpu=float(r[5]), vcsw=float(r[6]), nvcsw=float(r[7]), wchan=r[9]))
    main_rows = [r for r in rows if r['pid'] == r['tid']]
    ranks = sorted(r['rank'] for r in main_rows)
    nodes = sorted({r['node'] for r in rows})
    print(f'{a.dir}: {len(main_rows)} processes on {len(nodes)} nodes')
    for h in heads:
        if '# perf:' in h and ': ok' not in h:
            print('  ' + h)
    if ranks:
        missing = sorted(set(range(ranks[-1] + 1)) - set(ranks))
        print(f'  ranks found {ranks[0]}..{ranks[-1]}; missing (exited or never found): {ranges(missing) or "none"}')
        st = collections.Counter(r['state'] for r in main_rows)
        cpus = sorted(r['cpu'] for r in main_rows)
        print(f'  main threads: state {dict(st)}; CPU % min {cpus[0]:.0f} median {cpus[len(cpus) // 2]:.0f} '
              f'max {cpus[-1]:.0f}; voluntary switches/s median '
              f'{sorted(r["vcsw"] for r in main_rows)[len(main_rows) // 2]:.0f}')
        slow = [r for r in main_rows if r['cpu'] < 50]
        if slow:
            print(f'  main threads under 50 % CPU: ' + '; '.join(
                f'rank {r["rank"]} ({r["node"]}) {r["state"]} {r["cpu"]:.0f}% wchan {r["wchan"]}' for r in slow[:20]))
    dstate = [r for r in rows if r['state'] == 'D']
    for r in dstate[:40]:
        print(f'  D state: rank {r["rank"]} ({r["node"]}) tid {r["tid"]} {r["thread"]} wchan {r["wchan"]}')
    other = collections.defaultdict(list)
    for r in rows:
        if r['pid'] != r['tid']:
            other[r['thread']].append(r)
    for name, rs in sorted(other.items()):
        busy = [r for r in rs if r['cpu'] >= 5]
        print(f'  other threads "{name}": {len(rs)}, {len(busy)} at >= 5 % CPU'
              + (f' (max {max(r["cpu"] for r in busy):.0f} %)' if busy else '')
              + f', states {dict(collections.Counter(r["state"] for r in rs))}')

    # --- perf stacks
    per = collections.defaultdict(list)          # (rank, kind) -> [(frames, n)]
    for fn in sorted(glob.glob(os.path.join(a.dir, '*.folded'))):
        for line in open(fn):
            rank, kind, n, stack = line.rstrip('\n').split(' ', 3)
            per[(int(rank), kind)].append((stack.split(';'), int(n)))
    if not per:
        print('  no perf stacks')
        return
    # Signature of a sample: the frames just above the outermost progress call (opal_progress or
    # ucp_worker_progress), i.e. what the rank is waiting for; robust to stacks that DWARF unwinding cut short
    # at the outer end and to the varying innermost frames of the progress loop.
    def signature(fr):
        i = next((k for k, f in enumerate(fr) if f in PROGRESS), None)
        if i is None:
            return tuple(fr[-a.sig_frames:])
        return tuple(fr[max(0, i - a.sig_frames + 1):i + 1])

    groups = collections.defaultdict(list)       # signature -> ranks
    full = {}                                    # signature -> longest stack seen with it
    leaves = collections.defaultdict(collections.Counter)
    for (rank, kind), samples in per.items():
        if kind != 'main':
            continue
        sigs = collections.Counter()
        for fr, n in samples:
            sg = signature(fr)
            sigs[sg] += n
            leaves[sg][fr[-1]] += n
            i = next((k for k, f in enumerate(fr) if f in PROGRESS), len(fr) - 1)
            if len(fr[:i + 1]) > len(full.get(sg, ())):
                full[sg] = fr[:i + 1]
        groups[sigs.most_common(1)[0][0]].append(rank)
    # a signature that is the tail of a longer one (outer frames lost in unwinding) joins the longer one
    for sg in sorted(groups, key=len):
        longer = [g for g in groups if len(g) > len(sg) and g[-len(sg):] == sg]
        if longer:
            into = max(longer, key=lambda g: len(groups[g]))
            groups[into] += groups.pop(sg)
            leaves[into] += leaves.pop(sg)
    nsamp = sum(n for (r, k), s in per.items() if k == 'main' for _, n in s)
    print(f'\nmain-thread stacks: {len(groups)} group(s) by the {a.sig_frames} frames ending at the outermost '
          f'progress call; {nsamp} samples')
    for sg, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f'\n  {len(rs)} ranks: {ranges(rs)}')
        print('    longest stack seen, outermost first, to the progress call:')
        for f in full[sg][-a.frames:]:
            print(f'      {f}')
        tot = sum(leaves[sg].values())
        print('    hottest leaves: ' + ', '.join(f'{f} {100 * n / tot:.0f}%' for f, n in leaves[sg].most_common(6)))
    thr = collections.defaultdict(collections.Counter)
    for (rank, kind), samples in per.items():
        if kind != 'main':
            for fr, n in samples:
                thr[kind][';'.join(fr[-4:])] += n
    for kind, c in sorted(thr.items()):
        print(f'\n  {kind}: {sum(c.values())} samples; top stacks (innermost 4 frames):')
        for s, n in c.most_common(3):
            print(f'    {n:6d}  {s}')


if __name__ == '__main__':
    main()
