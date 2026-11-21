"""What the shift loop (#37) needs of the state script: a running step lets the session stop,
`wait` blocks only on the frontier, a mid-shift ceiling, and blockers and stalls set work aside."""
import json
import unittest

from tests.test_lifecycle import Working
from tests.test_stop import Stopping


class RunningStep(Stopping):
    """21 In progress, 22 Backlog behind it, 23 Needs you, 24 Done, 25 Ready."""
    fixture = "admitted"

    def begin(self, role="reviewer"):
        code, out = self.shift("step", "21", "--begin", "--gen", "1", "--role", role,
                               *self.readings())
        self.assertEqual((code, out["gate"]), (0, "proceed"), out)

    def test_a_running_step_allows_the_stop_and_never_counts_toward_a_stall(self):
        self.beat(0)
        self.begin("implementer")
        self.assertEqual(self.runtime()["step"]["role"], "implementer")
        for _ in range(4):
            self.assertEqual(self.stop(), {})
        self.assertEqual(self.state(21)["state"], "In progress")
        self.assertNotIn("stops", self.runtime())
        self.assertEqual(self.step()[0], 0)  # the matching record ends the step
        self.assertNotIn("step", self.runtime())
        self.blocked()

    def test_admit_starts_the_implementer_step_so_a_backgrounded_implementer_never_stalls(self):
        self.beat(0)
        self.assertEqual(self.needs_you()[0], 0)
        self.issue_body(25, "## Acceptance criteria\n\n- [ ] Looks right\n")
        code, out = self.admit(25)
        self.assertEqual((code, out.get("state")), (0, "In progress"), out)
        self.assertEqual((self.runtime()["step"]["ticket"], self.runtime()["step"]["role"]),
                         (25, "implementer"))
        for _ in range(3):
            self.assertEqual(self.stop(), {})
        self.assertEqual(self.state(25)["state"], "In progress")

    def test_leaving_a_ticket_ends_its_running_step(self):
        self.beat(0)
        self.begin()
        self.assertEqual(self.shift("stall", "21", "--gen", "1", "--why", "x")[0], 0)
        self.assertNotIn("step", self.runtime())
        self.blocked()  # 25 is Ready, so the stop is blocked again


class Frontier(Working):
    """Only 21 In progress, 22 Backlog behind it, 23 Needs you (human) and 24 Done."""
    def prepare(self):
        self.prescan["tickets"] = [t for t in self.prescan["tickets"]
                                   if t["number"] in (21, 22, 23, 24)]
        super().prepare()

    def test_wait_is_not_blocked_by_backlog_behind_a_needs_you_ticket(self):
        self.assertEqual(self.needs_you()[0], 0)
        code, out = self.shift("wait", "--gen", "1")
        self.assertEqual((code, out["shift_state"]), (0, "waiting"), out)

    def test_needs_you_and_stall_set_uncommitted_work_aside_on_a_named_ref(self):
        (self.target / "README.md").write_text("half-edited\n")
        (self.target / "new.txt").write_text("untracked\n")
        code, out = self.needs_you()
        self.assertEqual(code, 0, out)
        ref = out["set_aside"][0]
        self.assertEqual(self.state(21)["set_aside"], [ref])
        self.assertEqual(self.git("show", f"{ref}:new.txt"), "untracked")
        self.assertEqual(self.git("rev-parse", ref), self.git("rev-parse", ref, cwd=self.remote))
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.release(21, "--decision", "go")[0], 0)
        self.assertEqual(self.admit()[0], 0)
        (self.target / "new.txt").write_text("again\n")
        code, out = self.shift("stall", "21", "--gen", "1", "--why", "x")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out["set_aside"]), 2)
        self.assertEqual(self.git("show", f"{out['set_aside'][1]}:new.txt"), "again")
        self.assertEqual(self.git("status", "--porcelain"), "")


