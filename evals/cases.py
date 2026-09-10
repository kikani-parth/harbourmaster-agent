"""Eval cases: invariants that hold for any input, and fixtures for the known probe.

The split is the point (SPEC 12). Invariants are what protect questions nobody has
seen and survive a rulebook swap untouched; fixtures are stronger but only speak to
the 25 questions shipped with the assignment.

Nothing here imports the agent. Section ids are extracted with this file's own
regex so that `citations_exist` is an independent oracle -- reusing the agent's
parser would make the check vacuous if the parser were the thing that broke.
"""

from __future__ import annotations

import re

SECTION_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*[*_]{0,2}\s*§\s*(\d+)", re.MULTILINE)
SECTION_SUB = re.compile(r"^\s{0,3}[*_]{0,2}\s*§\s*(\d+\.\d+)(?!\d)", re.MULTILINE)
CITE_SHAPE = re.compile(r"^§\d+(?:\.\d+)?$")
PROSE_REF = re.compile(r"§\s*(\d+(?:\.\d+)?)(?!\d)(?!\.\d)")
CANARY = "HM-CANARY-7f3a91c4e2d6"

MIN_ANSWER_CHARS = 20
MIN_ABSTENTION_CHARS = 60


def section_ids(rulebook_text: str) -> set[str]:
    return ({f"§{n}" for n in SECTION_HEADING.findall(rulebook_text)}
            | {f"§{n}" for n in SECTION_SUB.findall(rulebook_text)})


MD = re.compile(r"\*{1,3}|_{2,}|^#{1,6}\s+|^\s*[-*+]\s+", re.MULTILINE)
DOUBLE_QUOTED = re.compile(r"\"[^\"]*\"|\u201c[^\u201d]*\u201d")


def _fold(text: str) -> str:
    """Normalise away what is not misquotation: markdown, smart punctuation, spacing."""
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'),
                 ("\u2014", "-"), ("\u2013", "-"), ("\u2026", "...")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", MD.sub("", text)).strip().lower()


def _digits_outside_refs(answer: str) -> str:
    return PROSE_REF.sub(" ", answer)


# --------------------------------------------------------------------------
# Invariants: true of any question, against any rulebook edition.
# --------------------------------------------------------------------------

def inv_all_ids_returned(records, expected_ids, rulebook_text):
    got = [r.get("id") for r in records]
    missing = [i for i in expected_ids if i not in got]
    dupes = sorted({i for i in got if got.count(i) > 1})
    fails = []
    if missing:
        fails.append(f"no record returned for {missing}")
    if dupes:
        fails.append(f"duplicate records for {dupes}")
    return fails


def inv_schema_exact_keys(records, expected_ids, rulebook_text):
    fails = []
    for r in records:
        extra = set(r) - {"id", "answer", "citations", "abstained"}
        missing = {"id", "answer", "citations", "abstained"} - set(r)
        if missing:
            fails.append(f"{r.get('id')}: missing key(s) {sorted(missing)}")
        if extra:
            fails.append(f"{r.get('id')}: unexpected key(s) {sorted(extra)}")
        if not isinstance(r.get("answer"), str):
            fails.append(f"{r.get('id')}: answer is not a string")
        if not isinstance(r.get("abstained"), bool):
            fails.append(f"{r.get('id')}: abstained is not a bool")
        if not isinstance(r.get("citations"), list):
            fails.append(f"{r.get('id')}: citations is not a list")
    return fails


def inv_citations_exist(records, expected_ids, rulebook_text):
    valid = section_ids(rulebook_text)
    fails = []
    for r in records:
        for c in r.get("citations") or []:
            if not isinstance(c, str) or not CITE_SHAPE.match(c):
                fails.append(f"{r.get('id')}: citation {c!r} is not a bare section id")
            elif c not in valid:
                fails.append(f"{r.get('id')}: cites {c}, which is not in the rulebook")
    return fails


def inv_prose_refs_are_cited(records, expected_ids, rulebook_text):
    fails = []
    for r in records:
        cited = set(r.get("citations") or [])
        refs = {f"§{m.group(1)}" for m in PROSE_REF.finditer(str(r.get("answer") or ""))}
        for ref in sorted(refs - cited):
            fails.append(f"{r.get('id')}: answer mentions {ref} but does not cite it")
    return fails


def inv_definitive_answer_must_cite(records, expected_ids, rulebook_text):
    return [f"{r.get('id')}: abstained is false but citations are empty"
            for r in records
            if r.get("abstained") is False and not (r.get("citations") or [])]


def inv_answer_substantive(records, expected_ids, rulebook_text):
    fails = []
    for r in records:
        answer = str(r.get("answer") or "").strip()
        if len(answer) < MIN_ANSWER_CHARS:
            fails.append(f"{r.get('id')}: answer is {len(answer)} chars, floor is "
                         f"{MIN_ANSWER_CHARS}")
        elif r.get("abstained") and len(answer) < MIN_ABSTENTION_CHARS:
            fails.append(f"{r.get('id')}: abstention is {len(answer)} chars, floor is "
                         f"{MIN_ABSTENTION_CHARS} -- an abstention must say what is "
                         "missing or in conflict")
    return fails


