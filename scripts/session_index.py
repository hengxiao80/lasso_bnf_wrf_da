#!/usr/bin/env python3
"""Index this repo's Claude Code sessions by group: writes notes/sessions.md.

Reads the session transcripts Claude Code keeps for this repo (~/.claude/projects/<repo path with
every non-alphanumeric character as '-'>/*.jsonl) and sorts them into the groups of
notes/session_groups.toml (rules at its top). Per session: dates (local time), name, number of
prompts, session ID and transcript dumps (notes/transcripts/*_<ID[:8]>_*.md, written by
scripts/transcript_to_md.py). Then one table of the hand-off notes in notes/handoffs/:
- out: the date and session in the note's 'Written <date> at the end of / during session "<name>"';
- in: the session the note's title names ('# Hand-off: "<name>..."'), or else a session whose first
  prompt names the note's file; the date is that session's first.

Run by the project hooks in .claude/settings.json at every session start and end (output discarded,
since SessionStart output would go into Claude's context). By hand: uv run scripts/session_index.py
[--stdout]; this also prints any entry of session_groups.toml that claims no session.
"""
import datetime
import glob
import json
import os
import re
import sys
import tomllib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTES = os.path.join(REPO, 'notes')
GROUPS = os.path.join(NOTES, 'session_groups.toml')
OUT = os.path.join(NOTES, 'sessions.md')
PROJECT_DIR = os.path.expanduser('~/.claude/projects/' + re.sub(r'[^A-Za-z0-9]', '-', os.path.realpath(REPO)))
HANDOFF_REF = re.compile(r'notes/handoffs/([\w.-]+\.md)')


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def prompt_text(m):
    """The user's own words in a user record, or None (tool results, commands, meta records)."""
    c = m.get('content') if isinstance(m, dict) else None
    if isinstance(c, list):
        c = '\n'.join(b.get('text', '') for b in c if isinstance(b, dict) and b.get('type') == 'text')
    if not isinstance(c, str) or not c.strip() or c.lstrip().startswith('<'):
        return None
    return c


def read_session(path):
    s = {'id': os.path.splitext(os.path.basename(path))[0], 'custom': None, 'ai': None,
         'prompts': 0, 'first_prompt': None, 'refs': set(), 't0': None, 't1': None}
    with open(path, errors='replace') as f:
        for line in f:
            i = line.find('"timestamp":"')
            if i >= 0:
                ts = line[i + 13:line.find('"', i + 13)]
                s['t0'] = s['t0'] or ts
                s['t1'] = ts
            # Only the small bookkeeping records and user records need parsing.
            if not any(k in line for k in ('"type":"custom-title"', '"type":"ai-title"', '"type":"user"')):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get('type')
            if t == 'custom-title':
                s['custom'] = d.get('customTitle') or s['custom']
            elif t == 'ai-title':
                s['ai'] = d.get('aiTitle') or s['ai']
            elif t == 'user' and not d.get('isMeta'):
                text = prompt_text(d.get('message'))
                if text:
                    s['prompts'] += 1
                    if not s['first_prompt']:
                        s['first_prompt'] = ' '.join(text.split())[:60]
                        s['refs'].update(HANDOFF_REF.findall(text))
    s['name'] = s['custom'] or s['ai'] or s['first_prompt'] or '(no name)'
    for k in ('t0', 't1'):
        s[k] = (datetime.datetime.fromisoformat(s[k].replace('Z', '+00:00')).astimezone() if s[k]
                else datetime.datetime.fromtimestamp(os.path.getmtime(path)).astimezone())
    return s


def read_handoffs():
    notes = []
    for p in sorted(glob.glob(os.path.join(NOTES, 'handoffs', '*.md'))):
        with open(p) as f:
            text = f.read(3000)
        title = re.search(r'"([^"]+)"', text.split('\n', 1)[0])
        m = re.search(r'Written (\d{4}-\d\d-\d\d) (?:at the end of|during) session "([^"]+)"', text)
        notes.append({'path': p, 'opens': title.group(1).split(':')[0] if title else None,
                      'written': m.group(1) if m else os.path.basename(p)[:10],
                      'by': m.group(2) if m else None})
    return notes


def assign(s, groups):
    """(group key, the `ids` or `names` entry that claimed the session, if any)."""
    id8 = s['id'][:8]
    for g in groups:
        if id8 in g.get('ids', []):
            return g['key'], (g['key'], id8)
    for g in groups:
        if s['custom'] and re.match(re.escape(g['key']) + r'\s*:', s['custom'], re.I):
            return g['key'], None
    names = [norm(n) for n in (s['custom'], s['ai']) if n]
    for g in groups:
        for p in g.get('names', []):
            if any(norm(p) in n for n in names):
                return g['key'], (g['key'], p)
    return None, None


def link(path, text):
    return f'[{text}]({os.path.relpath(path, NOTES)})'


def label(s):
    return f"**{s['custom']}**" if s['custom'] else f"*{s['name']}*"


