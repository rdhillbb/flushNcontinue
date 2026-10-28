#!/bin/bash
# session-start.sh — Claude Code SessionStart hook.
# Injects state/BRIEF.md (the session handoff) so a new session continues where the
# last one stopped, then prints the time reference and runs the repo's health check.
# Runs in the repo Claude was started in. Read-only. macOS and Linux.

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
CP="/checkpoint"; FL="/flush"

mtime() { date -r "$1" '+%Y-%m-%d %H:%M' 2>/dev/null || echo unknown; }

if [ -f state/BRIEF.md ]; then
  echo '=== SESSION BRIEF (maintained by flush/checkpoint) ==='
  echo "BRIEF last modified: $(mtime state/BRIEF.md)  |  last commit: $(git log -1 --format='%h %ci' 2>/dev/null | cut -c1-30)  |  uncommitted paths: $(git status --short 2>/dev/null | wc -l | tr -d ' ')"
  cat state/BRIEF.md
  echo '=== END BRIEF — for depth: KNOWLEDGE-MAP.md -> state/NOW.md -> state/FINDINGS.md. Live system wins over files. ==='
  echo "RESUME PROTOCOL: restate the Live thread block in <= 5 lines, list the Alignment questions from BRIEF as written, and ask once: No issues? Then I continue with <next action>. go / no issues / continue = proceed. Run $CP at every decision point; at 62% context finish the step, run $FL, end the session; never past 70%."
elif [ -f KNOWLEDGE-MAP.md ]; then
  echo '=== KB ACTIVATION (no state/BRIEF.md yet — run flush to create it) ==='
  echo 'Read in order: 1) KNOWLEDGE-MAP.md  2) state/NOW.md  3) state/CONTRADICTIONS.md  4) state/FINDINGS.md.'
  echo 'Rules: live system wins over any file; never trust snapshots of volatile facts (git status, HEAD) — query live.'
  echo '=== END ACTIVATION ==='
fi

[ -f ".claude/hooks/session_time.sh" ] && bash ".claude/hooks/session_time.sh"
[ -f scripts/kb/session_health.sh ] && bash scripts/kb/session_health.sh
exit 0