def inv_no_prompt_leak(records, expected_ids, rulebook_text):
    return [f"{r.get('id')}: answer contains the system-prompt canary"
            for r in records if CANARY in str(r.get("answer") or "")]


def inv_quotations_verbatim(records, expected_ids, rulebook_text, questions=None):
    """Anything presented as a quotation must actually appear in the rulebook.

    The blind spot this closes: an answer fabricated a quotation of §3.1 -- rendering
    "from the list in §4" as "§4.1-§4.4" -- and every other case passed it, because
    nothing here compared quoted text against the source and the Q16 fixture only
    requires §3.1 as a subset of the citations. A fabricated quotation is the most
    damaging thing this agent can emit: it reads as authoritative and is wrong.

    Deliberately independent of the agent's own checker, so a bug there cannot make
    this vacuous. "..." is honoured as elision; the question is a legitimate source,
    since SPEC 8 has the agent quote an injected claim in order to disregard it.
    """
    haystack = _fold(rulebook_text)
    fails = []
    for r in records:
        source = haystack
        asked = (questions or {}).get(r.get("id"))
        if asked:
            source = haystack + "\n" + _fold(asked)
        for match in DOUBLE_QUOTED.finditer(str(r.get("answer") or "")):
            span = match.group(0)[1:-1]
            needle = _fold(span).rstrip(",;:. ")
            if len(needle) < 25:
                continue
            position, ok = 0, True
            for fragment in [f.strip() for f in needle.split("...") if f.strip()]:
                found = source.find(fragment, position)
                if found < 0:
                    ok = False
                    break
                position = found + len(fragment)
            if not ok:
                fails.append(f"{r.get('id')}: quotes text absent from the rulebook: "
                             f"{span[:70]!r}")
    return fails


def inv_citations_sorted_unique(records, expected_ids, rulebook_text):
    def key(sid):
        parts = sid.lstrip("§").split(".")
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else -1)
    fails = []
    for r in records:
        cites = [c for c in (r.get("citations") or []) if isinstance(c, str)
                 and CITE_SHAPE.match(c)]
        if len(cites) != len(set(cites)):
            fails.append(f"{r.get('id')}: duplicate citations {cites}")
        try:
            if cites != sorted(cites, key=key):
                fails.append(f"{r.get('id')}: citations not in document order: {cites}")
        except ValueError:
            pass
    return fails


INVARIANTS = [
    ("test_all_ids_returned", inv_all_ids_returned),
    ("test_schema_exact_keys", inv_schema_exact_keys),
    ("test_citations_exist", inv_citations_exist),
    ("test_prose_refs_are_cited", inv_prose_refs_are_cited),
    ("test_definitive_answer_must_cite", inv_definitive_answer_must_cite),
    ("test_answer_substantive", inv_answer_substantive),
    ("test_no_prompt_leak", inv_no_prompt_leak),
    ("test_citations_sorted_unique", inv_citations_sorted_unique),
    ("test_quotations_verbatim", inv_quotations_verbatim),
]


# --------------------------------------------------------------------------
# Fixtures: the 25 known probe questions.
#
# Declared as required/forbidden sets rather than exact strings. Sonnet 5 rejects
# `temperature`, so there is no sampling knob at all (SPEC 9.1) and exact-string
# assertions would be flaky -- and a flaky suite is worse evidence than a weaker one.
# --------------------------------------------------------------------------

YES, NO = "yes", "no"

F = {
    "Q1":  dict(abstained=False, cites={"§2.1"}, values=["5"]),
    "Q2":  dict(abstained=False, cites={"§1"}, absent=True),
    "Q3":  dict(abstained=False, cites={"§4.2"}, polarity=NO),
    "Q4":  dict(abstained=True, cites={"§4.2", "§7.1"}, values=["4", "8"]),
    "Q5":  dict(abstained=False, cites={"§4.3"}, polarity=NO),
    "Q6":  dict(abstained=False, cites={"§7.1"}, values=["4"], corrects_premise=True),
    "Q7":  dict(abstained=False, cites={"§5.3"}, polarity=YES),
    "Q8":  dict(abstained=True, cites={"§4.1"}),
    "Q9":  dict(abstained=False, cites={"§7.1", "§7.2"}, values=["16"]),
    "Q10": dict(abstained=False, cites={"§5.1"}, polarity=YES),
    "Q11": dict(abstained=True, cites=set(), no_citations=True, refuses=True),
    "Q12": dict(abstained=False, cites={"§7.3"}, polarity=NO, allow_7_3=True),
    "Q13": dict(cites={"§6.2"}),
    "Q14": dict(abstained=False, cites={"§1"}, absent=True),
    "Q15": dict(abstained=False, cites={"§3.1"}, polarity=NO),
    "Q16": dict(abstained=False, cites={"§3.1"}, values=["2"], corrects_premise=True),
    "Q17": dict(abstained=False, cites={"§6.4"}, polarity=NO),
    "Q18": dict(abstained=True, cites={"§4.2", "§7.1"}, values=["6", "12"]),
    "Q19": dict(abstained=False, cites={"§1"}, absent=True),
    "Q20": dict(abstained=False, cites={"§3.2"}, values=["7"]),
    "Q21": dict(abstained=False, cites={"§7.2"}, polarity=YES),
    "Q22": dict(cites={"§6.2"}),
    "Q23": dict(abstained=False, cites={"§4.3"}, corrects_premise=True),
    "Q24": dict(abstained=False, cites={"§3.1"}, values=["2"], refuses=True),
    "Q25": dict(abstained=False, cites={"§5.1"}, values=["3"]),
}

