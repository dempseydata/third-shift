"""The usage gate, pause and resume (#24), driven through the state script's command line
(ADR 0007). The gate answers at `admit` and at `step --begin` (ADR 0003)."""
import json
import unittest

from tests.test_tickets import BRANCH, Armed


class Gated(Armed):
    """Helpers, no tests."""

    def begin(self, *readings, role="implementer"):
        return self.shift("step", "21", "--begin", "--gen", "1", "--role", role,
                          *(readings or self.readings()))

    def gate(self, *readings, role="implementer"):
        code, out = self.begin(*readings, role=role)
        self.assertEqual((code, out.pop("ok"), out.pop("ticket")), (0, True, 21), out)
        return out

    def record(self, before, after, role="implementer"):
        args = list(self.STEP)
        for flag, value in (("--role", role), ("--before-5h", before), ("--after-5h", after)):
            args[args.index(flag) + 1] = str(value)
        code, out = self.step(*args)
        self.assertEqual(code, 0, out)

    def refused_admit(self, readings, gate, n=21):
        before = self.snapshot()
        code, out = self.admit(n, readings=readings)
        self.assertEqual((code, out.get("gate")), (1, gate), out)
        self.assertIn("refused", out)
        self.assertEqual(self.snapshot()[:4], before[:4])  # the ledger is untouched
        return out

    def assert_refused(self, cases):
        for args in cases:
            code, out = self.shift(*args)
            self.assertEqual(code, 1, (args, out))
            self.assertIn("refused", out)

    UNREADABLE = ("--unreadable", "--guess", "5")


class AwayGate(Gated):
    """Away mode (threshold 98), the default weekly ceiling (80), #21 In progress with six
    implementer steps costing 9, 1, 2, 1, 1 and 2 points (the last across a reset)."""
    admitted = True

    def prepare(self):
        super().prepare()
        self.issue_body(25, "## Acceptance criteria\n\n- [ ] Looks right\n")
        for before, after in ((0, 9), (10, 11), (11, 13), (13, 14), (14, 15), (95, 2)):
            self.record(before, after)

    def test_admission_is_refused_at_the_away_threshold_or_the_ceiling(self):
        self.shift("stall", "21", "--gen", "1", "--why", "x")
        out = self.refused_admit(self.readings(98, guess=1), "pause-until", n=25)
        self.assertEqual(out["until"], self.RESET)
        self.refused_admit(self.readings(10, 50, 80), "end", n=25)
        code, out = self.admit(25, readings=self.readings(97, guess=50))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["estimate"], {"points": 2, "guess": False})
        self.assertEqual(self.state(25)["state"], "In progress")

    def test_the_look_ahead_takes_the_largest_of_the_roles_last_5_step_costs(self):
        estimate = {"points": 2, "guess": False}  # the 9-point step is the sixth back
        self.assertEqual(self.gate(*self.readings(97, guess=50)),
                         {"gate": "proceed", "estimate": estimate})
        self.assertEqual(self.gate(*self.readings(98, guess=50)), {
            "gate": "pause-until", "until": self.RESET, "estimate": estimate,
            "reason": "5-hour usage 98% plus a implementer step of 2 reaches 100%"})
        # a role with no steps yet uses its starting figure, marked as a guess
        self.assertEqual(self.gate(*self.readings(97, guess=2), role="reviewer"),
                         {"gate": "proceed", "estimate": {"points": 2, "guess": True}})
        self.assertEqual(self.gate(*self.readings(97, guess=3), role="reviewer")["gate"],
                         "pause-until")
        # away threshold 98 plus the reserve 5 would be 103: the pause point stays below 100
        self.assertEqual(self.gate(*self.readings(98, guess=0), role="reviewer")["gate"], "proceed")
        self.assertEqual(self.gate(*self.readings(99, guess=0), role="reviewer")["gate"],
                         "pause-until")

    def test_per_ticket_usage_is_the_difference_between_readings_in_whole_points(self):
        steps = self.ledger()["steps"]
        self.assertEqual([s["points"] for s in steps], [9, 1, 2, 1, 1, 2])
        self.assertEqual([s.get("lower_bound") for s in steps], [None] * 5 + [True])
        self.assertEqual(self.state(21)["usage"], 16)

    def test_unreadable_usage_retries_in_10_minutes_and_ends_the_shift_the_third_time(self):
        for expected in ("retry", "retry", "proceed", "retry", "retry", "end"):
            out = self.gate(*(() if expected == "proceed" else self.UNREADABLE))
            self.assertEqual(out["gate"], expected, out)  # a reading starts the count again
            if expected == "retry":
                self.assertEqual(out["retry_in_minutes"], 10)

    def test_the_weekly_ceiling_is_checked_against_the_highest_weekly_window(self):
        self.assertEqual(self.gate(*self.readings(10, 79, 50))["gate"], "proceed")
        out = self.gate(*self.readings(10, 50, 80))
        self.assertEqual(out["gate"], "end")
        self.assertIn("ceiling", out["reason"])

    def test_the_gate_refuses_incomplete_readings_and_writes_nothing(self):
        before = self.snapshot()
        r = self.readings()
        go = ("step", "21", "--begin", "--gen", "1", "--role", "fixer")
        self.assert_refused([
            (*go, *r[2:]),                       # no 5-hour reading
            (*go, *r[:2], *r[4:]),               # no reset time
            (*go, *r[:4], *r[6:]),               # no weekly reading
            (*go, *r[:-2]),                      # no starting figure
            (*go, "--unreadable", *r),           # unreadable and read at once
            (*go, *self.readings(101)),
            (*go, "--5h", "10", "--reset", "2026-11-20T05:00:00", *r[4:]),  # no timezone
            ("step", "22", "--begin", "--gen", "1", "--role", "fixer", *r),  # not in progress
            ("step", "21", "--gen", "1", "--role", "fixer", *r),  # a record, not --begin
        ])
        self.assertEqual(self.snapshot(), before)
        code, out = self.shift(*go[:4], "0", *go[5:], *r)
        self.assertEqual((code, out["stop"]), (2, True))

    def test_pause_and_resume_move_the_shift_and_record_the_reset_time(self):
        before = self.snapshot()
        self.assert_refused([
            ("resume", "--gen", "1"),  # running, not paused
            ("pause", "--gen", "1", "--reason", "lunch", "--until", self.RESET),
            ("pause", "--gen", "1", "--reason", "usage", "--until", "after lunch"),
            ("pause", "--gen", "1", "--reason", "usage", "--until", "2026-11-20T05:00:00"),
            ("pause", "--gen", "1", "--reason", "usage"),
        ])
        self.assertEqual(self.snapshot(), before)
        pause = ("pause", "--gen", "1", "--reason", "usage", "--until", self.RESET)
        self.assertEqual(self.shift(*pause[:2], "0", *pause[3:])[0], 2)
        code, out = self.shift(*pause)
        self.assertEqual((code, out["shift_state"]), (0, "paused"), out)
        state = self.runtime()
        self.assertEqual((state["shift_state"], state["until"]), ("paused", self.RESET))
        self.assert_ledger_commit("ledger: #20 paused")
        record = self.ledger()["pauses"][-1]
        self.assertEqual((record["reason"], record["until"]), ("usage", self.RESET))
        self.assertIn("at", record)
        before = self.snapshot()
        self.assert_refused([pause])  # already paused
        self.assertEqual(self.snapshot(), before)
        # while paused the gate answers the stored reset time (unreadable usage gives none)
        out = self.gate(*self.UNREADABLE)
        self.assertEqual((out["gate"], out["until"]), ("pause-until", self.RESET), out)
        self.shift("stall", "21", "--gen", "1", "--why", "x")
        self.assertEqual(self.refused_admit(self.UNREADABLE, "pause-until", n=25)["until"],
                         self.RESET)
        code, out = self.shift("resume", "--gen", "1")
        self.assertEqual((code, out["shift_state"]), (0, "running"), out)
        self.assertEqual(self.runtime()["shift_state"], "running")
        self.assertNotIn("until", self.runtime())
        self.assertIn("resumed", self.ledger()["pauses"][-1])
        self.assert_ledger_commit("ledger: #20 resumed")


