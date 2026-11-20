"""The lease, heartbeat, is-dead and revive (#25), driven through the state script's command
line (ADR 0007). "Now" comes from THIRD_SHIFT_NOW, so nothing sleeps."""
import json
import os
import subprocess
import sys
import time
import unittest
from datetime import datetime, timedelta

from tests.test_lifecycle import Working
from tests.test_shift import ROOT, SHIFT
from tests.test_tickets import BRANCH

T0 = datetime.fromisoformat("2030-01-01T00:00:00+00:00")  # after the fixture was armed


class Clock:
    def at(self, minutes):
        return {**self.env, "THIRD_SHIFT_NOW": (T0 + timedelta(minutes=minutes)).isoformat()}

    def beat(self, minutes, session="s1", **hook):
        hook = {"session_id": session, "cwd": str(self.target), "hook_event_name": "PreToolUse",
                "tool_name": "Bash", **hook}
        code, out = self.shift("heartbeat", env=self.at(minutes), input=json.dumps(hook))
        self.assertEqual(code, 0, out)
        return out

    def last_beat(self):
        f = self.home / "acme" / "widget" / "heartbeat"
        return json.loads(f.read_text())["at"] if f.exists() else None

    def dead(self, minutes):
        code, out = self.shift("is-dead", env=self.at(minutes))
        self.assertEqual(code, 0, out)
        return out["dead"]

    def revive(self, minutes):
        return self.shift("revive", env=self.at(minutes))


