"""needs-you, stall, release, note, wait and end (#23), driven through the state script's
command line (ADR 0007)."""
import json
import unittest

from tests.test_shift import issue
from tests.test_tickets import Armed


class Working(Armed):
    """An armed shift with #21 admitted; helpers, no tests."""
    admitted = True

    def assert_refused_unchanged(self, cases, code=1):
        before = self.snapshot()
        for args in cases:
            got, out = self.shift(*args)
            self.assertEqual(got, code, (args, out))
            self.assertIn("refused", out)
        self.assertEqual(self.snapshot(), before)  # once: one refusal cannot undo another's write

    def needs_you(self, n=21, reason="blocker", why="Which file format?"):
        return self.shift("needs-you", str(n), "--gen", "1", "--reason", reason, "--why", why)

    def release(self, n=21, *decision):
        return self.shift("release", str(n), "--gen", "1", *decision)

    def note(self, kind, n=21, *extra, text="a finding"):
        return self.shift("note", kind, str(n), "--gen", "1", "--text", text, *extra)


class InProgress(Working):
    """21 In progress, 22 Backlog, 23 Needs you (human), 24 Done, 25 Ready."""
    fixture = "admitted"

    # needs-you

    def accepts(self, reason):
        code, out = self.needs_you(reason=reason, why=f"why: {reason}")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state(21), {"state": "Needs you", "reason": reason,
                                          "why": f"why: {reason}"})
        self.assert_ledger_commit("ledger: #21 needs you")

    def test_needs_you_accepts_a_blocker(self):
        self.accepts("blocker")

    def test_needs_you_accepts_human_verify(self):
        self.accepts("human-verify")

    def test_needs_you_accepts_human(self):
        self.accepts("human")

    def test_needs_you_accepts_set_aside_after_a_crash(self):
        self.accepts("set aside after a crash")

    def test_needs_you_refuses_other_reasons_a_blank_why_and_tickets_not_in_progress(self):
        go = ("needs-you", "21", "--gen", "1")
        self.assert_refused_unchanged([
            (*go, "--reason", "crash", "--why", "x"),
            (*go, "--reason", "Blocker", "--why", "x"),
            (*go, "--reason", "blocker", "--why", "  "),
            (*go, "--reason", "blocker"),
            (*go, "--why", "x"),
            *(("needs-you", n, "--gen", "1", "--reason", "blocker", "--why", "x")
              for n in ("22", "23", "24", "25", "99")),  # Backlog, Needs you, Done, Ready, none
        ])
        self.assert_refused_unchanged([(*go[:3], "0", "--reason", "blocker", "--why", "x")], 2)

    def test_a_failed_push_leaves_the_ledger_as_it_was(self):
        before = self.snapshot()
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.assertEqual(self.needs_you()[0], 1)
        self.assertEqual(self.snapshot(), before)

    # stall

    def test_stall_sets_an_in_progress_ticket_aside(self):
        code, out = self.shift("stall", "21", "--gen", "1", "--why", "three blocked stops")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state(21), {"state": "Stalled", "why": "three blocked stops"})
        self.assert_ledger_commit("ledger: #21 stalled")

    def test_stall_refuses_a_blank_why_and_tickets_not_in_progress(self):
        self.assert_refused_unchanged([
            ("stall", "21", "--gen", "1", "--why", ""),
            ("stall", "21", "--gen", "1"),
            *(("stall", n, "--gen", "1", "--why", "x") for n in ("22", "23", "24", "25", "99")),
        ])
        self.assert_refused_unchanged([("stall", "21", "--gen", "0", "--why", "x")], 2)

    # release

    def test_release_returns_a_needs_you_ticket_to_the_frontier_with_the_answer(self):
        code, out = self.release(23, "--decision", "Signed by me")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state(23), {"state": "Ready", "released": [
            {"reason": None, "why": None, "decision": "Signed by me"}]})
        self.assert_ledger_commit("ledger: #23 released")

    def test_release_puts_a_blocked_ticket_in_backlog_and_keeps_the_question(self):
        self.needs_you(why="Which file format?")
        self.tracker({21: [issue(99)], 22: [issue(21)], 23: [], 25: []})
        code, out = self.release()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state(21), {"state": "Backlog", "released": [
            {"reason": "blocker", "why": "Which file format?", "decision": None}]})

    def test_release_refuses_a_ticket_not_in_needs_you_and_a_blank_decision(self):
        self.assert_refused_unchanged([
            *(("release", n, "--gen", "1") for n in ("21", "22", "24", "25", "99")),
            ("release", "23", "--gen", "1", "--decision", " "),
        ])
        self.assert_refused_unchanged([("release", "23", "--gen", "0")], 2)

    # note

    def test_note_records_each_kind_and_an_owed_finding_names_its_carrier(self):
        self.assertEqual(self.note("decision", text="slug is the number")[0], 0)
        self.assert_ledger_commit("ledger: #21 decision")
        self.assertEqual(self.note("nit", 25, text="raw error text")[0], 0)
        code, out = self.note("owed", 21, "--for", "22", text="no usage gate yet")
        self.assertEqual(code, 0, out)
        self.assert_ledger_commit("ledger: #21 owed")
        self.assertEqual(self.ledger()["notes"], [
            {"kind": "decision", "ticket": 21, "text": "slug is the number"},
            {"kind": "nit", "ticket": 25, "text": "raw error text"},
            {"kind": "owed", "ticket": 21, "text": "no usage gate yet", "for": 22}])

    def test_note_refuses_an_owed_finding_without_a_later_carrier_and_bad_fields(self):
        self.assert_refused_unchanged([
            ("note", "owed", "21", "--gen", "1", "--text", "x"),
            *(("note", "owed", "21", "--gen", "1", "--text", "x", "--for", n)
              for n in ("21", "24", "99")),  # itself, Done, not in the shift
            ("note", "decision", "21", "--gen", "1", "--text", "x", "--for", "22"),
            ("note", "idea", "21", "--gen", "1", "--text", "x"),
            ("note", "nit", "21", "--gen", "1", "--text", ""),
            ("note", "nit", "99", "--gen", "1", "--text", "x"),
        ])
        self.assert_refused_unchanged([("note", "nit", "21", "--gen", "0", "--text", "x")], 2)

    # wait and end

    def test_wait_refuses_while_a_ticket_can_still_move(self):
        self.assert_refused_unchanged([("wait", "--gen", "1")])  # 21 In progress, 22, 25
        self.shift("stall", "21", "--gen", "1", "--why", "x")
        self.assert_refused_unchanged([("wait", "--gen", "1")])  # 22 Backlog, 25 Ready
        self.assert_refused_unchanged([("wait", "--gen", "0")], 2)

    def test_end_disarms_the_shift_and_leaves_the_work_on_the_branch(self):
        main = self.git("rev-parse", "main", cwd=self.remote)
        code, out = self.shift("end", "--gen", "1", "--reason", "frontier empty")
        self.assertEqual(code, 0, out)
        self.assertEqual((out["shift_state"], out["end_state"]), ("ended", "branch"))
        self.assertEqual(self.ledger()["end"], {"reason": "frontier empty", "end_state": "branch"})
        self.assert_ledger_commit("ledger: #20 ended")
        self.assertEqual(self.git("rev-parse", "main", cwd=self.remote), main)
        state = self.runtime()
        self.assertEqual((state["armed"], state["shift_state"]), (False, "ended"))
        code, out = self.shift("next", "--gen", "1")
        self.assertEqual(code, 1, out)
        self.assertIn("no shift is armed", out["refused"])

    def test_end_refuses_a_blank_reason_and_a_stale_gen(self):
        self.assert_refused_unchanged([("end", "--gen", "1", "--reason", " "), ("end", "--gen", "1")])
        self.assert_refused_unchanged([("end", "--gen", "0", "--reason", "x")], 2)

    def test_a_failed_push_at_end_leaves_the_shift_armed(self):
        before = self.snapshot()
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.assertEqual(self.shift("end", "--gen", "1", "--reason", "x")[0], 1)
        self.assertEqual(self.snapshot(), before)
        hook.unlink()
        self.assertEqual(self.shift("end", "--gen", "1", "--reason", "x")[0], 0)


class Waiting(Working):
    """Only 21 In progress, 23 Needs you (human) and 24 Done: one stall from waiting."""
    def prepare(self):
        self.prescan["tickets"] = [t for t in self.prescan["tickets"] if t["number"] in (21, 23, 24)]
        super().prepare()

    def test_wait_when_only_needs_you_or_stalled_are_left_then_end(self):
        self.assertEqual(self.shift("stall", "21", "--gen", "1", "--why", "x")[0], 0)
        code, out = self.shift("wait", "--gen", "1")
        self.assertEqual((code, out["shift_state"]), (0, "waiting"), out)
        self.assertEqual(self.runtime()["shift_state"], "waiting")
        self.assert_refused_unchanged([("wait", "--gen", "1")])  # already waiting
        self.assertEqual(self.shift("end", "--gen", "1", "--reason", "waiting on you")[0], 0)

    def test_release_while_waiting_returns_the_shift_to_running(self):
        self.shift("stall", "21", "--gen", "1", "--why", "x")
        self.shift("wait", "--gen", "1")
        code, out = self.release(23, "--decision", "go")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.runtime()["shift_state"], "running")


if __name__ == "__main__":
    unittest.main()
