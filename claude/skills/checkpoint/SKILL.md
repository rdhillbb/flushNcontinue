---
name: checkpoint
description: Write a ≤ 1.5 KB live-thread checkpoint into the current repo's `state/BRIEF.md` so a crash or compaction mid-exchange loses nothing: the operator's last instruction verbatim, what the assistant was doing, the next action, decisions + dead ends so far, the open question. Registers and history are NOT touched (that is the flush skill). Run it at every decision point, after every completed step, before any long operation, and at 62% context right before flush. Use when the user says checkpoint, save the thread, mark where we are, or before a risky/long step. Universal skill (Claude Code and Codex); ~20 seconds; no narration.
user-invocable: true
argument-hint: [optional one-line note]
allowed-tools: Read, Write, Edit, Bash(git *), Bash(date *), Bash(bash *)
---

# checkpoint — save the live thread, right now

A crash or a context compaction in the middle of a deep exchange loses the dialog: what the
operator just said, what you were in the middle of, what comes next. The `flush` skill runs once
at the end and cannot help mid-session. The `checkpoint` skill (Claude Code: `/checkpoint`;
Codex: `checkpoint`) writes the live thread to disk in seconds so a fresh session (or a
post-compaction you) can pick up the exact sentence.

This skill is **universal**: the same body runs in both seats. Source of truth:
`~/apps/factorymaterial/claude/skills/checkpoint/SKILL.md`. The Claude seat
(`~/.claude/skills/checkpoint`) is a symlink to the source; `~/bin/sync_kb_skills.sh` copies it
into the Codex seat (`~/.codex/skills/checkpoint`). Edit the source, then sync.

**Precondition.** The repo must have `state/BRIEF.md` (a knowledge-base repo). If it is absent,
say so in one line and stop. Do not create a KB, a BRIEF, or any other file (that is the
`kbinit` skill).

## What to write

Exactly ONE block in `state/BRIEF.md`, placed directly after the header `Updated:` line. If a
`## Live thread (checkpoint)` block already exists, **overwrite it**; never stack a second one.

```markdown
## Live thread (checkpoint) — <YYYY-MM-DD HH:MM zone>

Agent: <Claude Code | Codex | other>
Task: <the task in one line>
Last operator instruction (verbatim, short): "<their words>"
I was doing: <the step in progress, and the file/commit/TO it touches>
Next action: <the single next thing to do>
Decisions this session (with WHY): <decision — because "<operator words>">; or none
Dead ends tried: <what failed and why it was abandoned>; or none
Open question for operator: <one question>; or none
Uncommitted: <N paths (git status --short | wc -l)>; or "verify with git status"
Context at checkpoint: <~NN%>; or unknown
```

Rules for the block:
- `Agent:` is the FIRST labelled line and names who wrote the block (Claude Code, Codex, or other). The operator switches between Codex and Claude mid-work; both seats read and write the same files (`state/BRIEF.md`, `state/NOW.md`, `docs/tribal/`), so a switch carries over through them.
- Every labelled line is present (10 in total), each ≤ 2 lines. `none` is a valid value. `unknown` is a valid
  value for context — if the agent cannot see its context share, write `unknown`. Never leave a
  label blank.
- **Never invent.** Quote the operator. If the exact words are gone from context, paraphrase and
  mark it `(paraphrased)`. If the WHY behind a decision is not known, write `WHY not stated`.
- The block is ≤ 1.5 KB. `state/BRIEF.md` stays ≤ 8 KB. If the checkpoint would push BRIEF
  over, shorten the **checkpoint**, never the rest of BRIEF.
- The optional argument (a one-line note) is appended to the `Task:` line in parentheses.

## What NOT to touch

- Everything else in `state/BRIEF.md` (the session thread, current state, read-next list) stays
  byte-identical, with two exceptions that keep the next session from reading stale facts:
  1. The header line becomes `Updated: <stamp> | Branch: verify with git branch --show-current | Tree: verify with git status`
     (never a path count; counts go stale between checkpoint and resume).
  2. In `## Alignment (answer before work starts)`, a question that was answered or made obsolete
     this session gets ` -> RESOLVED <date>: <answer or reason>` appended. Never add, reword or
     delete a question; writing new questions is `flush` only.
- Do not edit `state/NOW.md`, `state/FINDINGS.md`, `state/CONTRADICTIONS.md`, the history
  timeline, pitfalls, or memory. That is the `flush` skill.
- Do not `git add`, commit, or push.
- Do not run the `flush` skill from here.

## Procedure

1. `date '+%Y-%m-%d %H:%M %Z'` for the timestamp; `git status --short | wc -l` for the
   uncommitted count (if not a git repo, write "verify with git status").
2. Read `state/BRIEF.md`. Locate the header `Updated:` line and any existing
   `## Live thread (checkpoint)` block (it ends at the next `## ` heading).
3. Compose the block from THIS conversation — you are the only source for it.
4. Replace the existing block, or insert the new one directly after the header line.
5. Check sizes (block ≤ 1.5 KB, file ≤ 8 KB). Shorten the block if needed.

## Narration

At most one line to the operator:

`checkpoint written <HH:MM> — <Next action in ≤ 10 words>`

Nothing else. No summary of the session, no restating the block.

## Triggers — run it

- (a) after each operator decision,
- (b) after each completed step of a multi-step task,
- (c) before any long operation (build, factory run, large review, deploy, big read),
- (d) at 62% context, right before `flush` (and from 50% on, at every decision point; see the
  Context Management thresholds in the global operating file: `~/.claude/CLAUDE.md` for Claude
  Code, `~/.codex/AGENTS.md` for Codex),
- (e) whenever the operator says "checkpoint", "save the thread", "mark where we are".

## Resume protocol (the other half)

In a fresh session (the normal path: the previous session ended with a flush at 62%) or after a
compaction (crash fallback only), get `state/BRIEF.md` in front of you first: Claude Code's
SessionStart hook injects it, and so does Codex's (`~/.codex/hooks.json`). Do not read it again when it
is already in context; an agent without a hook must `cat state/BRIEF.md` first.
Then:

1. Read the `## Live thread (checkpoint)` block and restate it to the operator in ≤ 5 lines.
2. List the `## Alignment (answer before work starts)` questions exactly as written. Skip any marked
   `RESOLVED`; mention them in one line ("resolved since flush: N").
3. Ask ONCE: "No issues? Then I continue with <Next action>."

Operator "go", "no issues", or "continue" means proceed with the recorded next action. An answer
to a question is applied first, then proceed. If the section says `none`, ask only the one-line
continue question. This is what the operator did by hand at every new session; now the files
carry it. If the block was written by the other agent (`Agent:` says Codex and you are Claude, or
the reverse), that is normal; continue from it, do not restart.

On compaction: the SessionStart hook re-injects BRIEF afterwards, so the block must be fresh.
Write it before any long step.

## Relationship to the flush skill

- `checkpoint` = the live thread only. Seconds. Many times per session.
- `flush` (Claude Code: `/flush`; Codex: `flush`) = the full knowledge-base reconcile (registers,
  history, memory, BRIEF rewrite including the `## Alignment` section). Once per handoff, and at
  62% context, after which the session ends with "flushed at NN%, start a new session". Never
  work past 70%. A flush always ends with a fresh checkpoint block.
