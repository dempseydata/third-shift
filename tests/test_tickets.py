"""admit, step and done (#22), driven through the state script's command line (ADR 0007)."""
import json
import unittest

from tests.test_shift import LEDGER, REPO, SLUG, Target

BRANCH = f"third-shift/{SLUG}"


class Tickets(Target):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.arm()[0], 0)
        self.issue_body(21, "## What to build\n\nIt.\n\n## Acceptance criteria\n\n- [ ] It runs\n")

    def issue_body(self, n, body):
        f = self.gh / "fixture.json"
        fixture = json.loads(f.read_text())
        fixture["api"][f"repos/{REPO}/issues/{n}"] = {"number": n, "body": body}
        f.write_text(json.dumps(fixture))

    def snapshot(self):
        return ((self.target / LEDGER).read_text(), self.git("rev-parse", "HEAD"),
                self.git("rev-parse", BRANCH, cwd=self.remote), self.git("status", "--porcelain"))

    def assert_ledger_commit(self, message):
        self.assertEqual(self.git("log", "-1", "--format=%s"), message)
        files = self.git("show", "--name-only", "--format=", "HEAD").splitlines()
        self.assertIn(str(LEDGER), files)
        self.assertLessEqual(set(files), {str(LEDGER), str(LEDGER.with_suffix(".md"))})
        self.assertEqual(self.git("rev-parse", "HEAD"),
                         self.git("rev-parse", BRANCH, cwd=self.remote))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def state(self, n):
        return self.ledger()["tickets"][str(n)]

    def admit(self, n=21, gen="1"):
        return self.shift("admit", str(n), "--gen", gen)

    def evidence(self, name="verify/evidence/21.txt"):
        (self.target / name).parent.mkdir(parents=True, exist_ok=True)
        (self.target / name).write_text("passed\n")
        self.git("add", name)
        self.git("commit", "-qm", "#21: First")
        return f"https://github.com/{REPO}/blob/{self.git('rev-parse', 'HEAD')}/{name}"

    def done(self, rows, n=21, gen="1", cwd=None):
        (self.tmp / "verdicts.json").write_text(json.dumps(rows))
        return self.shift("done", str(n), "--comment", str(self.tmp / "verdicts.json"), "--gen", gen,
                          cwd=cwd)

    # admit

    def test_admit_moves_a_ready_ticket_to_in_progress(self):
        code, out = self.admit()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["state"], "In progress")
        self.assertEqual(self.state(21)["state"], "In progress")
        self.assert_ledger_commit("ledger: #21 admitted")

    def test_admit_sends_a_ticket_whose_criteria_changed_to_needs_you(self):
        self.issue_body(21, "## Acceptance criteria\n\n- [ ] It runs fast\n")
        code, out = self.admit()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["state"], "Needs you")
        self.assertEqual(self.state(21)["reason"], "blocker")
        self.assertIn("criteria changed", self.state(21)["why"])
        self.assert_ledger_commit("ledger: #21 needs you")

    def test_admit_reads_checked_boxes_and_crlf_bodies_as_the_same_criteria(self):
        self.issue_body(21, "## Acceptance criteria\r\n\r\n- [x] It runs\r\n\r\n## Notes\r\n- [ ] not one\r\n")
        self.assertEqual(self.admit()[1]["state"], "In progress")

    def test_admit_refuses_every_ticket_not_ready_and_writes_nothing(self):
        before = self.snapshot()
        for n in (22, 23, 24, 99):  # Backlog, Needs you, Done, not in the shift
            code, out = self.admit(n)
            self.assertEqual(code, 1, (n, out))
            self.assertEqual(self.snapshot(), before)

    def test_admit_refuses_a_second_ticket_while_one_is_in_progress(self):
        self.admit()
        self.issue_body(25, "## Acceptance criteria\n\n- [ ] Looks right\n")
        before = self.snapshot()
        code, out = self.admit(25)
        self.assertEqual(code, 1, out)
        self.assertIn("#21", out["refused"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.admit()[0], 1)  # nor twice

    def test_a_stale_gen_is_refused_with_stop_and_writes_nothing(self):
        before = self.snapshot()
        code, out = self.admit(gen="0")
        self.assertEqual(code, 2, out)
        self.assertTrue(out["stop"])
        self.assertEqual(self.snapshot(), before)

    def test_admit_needs_a_gen(self):
        self.assertEqual(self.shift("admit", "21")[0], 1)

    def test_a_failed_push_leaves_the_ledger_as_it_was_and_admit_can_run_again(self):
        (self.target / "work").write_text("staged work")
        self.git("add", "work")
        before = self.snapshot()
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.assertEqual(self.admit()[0], 1)
        self.assertEqual(self.snapshot(), before)
        hook.unlink()
        self.assertEqual(self.admit()[0], 0)
        self.assertEqual(self.git("status", "--porcelain"), "A  work")

    # step

    STEP = ("--role", "implementer", "--round", "1", "--model", "opus", "--effort", "high",
            "--before-5h", "40", "--before-weekly", "12", "--after-5h", "47", "--after-weekly", "13",
            "--start", "2026-11-20T01:00:00+00:00", "--end", "2026-11-20T01:20:00+00:00",
            "--tokens", "81234", "--outcome", "built")

    def step(self, *args, n=21, gen="1"):
        return self.shift("step", str(n), "--gen", gen, *(args or self.STEP))

    def test_step_writes_one_record_per_spawn(self):
        self.admit()
        code, out = self.step()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ledger()["steps"], [{
            "ticket": 21, "role": "implementer", "round": 1, "model": "opus", "effort": "high",
            "before": {"5h": 40, "weekly": 12}, "after": {"5h": 47, "weekly": 13},
            "start": "2026-11-20T01:00:00+00:00", "end": "2026-11-20T01:20:00+00:00",
            "tokens": 81234, "outcome": "built"}])
        self.assert_ledger_commit("ledger: #21 step")
        self.assertEqual(self.step()[0], 0)
        self.assertEqual(len(self.ledger()["steps"]), 2)

    def test_step_refuses_a_ticket_not_in_progress_and_bad_fields(self):
        before = self.snapshot()
        for n in (21, 22, 23, 24):  # Ready, Backlog, Needs you, Done
            self.assertEqual(self.step(n=n)[0], 1, n)
            self.assertEqual(self.snapshot(), before)
        self.admit()
        before = self.snapshot()
        bad = {"--role": "orchestrator", "--before-5h": "101", "--tokens": "-1",
               "--start": "last night", "--round": "0"}
        for flag, value in bad.items():
            args = list(self.STEP)
            args[args.index(flag) + 1] = value
            code, out = self.step(*args)
            self.assertEqual(code, 1, (flag, out))
            self.assertEqual(self.snapshot(), before)

    def test_step_refuses_an_end_before_its_start(self):
        self.admit()
        before = self.snapshot()
        args = list(self.STEP)
        args[args.index("--end") + 1] = "2026-11-20T00:59:00+00:00"
        self.assertEqual(self.step(*args)[0], 1)
        self.assertEqual(self.snapshot(), before)

    # done

    def test_done_closes_a_ticket_with_evidence_for_every_criterion(self):
        self.admit()
        url = self.evidence()
        code, out = self.done([{"criterion": "It runs", "verdict": "met", "evidence_url": url}])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["state"], "Done")
        self.assertIn(f"| It runs | met | [evidence]({url}) |", out["comment"])
        self.assertEqual(self.state(21)["state"], "Done")
        self.assertEqual(self.state(21)["verdicts"][0]["evidence_url"], url)
        self.assert_ledger_commit("ledger: #21 done")

    def test_a_needs_your_run_verdict_sends_the_ticket_to_needs_you(self):
        self.admit()
        url = self.evidence()
        code, out = self.done([{"criterion": "It runs", "verdict": "needs your run",
                                "evidence_url": url}])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["state"], "Needs you")
        self.assertEqual(self.state(21)["reason"], "human-verify")
        self.assertIn("It runs", self.state(21)["why"])
        self.assert_ledger_commit("ledger: #21 needs you")

    def test_done_refuses_without_a_verdict_and_pinned_evidence_for_every_criterion(self):
        self.admit()
        url = self.evidence()
        row = {"criterion": "It runs", "verdict": "met", "evidence_url": url}
        sha = url.split("/")[6]
        cases = {
            "no rows": [],
            "unknown criterion": [{**row, "criterion": "It walks"}],
            "twice": [row, row],
            "no verdict": [{**row, "verdict": ""}],
            "made-up verdict": [{**row, "verdict": "probably"}],
            "not met": [{**row, "verdict": "not met"}],
            "no evidence": [{**row, "evidence_url": ""}],
            "branch link": [{**row, "evidence_url": url.replace(sha, "main")}],
            "other repo": [{**row, "evidence_url": url.replace(REPO, "acme/other")}],
            "missing file": [{**row, "evidence_url": url.replace("21.txt", "22.txt")}],
            "unknown commit": [{**row, "evidence_url": url.replace(sha, "f" * 40)}],
            "trailing junk": [{**row, "evidence_url": url + " junk"}],
            "trailing newline": [{**row, "evidence_url": url + "\n"}],
            "query": [{**row, "evidence_url": url + "?x=1"}],
            "bad anchor": [{**row, "evidence_url": url + "#top"}],
            "line zero": [{**row, "evidence_url": url + "#L0"}],
            "the ledger": [{**row, "evidence_url": url.replace("verify/evidence/21.txt", str(LEDGER))}],
            "the ledger page": [{**row, "evidence_url": url.replace(
                "verify/evidence/21.txt", str(LEDGER.with_suffix(".md")))}],
            "a folder": [{**row, "evidence_url": url.rsplit("/", 1)[0]}],
            "unpushed commit": [{**row, "evidence_url": self.side_commit()}],
            "not a list": {"It runs": "met"},
        }
        before = self.snapshot()
        for why, rows in cases.items():
            code, out = self.done(rows)
            self.assertEqual(code, 1, (why, out))
            self.assertEqual(self.snapshot(), before, why)

    def test_done_from_a_subfolder_refuses_a_path_that_git_would_resolve_against_it(self):
        self.admit()
        url = self.evidence()
        sub = self.target / "verify" / "evidence"
        before = self.snapshot()
        for why, path in {"./": "./21.txt", "../": "../evidence/21.txt",
                          "//": "verify//evidence/21.txt"}.items():
            bad = url.replace("verify/evidence/21.txt", path)
            code, out = self.done([{"criterion": "It runs", "verdict": "met", "evidence_url": bad}],
                                  cwd=sub)
            self.assertEqual(code, 1, (why, out))
            self.assertEqual(self.snapshot(), before, why)
        code, out = self.done([{"criterion": "It runs", "verdict": "met", "evidence_url": url}],
                              cwd=sub)
        self.assertEqual(code, 0, out)

    def side_commit(self):
        """A pinned link to a commit on a branch the shift branch does not contain."""
        self.git("checkout", "-q", "-b", "side")
        url = self.evidence("verify/evidence/side.txt")
        self.git("checkout", "-q", BRANCH)
        return url

    def test_done_accepts_a_line_anchor_on_the_evidence_link(self):
        self.admit()
        url = self.evidence() + "#L1-L2"
        code, out = self.done([{"criterion": "It runs", "verdict": "met", "evidence_url": url}])
        self.assertEqual(code, 0, out)

    def test_done_refuses_a_ticket_not_in_progress(self):
        url = self.evidence()
        before = self.snapshot()
        for n in (21, 22, 23, 24):  # Ready, Backlog, Needs you, Done
            code, out = self.done([{"criterion": "It runs", "verdict": "met",
                                    "evidence_url": url}], n=n)
            self.assertEqual(code, 1, (n, out))
            self.assertEqual(self.snapshot(), before)

    # the owed item from #21's review

    def test_next_off_the_branch_without_a_ledger_names_the_branch(self):
        self.git("checkout", "-q", "main")
        code, out = self.shift("next", "--gen", "1")
        self.assertEqual(code, 1)
        self.assertIn(f"not on the shift branch {BRANCH}", out["refused"])


class NoCriteria(Target):
    issue_body, snapshot, admit, done = (Tickets.issue_body, Tickets.snapshot, Tickets.admit,
                                         Tickets.done)

    def test_done_refuses_a_ticket_with_no_frozen_criteria(self):
        self.prescan["tickets"][0]["criteria"] = []
        self.assertEqual(self.arm()[0], 0)
        self.issue_body(21, "## What to build\n\nIt.\n")
        self.assertEqual(self.admit()[0], 0)
        before = self.snapshot()
        code, out = self.done([])
        self.assertEqual(code, 1, out)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