class Revival(Clock, Working):
    """An armed shift, #21 In progress (the "admitted" fixture)."""
    fixture = "admitted"

    # the lease

    def test_a_stale_gen_is_refused_logged_and_told_to_stop(self):
        self.assert_refused_unchanged([("stall", "21", "--gen", "0", "--why", "x")], 2)
        code, out = self.shift("stall", "21", "--gen", "0", "--why", "x")
        self.assertTrue(out["stop"])
        log = (self.home / "acme" / "widget" / "refusals.jsonl").read_text().splitlines()
        self.assertEqual([(r["command"], r["gen"], r["lease"]) for r in map(json.loads, log)],
                         [("stall", 0, 1)] * 2)

    # heartbeat

    def test_heartbeat_does_nothing_unless_a_shift_is_armed(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        code, out = self.shift("heartbeat", env={**self.at(0), "THIRD_SHIFT_HOME": str(empty)},
                               input=json.dumps({"session_id": "s1", "cwd": str(self.target)}))
        self.assertEqual((code, list(empty.iterdir())), (0, []), out)
        self.assertEqual(self.shift("end", "--gen", "1", "--reason", "x")[0], 0)
        self.beat(0)
        self.assertIsNone(self.last_beat())
        self.assertNotIn("session_id", self.runtime())

    def test_the_first_hook_claims_the_lease_and_other_sessions_do_nothing(self):
        self.beat(0, session="other", cwd=str(self.tmp))  # a session in another folder
        self.assertIsNone(self.last_beat())
        self.beat(1)
        self.assertEqual(self.runtime()["session_id"], "s1")
        self.assertEqual(self.last_beat(), (T0 + timedelta(minutes=1)).isoformat())
        self.beat(2, session="s2")
        self.assertEqual(self.last_beat(), (T0 + timedelta(minutes=1)).isoformat())
        self.beat(3, agent_id="a1", agent_type="implementer")  # a tool call inside a subagent
        self.assertEqual(self.last_beat(), (T0 + timedelta(minutes=3)).isoformat())

    def test_concurrent_heartbeats_all_succeed(self):
        self.beat(0)  # claim the lease first, so every beat writes
        hook = json.dumps({"session_id": "s1", "cwd": str(self.target)})
        procs = [subprocess.Popen([sys.executable, str(SHIFT), "heartbeat"], cwd=self.target,
                                  env=self.at(1), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) for _ in range(20)]
        time.sleep(1)  # every process is started and blocked reading its hook
        for p in procs:  # release them together
            p.stdin.write(hook)
            p.stdin.close()
        results = [(p.stdout.read(), p.stderr.read(), p.wait()) for p in procs]
        for stdout, stderr, code in results:
            self.assertEqual(code, 0, stdout + stderr)
            self.assertTrue(json.loads(stdout)["ok"])
        self.assertEqual(sorted(f.name for f in (self.home / "acme" / "widget").glob("heartbeat*")),
                         ["heartbeat"])

    def test_a_corrupt_state_for_another_repo_does_not_stop_this_heartbeat(self):
        other = self.home / "aaa" / "broken"  # globbed first
        other.mkdir(parents=True)
        (other / "state.json").write_text("{not json")
        self.beat(0)
        self.beat(1, session="s2")  # passes over this repo's lease, so reaches every state file
        self.beat(2)
        self.assertEqual(self.last_beat(), (T0 + timedelta(minutes=2)).isoformat())

    def test_the_plugin_hook_runs_heartbeat_on_every_tool_call(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]["PreToolUse"]
        command = next(h["hooks"][0]["command"] for h in hooks if h.get("matcher") in (None, "*"))
        p = subprocess.run(["sh", "-c", command], cwd=self.target, capture_output=True, text=True,
                           env={**self.at(0), "CLAUDE_PLUGIN_ROOT": str(ROOT)},
                           input=json.dumps({"session_id": "s1", "cwd": str(self.target)}))
        self.assertEqual((p.returncode, p.stdout), (0, ""), p.stderr)
        self.assertEqual(self.last_beat(), T0.isoformat())

    # is-dead

    def test_dead_only_when_armed_running_and_silent_for_20_minutes(self):
        self.beat(0)
        self.assertFalse(self.dead(19))
        self.assertTrue(self.dead(20))
        self.beat(30)
        self.assertFalse(self.dead(49))
        self.assertEqual(self.shift("end", "--gen", "1", "--reason", "x")[0], 0)
        self.assertFalse(self.dead(500))

    def test_at_a_planned_pause_dead_only_once_reset_plus_15_minutes_has_passed(self):
        reset = (T0 + timedelta(minutes=120)).isoformat()
        self.assertEqual(self.shift("pause", "--gen", "1", "--reason", "usage", "--until", reset,
                                    env=self.at(0))[0], 0)
        self.beat(0)
        self.assertFalse(self.dead(134))  # silent for over two hours, but paused
        self.assertTrue(self.dead(135))
        self.beat(125)  # woke after the reset: the 20 minutes count again
        self.assertFalse(self.dead(144))
        self.assertTrue(self.dead(145))

    def test_a_pause_by_the_builder_is_never_dead(self):
        reset = (T0 + timedelta(minutes=120)).isoformat()
        self.assertEqual(self.shift("pause", "--gen", "1", "--reason", "owner", "--until", reset,
                                    env=self.at(0))[0], 0)
        self.assertFalse(self.dead(5000))
        self.assertEqual(self.revive(5000)[0], 1)
        self.assertEqual(self.shift("resume", "--gen", "1")[0], 0)  # running again: 20 minutes
        self.assertTrue(self.dead(20))

    # revive

    def test_revive_refuses_a_live_shift_and_writes_nothing(self):
        self.beat(0)
        self.assert_refused_unchanged([("revive",)], 1)  # real now is before T0: not silent
        before = self.snapshot()
        code, out = self.revive(19)
        self.assertEqual(code, 1, out)
        self.assertEqual(self.snapshot(), before)

    def test_revive_raises_the_gen_sets_work_aside_and_restarts_the_ticket(self):
        (self.target / "built.txt").write_text("committed\n")
        self.git("add", "built.txt")
        self.git("commit", "-qm", "#21: part")
        (self.target / "README.md").write_text("half-edited\n")
        (self.target / "new.txt").write_text("untracked\n")
        self.beat(0)
        code, out = self.revive(21)
        self.assertEqual(code, 0, out)
        ref = out["set_aside"]
        self.assertEqual((out["gen"], out["revivals"], out["ticket"]), (2, 1, 21))
        self.assertEqual(self.git("show", f"{ref}:README.md"), "half-edited")
        self.assertEqual(self.git("show", f"{ref}:new.txt"), "untracked")
        self.assertEqual(self.git("rev-parse", ref), self.git("rev-parse", ref, cwd=self.remote))
        self.assertEqual(self.git("status", "--porcelain"), "")  # restarted from its last commit
        self.assertEqual((self.target / "README.md").read_text(), "widget\n")
        self.assertTrue((self.target / "built.txt").exists())
        self.assert_ledger_commit("ledger: #20 revived")
        self.assertEqual(self.state(21), {"state": "In progress", "crashes": 1})
        state = self.runtime()
        self.assertEqual((state["gen"], state["revivals"], state.get("session_id")), (2, 1, None))
        self.assertEqual(self.shift("stall", "21", "--gen", "1", "--why", "x")[0], 2)  # old session
        self.beat(22, session="s2")  # the new session's first hook claims the lease
        self.assertEqual(self.runtime()["session_id"], "s2")
        self.assertFalse(self.dead(41))

    def test_the_revived_session_never_reclaims_the_lease(self):
        self.beat(0)
        self.assertEqual(self.revive(21)[0], 0)
        self.beat(22)  # the old session wakes before the new one's first tool call
        self.assertNotIn("session_id", self.runtime())
        self.assertEqual(self.last_beat(), T0.isoformat())
        self.beat(23, session="s2")
        self.assertEqual(self.runtime()["session_id"], "s2")
        self.assertFalse(self.dead(42))

    def test_two_crashes_make_a_blocker_and_a_third_revival_ends_the_shift(self):
        self.beat(0)
        self.assertEqual(self.revive(21)[0], 0)
        self.assertFalse(self.dead(40))  # a revival counts as a sign of life
        code, out = self.revive(41)
        self.assertEqual((code, out["set_aside"]), (0, None), out)
        self.assertEqual(self.state(21), {"state": "Needs you", "crashes": 2,
                                          "reason": "set aside after a crash",
                                          "why": "in progress during 2 crashes"})
        code, out = self.revive(61)
        self.assertEqual((code, out["shift_state"], out["ticket"]), (0, "ended", None), out)
        self.assertEqual(self.ledger()["end"]["reason"], "three revivals")
        self.assertEqual([r["gen"] for r in self.ledger()["revivals"]], [2, 3, 4])
        state = self.runtime()
        self.assertEqual((state["armed"], state["revivals"], state["gen"]), (False, 3, 4))

    def test_a_failed_push_at_revive_keeps_the_work_and_the_lease(self):
        (self.target / "README.md").write_text("half-edited\n")
        before = self.snapshot()
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.assertEqual(self.revive(21)[0], 1)
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn("set-aside", self.git("for-each-ref"))
        self.assertEqual((self.target / "README.md").read_text(), "half-edited\n")



class WaitingRevival(Clock, Working):
    """Only 21 In progress, 23 Needs you and 24 Done (as test_lifecycle.Waiting)."""
    def prepare(self):
        self.prescan["tickets"] = [t for t in self.prescan["tickets"] if t["number"] in (21, 23, 24)]
        super().prepare()

    def test_a_shift_waiting_on_the_builder_is_never_dead(self):
        self.assertEqual(self.shift("stall", "21", "--gen", "1", "--why", "x")[0], 0)
        self.assertEqual(self.shift("wait", "--gen", "1")[0], 0)
        self.assertFalse(self.dead(5000))
        self.assertEqual(self.revive(5000)[0], 1)


if __name__ == "__main__":
    unittest.main()
