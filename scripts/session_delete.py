#!/usr/bin/env python3
"""Delete Claude Code sessions of this repo: all sessions of a group, or sessions given by ID.

Groups are those of notes/sessions.md (scripts/session_index.py; rules in notes/session_groups.toml), plus
`empty` (the sessions without prompts). Ungrouped sessions are work not yet filed, so they go only by ID. An ID
can be any unique prefix of one, such as the 8 characters sessions.md shows for sessions without prompts.

Per session it deletes what Claude Code keeps under ~/.claude: the transcript projects/<repo dir>/<ID>.jsonl
(what `claude -r` lists), projects/<repo dir>/<ID>/ (subagent transcripts, tool results), file-history/<ID>/
(checkpoints for /rewind) and session-env/<ID>/; a background session goes through `claude rm` first, which
removes its jobs/<ID[:8]>/. Left alone: its prompts in ~/.claude/history.jsonl (the up-arrow history of all
projects) and its transcript dumps in notes/transcripts/. Sessions still running are skipped. Lists everything
and asks before deleting (-n: only list; -y: don't ask); then rebuilds notes/sessions.md.

  uv run scripts/session_delete.py --group junk --group empty -n
  uv run scripts/session_delete.py 05106cb2 6b39cf27
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_index as si  # noqa: E402

CLAUDE = os.path.expanduser('~/.claude')
DONE = ('done', 'stopped')      # background sessions in other states still run


def live_sessions():
    """IDs of the sessions running now, from ~/.claude/sessions/<pid>.json. A session whose process can't be
    checked from here (another host or PID namespace) counts as running."""
    try:
        with open('/etc/machine-id') as f:
            domain = f"linux:{f.read().strip()}:{os.readlink('/proc/self/ns/pid')}"
    except OSError:
        domain = None
    live = set()
    for p in glob.glob(os.path.join(CLAUDE, 'sessions', '*.json')):
        try:
            with open(p) as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if domain and d.get('pidDomain') == domain:
            try:
                os.kill(d['pid'], 0)
            except ProcessLookupError:
                continue                # a stale file: that process has ended
            except (PermissionError, KeyError, TypeError):
                pass
        live.add(d.get('sessionId'))
    return live


def job_state(sid):
    """State of session `sid` as a background session (jobs/<ID[:8]>/state.json), or None if it never was one."""
    try:
        with open(os.path.join(CLAUDE, 'jobs', sid[:8], 'state.json')) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    return d.get('state') if d.get('sessionId') == sid else None


def leftovers(sid):
    paths = [os.path.join(si.PROJECT_DIR, sid + '.jsonl'), os.path.join(si.PROJECT_DIR, sid),
             os.path.join(CLAUDE, 'file-history', sid), os.path.join(CLAUDE, 'session-env', sid)]
    return [p for p in paths if os.path.lexists(p)]


def size(p):
    if os.path.isdir(p) and not os.path.islink(p):
        n = sum(os.lstat(os.path.join(d, f)).st_size for d, _, fs in os.walk(p) for f in fs)
    else:
        n = os.lstat(p).st_size
    return f'{n / 1e3:.1f} kB'


def select(args, sessions, groups):
    by_group, empty, _ = si.classify(sessions, groups)
    keys = [g['key'] for g in groups]
    chosen = {}
    for key in args.group:
        if key in keys:
            ss = by_group.get(key, [])
        elif key == 'empty':
            ss = empty
        elif key == 'ungrouped':
            sys.exit('Ungrouped sessions are deleted only by ID.')
        else:
            sys.exit(f"No group {key!r}; groups: {', '.join(keys + ['empty'])}")
        if not ss:
            print(f'Group {key!r} has no sessions.')
        chosen.update((s['id'], s) for s in ss)
    for prefix in args.ids:
        m = [s for s in sessions if s['id'].startswith(prefix.lower())]
        if len(m) != 1:
            sys.exit(f"{prefix!r} matches " + (', '.join(s['id'] for s in m) if m else 'no session of this repo'))
        chosen[m[0]['id']] = m[0]
    return sorted(chosen.values(), key=lambda s: s['t0'])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ids', nargs='*', help='session IDs, or unique prefixes of them')
    ap.add_argument('-g', '--group', action='append', default=[],
                    help='a group key of notes/session_groups.toml, or empty (repeatable)')
    ap.add_argument('-n', '--dry-run', action='store_true', help='only list what would be deleted')
    ap.add_argument('-y', '--yes', action='store_true', help="delete without asking")
    args = ap.parse_args()
    if not args.ids and not args.group:
        ap.error('give session IDs or --group')

    sessions = si.load_sessions()
    chosen = select(args, sessions, si.load_groups())
    live = live_sessions()
    named = {}                          # session name -> hand-off notes that name it
    for h in si.read_handoffs():
        for n in {h['by'], h['opens']} - {None}:
            named.setdefault(si.norm(n), []).append(os.path.basename(h['path']))

    todo = []
    for s in chosen:
        sid, state = s['id'], job_state(s['id'])
        print(f"{sid}  {s['t0']:%Y-%m-%d}  {s['prompts']} prompt{'' if s['prompts'] == 1 else 's'}  {si.label(s)}")
        if sid in live or state not in (None,) + DONE:
            print('    skipped: still running' + (f' (background session, {state})' if state else ''))
            continue
        paths = leftovers(sid)
        if state:
            print(f'    claude rm {sid[:8]}  (background session, {state})')
        for p in paths:
            print(f"    {size(p):>10}  {p.replace(CLAUDE, '~/.claude', 1)}")
        for d in sorted(glob.glob(os.path.join(si.NOTES, 'transcripts', f'*_{sid[:8]}_*.md'))):
            print(f'    kept: {os.path.relpath(d, si.REPO)}')
        if s['custom'] and si.norm(s['custom']) in named:
            print(f"    named in hand-off note(s) {', '.join(named[si.norm(s['custom'])])}")
        todo.append((s, paths, state))

    if not todo or args.dry_run:
        print(f"{len(todo)} session(s) to delete" + ('; dry run, nothing deleted.' if args.dry_run else '.'))
        return
    if not args.yes:
        if not sys.stdin.isatty():
            sys.exit('Not a terminal, so no one to ask: pass -y to delete, or -n to only list.')
        if input(f'Delete these {len(todo)} session(s)? [y/N] ').strip().lower() not in ('y', 'yes'):
            sys.exit('Nothing deleted.')

    for s, paths, state in todo:
        if state:
            r = subprocess.run(['claude', 'rm', s['id'][:8]], stdin=subprocess.DEVNULL, capture_output=True,
                               text=True, timeout=120)
            if r.returncode:
                print(f"{s['id'][:8]}: `claude rm` failed, session left as it is:\n{r.stdout}{r.stderr}")
                continue
        for p in paths:
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
            elif os.path.lexists(p):    # `claude rm` may have taken it already
                os.remove(p)
        print(f"deleted {s['id']}")
    si.main()


if __name__ == '__main__':
    main()
