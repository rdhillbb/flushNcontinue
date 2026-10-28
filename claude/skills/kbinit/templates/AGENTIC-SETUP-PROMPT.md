# Agentic-coding setup — analysis + migration prompt

> **Updated 2026-10-19:** the two template sets were merged. The one template set is
> `~/apps/factorymaterial/claude/kb/` and the engine is `~/apps/factorymaterial/scripts/kb_tools.py`
> (`init`, `snapshot`, `append-history`, `verify-flush`, `lint`, `health`). Quick start in Claude Code:
> `/kbinit`; or paste this task into any seat:
>
> ```xml
> <task>
> Initialize or upgrade the repository knowledge base in <repo> using
> ~/apps/factorymaterial/claude/kb/procedures/kbinit.md and ~/apps/factorymaterial/scripts/kb_tools.py.
> Preserve all existing registers and history entries, verify `bash scripts/kb/kb_lint.sh` passes
> with 0 errors, and leave all changes uncommitted.
> </task>
> ```

Written 2026-09-28 (KHT). Paste this file into a fresh session (any repo) when you want the
analysis or the migration redone. It is self-contained: the principles, how our knowledge-base
(KB) system maps to them, what was built on 2026-09-28, the per-repo process, and the exact
steps to analyze a repo. Source of truth for the tooling: `~/apps/factorymaterial/claude/kb/` (templates, hooks, procedures) and `~/apps/factorymaterial/scripts/kb_tools.py` (engine).

## Why

The operator works solo, in Cambodia, switching between Claude Code and Codex, often across
context resets. Productivity in agentic coding is limited by SETUP, not model skill: a session
that loses the reasoning behind decisions, repeats a dead end, or trusts a stale snapshot wastes
the next hour. The goal is a setup where any fresh session (or the other agent seat) resumes
mid-thought, verifies the live system before trusting a file, and where recurring mistakes
become automated checks instead of prose.

## The six principles (from the article summary the operator pasted 2026-09-28)

Sources named in that summary: Lauren Tan's Cursor Compile talk (~2,000 PRs/month, Pstack
plugin), Shopify's River agent + Aquifer platform, Addy Osmani's "outer loop", Justin Young on
long-running agents, Lewis Metcalf's playgrounds, Nate's Faster Factory Kit.

1. **Make agents multiplayer** — work and context live where the team AND agents can reuse them,
   not in a private chat.
2. **Separate work history from the active workspace** — session history stored outside the
   chat, so model swaps, restarts and compaction do not destroy the record or the WHY.
3. **Keep humans accountable for what ships** — the human owns the outer loop (goals,
   boundaries, judging output); automated tests, permission boundaries and checks enforce it.
4. **Structure work for seamless handoffs** — progress notes, checklists, "verify the app runs"
   at session start; never delete a failing item to make a checklist green.
5. **Give agents ways to inspect their own work** — checkers, playgrounds, docs; turn each
   recurring mistake into a reusable skill AND an automated check.
6. **Eliminate obsolete processes** — do not recreate human bureaucracy for agents; whiteboard
   the direct path; measure before adding ceremony.

## How our KB system maps to them

| Principle | Mechanism (repo files unless noted) |
|---|---|
| 1 Multiplayer | KB in the repo; both seats read/write `state/BRIEF.md`, `state/NOW.md`, `docs/tribal/`; one rules file `AGENTS.md` (Codex reads it; a thin `CLAUDE.md` imports it with `@AGENTS.md` and adds only Claude-Code-only items); skills installed in both seats from `~/apps/factorymaterial/claude/skills/` via `~/bin/sync_kb_skills.sh` |
| 2 History vs workspace | `state/BRIEF.md` (handoff snapshot, ≤ 8 KB, Live thread block ≤ 1.5 KB) · registers `state/NOW.md` (facts now), `state/FINDINGS.md` + `FINDINGS-DETAIL.md`, `state/CONTRADICTIONS.md` · append-only ledger `docs/tribal/<quarter>.md` (newest at top) · pitfalls `P-NN` · `checkpoint` skill (seconds, many times) and `flush` skill (full reconcile) · PreCompact hook prints the Live thread into the compaction |
| 3 Accountability | Rule: commit / push / deploy only when the operator says so · deploy-window gate · secrets only in Parameter Store, never in files · PreToolUse guard blocks known-bad commands |
| 4 Handoffs | Resume protocol: restate the Live thread in ≤ 5 lines, list the `## Alignment` questions flush wrote into BRIEF, ask once "No issues? Then I continue with <Next action>." · `scripts/kb/session_health.sh` at session start (git + remote drift vs upstream, build, prod health, local services, BRIEF age) · never delete a finding; history append-only |
| 5 Self-inspection | `scripts/kb/kb_lint.sh` (wraps `kb_tools.py lint`: budgets, next IDs, dead pointers, secret hygiene, resume read cost) · `kb_tools.py verify-flush` (immutability of history, archive and IDs after every flush) · `scripts/hooks/pretooluse-guard.sh` (mechanical checks for promoted dead ends) · flush rule: every dead end is promoted to a `P-NN`, cited, or dropped with a reason |
| 6 Obsolete process | Lint prints the resume read cost (fixed load vs Read-next worst case) so ceremony is measured, not assumed; byte budgets on every HOT file |

