# claude/kb/: the ONE tribal-knowledge template set (`~/apps/factorymaterial/claude/kb/`)

Part of the updated software factory + tribal-knowledge system (`~/apps/factorymaterial`).
This is the only template set.

Installed into a project by the `kbinit` skill (Claude Code: `/kbinit`; Codex: `kbinit`),
which runs `kb_tools.py init`. Existing KB repos are upgraded with `~/bin/kb_upgrade.sh`.

## Engine and placeholders

Engine: `~/apps/factorymaterial/scripts/kb_tools.py` (stdlib only, linked from `~/bin`).

| Subcommand | Does |
|---|---|
| `init` | create missing registers, the one-rules-file pair, `scripts/kb/`; `--dry-run`, `--layout`, `--refresh-tools` |
| `snapshot` | before-snapshot for a flush |
| `append-history` | add one dated entry at the top of the quarter ledger |
| `verify-flush` | check the flush preserved everything; runs `lint` |
| `lint` | the only KB lint. JSON by default; `--text` prints the human sections |
| `health` | layout and register health |

Placeholders the engine fills: `{{PROJECT}}` `{{DATE}}` `{{STAMP}}` `{{QUARTER}}` `{{BRIEF}}` `{{NOW}}`
`{{NOW_ARCHIVE}}` `{{FINDINGS}}` `{{DETAILS}}` `{{CONTRADICTIONS}}` `{{PITFALLS}}` `{{HISTORY_INDEX}}`
`{{HISTORY_DIR}}` `{{HISTORY_NOTE}}` `{{KB_SECTION}}` `{{MEMORY_DIR}}` `{{TIME_ZONE}}` `{{TIME_ZONE_NOTE}}`.

## Two seats, one source

| Seat | Operating file (repo) | Global operating file | Skills dir | BRIEF at session start |
|---|---|---|---|---|
| Claude Code | `CLAUDE.md` (thin: `@AGENTS.md` + Claude-only items) | `~/.claude/CLAUDE.md` | `~/.claude/skills/` (symlinks) | injected by the SessionStart hook |
| Codex | `AGENTS.md` (the single rules file) | `~/.codex/AGENTS.md` | `~/.codex/skills/` (copies) | `cat state/BRIEF.md` (no hooks) |

The skills `checkpoint`, `flush`, `kbinit` have one source each: `../skills/<name>/SKILL.md`.
`~/bin/sync_kb_skills.sh` copies them into the Codex seat. The Claude seat is symlinks, so nothing
is written there. `--check` reports drift and exits 1. Edit the source, then sync. Never edit a seat copy.

## One rules file per repo (layout since 2026-10-18)

- `AGENTS.md` is the single source of every rule for every agent. Codex reads it directly.
  Claude Code loads it through the line `@AGENTS.md` directly under the first heading of `CLAUDE.md`.
- `CLAUDE.md` is thin (target about 1.5 KB, lint budget 4 KB). Only Claude-Code-only items:
  hooks, skills, auto-memory location, subagents. It says "never copy a rule here; edit AGENTS.md".
- The KB section (`KB-SECTION.md.template`) lives ONLY in `AGENTS.md`, between
  `<!-- KB-SECTION-BEGIN -->` and `<!-- KB-SECTION-END -->`. `kbinit` and `kb_upgrade.sh` insert
  or refresh it there and make sure `CLAUDE.md` has the `@AGENTS.md` line.
- The old model (the same section in both files, lint checking drift) is retired.

## Files

