"""The prescan's ticket half (#30), driven through `cli/prescan`'s command line (ADR 0007)."""
import json
import os
import subprocess
import sys
import unittest

from tests.test_shift import LEDGER, REPO, ROOT, SLUG, Target

PRESCAN = ROOT / "cli" / "prescan"
CRITERIA = "## Acceptance criteria\n\n- [ ] It runs\n"
RULES = json.loads((ROOT / "cli" / "rules.json").read_text())
RECIPE = "# Verify recipe\n\n## Launch\n\nStart it.\n"


def ticket(n, labels=("ready-for-agent",), body=CRITERIA, state="open"):
    return {"number": n, "title": f"Ticket {n}", "state": state, "body": body,
            "labels": [{"name": l} for l in labels]}


class PrescanTarget(Target):
    """A target that passes every environment check (#31), the machine faked: HOME, and `uv`,
    `pmset` and `npx` first on PATH; no tests."""
    fixture = "prescan"

    def prepare(self):  # a proven recipe: committed, then its Proven section names that commit
        checks = self.target / "verify" / "checks"
        checks.parent.mkdir()
        checks.write_text('#!/bin/sh\nsleep "${FAKE_CHECKS_SLEEP:-0}"\nexit "${FAKE_CHECKS_EXIT:-0}"\n')
        checks.chmod(0o755)
        (self.target / "verify" / "recipe.md").write_text(RECIPE)
        (self.target / "playwright.config.ts").write_text("export default {}\n")
        self.git("add", ".")
        self.git("commit", "-qm", "recipe")
        proven = self.git("rev-parse", "HEAD")
        (self.target / "verify" / "recipe.md").write_text(f"{RECIPE}\n## Proven\n\n{proven}: passed, failed on a break\n")
        self.git("commit", "-qam", "proven")
        self.git("push", "-q", "origin", "HEAD:main")

    def setUp(self):
        super().setUp()
        self.user = self.tmp / "user"
        self.settings = {"permissions": {"allow": RULES["allow"], "deny": RULES["deny"]},
                         "enabledPlugins": {"third-shift@third-shift": True}, "model": "opus"}
        self.browser = self.tmp / "ms-playwright" / "chromium-1"
        self.browser.mkdir(parents=True)
        (self.browser / "INSTALLATION_COMPLETE").touch()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.fake("uv", "echo uv 0.0.0")
        self.fake("pmset", "echo \"Now drawing from 'AC Power'\"")
        self.fake("npx", f"echo 'browser: chromium version 1'\necho '  Install location:    {self.browser}'")
        self.gh_extra = {"auth": {"hosts": {"github.com": [
                             {"state": "success", "active": True, "scopes": "project, repo"}]}},
                         "graphql": {"Board": {"repository": {"id": "R", "owner": {"id": "O", "projectsV2": {
                             "nodes": [{"title": "third-shift: widget"}]}}}}}}
        env = {k: v for k, v in self.env.items() if k != "CLAUDE_CONFIG_DIR"}
        self.env = {**env, "HOME": str(self.user),
                    "PATH": os.pathsep.join([str(self.bin), env["PATH"]])}

    def fake(self, name, script):
        f = self.bin / name
        f.write_text(f"#!/bin/sh\n{script}\n")
        f.chmod(0o755)

    def tickets(self, *issues, blocked_by=None):
        """The spec #20 on the fake tracker with these sub-issues and native links."""
        api = {f"repos/{REPO}/issues/20": {"number": 20, "title": "Widget version 1"},
               f"repos/{REPO}/issues/20/sub_issues":
               [{"number": i["number"], "title": i["title"], "state": i["state"]} for i in issues]}
        for i in issues:
            api[f"repos/{REPO}/issues/{i['number']}"] = i
            api[f"repos/{REPO}/issues/{i['number']}/dependencies/blocked_by"] = [
                {"number": b, "state": "open"} for b in (blocked_by or {}).get(i["number"], [])]
        (self.gh / "fixture.json").write_text(json.dumps({"repo": REPO, "api": api, **self.gh_extra}))

    def run_prescan(self, env=None):
        settings = self.user / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(self.settings))
        out = self.tmp / "out" / "prescan.json"
        out.parent.mkdir(exist_ok=True)
        p = subprocess.run([sys.executable, str(PRESCAN), "--spec", "20", "--out", str(out)],
                           cwd=self.target, env=env or self.env, capture_output=True, text=True)
        written = json.loads(out.read_text()) if out.exists() else None
        return p.returncode, json.loads(p.stdout), written

    def questions(self, *issues, blocked_by=None):
        self.tickets(*issues, blocked_by=blocked_by)
        code, out, written = self.run_prescan()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["questions"], written["questions"])
        return written


