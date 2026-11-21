"""`cli/recipe`, setup's Proven record and Playwright pin (#36), through its command line against
a temp target, with npx and npm faked (ADR 0007). The Proven section it writes is read back by
`cli/prescan` itself."""
import json
import subprocess
import sys
import unittest

from tests.test_prescan import RECIPE, PrescanTarget, ticket
from tests.test_shift import ROOT

RECIPE_CLI = ROOT / "cli" / "recipe"


class Recipe(PrescanTarget):
    fixture = "recipe"

    def prepare(self):  # what setup commits as `third-shift: setup`: no Proven section yet
        checks = self.target / "verify" / "checks"
        checks.parent.mkdir()
        checks.write_text("#!/bin/sh\nexit 0\n")
        checks.chmod(0o755)
        (self.target / "verify" / "recipe.md").write_text(RECIPE)
        (self.target / "playwright.config.ts").write_text("export default {}\n")
        self.git("add", ".")
        self.git("commit", "-qm", "third-shift: setup")
        self.git("push", "-q", "origin", "HEAD:main")

    def recipe(self, *args):
        r = subprocess.run([sys.executable, str(RECIPE_CLI), *args], cwd=self.target,
                           env=self.env, capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)

    def recipe_check(self):
        self.tickets(ticket(21))
        code, out, p = self.run_prescan()
        self.assertEqual(code, 0, out)
        return next(c for c in p["checks"] if c["name"] == "recipe proven"), p

    def record(self):
        setup = self.git("rev-parse", "HEAD")
        code, o = self.recipe("proven", "--commit", "HEAD", "--note", "list cut 3 to 2:\n# expected 3")
        self.assertEqual((code, o["proven"], o["written"]), (0, setup, True), o)
        self.git("commit", "-qam", "third-shift: setup proven")
        self.git("push", "-q", "origin", "HEAD:main")
        return setup

    def test_a_recipe_proven_by_setup_passes_the_prescan_and_a_changed_one_fails(self):
        setup = self.record()
        check, p = self.recipe_check()
        self.assertTrue(check["ok"], check)
        self.assertEqual(p["proven_commit"], setup)
        self.assertEqual(self.recipe("proven")[1], {"ok": True, "proven": setup, "changed": ""})
        recipe = self.target / "verify" / "recipe.md"
        recipe.write_text(recipe.read_text().replace("Start it.", "Start it twice."))
        self.git("commit", "-qam", "recipe changed")
        self.git("push", "-q", "origin", "HEAD:main")
        check, _ = self.recipe_check()
        self.assertFalse(check["ok"])
        self.assertIn("changed since the Proven commit: verify/recipe.md", check["detail"])

    def test_rerecording_keeps_one_proven_section(self):
        setup = self.record()
        code, o = self.recipe("proven", "--commit", setup, "--note", "list cut 3 to 2: # expected 3")
        self.assertEqual((code, o["written"]), (0, False), o)
        text = (self.target / "verify" / "recipe.md").read_text()
        self.assertEqual(text.count("## Proven"), 1)
        self.assertTrue(text.endswith(f"## Proven\n\n{setup}: list cut 3 to 2: # expected 3\n"))

    def test_a_commit_without_this_recipe_refuses_and_writes_nothing(self):
        recipe = self.target / "verify" / "recipe.md"
        before = recipe.read_text()
        code, o = self.recipe("proven", "--commit", self.base, "--note", "broke it")
        self.assertEqual(code, 1, o)
        self.assertIn("changed since the Proven commit", o["refused"])
        self.assertEqual(recipe.read_text(), before)
        self.assertEqual(self.recipe("proven")[1]["proven"], None)


class Pin(PrescanTarget):
    fixture = "prescan"

    def setUp(self):
        super().setUp()
        # chromium revisions by version; only revision 1 (self.browser) is installed
        revs = {"2.0.0": 5, "1.10.0": 4, "1.9.0": 1, "1.8.0": 0}
        cases = "".join(f"  *playwright@{v}\\ *) rev={r};;\n" for v, r in revs.items())
        self.calls = self.tmp / "npx.log"
        self.fake("npx", f'echo "$*" >> {self.calls}\ncase "$* " in\n'
                         f'  *--no-install*) rev="${{FAKE_LOCAL_REV:-9}}";;\n{cases}esac\n'
                         f'echo "Chrome (playwright chromium v$rev)"\n'
                         f'echo "  Install location:    {self.browser.parent}/chromium-$rev"')
        self.fake("npm", """echo '["1.8.0", "1.9.0", "2.1.0-alpha-1", "2.0.0", "1.10.0"]'""")

    def pin(self, playwright=None, env=None):
        pkg = {"devDependencies": {"@playwright/test": playwright}} if playwright else {}
        (self.target / "package.json").write_text(json.dumps(pkg))
        r = subprocess.run([sys.executable, str(RECIPE_CLI), "pin"], cwd=self.target,
                           env={**self.env, **(env or {})}, capture_output=True, text=True)
        tried = self.calls.read_text().split("\n")[:-1] if self.calls.exists() else []
        return r.returncode, json.loads(r.stdout), [next(w for w in c.split() if w.startswith(("playwright@", "--no-install")))
                                 for c in tried]

    def test_finds_the_newest_release_whose_browser_is_installed_and_tries_no_older(self):
        code, o, tried = self.pin("^1.9.0", {"FAKE_LOCAL_REV": "1"})  # a range is not a pin
        self.assertEqual((code, o), (0, {"ok": True, "version": "1.9.0", "pinned": False}), o)
        self.assertEqual(tried, ["playwright@2.0.0", "playwright@1.10.0", "playwright@1.9.0"])

    def test_an_exact_pin_whose_browser_is_installed_is_left_alone(self):
        code, o, tried = self.pin("1.9.0", {"FAKE_LOCAL_REV": "1"})
        self.assertEqual((code, o), (0, {"ok": True, "version": "1.9.0", "pinned": True}), o)
        self.assertEqual(tried, ["--no-install"])

    def test_refuses_when_no_release_matches_an_installed_browser(self):
        (self.browser / "INSTALLATION_COMPLETE").unlink()
        code, o, tried = self.pin()
        self.assertEqual(code, 1, o)
        self.assertIn("npx playwright install chromium", o["refused"])
        self.assertEqual(tried, ["playwright@2.0.0"])  # nothing installed: stop at once

    def test_npm_failing_refuses_with_its_error_not_an_install_advice(self):
        self.fake("npm", """echo '{"error": {"code": "ENOTFOUND", "summary": "offline"}}'; exit 1""")
        code, o, tried = self.pin()
        self.assertEqual(code, 1, o)
        self.assertIn("npm view @playwright/test failed", o["refused"])
        self.assertIn("offline", o["refused"])
        self.assertNotIn("install chromium", o["refused"])
        self.assertEqual(tried, [])

    def test_says_only_pre_releases_match_when_the_browser_is_newer_than_every_release(self):
        self.fake("npm", """echo '["1.8.0", "2.1.0-alpha-1"]'""")  # 1.8.0 has revision 0, below 1
        code, o, tried = self.pin()
        self.assertEqual(code, 1, o)
        self.assertIn("only pre-releases match", o["refused"])
        self.assertEqual(tried, ["playwright@1.8.0"])


if __name__ == "__main__":
    unittest.main()
