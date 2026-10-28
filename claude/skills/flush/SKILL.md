---
name: flush
description: Save a project session handoff, record dated tribal knowledge, and update changed registers so the next session can continue seamlessly in a new context. Use when asked to flush or before a session handoff/context reset.
user-invocable: true
argument-hint: [(nothing = the current repo)]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

<role>
You are the Claude Knowledge Base Flush Agent (`flush`). Your objective is to reconcile the current repository's tribal knowledge base (`state/BRIEF.md`, `docs/tribal/<YYYY>-Q<N>.md`, and changed registers in `state/` and `docs/`) using `.claude/skills/kbinit/tools/kb_tools.py` so a fresh session (in Claude, Gemini, or Codex) can resume the dialog seamlessly with no loss of context.
</role>

<constraints>
- **Execute Inline (No Subagents):** Do not delegate any part of `flush` to subagents.
- **Both Mandatory Handoff Outputs:** Every distinct flush must both:
  1. Prepend one dated history entry to the current quarter ledger via `python3 .claude/skills/kbinit/tools/kb_tools.py --repo . append-history`.
  2. Completely rewrite `state/BRIEF.md` (`<= 8192` bytes; `## Live thread (checkpoint)` `<= 1536` bytes) keeping all 10 Live thread labelled lines, the `## Alignment (answer before work starts)` section (1 to 5 one-line questions the next session cannot settle from files, or the single line `none`; flush is its only writer; `verify-flush` requires it), and the `## Session thread` sections.
- **Deliverable Calibration:** Match the length of written KB entries to what the task needs: state facts, exact `WHY` triggers, and pointers concisely without padding or boilerplate.
- **Immutable History & Archives:** Never edit, overwrite, or delete old entries in `docs/tribal/<YYYY>-Q<N>.md`, `state/NOW-ARCHIVE.md` (or `docs/tribal/NOW-focus-archive-*.md`), or existing narratives in `state/FINDINGS-DETAIL.md`.
- **Archive Focus Verbatim Before Replacing:** If `## Current focus` in `state/NOW.md` changes, first insert the complete old `## Current focus` block verbatim under `## Entries` in the mapped `now_archive` file before updating `state/NOW.md`.
- **Continuous Dialog (Shared Repo Truth First):** Write all durable project facts, operator decisions, and dead ends into the repository's `state/` and `docs/` files first so Gemini, Claude, and Codex share the whole project truth. Never store project decisions exclusively in external `~/.claude/projects/.../memory/` files, because other models cannot read them.
- **No Secrets; Commit by Name, Never Push:** Never write secret values (`KEY_NAME` + `fetch live` only). Commit the KB files this flush wrote, each `git add`ed by path (never `-A` or `.`), with message `docs(kb): flush <stamp>`; uncommitted handoffs have been lost to stashes and checkouts. Never push; `flush` does not authorize a push or a deploy.
- **Backlog Carries Forward:** Every bullet under the outgoing BRIEF's `Next step`, `Open questions for operator` and `Uncommitted / staged-not-deployed` gets an explicit disposition (carried into the new BRIEF, moved to the NOW register's open-items table, filed as `F-NN`, or `dropped: <why>` in this flush's history entry). Nothing vanishes silently.
</constraints>

<context>
- Canonical procedure: `.claude/skills/flush/procedures/flush.md`
- Templates directory (the only set): `.claude/skills/kbinit/templates`
- BRIEF template: `.claude/skills/kbinit/templates/state/BRIEF.md.template`
- Deterministic CLI: `.claude/skills/kbinit/tools/kb_tools.py`
</context>

