#!/usr/bin/env python3
"""Dump a Claude Code session transcript (JSONL) to Markdown under notes/transcripts/.

Run by the project hooks in .claude/settings.json before a compaction (PreCompact) and when the
context is cleared (SessionEnd, reason "clear"): the hook input JSON on stdin gives
transcript_path, session_id and the event. By hand: transcript_to_md.py <transcript.jsonl> [label].

Keeps user and assistant messages: text, tool calls (name + input) and tool results, in full.
Thinking blocks and bookkeeping records are left out. Output:
notes/transcripts/<YYYY-MM-DD_HHMMSS>_<session id[:8]>_<label>.md (UTC time of the dump).
"""
import datetime
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, 'notes', 'transcripts')


def block_text(b):
    t = b.get('type')
    if t == 'text':
        return b.get('text', '')
    if t == 'tool_use':
        inp = json.dumps(b.get('input', {}), indent=1, ensure_ascii=False)
        return f"**Tool call: {b.get('name')}**\n\n```json\n{inp}\n```"
    if t == 'tool_result':
        c = b.get('content')
        if isinstance(c, list):
            c = '\n'.join(x.get('text', f"[{x.get('type')}]") for x in c if isinstance(x, dict))
        c = str(c or '')
        err = ' (error)' if b.get('is_error') else ''
        return f"**Tool result{err}:**\n\n```\n{c.replace('```', '` ` `')}\n```"
    return None   # thinking, images, ...


def convert(path, session, label):
    parts = [f'# Session transcript {session}', '',
             f'- Source: `{path}`', f'- Dumped: {datetime.datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC ({label})', '']
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            role = d.get('type')
            m = d.get('message')
            if role not in ('user', 'assistant') or not isinstance(m, dict):
                continue
            c = m.get('content')
            texts = [c] if isinstance(c, str) else [block_text(b) for b in c or [] if isinstance(b, dict)]
            texts = [t for t in texts if t and t.strip()]
            if not texts:
                continue
            head = 'Compaction summary' if d.get('isCompactSummary') else role.capitalize()
            parts += [f"## {head} — {d.get('timestamp', '')}", ''] + ['\n\n'.join(texts), '']
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.datetime.utcnow().strftime('%Y-%m-%d_%H%M%S')
    out = os.path.join(OUT_DIR, f'{stamp}_{session[:8]}_{label}.md')
    with open(out, 'w') as f:
        f.write('\n'.join(parts))
    return out


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
        label = sys.argv[2] if len(sys.argv) > 2 else 'manual'
        session = os.path.splitext(os.path.basename(path))[0]
    else:
        h = json.load(sys.stdin)
        path, session = h['transcript_path'], h.get('session_id', 'unknown')
        event = h.get('hook_event_name', '')
        if event == 'SessionEnd':
            if h.get('reason') != 'clear':
                return
            label = 'clear'
        else:
            label = 'compact-' + str(h.get('trigger', ''))
    print(convert(path, session, label))


if __name__ == '__main__':
    main()