class DoneOnStdin(Working):
    fixture = "admitted"

    def test_done_reads_the_verdicts_on_stdin_with_a_dash(self):
        url = self.evidence()
        rows = [{"criterion": "It runs", "verdict": "met", "evidence_url": url}]
        code, out = self.shift("done", "21", "--gen", "1", "--comment", "-", input=json.dumps(rows))
        self.assertEqual((code, out.get("state")), (0, "Done"), out)

    def test_done_takes_the_verdicts_inline_as_one_argument(self):
        rows = [{"criterion": "It runs", "verdict": "met", "evidence_url": self.evidence()}]
        code, out = self.shift("done", "21", "--gen", "1", "--comment", json.dumps(rows))
        self.assertEqual((code, out.get("state")), (0, "Done"), out)

    def test_done_refuses_empty_invalid_or_truncated_verdicts_and_writes_nothing(self):
        cut = json.dumps([{"criterion": "It runs", "verdict": "met"}])[:-3]
        self.assert_refused_unchanged([("done", "21", "--gen", "1", "--comment", v)
                                       for v in ("-", "[not json]", cut)])


class Ceiling(Working):
    fixture = "admitted"

    def test_ceiling_raises_or_waives_the_weekly_ceiling_mid_shift(self):
        code, out = self.shift("ceiling", "--gen", "1", "90")
        self.assertEqual((code, out["ceiling"]), (0, 90), out)
        self.assertEqual(self.ledger()["opening"]["ceiling"], 90)
        self.assert_ledger_commit("ledger: #20 ceiling")
        code, out = self.shift("step", "21", "--begin", "--gen", "1", "--role", "reviewer",
                               *self.readings(10, 85))
        self.assertEqual(out["gate"], "proceed", out)
        self.assertEqual(self.shift("ceiling", "--gen", "1", "none")[0], 0)
        self.assertIsNone(self.ledger()["opening"]["ceiling"])
        self.assertEqual([c["ceiling"] for c in self.ledger()["ceilings"]], [90, None])

    def test_ceiling_refuses_a_bad_value_and_a_stale_gen(self):
        self.assert_refused_unchanged([("ceiling", "--gen", "1", v) for v in ("101", "-1", "x")]
                                      + [("ceiling", "--gen", "1")])
        self.assert_refused_unchanged([("ceiling", "--gen", "0", "90")], 2)



class ResumeCron(Working):
    """The loop runs no clock or converter of its own: every timestamp and the local-time cron
    for a resume come from the state script."""
    fixture = "admitted"
    NOW = "2026-07-01T03:00:00+00:00"  # summer: New York is UTC-4; the reset is in winter, UTC-5

    def test_gate_and_pause_answer_a_local_resume_cron_and_the_time(self):
        self.env.update(TZ="America/New_York", THIRD_SHIFT_NOW=self.NOW)
        begin = ("step", "21", "--begin", "--gen", "1", "--role", "reviewer")
        code, out = self.shift(*begin, *self.readings())
        self.assertEqual((code, out["gate"], out["now"]), (0, "proceed", self.NOW), out)
        args = list(self.STEP[:self.STEP.index("--start")]) + [
            "--start", out["now"], "--tokens", "1", "--outcome", "clean"]
        args[1] = "reviewer"
        code, out = self.step(*args)  # --end defaults to the script's now
        self.assertEqual((code, out["step"]["end"]), (0, self.NOW), out)
        code, out = self.shift(*begin, *self.readings(98, guess=50))
        self.assertEqual((out["gate"], out["resume_cron"]), ("pause-until", "3 0 20 11 *"), out)
        code, out = self.shift(*begin, "--unreadable", "--guess", "5")
        self.assertEqual((out["gate"], out["until"], out["resume_cron"]),
                         ("retry", "2026-07-01T03:10:00+00:00", "13 23 30 6 *"), out)
        code, out = self.shift("pause", "--gen", "1", "--reason", "usage", "--until", self.RESET)
        self.assertEqual((code, out["resume_cron"]), (0, "3 0 20 11 *"), out)


if __name__ == "__main__":
    unittest.main()
