"""The tracker mirror (#28): setup-board, cards, the shift status comment and resolution
comments, asserted on the fake gh's write log (ADR 0007)."""
import json
import re
from pathlib import Path

from tests.test_shift import REPO, SLUG, Target
from tests.test_tickets import Armed

STATES = ["Backlog", "Ready", "In progress", "Needs you", "Stalled", "Done"]
SPEC = "#20 Widget version 1"


def options(*names):
    return [{"id": f"O-{n}", "name": n, "color": "GRAY", "description": ""} for n in names]


def board(columns=STATES, specs=(SPEC,), why=True, views=(SPEC,), linked=True):
    fields = [{"id": "F-status", "name": "Status", "options": options(*columns)},
              {"id": "F-title", "name": "Title"}]
    if specs is not None:
        fields.append({"id": "F-spec", "name": "Spec", "options": options(*specs)})
    if why:
        fields.append({"id": "F-why", "name": "Why"})
    return {"id": "P1", "number": 7, "title": "third-shift: widget",
            "url": "https://github.com/orgs/acme/projects/7",
            "repositories": {"nodes": [{"nameWithOwner": REPO}] if linked else []},
            "fields": {"nodes": fields}, "views": {"nodes": [{"id": "V-x", "name": v} for v in views]}}


class Board(Target):
    """A target with the fake tracker's board answers; helpers, no tests."""

    def canned(self, **extra):
        f = self.gh / "fixture.json"
        fixture = json.loads(f.read_text())
        fixture.update(extra)
        f.write_text(json.dumps(fixture))

    def found(self, *projects, **graphql):
        api = json.loads((self.gh / "fixture.json").read_text())["api"]
        api[f"repos/{REPO}/issues/20"] = {"number": 20, "title": "Widget version 1"}
        api[f"repos/{REPO}/issues/20/comments"] = []
        self.canned(api=api, graphql={
            "Board": {"repository": {"id": "R1", "owner": {"id": "U1", "projectsV2": {
                "nodes": [{**board(), "title": "third-shift: other"}, *projects]}}}},
            "Issues": {"repository": {f"i{n}": {"id": f"N{n}"} for n in range(21, 26)}},
            "AddCards": {f"c{n}": {"item": {"id": f"I{n}"}} for n in range(21, 26)},
            **graphql},
            post={f"repos/{REPO}/issues/20/comments": {"id": 501}})

    def setup_board(self):
        return self.shift("setup-board", "--spec", "20")

    def calls(self):
        """The recorded writes as (graphql operation name or api path, args)."""
        out = []
        for line in self.writes():
            args = json.loads(line)
            q = next((a[6:] for a in args if a.startswith("query=")), None)
            out.append((re.match(r"mutation (\w+)", q)[1] if q else args[1], args))
        return out

    def ops(self):
        return [c[0] for c in self.calls()]

    def query(self, op):
        return next(a for o, args in self.calls() if o == op for a in args if a.startswith("query="))

    def bodies(self, path):
        return [a[5:] for o, args in self.calls() if o == path for a in args if a.startswith("body=")]

    def clear(self):
        (self.gh / "writes.jsonl").unlink(missing_ok=True)


