#!/bin/bash
# session_health.sh — "does the application run?" probe for the KB resume protocol (generic; installed by /kbinit).
# Read-only. ALWAYS exits 0. Never prints a secret. Ends with the kb_tools.py health JSON
# (git branch/head/changes, BRIEF age, KB layout status) when scripts/kb/kb_tools.py is present.
# Run by Claude Code's SessionStart hook; Codex runs it by hand:  bash scripts/kb/session_health.sh
# bash 3.2 compatible (macOS default).

# ---- project config (kbinit fills these in; leave empty to skip a check) ----
PROD_HEALTH_URL=""          # e.g. https://example.com/health  (expects HTTP 200)
LOCAL_TCP_PORTS=""          # space-separated "label:port" pairs expected to be LISTENING, e.g. "supportdash:8082"
CHECK_POSTGRES="auto"       # auto | yes | no  (auto = yes when pg_isready exists)
TZ_LABEL=""                 # e.g. Asia/Phnom_Penh; empty = system zone
# ---- end project config -----------------------------------------------------

SCRIPT_DIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd)
ROOT=$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd)
cd "$ROOT" 2>/dev/null || true

warn=0
if [ -n "$TZ_LABEL" ]; then
  echo "== SESSION HEALTH — $(TZ="$TZ_LABEL" date '+%Y-%m-%d %H:%M %Z')"
else
  echo "== SESSION HEALTH — $(date '+%Y-%m-%d %H:%M %Z')"
fi

# --- git ---------------------------------------------------------------
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch=$(git branch --show-current 2>/dev/null)
  head=$(git log -1 --format='%h %s' 2>/dev/null | cut -c1-60)
  dirty=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
  echo "OK   git: ${branch:-?} @ ${head:-?} | ${dirty} uncommitted path(s)"
  # remote drift: fetch, then compare HEAD with its upstream (or the remote default branch)
  remote=$(git remote 2>/dev/null | head -1)
  if [ -n "$remote" ]; then
    stale=""; git fetch -q "$remote" 2>/dev/null || stale=" (fetch failed — offline? comparing against the last fetch)"
    up=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)
    if [ -z "$up" ]; then
      up=$(git symbolic-ref -q --short "refs/remotes/$remote/HEAD" 2>/dev/null)
      [ -z "$up" ] && for b in main master; do git show-ref -q --verify "refs/remotes/$remote/$b" && { up="$remote/$b"; break; }; done
      [ -n "$up" ] && up_note=" (no upstream set; compared with $up)" || up_note=""
    else up_note=""; fi
    if [ -n "$up" ]; then
      set -- $(git rev-list --left-right --count "$up...HEAD" 2>/dev/null)
      if [ "${1:-0}" -gt 0 ]; then
        warn=$((warn+1)); echo "WARN git: $up has $1 commit(s) you do not have (local ahead ${2:-0}) — pull/rebase before committing$up_note$stale"
      else
        echo "OK   git: nothing new on $up (local ahead ${2:-0})$up_note$stale"
      fi
    else
      echo "INFO git: remote $remote has no main/master ref yet — nothing to compare"
    fi
  fi
else
  warn=$((warn+1)); echo "WARN git: not a git work tree"
fi

# --- build (auto-detected) --------------------------------------------
if [ -f go.mod ]; then
  if command -v go >/dev/null 2>&1; then
    build_out=$(go build ./... 2>&1); build_rc=$?
    if [ "$build_rc" -eq 0 ]; then
      echo "OK   go build ./... passes"
    else
      warn=$((warn+1)); echo "WARN go build ./... FAILED (exit $build_rc):"
      echo "$build_out" | tail -3 | sed 's/^/     /'
    fi
  else
    warn=$((warn+1)); echo "WARN go build: go.mod present but go not on PATH"
  fi
elif [ -f package.json ] && grep -qE '"build"[[:space:]]*:' package.json 2>/dev/null; then
  echo "INFO npm build not run at session start (slow); run \`npm run build\` before deploy"
else
  echo "INFO no build system detected (no go.mod, no package.json build script)"
fi

# --- prod health URL ---------------------------------------------------
if [ -n "$PROD_HEALTH_URL" ]; then
  prod=$(curl -s -m 12 -o /dev/null -w '%{http_code} %{time_total}' "$PROD_HEALTH_URL" 2>/dev/null)
  prod_code=${prod%% *}; prod_time=${prod#* }
  if [ "$prod_code" = "200" ]; then
    echo "OK   prod $PROD_HEALTH_URL → 200 in ${prod_time}s"
  else
    warn=$((warn+1)); echo "WARN prod $PROD_HEALTH_URL → HTTP ${prod_code:-000} (${prod_time:-n/a}s) — check the service before trusting anything"
  fi
fi

# --- local Postgres ----------------------------------------------------
pg_check="$CHECK_POSTGRES"
if [ "$pg_check" = "auto" ]; then
  if command -v pg_isready >/dev/null 2>&1; then pg_check="yes"; else pg_check="no"; fi
fi
if [ "$pg_check" = "yes" ]; then
  if command -v pg_isready >/dev/null 2>&1; then
    if pg_isready -q 2>/dev/null; then
      echo "OK   local Postgres accepting connections"
    else
      warn=$((warn+1)); echo "WARN local Postgres NOT running — start Postgres before any DB work"
    fi
  else
    warn=$((warn+1)); echo "WARN local Postgres: pg_isready not on PATH — cannot verify Postgres"
  fi
fi

# --- expected local listeners -----------------------------------------
for pair in $LOCAL_TCP_PORTS; do
  label=${pair%%:*}; port=${pair##*:}
  [ -n "$port" ] || continue
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "OK   $label listening on :$port"
  else
    warn=$((warn+1)); echo "WARN $label NOT listening on :$port — start it before relying on it"
  fi
done

# --- BRIEF age ---------------------------------------------------------
if [ -f state/BRIEF.md ]; then
  mtime=$(stat -f %m state/BRIEF.md 2>/dev/null || stat -c %Y state/BRIEF.md 2>/dev/null || echo 0)
  now=$(date +%s)
  age_h=$(( (now - mtime) / 3600 ))
  if [ "$age_h" -gt 72 ]; then
    warn=$((warn+1)); echo "WARN state/BRIEF.md is ${age_h} h old (> 72 h) — treat it as stale, verify live"
  else
    echo "OK   state/BRIEF.md is ${age_h} h old"
  fi
else
  warn=$((warn+1)); echo "WARN state/BRIEF.md missing — run the flush or kbinit skill"
fi

# --- summary -----------------------------------------------------------
if [ "$warn" -eq 0 ]; then
  echo "== SESSION HEALTH: clean"
else
  echo "== SESSION HEALTH: ${warn} warning(s) — live system wins over BRIEF"
fi

# --- KB tool check (local metadata only: git, BRIEF age, layout) --------
if [ -f "$SCRIPT_DIR/kb_tools.py" ]; then
  python3 "$SCRIPT_DIR/kb_tools.py" --repo "$ROOT" health 2>&1 || true
fi
exit 0
