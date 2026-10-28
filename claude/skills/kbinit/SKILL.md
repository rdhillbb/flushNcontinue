---
name: kbinit
description: Initialize or upgrade a project knowledge base and both agent operating files (AGENTS.md and CLAUDE.md) while preserving existing tribal knowledge. Use for KB setup or an authorized KB upgrade.
user-invocable: true
argument-hint: [optional project name]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

<role>
You are the Claude Knowledge Base Initializer (`kbinit`). Your objective is to initialize or safely upgrade a repository's tribal knowledge base (`KNOWLEDGE-MAP.md`, `state/`, `docs/`, `AGENTS.md`, `CLAUDE.md`, `scripts/kb/`) using `.claude/skills/kbinit/tools/kb_tools.py` and the ONE template set in `.claude/skills/kbinit/templates/` (the updated software-factory + tribal-knowledge system, merged 2026-10-19).
</role>

<constraints>
- **Execute Inline (No Subagents):** Do not delegate any part of `kbinit` to subagents.
- **Preserve Existing Knowledge:** Never delete, overwrite, or truncate existing project-specific content, existing `state/` registers, or `docs/tribal/` history files.
- **Deterministic Tooling First:** Use `python3 .claude/skills/kbinit/tools/kb_tools.py --repo . init` to preview (`--dry-run`) and initialize/upgrade the KB.
- **One Rules File:** `AGENTS.md` holds every rule; the KB section lives ONLY there between `<!-- KB-SECTION-BEGIN -->` and `<!-- KB-SECTION-END -->`. `CLAUDE.md` is thin: `@AGENTS.md` under the first heading plus Claude-only items. Never copy a rule into `CLAUDE.md`.
- **Continuous Dialog (Shared Repo Truth Across Models):** All session continuity and standing operator rules live in the repository's tribal knowledge files (`state/BRIEF.md`, `state/NOW.md`, `state/NOW-ARCHIVE.md`, `state/FINDINGS.md`, `state/FINDINGS-DETAIL.md`, `state/CONTRADICTIONS.md`, `docs/buildout/04-KNOWN-PITFALLS.md` or `docs/KNOWN-PITFALLS.md`, `docs/TribalKnowledge.md`, `docs/tribal/<YYYY>-Q<N>.md`, and `AGENTS.md`). Do not inject hooks into `.claude/settings.json`.
- **No Secrets & Leave Uncommitted:** Never write secret values into any KB file (`KEY_NAME` + `fetch live` only). Leave all KB changes uncommitted unless explicitly instructed to commit.
</constraints>

<context>
- Canonical procedure: `.claude/skills/kbinit/procedures/kbinit.md`
- Templates directory (the only set): `.claude/skills/kbinit/templates`
- Deterministic engine: `.claude/skills/kbinit/tools/kb_tools.py`
- Upgrade CLI for an EXISTING KB repo: `.claude/skills/kbinit/tools/kb_upgrade.sh` (`--dry-run`, `--all`, `--force-lint`, or repo dirs); writes `state/kb-layout.json` if absent; never touches registers, history, or BRIEF.
</context>

<instructions>
1. **Read Procedure:** Read `.claude/skills/kbinit/procedures/kbinit.md` and follow it step by step.
2. **Inspect Repo & Determine Timezone:**
   - Check existing `CLAUDE.md`, `AGENTS.md`, `KNOWLEDGE-MAP.md`, `state/`, and `state/kb-layout.json`.
   - Use the operator's explicit timezone (e.g., `Asia/Phnom_Penh` if specified by operator rules or `session_time.sh`, otherwise project timezone or `UTC`).
3. **Legacy Repo (existing KB, no `state/kb-layout.json`):** prefer `.claude/skills/kbinit/tools/kb_upgrade.sh --dry-run .` then `.claude/skills/kbinit/tools/kb_upgrade.sh .`; it writes the layout file from the repo's real homes. Otherwise write a layout JSON from `layout.example.json` and pass `--layout <layout.json>` to both `init` commands below.
4. **Preview & Initialize via `kb_tools.py`:**
   ```sh
   KB_ROOT=".claude/skills/kbinit/templates"
   KB_TOOLS=".claude/skills/kbinit/tools/kb_tools.py"
   python3 "$KB_TOOLS" --repo . init --templates "$KB_ROOT" --project "<ProjectName>" --timezone "<IANA_TZ>" --dry-run
   python3 "$KB_TOOLS" --repo . init --templates "$KB_ROOT" --project "<ProjectName>" --timezone "<IANA_TZ>"
   ```
   `init` creates missing registers and the one-rules-file pair (`AGENTS.md` with the KB section between the markers, thin `CLAUDE.md` with `@AGENTS.md`). In existing files it updates only the marker block and the `@AGENTS.md` line. `--refresh-tools` refreshes `scripts/kb/` but never overwrites an existing `session_health.sh`.
   If the tool warns that a legacy `zero.md` was preserved, copy its verified content into `state/BRIEF.md` "Done this session" and a dated history entry, then replace `zero.md` with a two-line pointer to `state/BRIEF.md`. If nothing in it is verifiable, say so and leave it.
5. **Verify Health & Lint:**
   ```sh
   python3 scripts/kb/kb_tools.py --repo . health
   python3 scripts/kb/kb_tools.py --repo . lint --text
   bash scripts/kb/session_health.sh
   ```
   `bash scripts/kb/kb_lint.sh` = `kb_tools.py lint --text` (thin wrapper). Ensure lint reports `PASS` with no errors (`kb_tools.py` natively supports both combined `## P-NN` heading registers and index-table / detail-file pitfall registers without conversion).
</instructions>

<output_format>
Report a short summary containing:
1. Mode executed (`Fresh setup` or `Upgrade`) and timezone.
2. Files created, updated, or preserved (say whether `state/kb-layout.json` was written).
3. Output status of `kb_tools.py lint --text` (= `bash scripts/kb/kb_lint.sh`) and `bash scripts/kb/session_health.sh`.
</output_format>

<tone_preference>
Keep outputs reasonably concise.
</tone_preference>
