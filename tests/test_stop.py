"""The Stop-hook gate (#26): `stop-check`, the Stop hook's entry point, fed hook-shaped stdin
and judged only by the decision it prints (ADR 0007). An empty object lets the session stop."""
import json
import subprocess
import unittest

from tests.test_revival import Clock
from tests.test_lifecycle import Working
from tests.test_shift import ROOT
from tests.test_tickets import BRANCH

BLOCK = "block"


class Stopping(Clock, Working):
    """Helpers, no tests."""

    def stop(self, session="s1", minutes=0, **hook):
        hook = {"session_id": session, "cwd": str(self.target), "hook_event_name": "Stop",
                "stop_hook_active": False, "last_assistant_message": "Done for now.", **hook}
        code, out = self.shift("stop-check", env=self.at(minutes), input=json.dumps(hook))
        self.assertEqual(code, 0, out)
        self.assertLessEqual(set(out), {"decision", "reason"})  # only the hook's own fields
        return out

    def blocked(self, **hook):
        out = self.stop(**hook)
        self.assertEqual(out.get("decision"), BLOCK, out)
        self.assertTrue(out["reason"].strip())
        return out["reason"]


class StopGate(Stopping):
    """21 In progress, 22 Backlog behind it, 23 Needs you, 24 Done, 25 Ready."""
    fixture = "admitted"

    def test_the_hook_blocks_the_stop_while_frontier_tickets_remain(self):
        reason = self.blocked()
        self.assertIn("#21", reason)

    def test_the_hook_does_nothing_unless_a_shift_is_armed_and_this_session_holds_the_lease(self):
        self.assertEqual(self.stop(session="other", cwd=str(self.tmp)), {})  # not the target
        self.beat(0)  # s1 claims the lease
        before = self.snapshot()
        for _ in range(4):
            self.assertEqual(self.stop(session="s2"), {})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.shift("end", "--gen", "1", "--reason", "x")[0], 0)
        self.assertEqual(self.stop(), {})

    def test_the_first_hook_may_be_the_stop_and_claims_the_lease(self):
        self.blocked()
        self.assertEqual(self.runtime()["session_id"], "s1")
        self.assertEqual(self.stop(session="s2"), {})

    def test_a_stop_file_allows_the_stop(self):
        self.beat(0)
        (self.home / "acme" / "widget" / "STOP").write_text("")
        self.assertEqual(self.stop(), {})

    def test_a_planned_pause_allows_the_stop(self):
        self.beat(0)
        self.assertEqual(self.shift("pause", "--gen", "1", "--reason", "usage",
                                    "--until", self.RESET)[0], 0)
        self.assertEqual(self.stop(), {})

    def test_the_weekly_ceiling_allows_the_stop(self):
        self.beat(0)
        code, out = self.shift("step", "21", "--begin", "--gen", "1", "--role", "reviewer",
                               *self.readings(10, 80))
        self.assertEqual((code, out["gate"]), (0, "end"), out)
        self.assertEqual(self.stop(), {})

    def test_three_blocked_stops_without_progress_stall_the_ticket_and_move_on(self):
        self.beat(0)
        (self.target / "README.md").write_text("half-edited\n")
        (self.target / "new.txt").write_text("untracked\n")
        self.blocked()
        self.blocked(stop_hook_active=True)
        self.assertEqual(self.state(21)["state"], "In progress")
        reason = self.blocked(stop_hook_active=True)
        self.assertIn("next --gen 1", reason)
        t = self.state(21)
        self.assertEqual(t["state"], "Stalled")
        ref = t["set_aside"][0]
        self.assertIn(ref, reason)
        self.assertEqual(self.git("show", f"{ref}:README.md"), "half-edited")
        self.assertEqual(self.git("show", f"{ref}:new.txt"), "untracked")
        self.assert_ledger_commit("ledger: #21 stalled")  # pushed, the ref with it, tree clean
        self.assertEqual(self.git("rev-parse", ref), self.git("rev-parse", ref, cwd=self.remote))
        self.assertTrue(self.runtime()["armed"])
        self.blocked()  # 25 is still Ready: the shift moves on
        self.assertEqual(self.state(25)["state"], "Ready")

    def test_progress_starts_the_count_again(self):
        self.beat(0)
        self.blocked()
        self.blocked()
        self.assertEqual(self.step()[0], 0)  # the ledger changed
        self.blocked()
        self.blocked()
        self.assertEqual(self.state(21)["state"], "In progress")
        self.blocked()
        self.assertEqual(self.state(21)["state"], "Stalled")
        self.assertNotIn("set_aside", self.state(21))  # nothing uncommitted to set aside

    def test_three_stalled_tickets_in_a_row_end_the_shift(self):
        self.beat(0)
        self.assertEqual(self.shift("stall", "21", "--gen", "1", "--why", "x")[0], 0)
        self.issue_body(25, "## Acceptance criteria\n\n- [ ] Looks right\n")
        self.assertEqual(self.admit(25)[0], 0)
        self.assertEqual(self.shift("stall", "25", "--gen", "1", "--why", "x")[0], 0)
        self.tracker({21: [], 22: [], 23: [], 25: []})
        self.assertEqual(self.shift("next", "--gen", "1")[0], 0)
        self.issue_body(22, "## Acceptance criteria\n\n- [ ] It flies\n")
        self.assertEqual(self.admit(22)[0], 0)
        self.blocked()
        self.blocked()
        reason = self.blocked()  # the third stall in a row: told once that the shift has ended
        self.assertIn("ended", reason)
        self.assertEqual(self.state(22)["state"], "Stalled")
        self.assertEqual(self.ledger()["end"]["reason"], "three stalled tickets in a row")
        self.assertEqual((self.runtime()["armed"], self.runtime()["shift_state"]), (False, "ended"))
        self.assertEqual(self.stop(), {})

    def test_three_stalled_tickets_in_a_row_end_a_waiting_shift(self):
        self.beat(0)
        self.assertEqual(self.shift("stall", "21", "--gen", "1", "--why", "x")[0], 0)
        self.issue_body(25, "## Acceptance criteria\n\n- [ ] Looks right\n")
        self.assertEqual(self.admit(25)[0], 0)
        self.assertEqual(self.shift("stall", "25", "--gen", "1", "--why", "x")[0], 0)
        self.tracker({21: [], 22: [], 23: [], 25: []})
        self.assertEqual(self.shift("next", "--gen", "1")[0], 0)
        self.issue_body(22, "## Acceptance criteria\n\n- [ ] It flies\n")
        self.assertEqual(self.admit(22)[0], 0)
        self.assertEqual(self.shift("stall", "22", "--gen", "1", "--why", "x")[0], 0)
        self.assertEqual(self.shift("wait", "--gen", "1")[0], 0)
        self.assertIn("ended", self.blocked())
        self.assertEqual(self.ledger()["end"]["reason"], "three stalled tickets in a row")
        self.assertEqual(self.stop(), {})

    def test_with_nothing_in_progress_blocked_stops_without_progress_end_in_a_stop(self):
        self.beat(0)
        self.assertEqual(self.shift("stall", "21", "--gen", "1", "--why", "x")[0], 0)
        before = self.snapshot()
        self.assertIn("#25", self.blocked())  # 25 is Ready, yet nothing picks it up
        self.blocked(stop_hook_active=True)
        self.assertEqual(self.stop(stop_hook_active=True), {})  # the watchman takes over
        self.assertTrue(self.runtime()["armed"])
        self.blocked()  # the count starts again, never rising for good
        self.assertEqual(self.snapshot()[:4], before[:4])  # the ledger and tree untouched

    def test_a_revival_clears_the_gates_end(self):
        self.beat(0)
        code, out = self.shift("step", "21", "--begin", "--gen", "1", "--role", "reviewer",
                               *self.readings(10, 80))
        self.assertEqual((code, out["gate"]), (0, "end"), out)
        self.assertEqual(self.revive(21)[0], 0)
        self.blocked(session="s2", minutes=21)

    def test_another_outcome_breaks_the_row_of_stalls(self):
        self.beat(0)
        self.assertEqual(self.shift("stall", "21", "--gen", "1", "--why", "x")[0], 0)
        self.issue_body(25, "## Acceptance criteria\n\n- [ ] Looks right\n")
        self.assertEqual(self.admit(25)[0], 0)
        self.assertEqual(self.needs_you(25)[0], 0)
        self.tracker({21: [], 22: [], 23: [], 25: []})
        self.assertEqual(self.shift("next", "--gen", "1")[0], 0)
        self.issue_body(22, "## Acceptance criteria\n\n- [ ] It flies\n")
        self.assertEqual(self.admit(22)[0], 0)
        self.assertEqual(self.shift("stall", "22", "--gen", "1", "--why", "x")[0], 0)
        self.assertEqual(self.stop(), {})  # nothing left to move, and the shift is still armed
        self.assertTrue(self.runtime()["armed"])

    def test_the_plugin_stop_hook_prints_the_decision(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]["Stop"]
        command = hooks[0]["hooks"][0]["command"]
        hook = json.dumps({"session_id": "s1", "cwd": str(self.target), "hook_event_name": "Stop",
                           "stop_hook_active": False})
        p = subprocess.run(["sh", "-c", command], cwd=self.target, capture_output=True, text=True,
                           env={**self.at(0), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, input=hook)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["decision"], BLOCK)

    def test_a_failure_fails_open_never_blocking(self):
        self.beat(0)
        self.git("checkout", "-q", "-b", "elsewhere")
        hook = json.dumps({"session_id": "s1", "cwd": str(self.target), "hook_event_name": "Stop"})
        for stdin in (hook, "{not json"):
            code, out = self.shift("stop-check", env=self.at(0), input=stdin)
            self.assertEqual(code, 1, out)  # Claude Code: a non-blocking error, so the stop goes on
            self.assertNotIn("decision", out)
        self.git("checkout", "-q", BRANCH)


class SmallStopGate(Stopping):
    """21 In progress, 22 Backlog behind it, 23 Needs you (human), 24 Done."""

    def prepare(self):
        self.prescan["tickets"] = [t for t in self.prescan["tickets"] if t["number"] != 25]
        super().prepare()

    def test_the_hook_allows_the_stop_when_the_frontier_is_empty(self):
        self.beat(0)
        self.assertEqual(self.shift("stall", "21", "--gen", "1", "--why", "x")[0], 0)
        self.assertEqual(self.stop(), {})  # 22 waits behind a stalled ticket

    def test_a_ticket_left_in_backlog_behind_a_done_ticket_still_remains(self):
        self.beat(0)
        url = self.evidence()
        code, out = self.done([{"criterion": "It runs", "verdict": "met", "evidence_url": url}])
        self.assertEqual(code, 0, out)
        self.assertIn("#22", self.blocked())  # `next` has not run yet to make it Ready


if __name__ == "__main__":
    unittest.main()
