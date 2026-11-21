"""The stop file ends a shift, revived or not (#38), driven through the state script's command
line (ADR 0007): the gate ends a live shift at its next boundary, and a silent shift is dead
even while it waits on the builder, so the watchman revives it to hand over."""
import json
import subprocess
import sys
import unittest
from datetime import timedelta

from tests.test_revival import T0, Clock
from tests.test_lifecycle import Working
from tests.test_shift import SHIFT


class StopFile(Clock, Working):
    """An armed shift, #21 In progress (the "admitted" fixture)."""
    fixture = "admitted"

    def stop_file(self):
        (self.home / "acme" / "widget" / "STOP").write_text("")

    def test_the_gate_ends_the_shift_at_the_next_boundary(self):
        self.stop_file()
        code, out = self.shift("step", "21", "--begin", "--gen", "1", "--role", "reviewer",
                               *self.readings())
        self.assertEqual((code, out["gate"], out["reason"]), (0, "end", "stop file"), out)

    def test_a_silent_shift_waiting_on_the_builder_is_dead_at_a_stop_file(self):
        reset = (T0 + timedelta(minutes=120)).isoformat()
        self.assertEqual(self.shift("pause", "--gen", "1", "--reason", "owner", "--until", reset,
                                    env=self.at(0))[0], 0)
        self.beat(0)
        self.stop_file()
        self.assertFalse(self.dead(19))  # a live session meets the gate first
        self.assertTrue(self.dead(20))

    def test_revive_at_a_stop_file_ends_the_shift_without_reviving_it(self):
        self.beat(0)
        (self.target / "wip.txt").write_text("uncommitted\n")
        self.stop_file()
        code, out = self.revive(20)
        self.assertEqual((code, out["shift_state"], out["stop_file"]), (0, "ended", True), out)
        self.assertNotIn("gen", out)  # not revived: no generation, no set-aside, no notification
        self.assertEqual(self.ledger()["end"]["reason"], "stop file")
        self.assertNotIn("revivals", self.ledger())
        self.assertNotIn("revivals", self.runtime())
        self.assertTrue((self.target / "wip.txt").exists())  # nothing set aside
        self.assertFalse((self.home / "acme" / "widget" / "STOP").exists())  # spent: the next shift runs
        self.assertFalse(self.dead(500))

    def test_revive_without_a_stop_file_says_so(self):
        self.beat(0)
        code, out = self.revive(20)
        self.assertEqual((code, out["stop_file"]), (0, False), out)
        self.assertIn("watchman", out)


class Watchman(Clock, Working):
    """The watchman's session starts outside the target: is-dead finds it by name (#38)."""
    fixture = "admitted"

    def test_is_dead_finds_the_target_by_repo_from_any_folder(self):
        self.beat(0)
        p = subprocess.run([sys.executable, str(SHIFT), "is-dead", "acme/widget"], cwd=self.tmp,
                           env={**self.at(20), "PATH": "/usr/bin:/bin"},  # no gh: never asked
                           capture_output=True, text=True)
        out = json.loads(p.stdout)
        self.assertEqual((p.returncode, out["dead"], out["target"]),
                         (0, True, self.git("rev-parse", "--show-toplevel")), out)
        self.assertRegex(out["continue_cron"], r"^\d+ \d+ \d+ \d+ \*$")
        p = subprocess.run([sys.executable, str(SHIFT), "is-dead", "acme/nothing"], cwd=self.tmp,
                           env=self.at(20), capture_output=True, text=True)
        self.assertEqual((p.returncode, json.loads(p.stdout)["dead"]), (0, False))

    def test_end_answers_the_watchmans_task_id_for_its_removal(self):
        f = self.home / "acme" / "widget" / "state.json"
        f.write_text(json.dumps({**self.runtime(), "watchman": "third-shift-acme-widget"}))
        code, out = self.shift("end", "--gen", "1", "--reason", "frontier empty")
        self.assertEqual((code, out["watchman"]), (0, "third-shift-acme-widget"), out)


if __name__ == "__main__":
    unittest.main()
