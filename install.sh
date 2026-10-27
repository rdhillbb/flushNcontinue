#!/bin/bash
# install.sh — install the flushNcontinue knowledge-base toolkit
# into this user's Claude Code setup.
#
#   bash install.sh --dry-run   show what would change, write nothing
#   bash install.sh             install (safe to run again; it only fixes what is missing)
#   bash install.sh --check     verify an existing install, write nothing; exit 1 on a problem
#
# What it does (all under $HOME, nothing else):
#   1. ~/apps/factorymaterial  -> symlink to this clone (the skills name that path)
#   2. ~/bin                   -> links: kb_tools.py kb_upgrade.sh kb_handoff.sh session_time.sh
#   3. ~/.claude/skills/<name> -> links into this clone (checkpoint flush kbinit)
#   4. ~/.claude/settings.json -> SessionStart + PreCompact hooks merged in (other settings kept)
#   5. ~/.claude/CLAUDE.md     -> created from the template ONLY if missing
#
# Never: deletes a file (anything replaced is renamed *.bak-flushNcontinue-<stamp>), overwrites
# your personal CLAUDE.md, touches a project repo, runs git push.
# bash 3.2 compatible (macOS) and Linux. Needs: bash, git, python3, Claude Code.

set -u
MODE="install"
case "${1:-}" in
  --dry-run) MODE="dry" ;;
  --check)   MODE="check" ;;
  "")        ;;
  *) echo "usage: bash install.sh [--dry-run|--check]"; exit 2 ;;
esac

REPO="$(cd "$(dirname "$0")" && pwd -P)"
FM="$HOME/apps/factorymaterial"
STAMP="$(date '+%Y%m%d-%H%M%S')"
SKILLS="checkpoint flush kbinit"
PROBLEMS=0

say()  { echo "$*"; }
ok()   { echo "ok     $*"; }
todo() { if [ "$MODE" = "check" ]; then echo "WARN   $*"; PROBLEMS=$((PROBLEMS+1)); else echo "do     $*"; fi; }
fail() { echo "STOP   $*"; exit 1; }
run()  { if [ "$MODE" = "install" ]; then "$@"; fi; }

backup() {  # rename an existing path out of the way; never delete
  run mv "$1" "$1.bak-flushNcontinue-$STAMP"
  say "       (old one kept as $1.bak-flushNcontinue-$STAMP)"
}

# link TARGET LINKPATH — make LINKPATH a symlink to TARGET, backing up whatever was there
link() {
  local target="$1" path="$2"
  if [ -L "$path" ] && [ "$(readlink "$path")" = "$target" ]; then ok "$path -> $target"; return; fi
  todo "link $path -> $target"
  if [ -e "$path" ] || [ -L "$path" ]; then backup "$path"; fi
  run mkdir -p "$(dirname "$path")"
  run ln -s "$target" "$path"
}

say "flushNcontinue installer — mode: $MODE — clone: $REPO"
say ""

# ---- 0. pre-flight -------------------------------------------------------------------
for t in bash git python3; do command -v "$t" >/dev/null 2>&1 || fail "$t is not installed"; done
if command -v claude >/dev/null 2>&1 || [ -d "$HOME/.claude" ]; then ok "Claude Code found"
else fail "Claude Code not found. Install it first: https://docs.claude.com/en/docs/claude-code"; fi

# ---- 1. ~/apps/factorymaterial -> this clone -----------------------------------------
if [ -e "$FM" ] && [ ! -L "$FM" ] && [ "$REPO" != "$(cd -P "$FM" && pwd -P)" ]; then
  fail "$FM is a real folder, not this clone. Move it away (or clone this repo there) and re-run."
fi
if [ "$REPO" = "$(cd -P "$FM" 2>/dev/null && pwd -P)" ] && [ ! -L "$FM" ]; then
  ok "$FM is this clone"
else
  link "$REPO" "$FM"
fi

# ---- 2. ~/bin helpers -------------------------------------------------------------------
for f in kb_tools.py kb_upgrade.sh kb_handoff.sh; do link "$FM/scripts/$f" "$HOME/bin/$f"; done
link "$FM/bin/session_time.sh" "$HOME/bin/session_time.sh"

# ---- 3. Claude skills (links into this clone) -------------------------------------------
for s in $SKILLS; do link "$FM/claude/skills/$s" "$HOME/.claude/skills/$s"; done

# ---- 4. hooks in ~/.claude/settings.json -------------------------------------------------
python3 - "$HOME/.claude/settings.json" "$MODE" "$STAMP" <<'PY'
import json, os, sys, shutil
path, mode, stamp = sys.argv[1:4]
start = 'bash "$HOME/apps/factorymaterial/hooks/session-start.sh"'
pre   = 'bash "$HOME/apps/factorymaterial/hooks/pre-compact.sh"'
data = {}
if os.path.exists(path):
    try:
        with open(path) as fh: data = json.load(fh)
    except Exception as e:
        print(f"STOP   {path} is not valid JSON ({e}); fix it by hand, then re-run"); sys.exit(3)
hooks = data.setdefault("hooks", {})
def present(event, marker):
    return any(marker in h.get("command", "")
               for g in hooks.get(event, []) for h in g.get("hooks", []))
changes = []
# An existing hand-written BRIEF injector counts too, so BRIEF is never injected twice.
if not (present("SessionStart", "session-start.sh") or present("SessionStart", "SESSION BRIEF")):
    changes.append(("SessionStart", start, 60))
if not (present("PreCompact", "pre-compact.sh") or present("PreCompact", "PRE-COMPACT")):
    changes.append(("PreCompact", pre, 10))
if not changes:
    print(f"ok     {path}: SessionStart + PreCompact hooks present"); sys.exit(0)
for ev, _, _ in changes:
    print(("WARN   " if mode == "check" else "do     ") + f"{path}: add {ev} hook")
if mode == "check": sys.exit(1)
if mode == "dry": sys.exit(0)
for ev, cmd, t in changes:
    hooks.setdefault(ev, []).append({"matcher": "", "hooks": [{"type": "command", "command": cmd, "timeout": t}]})
if os.path.exists(path):
    shutil.copy2(path, f"{path}.bak-flushNcontinue-{stamp}")
    print(f"       (old one kept as {path}.bak-flushNcontinue-{stamp})")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as fh: json.dump(data, fh, indent=2); fh.write("\n")
PY
rc=$?
[ $rc -eq 3 ] && exit 1
[ $rc -eq 1 ] && PROBLEMS=$((PROBLEMS+1))

# ---- 5. personal CLAUDE.md (only if missing) -------------------------------------------
if [ -f "$HOME/.claude/CLAUDE.md" ]; then
  ok "$HOME/.claude/CLAUDE.md exists (left as is; compare with templates/personal-CLAUDE.md if you like)"
else
  todo "create ~/.claude/CLAUDE.md from templates/personal-CLAUDE.md — then fill in your name and time zone"
  run mkdir -p "$HOME/.claude"
  run cp "$REPO/templates/personal-CLAUDE.md" "$HOME/.claude/CLAUDE.md"
fi

say ""
case "$MODE" in
  dry)     say "dry run: nothing was written. Run 'bash install.sh' to apply." ;;
  check)   if [ "$PROBLEMS" -eq 0 ]; then say "check: clean"; exit 0; else say "check: $PROBLEMS problem(s); run 'bash install.sh' to fix"; exit 1; fi ;;
  install) say "installed. Verify with 'bash install.sh --check', then restart Claude Code." ;;
esac
exit 0
