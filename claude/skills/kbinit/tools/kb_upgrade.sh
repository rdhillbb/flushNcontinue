#!/bin/bash
# kb_upgrade.sh — bring an EXISTING knowledge-base repo up to the current KB tooling.
#
#   kb_upgrade.sh [--dry-run] [--all] [--force-lint] [repo-dir ...]
#
#   (no dirs)      current directory
#   --all          every dir (maxdepth 2) under $HOME/go/src and $HOME/apps that has
#                  KNOWLEDGE-MAP.md, deduped by physical path
#   --dry-run      print what would change, write nothing (the closing lint still runs:
#                  it is read-only and reports the repo's CURRENT state)
#   --force-lint   replace a scripts/kb/kb_lint.sh that differs from the template
#                  (backup kept); without it a differing lint is reported as MANUAL
#
# A repo qualifies only if it has KNOWLEDGE-MAP.md AND state/BRIEF.md (an installed KB;
# a bare directory goes through the kbinit skill instead). Per repo, idempotently:
#   a. scripts/kb/kb_lint.sh            ADD if absent; differs -> MANUAL (or UPDATE with --force-lint, .bak kept)
#      scripts/kb/kb_tools.py           ADD if absent; UPDATE if differs (.bak kept). Installed from the
#                                       MASTER copy next to this script (scripts/kb_tools.py), one source
#   b. scripts/kb/session_health.sh     ADD if absent (never overwritten: the CONFIG block is per project)
#   c. scripts/hooks/pretooluse-guard.sh ADD if absent; UPDATE if differs (.bak kept)
#   d. .claude/settings.json            ensure hooks.PreToolUse wires pretooluse-guard.sh (python3 merge, other keys kept)
#   f. state/kb-layout.json             ADD if absent, derived from the repo's existing files (project = dir
#      name, timezone Asia/Phnom_Penh, history quarterly if docs/tribal/ exists else flat, pitfalls =
#      whichever pitfalls file exists, now_archive = newest docs/tribal/NOW-focus-archive-*.md else
#      state/NOW-ARCHIVE.md, memory_dir only when the repo's own files name a non-default auto-memory path);
#      validated with kb_tools.validate_layout before writing. An existing layout is loaded and validated,
#      never modified; an invalid one is MANUAL and step e is skipped. Runs before e, which needs the layout.
#   e. operating files (one rules file): AGENTS.md carries the KB section (refresh the old-layout
#      wording in place, insert it if missing, create AGENTS.md from project-AGENTS.md.template if
#      absent; step 5 -> session_health.sh wording); CLAUDE.md gets an @AGENTS.md line under its first
#      heading (created thin from project-CLAUDE.md.template if absent) and loses any KB-section copy
#      (backup kept). A CLAUDE.md over 4 KB is reported MANUAL: move its rules into AGENTS.md.
#      Templates are rendered by kb_tools.render(kb_tools.values(layout)) — the same placeholders kbinit uses.
#   g. closing check: python3 scripts/kb/kb_tools.py --repo <repo> lint (status + error count).
# Registers, history, BRIEF and everything else are never touched. Never runs a git
# command that modifies anything, never commits. Exit 0 always. bash 3.2 compatible.
# Source of the files it installs: <this script's dir>/../templates (templates, scripts/kb, scripts/hooks)
# plus <this script's dir>/kb_tools.py (the master engine). Installed at .claude/skills/kbinit/tools/kb_upgrade.sh.

