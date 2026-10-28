#!/usr/bin/env python3
"""Portable KB initialization, history writing and preservation checks (stdlib only)."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import glob
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import uuid
from zoneinfo import ZoneInfo

DEFAULT_HOMES = {
    "brief": "state/BRIEF.md", "now": "state/NOW.md",
    "now_archive": "state/NOW-ARCHIVE.md", "findings": "state/FINDINGS.md",
    "details": "state/FINDINGS-DETAIL.md", "contradictions": "state/CONTRADICTIONS.md",
    "pitfalls": "docs/buildout/04-KNOWN-PITFALLS.md",
    "history_index": "docs/TribalKnowledge.md", "history_dir": "docs/tribal",
}
LAYOUT = "state/kb-layout.json"
BLOCK = re.compile(r"<!-- KB-SECTION-BEGIN\b[^\n]*-->.*?<!-- KB-SECTION-END -->", re.S)
BUDGETS = {"brief": 8192, "now": 35840, "findings": 36864, "contradictions": 20480}
# Lint budgets ported from the bash kb_lint.sh (bytes). Operating files, the HOT tier (register
# files beside BRIEF), the newest quarterly history child, the live checkpoint block, BRIEF age,
# and the fixed resume load a fresh session reads before any work.
OPERATING_BUDGETS = {"KNOWLEDGE-MAP.md": 12288, "CLAUDE.md": 4096, "AGENTS.md": 20480}
HOT_TIER_BUDGET = 102400
HISTORY_CHILD_BUDGET = 307200
CHECKPOINT_BUDGET = 1536
ALIGNMENT_TITLE = "Alignment (answer before work starts)"   # flush writes 1 to 5 questions or none
BRIEF_MAX_AGE_HOURS = 72
FIXED_LOAD_BUDGET = 120000
POINTER_PREFIXES = ("docs", "scripts", "state", "internal", "tasks", "archive", "cmd", "config")
PARITY_SCRIPT = "bin/sync_kb_skills.sh"   # relative to $HOME; run with --check when executable
LABELS = ("Agent:", "Task:", "Last operator instruction (verbatim, short):", "I was doing:",
          "Next action:", "Decisions this session (with WHY):", "Dead ends tried:",
          "Open question for operator:", "Uncommitted:", "Context at checkpoint:")


def path_in(root, relative):
    """Reject ambiguous paths and symlinked homes before reading or writing."""
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative or "\\" in relative or any(ord(c) < 32 for c in relative):
        raise ValueError("Invalid KB path")
    p = PurePosixPath(relative)
    if p.is_absolute() or any(part in ("..", ".git", ".claude", ".codex", ".env") for part in p.parts):
        raise ValueError("KB paths must stay in the project and outside private configuration")
    if str(p) != relative or relative == ".":
        raise ValueError("KB paths must be normalized relative paths")
    target = root / relative
    for item in (target, *target.parents):
        if item == root:
            break
        if item.is_symlink():
            raise ValueError("Symlinked KB path: " + relative)
    if not target.resolve().is_relative_to(root):
        raise ValueError("KB path escapes project")
    return target


def read(path):
    return path.read_bytes().decode("utf-8")


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write(path, text):
    """Atomically replace one file; leave equal content and its mtime untouched."""
    if path.exists() and read(path) == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(prefix=".kb-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(text.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True


def validate_layout(root, layout):
    root = Path(root).resolve()
    if layout.get("version") != 1 or layout.get("history_kind") not in ("quarterly", "flat"):
        raise ValueError("Unsupported KB layout version or history_kind")
    ZoneInfo(layout["timezone"])
    if not isinstance(layout.get("project"), str) or not layout["project"].strip() or "\n" in layout["project"]:
        raise ValueError("Project must be a nonempty single line")
    homes = layout["homes"]
    if set(homes) != set(DEFAULT_HOMES):
        raise ValueError("Layout homes must name exactly: " + ", ".join(DEFAULT_HOMES))
    if len(set(homes.values())) != len(homes):
        raise ValueError("Knowledge homes must be distinct")
    files = [v for k, v in homes.items() if k != "history_dir"]
    reserved = {LAYOUT, "KNOWLEDGE-MAP.md", "CLAUDE.md", "AGENTS.md", "state/README.md"}
    for key, relative in homes.items():
        target = path_in(root, relative)
        if relative in reserved or (key != "history_dir" and not relative.endswith(".md")):
            raise ValueError("Invalid knowledge home: " + relative)
        if target.exists() and (target.is_dir() != (key == "history_dir")):
            raise ValueError("Wrong file type for home: " + relative)
    for item in files:
        if any(other.startswith(item + "/") for other in homes.values()):
            raise ValueError("Knowledge file is also used as a parent directory")
    if any(v.startswith(homes["history_dir"] + "/") for k, v in homes.items() if k not in ("history_dir", "now_archive")):
        raise ValueError("History directory must be separate from register and index files")
    return layout


def load_layout(root):
    root = Path(root).resolve()
    path = path_in(root, LAYOUT)
    if not path.exists():
        raise ValueError("No KB layout: read KNOWLEDGE-MAP.md and adopt its homes with kbinit first")
    return validate_layout(root, json.loads(read(path)))


def clock(layout):
    return datetime.now(ZoneInfo(layout["timezone"]))


def values(layout, at):
    vals = {key.upper(): val for key, val in layout["homes"].items()}
    vals.update(PROJECT=layout["project"], DATE=at.date().isoformat(), STAMP=at.isoformat(timespec="seconds"),
                QUARTER=f"{at.year}-Q{(at.month-1)//3+1}")
    vals["HISTORY_NOTE"] = ("Quarterly children under `" + vals["HISTORY_DIR"] + "`, newest entry first"
                            if layout["history_kind"] == "quarterly" else "Existing flat ledger, newest entry first")
    # Claude Code auto-memory for this repo (Codex has none). Override with an optional top-level
    # layout key "memory_dir" when a repo's memory is keyed on another path (e.g. a renamed checkout).
    root = layout.get("_root")
    derived = ("~/.claude/projects/" + str(root).replace("/", "-") + "/memory") if root else "~/.claude/projects/<repo-key>/memory"
    vals["MEMORY_DIR"] = layout.get("memory_dir") or derived
    vals["TIME_ZONE"] = layout["timezone"]
    vals["TIME_ZONE_NOTE"] = "operator zone " + layout["timezone"] + " (state the zone in every timestamp)"
    return vals


def render(text, vals):
    def replace(match):
        key = match[1]
        if key not in vals:
            raise ValueError("Unresolved template placeholder: " + key)
        return vals[key]
    return re.sub(r"\{\{([A-Z_]+)\}\}", replace, text)


def managed_section(text, section):
    begins = text.count("<!-- KB-SECTION-BEGIN")
    ends = text.count("<!-- KB-SECTION-END -->")
    matches = list(BLOCK.finditer(text))
    if begins or ends:
        if begins != 1 or ends != 1 or len(matches) != 1:
            raise ValueError("Malformed or duplicate KB section markers; preserve file and reconcile first")
        return text[:matches[0].start()] + section.rstrip() + text[matches[0].end():]
    return text.rstrip() + "\n\n" + section.rstrip() + "\n"


def _find_operating_template(templates, name):
    for candidate in (templates / f"project-{name}.md.template",
                      templates.parent / f"project-{name}.md.template",
                      templates / f"{name}.md.template"):
        if candidate.is_file():
            return candidate
    raise ValueError(f"Missing operating file template: project-{name}.md.template")


def _find_kb_scripts(templates):
    script_dir = Path(__file__).resolve().parent
    kb_sub = templates / "scripts/kb"
    found = {}
    for base in (kb_sub, script_dir):
        if base.is_dir():
            for name in ("kb_tools.py", "kb_lint.sh", "session_health.sh"):
                p = base / name
                if p.is_file() and name not in found:
                    found[name] = p
    return [found[k] for k in sorted(found)]


def initialize(root, templates, project=None, zone="UTC", layout_file=None, dry_run=False, refresh_tools=False):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Project directory must already exist")
    templates = Path(templates).resolve()
    current = path_in(root, LAYOUT)
    if current.exists():
        layout = load_layout(root)
        if layout_file and json.loads(read(Path(layout_file))) != layout:
            raise ValueError("Existing layout cannot be changed by init; plan a separate home migration")
    elif layout_file:
        layout = validate_layout(root, json.loads(read(Path(layout_file))))
    else:
        legacy = any(path_in(root, x).exists() for x in ("KNOWLEDGE-MAP.md", "state/BRIEF.md", "docs/TribalKnowledge.md", "docs/KNOWN-PITFALLS.md", DEFAULT_HOMES["pitfalls"]))
        if legacy:
            raise ValueError("Existing knowledge detected: read its map and provide --layout; do not create competing homes")
        layout = validate_layout(root, {"version": 1, "project": project or root.name, "timezone": zone,
                                      "history_kind": "quarterly", "homes": DEFAULT_HOMES.copy()})
    at = clock(layout)
    vals = values(dict(layout, _root=root), at)
    section = render(read(templates/"KB-SECTION.md.template"), vals)
    vals["KB_SECTION"] = section.rstrip()
    planned = {}
    kept = []
    def missing(relative, content):
        target = path_in(root, relative)
        if target.exists():
            kept.append(relative)
        else:
            planned[relative] = content
    missing(LAYOUT, json.dumps(layout, indent=2) + "\n")
    missing("KNOWLEDGE-MAP.md", render(read(templates/"KNOWLEDGE-MAP.md.template"), vals))
    missing("state/README.md", read(templates/"state/README.md"))
    for key, source in (("brief", "BRIEF"), ("now", "NOW"), ("now_archive", "NOW-ARCHIVE"),
                        ("findings", "FINDINGS"), ("details", "FINDINGS-DETAIL"), ("contradictions", "CONTRADICTIONS")):
        missing(layout["homes"][key], render(read(templates/f"state/{source}.md.template"), vals))
    missing(layout["homes"]["pitfalls"], render(read(templates/"docs/KNOWN-PITFALLS.md.template"), vals))
    if layout["history_kind"] == "quarterly":
        missing(layout["homes"]["history_index"], render(read(templates/"docs/TribalKnowledge.md.template"), vals))
    elif not path_in(root, layout["homes"]["history_index"]).is_file():
        raise ValueError("Flat history adoption requires the existing ledger")
    for name in ("CLAUDE", "AGENTS"):
        relative = name + ".md"
        target = path_in(root, relative)
        if name == "CLAUDE" and target.exists():
            existing = read(target)
            if not BLOCK.search(existing) and re.search(r"^@AGENTS\.md\s*$", existing, re.M):
                kept.append(relative)  # one rules file: thin CLAUDE.md imports AGENTS.md, which holds the block
                continue
        new = (managed_section(read(target), section) if target.exists()
               else render(read(_find_operating_template(templates, name)), vals))
        if not target.exists() or read(target) != new:
            planned[relative] = new
    warnings = []
    for source in _find_kb_scripts(templates):
        relative = "scripts/kb/" + source.name
        target = path_in(root, relative)
        content = read(source)
        if not target.exists():
            planned[relative] = content
        elif read(target) != content:
            # session_health.sh carries a per-project CONFIG block: never overwritten, even on refresh.
            if refresh_tools and source.name != "session_health.sh":
                backup = "state/archive/kb-tools-" + at.strftime("%Y%m%dT%H%M%S") + "-" + digest(read(target))[:12] + "/" + source.name
                backup_path = path_in(root, backup)
                if backup_path.exists() and read(backup_path) != read(target):
                    raise ValueError("Backup path already has different content")
                planned[backup] = read(target)
                planned[relative] = content
            elif source.name == "session_health.sh":
                warnings.append("Existing tool preserved (per-project CONFIG block, never refreshed): " + relative)
            else:
                warnings.append("Existing tool preserved; review before --refresh-tools: " + relative)
    if path_in(root, "KNOWLEDGE-MAP.md").exists():
        warnings.append("Existing map preserved: reconcile its old Update Procedure and custom paths before declaring upgrade complete")
    if path_in(root, "zero.md").exists():
        warnings.append("Legacy zero.md preserved: migrate verified content to BRIEF/history before retiring it")
    if path_in(root, "AGENTS.override.md").exists():
        warnings.append("AGENTS.override.md exists: verify it does not hide the new KB instructions")
    if layout["history_kind"] == "quarterly" and not history_files(root, layout):
        child = layout["homes"]["history_dir"] + "/" + vals["QUARTER"] + ".md"
        init_id = "init-" + digest(layout["project"] + str(root))[:20]
        entry = "Knowledge base initialized. Existing project content preserved.\nEvidence: KNOWLEDGE-MAP.md; KB changes are uncommitted.\nNext: record verified project facts."
        initial = render(read(templates/"docs/tribal/QUARTER.md.template"), vals)
        planned[child] = insert_after_heading(initial, "## Entries", history_addition(init_id, entry, at))
        index_name = layout["homes"]["history_index"]
        index_text = planned[index_name] if index_name in planned else read(path_in(root, index_name))
        planned[index_name] = index_with_child(index_text, child, at)
    for relative in planned:
        dest = path_in(root, relative)
        if dest.exists() and not dest.is_file():
            raise ValueError("Destination is not a file: " + relative)
        for parent in dest.parents:
            if parent == root:
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError("Destination parent is not a directory")
    if not dry_run:
        for relative, content in planned.items():
            target = path_in(root, relative)
            write(target, content)
            if relative.startswith("scripts/kb/") and target.suffix in (".sh", ".py"):
                target.chmod(target.stat().st_mode | 0o111)
    return {"planned": list(planned), "kept": kept, "warnings": warnings, "dry_run": dry_run}


def history_files(root, layout):
    root = Path(root).resolve()
    homes = layout["homes"]
    if layout["history_kind"] == "flat":
        path = path_in(root, homes["history_index"])
        return [path] if path.exists() else []
    directory = path_in(root, homes["history_dir"])
    exclude = path_in(root, homes["now_archive"])
    paths = [p for p in (sorted(directory.glob("*.md")) if directory.exists() else []) if p != exclude]
    for path in paths:
        path_in(root, path.relative_to(root).as_posix())
    return paths


def insert_after_heading(text, heading, addition):
    suffix = r"(?: \([^\r\n]*\))?" if heading == "## Children" else ""
    pattern = re.compile(r"^" + re.escape(heading) + suffix + r"\r?\n", re.M)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError("Expected exactly one " + heading + " heading")
    pos = matches[0].end()
    return text[:pos] + addition + text[pos:]


def history_addition(run_id, entry, at):
    return (f"<!-- flush:{run_id} -->\n### " + at.isoformat(timespec="seconds") + " — handoff\n\n"
            + entry.strip() + f"\n<!-- /flush:{run_id} -->\n\n")


def index_with_child(text, relative, at):
    if relative in text:
        return text
    return insert_after_heading(text, "## Children", f"\n- `{relative}` — opened {at.date().isoformat()}\n")


def append_history(root, layout, run_id, entry, at=None):
    root = Path(root).resolve()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", run_id):
        raise ValueError("Invalid flush run ID")
    if not entry.strip() or "<!-- flush:" in entry or "<!-- /flush:" in entry:
        raise ValueError("History entry must be nonempty and cannot contain flush markers")
    at = at or clock(layout)
    start, end = f"<!-- flush:{run_id} -->", f"<!-- /flush:{run_id} -->"
    for path in history_files(root, layout):
        text = read(path)
        if start in text:
            expected = "\n" + entry.strip() + "\n" + end
            if text.count(start) != 1 or expected not in text[text.index(start):].split(end, 1)[0] + end:
                raise ValueError("Retry ID already exists with different entry content")
            if layout["history_kind"] == "quarterly":
                index = path_in(root, layout["homes"]["history_index"])
                write(index, index_with_child(read(index), path.relative_to(root).as_posix(), at))
            return {"path": path.relative_to(root).as_posix(), "duplicate_retry": True}
    addition = history_addition(run_id, entry, at)
    homes = layout["homes"]
    index = path_in(root, homes["history_index"])
    new_index = None
    if layout["history_kind"] == "flat":
        target = index
        if not target.is_file():
            raise ValueError("History home does not exist")
        old = read(target)
    else:
        quarter = f"{at.year}-Q{(at.month-1)//3+1}"
        number = 1
        while True:
            filename = quarter + ("" if number == 1 else f"-{number:02d}") + ".md"
            target = path_in(root, homes["history_dir"] + "/" + filename)
            if not target.exists() or target.stat().st_size < 307200:
                break
            number += 1
        old = read(target) if target.exists() else f"# {layout['project']} tribal knowledge — {quarter}\n\nImmutable entries, newest first.\n\n## Entries\n\n"
        if not index.is_file():
            raise ValueError("History index is missing")
        relative = target.relative_to(root).as_posix()
        new_index = index_with_child(read(index), relative, at)
    updated = insert_after_heading(old, "## Entries", addition)
    write(target, updated)
    if new_index is not None:
        write(index, new_index)
    return {"path": target.relative_to(root).as_posix(), "duplicate_retry": False}


def snapshot(root, layout):
    root = Path(root).resolve()
    paths = {value for key, value in layout["homes"].items() if key != "history_dir"}
    paths.update(path.relative_to(root).as_posix() for path in history_files(root, layout))
    paths.update((LAYOUT, "KNOWLEDGE-MAP.md"))
    files = {}
    for relative in sorted(paths):
        path = path_in(root, relative)
        if path.is_file():
            content = read(path)
            files[relative] = {"text": content, "sha256": digest(content), "mtime_ns": path.stat().st_mtime_ns}
    return {"version": 1, "root": str(root), "run_id": str(uuid.uuid4()),
            "at": clock(layout).isoformat(), "layout": layout, "files": files}


def section(text, title):
    match = re.search(r"^## " + re.escape(title) + r"[^\n]*\n.*?(?=^## |\Z)", text, re.M | re.S)
    return match[0] if match else ""


def alignment_errors(brief_text):
    """The Alignment section rule, shared by verify_flush (errors) and lint (warnings).

    Directly after the Live thread, flush writes `## Alignment (answer before work starts)` holding
    either the single line `none` or 1 to 5 numbered one-line questions (`1. <question>`).
    """
    block = section(brief_text, ALIGNMENT_TITLE)
    if not block:
        return ["BRIEF missing " + ALIGNMENT_TITLE + " section (flush writes 1 to 5 questions or none)"]
    lines = [line.strip() for line in block.split("\n")[1:] if line.strip()]
    if lines == ["none"]:
        return []
    if 1 <= len(lines) <= 5 and all(re.match(r"^\d+\. \S", line) for line in lines):
        return []
    return ["BRIEF Alignment must be 1 to 5 numbered one-line questions or the single line none"]


def ids(text, prefix):
    return re.findall(r"^\|\s*(" + re.escape(prefix) + r"-\d+)\s*\|", text, re.M)


def prepend_preserved(before, after, heading):
    if not before or before == after:
        return True
    suffix = r"(?: \([^\r\n]*\))?" if heading == "## Children" else ""
    match = re.search(r"^" + re.escape(heading) + suffix + r"\r?\n", before, re.M)
    if match:
        return bool(after.startswith(before[:match.end()]) and after.endswith(before[match.end():]))
    if heading == "## Entries":
        legacy_match = re.search(r"^### [^\r\n]+\r?\n", before, re.M)
        if legacy_match:
            return bool(after.startswith(before[:legacy_match.start()]) and after.endswith(before[legacy_match.start():]))
    return False


def verify_flush(root, before):
    root = Path(root).resolve()
    layout = load_layout(root)
    if before.get("version") != 1 or before.get("root") != str(root) or before.get("layout") != layout:
        raise ValueError("Snapshot does not match this project and layout")
    homes = layout["homes"]
    errors = []
    old = {p: record["text"] for p, record in before["files"].items()}
    for path, record in before["files"].items():
        path_in(root, path)
        if digest(record["text"]) != record["sha256"]:
            raise ValueError("Snapshot content hash mismatch")
        if not path_in(root, path).is_file():
            errors.append("Deleted KB file: " + path)
    run_id = before["run_id"]
    if not re.fullmatch(r"[a-f0-9-]{36}", run_id):
        raise ValueError("Malformed snapshot run ID")
    marker = re.compile(r"<!-- flush:" + re.escape(run_id) + r" -->\n.*?<!-- /flush:" + re.escape(run_id) + r" -->\n\n", re.S)
    count = 0
    history_names = {p.relative_to(root).as_posix() for p in history_files(root, layout)}
    for name in history_names:
        text = read(path_in(root, name))
        blocks = list(marker.finditer(text))
        count += len(blocks)
        stripped = marker.sub("", text)
        if name in old and stripped != old[name]:
            errors.append("Old history changed: " + name)
        if blocks:
            heading = re.search(r"^## Entries\r?\n", text, re.M)
            if not heading or blocks[0].start() != heading.end():
                errors.append("New handoff is not at the top of Entries: " + name)
    if count != 1:
        errors.append("Exactly one dated history entry is required for this flush run")
    brief_path = path_in(root, homes["brief"])
    brief = read(brief_path) if brief_path.is_file() else ""
    live = section(brief, "Live thread (checkpoint)")
    for label in LABELS:
        if not re.search(r"^" + re.escape(label), live, re.M):
            errors.append("BRIEF Live thread missing " + label)
    errors.extend(alignment_errors(brief))
    for title in ("Session thread", "Current state", "Read next"):
        if not section(brief, title):
            errors.append("BRIEF missing " + title)
    if len(brief.encode()) > 8192 or len(live.encode()) > 1536:
        errors.append("BRIEF or Live thread exceeds its byte budget")
    record = before["files"].get(homes["brief"])
    if record and brief_path.is_file() and brief == record["text"] and brief_path.stat().st_mtime_ns == record["mtime_ns"]:
        errors.append("BRIEF was not rewritten for this flush")
    for key, prefix in (("findings", "F"), ("contradictions", "C")):
        path = path_in(root, homes[key])
        text = read(path) if path.exists() else ""
        if not set(ids(old.get(homes[key], ""), prefix)) <= set(ids(text, prefix)):
            errors.append("Existing " + prefix + " IDs were deleted")
        if any(v > 1 for v in Counter(ids(text, prefix)).values()):
            errors.append("Duplicate " + prefix + " IDs")
    detail = path_in(root, homes["details"])
    if detail.exists() and not read(detail).startswith(old.get(homes["details"], "")):
        errors.append("Existing finding narrative was rewritten")
    now = path_in(root, homes["now"])
    archive = path_in(root, homes["now_archive"])
    archive_text = read(archive) if archive.exists() else ""
    old_focus = section(old.get(homes["now"], ""), "Current focus")
    if now.exists() and old_focus and old_focus != section(read(now), "Current focus") and old_focus not in archive_text:
        errors.append("Superseded Current focus is not preserved verbatim in the NOW archive")
    if not prepend_preserved(old.get(homes["now_archive"], ""), archive_text, "## Entries"):
        errors.append("Existing NOW archive was changed")
    if layout["history_kind"] == "quarterly":
        index = path_in(root, homes["history_index"])
        if index.exists() and not prepend_preserved(old.get(homes["history_index"], ""), read(index), "## Children"):
            errors.append("Existing history index content was removed or rewritten")
    pit = path_in(root, homes["pitfalls"])
    pit_text = read(pit) if pit.exists() else ""
    pit_old = old.get(homes["pitfalls"], "")
    pit_old_heads = re.findall(r"^## P-\d+\b.*?(?=^## P-\d+\b|\Z)", pit_old, re.M | re.S)
    for block in pit_old_heads:
        if block not in pit_text:
            errors.append("Existing pitfall narrative changed")
    if not pit_old_heads:
        for row in re.findall(r"^\|\s*P-\d+\s*\|.*$", pit_old, re.M):
            if row not in pit_text:
                errors.append("Existing pitfall narrative changed")
    if not set(ids(pit_old, "P")) <= set(ids(pit_text, "P")):
        errors.append("Existing pitfall index IDs removed")
    errors.extend(lint(root, layout, parity=False)["errors"])
    return {"status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors)), "run_id": run_id}


def _git(root, args):
    """Read-only git query; None when git or the repository is unavailable."""
    try:
        env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
        result = subprocess.run(["git", *args], cwd=root, env=env, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _size_row(root, relative, budget):
    path = root / relative
    if not path.is_file():
        return {"file": relative, "missing": True, "bytes": 0, "lines": 0, "maxline": 0, "budget": budget}
    text = read(path)
    return {"file": relative, "missing": False, "bytes": len(text.encode()), "lines": text.count("\n"),
            "maxline": max((len(line) for line in text.split("\n")), default=0), "budget": budget}


def _pointer_base(pointer):
    """Strip trailing punctuation, a :line suffix and a #anchor from a backticked pointer."""
    base = re.sub(r"[.,;:)]+$", "", pointer)
    base = re.sub(r":\d+$", "", base)
    return base.split("#", 1)[0]


