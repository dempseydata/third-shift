"""The prescan's environment checks (#31), through `cli/prescan`'s command line with the machine
faked per check (ADR 0007): never the real home, gh login, power or Playwright cache."""
import json
import os
import shutil
import sys
import time
import unittest

from tests.test_prescan import PrescanTarget, ticket
from tests.test_shift import ROOT

NAMES = ["project scope", "token scopes", "board", "uv", "allow and deny rules", "guard hooks",
         "recipe proven", "playwright browser", "push", "mains power", "clean start",
         "verify/checks"]


class Environment(PrescanTarget):
    fixture = "prescan"

    def scan(self, env=None):
        self.tickets(ticket(21))
        code, out, p = self.run_prescan(env and {**self.env, **env})
        self.assertEqual(code, 0, out)  # a failed check is a result, never a refusal
        return p

    def failed(self, env=None):
        """The failed checks' names; each failure points to setup."""
        checks = self.scan(env)["checks"]
        for c in checks:
            if not c["ok"]:
                self.assertIn("setup", c["detail"], c)
        return [c["name"] for c in checks if not c["ok"]]

    def test_every_check_passes_on_a_ready_machine_and_target(self):
        def tree(root):
            return {(p, p.read_bytes() if p.is_file() else None) for p in root.rglob("*")
                    if ".git" not in p.relative_to(root).parts}
        self.tickets(ticket(21))
        settings = self.user / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps(self.settings))
        before = tree(self.user), tree(self.target), tree(ROOT)
        p = self.scan()
        self.assertEqual([c["name"] for c in p["checks"]], NAMES)
        self.assertEqual([c for c in p["checks"] if not c["ok"]], [])
        self.assertEqual(p["warnings"], [])
        self.assertIsInstance(p["baseline_seconds"], float)
        self.assertEqual(p["proven_commit"], self.git("rev-parse", "HEAD~1"))
        self.assertEqual((tree(self.user), tree(self.target), tree(ROOT)), before)  # read-only
        self.assertEqual(self.writes(), [])

    def test_a_token_without_the_project_scope(self):
        self.gh_extra["auth"]["hosts"]["github.com"][0]["scopes"] = "repo, gist"
        self.assertEqual(self.failed(), ["project scope"])

    def test_a_token_without_the_repo_scope(self):
        self.gh_extra["auth"]["hosts"]["github.com"][0]["scopes"] = "project"
        self.assertEqual(self.failed(), ["token scopes"])

    def test_gh_not_logged_in(self):
        del self.gh_extra["auth"]
        self.assertEqual(self.failed()[:2], ["project scope", "token scopes"])

    def test_no_board_titled_for_the_repo(self):
        self.gh_extra["graphql"]["Board"]["repository"]["owner"]["projectsV2"]["nodes"] = [
            {"title": "third-shift: other"}]
        self.assertEqual(self.failed(), ["board"])

    def test_no_uv(self):
        self.fake("uv", "exit 127")
        self.assertEqual(self.failed(), ["uv"])

    def test_a_missing_allow_or_deny_rule(self):
        for kind in ("allow", "deny"):
            with self.subTest(kind):
                whole = self.settings["permissions"][kind]
                self.settings["permissions"][kind] = whole[1:]
                self.assertEqual(self.failed(), ["allow and deny rules"])
                self.settings["permissions"][kind] = whole

    def test_writes_outside_working_directories_not_blocked(self):
        for value in (None, False):
            with self.subTest(value):
                self.settings["permissions"]["blockWritesOutsideWorkingDirectories"] = value
                self.assertEqual(self.failed(), ["allow and deny rules"])

    def test_no_user_settings(self):
        self.settings = None  # json "null": unreadable as settings
        self.assertEqual(self.failed(), ["allow and deny rules", "guard hooks"])

    def test_the_guard_counts_only_through_the_plugin_route(self):
        self.settings["enabledPlugins"] = {"third-shift@third-shift": False}
        self.assertEqual(self.failed(), ["guard hooks"])

    def test_the_recipe_changed_since_its_proven_commit(self):
        recipe = self.target / "verify" / "recipe.md"
        recipe.write_text("changed\n" + recipe.read_text())  # same Proven section, new body
        self.git("commit", "-qam", "recipe changed")
        self.git("push", "-q", "origin", "HEAD:main")
        p = self.scan()
        bad = [c for c in p["checks"] if not c["ok"]]
        self.assertEqual([c["name"] for c in bad], ["recipe proven"])
        self.assertIn("changed since the Proven commit: verify/recipe.md", bad[0]["detail"])

    def test_the_playwright_config_changed_since_the_proven_commit(self):
        (self.target / "playwright.config.ts").write_text("export default {retries: 9}\n")
        self.assertIn("recipe proven", self.failed())

    def test_a_recipe_without_a_proven_commit(self):
        (self.target / "verify" / "recipe.md").write_text("# Verify recipe\n")
        self.git("commit", "-qam", "unproven")
        self.git("push", "-q", "origin", "HEAD:main")
        p = self.scan()
        self.assertEqual([c["name"] for c in p["checks"] if not c["ok"]], ["recipe proven"])
        self.assertIsNone(p["proven_commit"])

    def test_the_playwright_browser_missing(self):
        shutil.rmtree(self.browser)
        self.assertEqual(self.failed(), ["playwright browser"])

    def test_a_playwright_browser_folder_without_its_completion_marker(self):
        (self.browser / "INSTALLATION_COMPLETE").unlink()
        self.assertEqual(self.failed(), ["playwright browser"])

    def test_a_failed_push_dry_run(self):
        self.git("remote", "set-url", "--push", "origin", str(self.tmp / "nowhere.git"))
        self.assertEqual(self.failed(), ["push"])

    def test_the_push_dry_run_skips_the_targets_pre_push_hook(self):
        hook = self.target / ".git" / "hooks" / "pre-push"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.assertEqual(self.failed(), [])

    def test_battery_refuses_an_away_shift_and_warns_a_day_shift(self):
        self.fake("pmset", "echo \"Now drawing from 'Battery Power'\"")
        p = self.scan()
        power = next(c for c in p["checks"] if c["name"] == "mains power")
        self.assertEqual((power["ok"], power["mode"]), (False, "away"))
        self.assertEqual(len(p["warnings"]), 1)
        self.assertIn("battery", p["warnings"][0])
        self.prescan = p
        self.sitting["classes"] = {}
        code, out = self.arm()  # away
        self.assertEqual(code, 1, out)
        self.assertIn("mains power", out["refused"])
        (self.tmp / "prescan.json").write_text(json.dumps(p))
        code, out = self.shift("arm", "--prescan", str(self.tmp / "prescan.json"),
                               "--sitting", str(self.tmp / "sitting.json"), "--mode", "day")
        self.assertEqual(code, 0, out)
        self.assertIn(p["warnings"][0], self.ledger()["opening"]["warnings"])

    def test_unreadable_power_refuses_an_away_shift(self):
        self.fake("pmset", "exit 1")
        self.assertEqual(self.failed(), ["mains power"])

    def test_a_dirty_tree_or_one_off_the_default_branch_or_ahead(self):
        (self.target / "scratch").write_text("x")
        self.assertEqual(self.failed(), ["clean start"])
        (self.target / "scratch").unlink()
        self.git("switch", "-q", "-c", "elsewhere")
        self.assertEqual(self.failed(), ["clean start"])
        self.git("switch", "-q", "main")
        self.git("commit", "-q", "--allow-empty", "-m", "ahead")
        self.assertEqual(self.failed(), ["clean start"])

    def test_failing_checks_script(self):
        p = self.scan({"FAKE_CHECKS_EXIT": "1"})
        self.assertEqual([c["name"] for c in p["checks"] if not c["ok"]], ["verify/checks"])
        self.assertIsNone(p["baseline_seconds"])

    def test_no_checks_script(self):
        (self.target / "verify" / "checks").unlink()
        self.assertIn("verify/checks", self.failed())

    def test_checks_script_bounded_by_a_timeout(self):
        p = self.scan({"FAKE_CHECKS_SLEEP": "5", "THIRD_SHIFT_CHECKS_TIMEOUT": "0.5"})
        c = next(c for c in p["checks"] if c["name"] == "verify/checks")
        self.assertFalse(c["ok"])
        self.assertIn("timed out", c["detail"])

    def runner(self, trap):
        """verify/checks as a test runner with a server started outside its group, as
        Playwright's webServer is; the pid file names the runner, then the server."""
        pids = self.tmp / "pids"
        server = f"{sys.executable} -c 'import os, time; os.setsid(); time.sleep(30)'"
        checks = self.target / "verify" / "checks"
        checks.write_text(f"#!/bin/sh\n{server} >/dev/null 2>&1 &\nchild=$!\n"
                          f"echo $$ $child > {pids}\n{trap}\nwhile :; do sleep 0.1; done\n")
        self.git("commit", "-qam", "runner")
        self.git("push", "-q", "origin", "HEAD:main")
        return pids

    def assertGone(self, *pids):
        def alive(pid):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            return True
        deadline = time.monotonic() + 3
        while any(map(alive, pids)) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual([p for p in pids if alive(p)], [])

    def test_a_timed_out_runner_gets_sigterm_to_stop_its_detached_server(self):
        pids = self.runner("trap 'kill $child; exit 0' TERM")
        p = self.scan({"THIRD_SHIFT_CHECKS_TIMEOUT": "0.5"})
        self.assertIn("timed out", next(c for c in p["checks"] if c["name"] == "verify/checks")["detail"])
        self.assertGone(*map(int, pids.read_text().split()))

    def test_a_timed_out_runner_ignoring_sigterm_is_killed_after_the_grace(self):
        pids = self.runner("trap '' TERM")
        runner, server = map(int, (self.scan({"THIRD_SHIFT_CHECKS_TIMEOUT": "0.5",
                                              "THIRD_SHIFT_CHECKS_GRACE": "0.5"}) and
                                   pids.read_text()).split())
        os.kill(server, 9)  # outside the group and its runner never stopped it: not ours to reach
        self.assertGone(runner)

    def test_the_baseline_is_the_checks_duration(self):
        p = self.scan({"FAKE_CHECKS_SLEEP": "1"})
        self.assertGreaterEqual(p["baseline_seconds"], 1)
        self.assertLess(p["baseline_seconds"], 3)

    def test_a_default_model_other_than_opus_is_a_warning_only(self):
        self.settings["model"] = "sonnet"
        p = self.scan()
        self.assertEqual([c["name"] for c in p["checks"] if not c["ok"]], [])
        self.assertEqual(len(p["warnings"]), 1)
        self.assertIn("Opus", p["warnings"][0])


if __name__ == "__main__":
    unittest.main()
