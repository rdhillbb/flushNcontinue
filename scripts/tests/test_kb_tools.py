import copy
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

TEMPLATES = Path(__file__).resolve().parents[2] / "claude" / "kb"
SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kb_tools", SCRIPTS / "kb_tools.py")
kb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kb)


class KBTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kb-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "project with spaces"
        self.root.mkdir()
        # Lint reads $HOME (parity script, global CLAUDE.md, memory index, ~/ pointers): isolate it.
        self.home = Path(self.temp.name).resolve() / "home"
        self.home.mkdir()
        patcher = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def init(self, **kwargs):
        result = kb.initialize(self.root, TEMPLATES, **kwargs)
        self.layout = kb.load_layout(self.root)
        return result

    def file(self, name):
        return self.root / self.layout["homes"][name]

    def tree(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    def handoff(self, before, entry="Agent: test\nTask: handoff\nChanges: no new facts\nNext: resume review"):
        kb.append_history(self.root, self.layout, before["run_id"], entry)
        brief = self.file("brief")
        # New handoff replaces the full snapshot while retaining compatible structure.
        brief.write_text(kb.read(brief).replace("Agent: kbinit", "Agent: test") + "\n")
        return kb.verify_flush(self.root, before)

    def test_new_project_creates_both_operating_files_and_requested_homes(self):
        self.init(project="Example", zone="Asia/Phnom_Penh")
        for name in ("CLAUDE.md", "AGENTS.md", "state/BRIEF.md", "state/NOW-ARCHIVE.md",
                     "state/FINDINGS.md", "state/FINDINGS-DETAIL.md", "state/CONTRADICTIONS.md",
                     "docs/buildout/04-KNOWN-PITFALLS.md", "KNOWLEDGE-MAP.md"):
            self.assertTrue((self.root/name).is_file(), name)
            self.assertNotIn("{{", kb.read(self.root/name))
        self.assertEqual(kb.lint(self.root, self.layout)["errors"], [])
        self.assertFalse((self.root/".claude").exists())
        self.assertFalse((self.root/"docs/KNOWN-PITFALLS.md").exists())
        self.assertEqual(len(kb.history_files(self.root, self.layout)), 1)

    def test_repeated_init_is_byte_and_mtime_idempotent(self):
        self.init()
        before = self.tree()
        result = self.init()
        self.assertEqual(result["planned"], [])
        self.assertEqual(self.tree(), before)

    def test_dry_run_writes_nothing(self):
        result = kb.initialize(self.root, TEMPLATES, dry_run=True)
        self.assertIn("CLAUDE.md", result["planned"])
        self.assertTrue(any("docs/tribal/" in p for p in result["planned"]))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_project_rules_survive_managed_refresh(self):
        original = "# App\n\nKeep local policy.\n\n<!-- KB-SECTION-BEGIN (old note) -->\nold block\n<!-- KB-SECTION-END -->\n\n## Rules\nCustom testing policy.\n"
        (self.root/"CLAUDE.md").write_text(original)
        self.init()
        new = kb.read(self.root/"CLAUDE.md")
        self.assertEqual(kb.BLOCK.sub("MANAGED", original), kb.BLOCK.sub("MANAGED", new))
        self.assertEqual(kb.BLOCK.search(new)[0], kb.BLOCK.search(kb.read(self.root/"AGENTS.md"))[0])

    def test_malformed_markers_abort_before_writes(self):
        (self.root/"CLAUDE.md").write_text("# App\n<!-- KB-SECTION-BEGIN -->\nmissing end\n")
        before = self.tree()
        with self.assertRaisesRegex(ValueError, "Malformed"):
            self.init()
        self.assertEqual(before, self.tree())

    def test_existing_knowledge_requires_explicit_layout(self):
        (self.root/"KNOWLEDGE-MAP.md").write_text("Existing custom map\n")
        before = self.tree()
        with self.assertRaisesRegex(ValueError, "provide --layout"):
            self.init()
        self.assertEqual(before, self.tree())

    def legacy(self, flat=False):
        homes = {key: "knowledge/" + Path(value).name for key, value in kb.DEFAULT_HOMES.items()}
        homes["history_dir"] = "knowledge/timeline"
        homes["pitfalls"] = "docs/lessons.md"
        homes["history_index"] = "knowledge/history.md"
        layout = {"version": 1, "project": "Legacy", "timezone": "UTC",
                  "history_kind": "flat" if flat else "quarterly", "homes": homes}
        config = Path(self.temp.name)/"adopt.json"
        config.write_text(json.dumps(layout))
        (self.root/"KNOWLEDGE-MAP.md").write_text("Custom homes and rules remain here.\n")
        if flat:
            target = self.root/homes["history_index"]
            target.parent.mkdir(parents=True)
            target.write_text("# Legacy history\n\n## Entries\n\n### Earlier\nOriginal immutable evidence.\n")
        return config

    def test_custom_homes_are_used_without_parallel_defaults(self):
        config = self.legacy()
        self.init(layout_file=config)
        self.assertTrue((self.root/"knowledge/BRIEF.md").is_file())
        self.assertTrue((self.root/"docs/lessons.md").is_file())
        self.assertFalse((self.root/"state/BRIEF.md").exists())
        self.assertFalse((self.root/"docs/buildout/04-KNOWN-PITFALLS.md").exists())
        self.assertEqual(kb.read(self.root/"KNOWLEDGE-MAP.md"), "Custom homes and rules remain here.\n")

    def test_existing_flat_history_is_not_reorganized(self):
        config = self.legacy(flat=True)
        before = kb.read(self.root/"knowledge/history.md")
        self.init(layout_file=config)
        self.assertEqual(kb.read(self.file("history_index")), before)
        self.assertFalse((self.root/"knowledge/timeline").exists())
        snapshot = kb.snapshot(self.root, self.layout)
        self.assertEqual(self.handoff(snapshot)["status"], "PASS")
        self.assertIn(before.split("## Entries\n", 1)[1], kb.read(self.file("history_index")))

    def test_register_content_is_preserved_by_init(self):
        self.init()
        self.file("findings").write_text("Existing finding content\n")
        self.file("brief").write_text("Existing live handoff\n")
        before = self.tree()
        self.init()
        self.assertEqual(before, self.tree())

    def test_legacy_zero_is_retained_until_agent_verifies_migration(self):
        (self.root/"zero.md").write_text("A previous decision and failed approach.\n")
        result = self.init()
        self.assertEqual(kb.read(self.root/"zero.md"), "A previous decision and failed approach.\n")
        self.assertTrue(any("zero.md" in x for x in result["warnings"]))

    def test_custom_tool_preserved_or_backed_up_on_explicit_refresh(self):
        self.init()
        tool = self.root/"scripts/kb/kb_lint.sh"
        tool.write_text("#!/bin/sh\necho custom\n")
        result = self.init()
        self.assertIn("echo custom", kb.read(tool))
        self.assertTrue(any("preserved" in x for x in result["warnings"]))
        self.init(refresh_tools=True)
        backups = list((self.root/"state/archive").glob("*/kb_lint.sh"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(kb.read(backups[0]), "#!/bin/sh\necho custom\n")
        self.assertEqual(kb.read(tool), kb.read(TEMPLATES/"scripts/kb/kb_lint.sh"))

    def test_session_health_never_overwritten_even_on_refresh(self):
        self.init()
        tool = self.root/"scripts/kb/session_health.sh"
        tool.write_text("#!/bin/sh\n# CONFIG per project\necho custom\n")
        result = self.init(refresh_tools=True)
        self.assertEqual(kb.read(tool), "#!/bin/sh\n# CONFIG per project\necho custom\n")
        self.assertTrue(any("session_health.sh" in x and "preserved" in x for x in result["warnings"]))
        self.assertEqual(list((self.root/"state/archive").glob("*/session_health.sh")), [])

    def test_symlinked_destination_rejected_without_external_write(self):
        outside = Path(self.temp.name)/"outside"
        outside.mkdir()
        (self.root/"state").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.init()
        self.assertEqual(list(outside.iterdir()), [])

    def test_traversal_duplicate_or_private_homes_rejected(self):
        self.init()
        for value in ("../escape.md", "/escape.md", ".git/config.md", "state/BRIEF.md"):
            layout = copy.deepcopy(self.layout)
            layout["homes"]["pitfalls"] = value
            with self.assertRaises(ValueError):
                kb.validate_layout(self.root, layout)

    def test_no_change_flush_still_updates_brief_and_history_only(self):
        self.init()
        snapshot = kb.snapshot(self.root, self.layout)
        before = self.tree()
        self.assertEqual(self.handoff(snapshot)["errors"], [])
        changed = {path for path, data in self.tree().items() if before.get(path) != data}
        self.assertEqual(changed, {self.layout["homes"]["brief"], kb.history_files(self.root, self.layout)[0].relative_to(self.root).as_posix()})

    def test_each_distinct_flush_adds_one_entry(self):
        self.init()
        runs = []
        for _ in range(2):
            before = kb.snapshot(self.root, self.layout)
            self.assertEqual(self.handoff(before)["status"], "PASS")
            runs.append(before["run_id"])
        text = kb.read(kb.history_files(self.root, self.layout)[0])
        self.assertLess(text.index(runs[1]), text.index(runs[0]))
        self.assertTrue(all(text.count("<!-- flush:"+r+" -->") == 1 for r in runs))

    def test_same_run_retry_is_idempotent_but_changed_entry_rejected(self):
        self.init()
        before = kb.snapshot(self.root, self.layout)
        kb.append_history(self.root, self.layout, before["run_id"], "Actual handoff")
        tree = self.tree()
        result = kb.append_history(self.root, self.layout, before["run_id"], "Actual handoff")
        self.assertTrue(result["duplicate_retry"])
        self.assertEqual(tree, self.tree())
        with self.assertRaisesRegex(ValueError, "different"):
            kb.append_history(self.root, self.layout, before["run_id"], "Different handoff")

    def test_history_and_brief_both_required(self):
        self.init()
        before = kb.snapshot(self.root, self.layout)
        kb.append_history(self.root, self.layout, before["run_id"], "A handoff")
        errors = kb.verify_flush(self.root, before)["errors"]
        self.assertTrue(any("BRIEF was not rewritten" in x for x in errors))
        before2 = kb.snapshot(self.root, self.layout)
        self.file("brief").write_text(kb.read(self.file("brief"))+"\n")
        self.assertTrue(any("Exactly one" in x for x in kb.verify_flush(self.root, before2)["errors"]))

    def alignment_brief(self, before, body):
        brief = self.file("brief")
        text = kb.read(brief)
        block = kb.section(text, kb.ALIGNMENT_TITLE)
        self.assertTrue(block, "fixture BRIEF has no Alignment section")
        replacement = "" if body is None else "## " + kb.ALIGNMENT_TITLE + "\n\n" + body + "\n\n"
        brief.write_text(text.replace(block, replacement))
        return self.handoff(before)["errors"]

    def test_verify_flush_requires_alignment_section(self):
        self.init()
        errors = self.alignment_brief(kb.snapshot(self.root, self.layout), None)
        self.assertTrue(any("BRIEF missing Alignment (answer before work starts) section" in x for x in errors), errors)

    def test_verify_flush_accepts_alignment_none_and_numbered_questions(self):
        self.init()
        self.assertEqual(self.alignment_brief(kb.snapshot(self.root, self.layout), "none"), [])
        questions = "1. Deploy Sunday or wait?\n2. Keep the old emailer?\n3. Which DB is truth?"
        self.assertEqual(self.alignment_brief(kb.snapshot(self.root, self.layout), questions), [])

    def test_verify_flush_rejects_malformed_alignment(self):
        self.init()
        rule = "BRIEF Alignment must be 1 to 5 numbered one-line questions or the single line none"
        six = "\n".join(str(i) + ". question " + str(i) for i in range(1, 7))
        self.assertIn(rule, self.alignment_brief(kb.snapshot(self.root, self.layout), six))
        self.assertIn(rule, self.alignment_brief(kb.snapshot(self.root, self.layout), "1. ok\nnot numbered"))
        self.assertIn(rule, self.alignment_brief(kb.snapshot(self.root, self.layout), ""))

    def test_modified_old_history_detected(self):
        self.init()
        before = kb.snapshot(self.root, self.layout)
        self.handoff(before)
        path = kb.history_files(self.root, self.layout)[0]
        path.write_text(kb.read(path).replace("Knowledge base initialized", "Altered past event"))
        self.assertTrue(any("Old history changed" in x for x in kb.verify_flush(self.root, before)["errors"]))

    def test_changed_focus_must_be_archived_verbatim(self):
        self.init()
        before = kb.snapshot(self.root, self.layout)
        old_focus = kb.section(kb.read(self.file("now")), "Current focus")
        self.file("now").write_text(kb.read(self.file("now")).replace(old_focus, "## Current focus\n\nA new task.\n\n"))
        self.assertTrue(any("Current focus" in e for e in self.handoff(before)["errors"]))
        archive = self.file("now_archive")
        archive.write_text(kb.insert_after_heading(kb.read(archive), "## Entries", "\n### Archived at handoff\n\n"+old_focus))
        self.assertEqual(kb.verify_flush(self.root, before)["errors"], [])

    def test_old_finding_and_contradiction_ids_cannot_disappear(self):
        self.init()
        self.file("findings").write_text(kb.read(self.file("findings"))+"\n| F-12 | OPEN | High | Defect | Evidence |\n")
        self.file("contradictions").write_text(kb.read(self.file("contradictions"))+"\n| C-4 | OPEN | docs | Stale | Evidence |\n")
        before = kb.snapshot(self.root, self.layout)
        self.file("findings").write_text(kb.read(self.file("findings")).replace("F-12", "F-13"))
        self.file("contradictions").write_text(kb.read(self.file("contradictions")).replace("C-4", "C-5"))
        errors = self.handoff(before)["errors"]
        self.assertIn("Existing F IDs were deleted", errors)
        self.assertIn("Existing C IDs were deleted", errors)

    def test_append_finding_evidence_allowed_rewriting_old_evidence_fails(self):
        self.init()
        before = kb.snapshot(self.root, self.layout)
        self.file("details").write_text(kb.read(self.file("details"))+"\n### F-1\nNew evidence.\n")
        self.assertEqual(self.handoff(before)["status"], "PASS")
        self.file("details").write_text("Only new evidence, old material removed.\n")
        self.assertIn("Existing finding narrative was rewritten", kb.verify_flush(self.root, before)["errors"])

    def test_quarter_rollover_and_size_split_preserve_previous_children(self):
        self.init()
        stamp = datetime(2030, 12, 31, 23, 59, tzinfo=ZoneInfo("UTC"))
        first = kb.append_history(self.root, self.layout, "year-end-1", "Year end", stamp)
        content = kb.read(self.root/first["path"])
        next_result = kb.append_history(self.root, self.layout, "year-start-1", "Next year", datetime(2031,1,1,tzinfo=ZoneInfo("UTC")))
        self.assertIn("2031-Q1.md", next_result["path"])
        self.assertEqual(kb.read(self.root/first["path"]), content)
        target = self.root/next_result["path"]
        target.write_text(kb.read(target)+"x"*307200)
        old_large = target.read_bytes()
        split = kb.append_history(self.root, self.layout, "year-start-2", "Continuation", datetime(2031,1,2,tzinfo=ZoneInfo("UTC")))
        self.assertIn("2031-Q1-02.md", split["path"])
        self.assertEqual(target.read_bytes(), old_large)
        self.assertIn(split["path"], kb.read(self.file("history_index")))

    def test_crlf_history_old_bytes_remain_identical(self):
        config = self.legacy(flat=True)
        target = self.root/"knowledge/history.md"
        target.write_bytes(b"# History\r\n\r\n## Entries\r\n\r\n### Old\r\nOriginal\r\n")
        self.init(layout_file=config)
        before = kb.snapshot(self.root, self.layout)
        self.assertEqual(self.handoff(before)["status"], "PASS")
        self.assertIn(b"\r\n### Old\r\nOriginal\r\n", target.read_bytes())

    def test_lint_compares_shared_content_not_operating_file_mtime(self):
        self.init()
        agents = self.root/"AGENTS.md"
        claude = self.root/"CLAUDE.md"
        self.assertNotIn("Shared KB blocks differ between Claude and Codex", kb.lint(self.root, self.layout)["errors"])
        block = kb.BLOCK.search(kb.read(agents))[0]
        claude.write_text("# App\n\n" + block.replace("Session Start", "Changed shared block", 1) + "\n")
        self.assertIn("Shared KB blocks differ between Claude and Codex", kb.lint(self.root, self.layout)["errors"])

    def test_health_only_runs_bounded_local_git_queries(self):
        self.init()
        def local_only(command, **kwargs):
            self.assertIn(command[1], ("branch", "rev-parse", "status"))
            self.assertEqual(command[0], "git")
            self.assertEqual(kwargs["timeout"], 5)
            return subprocess.CompletedProcess(command, 0, "example\n", "")
        with mock.patch.object(kb.subprocess, "run", side_effect=local_only) as run:
            result = kb.health(self.root)
            self.assertEqual(run.call_count, 3)
            self.assertIn("not checked", result["scope"])

    def test_wrappers_work_from_another_cwd(self):
        self.init()
        result = subprocess.run(["sh", str(self.root/"scripts/kb/session_health.sh")], cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        tail = result.stdout[result.stdout.rfind("\n{") + 1:] if "\n{" in result.stdout else result.stdout
        self.assertIsInstance(json.loads(tail), dict)   # text probe first, kb_tools health JSON last
        result = subprocess.run(["sh", str(self.root/"scripts/kb/kb_lint.sh")], cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("== KB LINT", result.stdout)
        self.assertIn("== RESULT:", result.stdout)
        self.assertIn("== Resume read cost", result.stdout)

    def test_cli_snapshot_does_not_overwrite_existing_baseline(self):
        self.init()
        dest = Path(self.temp.name)/"before.json"
        cmd = [sys.executable, str(self.root/"scripts/kb/kb_tools.py"), "--repo", str(self.root), "snapshot", "--out", str(dest)]
        first = subprocess.run(cmd, capture_output=True, text=True)
        original = dest.read_bytes()
        second = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(dest.read_bytes(), original)

    def test_retry_repairs_index_after_interrupted_history_write(self):
        self.init()
        index = self.file("history_index")
        original_index = kb.read(index)
        result = kb.append_history(self.root, self.layout, "interrupted-run", "New quarter", datetime(2040,1,1,tzinfo=ZoneInfo("UTC")))
        index.write_text(original_index)
        ledger = self.root/result["path"]
        before = ledger.read_bytes()
        retry = kb.append_history(self.root, self.layout, "interrupted-run", "New quarter")
        self.assertTrue(retry["duplicate_retry"])
        self.assertEqual(ledger.read_bytes(), before)
        self.assertIn(result["path"], kb.read(index))

    def test_inserting_text_inside_old_focus_archive_is_detected(self):
        self.init()
        archive = self.file("now_archive")
        archive.write_text(kb.read(archive)+"\n### Old\nFirst line.\nSecond line.\n")
        before = kb.snapshot(self.root, self.layout)
        archive.write_text(kb.read(archive).replace("First line.\n", "First line.\nInserted revision.\n"))
        self.assertIn("Existing NOW archive was changed", self.handoff(before)["errors"])

    def test_old_index_heading_and_custom_project_sources_survive_adoption(self):
        config = self.legacy()
        target = self.root/"knowledge/history.md"
        target.parent.mkdir(parents=True)
        target.write_text("# History\n\n## Children (quarter map)\n\nOlder references.\n")
        self.init(layout_file=config)
        self.assertIn("Older references.\n", kb.read(target))
        self.assertIn("knowledge/timeline/", kb.read(target))

    def test_snapshot_from_other_project_cannot_verify(self):
        self.init()
        before = kb.snapshot(self.root, self.layout)
        before["root"] = str(self.root.parent)
        with self.assertRaisesRegex(ValueError, "does not match"):
            kb.verify_flush(self.root, before)

    def test_faxitoncenew_now_archive_inside_history_dir_supported(self):
        homes = dict(kb.DEFAULT_HOMES)
        homes["now_archive"] = "docs/tribal/NOW-focus-archive-2026-09-07.md"
        layout = {"version": 1, "project": "FaxItOnce", "timezone": "Asia/Phnom_Penh",
                  "history_kind": "quarterly", "homes": homes}
        config = Path(self.temp.name) / "faxitonce_layout.json"
        config.write_text(json.dumps(layout))
        archive = self.root / homes["now_archive"]
        archive.parent.mkdir(parents=True, exist_ok=True)
        old_archive = "# NOW — Focus Archive\n\n---\n\n### Earlier focus (2026-09-07)\nOld focus line.\n"
        archive.write_text(old_archive)
        self.init(layout_file=config)
        self.assertNotIn(archive, kb.history_files(self.root, self.layout))
        before = kb.snapshot(self.root, self.layout)
        old_focus = kb.section(kb.read(self.file("now")), "Current focus")
        self.file("now").write_text(kb.read(self.file("now")).replace(old_focus, "## Current focus\n\nNew focus.\n\n"))
        archive.write_text("# NOW — Focus Archive\n\n---\n\n### Archived at handoff\n\n" + old_focus + "\n### Earlier focus (2026-09-07)\nOld focus line.\n")
        self.assertEqual(self.handoff(before)["status"], "PASS")

    def test_table_only_pitfalls_register_like_cmmc_sentinel_oci_supported(self):
        homes = dict(kb.DEFAULT_HOMES)
        homes["pitfalls"] = "docs/buildout_templates/04-KNOWN-PITFALLS.md"
        layout = {"version": 1, "project": "CMMCSentinel", "timezone": "Asia/Phnom_Penh",
                  "history_kind": "quarterly", "homes": homes}
        config = Path(self.temp.name) / "cmmc_layout.json"
        config.write_text(json.dumps(layout))
        pit = self.root / homes["pitfalls"]
        pit.parent.mkdir(parents=True, exist_ok=True)
        pit.write_text(
            "# OCI Gov Cloud — Known Pitfalls Index\n\n"
            "## CRITICAL — Will Lock You Out\n\n"
            "| # | Topic | Link |\n|---|---|---|\n"
            "| P-01 | Missing SSH egress | [P-01-ssh-egress-missing.md](pitfalls/P-01-ssh-egress-missing.md) |\n"
            "| P-02 | FIPS rejects Ed25519 SSH keys | [P-02-fips-ed25519.md](pitfalls/P-02-fips-ed25519.md) |\n"
        )
        self.init(layout_file=config)
        lint_res = kb.lint(self.root, self.layout)
        self.assertEqual(lint_res["errors"], [])
        self.assertEqual(lint_res["next_ids"]["P"], "P-3")
        before = kb.snapshot(self.root, self.layout)
        pit.write_text(kb.read(pit) + "| P-03 | New pitfall | [P-03-new.md](pitfalls/P-03-new.md) |\n")
        self.assertEqual(self.handoff(before)["status"], "PASS")
        pit.write_text(kb.read(pit).replace("Missing SSH egress", "Rewritten old row"))
        self.assertIn("Existing pitfall narrative changed", kb.verify_flush(self.root, before)["errors"])

    # ---------------------------------------------------------------- lint: port of the bash kb_lint.sh

    def lint(self, **kwargs):
        return kb.lint(self.root, self.layout, **kwargs)

    def test_lint_return_shape_is_backward_compatible_and_adds_sections(self):
        self.init()
        result = self.lint()
        for key in ("status", "errors", "warnings", "sizes", "next_ids"):
            self.assertIn(key, result)
        self.assertEqual(result["status"], "PASS")
        self.assertIsInstance(result["sizes"][self.layout["homes"]["brief"]], int)
        for key in ("size_table", "hot_tier", "highest_ids", "freshness", "dead_pointers", "secrets",
                    "import_check", "parity", "resume_cost", "warnings_by_section"):
            self.assertIn(key, result)
        self.assertEqual(sorted(result["warnings"]), sorted(sum(result["warnings_by_section"].values(), [])))

    def test_lint_cli_text_and_json_and_exit_codes(self):
        self.init()
        cmd = [sys.executable, str(SCRIPTS/"kb_tools.py"), "--repo", str(self.root), "lint"]
        as_json = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(as_json.returncode, 0, as_json.stderr)
        self.assertEqual(json.loads(as_json.stdout)["status"], "PASS")
        as_text = subprocess.run(cmd + ["--text"], capture_output=True, text=True)
        self.assertEqual(as_text.returncode, 0, as_text.stderr)
        for heading in ("== Sizes", "== Next free IDs", "== Freshness", "== Dead pointers", "== Secret hygiene",
                        "== Import check", "== Skill parity", "== Resume read cost", "== RESULT:"):
            self.assertIn(heading, as_text.stdout)
        # a hard failure (duplicate IDs) exits 1 in text mode and names the error; warnings alone do not fail
        self.file("findings").write_text(kb.read(self.file("findings")) + "| F-7 | OPEN | a | b | c |\n| F-7 | OPEN | a | b | c |\n")
        failed = subprocess.run(cmd + ["--text"], capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("ERROR: Duplicate F register IDs", failed.stdout)
        self.assertIn("== RESULT: FAIL", failed.stdout)

    def test_lint_size_table_lines_longest_line_and_budgets(self):
        self.init()
        now = self.file("now")
        now.write_text(kb.read(now) + "x" * 500 + "\n")
        result = self.lint()
        row = next(r for r in result["size_table"] if r["file"] == self.layout["homes"]["now"])
        self.assertEqual(row["lines"], kb.read(now).count("\n"))
        self.assertEqual(row["maxline"], 500)
        self.assertEqual(row["budget"], kb.BUDGETS["now"])
        self.assertEqual(result["hot_tier"]["budget"], kb.HOT_TIER_BUDGET)
        self.assertIn("CLAUDE.md", [r["file"] for r in result["size_table"]])
        self.assertEqual(next(r for r in result["size_table"] if r["file"] == "CLAUDE.md")["budget"], 4096)
        (self.root/"CLAUDE.md").write_text(kb.read(self.root/"CLAUDE.md") + "#" * 5000 + "\n")
        warnings = self.lint()["warnings"]
        self.assertTrue(any("Over byte budget: CLAUDE.md" in w for w in warnings), warnings)
        self.assertTrue(any("over its 4096 budget" in w for w in warnings), warnings)

    def test_lint_hot_tier_budget_warning(self):
        self.init()
        self.file("contradictions").write_text(kb.read(self.file("contradictions")) + "y" * (kb.HOT_TIER_BUDGET + 10) + "\n")
        result = self.lint()
        self.assertGreater(result["hot_tier"]["bytes"], kb.HOT_TIER_BUDGET)
        self.assertTrue(any("HOT tier" in w for w in result["warnings"]))

    def test_lint_freshness_brief_age_and_checkpoint_block(self):
        self.init()
        result = self.lint()
        self.assertEqual(result["freshness"]["brief_age_hours"], 0)
        self.assertIsNotNone(result["freshness"]["checkpoint_stamp"])
        self.assertLessEqual(result["freshness"]["checkpoint_bytes"], kb.CHECKPOINT_BUDGET)
        self.assertEqual(result["freshness"]["last_checkpoint_by"], "kbinit")
        self.assertIsNotNone(result["freshness"]["checkpoint_next_action"])
        self.assertFalse(any("BRIEF is" in w and "h old" in w for w in result["warnings"]))
        brief = self.file("brief")
        old = datetime.now().timestamp() - 100 * 3600
        os.utime(brief, (old, old))
        result = self.lint()
        self.assertGreaterEqual(result["freshness"]["brief_age_hours"], 99)
        self.assertTrue(any("h old (> 72 h)" in w for w in result["warnings"]), result["warnings"])
        # oversize live block, then no live block at all
        live = kb.section(kb.read(brief), "Live thread (checkpoint)")
        brief.write_text(kb.read(brief).replace(live, live.rstrip("\n") + "\n" + "z" * 1600 + "\n\n"))
        warnings = self.lint()["warnings"]
        self.assertTrue(any("Live thread (checkpoint) block is" in w and "over its 1536 budget" in w for w in warnings), warnings)
        brief.write_text(kb.read(brief).replace("## Live thread (checkpoint)", "## Something else"))
        warnings = self.lint()["warnings"]
        self.assertTrue(any("no Live thread (checkpoint) block" in w for w in warnings), warnings)

    def test_lint_warns_when_alignment_section_absent_or_malformed(self):
        self.init()
        self.assertFalse(any("Alignment" in w for w in self.lint()["warnings"]))
        brief = self.file("brief")
        text = kb.read(brief)
        block = kb.section(text, kb.ALIGNMENT_TITLE)
        brief.write_text(text.replace(block, "## " + kb.ALIGNMENT_TITLE + "\n\nfree text, not numbered\n\n"))
        warnings = self.lint()["warnings"]
        self.assertTrue(any("BRIEF Alignment must be 1 to 5 numbered" in w for w in warnings), warnings)
        brief.write_text(text.replace(block, ""))
        result = self.lint()
        self.assertTrue(any("BRIEF has no Alignment section; the next flush adds it" in w for w in result["warnings"]), result["warnings"])
        self.assertEqual(result["errors"], [])

    def test_lint_last_commit_newer_than_brief_warns_and_non_git_dir_tolerated(self):
        self.init()
        result = self.lint()   # temp dir is not a repository
        self.assertIsNone(result["freshness"]["last_commit"])
        self.assertIsNone(result["freshness"]["uncommitted_paths"])
        def fake_git(command, **kwargs):
            self.assertEqual(command[0], "git")
            self.assertIn(command[1], ("log", "status"))
            self.assertEqual(kwargs["timeout"], 5)
            out = "abc1234\x00commit message\x002099-01-01 00:00:00 +0000\x004070908800\n" if command[1] == "log" else " M a.md\n?? b.md\n"
            return subprocess.CompletedProcess(command, 0, out, "")
        with mock.patch.object(kb.subprocess, "run", side_effect=fake_git):
            result = self.lint()
        self.assertEqual(result["freshness"]["last_commit"], "abc1234 commit message")
        self.assertEqual(result["freshness"]["uncommitted_paths"], 2)
        self.assertTrue(any("older than the last commit" in w for w in result["warnings"]), result["warnings"])

    def test_lint_dead_pointers_cover_more_prefixes_globs_placeholders_and_home_paths(self):
        self.init()
        km = self.root/"KNOWLEDGE-MAP.md"
        (self.root/"internal").mkdir()
        (self.root/"internal/real.go").write_text("package x\n")
        km.write_text(kb.read(km) + "\nSee `internal/real.go`, `internal/missing.go:12`, `docs/tribal/2099-Q*.md`, "
                      "`tasks/<initiative>/TOs/x.md`, `docs/{a,b}.md`, `~/bin/absent_tool.py`, `~/bin/present_tool.py`.\n")
        (self.home/"bin").mkdir()
        (self.home/"bin/present_tool.py").write_text("print(1)\n")
        result = self.lint()
        pointers = {d["pointer"] for d in result["dead_pointers"]}
        self.assertIn("internal/missing.go:12", pointers)
        self.assertIn("docs/tribal/2099-Q*.md", pointers)
        self.assertIn("~/bin/absent_tool.py", pointers)
        self.assertNotIn("internal/real.go", pointers)
        self.assertNotIn("~/bin/present_tool.py", pointers)
        self.assertFalse(any("<initiative>" in p or "{a,b}" in p for p in pointers))
        self.assertTrue(any("Dead pointer (global): KNOWLEDGE-MAP.md -> ~/bin/absent_tool.py" == w for w in result["warnings"]))
        self.assertTrue(any(d["global"] for d in result["dead_pointers"]))

    def test_lint_secret_hygiene_reports_file_line_only(self):
        self.init()
        self.assertEqual(self.lint()["secrets"]["hits"], [])
        now = self.file("now")
        now.write_text(kb.read(now) + "\nkey `/proj/db_password` = `hunter2hunter2`\n")
        self.file("findings").write_text(kb.read(self.file("findings")) + "\nran PGPASSWORD=abcd1234 psql\n")
        (self.root/"docs").mkdir(exist_ok=True)
        (self.root/"docs/notes.md").write_text("password=secretvalue\npassword=$LOCAL_DB_PASSWORD\n")
        result = self.lint()
        hits = result["secrets"]["hits"]
        self.assertEqual(len(hits), 3, hits)
        self.assertTrue(all(h.count(":") == 1 and h.rsplit(":", 1)[1].isdigit() for h in hits), hits)
        self.assertFalse(any("hunter2" in h or "abcd1234" in h or "secretvalue" in h for h in hits))
        self.assertIn("docs/notes.md:1", hits)
        self.assertTrue(any("secret value appears" in w and "3 hit(s)" in w for w in result["warnings"]))
        self.assertFalse(any("hunter2" in w for w in result["warnings"]))

    def test_lint_settings_local_pgpassword_rules_counted_never_printed(self):
        self.init()
        settings = self.root/".claude/settings.local.json"
        settings.parent.mkdir()
        settings.write_text('{"permissions": {"allow": ["Bash(PGPASSWORD=$LOCAL_DB_PASSWORD psql:*)"]}}\n')
        result = self.lint()
        self.assertEqual(result["secrets"]["settings_local_pgpassword_rules"], 0)
        settings.write_text('{"permissions": {"allow": ["Bash(PGPASSWORD=\\"abc\\" psql:*)", "Bash(PGPASSWORD=xyz psql:*)"]}}\n')
        result = self.lint()
        self.assertEqual(result["secrets"]["settings_local_pgpassword_rules"], 2)
        self.assertTrue(any("settings.local.json carries 2 allow rule(s)" in w for w in result["warnings"]))
        self.assertFalse(any("xyz" in w or "abc" in w for w in result["warnings"]))
        text = kb.lint_text(result)
        self.assertNotIn("xyz", text)

    def test_lint_import_check_thin_claude_block_copy_and_self_contained_agents(self):
        self.init()
        claude = self.root/"CLAUDE.md"
        result = self.lint()   # template CLAUDE.md is thin and imports AGENTS.md
        self.assertTrue(result["import_check"]["claude_imports_agents"])
        block = kb.BLOCK.search(kb.read(self.root/"AGENTS.md"))[0]
        claude.write_text("# App\n\n" + block + "\n")   # old two-block model: block copy, no import line
        result = self.lint()
        self.assertFalse(result["import_check"]["claude_imports_agents"])
        self.assertTrue(any("no '@AGENTS.md' line" in w for w in result["warnings"]))
        claude.write_text("# App\n@AGENTS.md\n\n## Claude Code only\nhooks.\n")
        result = self.lint()
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["import_check"]["claude_imports_agents"])
        self.assertFalse(any("@AGENTS.md" in w or "KB-SECTION copy" in w for w in result["warnings"]), result["warnings"])
        claude.write_text("# App\n@AGENTS.md\n\n" + block + "\n")
        result = self.lint()
        self.assertTrue(any("KB-SECTION copy" in w for w in result["warnings"]), result["warnings"])
        agents = self.root/"AGENTS.md"
        agents.write_text(kb.read(agents) + "\nRead `CLAUDE.md` first.\n")
        self.assertTrue(any("self-contained" in w for w in self.lint()["warnings"]))

    def test_lint_skill_parity_runs_home_script_when_executable(self):
        self.init()
        result = self.lint()
        self.assertFalse(result["parity"]["checked"])
        script = self.home/kb.PARITY_SCRIPT
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("#!/bin/sh\n[ \"$1\" = --check ] || exit 2\necho 'WARN  DRIFT  flush'\nexit 1\n")
        script.chmod(0o755)
        result = self.lint()
        self.assertTrue(result["parity"]["checked"])
        self.assertFalse(result["parity"]["in_sync"])
        self.assertEqual(result["parity"]["output"], ["WARN  DRIFT  flush"])
        self.assertTrue(any("skill drift between seats" in w for w in result["warnings"]))
        self.assertIn("WARN  DRIFT  flush", kb.lint_text(result))
        script.write_text("#!/bin/sh\nexit 0\n")
        result = self.lint()
        self.assertTrue(result["parity"]["in_sync"])
        self.assertFalse(any("drift" in w for w in result["warnings"]))
        self.assertFalse(self.lint(parity=False)["parity"]["checked"])
        with mock.patch.object(kb.subprocess, "run") as run:
            kb.verify_flush(self.root, kb.snapshot(self.root, self.layout))
            self.assertFalse(any(call.args[0][0] == str(script) for call in run.call_args_list))

    def test_lint_resume_read_cost_fixed_and_pointed_rows(self):
        self.init()
        (self.home/".claude").mkdir()
        (self.home/".claude/CLAUDE.md").write_text("global rules\n")
        result = self.lint()
        rows = {r["file"]: r for r in result["resume_cost"]["fixed"]}
        self.assertEqual(rows[self.layout["homes"]["brief"]]["bytes"], result["sizes"][self.layout["homes"]["brief"]])
        self.assertEqual(rows["~/.claude/CLAUDE.md"]["bytes"], len("global rules\n"))
        self.assertTrue(next(r for r in result["resume_cost"]["fixed"] if r["label"] == "auto-memory index")["missing"])
        self.assertEqual(result["resume_cost"]["fixed_bytes"], sum(r["bytes"] for r in result["resume_cost"]["fixed"]))
        self.assertEqual(result["resume_cost"]["fixed_tokens"], result["resume_cost"]["fixed_bytes"] // 4)
        pointed = {r["file"]: r for r in result["resume_cost"]["pointed"]}
        self.assertIn("KNOWLEDGE-MAP.md", pointed)
        self.assertFalse(pointed[self.layout["homes"]["now"] + " (Current focus section)"]["missing"])
        brief = self.file("brief")
        read_next = kb.section(kb.read(brief), "Read next")
        brief.write_text(kb.read(brief).replace(read_next, read_next.rstrip("\n") + "\n1. `" + self.layout["homes"]["findings"] + "` F-1.\n2. `docs/absent.md`.\n\n"))
        result = self.lint()
        labels = {r["file"]: r["label"] for r in result["resume_cost"]["pointed"]}
        self.assertEqual(labels[self.layout["homes"]["findings"]], "BRIEF Read next")
        self.assertNotIn("docs/absent.md", labels)
        self.assertGreater(result["resume_cost"]["worst_case_bytes"], result["resume_cost"]["fixed_bytes"])
        self.assertFalse(any("fixed resume load" in w for w in result["warnings"]))
        (self.home/".claude/CLAUDE.md").write_text("g" * (kb.FIXED_LOAD_BUDGET + 1))
        self.assertTrue(any("fixed resume load is" in w for w in self.lint()["warnings"]))

    def test_lint_text_places_warnings_in_their_section(self):
        self.init()
        km = self.root/"KNOWLEDGE-MAP.md"
        km.write_text(kb.read(km) + "\n`docs/nowhere.md`\n")
        text = kb.lint_text(self.lint())
        pointers = text.index("== Dead pointers")
        secrets = text.index("== Secret hygiene")
        self.assertLess(pointers, text.index("WARN: Dead pointer: KNOWLEDGE-MAP.md -> docs/nowhere.md"))
        self.assertLess(text.index("WARN: Dead pointer"), secrets)
        self.assertRegex(text, r"== RESULT: \d+ warning\(s\)\n$")


if __name__ == "__main__":
    unittest.main()