def row(s):
    dumps = sorted(glob.glob(os.path.join(NOTES, 'transcripts', f"*_{s['id'][:8]}_*.md")))
    dumps = ', '.join(link(p, os.path.basename(p)) for p in dumps)
    d0, d1 = f"{s['t0']:%m-%d}", f"{s['t1']:%m-%d}"
    dates = d0 if d0 == d1 else f'{d0} – {d1}'
    return f"| {dates} | {label(s)} | {s['prompts']} | `{s['id']}` | {dumps} |"


def handoff_rows(notes, sessions):
    named = {norm(s['custom']): s for s in sessions if s['custom']}   # later sessions win
    rows = []
    for h in notes:
        by = named.get(norm(h['by'])) if h['by'] else None
        out = f"{label(by)} (`{by['id'][:8]}`)" if by else (f"{h['by']} (not found)" if h['by'] else '')
        into = [named[norm(h['opens'])]] if h['opens'] and norm(h['opens']) in named else [
            s for s in sessions if os.path.basename(h['path']) in s['refs']]
        rows.append(f"| {link(h['path'], os.path.basename(h['path']))} | {h['written']} | {out} | " +
                    '; '.join(f"{s['t0']:%Y-%m-%d}" for s in into) + ' | ' +
                    '; '.join(f"{label(s)} (`{s['id'][:8]}`)" for s in into) + ' |')
    return rows


def main():
    with open(GROUPS, 'rb') as f:
        groups = tomllib.load(f)['group']
    sessions = [read_session(p) for p in glob.glob(os.path.join(PROJECT_DIR, '*.jsonl'))]
    sessions.sort(key=lambda s: s['t0'])
    notes = read_handoffs()
    empty = [s for s in sessions if s['prompts'] == 0]
    by_group, used = {}, set()
    for s in sessions:
        if s['prompts']:
            key, entry = assign(s, groups)
            by_group.setdefault(key, []).append(s)
            used.add(entry)
    unused = [f"{g['key']}: {e!r}" for g in groups for e in g.get('ids', []) + g.get('names', [])
              if (g['key'], e) not in used]

    now = datetime.datetime.now().astimezone()
    lines = ['# Claude Code sessions for this repo', '',
             f"Written by `scripts/session_index.py` on {now:%Y-%m-%d %H:%M %Z} from "
             f"`{PROJECT_DIR.replace(os.path.expanduser('~'), '~')}/` ({len(sessions)} sessions). "
             'Groups and their rules: `notes/session_groups.toml`.', '',
             'Resume one with `claude -r <session ID>` (or `claude -r "<name>"` if you named it). '
             'Bold: a name you gave the session; italics: Claude Code\'s own title. '
             'Prompts: messages you typed, not counting slash commands. Dates in local time.', '']
    for g in groups + [{'key': None, 'title': 'Ungrouped'}]:
        ss = by_group.get(g['key'])
        if not ss:
            continue
        key = f" (`{g['key']}`)" if g['key'] else ''
        d0, d1 = f"{ss[0]['t0']:%Y-%m-%d}", f"{max(s['t1'] for s in ss):%Y-%m-%d}"
        span = d0 if d0 == d1 else f'{d0} – {d1}'
        n = f"{len(ss)} session{'s' if len(ss) > 1 else ''}"
        lines += [f"## {g['title']}{key}: {n}, {span}", '',
                  '| Dates | Name | Prompts | Session ID | Transcript dumps |', '|---|---|--:|---|---|']
        lines += [row(s) for s in ss] + ['']
    if notes:
        lines += [f'## Hand-off notes: {len(notes)}', '',
                  '| Note | Out: written | Out: by session | In: picked up | In: by session |',
                  '|---|---|---|---|---|'] + handoff_rows(notes, [s for s in sessions if s['prompts']]) + ['']
    if empty:
        lines += [f'## Without prompts: {len(empty)}', '',
                  'Opened and left, or used only for slash commands (such as a cancelled `/resume`): ' +
                  ', '.join(f"`{s['id'][:8]}` ({s['t0']:%m-%d})" for s in empty) + '.', '']

    text = '\n'.join(lines)
    if '--stdout' in sys.argv[1:]:
        print(text)
        return
    # Atomic, since the SessionStart/SessionEnd hooks of two sessions may run at once.
    tmp = f'{OUT}.{os.getpid()}.tmp'
    with open(tmp, 'w') as f:
        f.write(text)
    os.replace(tmp, OUT)
    counts = ', '.join(f"{g['key']} {len(by_group[g['key']])}" for g in groups if g['key'] in by_group)
    print(f"{OUT}: {counts}; ungrouped {len(by_group.get(None, []))}; without prompts {len(empty)}")
    if unused:
        print('Entries in session_groups.toml that claim no session (stale, or covered by an earlier one): ' +
              ', '.join(unused))


if __name__ == '__main__':
    main()
