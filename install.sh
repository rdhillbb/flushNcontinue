#!/bin/bash
# install.sh — install the flushNcontinue knowledge-base skills into ONE project.
#
#   bash install.sh <projectdir> --dry-run   show what would change, write nothing
#   bash install.sh <projectdir>             install (safe to run again; it only fixes what differs)
#   bash install.sh <projectdir> --check     verify an install, write nothing; exit 1 on a problem
#
# Copies (no links) into <projectdir>/.claude/:
#   skills/checkpoint/  skills/flush/  skills/kbinit/   the three skills and their files
#   hooks/session-start.sh  hooks/pre-compact.sh  hooks/session_time.sh
#   settings.json        SessionStart + PreCompact hooks merged in; other settings kept
#
# Never: deletes anything (a replaced file or folder is moved to
# <projectdir>/.claude/backups/flushNcontinue-<stamp>/), touches your home folder,
# runs git. You decide whether to commit the result.
# Works on macOS, Linux and Windows (Git Bash). Needs: bash, python3.

set -u
PROJ="" ; MODE="install"
for a in "$@"; do
  case "$a" in
    --dry-run) MODE="dry" ;;
    --check)   MODE="check" ;;
    -*) echo "unknown option: $a"; exit 2 ;;
    *)  if [ -z "$PROJ" ]; then PROJ="$a"; else echo "only one project directory, please"; exit 2; fi ;;
  esac
done
if [ -z "$PROJ" ]; then
  echo "usage: bash install.sh <projectdir> [--dry-run|--check]"; exit 2
fi
[ -d "$PROJ" ] || { echo "STOP   project directory not found: $PROJ"; exit 1; }

REPO="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$PROJ" && pwd)"
DOT="$PROJ/.claude"
STAMP="$(date '+%Y%m%d-%H%M%S')"
BACKUP="$DOT/backups/flushNcontinue-$STAMP"
SKILLS="checkpoint flush kbinit"
HOOKS="session-start.sh pre-compact.sh session_time.sh"
PROBLEMS=0

ok()   { echo "ok     $*"; }
todo() { if [ "$MODE" = "check" ]; then echo "WARN   $*"; PROBLEMS=$((PROBLEMS+1)); else echo "do     $*"; fi; }
fail() { echo "STOP   $*"; exit 1; }
run()  { if [ "$MODE" = "install" ]; then "$@"; fi; }

# keep REL — move <DOT>/REL into the backup folder before it is replaced
keep() {
  run mkdir -p "$(dirname "$BACKUP/$1")"
  run mv "$DOT/$1" "$BACKUP/$1"
  echo "       (old copy kept in .claude/backups/flushNcontinue-$STAMP/$1)"
}

# put SRC REL — copy SRC (file or folder) to <DOT>/REL unless it is already identical
put() {
  local src="$1" rel="$2" dst="$DOT/$2"
  if [ -e "$dst" ] && diff -r -q "$src" "$dst" >/dev/null 2>&1; then ok ".claude/$rel"; return; fi
  todo "copy .claude/$rel"
  if [ -e "$dst" ]; then keep "$rel"; fi
  run mkdir -p "$(dirname "$dst")"
  run cp -R "$src" "$dst"
}

echo "flushNcontinue — mode: $MODE — project: $PROJ"
echo ""

# ---- 0. pre-flight -------------------------------------------------------------------
if ! { command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; }; then
  fail "python3 (3.8 or newer) does not run in this shell. Windows: install Python from the Microsoft Store, then reopen Git Bash."
fi
ok "python3 $(python3 -c 'import platform; print(platform.python_version())')"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) ok "Windows (Git Bash)" ;; esac
[ -f "$REPO/claude/skills/kbinit/SKILL.md" ] || fail "run this from a complete flushNcontinue clone (claude/skills missing)"

# ---- 1. skills -------------------------------------------------------------------------
for s in $SKILLS; do put "$REPO/claude/skills/$s" "skills/$s"; done

# ---- 2. hook scripts --------------------------------------------------------------------
for h in $HOOKS; do put "$REPO/claude/hooks/$h" "hooks/$h"; done

# ---- 3. hooks in <project>/.claude/settings.json ---------------------------------------
python3 - "$DOT/settings.json" "$HOME/.claude/settings.json" "$MODE" "$BACKUP" <<'PY'
import json, os, sys, shutil
path, user_path, mode, backup = sys.argv[1:5]
start = 'bash "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/session-start.sh"'
pre   = 'bash "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/pre-compact.sh"'

def load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p, encoding="utf-8") as fh: return json.load(fh)
    except Exception as e:
        print(f"STOP   {p} is not valid JSON ({e}); fix it by hand, then re-run"); sys.exit(3)

def has(data, event, markers):
    return any(any(m in h.get("command", "") for m in markers)
               for g in data.get("hooks", {}).get(event, []) for h in g.get("hooks", []))

data, user = load(path), load(user_path)
want = [("SessionStart", start, 60, ["session-start.sh", "SESSION BRIEF"]),
        ("PreCompact",   pre,   10, ["pre-compact.sh", "PRE-COMPACT"])]
add = []
for ev, cmd, t, markers in want:
    if has(data, ev, markers):
        print(f"ok     .claude/settings.json: {ev} hook present")
    elif has(user, ev, markers):
        print(f"ok     {ev}: your personal ~/.claude/settings.json already does this; not added here (it would run twice)")
    else:
        add.append((ev, cmd, t))
if not add: sys.exit(0)
for ev, _, _ in add:
    print(("WARN   " if mode == "check" else "do     ") + f".claude/settings.json: add {ev} hook")
if mode == "check": sys.exit(1)
if mode == "dry": sys.exit(0)
hooks = data.setdefault("hooks", {})
for ev, cmd, t in add:
    hooks.setdefault(ev, []).append({"matcher": "", "hooks": [{"type": "command", "shell": "bash", "command": cmd, "timeout": t}]})
if os.path.exists(path):
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(path, os.path.join(backup, "settings.json"))
    print(f"       (old copy kept in .claude/backups/{os.path.basename(backup)}/settings.json)")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(data, fh, indent=2); fh.write("\n")
PY
rc=$?
[ $rc -eq 3 ] && exit 1
[ $rc -eq 1 ] && PROBLEMS=$((PROBLEMS+1))

echo ""
case "$MODE" in
  dry)   echo "dry run: nothing was written. Run without --dry-run to apply." ;;
  check) if [ "$PROBLEMS" -eq 0 ]; then echo "check: clean"; exit 0; fi
         echo "check: $PROBLEMS problem(s); run 'bash install.sh $PROJ' to fix"; exit 1 ;;
  install)
    echo "installed into $DOT"
    echo "next: restart Claude Code in the project. If the project has no knowledge base yet, run /kbinit."
    echo "      To share with the team, commit .claude/skills .claude/hooks .claude/settings.json"
    echo "      (not .claude/backups). Verify any time: bash install.sh $PROJ --check" ;;
esac
exit 0
