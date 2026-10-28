#!/bin/bash
# kb_handoff.sh — open the NEXT session in a new Herdr tab after a flush and hand it the
# resume protocol, so the operator does not have to start it and type the questions by hand.
#
#   kb_handoff.sh [--repo DIR] [--label TEXT] [--kind claude|codex] [--no-prompt]
#
#   --repo DIR     repo with state/BRIEF.md (default: current directory)
#   --label TEXT   tab label (default: "<repo basename> handoff <HH:MM>")
#   --kind KIND    agent to start (default: claude)
#   --no-prompt    create the tab and start the agent, but do not send the resume prompt
#
# Preconditions: running inside Herdr (HERDR_ENV=1) with the `herdr` CLI on PATH, and
# state/BRIEF.md present (flush must have run; verify-flush PASS). Exit 0 and print the
# pane id on success; any other exit means "print the end line and let the operator open
# the session". Nothing here edits the repo.
set -u

REPO="$PWD"; LABEL=""; KIND="claude"; PROMPT=1
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --kind) KIND="$2"; shift 2 ;;
    --no-prompt) PROMPT=0; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "kb_handoff: unknown argument $1" >&2; exit 2 ;;
  esac
done

[ "${HERDR_ENV:-}" = "1" ] || { echo "kb_handoff: not inside Herdr (HERDR_ENV unset)" >&2; exit 3; }
command -v herdr >/dev/null 2>&1 || { echo "kb_handoff: herdr CLI not on PATH" >&2; exit 3; }
REPO="$(cd "$REPO" 2>/dev/null && pwd -P)" || { echo "kb_handoff: repo dir not found" >&2; exit 2; }
[ -f "$REPO/state/BRIEF.md" ] || { echo "kb_handoff: $REPO/state/BRIEF.md missing; run flush first" >&2; exit 2; }
[ -n "$LABEL" ] || LABEL="$(basename "$REPO") handoff $(date '+%H:%M')"

created="$(herdr tab create --cwd "$REPO" --label "$LABEL" 2>&1)" || { echo "kb_handoff: tab create failed: $created" >&2; exit 4; }
read -r PANE TAB <<EOF
$(printf '%s' "$created" | python3 -c 'import sys, json
d = json.load(sys.stdin).get("result", {})
print(d.get("root_pane", {}).get("pane_id", ""), d.get("tab", {}).get("tab_id", ""))' 2>/dev/null)
EOF
[ -n "${PANE:-}" ] || { echo "kb_handoff: could not read pane id from: $created" >&2; exit 4; }

NAME="handoff-$(date '+%H%M%S')"
if ! started="$(herdr agent start "$NAME" --kind "$KIND" --pane "$PANE" 2>&1)"; then
  echo "kb_handoff: agent start failed: $started" >&2
  echo "kb_handoff: tab $TAB is open with a shell; start $KIND there by hand" >&2
  exit 5
fi

MSG="New session after a flush. Read state/BRIEF.md and run the resume protocol: restate the Live thread in 5 lines, list the Alignment questions as written, and ask once: No issues? Then I continue with the next action."
if [ "$PROMPT" = 1 ]; then
  herdr agent prompt "$NAME" "$MSG" >/dev/null 2>&1 || { echo "kb_handoff: agent started in pane $PANE but the prompt was not accepted; paste it by hand" >&2; exit 6; }
fi
echo "kb_handoff: next session ready in tab $TAB (pane $PANE, agent $NAME, $KIND)"