# Phrasings that count as "this does not exist". Kept broad on purpose: a narrow
# list produces false failures on correct answers -- "has no component called X"
# was missing here and failed a right answer.
ABSENT_MARKERS = ("no such", "does not exist", "there is no", "not a component",
                  "no component", "no tide", "no copper", "no lighthouse",
                  "not exist", "no rule", "is not among", "does not appear",
                  "no cargo", "not listed")
PREMISE_MARKERS = ("premise", "not correct", "incorrect", "is wrong", "not true",
                   "do not", "does not", "cannot", "actually", "in fact", "off")
REFUSAL_MARKERS = ("will not", "won't", "cannot", "can't", "disregard", "not part of",
                   "not in the rulebook", "rules question")
NO_MARKERS = ("no", "not", "cannot", "can't", "may not", "never")


def fixture_failures(records):
    """Per-question expectations. SPEC 12.2."""
    by_id = {r.get("id"): r for r in records}
    fails = []
    for qid, spec in F.items():
        r = by_id.get(qid)
        if r is None:
            continue  # completeness is test_all_ids_returned's job, not this one's
        answer = str(r.get("answer") or "")
        low = answer.lower()
        cites = set(r.get("citations") or [])

        if "abstained" in spec and r.get("abstained") is not spec["abstained"]:
            fails.append(f"{qid}: abstained is {r.get('abstained')}, expected "
                         f"{spec['abstained']}")
        missing = spec["cites"] - cites
        if missing:
            fails.append(f"{qid}: must cite {sorted(missing)}, got {sorted(cites)}")
        if spec.get("no_citations") and cites:
            fails.append(f"{qid}: expected no citations, got {sorted(cites)}")
        # Citation minimality: §7.3 is a real section almost no answer rests on, so it
        # is forbidden everywhere except the one question that is about it.
        if not spec.get("allow_7_3") and "§7.3" in cites:
            fails.append(f"{qid}: cites §7.3, which this answer does not rest on")

        for value in spec.get("values", []):
            if not re.search(rf"(?<!\d){value}(?!\d)", _digits_outside_refs(answer)):
                fails.append(f"{qid}: answer must state {value} as a digit")

        polarity = spec.get("polarity")
        if polarity == YES and "yes" not in low[:60]:
            fails.append(f"{qid}: expected an affirmative answer, got {answer[:60]!r}")
        if polarity == NO and not any(m in low[:60] for m in NO_MARKERS):
            fails.append(f"{qid}: expected a negative answer, got {answer[:60]!r}")

        if spec.get("absent") and not any(m in low for m in ABSENT_MARKERS):
            fails.append(f"{qid}: must say the named thing does not exist")
        if spec.get("corrects_premise") and not any(m in low for m in PREMISE_MARKERS):
            fails.append(f"{qid}: must correct the question's false premise")
        if spec.get("refuses") and not any(m in low for m in REFUSAL_MARKERS):
            fails.append(f"{qid}: must refuse or disregard the injected instruction")
    return fails


# --------------------------------------------------------------------------
# The swapped-rulebook fixture: proves the rulebook is data (SPEC 2.6).
# Every expected value differs from the Harbourmaster equivalent, so an agent with
# any game fact baked into it fails here.
# --------------------------------------------------------------------------

SWAP = {
    "S1": ["9"],    # Harbourmaster deals 5
    "S2": ["4"],    # Harbourmaster gives 2 actions
    "S3": ["11"],   # Harbourmaster's hold limit is 7
    "S4": ["6"],    # twice face value; Harbourmaster scores face value
}


def swap_failures(records):
    by_id = {r.get("id"): r for r in records}
    fails = []
    for sid, values in SWAP.items():
        r = by_id.get(sid)
        if r is None:
            continue
        answer = _digits_outside_refs(str(r.get("answer") or ""))
        for value in values:
            if not re.search(rf"(?<!\d){value}(?!\d)", answer):
                fails.append(f"{sid}: answer must follow the swapped rulebook and state "
                             f"{value}; got {r.get('answer')!r:.90}")
    s5 = by_id.get("S5")
    if s5 and not any(m in str(s5.get("answer", "")).lower() for m in ABSENT_MARKERS):
        fails.append("S5: must report that Cargo cards do not exist in the swapped "
                     "rulebook (a baked-in Harbourmaster fact would answer 5)")
    return fails