class SetupBoard(Board):

    def test_setup_board_creates_links_and_lays_out_a_new_board(self):
        new = board(columns=["Todo", "In Progress", "Done"], specs=None, why=False, views=())
        laid = board()["fields"]["nodes"]
        self.found(CreateBoard={"createProjectV2": {"projectV2": new}},
                   StatusOptions={"updateProjectV2Field": {"projectV2Field": laid[0]}},
                   SpecField={"createProjectV2Field": {"projectV2Field": laid[2]}},
                   WhyField={"createProjectV2Field": {"projectV2Field": laid[3]}},
                   View={"createProjectV2View": {"projectV2View": {"id": "V1"}}})
        code, out = self.setup_board()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["made"], ["board", "status", "spec", "why", "view"])
        self.assertEqual(self.ops(), ["CreateBoard", "StatusOptions", "SpecField", "WhyField",
                                      "View", "ViewFilter"])
        create = self.query("CreateBoard")
        self.assertIn('title: "third-shift: widget"', create)
        self.assertIn('repositoryId: "R1"', create)  # linked at birth
        status = self.query("StatusOptions")
        self.assertEqual(re.findall(r'name: "([^"]+)"', status), STATES)
        self.assertIn('id: "O-In Progress", name: "In progress"', status)  # its cards stay put
        self.assertIn(f'name: "{SPEC}"', self.query("SpecField"))
        self.assertIn("dataType: TEXT", self.query("WhyField"))
        self.assertIn("layout: BOARD_LAYOUT", self.query("View"))
        self.assertIn('filter: "spec:\\"#20 Widget version 1\\""', self.query("ViewFilter"))

    def test_setup_board_links_a_found_board_and_adds_the_spec_and_its_view(self):
        self.found(board(specs=["#19 Old"], views=["#19 Old"], linked=False),
                   SpecOptions={"updateProjectV2Field": {"projectV2Field": {
                       "id": "F-spec", "name": "Spec", "options": options("#19 Old", SPEC)}}},
                   View={"createProjectV2View": {"projectV2View": {"id": "V1"}}})
        code, out = self.setup_board()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ops(), ["Link", "SpecOptions", "View", "ViewFilter"])
        self.assertIn('id: "O-#19 Old", name: "#19 Old"', self.query("SpecOptions"))

    def test_setup_board_changes_nothing_on_a_laid_out_board(self):
        self.found(board())
        code, out = self.setup_board()
        self.assertEqual((code, out["made"], self.writes()), (0, [], []))

    def test_arm_draws_every_card_and_posts_one_status_comment(self):
        self.found(board())
        self.setup_board()
        self.canned(fail=["Board"])  # found by title no more: the cache answers
        code, out = self.arm()
        self.assertEqual(code, 0, out)
        self.assertNotIn("mirror", out)
        self.assertEqual(self.ops(), ["AddCards", "Cards", f"repos/{REPO}/issues/20/comments"])
        for n in range(21, 26):
            self.assertIn(f'c{n}: addProjectV2ItemById(input: {{projectId: "P1", contentId: "N{n}"}})',
                          self.query("AddCards"))
        q = self.query("Cards")
        for n, state in ((21, "Ready"), (22, "Backlog"), (23, "Needs you"), (24, "Done"),
                         (25, "Ready")):
            self.assertIn(f's{n}: updateProjectV2ItemFieldValue(input: {{projectId: "P1", '
                          f'itemId: "I{n}", fieldId: "F-status", value: {{singleSelectOptionId: '
                          f'"O-{state}"}}}})', q)
            self.assertIn(f'p{n}: updateProjectV2ItemFieldValue(input: {{projectId: "P1", '
                          f'itemId: "I{n}", fieldId: "F-spec", value: {{singleSelectOptionId: '
                          f'"O-{SPEC}"}}}})', q)
        [body] = self.bodies(f"repos/{REPO}/issues/20/comments")
        self.assertTrue(body.startswith(f"<!-- third-shift status {SLUG} {self.base} -->"))
        self.assertIn("| #23 | Needs you |", body)