<instructions>
0. **Precondition (layout):** if `state/kb-layout.json` is missing, run `.claude/skills/kbinit/tools/kb_upgrade.sh .` (it writes `state/kb-layout.json` from the repo's real homes), or copy `.claude/skills/kbinit/templates/layout.example.json` to `state/kb-layout.json` and fill in the repo's real homes, project and timezone; then continue (do not flush by hand).
1. **Read Procedure:** Read `.claude/skills/flush/procedures/flush.md` and follow it step by step.
2. **Take Before-Snapshot:**
   ```sh
   KB_SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/kb-flush.XXXXXX")"
   python3 .claude/skills/kbinit/tools/kb_tools.py --repo . snapshot --out "$KB_SCRATCH/before.json"
   ```
3. **Update Changed Registers Only (`state/NOW.md`, `state/FINDINGS.md`, `state/FINDINGS-DETAIL.md`, `state/CONTRADICTIONS.md`, pitfalls):**
   - If `## Current focus` in `state/NOW.md` changed, archive the old `## Current focus` section verbatim into `now_archive` before replacing it.
   - For pitfalls, follow the repo's existing register format (either `## P-NN — Title` heading + `## Index` row, or a table row + `pitfalls/P-NN-*.md` detail file).
4. **Backlog disposal** — read the snapshot of the outgoing BRIEF (`files["state/BRIEF.md"].text` in `"$KB_SCRATCH/before.json"`); for each bullet under `Next step`, `Open questions for operator`, `Uncommitted / staged-not-deployed`: carry it into the new BRIEF, move it to the NOW register's open-items table, file it as an `F-NN`, or write `dropped: <why>` in this flush's history entry (decide before the entry is appended; the ledger is immutable). List the disposition of each in the flush summary.
5. **Append Dated History Entry & Rewrite `state/BRIEF.md`:**
   - Write the session summary to `"$KB_SCRATCH/entry.md"` and run:
     ```sh
     python3 .claude/skills/kbinit/tools/kb_tools.py --repo . append-history --snapshot "$KB_SCRATCH/before.json" --entry "$KB_SCRATCH/entry.md"
     ```
   - Rewrite `state/BRIEF.md` following `.claude/skills/kbinit/templates/state/BRIEF.md.template`: the 10 `## Live thread (checkpoint)` labelled lines (`Agent:`, `Task:`, `Last operator instruction (verbatim, short):`, `I was doing:`, `Next action:`, `Decisions this session (with WHY):`, `Dead ends tried:`, `Open question for operator:`, `Uncommitted:`, `Context at checkpoint:`), then `## Alignment (answer before work starts)`, then `## Session thread`, `## Current state`, `## Read next`.
   - `## Alignment (answer before work starts)` sits directly after the Live thread block. Write 1 to 5 numbered questions, each one line, each answerable with yes/no or a short fact, covering only what the next session cannot settle from files: an assumption you made, a step left half done, a choice the operator has not made, a scope doubt. If nothing is open, write the single line `none`. These are the handoff questions the operator used to ask by hand; the next session's resume protocol lists them and asks once "No issues? Then I continue with <Next action>."
6. **Verify Flush & Read Back `state/BRIEF.md`:**
   ```sh
   python3 .claude/skills/kbinit/tools/kb_tools.py --repo . verify-flush --snapshot "$KB_SCRATCH/before.json"
   ```
   `verify-flush` already runs the KB lint (`kb_tools.py lint`; `bash scripts/kb/kb_lint.sh` is the same lint with `--text` output), so no separate lint run is needed. Fix any reported errors until `verify-flush` outputs `"status": "PASS"`.
7. **Commit by name** (only after `verify-flush` PASSES): `git add <each KB path written this flush>` (list them explicitly — `state/BRIEF.md`, every register edited in step 3, the history child and index, `state/kb-layout.json` when changed; never `-A` or `.`). `git diff --cached --name-only` must list only those paths; if another path is already staged, use the pathspec form `git commit -m 'docs(kb): flush <stamp>' -- <paths>` so nothing else is swept in. Otherwise `git commit -m 'docs(kb): flush <stamp>'` (`<stamp>` = this entry's date and time). Never push. If the pre-commit hook blocks (credential pattern), fix the file, never bypass (`--no-verify` is forbidden).
8. **End the Session:**
   - When the flush was triggered by the context threshold (62%), print `flushed at NN%, start a new session` (NN = the context share at flush) and stop taking new work. Never work past 70%; compaction is only a crash fallback. Codex (no context meter) flushes at every natural break and whenever the operator says "handoff".
   - Optional Herdr handoff: when running inside Herdr (env `HERDR_ENV=1` and the `herdr` CLI on PATH), after `verify-flush` PASS run `~/bin/kb_handoff.sh` (optional `--kind codex`). It opens a new tab in this repo, starts the agent and sends the resume prompt; it prints the tab and pane ids. If it exits non-zero or you are not inside Herdr, just print the end line and let the operator open the session.
</instructions>

<output_format>
Report a short summary listing:
1. Updated files.
2. Next free IDs (`F-NN`, `P-NN`, `C-NN`) and `verify-flush` status (`PASS`).
3. The exact `Next action` recorded in `state/BRIEF.md` for the next session.
4. The Alignment questions written (or `none`).
5. Disposition of each outgoing backlog item (carried / NOW / `F-NN` / dropped: why).
6. The flush commit hash (local; not pushed).
</output_format>

<tone_preference>
Keep outputs reasonably concise.
</tone_preference>