## Assessment of 2026-09-28 (FaxItOnce repo, before that day's changes)

- Fully covered before: principles 1, 2, 3 and the second half of 4. About 75-80% of the
  article, honestly counted; the credit is the KB system as a whole, flush is its mechanism.
- Gaps closed that day: 4 (first half) — session-start health probe; 5 — guard hook + the
  dead-end promotion rule in flush.
- Made measurable, not cut: 6 — fixed resume load 53 KB (~13k tokens); Read-next worst case
  665 KB. The auto-memory index (22 KB) is the largest fixed item. No file cut; operator's call.
- Fallout: the broader secret pattern found a local DB password written in 8 tracked markdown
  files (redacted) and 24 code/script files (open, F-105 in FaxItOnce).

## Tooling built 2026-09-28 (now under `~/apps/factorymaterial/claude/kb/`, copied per repo)

- `scripts/kb/session_health.sh` — CONFIG block per project (PROD_HEALTH_URL, LOCAL_TCP_PORTS,
  CHECK_POSTGRES, TZ_LABEL); build auto-detect; always exit 0. The global Claude SessionStart
  hook (`~/.claude/settings.json`) runs it when executable; Codex runs it by hand.
- `scripts/hooks/pretooluse-guard.sh` + `settings.pretooluse.json` — blocks `psql -v … -c`,
  bare `git stash` in a linked worktree, log redirects into `/tmp/*.log`. Active from the NEXT
  session after wiring.
- `scripts/kb/kb_lint.sh` — thin wrapper over `scripts/kb/kb_tools.py lint --text`: resume read cost;
  literal-password checks (`.claude/settings.local.json`, `state/ docs/ tasks/`); repo-generic auto-memory path.
- `~/apps/factorymaterial/scripts/kb_upgrade.sh` (linked from `~/bin`) — idempotent upgrade of a repo that already has a KB:
  `--dry-run`, `--all` (sweeps `~/go/src` and `~/apps`), `--force-lint` (backup kept). Never
  touches registers, history or BRIEF.
- Skills `checkpoint`, `flush`, `kbinit` — flush step 4 now requires the dead-end tally; kbinit
  installs the three new pieces and documents upgrade mode.

## Process per repo type

| Repo state | Command | Notes |
|---|---|---|
| New project | `/projectsetup` (calls `/kbinit` last) | ports first, then CLAUDE.md/PORTS.md, then KB |
| Has `KNOWLEDGE-MAP.md` + `state/BRIEF.md` | `~/bin/kb_upgrade.sh .` (writes `state/kb-layout.json` if absent) | repeatable; then fill the probe's CONFIG block |
| Has only `zero.md` / bare `CLAUDE.md` | `/kbinit` in that repo | migrates zero.md; asks for the health config |
| Old-layout KB (huge NOW/FINDINGS, no DETAIL, no tribal, zero.md live) | a KB review session: snapshot to `archive/kb-review-<date>/before/`, split FINDINGS → DETAIL, demote NOW history to `docs/tribal/NOW-focus-archive-<date>.md`, open `docs/tribal/`, retire zero.md to a pointer, fix dead pointers, then rewrite BRIEF | done for FaxItOnce 2026-09-07 and cmmc-sentinel-OCI 2026-09-28 |

Always end with `/checkpoint` so the first BRIEF block exists for the next session.

## The analysis to run in any repo (paste as the task)

1. Run `bash .claude/hooks/session_time.sh`, then `bash scripts/kb/kb_lint.sh` and
   `bash scripts/kb/session_health.sh` if they exist. Record every WARN.
2. For each of the six principles, state: covered / partial / missing, with the file or hook that
   proves it. Do not award credit from memory — open the file.
3. Measure the resume cost (lint prints it). List what a fresh session actually reads.
4. List dead ends recorded in BRIEF that have no `P-NN`. Each needs a fate: promote, cite, drop.
5. Check secret hygiene beyond the lint: `git grep -n` for any password value the operator
   names; report file counts only, never the value.
6. Produce: a table of principle → status → gap → fix, a per-file byte table vs budget, and an
   ordered fix list with the command for each. Change nothing until the operator says so,
   except a `.gitignore` line for an unignored secret file, which is always safe.

## Rules that must hold everywhere

- Facts only: verify before asserting; "unknown" beats a confident guess.
- Never write a secret's value into any file; key name + "fetch live".
- Never delete a finding or a history entry; append-only, newest at top.
- Commit, push, deploy only on the operator's word. `/flush` leaves everything uncommitted.
- Concurrent writers clobber registers: one writer per register file at a time.
- Snapshot before any KB restructure (`archive/kb-review-<date>/before/`).

## Open items as of 2026-09-28

- 48 legacy repos still need `/kbinit` (one session each). 15 KB repos are upgraded.
- FaxItOnce: F-135 (3 password allow rules in `.claude/settings.local.json`), F-105 (24 code
  files with the local DB password), AGENTS.md over its 20 KB budget.
- cmmc-sentinel-OCI: KB review in progress 2026-09-28 (FINDINGS split, NOW slim, ledger,
  zero.md retire).
- Decide whether the 22 KB auto-memory index should be trimmed (principle 6).
