"""`cli/settings`, through its command line against a temp CLAUDE_CONFIG_DIR (ADR 0007): never
the real home or user settings."""
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_shift import ROOT

SETTINGS = ROOT / "cli" / "settings"
RULES = json.loads((ROOT / "cli" / "rules.json").read_text())


class Settings(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name) / "claude"
        self.file = self.dir / "settings.json"
        self.env = {**os.environ, "CLAUDE_CONFIG_DIR": str(self.dir), "HOME": d.name}

    def run_settings(self, *args):
        r = subprocess.run([sys.executable, str(SETTINGS), *args], env=self.env,
                           capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)

    def test_show_changes_nothing_and_write_adds_every_rule_once(self):
        mine = {"model": "opus", "permissions": {"allow": ["Bash(ls *)", RULES["allow"][0]],
                                                 "defaultMode": "auto"},
                "enabledPlugins": {"x@y": True}}
        self.dir.mkdir()
        self.file.write_text(json.dumps(mine))
        before = self.file.read_text()
        code, show = self.run_settings()
        self.assertEqual(code, 0, show)
        self.assertFalse(show["written"])
        self.assertEqual(show["add"], {"allow": RULES["allow"][1:], "deny": RULES["deny"],
                                       "set": RULES["set"]})
        self.assertEqual(self.file.read_text(), before)  # show writes nothing
        code, wrote = self.run_settings("--write")
        self.assertEqual((code, wrote["add"], wrote["written"]), (0, show["add"], True))
        after = json.loads(self.file.read_text())
        self.assertEqual(after["permissions"]["allow"], ["Bash(ls *)"] + RULES["allow"])
        self.assertEqual(after["permissions"]["deny"], RULES["deny"])
        self.assertTrue(after["permissions"]["blockWritesOutsideWorkingDirectories"])
        self.assertEqual((after["model"], after["enabledPlugins"], after["permissions"]["defaultMode"]),
                         ("opus", {"x@y": True}, "auto"))
        written = self.file.read_text()
        code, again = self.run_settings("--write")  # a rerun changes nothing
        self.assertEqual((code, again["add"], again["written"]), (0, {"allow": [], "deny": [], "set": {}},
                                                              False))
        self.assertEqual(self.file.read_text(), written)

    def test_no_settings_file_is_created(self):
        code, r = self.run_settings("--write")
        self.assertEqual((code, r["written"]), (0, True))
        self.assertEqual(json.loads(self.file.read_text()),
                         {"permissions": {"allow": RULES["allow"], "deny": RULES["deny"],
                                          **RULES["set"]}})

    def test_a_users_own_write_block_value_is_shown_before_it_is_replaced(self):
        self.dir.mkdir()
        self.file.write_text(json.dumps({"permissions": {"blockWritesOutsideWorkingDirectories": False}}))
        code, show = self.run_settings()
        self.assertEqual((code, show["add"]["set"]), (0, {"blockWritesOutsideWorkingDirectories": True}))
        self.assertFalse(json.loads(self.file.read_text())["permissions"]["blockWritesOutsideWorkingDirectories"])
        self.run_settings("--write")
        self.assertTrue(json.loads(self.file.read_text())["permissions"]["blockWritesOutsideWorkingDirectories"])

    def test_the_files_mode_is_kept(self):
        self.dir.mkdir()
        self.file.write_text("{}")
        self.file.chmod(0o600)
        self.assertEqual(self.run_settings("--write")[0], 0)
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)

    def test_a_read_only_settings_file_refuses_and_is_kept(self):
        self.dir.mkdir()
        self.file.write_text("{}")
        self.file.chmod(0o444)
        code, r = self.run_settings("--write")
        self.assertEqual((code, r["ok"]), (1, False))
        self.assertEqual((self.file.read_text(), self.file.stat().st_mode & 0o777), ("{}", 0o444))

    def test_an_unwritable_folder_refuses_with_one_json_object(self):
        self.dir.mkdir()
        self.file.write_text("{}")
        self.dir.chmod(0o555)
        self.addCleanup(self.dir.chmod, 0o755)
        code, r = self.run_settings("--write")
        self.assertEqual((code, r["ok"]), (1, False))
        self.assertEqual([p.name for p in self.dir.iterdir()], ["settings.json"])
        self.assertEqual(self.file.read_text(), "{}")

    def test_non_ascii_text_is_kept_byte_identical(self):
        self.dir.mkdir()
        self.file.write_text('{"note": "café ☕"}', encoding="utf-8")
        self.assertEqual(self.run_settings("--write")[0], 0)
        self.assertIn('"note": "café ☕"'.encode(), self.file.read_bytes())

    def test_a_symlinked_settings_file_stays_a_symlink(self):
        self.dir.mkdir()
        real = self.dir / "real.json"
        real.write_text("{}")
        self.file.symlink_to(real)
        self.assertEqual(self.run_settings("--write")[0], 0)
        self.assertTrue(self.file.is_symlink())
        self.assertEqual(json.loads(real.read_text())["permissions"]["deny"], RULES["deny"])

    def test_unreadable_or_odd_settings_refuse_and_are_kept(self):
        self.dir.mkdir()
        for text in ('{"permissions": {', '[]', '{"permissions": {"allow": "Bash(ls)"}}'):
            with self.subTest(text):
                self.file.write_text(text)
                code, r = self.run_settings("--write")
                self.assertEqual((code, r["ok"]), (1, False))
                self.assertEqual(self.file.read_text(), text)

    def test_the_script_allow_rules_match_how_the_skills_call_the_scripts(self):
        """Claude Code substitutes ${CLAUDE_PLUGIN_ROOT} in skill text, so the call carries an
        absolute path; a Bash rule's * matches any text, as fnmatch's does."""
        calls = set(re.findall(r'uv run --script "\$\{CLAUDE_PLUGIN_ROOT\}/cli/(\w+)"[^\n`]*',
                               "".join(p.read_text() for p in (ROOT / "skills").rglob("*.md"))))
        self.assertTrue({"shift", "prescan", "settings"} <= calls, calls)
        rules = [r[5:-1] for r in RULES["allow"] if r.startswith("Bash(uv ")]
        for script in calls - {"settings", "recipe"}:  # setup runs attended: its scripts may prompt
            cmd = f'uv run --script "/plugins/cache/third-shift/0.1.0/cli/{script}" arm --gen 1'
            self.assertTrue(any(fnmatch.fnmatchcase(cmd, r) for r in rules), cmd)


if __name__ == "__main__":
    unittest.main()
