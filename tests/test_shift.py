"""The state script, driven as a subprocess against a temp target repo, a local bare
remote, a temp runtime folder and the fake gh in tests/bin (ADR 0007)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIFT = ROOT / "cli" / "shift"
REPO = "acme/widget"
SLUG = "20-widget-version-1"
LEDGER = Path("docs/third-shift-ledger") / f"{SLUG}.json"
LOCKS = {}  # fixture name: the lock its first test holds while building it
TEMPLATES = {}  # fixture name: (folder, base commit, folder built in); each folder goes when the run ends


def issue(number, state="open"):
    return {"number": number, "state": state, "title": f"Ticket {number}"}


class Target(unittest.TestCase):
    """A temp target repo, its bare remote, runtime folder and fake gh; no tests.

    The first test of each class builds the fixture (and runs `prepare`); the rest copy it,
    which skips the costly git set-up and arm. Classes naming the same `fixture`, whose
    `prepare` builds the same state, share one build."""
    armed = False

    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.tmp = Path(d.name)
        self.home = self.tmp / "runtime"
        self.gh = self.tmp / "gh"
        self.gh.mkdir()
        self.remote = self.tmp / "remote.git"
        self.target = self.tmp / "target"
        self.env = {
            **os.environ,
            # the fake gh runs on the suite's Python, which starts in a third of the time
            "PATH": os.pathsep.join([str(ROOT / "tests" / "bin"), str(Path(sys.executable).parent),
                                     os.environ["PATH"]]),
            "THIRD_SHIFT_HOME": str(self.home),
            "FAKE_GH_DIR": str(self.gh),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        cls = type(self)
        key = cls.__dict__.get("fixture", f"{cls.__module__}.{cls.__qualname__}")  # not a parent's
        with LOCKS.setdefault(key, threading.Lock()):  # tests run on threads: one build
            template = TEMPLATES.get(key)
            if template:
                shutil.copytree(template[0].name, self.tmp, symlinks=True, dirs_exist_ok=True,
                                copy_function=shutil.copy)  # copy2's metadata costs 5x
                # paths into the new copy (the remote's, the target's), without a git process
                for f in (self.target / ".git" / "config", *self.home.glob("*/*/state.json")):
                    f.write_text(f.read_text().replace(template[2], str(self.tmp)))
                self.base = template[1]
            else:
                self.git("init", "-q", "--bare", "-b", "main", str(self.remote), cwd=self.tmp)
                self.git("clone", "-q", str(self.remote), str(self.target), cwd=self.tmp)
                (self.target / "README.md").write_text("widget\n")
                self.git("add", ".")
                self.git("commit", "-qm", "init")
                self.git("push", "-q", "origin", "HEAD:main")
                self.base = self.git("rev-parse", "HEAD")
            self.prescan = {
                "spec": {"number": 20, "title": "Widget version 1"},
                "repo": REPO,
                "base_commit": self.base,
                "tickets": [
                    {"number": 21, "title": "First", "state": "open",
                     "labels": ["ready-for-agent"], "blocked_by": [], "criteria": ["It runs"]},
                    {"number": 22, "title": "Second", "state": "open",
                     "labels": ["ready-for-agent"], "blocked_by": [21], "criteria": ["It flies"]},
                    {"number": 23, "title": "Human", "state": "open",
                     "labels": ["ready-for-human"], "blocked_by": [], "criteria": ["Signed"]},
                    {"number": 24, "title": "Old", "state": "closed",
                     "labels": ["ready-for-agent"], "blocked_by": [], "criteria": ["Was done"]},
                    {"number": 25, "title": "Triage", "state": "open",
                     "labels": ["needs-triage"], "blocked_by": [], "criteria": ["Looks right"]},
                ],
                "checks": [{"name": "uv", "ok": True, "detail": ""}],
                "warnings": ["App default model is not Opus"],
                "baseline_seconds": 12.5,
                "proven_commit": self.base,
            }
            self.sitting = {
                "classes": {"25": "human-verified"},
                "gaps": [{"question": "Which file format?", "answer": "JSON",
                          "adr": "docs/adr/0009-file-format.md"}],
                "end_state": "branch",
                "binding_sources": ["docs/adr/", "closed decision tickets", "#20", "briefs"],
                "warnings": [],
            }
            if not template:
                self.tracker({21: [], 22: [issue(21)], 23: [], 25: []})
                self.prepare()
                for repo in (self.target, self.remote):  # fewer files to copy per test
                    self.git("repack", "-adq", cwd=repo)
                for sample in self.tmp.rglob("hooks/*.sample"):
                    sample.unlink()
                keep = tempfile.TemporaryDirectory()
                shutil.copytree(self.tmp, keep.name, symlinks=True, dirs_exist_ok=True,
                                copy_function=shutil.copy)
                TEMPLATES[key] = keep, self.base, str(self.tmp)

    def prepare(self):
        """The state every test of the class starts from, built once and copied."""
        if self.armed:
            self.assertEqual(self.arm()[0], 0)

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.target, env=self.env,
                              check=True, capture_output=True, text=True).stdout.strip()

    def tracker(self, blocked_by, closed=()):
        api = {f"repos/{REPO}/issues/20/sub_issues":
               [issue(t["number"], "closed" if t["number"] in closed or t["state"] == "closed"
                      else "open") for t in self.prescan["tickets"]]}
        for n, blockers in blocked_by.items():
            api[f"repos/{REPO}/issues/{n}/dependencies/blocked_by"] = blockers
        (self.gh / "fixture.json").write_text(json.dumps({"repo": REPO, "api": api}))

    def shift(self, *args, cwd=None, env=None, uv=False, input=""):
        # the suite's own Python skips uv's start-up; one test runs the ADR 0003 form
        run = ["uv", "run", "--script"] if uv else [sys.executable]
        p = subprocess.run([*run, str(SHIFT), *args], cwd=cwd or self.target, input=input,
                           env=env or self.env, capture_output=True, text=True)
        return p.returncode, json.loads(p.stdout) if p.stdout.strip() else p.stderr

    def arm(self, *extra):
        (self.tmp / "prescan.json").write_text(json.dumps(self.prescan))
        (self.tmp / "sitting.json").write_text(json.dumps(self.sitting))
        return self.shift("arm", "--prescan", str(self.tmp / "prescan.json"),
                          "--sitting", str(self.tmp / "sitting.json"), "--mode", "away", *extra)

    def writes(self):
        f = self.gh / "writes.jsonl"
        return f.read_text().splitlines() if f.exists() else []

    def ledger(self):
        return json.loads((self.target / LEDGER).read_text())


class Shift(Target):
    fixture = "unarmed"  # shared with tests.test_tickets.NoCriteria
    # arm

    def test_arm_writes_the_opening_entry(self):
        code, out = self.arm("--ceiling", "90")
        self.assertEqual(code, 0, out)
        o = self.ledger()["opening"]
        self.assertEqual(o["spec"], {"number": 20, "title": "Widget version 1"})
        self.assertEqual(o["repo"], REPO)
        self.assertEqual(o["branch"], f"third-shift/{SLUG}")
        self.assertEqual(o["base_commit"], self.base)
        self.assertEqual(o["version"], json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text())["version"])
        self.assertEqual((o["mode"], o["threshold"], o["reserve"], o["ceiling"]),
                         ("away", 98, 5, 90))
        self.assertEqual(o["end_state"], "branch")
        self.assertEqual(o["baseline_seconds"], 12.5)
        self.assertEqual(o["proven_commit"], self.base)
        self.assertEqual(o["binding_sources"], self.sitting["binding_sources"])
        self.assertEqual(o["gaps"], self.sitting["gaps"])
        self.assertEqual(o["warnings"], ["App default model is not Opus"])
        self.assertEqual(o["tickets"][1], {
            "number": 22, "title": "Second", "class": "agent", "starting_state": "Backlog",
            "blocked_by": [21], "criteria": ["It flies"]})
        self.assertEqual([t["class"] for t in o["tickets"]],
                         ["agent", "agent", "human", "agent", "human-verified"])

    def test_arm_defaults_the_ceiling_and_day_threshold(self):
        (self.tmp / "prescan.json").write_text(json.dumps(self.prescan))
        (self.tmp / "sitting.json").write_text(json.dumps(self.sitting))
        code, out = self.shift("arm", "--prescan", str(self.tmp / "prescan.json"),
                               "--sitting", str(self.tmp / "sitting.json"), "--mode", "day")
        self.assertEqual(code, 0, out)
        o = self.ledger()["opening"]
        self.assertEqual((o["threshold"], o["ceiling"]), (90, 80))

    def test_arm_can_waive_the_ceiling(self):
        code, out = self.arm("--ceiling", "none")
        self.assertEqual(code, 0, out)
        self.assertIsNone(self.ledger()["opening"]["ceiling"])

    def test_human_tickets_start_in_needs_you_and_closed_in_done(self):
        self.arm()
        states = {t["number"]: t["starting_state"] for t in self.ledger()["opening"]["tickets"]}
        self.assertEqual(states, {21: "Ready", 22: "Backlog", 23: "Needs you",
                                  24: "Done", 25: "Ready"})

    def test_arm_commits_and_pushes_the_ledger_on_the_shift_branch(self):
        self.arm()
        branch = f"third-shift/{SLUG}"
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), branch)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "ledger: #20 armed")
        files = self.git("show", "--name-only", "--format=", "HEAD").splitlines()
        self.assertEqual(sorted(files), [str(LEDGER), str(LEDGER.with_suffix(".md"))])
        self.assertEqual(self.git("rev-parse", branch),
                         self.git("rev-parse", branch, cwd=self.remote))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_arm_keeps_runtime_state_outside_the_target(self):
        code, out = self.arm()
        state = json.loads((self.home / "acme" / "widget" / "state.json").read_text())
        self.assertEqual((state["armed"], state["gen"], state["spec"]), (True, 1, 20))
        for name in ("prescan", "sitting"):  # spec: Records, on the Mac; revival needs them
            self.assertEqual(json.loads((self.home / "acme" / "widget" / f"{name}.json").read_text()),
                             getattr(self, name))
        self.assertEqual(out["gen"], 1)
        self.assertEqual(self.writes(), [])

    def assert_refused(self, code):
        self.assertEqual(code, 1)
        self.assertFalse((self.home / "acme").exists())
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), "main")
        self.assertFalse((self.target / "docs").exists())
        self.assertEqual(self.git("branch", "-a").count("third-shift"), 0)
        self.assertEqual(self.writes(), [])

    def test_arm_refuses_an_unclassed_ticket(self):
        self.sitting["classes"] = {}
        code, out = self.arm()
        self.assert_refused(code)
        self.assertIn("#25", out["refused"])

    def test_arm_refuses_an_unanswered_gap(self):
        self.sitting["gaps"][0]["answer"] = ""
        self.assert_refused(self.arm()[0])

    def test_arm_refuses_a_gap_answered_with_whitespace(self):
        self.sitting["gaps"][0]["answer"] = "  "
        self.assert_refused(self.arm()[0])

    def test_arm_refuses_a_failed_check(self):
        self.prescan["checks"].append({"name": "verify/checks", "ok": False, "detail": "red"})
        self.assert_refused(self.arm()[0])

    def test_arm_refuses_when_the_base_commit_has_moved(self):
        (self.target / "x").write_text("x")
        self.git("add", ".")
        self.git("commit", "-qm", "moved")
        self.git("push", "-q", "origin", "main")  # ADR 0005: the base is the default branch
        code, _ = self.arm()
        self.assertEqual(code, 1)
        self.assertFalse((self.home / "acme").exists())
        self.assertFalse((self.target / "docs").exists())
        self.assertEqual(self.writes(), [])

    def test_arm_refuses_an_unknown_class(self):
        self.sitting["classes"]["25"] = "bogus"
        self.assert_refused(self.arm()[0])

    def test_arm_refuses_a_negative_unreadable_or_over_100_ceiling(self):
        for ceiling in ("-5", "abc", "101"):
            code, out = self.arm("--ceiling", ceiling)
            self.assert_refused(code)
            self.assertIn("refused", out)

    def test_arm_refuses_a_malformed_sitting_file(self):
        del self.sitting["end_state"]
        code, out = self.arm()
        self.assert_refused(code)
        self.assertIn("refused", out)

    def test_arm_refuses_a_missing_prescan_file(self):
        code, out = self.shift("arm", "--prescan", str(self.tmp / "nope"),
                               "--sitting", str(self.tmp / "nope"), "--mode", "day")
        self.assertEqual(code, 1)
        self.assertIn("refused", out)

    def test_arm_refuses_a_repo_name_that_escapes_the_runtime_folder(self):
        for repo in ("../../escape", "acme/..", "acme"):
            self.prescan["repo"] = repo
            code, out = self.arm()
            self.assert_refused(code)
            self.assertIn("refused", out)
            self.assertFalse((self.home / repo / "state.json").exists())

    def test_a_refused_push_leaves_nothing_behind_and_arm_can_run_again(self):
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        code, out = self.arm()
        self.assert_refused(code)
        self.assertIn("refused", out)
        hook.unlink()
        self.assertEqual(self.arm()[0], 0)

    def test_a_rejected_ledger_commit_leaves_nothing_behind_and_arm_can_run_again(self):
        hook = self.target / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        code, out = self.arm()
        self.assert_refused(code)
        self.assertEqual(self.git("status", "--porcelain"), "")
        hook.unlink()
        self.assertEqual(self.arm()[0], 0)

    def test_a_rejected_ledger_commit_reports_the_hooks_output(self):
        hook = self.target / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\necho said-on-stdout\necho said-on-stderr >&2\nexit 1\n")
        hook.chmod(0o755)
        code, out = self.arm()
        self.assertEqual(code, 1)
        self.assertIn("said-on-stdout", out["refused"])
        self.assertIn("said-on-stderr", out["refused"])

    def test_arm_refuses_while_a_shift_is_armed_and_keeps_its_state(self):
        self.assertEqual(self.arm()[0], 0)
        state = self.home / "acme" / "widget" / "state.json"
        before = state.read_text()
        self.git("checkout", "-q", "main")
        self.prescan["spec"] = {"number": 30, "title": "Another"}
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        code, out = self.arm()
        self.assertEqual(code, 1)
        self.assertIn("refused", out)
        self.assertEqual(state.read_text(), before)
        self.assertNotIn("third-shift/30", self.git("branch", "-a"))
        hook.unlink()
        self.assertEqual(self.arm()[0], 1)
        self.assertEqual(state.read_text(), before)

    def test_a_failed_state_write_leaves_nothing_behind_and_arm_can_run_again(self):
        self.home.write_text("not a folder")
        code, out = self.arm()
        self.assertEqual(code, 1)
        self.assertIn("refused", out)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), "main")
        self.assertFalse((self.target / "docs").exists())
        self.assertEqual(self.git("branch", "-a").count("third-shift"), 0)
        self.assertNotIn("third-shift", self.git("branch", cwd=self.remote))
        self.home.unlink()
        self.assertEqual(self.arm()[0], 0)

    def test_arm_from_a_subfolder_writes_the_ledger_at_the_top(self):
        sub = self.target / "src"
        sub.mkdir()
        (self.tmp / "prescan.json").write_text(json.dumps(self.prescan))
        (self.tmp / "sitting.json").write_text(json.dumps(self.sitting))
        code, out = self.shift("arm", "--prescan", str(self.tmp / "prescan.json"),
                               "--sitting", str(self.tmp / "sitting.json"), "--mode", "day",
                               cwd=sub)
        self.assertEqual(code, 0, out)
        self.assertTrue((self.target / LEDGER).exists())
        self.assertFalse((sub / "docs").exists())

    def test_the_script_runs_as_a_uv_script(self):
        code, out = self.shift("bogus", uv=True)
        self.assertEqual(code, 1)
        self.assertIn("refused", out)

    def test_usage_errors_are_refused_as_one_json_object(self):
        for args in ((), ("bogus",), ("arm", "--prescan", "p", "--sitting", "s", "--mode", "night"),
                     ("next",)):
            code, out = self.shift(*args)
            self.assertEqual(code, 1, args)
            self.assertIn("refused", out)

    def test_arm_commits_only_the_ledger_and_leaves_staged_work_staged(self):
        (self.target / "mine").write_text("mine")
        self.git("add", "mine")
        self.assertEqual(self.arm()[0], 0)
        files = self.git("show", "--name-only", "--format=", "HEAD").splitlines()
        self.assertEqual(sorted(files), [str(LEDGER), str(LEDGER.with_suffix(".md"))])
        self.assertEqual(self.git("status", "--porcelain"), "A  mine")

    def test_an_unsluggable_title_falls_back_to_the_number(self):
        self.prescan["spec"]["title"] = "!!!"
        code, out = self.arm()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["branch"], "third-shift/20")
        self.assertTrue((self.target / "docs/third-shift-ledger/20.json").exists())

    # next

    def test_next_reports_a_missing_gh_as_one_json_object(self):
        bin_ = self.tmp / "nogh"
        bin_.mkdir()
        (bin_ / "uv").symlink_to(shutil.which("uv"))
        (bin_ / "git").symlink_to(shutil.which("git"))
        code, out = self.shift("next", "--gen", "1",
                               env={**self.env, "PATH": f"{bin_}{os.pathsep}/usr/bin:/bin"})
        self.assertEqual(code, 1)
        self.assertIn("refused", out)

    def test_next_refuses_without_an_armed_shift(self):
        code, _ = self.shift("next", "--gen", "1")
        self.assertEqual(code, 1)


class Next(Target):
    armed = True

    def test_next_commits_and_pushes_a_changed_ledger(self):
        self.tracker({21: [], 22: [issue(21, "closed")], 25: []}, closed=[21])
        self.assertEqual(self.shift("next", "--gen", "1")[0], 0)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.git("log", "-1", "--format=%s"), "ledger: #20 frontier")
        files = self.git("show", "--name-only", "--format=", "HEAD").splitlines()
        self.assertEqual(sorted(files), [str(LEDGER), str(LEDGER.with_suffix(".md"))])
        branch = f"third-shift/{SLUG}"
        self.assertEqual(self.git("rev-parse", branch),
                         self.git("rev-parse", branch, cwd=self.remote))

    def test_next_leaves_history_alone_when_nothing_changed(self):
        self.shift("next", "--gen", "1")
        self.assertEqual(self.git("log", "-1", "--format=%s"), "ledger: #20 armed")

    def test_next_runs_from_a_subfolder(self):
        sub = self.target / "docs"
        code, out = self.shift("next", "--gen", "1", cwd=sub)
        self.assertEqual((code, out["ticket"]["number"]), (0, 21))

    def test_next_refuses_off_the_shift_branch(self):
        self.git("checkout", "-q", "-b", "other")
        self.tracker({21: [], 22: [issue(21, "closed")], 25: []}, closed=[21])
        code, out = self.shift("next", "--gen", "1")
        self.assertEqual(code, 1)
        self.assertIn("refused", out)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "ledger: #20 armed")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertNotIn("other", self.git("branch", "-a", cwd=self.remote))

    def test_next_pushes_a_frontier_commit_whose_push_failed_before(self):
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.tracker({21: [], 22: [issue(21, "closed")], 25: []}, closed=[21])
        self.assertEqual(self.shift("next", "--gen", "1")[0], 1)
        hook.unlink()
        self.assertEqual(self.shift("next", "--gen", "1")[0], 0)
        branch = f"third-shift/{SLUG}"
        self.assertEqual(self.git("rev-parse", branch),
                         self.git("rev-parse", branch, cwd=self.remote))

    def test_next_returns_the_first_frontier_ticket(self):
        code, out = self.shift("next", "--gen", "1")
        self.assertEqual((code, out["ticket"]["number"]), (0, 21))
        self.assertEqual(self.writes(), [])

    def test_next_sets_ready_from_native_blocking_only(self):
        self.tracker({21: [], 22: [issue(21, "closed")], 25: [issue(99)]}, closed=[21])
        code, out = self.shift("next", "--gen", "1")
        self.assertEqual((code, out["ticket"]["number"]), (0, 22))
        states = {n: t["state"] for n, t in self.ledger()["tickets"].items()}
        self.assertEqual(states, {"21": "Done", "22": "Ready", "23": "Needs you",
                                  "24": "Done", "25": "Backlog"})

    def test_next_reports_an_empty_frontier(self):
        self.tracker({22: [issue(99)]}, closed=[21, 25])
        code, out = self.shift("next", "--gen", "1")
        self.assertEqual((code, out["ticket"]), (0, None))
        self.assertEqual(out["frontier"], "empty")

    def test_next_refuses_a_stale_gen_with_stop_and_writes_nothing(self):
        self.tracker({21: [], 22: [issue(21, "closed")], 25: []}, closed=[21])
        code, out = self.shift("next", "--gen", "0")
        self.assertEqual(code, 2, out)
        self.assertTrue(out["stop"])
        self.assertEqual(self.git("log", "-1", "--format=%s"), "ledger: #20 armed")
        self.assertEqual(self.git("status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
