#!/bin/bash
# PreToolUse guard for the Bash tool (Claude Code hook). Template copy — installed
# per repo by the kbinit skill / kb_upgrade.sh as scripts/hooks/pretooluse-guard.sh.
# Reads the tool call as JSON on stdin, inspects tool_input.command, and
# blocks (exit 2 + reason on stderr) three recurring mistakes:
#   a. psql with a -v variable AND -c  (-c does not interpolate :'var';
#      see the repo's pitfalls file)
#   b. bare git stash / pop / drop / apply with no ref — ONLY when the repo is a
#      git worktree (shared stash stack); a normal checkout may stash freely
#   c. writing a log file into /tmp (operator rule: logs go to ~/logs/)
# Anything else exits 0 silently. bash 3.2 compatible. Never logs the command.

cmd=$(python3 -c 'import sys,json
try:
    print(json.load(sys.stdin).get("tool_input",{}).get("command",""))
except Exception:
    print("")' 2>/dev/null) || cmd=""
[ -z "$cmd" ] && exit 0

# --- a. psql -v var=... together with -c ---------------------------------
if printf '%s' "$cmd" | grep -Eq '(^|[[:space:]|;&(])psql([[:space:]]|$)' \
   && printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])-v[[:space:]]+[A-Za-z_][A-Za-z_0-9]*=' \
   && printf '%s' "$cmd" | grep -Eq '[[:space:]]-c[[:space:]]'; then
  echo "BLOCKED: psql -c does not interpolate -v variables (:'var' stays literal; see the repo's pitfalls file). Pipe the SQL on stdin instead: printf '...' | psql -v var=... -d <db>  — or use a heredoc." >&2
  exit 2
fi

# --- b. bare git stash / pop / drop / apply without a ref (worktrees only) --
# Matches: git stash            git stash pop        git stash drop      git stash apply
# Allows:  git stash push ...   git stash list       git stash show ...  git stash apply <sha|stash@{n}>
# Applies only when this checkout is a linked worktree (git-dir != common-dir):
# the stash stack is shared with the main checkout and every other worktree.
if printf '%s' "$cmd" | grep -Eq '(^|[[:space:]|;&(])git[[:space:]]+stash([[:space:]]+(pop|drop|apply))?[[:space:]]*($|[;&|)])'; then
  git_dir=$(git rev-parse --git-dir 2>/dev/null)
  common_dir=$(git rev-parse --git-common-dir 2>/dev/null)
  if [ -n "$git_dir" ] && [ "$git_dir" != "$common_dir" ]; then
    echo "BLOCKED: this is a git worktree with a SHARED stash stack; other sessions push/pop concurrently. Use a temporary WIP commit, or \`git stash push -u -m '<unique-tag>'\` then \`git stash apply <sha>\` and drop by tag." >&2
    exit 2
  fi
fi

# --- c. redirect or tee into /tmp/<anything>.log --------------------------
# Only /tmp/...log via > , >> or tee. Other /tmp use (scratchpad, ls) passes.
if printf '%s' "$cmd" | grep -Eq '(>>?[[:space:]]*|tee([[:space:]]+-[a-zA-Z]+)*[[:space:]]+)/tmp/[^[:space:]]*\.log([[:space:]]|$|[;&|)])'; then
  echo "BLOCKED: never write logs to /tmp — use ~/logs/ (operator rule)." >&2
  exit 2
fi

exit 0