class Mirror(Board, Armed):
    """An armed shift on a laid-out board, #21 admitted; the arm's writes cleared."""
    admitted = True

    def prepare(self):
        self.found(board())
        self.assertEqual(self.setup_board()[0], 0)
        super().prepare()
        self.clear()

    def comment(self):
        return self.bodies(f"repos/{REPO}/issues/comments/501")[-1]

    def test_admit_drew_its_card_and_the_comment_shows_the_step(self):
        code, out = self.step()
        self.assertEqual(code, 0, out)
        self.assertNotIn("Cards", self.ops())  # no card changed
        self.assertIn("| #21 | In progress | step: implementer, round 1 |", self.comment())
        self.assertNotIn(f"repos/{REPO}/issues/20/comments", self.ops())  # created once

    def test_the_status_comment_is_edited_in_place_on_shift_state_changes(self):
        self.shift("pause", "--gen", "1", "--reason", "usage", "--until", self.RESET)
        self.assertIn(f"### Shift status: paused (usage) until {self.RESET}", self.comment())
        self.shift("resume", "--gen", "1")
        self.assertIn("### Shift status: running", self.comment())
        self.assertIn("| #21 | In progress | admitted |", self.comment())
        self.assertTrue(self.comment().startswith(f"<!-- third-shift status {SLUG} {self.base} -->"))
        self.assertEqual(self.ops(), [f"repos/{REPO}/issues/comments/501"] * 2)

    def test_why_shows_only_in_needs_you(self):
        self.shift("needs-you", "21", "--gen", "1", "--reason", "blocker", "--why", "is zero an error?")
        q = self.query("Cards")
        self.assertIn('"O-Needs you"', q)
        self.assertIn('w21: updateProjectV2ItemFieldValue(input: {projectId: "P1", itemId: "I21", '
                      'fieldId: "F-why", value: {text: "is zero an error?"}})', q)
        self.assertIn("| #21 | Needs you | blocker · is zero an error? |", self.comment())
        self.clear()
        self.shift("release", "21", "--gen", "1", "--decision", "an error")
        q = self.query("Cards")
        self.assertIn('"O-Ready"', q)
        self.assertIn('w21: clearProjectV2ItemFieldValue(input: {projectId: "P1", itemId: "I21", '
                      'fieldId: "F-why"})', q)

    def test_done_posts_the_resolution_table_and_closes_the_issue(self):
        url = self.evidence()
        code, out = self.done([{"criterion": "It runs", "verdict": "met", "evidence_url": url}])
        self.assertEqual(code, 0, out)
        self.assertNotIn("mirror", out)
        ops = self.ops()
        self.assertLess(ops.index(f"repos/{REPO}/issues/21/comments"),
                        ops.index(f"repos/{REPO}/issues/21"))  # the table, then the close
        [body] = self.bodies(f"repos/{REPO}/issues/21/comments")
        self.assertIn(f"| It runs | met | [evidence]({url}) |", body)
        close = next(a for o, a in self.calls() if o == f"repos/{REPO}/issues/21")
        self.assertEqual(close[2:], ["-X", "PATCH", "-f", "state=closed", "-f", "state_reason=completed"])
        self.assertIn('"O-Done"', self.query("Cards"))

    def test_needs_your_run_comments_without_closing(self):
        url = self.evidence()
        self.done([{"criterion": "It runs", "verdict": "needs your run", "evidence_url": url}])
        [body] = self.bodies(f"repos/{REPO}/issues/21/comments")
        self.assertIn("| It runs | needs your run |", body)
        self.assertNotIn(f"repos/{REPO}/issues/21", self.ops())
        self.assertIn('"O-Needs you"', self.query("Cards"))

    def test_a_failed_tracker_write_loses_no_state_and_the_next_command_catches_up(self):
        url = self.evidence()
        self.canned(fail=["Cards", f"repos/{REPO}/issues/21"])
        code, out = self.done([{"criterion": "It runs", "verdict": "met", "evidence_url": url}])
        self.assertEqual(code, 0, out)
        self.assertTrue(out["mirror"].startswith("behind:"), out)
        self.assertEqual(self.state(21)["state"], "Done")  # the record stands, pushed
        self.assertEqual(self.ops(), [])  # nothing failed was recorded
        self.canned(fail=[f"repos/{REPO}/issues/21"])
        code, out = self.shift("next", "--gen", "1")
        self.assertIn("mirror", out)  # the close still fails; the cards are drawn
        self.assertIn('s21: updateProjectV2ItemFieldValue', self.query("Cards"))
        self.assertEqual(len(self.bodies(f"repos/{REPO}/issues/21/comments")), 1)
        self.canned(fail=[])
        self.clear()
        code, out = self.shift("next", "--gen", "1")
        self.assertNotIn("mirror", out)
        self.assertEqual(self.ops(), [f"repos/{REPO}/issues/21",  # the close, but no repost
                                      f"repos/{REPO}/issues/comments/501"])

    def test_comments_and_cards_carry_no_machine_paths_or_labels(self):
        top = self.git("rev-parse", "--show-toplevel")  # the folder as git and the script name it
        why = f"see {top}/src/x.py and {Path.home()}/notes"
        self.shift("needs-you", "21", "--gen", "1", "--reason", "blocker", "--why", why)
        self.assertIn("see ./src/x.py and ~/notes", self.comment())
        everything = "\n".join(self.writes())
        for private in (str(Path(top).parent), str(Path.home())):
            self.assertNotIn(private, everything)
        self.assertNotIn("label", everything.lower())

    def test_the_status_comment_is_found_by_its_marker_when_its_id_is_lost(self):
        state_file = self.home / "acme" / "widget" / "state.json"
        state = json.loads(state_file.read_text())
        state["mirror"].pop("comment")
        state["mirror"]["comment_hash"] = ""
        state_file.write_text(json.dumps(state))
        api = json.loads((self.gh / "fixture.json").read_text())["api"]
        api[f"repos/{REPO}/issues/20/comments"] = [
            {"id": 9, "body": "a builder's note"},
            {"id": 501, "body": f"<!-- third-shift status {SLUG} {self.base} -->\nold"}]
        self.canned(api=api)
        self.shift("note", "nit", "21", "--gen", "1", "--text", "x")  # notes do not mirror
        self.assertEqual(self.ops(), [])
        self.step()
        self.assertEqual(self.ops(), [f"repos/{REPO}/issues/comments/501"])

    def test_a_recreated_board_drops_the_cached_cards_and_adds_them_again(self):
        self.found({**board(), "id": "P2"})
        self.assertEqual(self.setup_board()[0], 0)
        self.shift("needs-you", "21", "--gen", "1", "--reason", "blocker", "--why", "x")
        self.assertIn('c21: addProjectV2ItemById(input: {projectId: "P2", contentId: "N21"})',
                      self.query("AddCards"))

    def test_a_recreated_board_gets_the_unchanged_cards_too(self):
        self.found({**board(), "id": "P2"})
        self.assertEqual(self.setup_board()[0], 0)
        self.step()  # nothing changed in the ledger; every card is missing from the new board
        add, cards = self.query("AddCards"), self.query("Cards")
        for n, state in ((22, "Backlog"), (24, "Done")):
            self.assertIn(f'c{n}: addProjectV2ItemById(input: {{projectId: "P2", contentId: "N{n}"}})', add)
            self.assertIn(f's{n}: updateProjectV2ItemFieldValue(input: {{projectId: "P2", itemId: '
                          f'"I{n}", fieldId: "F-status", value: {{singleSelectOptionId: "O-{state}"}}}})',
                          cards)

    def test_an_emoji_in_why_goes_out_as_text(self):
        self.shift("needs-you", "21", "--gen", "1", "--reason", "blocker", "--why", "zero? \U0001F914")
        self.assertIn('value: {text: "zero? \U0001F914"}', self.query("Cards"))
        self.assertIn("blocker · zero? \U0001F914", self.comment())


class NoBoard(Board, Armed):
    """An armed shift, #21 admitted, and no board titled for the repo."""
    admitted = True

    def prepare(self):
        self.found()
        super().prepare()
        self.clear()

    def test_without_a_board_done_still_comments_closes_and_says_behind(self):
        url = self.evidence()
        code, out = self.done([{"criterion": "It runs", "verdict": "met", "evidence_url": url}])
        self.assertEqual((code, out.get("mirror")), (0, "behind: no board"), out)
        self.assertEqual(self.ops(), [f"repos/{REPO}/issues/21/comments", f"repos/{REPO}/issues/21",
                                      f"repos/{REPO}/issues/comments/501"])  # no cards

    def test_without_a_board_needs_your_run_comments_without_closing(self):
        url = self.evidence()
        code, out = self.done([{"criterion": "It runs", "verdict": "needs your run", "evidence_url": url}])
        self.assertEqual(out.get("mirror"), "behind: no board", out)
        self.assertNotIn(f"repos/{REPO}/issues/21", self.ops())
        self.assertEqual(len(self.bodies(f"repos/{REPO}/issues/21/comments")), 1)