# ---- locate the source tree (follows a symlink to the real script if there is one) --------
SELF="$0"
while [ -L "$SELF" ]; do
  t=$(readlink "$SELF")
  case "$t" in /*) SELF="$t" ;; *) SELF="$(dirname "$SELF")/$t" ;; esac
done
SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd -P)"
TPL="$(cd "$SCRIPT_DIR/../templates" 2>/dev/null && pwd -P)"
MASTER_TOOLS="$SCRIPT_DIR/kb_tools.py"

DRY=0; ALL=0; FORCE_LINT=0
DIRS=""
for a in "$@"; do
  case "$a" in
    --dry-run)    DRY=1 ;;
    --all)        ALL=1 ;;
    --force-lint) FORCE_LINT=1 ;;
    -h|--help)    sed -n '2,38p' "$SELF"; exit 0 ;;
    -*)           echo "unknown option: $a" >&2; exit 0 ;;
    *)            DIRS="$DIRS
$a" ;;
  esac
done
if [ -z "$TPL" ] || [ ! -d "$TPL" ]; then
  echo "source tree missing: $SCRIPT_DIR/../templates (nothing done)"; exit 0
fi
if [ ! -f "$MASTER_TOOLS" ]; then
  echo "master kb_tools.py missing: $MASTER_TOOLS (nothing done)"; exit 0
fi

STEP5_PREFIX='5. Verify live before trusting any file:'
STEP5_NEW='5. Verify live before trusting any file: `bash scripts/kb/session_health.sh` (git state, build, prod health, local services, BRIEF age; Claude Code'"'"'s SessionStart hook runs it automatically, Codex must run it by hand). **The live system wins over every file.**'
TODAY=$(date +%Y-%m-%d)
TMPD="${TMPDIR:-/tmp}"

# ---- collect repo list -----------------------------------------------------
phys() { (cd "$1" 2>/dev/null && pwd -P); }
REPOS=""
add_repo() {
  local p; p=$(phys "$1") || { echo "SKIP  $1: not a directory"; return; }
  case "
$REPOS
" in *"
$p
"*) return ;; esac
  REPOS="$REPOS
$p"
}
if [ "$ALL" = 1 ]; then
  for base in "$HOME/go/src" "$HOME/apps"; do
    [ -d "$base" ] || continue
    find "$base" -mindepth 2 -maxdepth 3 -name KNOWLEDGE-MAP.md -not -path '*/node_modules/*' -not -path '*/TEMPLATES/*' 2>/dev/null \
      | sed 's#/KNOWLEDGE-MAP.md$##' | sort
  done | while IFS= read -r d; do printf '%s\n' "$d"; done > "$TMPD/kb_upgrade_list.$$"
  while IFS= read -r d; do [ -n "$d" ] && add_repo "$d"; done < "$TMPD/kb_upgrade_list.$$"
  rm -f "$TMPD/kb_upgrade_list.$$"
fi
if [ -n "$DIRS" ]; then
  printf '%s\n' "$DIRS" | while IFS= read -r d; do [ -n "$d" ] && printf '%s\n' "$d"; done > "$TMPD/kb_upgrade_dirs.$$"
  while IFS= read -r d; do add_repo "$d"; done < "$TMPD/kb_upgrade_dirs.$$"
  rm -f "$TMPD/kb_upgrade_dirs.$$"
fi
[ -z "$REPOS" ] && [ "$ALL" = 0 ] && add_repo "$PWD"
[ -z "$REPOS" ] && { echo "no KB repos found"; exit 0; }

# ---- helpers ----------------------------------------------------------------
CH=0; MAN=0
say() { printf '%s\n' "$*"; }
would() { # would <ACTION> <text>  -> prints DRY or the action, counts a change
  if [ "$DRY" = 1 ]; then say "DRY   (would $1) $2"; else say "$1  $2"; fi
  CH=$((CH+1))
}
manual() { say "MANUAL: $*"; MAN=$((MAN+1)); }
bakname() { # bakname <file> -> unused backup path
  local b="$1.bak-$TODAY"
  [ -e "$b" ] && b="$1.bak-$TODAY-$(date +%H%M%S)"
  printf '%s' "$b"
}
install_file() { # install_file <src> <dst> <ADD|UPDATE>   (src may be a symlink; cp follows it)
  if [ "$DRY" = 0 ]; then
    mkdir -p "$(dirname "$2")"
    if [ "$3" = UPDATE ]; then local b; b=$(bakname "$2"); cp -p "$2" "$b"; say "      backup: $b"; fi
    cp "$1" "$2" && chmod +x "$2"
  fi
}

# python for steps f + e, kept out of $( ) because bash 3.2 mis-parses backticks in a heredoc there
read -r -d '' PY_OPFILES <<'PY'
import glob, json, os, re, sys, time
R, TPL, MASTER_DIR, dry, today, s5p, s5n = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1", sys.argv[5], sys.argv[6], sys.argv[7]
BEGIN, END = "<!-- KB-SECTION-BEGIN", "<!-- KB-SECTION-END -->"
out = []
def emit(kind, act, txt): out.append("%s|%s|%s" % (kind, act, txt))
def done(): print("\n".join(out)); sys.exit(0)
sys.path.insert(0, MASTER_DIR)
try:
    import kb_tools
except Exception as e:
    emit("MAN", "", "cannot import kb_tools from %s (%s); layout + operating-file steps skipped" % (MASTER_DIR, e)); done()
def rd(p):
    try: return open(p, encoding="utf-8").read()
    except FileNotFoundError: return None
    except Exception as e: emit("MAN", "", "%s unreadable: %s" % (os.path.relpath(p, R), e)); return False
def bak(p):
    b = p + ".bak-" + today
    if os.path.exists(b): b = p + ".bak-" + today + "-" + time.strftime("%H%M%S")
    return b
def write(p, old, new):
    if dry: return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if old is not None:
        b = bak(p); open(b, "w", encoding="utf-8", newline="").write(old); emit("SAY", "", "      backup: " + b)
    open(p, "w", encoding="utf-8", newline="").write(new)

# ---- f. state/kb-layout.json ------------------------------------------------
LAYOUT_REL = "state/kb-layout.json"
LAYOUT_P = os.path.join(R, LAYOUT_REL)
layout = None
LAYOUT_ERRS = (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError)
def memory_dir_in_repo():
    # the repo's own files may name a non-default auto-memory path (e.g. a renamed checkout)
    for name in ("KNOWLEDGE-MAP.md", "AGENTS.md", "CLAUDE.md"):
        t = rd(os.path.join(R, name)) or ""
        m = re.search(r"((?:~|/Users/[^/\s`]+)/\.claude/projects/[^\s`]+?)/MEMORY\.md", t)
        if m: return m.group(1)
    return None
if os.path.exists(LAYOUT_P):
    try:
        layout = kb_tools.validate_layout(R, json.loads(rd(LAYOUT_P) or ""))
        emit("SKIP", "", "%s (present, valid; never modified)" % LAYOUT_REL)
    except LAYOUT_ERRS as e:
        emit("MAN", "", "existing %s is invalid (%s); not modified. Operating-file step skipped until it is fixed (see claude/kb/layout.example.json)" % (LAYOUT_REL, e))
        layout = None
else:
    tribal = os.path.join(R, "docs/tribal")
    pit = "docs/buildout/04-KNOWN-PITFALLS.md" if os.path.exists(os.path.join(R, "docs/buildout/04-KNOWN-PITFALLS.md")) else "docs/KNOWN-PITFALLS.md"
    arch = sorted(os.path.basename(p) for p in glob.glob(os.path.join(tribal, "NOW-focus-archive-*.md")))
    now_archive = "docs/tribal/" + arch[-1] if arch else "state/NOW-ARCHIVE.md"
    cand = {"version": 1, "project": os.path.basename(R), "timezone": "Asia/Phnom_Penh",
            "history_kind": "quarterly" if os.path.isdir(tribal) else "flat",
            "homes": {"brief": "state/BRIEF.md", "now": "state/NOW.md", "now_archive": now_archive,
                      "findings": "state/FINDINGS.md", "details": "state/FINDINGS-DETAIL.md",
                      "contradictions": "state/CONTRADICTIONS.md", "pitfalls": pit,
                      "history_index": "docs/TribalKnowledge.md", "history_dir": "docs/tribal"}}
    md = memory_dir_in_repo()
    if md:
        default_md = kb_tools.values(dict(cand, _root=R), kb_tools.clock(cand))["MEMORY_DIR"]
        if md != default_md: cand["memory_dir"] = md
    try:
        layout = kb_tools.validate_layout(R, cand)
        desc = "project %s, history %s, pitfalls %s, now_archive %s" % (cand["project"], cand["history_kind"], pit, now_archive)
        if "memory_dir" in cand: desc += ", memory_dir %s (from the repo's own files)" % cand["memory_dir"]
        emit("ACT", "ADD", "%s (derived: %s)" % (LAYOUT_REL, desc))
        write(LAYOUT_P, None, json.dumps(layout, indent=2) + "\n")
    except LAYOUT_ERRS as e:
        emit("MAN", "", "cannot derive %s (%s); write it by hand from claude/kb/layout.example.json. Operating-file step skipped" % (LAYOUT_REL, e))
        layout = None
if layout is None: done()
# every file home must exist or kb_tools lint/flush fail. The one home a legacy repo lacks is the
# NOW archive (kbinit creates it empty from its template); anything else missing is MANUAL.
for key, rel in layout["homes"].items():
    if key == "history_dir" or os.path.exists(os.path.join(R, rel)): continue
    na_tpl = os.path.join(TPL, "state/NOW-ARCHIVE.md.template")
    if key == "now_archive" and os.path.isfile(na_tpl):
        try:
            body = kb_tools.render(rd(na_tpl), kb_tools.values(dict(layout, _root=R), kb_tools.clock(layout)))
        except ValueError as e:
            emit("MAN", "", "layout home %s is missing and NOW-ARCHIVE.md.template did not render (%s)" % (rel, e)); continue
        emit("ACT", "ADD", "%s (empty NOW archive from state/NOW-ARCHIVE.md.template; the layout names it)" % rel)
        write(os.path.join(R, rel), None, body)
    else:
        emit("MAN", "", "layout home %s (%s) does not exist; create it (kbinit templates under %s/state, docs) or lint fails" % (rel, key, TPL))

# ---- e. operating files -----------------------------------------------------
at = kb_tools.clock(layout)
vals = kb_tools.values(dict(layout, _root=R), at)
def render(text, name, v):
    try: return kb_tools.render(text, v)
    except ValueError as e:
        emit("MAN", "", "%s: %s" % (name, e)); return None
def tpl_path(*names):
    for n in names:
        p = os.path.join(TPL, n)
        if os.path.isfile(p): return p
    return None
def block(t):
    if not t: return None
    L = t.split("\n")
    b = [i for i, l in enumerate(L) if l.lstrip().startswith(BEGIN)]
    if not b: return None
    e = [i for i, l in enumerate(L) if i > b[0] and l.strip().startswith(END)]
    return (b[0], e[0]) if e else "BAD"
def section_of(t):
    k = block(t)
    if not k or k == "BAD": return None
    return "\n".join(t.split("\n")[k[0]:k[1] + 1])
NEW_ID = "Both seats read this section: Codex from `AGENTS.md`, Claude Code through the `@AGENTS.md` import in `CLAUDE.md`."
# rendered KB section (the template's BEGIN line is the current marker wording)
sec_p = tpl_path("KB-SECTION.md.template")
tsec = render(rd(sec_p), "KB-SECTION.md.template", vals) if sec_p else None
if not sec_p: emit("MAN", "", "template KB-SECTION.md.template missing in %s; cannot insert or create the KB section" % TPL)
tsec = (tsec or "").rstrip("\n")
TPL_BEGIN = next((l for l in tsec.split("\n") if l.lstrip().startswith(BEGIN)), None)
def fix(t):
    ch = []
    t2 = re.sub(r"This section is identical in `CLAUDE\.md`[^\n]*?`AGENTS\.md` \(Codex\)\.", NEW_ID, t)
    if t2 != t: ch.append("'identical in both files' sentence -> @AGENTS.md import sentence")
    t3 = re.sub(r"CLAUDE\.md/AGENTS\.md drift", "the `@AGENTS.md` import in `CLAUDE.md`", t2)
    if t3 != t2: ch.append("health-check line: drift check -> @AGENTS.md import check")
    L = t3.split("\n")
    for i, l in enumerate(L):
        if l.rstrip("\r").startswith(s5p):
            if "session_health.sh" not in l:
                L[i] = s5n + ("\r" if l.endswith("\r") else ""); ch.append("step 5 -> session_health.sh wording")
            break
    if TPL_BEGIN:
        for i, l in enumerate(L):
            if l.lstrip().startswith(BEGIN):
                if l.rstrip("\r") != TPL_BEGIN:
                    L[i] = TPL_BEGIN + ("\r" if l.endswith("\r") else ""); ch.append("KB-SECTION-BEGIN marker comment -> current template wording")
                break
    # 2026-10-19 handoff: thresholds, resume protocol and flush bullet follow the template line
    # whenever the repo still carries the pre-handoff wording (idempotent: new wording never matches)
    for pre, oldre, what in (("3. **Resume protocol:**", r"continue with <next action>\?", "resume protocol -> alignment questions"),
                             ("- **Context thresholds:**", r"65%", "thresholds -> 62% flush + new session, 70% ceiling"),
                             ("- `flush` skill = full KB reconcile", r"^(?!.*Alignment)", "flush bullet -> mentions ## Alignment")):
        tl = next((x for x in tsec.split("\n") if x.startswith(pre)), None)
        if not tl: continue
        for i, l in enumerate(L):
            if l.startswith(pre) and re.search(oldre, l) and l.rstrip("\r") != tl:
                L[i] = tl + ("\r" if l.endswith("\r") else ""); ch.append(what)
                break
    return "\n".join(L), ch

A, C = os.path.join(R, "AGENTS.md"), os.path.join(R, "CLAUDE.md")
a, c = rd(A), rd(C)
if a is False or c is False: done()
csec = section_of(c)
src_sec, src_name = (csec, "the copy in CLAUDE.md") if csec else (tsec, "KB-SECTION.md.template")

# AGENTS.md: the single rules file, carries the KB section
a_new = a
if a is None:
    ap = tpl_path("project-AGENTS.md.template", "AGENTS.md.template")
    if not ap:
        emit("MAN", "", "AGENTS.md absent and no project-AGENTS.md.template / AGENTS.md.template in %s; create it by hand" % TPL)
    elif not tsec:
        emit("MAN", "", "AGENTS.md absent; not created because the KB section template is unavailable")
    else:
        av = dict(vals); av["KB_SECTION"] = tsec
        tpl = render(rd(ap), os.path.basename(ap), av)
        if tpl is not None:
            tsk = section_of(tpl)
            if csec and tsk: tpl = tpl.replace(tsk, csec)
            a_new, _ = fix(tpl)
            emit("ACT", "ADD", "AGENTS.md (created from %s; KB section from %s) -> fill its project stubs" % (os.path.basename(ap), src_name))
            write(A, None, a_new)
else:
    k = block(a)
    if k == "BAD":
        emit("MAN", "", "AGENTS.md has KB-SECTION-BEGIN without KB-SECTION-END; fix by hand")
    elif k:
        a_new, ch = fix(a)
        if ch:
            emit("ACT", "UPDATE", "AGENTS.md KB section refreshed: " + "; ".join(ch)); write(A, a, a_new)
        else:
            emit("SKIP", "", "AGENTS.md KB section (no old-layout wording found)")
        if tsec:
            cur = section_of(a_new) or ""
            nd = len(set(cur.split("\n")) ^ set(tsec.split("\n")))
            if nd: emit("INFO", "", "AGENTS.md KB section differs from the rendered template in %d line(s); project customizations kept" % nd)
    elif not src_sec:
        emit("MAN", "", "AGENTS.md has no KB section and the template is unavailable; insert it by hand")
    else:
        L = a.split("\n")
        h = next((i for i, l in enumerate(L) if l.startswith("## ")), len(L))
        ins = src_sec.split("\n") + ["", "---", ""]
        a_new, _ = fix("\n".join(L[:h] + ins + L[h:]))
        emit("ACT", "UPDATE", "AGENTS.md: KB section inserted before the first ## heading (from %s)" % src_name)
        write(A, a, a_new)

# CLAUDE.md: thin, imports AGENTS.md
a_has = bool(section_of(a_new))
created_c, base = False, c
if c is None:
    cp = tpl_path("project-CLAUDE.md.template", "CLAUDE.md.template")
    if not cp:
        emit("MAN", "", "CLAUDE.md absent and no project-CLAUDE.md.template / CLAUDE.md.template in %s; create it by hand" % TPL); base = None
    else:
        cv = dict(vals); cv.pop("KB_SECTION", None)   # the thin CLAUDE.md must not carry the block
        base = render(rd(cp), os.path.basename(cp) + " (the CLAUDE template must not use {{KB_SECTION}})", cv)
        created_c = base is not None
if base is not None:
    L = base.split("\n"); ch = []
    if not any(re.match(r"^\s*@AGENTS\.md\s*$", l) for l in L):
        h = next((i for i, l in enumerate(L) if l.startswith("# ")), -1)
        L.insert(h + 1, "@AGENTS.md"); ch.append("@AGENTS.md inserted %s" % ("after the first heading" if h >= 0 else "at the top (no # heading)"))
    k = block("\n".join(L))
    if k == "BAD":
        emit("MAN", "", "CLAUDE.md has KB-SECTION-BEGIN without KB-SECTION-END; remove the copy by hand")
    elif k and a_has:
        norm = lambda s: "\n".join(x.rstrip() for x in (s or "").strip().split("\n"))
        cs = "\n".join(L[k[0]:k[1] + 1])
        if norm(fix(cs)[0]) == norm(section_of(a_new)) or norm(cs) == norm(section_of(a) if a else ""):
            del L[k[0]:k[1] + 1]; ch.append("KB-section copy removed (same as AGENTS.md's, which carries it)")
        else:
            emit("MAN", "", "CLAUDE.md KB section differs from the one in AGENTS.md; reconcile into AGENTS.md by hand, then remove the CLAUDE.md copy")
    elif k:
        emit("MAN", "", "CLAUDE.md still carries the KB section but AGENTS.md does not; not removed")
    c_new = re.sub(r"\n{4,}", "\n\n\n", "\n".join(L))
    if created_c:
        emit("ACT", "ADD", "CLAUDE.md (thin, from the CLAUDE template: @AGENTS.md + Claude-only items) -> fill its stubs"); write(C, None, c_new)
    elif ch:
        emit("ACT", "UPDATE", "CLAUDE.md: " + "; ".join(ch)); write(C, c, c_new)
    else:
        emit("SKIP", "", "CLAUDE.md (@AGENTS.md present, no KB-section copy)")
    n = len(c_new.encode("utf-8"))
    if n > 4096:
        emit("MAN", "", "CLAUDE.md would be %d bytes (lint budget 4096, target about 1.5 KB): move its shared rules VERBATIM into AGENTS.md, keep only Claude-only items (see project-CLAUDE.md.template)" % n)
    for name, t in (("AGENTS.md", a_new), ("CLAUDE.md", c_new)):
        if t and "{{" in t: emit("MAN", "", "%s has unfilled {{...}} placeholders" % name)
if a_new and len(a_new.encode("utf-8")) > 20480:
    emit("MAN", "", "AGENTS.md would be %d bytes, over its 20480 budget" % len(a_new.encode("utf-8")))
done()
PY

upgrade_repo() {
  local R="$1"
  say "== $R"
  if [ ! -f "$R/KNOWLEDGE-MAP.md" ] || [ ! -f "$R/state/BRIEF.md" ]; then
    say "SKIP  no installed KB here (needs KNOWLEDGE-MAP.md + state/BRIEF.md; run the kbinit skill)"
    say "== $R: 0 change(s), 0 manual item(s)"
    return
  fi
  CH=0; MAN=0

  # a. kb_lint.sh (differs -> MANUAL unless --force-lint)
  local src="$TPL/scripts/kb/kb_lint.sh" dst="$R/scripts/kb/kb_lint.sh"
  if [ ! -f "$src" ]; then manual "template $src is missing; cannot install kb_lint.sh"
  elif [ ! -f "$dst" ]; then install_file "$src" "$dst" ADD; would ADD "scripts/kb/kb_lint.sh"
  elif cmp -s "$src" "$dst"; then say "SKIP (up to date)  scripts/kb/kb_lint.sh"
  else
    local n; n=$(diff "$dst" "$src" | grep -c '^[<>]')
    if [ "$FORCE_LINT" = 1 ]; then
      install_file "$src" "$dst" UPDATE; would UPDATE "scripts/kb/kb_lint.sh (differed by $n lines; --force-lint)"
    else
      local age="template is newer"; [ "$dst" -nt "$src" ] && age="repo copy is newer than the template"
      manual "lint differs by $n lines ($age); rerun with --force-lint to replace (backup kept)"
    fi
  fi
  # a. kb_tools.py (always from the master copy; differs -> UPDATE, .bak kept)
  src="$MASTER_TOOLS"; dst="$R/scripts/kb/kb_tools.py"
  if [ ! -f "$dst" ]; then install_file "$src" "$dst" ADD; would ADD "scripts/kb/kb_tools.py (from the master $MASTER_TOOLS)"
  elif cmp -s "$src" "$dst"; then say "SKIP (up to date)  scripts/kb/kb_tools.py"
  else
    n=$(diff "$dst" "$src" | grep -c '^[<>]')
    install_file "$src" "$dst" UPDATE; would UPDATE "scripts/kb/kb_tools.py (differed by $n lines from the master)"
  fi

  # b. session_health.sh (never overwrite)
  src="$TPL/scripts/kb/session_health.sh"; dst="$R/scripts/kb/session_health.sh"
  if [ -f "$dst" ]; then say "SKIP (up to date)  scripts/kb/session_health.sh (present; CONFIG block is per project)"
  elif [ ! -f "$src" ]; then manual "template $src is missing; cannot install session_health.sh"
  else install_file "$src" "$dst" ADD; would ADD "scripts/kb/session_health.sh  -> fill its CONFIG block (prod health URL, local ports, timezone)"
  fi

  # c. pretooluse-guard.sh
  src="$TPL/scripts/hooks/pretooluse-guard.sh"; dst="$R/scripts/hooks/pretooluse-guard.sh"
  if [ ! -f "$src" ]; then manual "template $src is missing; cannot install pretooluse-guard.sh"
  elif [ ! -f "$dst" ]; then install_file "$src" "$dst" ADD; would ADD "scripts/hooks/pretooluse-guard.sh"
  elif cmp -s "$src" "$dst"; then say "SKIP (up to date)  scripts/hooks/pretooluse-guard.sh"
  else install_file "$src" "$dst" UPDATE; would UPDATE "scripts/hooks/pretooluse-guard.sh"
  fi

  # d. .claude/settings.json hook wiring
  local frag="$TPL/scripts/hooks/settings.pretooluse.json" sj="$R/.claude/settings.json"
  if [ ! -f "$frag" ]; then manual "template $frag is missing; cannot wire the guard hook"
  else
    local st
    st=$(python3 - "$sj" "$frag" "$DRY" <<'PY'
import json, os, sys
sj, frag, dry = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
try:
    entry = json.load(open(frag))
except Exception as e:
    print("BAD_FRAG " + str(e)); sys.exit(0)
data, existed = {}, os.path.exists(sj)
if existed:
    try:
        data = json.load(open(sj))
    except Exception as e:
        print("BAD_JSON " + str(e)); sys.exit(0)
    if not isinstance(data, dict):
        print("BAD_JSON top level is not an object"); sys.exit(0)
hooks = data.get("hooks")
if not isinstance(hooks, dict):
    hooks = {}; data["hooks"] = hooks
pre = hooks.get("PreToolUse")
if not isinstance(pre, list):
    pre = []; hooks["PreToolUse"] = pre
def wired(e):
    if not isinstance(e, dict): return False
    for h in e.get("hooks", []) or []:
        if isinstance(h, dict) and "pretooluse-guard.sh" in str(h.get("command", "")):
            return True
    return False
if any(wired(e) for e in pre):
    print("SKIP"); sys.exit(0)
pre.append(entry)
if not dry:
    os.makedirs(os.path.dirname(sj), exist_ok=True)
    with open(sj, "w") as f:
        json.dump(data, f, indent=2); f.write("\n")
print("UPDATE" if existed else "ADD")
PY
)
    case "$st" in
      SKIP)   say "SKIP (up to date)  .claude/settings.json (PreToolUse guard wired)" ;;
      ADD)    would ADD ".claude/settings.json (created with the PreToolUse guard hook)" ;;
      UPDATE) would UPDATE ".claude/settings.json (PreToolUse guard hook merged, other keys kept)" ;;
      *)      manual ".claude/settings.json not merged: $st" ;;
    esac
  fi

  # f. state/kb-layout.json, then e. operating files (one python run; e needs the layout)
  st=$(python3 -c "$PY_OPFILES" "$R" "$TPL" "$SCRIPT_DIR" "$DRY" "$TODAY" "$STEP5_PREFIX" "$STEP5_NEW" 2>&1)
  while IFS='|' read -r kind act txt; do
    case "$kind" in
      ACT)  would "$act" "$txt" ;;
      MAN)  manual "$txt" ;;
      SKIP) say "SKIP (up to date)  $txt" ;;
      INFO) say "INFO  $txt" ;;
      SAY)  say "$txt" ;;
      "")   ;;
      *)    manual "layout/operating-file step: $kind $act $txt" ;;
    esac
  done <<EOF
$st
EOF

  # g. closing check: kb_tools.py lint (read-only; in --dry-run it reports the current state)
  local tools="$R/scripts/kb/kb_tools.py" label=""
  [ "$DRY" = 1 ] && label=" [current state, before any change]"
  if [ ! -f "$tools" ]; then tools="$MASTER_TOOLS"; label="$label [repo has no scripts/kb/kb_tools.py; ran the master copy]"; fi
  local lint; lint=$(python3 "$tools" --repo "$R" lint 2>&1)
  printf '%s\n' "$lint" | python3 -c '
import json, sys
raw = sys.stdin.read(); label = sys.argv[1]
try:
    d = json.loads(raw)
    print("LINT  kb_tools.py lint%s: %s, %d error(s), %d warning(s)" % (label, d.get("status"), len(d.get("errors", [])), len(d.get("warnings", []))))
    for e in d.get("errors", []): print("      error: " + e)
except Exception:
    first = next((l for l in raw.splitlines() if l.strip()), "no output")
    print("LINT  kb_tools.py lint%s: could not run (%s)" % (label, first))
' "$label"

  say "== $R: $CH change(s), $MAN manual item(s)"
}

# main loop in this shell (fd 3) so the totals survive
printf '%s\n' "$REPOS" | while IFS= read -r r; do [ -n "$r" ] && printf '%s\n' "$r"; done > "$TMPD/kb_upgrade_run.$$"
TOT_REPOS=0; TOT_CH=0; TOT_MAN=0
while IFS= read -r r <&3; do
  [ -n "$r" ] || continue
  upgrade_repo "$r"
  TOT_REPOS=$((TOT_REPOS+1)); TOT_CH=$((TOT_CH+CH)); TOT_MAN=$((TOT_MAN+MAN))
done 3< "$TMPD/kb_upgrade_run.$$"
rm -f "$TMPD/kb_upgrade_run.$$"
mode="applied"; [ "$DRY" = 1 ] && mode="dry-run, nothing written"
say "== TOTAL: $TOT_REPOS repo(s), $TOT_CH change(s), $TOT_MAN manual item(s) ($mode)"
exit 0
