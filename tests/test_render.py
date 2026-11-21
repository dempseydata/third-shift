"""The eval set's render script (#33), driven through `evals/render`'s command line, on copies of
the plugin's briefs and cases, so the repo's own prompt.md files are never written."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFS = Path("skills") / "start" / "references"


class Render(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "evals").mkdir()
        shutil.copy(ROOT / "evals" / "render", self.root / "evals" / "render")
        shutil.copytree(ROOT / REFS, self.root / REFS)

    def render(self):
        run = subprocess.run([sys.executable, self.root / "evals" / "render"],
                             capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout)

    def test_every_case_renders_from_the_current_briefs(self):
        for case in (ROOT / "evals").glob("*/slots.json"):
            shutil.copytree(case.parent, self.root / "evals" / case.parent.name,
                            ignore=shutil.ignore_patterns("prompt.md"))
        code, out = self.render()
        self.assertEqual((code, out["ok"]), (0, True), out)
        self.assertEqual(len(out["rendered"]), 8)
        briefs = (ROOT / REFS / "briefs.md").read_text()
        for name in out["rendered"]:
            case = self.root / "evals" / name
            prompt = (case / "prompt.md").read_text()
            role = json.loads((case / "slots.json").read_text())["brief"]
            model = re.search(rf"^\| {role} \| (\w+) \|", briefs, re.M)[1].lower()
            self.assertTrue(prompt.startswith(f"---\nmodel: {model}\n---\n"), name)
            self.assertIn(str(case / "fixtures") + "/", prompt)
            self.assertEqual(re.findall(r"\{[a-z_]+\}", prompt), [], name)

    def test_a_slot_with_no_value_refuses_and_writes_nothing(self):
        (self.root / REFS / "briefs.md").write_text(
            "| Role | Model |\n| --- | --- |\n| Prescan | Opus |\n\n"
            "## Prescan\n\n```\nScan {spec} against {sources}.\n```\n")
        for name, slots in (("a-full", {"spec": "#1", "sources": "ADR 1"}), ("b-short", {"spec": "#1"})):
            case = self.root / "evals" / name
            case.mkdir()
            (case / "slots.json").write_text(json.dumps({"brief": "Prescan", "slots": slots}))
        code, out = self.render()
        self.assertEqual(code, 1)
        self.assertIn("b-short: no value for slot sources", out["refused"])
        self.assertEqual(list(self.root.glob("evals/*/prompt.md")), [])


def grader(case):
    """A case's regex grader from its case.yaml: the single-quoted `pattern` and its `flags`."""
    text = (ROOT / "evals" / case / "case.yaml").read_text()
    pattern = re.search(r"^    pattern: '(.*)'$", text, re.M)[1].replace("''", "'")
    flags = re.search(r"^    flags: '(\w*)'$", text, re.M)
    return re.compile(pattern, (re.I if flags and "i" in flags[1] else 0)
                      | (re.M if flags and "m" in flags[1] else 0))


# One hand-written right and wrong answer per regex grader, laid out as a run might write them.
ANSWERS = {
    "p1-file-contract": (
        "## Decision gaps\n\n- **Journal format.** No source fixes it.\n  - Producer: #11\n"
        "  - Consumer: #12\n  - Options: JSON Lines (recommended); TSV.",
        "## Decision gaps\n\nNone.\n\n## Agent\n\n#11, #12, #13" + "\n" * 3 + " " * 400
        + "The journal is read and written by the tickets."),
    "p2-name-collision": (
        "1. **Subcommand name.**\n   #13 adds `quill quill`.\n   It collides with the tool's name.",
        "## Decision gaps\n\nNone.\n\n## Agent\n\n#11, #12, #13"),
    "p3-adr-contradiction": (
        "- **Journal format.**\n  - ADR 0001 says JSON Lines at `journal.jsonl`.\n"
        "  - The spec #10 says tab-separated lines at `journal.tsv`.\n  - They contradict.",
        "## Decision gaps\n\nNone: ADR 0001 fixes the journal.\n\n## Agent\n\n#11, #12, #13"),
    "p4-control": (
        "### Decision gaps\n\nNone.\n\n### Agent\n\n#11, #12, #13",
        "### Decision gaps\n\n1. **Shared reader.** Should `count` share the journal reader?"),
    "p5-human-verified": (
        "## Human-verified\n\n1. #13: \"easy to scan\" needs a person's judgement.",
        "## Human-verified\n\nNone.\n\n## Agent\n\n#11, #12, #13"),
    "p6-human": (
        "## Human\n\n1. #13: needs a Dropbox account and a registered Dropbox app.",
        "## Human-verified\n\n- #13: needs a Dropbox account.\n\n## Agent\n\n#11, #12"),
    "r1-unmet-criterion": (
        "Verdict: MUST-FIX\n\n1. #12 criterion 3: exit 3 when the journal file does not exist; the diff exits 0.",
        "CLEAN. No MUST-FIX findings."),
}

# Further shapes from review, as (case, answer, should pass).
SHAPES = [
    ("p4-control", "There are no hard-to-reverse gaps.", True),
    ("p4-control", "## Decision gaps\n\nThere are none.", True),
    ("p4-control", "Decision gaps: 0", True),
    ("p4-control", "Decision gaps: 1. Should `count` share the journal reader?", False),
    ("p5-human-verified", "| #13 | human-verified |", True),
    ("p5-human-verified", "#13 is human-verified.", True),
    ("p5-human-verified", "| #13 | agent |", False),
    ("p6-human", "| #13 | human |", True),
    ("p6-human", "#13 is human-verified.", False),
    ("p6-human", "## Human verified\n\n- #13: needs a Dropbox account.", False),
    ("p6-human", "| #13 | Human verified |", False),
    ("r1-unmet-criterion", "CLEAN. No MUST-FIX findings; #12 exits 3 as criterion 3 asks.", False),
    ("r1-unmet-criterion", "MUST-FIX: a style nit in the test names.", False),
]


class Graders(unittest.TestCase):
    def test_each_regex_grader_passes_a_right_answer_and_fails_a_wrong_one(self):
        for case, (right, wrong) in ANSWERS.items():
            with self.subTest(case):
                self.assertTrue(grader(case).search(right), "right answer fails")
                self.assertFalse(grader(case).search(wrong), "wrong answer passes")

    def test_each_review_shape_is_graded_as_written(self):
        for case, answer, passes in SHAPES:
            with self.subTest(case, answer=answer):
                self.assertEqual(bool(grader(case).search(answer)), passes)


if __name__ == "__main__":
    unittest.main()