def _pointer_dead(target):
    text = str(target)
    if "*" in text or "?" in text:
        return not glob.glob(text)
    return not target.exists()


def lint(root, layout, parity=True):
    """Every check of the bash kb_lint.sh plus the register invariants. Errors fail, warnings do not.

    `parity` runs ~/bin/sync_kb_skills.sh --check when it is executable (the only external command
    besides read-only git); verify_flush passes False because it consumes errors only.
    """
    root = Path(root).resolve()
    errors, warnings, sizes, next_ids = [], [], {}, {}
    by_section = {}
    def warn(section_name, message):
        warnings.append(message)
        by_section.setdefault(section_name, []).append(message)
    homes = layout["homes"]
    zone = ZoneInfo(layout["timezone"])
    now_at = datetime.now(zone)
    texts = {}
    for key, relative in homes.items():
        if key == "history_dir":
            continue
        path = path_in(root, relative)
        if not path.is_file():
            errors.append("Missing KB home: " + relative)
            continue
        text = read(path)
        texts[key] = text
        sizes[relative] = len(text.encode())
    # ---------------------------------------------------------------- sizes (bytes / lines / longest line / budget)
    history = history_files(root, layout)
    newest_child = history[-1].relative_to(root).as_posix() if history else None
    rows = [(homes["brief"], BUDGETS["brief"]), (homes["now"], BUDGETS["now"]),
            (homes["contradictions"], BUDGETS["contradictions"]), (homes["findings"], BUDGETS["findings"]),
            (homes["details"], None), ("KNOWLEDGE-MAP.md", OPERATING_BUDGETS["KNOWLEDGE-MAP.md"]),
            ("CLAUDE.md", OPERATING_BUDGETS["CLAUDE.md"]), ("AGENTS.md", OPERATING_BUDGETS["AGENTS.md"]),
            (homes["pitfalls"], None)]
    if newest_child:
        rows.append((newest_child, HISTORY_CHILD_BUDGET if layout["history_kind"] == "quarterly" else None))
    elif layout["history_kind"] == "quarterly":
        warn("sizes", "no history child found under " + homes["history_dir"])
    size_table = []
    for relative, budget in rows:
        row = _size_row(root, relative, budget)
        size_table.append(row)
        if row["missing"]:
            continue   # missing homes and operating files are reported as errors below
        sizes.setdefault(relative, row["bytes"])
        if budget is not None and row["bytes"] > budget:
            warn("sizes", "Over byte budget: " + relative + " is " + str(row["bytes"]) + " bytes, over its " + str(budget) + " budget")
    hot_dir = PurePosixPath(homes["brief"]).parent.as_posix()
    hot_files = [homes[k] for k in ("brief", "now", "contradictions", "findings")]
    hot_readme = hot_dir + "/README.md"
    if (root / hot_readme).is_file():
        hot_files.append(hot_readme)
    hot_bytes = sum(len(read(root / f).encode()) for f in hot_files if (root / f).is_file())
    hot_tier = {"dir": hot_dir, "bytes": hot_bytes, "budget": HOT_TIER_BUDGET, "files": hot_files}
    if hot_bytes > HOT_TIER_BUDGET:
        warn("sizes", hot_dir + "/ HOT tier is " + str(hot_bytes) + " bytes, over the " + str(HOT_TIER_BUDGET) + " budget")
    # ---------------------------------------------------------------- next free IDs
    highest = {}
    for key, prefix in (("findings", "F"), ("contradictions", "C"), ("pitfalls", "P")):
        found = ids(texts.get(key, ""), prefix)
        nums = [int(v.split('-')[1]) for v in found]
        # closed tier (e.g. state/FINDINGS-CLOSED.md) and declared "Next free ID" lines also count,
        # so an ID that was moved out or retired is never handed out again
        home = path_in(root, homes[key]) if key in homes else None
        if home is not None:
            closed = home.with_name(home.stem + "-CLOSED" + home.suffix)
            if closed.is_file():
                nums += [int(v.split('-')[1]) for v in ids(read(closed), prefix)]
        nums += [int(n) - 1 for n in re.findall(r"[Nn]ext free(?: ID)?:?\**\s*" + prefix + r"-(\d+)", texts.get(key, ""))]
        highest[prefix] = max(nums or [0])
        next_ids[prefix] = f"{prefix}-{highest[prefix]+1}"
        if any(n > 1 for n in Counter(found).values()):
            errors.append("Duplicate " + prefix + " register IDs")
    pit_body = texts.get("pitfalls", "")
    pit_heads = re.findall(r"^## (P-\d+)\b", pit_body, re.M)
    if (pit_heads or re.search(r"^## Index\b", pit_body, re.M)) and set(pit_heads) != set(ids(pit_body, "P")):
        errors.append("Pitfall headings and index IDs disagree")
    if len(re.findall(r"^## Current focus\s*$", texts.get("now", ""), re.M)) != 1:
        errors.append("NOW must contain exactly one Current focus section")
    # ---------------------------------------------------------------- operating files: managed block / import
    operating = {}
    for name in ("KNOWLEDGE-MAP.md", "CLAUDE.md", "AGENTS.md"):
        path = path_in(root, name)
        operating[name] = read(path) if path.is_file() else None
    sections = []
    for name in ("CLAUDE.md", "AGENTS.md"):
        text = operating[name] or ""
        matches = list(BLOCK.finditer(text))
        if name == "CLAUDE.md" and not matches and re.search(r"^@AGENTS\.md\s*$", text, re.M):
            continue  # one rules file: CLAUDE.md imports AGENTS.md, which holds the block
        if len(matches) != 1:
            errors.append("Missing or ambiguous managed KB block in " + name)
        else:
            sections.append(matches[0][0])
    if len(sections) == 2 and sections[0] != sections[1]:
        errors.append("Shared KB blocks differ between Claude and Codex")
    import_check = {"agents_present": operating["AGENTS.md"] is not None, "claude_present": operating["CLAUDE.md"] is not None}
    if operating["AGENTS.md"] is not None:
        if operating["CLAUDE.md"] is not None:
            ctext = operating["CLAUDE.md"]
            imports = bool(re.search(r"^[ \t]*@AGENTS\.md[ \t]*$", ctext, re.M))
            import_check["claude_imports_agents"] = imports
            import_check["claude_bytes"] = len(ctext.encode())
            import_check["claude_budget"] = OPERATING_BUDGETS["CLAUDE.md"]
            if not imports:
                warn("import", "CLAUDE.md has no '@AGENTS.md' line; Claude Code will not load the rules")
            elif BLOCK.search(ctext):
                warn("import", "CLAUDE.md imports AGENTS.md and also carries a KB-SECTION copy; remove the copy")
        if re.search(r"read .CLAUDE\.md. first", operating["AGENTS.md"], re.I):
            warn("import", "AGENTS.md tells the reader to read CLAUDE.md first; it must be self-contained")
    # ---------------------------------------------------------------- freshness: BRIEF age, last commit, live checkpoint
    freshness = {"brief_modified": None, "brief_age_hours": None, "last_commit": None, "last_commit_date": None,
                 "uncommitted_paths": None, "checkpoint_stamp": None, "checkpoint_bytes": None,
                 "checkpoint_budget": CHECKPOINT_BUDGET, "checkpoint_next_action": None, "last_checkpoint_by": None}
    brief_path = path_in(root, homes["brief"])
    brief_epoch = 0
    if brief_path.is_file():
        brief_epoch = brief_path.stat().st_mtime
        age_hours = int((now_at.timestamp() - brief_epoch) // 3600)
        freshness["brief_modified"] = datetime.fromtimestamp(brief_epoch, zone).isoformat(timespec="minutes")
        freshness["brief_age_hours"] = age_hours
        if age_hours > BRIEF_MAX_AGE_HOURS:
            warn("freshness", "BRIEF is " + str(age_hours) + " h old (> " + str(BRIEF_MAX_AGE_HOURS) + " h); verify it before trusting the session thread")
    log = _git(root, ["log", "-1", "--format=%h%x00%s%x00%ci%x00%ct"])
    if log and log.strip():
        parts = log.strip("\n").split("\x00")
        if len(parts) == 4:
            freshness["last_commit"] = (parts[0] + " " + parts[1])[:90]
            freshness["last_commit_date"] = parts[2]
            if parts[3].isdigit() and brief_epoch and brief_epoch < int(parts[3]):
                warn("freshness", "BRIEF is older than the last commit; a session committed without flushing")
        status = _git(root, ["status", "--short"])
        if status is not None:
            freshness["uncommitted_paths"] = len(status.splitlines())
    brief_text = texts.get("brief", "")
    live = section(brief_text, "Live thread (checkpoint)")
    if brief_path.is_file():
        if not live:
            warn("freshness", "BRIEF has no Live thread (checkpoint) block; run checkpoint")
        else:
            head = live.split("\n", 1)[0]
            stamp = re.sub(r"^## Live thread \(checkpoint\)\s*[—-]*\s*", "", head).strip()
            freshness["checkpoint_stamp"] = stamp or "(no stamp)"
            cp_bytes = len(live.rstrip("\n").encode()) + 1
            freshness["checkpoint_bytes"] = cp_bytes
            if cp_bytes > CHECKPOINT_BUDGET:
                warn("freshness", "Live thread (checkpoint) block is " + str(cp_bytes) + " bytes, over its " + str(CHECKPOINT_BUDGET) + " budget; it must stay readable at a glance")
            action = re.search(r"(?im)^\**next action\**:?\**[ \t]*(.*)$", live)
            next_action = action[1].replace("*", "").strip() if action else ""
            freshness["checkpoint_next_action"] = next_action or None
        agent = re.search(r"^Agent:\s*(.*)$", brief_text, re.M)
        freshness["last_checkpoint_by"] = agent[1].strip() if agent else None
        if not section(brief_text, ALIGNMENT_TITLE):
            warn("freshness", "BRIEF has no Alignment section; the next flush adds it")
        else:
            for message in alignment_errors(brief_text):
                warn("freshness", message)
    # ---------------------------------------------------------------- dead pointers (repo paths and ~/ tool paths in backticks)
    prefixes = set(POINTER_PREFIXES) | {PurePosixPath(v).parts[0] for v in homes.values() if "/" in v}
    repo_pointer = re.compile(r"`((?:" + "|".join(sorted(re.escape(p) for p in prefixes)) + r")/[^`\s]+)`")
    home_pointer = re.compile(r"`(?:~|\$HOME)(/[^`\s]+)`")
    dead = []
    for name in ("KNOWLEDGE-MAP.md", "CLAUDE.md", "AGENTS.md", homes["brief"]):
        path = path_in(root, name)
        if not path.exists():
            errors.append("Missing operating file: " + name)
            continue
        text = read(path)
        seen = set()
        for match in repo_pointer.finditer(text):
            base = _pointer_base(match[1])
            if base in seen or any(c in base for c in "<>{"):
                continue
            seen.add(base)
            if _pointer_dead(root / base):
                dead.append({"source": name, "pointer": match[1], "global": False})
                warn("pointers", "Dead pointer: " + name + " -> " + match[1])
        for match in home_pointer.finditer(text):
            base = _pointer_base(match[1]).rstrip("/")
            if base in seen or any(c in base for c in "<>{"):
                continue
            seen.add(base)
            if _pointer_dead(Path.home() / base.lstrip("/")):
                dead.append({"source": name, "pointer": "~" + match[1], "global": True})
                warn("pointers", "Dead pointer (global): " + name + " -> ~" + match[1])
    # ---------------------------------------------------------------- secret hygiene (file:line only, never the text)
    hot_mds = sorted(p.relative_to(root).as_posix() for p in (root / hot_dir).glob("*.md")) if (root / hot_dir).is_dir() else []
    scan_core = [n for n in ("KNOWLEDGE-MAP.md", "CLAUDE.md", "AGENTS.md") if operating[n] is not None]
    scan_core += [f for f in hot_mds if f not in scan_core]
    scan_wide = list(scan_core)
    for sub in ("docs", "tasks"):
        if (root / sub).is_dir():
            scan_wide += sorted(p.relative_to(root).as_posix() for p in (root / sub).glob("*.md"))
    key_then_value = re.compile(r"`/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_.-]+)+`[ \t]*=[ \t]*`")
    password_literal = re.compile(r"PGPASSWORD=['\"]?[A-Za-z0-9!@#%^&*]{4,}|[Pp]assword=['\"]?[A-Za-z0-9!@#%^&*]{6,}")
    hits = []
    def scan(files, pattern):
        for relative in files:
            path = root / relative
            if not path.is_file():
                continue
            for number, line in enumerate(read(path).split("\n"), 1):
                if pattern.search(line):
                    hits.append(relative + ":" + str(number))
    scan(scan_core, key_then_value)
    scan(scan_wide, password_literal)
    hits = sorted(set(hits))
    secrets = {"hits": hits, "settings_local_pgpassword_rules": None}
    if hits:
        warn("secrets", "a secret value appears to be written into a KB file (" + str(len(hits)) + " hit(s); file:line listed); replace it with 'fetch from Parameter Store'")
    for key in ("brief", "now", "contradictions", "findings"):
        text = texts.get(key, "")
        for match in re.finditer(r"(?i)(password|api[_-]?key|access[_-]?token)\s*[:=]\s*[\"']([A-Za-z0-9+/=_-]{12,})[\"']", text):
            line = text[:match.start()].count("\n") + 1
            warn("secrets", "Possible credential; inspect privately: " + homes[key] + ":" + str(line))
    settings_local = root / ".claude" / "settings.local.json"   # read-only count; never printed
    if settings_local.is_file():
        rule = re.compile(r'PGPASSWORD=(\'|"|\\"[^$]|[A-Za-z0-9])')
        count = len(rule.findall(read(settings_local)))
        secrets["settings_local_pgpassword_rules"] = count
        if count:
            warn("secrets", ".claude/settings.local.json carries " + str(count) + " allow rule(s) with a literal PGPASSWORD; delete those rules and use the env var")
    # ---------------------------------------------------------------- skill parity (Claude seat vs Codex seat)
    parity_result = {"checked": False, "in_sync": None, "output": [], "script": "~/" + PARITY_SCRIPT}
    script = Path.home() / PARITY_SCRIPT
    if parity and script.is_file() and os.access(script, os.X_OK):
        try:
            run = subprocess.run([str(script), "--check"], cwd=root, capture_output=True, text=True, timeout=60)
            parity_result.update(checked=True, in_sync=run.returncode == 0,
                                 output=(run.stdout + run.stderr).splitlines()[:10])
            if run.returncode != 0:
                warn("parity", "skill drift between seats; run " + parity_result["script"])
        except (OSError, subprocess.TimeoutExpired) as error:
            parity_result["reason"] = "parity script failed: " + type(error).__name__
    # ---------------------------------------------------------------- resume read cost
    def cost_row(target, label, display):
        path = Path(target)
        if path.is_file():
            size = len(read(path).encode())
            return {"file": display, "label": label, "bytes": size, "tokens": size // 4, "missing": False}
        return {"file": display, "label": label, "bytes": 0, "tokens": 0, "missing": True}
    memory_dir = values(dict(layout, _root=root), now_at)["MEMORY_DIR"]
    memory_index = Path(os.path.expanduser(memory_dir)) / "MEMORY.md"
    fixed = [cost_row(root / homes["brief"], "hook-injected", homes["brief"]),
             cost_row(root / "CLAUDE.md", "project instructions", "CLAUDE.md"),
             cost_row(root / "AGENTS.md", "imported by CLAUDE.md", "AGENTS.md"),
             cost_row(Path.home() / ".claude/CLAUDE.md", "global", "~/.claude/CLAUDE.md"),
             cost_row(memory_index, "auto-memory index", memory_dir.rstrip("/") + "/MEMORY.md")]
    fixed_bytes = sum(r["bytes"] for r in fixed)
    if fixed_bytes > FIXED_LOAD_BUDGET:
        warn("resume", "fixed resume load is " + str(fixed_bytes) + " bytes (~" + str(fixed_bytes // 4) + " tokens); trim BRIEF, CLAUDE.md or the memory index")
    pointed = [cost_row(root / "KNOWLEDGE-MAP.md", "map, read on demand", "KNOWLEDGE-MAP.md")]
    focus = section(texts.get("now", ""), "Current focus")
    pointed.append({"file": homes["now"] + " (Current focus section)", "label": "NOW current focus", "bytes": len(focus.encode()),
                    "tokens": len(focus.encode()) // 4, "missing": not focus})
    read_next = section(brief_text, "Read next")
    listed = []
    for pointer in re.findall(r"`([^`\n]+)`", read_next):
        target = Path(os.path.expanduser(pointer)) if pointer.startswith(("~/", "$HOME/")) else root / pointer
        if pointer in listed or not target.is_file():
            continue
        listed.append(pointer)
        pointed.append(cost_row(target, "BRIEF Read next", pointer))
    worst_bytes = fixed_bytes + sum(r["bytes"] for r in pointed)
    resume_cost = {"fixed": fixed, "fixed_bytes": fixed_bytes, "fixed_tokens": fixed_bytes // 4, "fixed_budget": FIXED_LOAD_BUDGET,
                   "pointed": pointed, "worst_case_bytes": worst_bytes, "worst_case_tokens": worst_bytes // 4}
    # ---------------------------------------------------------------- history children
    for path in history:
        if len(re.findall(r"^## Entries\s*$", read(path), re.M)) != 1:
            errors.append("Missing/ambiguous Entries heading: " + path.relative_to(root).as_posix())
    return {"status": "FAIL" if errors else "PASS", "errors": sorted(set(errors)),
            "warnings": sorted(set(warnings)), "sizes": sizes, "next_ids": next_ids,
            "root": str(root), "at": now_at.isoformat(timespec="minutes"),
            "size_table": size_table, "hot_tier": hot_tier, "highest_ids": highest,
            "import_check": import_check, "freshness": freshness, "dead_pointers": dead,
            "secrets": secrets, "parity": parity_result, "resume_cost": resume_cost,
            "warnings_by_section": {k: sorted(set(v)) for k, v in by_section.items()}}


def lint_text(result):
    """Human-readable sections in the order of the bash kb_lint.sh; warnings appear in their section."""
    out = []
    warned = result.get("warnings_by_section", {})
    def sec(name):
        for message in warned.get(name, []):
            out.append("  WARN: " + message)
    out.append("== KB LINT — " + result["at"] + " — " + result["root"])
    out.append("")
    out.append("== Sizes (bytes / lines / longest line)")
    out.append("  %-44s %9s %6s %8s  %s" % ("FILE", "BYTES", "LINES", "MAXLINE", "BUDGET"))
    for row in result["size_table"]:
        if row["missing"]:
            out.append("  %-44s %9s" % (row["file"], "MISSING"))
        else:
            out.append("  %-44s %9d %6d %8d  %s" % (row["file"], row["bytes"], row["lines"], row["maxline"],
                                                  row["budget"] if row["budget"] is not None else "-"))
    hot = result["hot_tier"]
    out.append("  " + hot["dir"] + "/ HOT tier total (brief, now, contradictions, findings, README): " + str(hot["bytes"]) + " bytes (budget " + str(hot["budget"]) + ")")
    sec("sizes")
    out.append("")
    out.append("== Next free IDs (read the register again immediately before assigning — two sessions can collide)")
    for prefix in ("F", "P", "C"):
        if prefix in result["next_ids"]:
            out.append("  next " + prefix + ": " + result["next_ids"][prefix] + "   (highest known: " + prefix + "-" + str(result["highest_ids"][prefix]) + ")")
    out.append("")
    out.append("== Freshness")
    f = result["freshness"]
    if f["brief_modified"]:
        out.append("  BRIEF last modified: " + f["brief_modified"] + "  (" + str(f["brief_age_hours"]) + " h ago)")
    if f["last_commit"]:
        out.append("  last commit: " + f["last_commit"])
        out.append("  last commit date: " + str(f["last_commit_date"]))
    else:
        out.append("  last commit: (not a git repository or git unavailable)")
    if f["uncommitted_paths"] is not None:
        out.append("  uncommitted paths: " + str(f["uncommitted_paths"]) + " (git status --short)")
    if f["checkpoint_stamp"]:
        out.append("  live checkpoint: " + f["checkpoint_stamp"])
        out.append("  live checkpoint size: " + str(f["checkpoint_bytes"]) + " bytes (budget " + str(f["checkpoint_budget"]) + ")")
        if not f["checkpoint_next_action"]:
            out.append("  INFO: checkpoint has no next action")
    sec("freshness")
    out.append("")
    out.append("== Dead pointers (backticked repo and ~/ paths in KNOWLEDGE-MAP.md, CLAUDE.md, AGENTS.md and BRIEF that do not exist)")
    if not result["dead_pointers"]:
        out.append("  none")
    for item in result["dead_pointers"]:
        out.append("  " + ("(global) " if item["global"] else "") + item["source"] + " -> " + item["pointer"])
    sec("pointers")
    out.append("")
    out.append("== Secret hygiene (Parameter Store key followed by a written value, password literals; file:line only)")
    s = result["secrets"]
    out.append("  none" if not s["hits"] else "\n".join("  " + h for h in s["hits"]))
    if s["settings_local_pgpassword_rules"] is not None:
        out.append("  .claude/settings.local.json: " + ("no literal PGPASSWORD in allow rules" if not s["settings_local_pgpassword_rules"]
                                                       else str(s["settings_local_pgpassword_rules"]) + " literal PGPASSWORD rule(s)"))
    sec("secrets")
    out.append("")
    out.append("== Import check (AGENTS.md = single rules source; CLAUDE.md imports it)")
    i = result["import_check"]
    if not i["agents_present"]:
        out.append("  no AGENTS.md (Codex has no operating file in this repo)")
    elif i["claude_present"]:
        out.append("  CLAUDE.md imports AGENTS.md (@AGENTS.md line present)" if i.get("claude_imports_agents") else "  CLAUDE.md does not import AGENTS.md")
        out.append("  CLAUDE.md is " + ("thin: " if i["claude_bytes"] <= i["claude_budget"] else "") + str(i["claude_bytes"]) + " bytes (budget " + str(i["claude_budget"]) + ")")
    else:
        out.append("  CLAUDE.md missing; Claude Code has no import of AGENTS.md")
    sec("import")
    out.append("")
    out.append("== Skill parity (Claude seat vs Codex seat; " + result["parity"]["script"] + " --check)")
    p = result["parity"]
    if p["checked"]:
        out.append("  in sync" if p["in_sync"] else "  drift reported:")
        if not p["in_sync"]:
            out.extend("  " + line for line in p["output"])
    else:
        out.append("  (" + p.get("reason", "no executable " + p["script"] + "; parity not checked") + ")")
    if f["last_checkpoint_by"]:
        out.append("  last checkpoint by: " + f["last_checkpoint_by"])
    sec("parity")
    out.append("")
    out.append("== Resume read cost (what a fresh session loads before doing work)")
    r = result["resume_cost"]
    def cost_line(row):
        if row["missing"]:
            return "  %8s        %8s  %s  (%s — MISSING)" % ("-", "-", row["file"], row["label"])
        return "  %8d bytes  ~%6d tokens  %s  (%s)" % (row["bytes"], row["tokens"], row["file"], row["label"])
    out.extend(cost_line(row) for row in r["fixed"])
    out.append("  %8d bytes  ~%6d tokens  FIXED LOAD (every session, before any work; budget %d)" % (r["fixed_bytes"], r["fixed_tokens"], r["fixed_budget"]))
    out.append("  -- pointed to (whole-file size; a disciplined resume reads only the named block/IDs):")
    out.extend(cost_line(row) for row in r["pointed"])
    out.append("  %8d bytes  ~%6d tokens  WORST CASE if every pointed-to file were read end to end (informational, no warning)" % (r["worst_case_bytes"], r["worst_case_tokens"]))
    sec("resume")
    out.append("")
    if result["errors"]:
        out.append("== Errors (hard failures)")
        out.extend("  ERROR: " + e for e in result["errors"])
        out.append("")
    n_err, n_warn = len(result["errors"]), len(result["warnings"])
    if n_err:
        out.append("== RESULT: FAIL — " + str(n_err) + " error(s), " + str(n_warn) + " warning(s)")
    elif n_warn:
        out.append("== RESULT: " + str(n_warn) + " warning(s)")
    else:
        out.append("== RESULT: clean")
    return "\n".join(out) + "\n"


def health(root):
    """Local checks only: no fetch, build, database, service or memory access."""
    root = Path(root).resolve()
    out = {"time": datetime.now(timezone.utc).isoformat(), "git": {}}
    for key, command in (("branch", ["git", "branch", "--show-current"]),
                         ("head", ["git", "rev-parse", "--short", "HEAD"]),
                         ("changes", ["git", "status", "--short"])):
        try:
            env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=5)
            out["git"][key] = (len(result.stdout.splitlines()) if key == "changes" else result.stdout.strip()) if result.returncode == 0 else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            out["git"][key] = "unavailable"
    try:
        layout = load_layout(root)
        brief = path_in(root, layout["homes"]["brief"])
        out["brief_age_hours"] = round((datetime.now().timestamp() - brief.stat().st_mtime)/3600, 2) if brief.exists() else None
    except (ValueError, OSError):
        out["kb"] = "layout missing or invalid; inspect the project's map"
    out["scope"] = "Local metadata only; application health and test status not checked"
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    default_templates = Path(os.environ.get("KB_TEMPLATES", str(Path.cwd()/".claude/skills/kbinit/templates")))
    init.add_argument("--templates", type=Path, default=default_templates)
    init.add_argument("--project")
    init.add_argument("--timezone", default="UTC")
    init.add_argument("--layout", type=Path)
    init.add_argument("--dry-run", action="store_true")
    init.add_argument("--refresh-tools", action="store_true")
    snap = sub.add_parser("snapshot")
    snap.add_argument("--out", type=Path, required=True)
    hist = sub.add_parser("append-history")
    hist.add_argument("--snapshot", type=Path, required=True)
    hist.add_argument("--entry", type=Path, required=True)
    verify = sub.add_parser("verify-flush")
    verify.add_argument("--snapshot", type=Path, required=True)
    lint_cmd = sub.add_parser("lint")
    lint_cmd.add_argument("--text", action="store_true", help="human-readable sections (JSON is the default)")
    sub.add_parser("health")
    args = parser.parse_args()
    root = args.repo.resolve()
    try:
        if args.command == "init":
            result = initialize(root, args.templates, args.project, args.timezone, args.layout, args.dry_run, args.refresh_tools)
        elif args.command == "health":
            result = health(root)
        else:
            layout = load_layout(root)
            if args.command == "snapshot":
                data = snapshot(root, layout)
                with args.out.open("x", encoding="utf-8") as stream:
                    json.dump(data, stream, indent=2)
                    stream.write("\n")
                result = {"snapshot": str(args.out), "run_id": data["run_id"]}
            elif args.command == "append-history":
                before = json.loads(read(args.snapshot))
                if before["root"] != str(root) or before["layout"] != layout:
                    raise ValueError("History snapshot belongs to a different root or layout")
                result = append_history(root, layout, before["run_id"], read(args.entry))
            elif args.command == "verify-flush":
                result = verify_flush(root, json.loads(read(args.snapshot)))
            else:
                result = lint(root, layout)
        if args.command == "lint" and args.text:
            print(lint_text(result), end="")
            return 1 if result["errors"] else 0
        print(json.dumps(result, indent=2))
        return 1 if result.get("errors") else 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("KB check failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
