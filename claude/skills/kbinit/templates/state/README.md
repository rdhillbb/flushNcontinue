# state/ — the HOT register tier

This directory is the **register tier** of the knowledge system: small, freshness-stamped,
read (or injected) at the start of every session. Maintained by the `flush` and `checkpoint`
skills (Claude Code: `/flush`, `/checkpoint`). Entry point and precedence: `../KNOWLEDGE-MAP.md`.
Health check: `bash scripts/kb/kb_lint.sh`. The checker reads the register paths from
`kb-layout.json` here; keep it in step with the map.

| File | Answers | Lifecycle | Budget |
|---|---|---|---|
| `BRIEF.md` | Where did the last session stop; what was decided; what is next? Top block = `## Live thread (checkpoint)`, overwritten by `checkpoint` many times per session | whole file overwritten every `flush`; injected by the session-start hook | 8 KB (live thread ≤ 1.5 KB) |
| `NOW.md` | What is true *right now*? | facts edited in place with `last_verified`; ONE `## Current focus` block | 35 KB |
| `NOW-ARCHIVE.md` | Which focus blocks were superseded? | append-only, verbatim copies, newest first (COLD) | none |
| `CONTRADICTIONS.md` | Which docs are *stale*? (`C-NN`) | rows close as docs are fixed at source; IDs kept | 20 KB |
| `FINDINGS.md` | Which findings are *open*? (`F-NN`, one line each) | shrinks as findings close; audit trail, never deleted | 36 KB |
| `FINDINGS-DETAIL.md` | Full narrative per finding | append-only (COLD — grep the `F-NN`) | none |
| `kb-layout.json` | Which path is the home for each register (for `kb_tools.py`) | changes only by a planned home migration | none |

A repo may map these homes to other paths (see `kb-layout.json`); the roles above still apply.

**Rules**
- The live system wins over any file. Never snapshot a volatile fact (working-tree status, exact
  HEAD, live health, credentials) — write "query live" and how.
- Each fact has exactly one home. Point, don't copy. BRIEF is a snapshot of facts that live here.
- Never write a secret's value here — key name + "fetch live" only.
- IDs: one writer; read the register immediately before assigning the next `F-`/`C-`. Never reuse,
  never delete.
- Budgets are bytes, not lines. Over budget in `NOW.md` means a focus block became history —
  archive it verbatim in `NOW-ARCHIVE.md`. Over budget in `FINDINGS.md` means narrative crept in —
  move it to `FINDINGS-DETAIL.md`.
- History and archived narrative are immutable; `verify-flush` enforces it.
