#!/bin/bash
# pre-compact.sh — Claude Code PreCompact hook.
# Prints the Live thread block of state/BRIEF.md so the compaction summary keeps it.
# Compaction is a crash fallback; the normal path is flush at 62% and a new session.

echo 'PRE-COMPACT: the summary MUST preserve verbatim the following live thread (task, last operator instruction, what I was doing, next action, decisions with WHY, dead ends, open question). If it is stale, the block below is still the best anchor. If this is a KB repo and there is time, run checkpoint or flush now.'
if [ -f state/BRIEF.md ]; then
  awk '/^## Live thread/{p=1;print;next} /^## /{if(p)exit} p' state/BRIEF.md
else
  echo '(no state/BRIEF.md in this repo — carry the thread from context)'
fi
exit 0
