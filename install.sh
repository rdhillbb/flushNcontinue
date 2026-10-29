#!/bin/bash
# install.sh — install the flushNcontinue knowledge-base skills into ONE project.
#
#   bash install.sh <projectdir> --dry-run   show what would change, write nothing
#   bash install.sh <projectdir>             install (safe to run again; it only fixes what differs)
#   bash install.sh <projectdir> --check     verify an install, write nothing; exit 1 on a problem
#   bash install.sh --personal [--dry-run|--check]
#                                            once per computer: ~/bin/session_time.sh and the
#                                            flush status line in ~/.claude (see below)
#
# Copies (no links) into <projectdir>/.claude/:
#   skills/checkpoint/  skills/flush/  skills/kbinit/   the three skills and their files
#   hooks/session-start.sh  hooks/pre-compact.sh  hooks/session_time.sh
#   settings.json        SessionStart + PreCompact hooks merged in; other settings kept
#
# --personal writes only: ~/bin/session_time.sh, ~/.claude/flushNcontinue/statusline.py, and a
# "statusLine" entry in ~/.claude/settings.json IF you have none (an existing status line is never
# replaced). Replaced files are kept as <file>.bak-flushNcontinue-<stamp>.
#
# Never: deletes anything (a replaced file or folder is moved to
# <projectdir>/.claude/backups/flushNcontinue-<stamp>/), touches your home folder without
# --personal, runs git. You decide whether to commit the result.
# Works on macOS, Linux and Windows (Git Bash). Needs: bash, python3.

set -u
PROJ="" ; MODE="install" ; PERSONAL=0
for a in "$@"; do
  case "$a" in
    --dry-run) MODE="dry" ;;
    --check)   MODE="check" ;;
    --personal) PERSONAL=1 ;;
    -*) echo "unknown option: $a"; exit 2 ;;
    *)  if [ -z "$PROJ" ]; then PROJ="$a"; else echo "only one project directory, please"; exit 2; fi ;;
  esac
done
REPO="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date '+%Y%m%d-%H%M%S')"

# ---- personal setup (once per computer) ------------------------------------------------
if [ "$PERSONAL" -eq 1 ]; then
  [ -z "$PROJ" ] || { echo "--personal takes no project directory; run it on its own"; exit 2; }
  if ! { command -v python3 >/dev/null 2>&1 && python3 -c 'import sys, zoneinfo; zoneinfo.ZoneInfo("America/New_York"); sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; }; then
    echo "STOP   python3 3.9+ with time-zone data is needed. Windows: install Python from the Microsoft Store, run: python3 -m pip install --user tzdata, then reopen Git Bash."; exit 1
  fi
  echo "flushNcontinue — mode: $MODE — personal setup in $HOME"
  echo ""
  python3 - "$REPO" "$HOME" "$MODE" "$STAMP" <<'PERSONAL_PY'
import json, os, sys, shutil, filecmp
repo, home, mode, stamp = sys.argv[1:5]
problems = 0
def say(ok, msg):
    global problems
    if ok:
        print(f"ok     {msg}"); return
    if mode == "check":
        problems += 1; print(f"WARN   {msg}")
    else:
        print(f"do     {msg}")
def put(src, dst, label):
    if os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False):
        say(True, label); return
    say(False, f"copy {label}")
    if mode != "install": return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        shutil.copy2(dst, f"{dst}.bak-flushNcontinue-{stamp}")
        print(f"       (old copy kept as {dst}.bak-flushNcontinue-{stamp})")
    shutil.copy2(src, dst); os.chmod(dst, 0o755)
put(os.path.join(repo, "claude/hooks/session_time.sh"), os.path.join(home, "bin/session_time.sh"), "~/bin/session_time.sh")
put(os.path.join(repo, "claude/hooks/statusline.py"), os.path.join(home, ".claude/flushNcontinue/statusline.py"), "~/.claude/flushNcontinue/statusline.py")
sp = os.path.join(home, ".claude/settings.json")
cmd = "python3 ~/.claude/flushNcontinue/statusline.py"
data = {}
if os.path.exists(sp):
    try:
        with open(sp, encoding="utf-8") as fh: data = json.load(fh)
    except Exception as e:
        print(f"STOP   {sp} is not valid JSON ({e}); fix it by hand, then re-run"); sys.exit(3)
    if not isinstance(data, dict):
        print(f"STOP   {sp} must be a JSON object {{...}}; fix it by hand, then re-run"); sys.exit(3)
cur = data.get("statusLine")
if isinstance(cur, dict) and "flushNcontinue/statusline.py" in str(cur.get("command", "")):
    say(True, "~/.claude/settings.json: flush status line set")
elif cur:
    print("ok     ~/.claude/settings.json: you already have your own status line; NOT replaced.")
    print(f"       To use the flush status line instead, set statusLine.command to: {cmd}")
else:
    say(False, "~/.claude/settings.json: add the flush status line")
    if mode == "install":
        if os.path.exists(sp):
            shutil.copy2(sp, f"{sp}.bak-flushNcontinue-{stamp}")
            print(f"       (old copy kept as {sp}.bak-flushNcontinue-{stamp})")
        data["statusLine"] = {"type": "command", "command": cmd}
        os.makedirs(os.path.dirname(sp), exist_ok=True)
        with open(sp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2); fh.write("\n")