class Prescan(PrescanTarget):
    fixture = "prescan"

    def test_writes_the_ticket_set_and_nothing_else(self):
        main = self.git("rev-parse", "HEAD")
        (self.target / "local").write_text("x")  # HEAD ahead of the default branch
        self.git("add", ".")
        self.git("commit", "-qm", "local")
        self.tickets(ticket(21), ticket(22, body="## Blocked by\n\n- #21\n\n" + CRITERIA),
                     ticket(23, ["ready-for-human"]), ticket(24, state="closed"),
                     blocked_by={22: [21]})
        code, out, p = self.run_prescan()
        self.assertEqual(code, 0, out)
        self.assertTrue(out["ok"])
        self.assertEqual(p["spec"], {"number": 20, "title": "Widget version 1"})
        self.assertEqual(p["repo"], REPO)
        self.assertEqual(p["base_commit"], main)  # the default branch's, not HEAD's
        self.assertEqual([(t["number"], t["state"], t["labels"], t["blocked_by"], t["criteria"])
                          for t in p["tickets"]],
                         [(21, "open", ["ready-for-agent"], [], ["It runs"]),
                          (22, "open", ["ready-for-agent"], [21], ["It runs"]),
                          (23, "open", ["ready-for-human"], [], ["It runs"]),
                          (24, "closed", ["ready-for-agent"], [], ["It runs"])])
        self.assertEqual(p["questions"], [])
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.writes(), [])
        self.assertFalse(self.home.exists())
        self.assertEqual([f.name for f in (self.tmp / "out").iterdir()], ["prescan.json"])

    def test_writes_no_bytecode_into_the_plugin_or_target(self):
        def tree(root):
            return {p for p in root.rglob("*") if ".git" not in p.relative_to(root).parts}
        self.tickets(ticket(21))
        env = {k: v for k, v in self.env.items() if k != "PYTHONDONTWRITEBYTECODE"}
        before = tree(ROOT), tree(self.target)
        code, out, _ = self.run_prescan(env)
        self.assertEqual(code, 0, out)
        self.assertFalse((ROOT / "cli" / "__pycache__").exists())
        self.assertEqual((tree(ROOT), tree(self.target)), before)

    def test_refuses_a_spec_with_no_sub_issues(self):
        self.tickets()
        code, out, written = self.run_prescan()
        self.assertEqual(code, 1)
        self.assertFalse(out["ok"])
        self.assertIsNone(written)

    def test_a_ticket_without_one_triage_label_is_a_question(self):
        p = self.questions(ticket(21), ticket(22, ["needs-triage"]), ticket(23, []),
                           ticket(24, ["ready-for-agent", "ready-for-human"]))
        self.assertEqual([q.split(":")[0] for q in p["questions"]], ["#22", "#23", "#24"])

    def test_a_body_blocker_without_a_native_link_is_a_question_not_an_edge(self):
        p = self.questions(ticket(21), ticket(22, body="## Blocked by\n\n- #21\n- "
                                              f"https://github.com/{REPO}/issues/23\n\n" + CRITERIA),
                           ticket(23), blocked_by={22: [23]})
        self.assertEqual(p["tickets"][1]["blocked_by"], [23])
        self.assertEqual(len(p["questions"]), 1)
        self.assertIn("#22", p["questions"][0])
        self.assertIn("#21", p["questions"][0])

    def test_every_blocker_in_the_section_is_read_past_a_bare_number(self):
        p = self.questions(ticket(21), ticket(23), ticket(22, body="## Blocked by\n\n#21\n- #23\n\n" + CRITERIA))
        self.assertEqual(len(p["questions"]), 1)
        self.assertIn("#21, #23", p["questions"][0])

    def test_a_cycle_in_the_edges_is_a_question(self):
        p = self.questions(ticket(21), ticket(22), ticket(23), ticket(24),
                           blocked_by={21: [23], 22: [21], 23: [22], 24: [23]})
        self.assertEqual(len(p["questions"]), 1)
        self.assertIn("#21, #22, #23", p["questions"][0])
        self.assertNotIn("#24", p["questions"][0])  # downstream of the cycle, not in it

    def test_each_checkbox_is_extracted_and_none_is_a_question(self):
        p = self.questions(
            ticket(21, body="## Acceptance criteria\r\n\r\n- [x] One\r\n* [ ] Two \r\n\r\n## Notes\n- [ ] No"),
            ticket(22, body="## What to build\n\n- [ ] Not a criterion\n"))
        self.assertEqual(p["tickets"][0]["criteria"], ["One", "Two"])
        self.assertEqual(p["tickets"][1]["criteria"], [])
        self.assertEqual([q.split(":")[0] for q in p["questions"]], ["#22"])

    def test_a_blank_checkbox_is_no_criterion(self):
        p = self.questions(ticket(21, body="## Acceptance criteria\n\n- [ ]   \n- [ ] Real\n"),
                           ticket(22, body="## Acceptance criteria\n\n- [ ] \t\n"))
        self.assertEqual([t["criteria"] for t in p["tickets"]], [["Real"], []])
        self.assertEqual([q.split(":")[0] for q in p["questions"]], ["#22"])

    def test_plus_and_numbered_checkboxes_are_criteria(self):
        p = self.questions(ticket(21, body="## Acceptance criteria\n\n+ [ ] One\n1. [x] Two\n2) [ ] Three\n"))
        self.assertEqual(p["tickets"][0]["criteria"], ["One", "Two", "Three"])

    def test_refuses_while_an_unmerged_shift_branch_exists(self):
        self.tickets(ticket(21))
        self.git("checkout", "-q", "-b", f"third-shift/{SLUG}")
        (self.target / "work").write_text("x")
        self.git("add", ".")
        self.git("commit", "-qm", "work")
        self.git("push", "-q", "origin", f"third-shift/{SLUG}")
        self.git("checkout", "-q", "main")
        self.git("branch", "-q", "-D", f"third-shift/{SLUG}")  # the remote's alone still blocks
        code, out, written = self.run_prescan()
        self.assertEqual(code, 1, out)
        self.assertIn(f"third-shift/{SLUG}", out["refused"])
        self.assertIsNone(written)
        self.git("push", "-q", "origin", f"origin/third-shift/{SLUG}:main")  # merged: no block
        self.assertEqual(self.run_prescan()[0], 0)

    def test_its_output_arms_the_shift(self):
        self.tickets(ticket(21), ticket(22), ticket(23, ["ready-for-human"]),
                     ticket(24, state="closed"), blocked_by={22: [21]})
        code, out, p = self.run_prescan()
        self.assertEqual(code, 0, out)
        self.prescan = p
        self.sitting["classes"] = {}
        code, out = self.arm()
        self.assertEqual(code, 0, out)
        o = json.loads((self.target / LEDGER).read_text())["opening"]
        self.assertEqual(o["base_commit"], p["base_commit"])
        self.assertEqual([(t["number"], t["class"], t["starting_state"], t["criteria"])
                          for t in o["tickets"]],
                         [(21, "agent", "Ready", ["It runs"]), (22, "agent", "Backlog", ["It runs"]),
                          (23, "human", "Needs you", ["It runs"]), (24, "agent", "Done", ["It runs"])])


if __name__ == "__main__":
    unittest.main()
