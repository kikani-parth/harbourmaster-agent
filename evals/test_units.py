"""Unit tests for two internals the run.sh-driven cases cannot reach.

These import the agent directly, which the agent-behaviour cases in `cases.py`
deliberately never do (SPEC 12: `evals.sh` must exercise the agent only through
`./run.sh`, or the mutation step tests nothing). They are reported as a separate
group for that reason -- a mutation corrupts run.sh's output and cannot affect
these, so they are expected to pass in every mutation block.

Both targets are otherwise untested:
  - the parser's `word-form` tolerance-ladder variant, which no shipped rulebook
    exercises, so a regression in it would be invisible until an edition needed it;
  - `salvage_tool_leak`, which recovers a real Sonnet 5 serialisation fault that
    `strict` would have prevented (SPEC 9.2) and which fired 4 times in a 42-call
    probe run.
"""

from __future__ import annotations

import io
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from harbourmaster import rulebook  # noqa: E402
from harbourmaster.model import salvage_tool_leak  # noqa: E402

QUIET = io.StringIO()

WORD_FORM = """\
# BELLFOUNDER — Official Rules (v1)

*A word-form rulebook, for the parser's tolerance ladder.*

---

## Section 1 Components

- 24 **Bell cards** in three suits — Bronze, Iron, Silver
- 6 **Tower tiles**

## Section 2 Setup

Section 2.1 Deal seven Bell cards to each player.

Section 2.2 Place three Tower tiles in a row.

## Section 3 Scoring

Section 3.1 Score each Bell card using the table below.

| Suit | Points |
|---|---|
| Bronze | 1 |
| Iron | 2 |
| Silver | 3 |

Section 3.2 A player who rings three Bells scores 4 points.
"""


def load_text(text: str):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    return rulebook.load(path, log=QUIET)


class WordFormVariant(unittest.TestCase):
    def test_selected_and_discovers_both_levels(self):
        rb = load_text(WORD_FORM)
        self.assertEqual(rb.variant, "word-form")
        self.assertEqual(
            rb.ids, ["§1", "§2", "§2.1", "§2.2", "§3", "§3.1", "§3.2"])

    def test_heading_title_captured(self):
        rb = load_text(WORD_FORM)
        self.assertEqual(rb.sections["§1"].title, "Components")
        self.assertEqual(rb.sections["§3"].title, "Scoring")

    def test_case_insensitive(self):
        rb = load_text(WORD_FORM.replace("## Section 1", "## SECTION 1")
                                .replace("Section 2.1", "section 2.1"))
        self.assertEqual(rb.variant, "word-form")
        self.assertIn("§1", rb.sections)
        self.assertIn("§2.1", rb.sections)

    def test_trailing_table_travels_with_its_subsection(self):
        # The same property the sigil variant needs: a scoring question has nothing
        # to cite if the table detaches from the subsection that introduces it.
        rb = load_text(WORD_FORM)
        text = rb.sections["§3.1"].text
        self.assertIn("| Bronze | 1 |", text)
        self.assertIn("| Silver | 3 |", text)
        self.assertNotIn("rings three Bells", text)  # stops at §3.2

    def test_bullet_list_travels_with_its_section(self):
        rb = load_text(WORD_FORM)
        self.assertIn("24 **Bell cards**", rb.sections["§1"].text)

    def test_sigil_variant_wins_when_the_sigil_is_present(self):
        # Ladder order matters: the real rulebook must never be read as word-form.
        rb = rulebook.load("RULEBOOK.md", log=QUIET)
        self.assertEqual(rb.variant, "sigil")

    def test_refused_when_subsections_use_a_third_convention(self):
        # Headings parse, subsections do not, and the sigil is absent -- so only the
        # unparsed-outline guard can see it. This is the word-form twin of the
        # partial parse that silently succeeded before that guard existed.
        broken = WORD_FORM.replace("Section 2.1", "Rule 2.1") \
                          .replace("Section 2.2", "Rule 2.2") \
                          .replace("Section 3.1", "Rule 3.1") \
                          .replace("Section 3.2", "Rule 3.2")
        with self.assertRaises(rulebook.RulebookError) as caught:
            load_text(broken)
        self.assertIn("did not parse as sections", caught.exception.diagnostic)


class SalvageToolLeak(unittest.TestCase):
    # Verbatim shape observed from Sonnet 5: the closing tag and every parameter
    # after it land inside the value of `answer`, and `citations` never arrives.
    LEAKED = {
        "answer": (
            'You score 6 points. Spice scores at face value per §7.1.'
            '</answer>\n<parameter name="citations">["§7.1", "§4.2"]'
        ),
        "abstained": True,
        "question_class": "contradiction",
    }

    def test_noop_on_clean_payload(self):
        clean = {"answer": "Each player starts with 5 Cargo cards.",
                 "citations": ["§2.1"], "abstained": False}
        self.assertEqual(salvage_tool_leak(dict(clean)), clean)

    def test_recovers_the_leaked_citations(self):
        out = salvage_tool_leak(dict(self.LEAKED))
        self.assertEqual(out["citations"], ["§7.1", "§4.2"])

    def test_answer_truncated_at_the_leak_boundary(self):
        out = salvage_tool_leak(dict(self.LEAKED))
        self.assertEqual(
            out["answer"],
            "You score 6 points. Spice scores at face value per §7.1.")
        self.assertNotIn("<parameter", out["answer"])
        self.assertNotIn("</answer>", out["answer"])

    def test_preserves_fields_that_arrived_properly(self):
        out = salvage_tool_leak(dict(self.LEAKED))
        self.assertIs(out["abstained"], True)
        self.assertEqual(out["question_class"], "contradiction")

    def test_does_not_overwrite_a_populated_field(self):
        data = dict(self.LEAKED, citations=["§9.9"])
        self.assertEqual(salvage_tool_leak(data)["citations"], ["§9.9"])

    def test_parses_bool_and_nested_json_values(self):
        data = {"answer": 'Text.</answer>\n'
                          '<parameter name="abstained">true</parameter>\n'
                          '<parameter name="conflict">{"kind": "contradiction"}</parameter>'}
        out = salvage_tool_leak(data)
        self.assertIs(out["abstained"], True)
        self.assertEqual(out["conflict"], {"kind": "contradiction"})

    def test_bare_string_value_survives_unparseable_json(self):
        data = {"answer": 'Text.</answer>\n'
                          '<parameter name="question_class">direct</parameter>'}
        self.assertEqual(salvage_tool_leak(data)["question_class"], "direct")

    def test_tolerates_hostile_and_malformed_input(self):
        for bad in (None, [], "a string", 42):
            self.assertEqual(salvage_tool_leak(bad), bad)
        self.assertEqual(salvage_tool_leak({"answer": None}), {"answer": None})
        # A question that merely mentions the tag must not be treated as a leak.
        quoted = {"answer": 'The player asked about "<parameter name=x>" literally.',
                  "citations": ["§1"]}
        self.assertEqual(salvage_tool_leak(dict(quoted)), quoted)


def failures() -> list[str]:
    """Run both cases and return one message per failure, for evals/runner.py."""
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    out = []
    for case, trace in result.failures + result.errors:
        last = [ln for ln in trace.strip().splitlines() if ln.strip()][-1]
        out.append(f"{case.id().rsplit('.', 2)[-2]}.{case.id().rsplit('.', 1)[-1]}: {last}")
    return out


if __name__ == "__main__":
    unittest.main(verbosity=2)