class DayFastForward(Gated):
    """Day mode (threshold 90) with the weekly ceiling waived, and fast-forward as the end
    state chosen at the sitting; #21 Ready. One fixture for both, to save a build."""

    def prepare(self):
        self.sitting["end_state"] = "fast-forward"
        self.arm = lambda *extra, arm=self.arm: arm("--mode", "day", "--ceiling", "none", *extra)
        super().prepare()

    def test_the_day_threshold_the_reserve_and_a_waived_ceiling(self):
        self.refused_admit(self.readings(90, guess=1), "pause-until")
        self.refused_admit(self.UNREADABLE, "retry")
        self.refused_admit(self.readings(89, guess=11), "pause-until")  # 89 + 11 reaches 100
        self.assert_refused([("admit", "21", "--gen", "1")])  # no readings
        code, out = self.admit(readings=self.readings(89, 100, guess=10))
        self.assertEqual((code, out["estimate"]), (0, {"points": 10, "guess": True}), out)
        self.assertEqual(self.gate(*self.readings(94, 100, guess=1))["gate"], "proceed")
        out = self.gate(*self.readings(95, guess=1))  # threshold + 5
        self.assertEqual((out["gate"], out["until"]), ("pause-until", self.RESET))

    # end with the fast-forward end state (#23)

    def test_end_fast_forwards_the_default_branch_and_pushes(self):
        code, out = self.shift("end", "--gen", "1", "--reason", "frontier empty")
        self.assertEqual((code, out["end_state"]), (0, "fast-forward"), out)
        self.assertEqual(self.git("log", "-1", "--format=%s", "main", cwd=self.remote),
                         "ledger: #20 ended")
        self.assertEqual(self.git("rev-parse", "main", cwd=self.remote),
                         self.git("rev-parse", BRANCH, cwd=self.remote))

    def test_end_killed_at_the_push_completes_when_run_again(self):
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\np=$PPID\nwhile [ \"$p\" -gt 1 ]; do\n"  # kill the script
                        "  case \"$(ps -o command= -p $p)\" in *cli/shift*) kill -9 $p; exit 1;; esac\n"
                        "  p=$(ps -o ppid= -p $p | tr -d ' ')\ndone\nexit 1\n")
        hook.chmod(0o755)
        self.assertNotEqual(self.shift("end", "--gen", "1", "--reason", "x")[0], 0)
        self.assertTrue(self.runtime()["armed"])
        hook.unlink()
        code, out = self.shift("end", "--gen", "1", "--reason", "x")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.runtime()["shift_state"], "ended")
        self.assertEqual(self.git("rev-parse", "main", cwd=self.remote),
                         self.git("rev-parse", BRANCH, cwd=self.remote))

    def test_end_refuses_when_the_default_branch_cannot_fast_forward(self):
        self.git("checkout", "-q", "main")
        (self.target / "moved").write_text("moved")
        self.git("add", "moved")
        self.git("commit", "-qm", "moved")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", BRANCH)
        before = self.snapshot()
        code, out = self.shift("end", "--gen", "1", "--reason", "x")
        self.assertEqual(code, 1, out)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
