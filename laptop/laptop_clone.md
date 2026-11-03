# Laptop clone of bnf_wrf_da

This rule applies only to the clone on the user's Mac. Its source is `laptop/laptop_clone.md` (tracked in the repo); the laptop clone links it to `.claude/rules/laptop_clone.md` (git-ignored). On Cirrus it is not in `.claude/rules/` and does not apply.

## What this clone is

- A clone of the GitHub repo for reading and editing the notes. The main copy, with the data, builds and runs, is on OLCF Cirrus at `/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/bnf_wrf_da`, and the Claude Code sessions there do the implementation work.
- `CLAUDE.md` describes the Cirrus copy. Its environment, module, build, Slurm and job instructions, and its absolute paths, don't apply here.

## What isn't here

- `cases/` data and run outputs (only small configuration files are tracked), `../software` (WRF, WPS, WRFDA and DART source and builds), `notes/papers/` (PDFs), `notes/sessions.md`, `notes/transcripts/` and the `.venv`.
- Don't guess what they contain. When an answer depends on run output, logs or WRF/DART source, say that it needs checking on Cirrus (or in the source, if the user has cloned it here) instead of stating it as fact.
- Nothing is built or run here: no jobs, no project scripts.

## What to edit

- Markdown under `notes/`, and `CLAUDE.md` when the user asks. Nothing under `scripts/`, `patches/`, `cases/`, `src/` or other code. A code change worked out here goes into a hand-off note for a Cirrus session (below).
- Markdown written for the user follows the Typora rules in `~/.claude/rules/typora-markdown.md`. If that file isn't on this machine, ask the user for it before writing notes.
- Before saying an edit is done, look at `git diff` for changes beyond the intended ones: Typora can rewrite tables, escapes or blank lines when it saves a file.

## Git

- The user syncs the two copies through GitHub, usually by hand. Run `git pull`, `fetch` or `push` only when the user asks, and no `rebase` or `merge` beyond what an asked-for pull does. Work on `main`: no branches, no worktrees.
- Commit only when the user asks. Commit messages end with the `Co-Authored-By: Claude ...` trailer.

## Hand-offs to Cirrus

- Work for a Cirrus session goes in `notes/handoffs/YYYY-MM-DD_<topic>.md`, titled `# Hand-off: "<session name>: <topic>"`, where the session name is the Cirrus session that picks it up and starts with an existing group key from `.claude-sessions.toml` (e.g. `expansion: part 11`; ask the user which). Under the title: `Written <YYYY-MM-DD> at the end of session "<name>"`, then a line saying it was written in the laptop clone.
- Memories saved here stay on this machine. Anything learned here that should also hold on Cirrus goes into a note, a hand-off, or `CLAUDE.md` (when the user asks).

## Carried over from the Cirrus sessions' memory

- No LaTeX in chat answers: the terminal doesn't render it. Derivations go into the relevant note (Typora rules), and the reply points to the section and uses plain text or Unicode (λ, σ², ≈).
- Short status lines need the same technical care as full answers (right tool, e.g. DART vs WRFDA; right quantity, e.g. value vs tendency). If there is no room to say it precisely, say less.
- In DART `input.nml` walkthrough sessions, append each explanation to `notes/dart_namelist_discussion_log.md` as it happens: dated, naming the namelist block(s), with the short answer and cross-references to related variables and to `initial_plan_from_codex/`. Append at the bottom; don't rewrite earlier entries unless correcting them.