sys.exit(1 if problems else 0)
PERSONAL_PY
  rc=$?
  echo ""
  [ $rc -eq 3 ] && exit 1
  if [ $rc -ne 0 ] && [ "$MODE" != "check" ]; then echo "STOP   personal setup failed (see the error above); nothing more was done"; exit 1; fi
  case "$MODE" in
    dry)   echo "dry run: nothing was written. Run without --dry-run to apply." ;;
    check) if [ $rc -eq 0 ]; then echo "check: clean"; else echo "check: problem(s); run 'bash install.sh --personal' to fix"; exit 1; fi ;;
    install) echo "personal setup done. Restart Claude Code to see the status line." ;;
  esac
  exit 0
fi

if [ -z "$PROJ" ]; then
  echo "usage: bash install.sh <projectdir> [--dry-run|--check]"
  echo "       bash install.sh --personal [--dry-run|--check]   (once per computer)"; exit 2
fi
[ -d "$PROJ" ] || { echo "STOP   project directory not found: $PROJ"; exit 1; }

PROJ="$(cd "$PROJ" && pwd)"
DOT="$PROJ/.claude"
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
  [ "$MODE" = "install" ] && [ ! -f "$DOT/backups/.gitignore" ] && printf '*\n' > "$DOT/backups/.gitignore"
  run mv "$DOT/$1" "$BACKUP/$1"
  [ "$MODE" = "install" ] && echo "       (old copy kept in .claude/backups/flushNcontinue-$STAMP/$1)"
  return 0
}

# put SRC REL — copy SRC (file or folder) to <DOT>/REL unless it is already identical
put() {
  local src="$1" rel="$2" dst="$DOT/$2"
  if [ -e "$dst" ] && diff -r -q -x __pycache__ -x '*.pyc' "$src" "$dst" >/dev/null 2>&1; then ok ".claude/$rel"; return; fi
  todo "copy .claude/$rel"
  if [ -e "$dst" ]; then keep "$rel"; fi
  run mkdir -p "$(dirname "$dst")"
  # copy without Python caches (they appear in the clone once its tools have run)
  run python3 -c 'import shutil, sys, os
s, d = sys.argv[1:3]
if os.path.isdir(s): shutil.copytree(s, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
else: shutil.copy2(s, d)' "$src" "$dst"
}

echo "flushNcontinue — mode: $MODE — project: $PROJ"
echo ""

# ---- 0. pre-flight -------------------------------------------------------------------
if ! { command -v python3 >/dev/null 2>&1 && python3 -c 'import sys, zoneinfo; zoneinfo.ZoneInfo("America/New_York"); sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; }; then
  fail "python3 3.9+ with time-zone data is needed. Windows: install Python from the Microsoft Store, run: python3 -m pip install --user tzdata, then reopen Git Bash."
fi
ok "python3 $(python3 -c 'import platform; print(platform.python_version())')"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) ok "Windows (Git Bash)" ;; esac
[ -f "$REPO/claude/skills/kbinit/SKILL.md" ] || fail "run this from a complete flushNcontinue clone (claude/skills missing)"

# ---- 1. skills -------------------------------------------------------------------------
for s in $SKILLS; do put "$REPO/claude/skills/$s" "skills/$s"; done

# ---- 2. hook scripts --------------------------------------------------------------------
for h in $HOOKS; do put "$REPO/claude/hooks/$h" "hooks/$h"; done
# Unix line endings for everything under .claude/ (Windows checkouts would otherwise break the bash hooks)
put "$REPO/claude/gitattributes" ".gitattributes"

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
    hooks = data.get("hooks") if isinstance(data, dict) else None
    groups = hooks.get(event, []) if isinstance(hooks, dict) else []
    return any(isinstance(g, dict) and isinstance(h, dict) and any(m in str(h.get("command", "")) for m in markers)
               for g in groups if isinstance(g, dict) for h in (g.get("hooks") or []))

data, user = load(path), load(user_path)
if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
    print(f"STOP   {path}: expected a JSON object with a \"hooks\" object; fix it by hand, then re-run"); sys.exit(3)
want = [("SessionStart", start, 60, ["session-start.sh", "SESSION BRIEF"]),
        ("PreCompact",   pre,   10, ["pre-compact.sh", "PRE-COMPACT"])]
add = []
for ev, cmd, t, markers in want:
    if has(data, ev, markers):
        print(f"ok     .claude/settings.json: {ev} hook present")
    else:
        # always written to the project, so teammates who pull get it
        if has(user, ev, markers):
            print(f"note   {ev}: your personal ~/.claude/settings.json also does this; on this computer it runs twice")
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
if [ $rc -ne 0 ] && [ $rc -ne 1 ]; then echo "STOP   settings.json step failed (see the error above)"; exit 1; fi

echo ""
case "$MODE" in
  dry)   echo "dry run: nothing was written. Run without --dry-run to apply." ;;
  check) if [ "$PROBLEMS" -eq 0 ]; then echo "check: clean"; exit 0; fi
         echo "check: $PROBLEMS problem(s); run 'bash install.sh $PROJ' to fix"; exit 1 ;;
  install)
    echo "installed into $DOT"
    echo "next: once per computer: bash $REPO/install.sh --personal"
    echo "      restart Claude Code in the project. If the project has no knowledge base yet, run /kbinit."
    echo "      To share with the team, commit .claude/skills .claude/hooks .claude/settings.json .claude/.gitattributes"
    echo "      (not .claude/backups). Verify any time: bash install.sh $PROJ --check" ;;
esac
exit 0