| Template file | Lands at | Purpose |
|---|---|---|
| `KNOWLEDGE-MAP.md.template` | `KNOWLEDGE-MAP.md` | the single entry point: model, precedence, read order, update procedure, budgets |
| `KB-SECTION.md.template` | inside `AGENTS.md` only | the agent-neutral "Session Start" + "History Log" sections, between the markers |
| `AGENTS.md.template` | `AGENTS.md` (only if absent) | the single rules file: KB section + house rules + project-fact stubs + build/test + task router + Codex seat |
| `CLAUDE.md.template` | `CLAUDE.md` (only if absent) | thin Claude Code file: header, `@AGENTS.md`, Claude-only section |
| `layout.example.json` | `state/kb-layout.json` | the homes map the engine reads; legacy repos get theirs from `kb_upgrade.sh` or `init --layout` |
| `state/README.md` | `state/README.md` | what the register tier is |
| `state/BRIEF.md.template` | `state/BRIEF.md` | handoff snapshot; Live thread (checkpoint) block at top |
| `state/NOW.md.template` | `state/NOW.md` | what is true now (freshness-stamped facts + ONE current-focus block) |
| `state/NOW-ARCHIVE.md.template` | `state/NOW-ARCHIVE.md` | old current-focus blocks, verbatim |
| `state/CONTRADICTIONS.md.template` | `state/CONTRADICTIONS.md` | doc-rot register (`C-NN`) |
| `state/FINDINGS.md.template` | `state/FINDINGS.md` | open findings, one line each (`F-NN`) |
| `state/FINDINGS-DETAIL.md.template` | `state/FINDINGS-DETAIL.md` | append-only narrative per finding |
| `docs/TribalKnowledge.md.template` | `docs/TribalKnowledge.md` | index to the quarter history children |
| `docs/tribal/QUARTER.md.template` | `docs/tribal/{{QUARTER}}.md` | append-only, newest-first history ledger |
| `docs/KNOWN-PITFALLS.md.template` | `docs/KNOWN-PITFALLS.md` | what bit us before (`P-NN`), Index table at top |
| `scripts/kb/kb_lint.sh` | `scripts/kb/kb_lint.sh` | thin wrapper: `kb_tools.py lint --text` |
| `scripts/kb/session_health.sh` | `scripts/kb/session_health.sh` | session-start probe (git, build, prod health, local services, BRIEF age). The project fills its CONFIG block. `init --refresh-tools` never overwrites an existing one |
| `scripts/hooks/` | `scripts/hooks/` | Claude Code hooks (PreToolUse guard for Bash and its settings snippet) |
| `procedures/kbinit.md`, `procedures/flush.md` | read by the skills | the canonical step lists |

## Byte budgets (bytes, not lines; a session pays for every byte read)

| File | Budget |
|---|---|
| `state/BRIEF.md` | 8 KB (Live thread block <= 1.5 KB) |
| `state/NOW.md` | 35 KB |
| `state/FINDINGS.md` | 36 KB |
| `state/CONTRADICTIONS.md` | 20 KB |
| `KNOWLEDGE-MAP.md` | 14 KB |
| `AGENTS.md` | 20 KB |
| `CLAUDE.md` | 4 KB (thin) |
| `docs/tribal/<quarter>.md` | about 300 KB, then split |

## Checkpoint / flush / thresholds (the whole discipline)

- `checkpoint` (about 20 s) overwrites the <= 1.5 KB `## Live thread (checkpoint)` block at the top of `state/BRIEF.md`.
  It records the last operator instruction verbatim, what was in flight, next action, decisions with WHY, dead ends.
  Run it after every operator decision, every completed step, and before any long operation.
- `flush` is the full reconcile: registers, history, pitfalls, memory on the Claude seat, BRIEF rewrite.
  It always ends with a fresh checkpoint. `verify-flush` runs lint.
- Context thresholds: **50%** checkpoint at every decision point. Above 60%: shorter answers,
  verify every claim. **62%** finish the current step, flush, end the session with the line
  "flushed at NN%, start a new session". **70%** hard ceiling, never crossed (hallucination is
  observed from ~72%). Ending at 62% is the normal path; compaction is only a crash fallback.
  Codex has no context meter and no hooks: flush at every natural break and whenever the
  operator says "handoff".
- BRIEF carries a `## Alignment (answer before work starts)` section directly after the Live
  thread block: 1 to 5 numbered one-line questions the next session cannot settle from files
  (an assumption made, a half-done step, a choice the operator has not made, a scope doubt), or
  the single line `none`. Written by flush only; checkpoint never touches it; `verify-flush`
  requires it.
- Resume (fresh session or after compaction): restate the Live thread in <= 5 lines, list the
  Alignment questions as written, and ask ONCE: "No issues? Then I continue with <Next action>."
  "go", "no issues" or "continue" means proceed; an answer to a question is applied first. If the
  section says `none`, ask only the one-line continue question.
- Claude Code's SessionStart hook injects BRIEF with its age. Its PreCompact hook prints the Live
  thread block into the compaction. Codex has no hooks and gets the same behavior from the text in
  `AGENTS.md` (Claude Code reads the same text through `@AGENTS.md`).
- The live system always wins over any file. Never write a secret's value into any KB file.
