"""Deterministic checks on the model's output.

This is the layer that makes SPEC 7's guarantees real rather than aspirational.
Nothing here asks the model anything; it is all mechanical, which is also why
failing over to a different model (SPEC 9.3) is a non-event. See SPEC.md 10.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .prompt import CANARY

MIN_ANSWER_CHARS = 20
MIN_ABSTENTION_CHARS = 60
ABSTENTION_CLASSES_NEEDING_SUBSTANCE = {"contradiction", "silence", "undefined_term"}

# SPEC 4's table, enforced mechanically. The model's own classification is evidence
# against its own abstention flag: naming a contradiction and then ruling on it is the
# deviation SPEC 6.3 predicts, and it is detectable without judging the answer.
MUST_ABSTAIN = {"contradiction", "silence", "undefined_term"}
MUST_BE_DEFINITIVE = {"direct", "computed", "false_premise", "nonexistent_entity",
                      "general_specific"}

# A declared defect of one of these kinds cannot be answered definitively. Enforced on
# the conflict object rather than on question_class, because the model was observed
# reclassifying the question to escape the rule while still reporting the conflict.
UNRESOLVABLE_CONFLICTS = {"contradiction", "silence", "undefined_term", "ambiguous_scope"}

CITE_EXACT = re.compile(r"^§\d+(?:\.\d+)?$")
# Normalisation, tried in order. Both models were observed returning the id followed
# by the section's entire text, so a leading-anchored match comes first.
# The lookahead must reject a following digit, and a following dot ONLY when a digit
# comes after it. `(?![\d.])` would reject "§3.2." at the end of a sentence, which
# made the prose-reference check blind to any citation before a full stop.
_TAIL = r"(?!\d)(?!\.\d)"
_NORM = (
    re.compile(r"^\s*§?\s*(\d+(?:\.\d+)?)" + _TAIL),
    re.compile(r"§\s*(\d+(?:\.\d+)?)" + _TAIL),
    re.compile(r"(?:section|sec\.?|clause)\s+(\d+(?:\.\d+)?)" + _TAIL, re.IGNORECASE),
)
PROSE_REF = re.compile(r"§\s*(\d+(?:\.\d+)?)" + _TAIL)

# Only double quotes delimit a quotation. Treating ' as a delimiter made every
# apostrophe ("there's", "player's") open a bogus span, which produced misquotation
# reports on text the model never claimed to be quoting.
QUOTED_SPAN = re.compile(r"\"[^\"]*\"|\u201c[^\u201d]*\u201d")
# "one" is excluded: it is overwhelmingly a pronoun or article in English ("the
# authoritative one", "one of"), and an asserted quantity of 1 does not occur in
# practice. two..twenty as words are almost always quantities.
NUMBER_WORD = re.compile(
    r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b",
    re.IGNORECASE,
)
# Idiomatic uses that are not quantities being asserted.
NUMBER_WORD_OK_NEXT = {"of", "another", "time", "per", "or", "and"}
NUMBER_WORD_OK_PREV = {"no", "any", "each", "at", "as"}

MARKDOWN = re.compile(r"\*{1,3}|_{2,}|^#{1,6}\s+|^\s*[-*+]\s+", re.MULTILINE)


def _norm_quote(text: str) -> str:
    """Fold the differences that are not misquotation: whitespace, smart punctuation."""
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'),
                 ("\u2014", "-"), ("\u2013", "-"), ("\u2026", "...")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip().lower()


def misquotations(answer: str, rulebook, question: str | None = None) -> list[str]:
    """Quoted spans that do not appear in the rulebook.

    SPEC 11 asks the agent to quote the decisive clause, which creates the risk of a
    quotation that reads as authoritative and is not what the rulebook says. That is
    the worst failure mode available to a rules agent, and it is mechanically
    checkable. "..." is honoured as elision: each fragment must appear, in order.
    Short spans are skipped -- they are usually a single quoted term, not a claim
    about the text.
    """
    # The agent legitimately quotes the player's own words -- naming an injected claim
    # in order to disregard it (SPEC 8) requires reproducing it -- so the question is a
    # valid source for a quotation alongside the rulebook.
    haystack = _norm_quote(strip_markdown(rulebook.raw))
    if question:
        haystack += "\n" + _norm_quote(question)
    bad = []
    for match in QUOTED_SPAN.finditer(answer):
        span = match.group(0)[1:-1]
        # Punctuation placed inside the closing quote is a typographic convention.
        needle = _norm_quote(span).rstrip(",;:. ")
        if len(needle) < 25:
            continue
        position, ok = 0, True
        for fragment in [f.strip() for f in needle.split("...") if f.strip()]:
            found = haystack.find(fragment, position)
            if found < 0:
                ok = False
                break
            position = found + len(fragment)
        if not ok:
            bad.append(span[:80])
    return bad


@dataclass
class Problem:
    code: str
    detail: str
    hard: bool  # hard problems must never be emitted; soft ones are repair-worthy
    sections: tuple = ()  # sections the problem is about, for finalise's fallback


def normalise_citation(raw: str) -> str | None:
    """Extract a bare section id from whatever the model returned."""
    if not isinstance(raw, str):
        return None
    for pattern in _NORM:
        m = pattern.search(raw)
        if m:
            return f"§{m.group(1)}"
    return None


def strip_markdown(text: str) -> str:
    """Safe mechanical transform: the interface calls `answer` plain text."""
    return re.sub(r"[ \t]{2,}", " ", MARKDOWN.sub("", text)).strip()


WORD_TO_DIGIT = {
    "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
    "thirteen": "13", "fourteen": "14", "fifteen": "15", "sixteen": "16",
    "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20",
}


def digitise(answer: str) -> tuple[str, list[str]]:
    """Rewrite asserted number-words as digits, never inside a quotation.

    SPEC 11 requires digits and SPEC 10 holds that the validator enforces what the
    prompt only requests. Measured: the repair loop does not land this one -- it left
    the words in place on one probe question and introduced them on another -- so the
    transform is mechanical, like markdown stripping. It is meaning-preserving for a
    standalone cardinal, and quoted spans are excluded so a verbatim quotation of the
    rulebook (which spells its numbers as words) is never altered.
    """
    pieces = re.split(f"({QUOTED_SPAN.pattern})", answer)
    replaced: list[str] = []

    def swap(match):
        word = match.group(0)
        lower = word.lower()
        if lower not in WORD_TO_DIGIT:
            return word
        replaced.append(lower)
        return WORD_TO_DIGIT[lower]

    for i, piece in enumerate(pieces):
        if piece and not QUOTED_SPAN.fullmatch(piece):
            # Skip hyphenated ordinals ("twenty-first") and the idiomatic contexts
            # already exempted by the detector.
            pieces[i] = re.sub(r"\b(" + "|".join(WORD_TO_DIGIT) + r")\b(?!-)",
                               swap, piece, flags=re.IGNORECASE)
    return "".join(pieces), replaced


def _quantities(answer: str) -> set[str]:
    """Distinct numeric quantities asserted, ignoring section references."""
    return set(re.findall(r"(?<!\d)(\d+)(?!\d)", PROSE_REF.sub(" ", answer)))


def _number_words(answer: str) -> list[str]:
    """Number-words outside quoted spans, excluding idiomatic non-quantity uses."""
    # Markdown is stripped first: "**five**" does not tokenise as a word otherwise.
    unquoted = QUOTED_SPAN.sub(" ", strip_markdown(answer))
    lowered = re.findall(r"[A-Za-z]+", unquoted.lower())
    hits = []
    for i, word in enumerate(lowered):
        if not NUMBER_WORD.fullmatch(word):
            continue
        nxt = lowered[i + 1] if i + 1 < len(lowered) else ""
        prev = lowered[i - 1] if i else ""
        if nxt in NUMBER_WORD_OK_NEXT or prev in NUMBER_WORD_OK_PREV:
            continue
        hits.append(word)
    return hits


def check(data: dict, rulebook, question: str | None = None,
          register=None) -> list[Problem]:
    """Every SPEC 10 check. Returns problems; empty means the record is clean."""
    problems: list[Problem] = []

    answer = data.get("answer")
    abstained = data.get("abstained")
    citations = data.get("citations")
    qclass = data.get("question_class") or ""

    # 1. schema
    if not isinstance(answer, str) or not answer.strip():
        problems.append(Problem("schema", "answer missing or empty", True))
        answer = ""
    if not isinstance(abstained, bool):
        problems.append(Problem("schema", f"abstained is {type(abstained).__name__}, not bool", True))
        abstained = True
    if not isinstance(citations, list) or not all(isinstance(c, str) for c in citations):
        problems.append(Problem("schema", "citations is not a list of strings", True))
        citations = []

    # 2. citations exist in the parsed index
    normalised, invalid = [], []
    for raw in citations:
        sid = normalise_citation(raw)
        if sid and sid in rulebook.sections:
            normalised.append(sid)
        else:
            invalid.append(raw)
    if invalid:
        problems.append(Problem(
            "citation_not_in_rulebook",
            "these are not sections of the loaded rulebook: " + ", ".join(map(repr, invalid)),
            True,
        ))

    # 3. every prose reference is also a citation
    prose = {f"§{m.group(1)}" for m in PROSE_REF.finditer(answer)}
    dangling = sorted(prose - set(normalised))
    if dangling:
        problems.append(Problem(
            "prose_ref_not_cited",
            "the answer mentions " + ", ".join(dangling)
            + " but they are not in the citations array. To refer to a section that does"
              " not exist, write it in words with no § sign.",
            True,
        ))

    # 4. a definitive answer must rest on something
    if abstained is False and not normalised:
        problems.append(Problem(
            "definitive_without_citation",
            "abstained is false but no valid citation remains", True))

    # 5. length floors
    if answer.strip() and len(answer.strip()) < MIN_ANSWER_CHARS:
        problems.append(Problem(
            "too_short", f"answer is {len(answer.strip())} chars, floor is {MIN_ANSWER_CHARS}", True))
    if (abstained and qclass in ABSTENTION_CLASSES_NEEDING_SUBSTANCE
            and len(answer.strip()) < MIN_ABSTENTION_CHARS):
        problems.append(Problem(
            "abstention_not_substantive",
            f"a {qclass} abstention is {len(answer.strip())} chars, floor is "
            f"{MIN_ABSTENTION_CHARS}; name what is missing or in conflict and give the "
            "competing readings",
            False,
        ))

    # 6. declared-defect / abstention consistency
    conflict = data.get("conflict") if isinstance(data.get("conflict"), dict) else {}
    kind = conflict.get("kind") or "none"
    if (kind in UNRESOLVABLE_CONFLICTS and conflict.get("bears_on_answer")
            and abstained is False):
        problems.append(Problem(
            "ruled_on_declared_defect",
            f"conflict.kind is {kind} and bears_on_answer is true, so the rulebook does "
            "not settle this: set abstained true. A lean toward the better-supported "
            "reading is still an abstention. Do not reclassify the question or narrow a "
            "section's stated scope to escape this.",
            True,
        ))
    declared = [normalise_citation(x) for x in (conflict.get("sections") or [])
                if isinstance(x, str)]
    declared = [d for d in declared if d and d in rulebook.sections]
    missing = sorted(set(declared) - set(normalised))
    if missing and conflict.get("bears_on_answer"):
        problems.append(Problem(
            "conflict_sections_not_cited",
            "the conflict you declared rests on " + ", ".join(missing)
            + ", so those sections must appear in the citations array: an abstention "
              "cites the sections it found silent or conflicting",
            True,
        ))
    if qclass in MUST_ABSTAIN and abstained is False:
        problems.append(Problem(
            "contradiction_ruled_on" if qclass == "contradiction" else "gap_ruled_on",
            f"question_class is {qclass}, which cannot be answered definitively: set "
            "abstained true. A lean toward the better-supported reading is still an "
            "abstention, not a ruling.",
            True,
        ))
    if qclass in MUST_BE_DEFINITIVE and abstained is True:
        problems.append(Problem(
            "abstained_on_answerable",
            f"question_class is {qclass}, which the rulebook settles: either abstain "
            "with a class that justifies it, or answer definitively.",
            False,  # soft: never coerce toward false confidence
        ))

    # 6a. a contradiction the rulebook demonstrably contains, which this answer ruled
    # on anyway. Established independently of the model (defects.py), because the
    # model's own declaration is evadable -- it has denied this outright with
    # question_class=direct and conflict.kind=none.
    #
    # All three conditions are required. Term match alone would fire on any scoring
    # question; citing both halves alone would fire on Q6, which cites both sections to
    # correct a false premise about a different suit and rightly answers definitively.
    # The register is generated, not verified, so it can carry a general/specific pair
    # as if it were indeterminate. The per-question declaration vetoes it: the model is
    # reliable at spotting an exception-carve (§6.4 from §3.3, §5.1 from §4.4) and
    # unreliable only at admitting a conflict it would rather resolve. So the register
    # wins when the answer denies a conflict, and the answer wins when it identifies
    # the relationship as general/specific over the same sections.
    vetoed = (kind == "general_specific" and set(declared) & set().union(
        *(k.sections for k in register)) if register else False)
    for known in (register or []):
        if (abstained is False and not vetoed and question and known.bears_on(question)
                and known.sections <= set(normalised)):
            problems.append(Problem(
                "denied_known_contradiction",
                f"an independent audit of this rulebook found "
                f"{' and '.join(sorted(known.sections))} to be in contradiction: "
                f"{known.note} That bears on this question, so the rulebook does not "
                "settle it. Give both readings with the figure each produces, and set "
                "abstained true.",
                True,
                tuple(sorted(known.sections)),
            ))

    # 6b. a numeric contradiction must show both figures.
    # SPEC 5 requires the competing readings AND their consequences. Prompt-level
    # instruction was measured at 2/5 compliance, and strengthening the wording made
    # the abstention itself worse (5/5 -> 2/5), so this is enforced here and left soft
    # so the repair loop does the work without a destructive downgrade.
    # Gated on the answer already containing a quantity: a non-numeric contradiction
    # has no second figure to give.
    if (kind == "contradiction" and conflict.get("bears_on_answer")
            and len(_quantities(answer)) == 1):
        problems.append(Problem(
            "contradiction_missing_alternative",
            "this contradiction changes a quantity, so state the figure BOTH readings "
            "produce, as digits -- a player has to be able to read both candidate "
            "answers off the reply and pick one",
            False,
        ))

    # 7. quotations are verbatim
    for span in misquotations(answer, rulebook, question):
        problems.append(Problem(
            "misquotation",
            f"this quoted text is not in the rulebook: {span!r}. Quote verbatim or "
            "paraphrase without quotation marks.",
            True,
        ))

    # 8. canary
    if CANARY in answer:
        problems.append(Problem("canary_leak", "the answer contains the secret marker", True))

    # 9. digits (soft: repair, then accept). See SPEC 11.2.
    # An earlier version fired only when the answer contained no digit at all; a stray
    # number anywhere ("42" quoted from an injected question) defeated it. Pronoun noise
    # is handled by excluding "one" from NUMBER_WORD instead.
    words = _number_words(answer)
    if words:
        problems.append(Problem(
            "quantity_as_word",
            "write quantities as digits, not words: " + ", ".join(sorted(set(words))),
            False,
        ))

    # 10. markdown (soft: stripped mechanically)
    if MARKDOWN.search(answer):
        problems.append(Problem("markdown", "answer contains markdown formatting", False))

    return problems


def repair_note(problems: list[Problem]) -> str:
    return " ".join(f"{p.code}: {p.detail}" for p in problems)


def finalise(qid: str, data: dict, rulebook, problems: list[Problem]) -> tuple[dict, list[str]]:
    """Build the emitted record, applying SPEC 7 and 10 fallbacks to what remains."""
    notes: list[str] = []
    answer = strip_markdown(str(data.get("answer") or ""))
    answer, digitised = digitise(answer)
    abstained = data.get("abstained")
    abstained = True if not isinstance(abstained, bool) else abstained

    citations, dropped = [], []
    for raw in data.get("citations") or []:
        sid = normalise_citation(raw) if isinstance(raw, str) else None
        if sid and sid in rulebook.sections:
            citations.append(sid)
        else:
            dropped.append(raw)
    citations = rulebook.sort_ids(citations)
    if dropped:
        notes.append(f"dropped {len(dropped)} invalid citation(s): {dropped}")

    if digitised:
        notes.append(f"rewrote quantity word(s) as digits: {sorted(set(digitised))}")

    codes = {p.code for p in problems}

    # A leak is the one failure where the answer itself cannot be emitted.
    if "canary_leak" in codes or CANARY in answer:
        answer = ("I answer Harbourmaster rules questions from the rulebook, and cannot "
                  "share my instructions.")
        abstained, citations = True, []
        notes.append("canary leak: answer replaced and downgraded to abstention")

    # Strip any prose reference that survived to a section we are not citing, so the
    # emitted record cannot carry a dangling id.
    dangling = sorted({f"§{m.group(1)}" for m in PROSE_REF.finditer(answer)} - set(citations))
    real = [sid for sid in dangling if sid in rulebook.sections]
    unreal = [sid for sid in dangling if sid not in rulebook.sections]
    if real:
        # The answer genuinely leans on these, so cite them rather than editing the
        # text. Rewriting is not safe here: a dangling ref can sit inside a quotation,
        # and mangling a quotation is worse than an over-broad citation list.
        citations = rulebook.sort_ids(citations + real)
        notes.append(f"added prose-referenced section(s) to citations: {real}")
    for sid in unreal:
        answer = re.sub(re.escape(sid) + _TAIL, "section " + sid[1:], answer)
    if unreal:
        notes.append(f"de-sigilled reference(s) to nonexistent section(s): {unreal}")

    denied = next((p for p in problems if p.code == "denied_known_contradiction"), None)
    if denied and abstained is False:
        abstained = True
        citations = rulebook.sort_ids(list(citations) + list(denied.sections))
        answer = (answer.rstrip().rstrip(".") + ". Note: "
                  + " and ".join(denied.sections)
                  + " contradict each other on this point, so the rulebook does not "
                    "settle it definitively and the figure above is only one reading.")
        notes.append(f"forced abstention: ruled on the known contradiction "
                     f"{list(denied.sections)} after repair")

    # Coercion is one-directional by design: an identified contradiction or gap is
    # forced to abstain, but a declined answer is never forced into confidence.
    _conflict = data.get("conflict") if isinstance(data.get("conflict"), dict) else {}
    _kind = _conflict.get("kind") or "none"
    if abstained is False and (
        data.get("question_class") in MUST_ABSTAIN
        or (_kind in UNRESOLVABLE_CONFLICTS and _conflict.get("bears_on_answer"))
    ):
        abstained = True
        notes.append(
            f"forced abstention: declared {_kind} defect bearing on the answer "
            f"(class={data.get('question_class')}) with abstained false")

    if abstained is False and not citations:
        answer = (answer + " (The agent could not ground this answer in any section of "
                  "the rulebook, so it is not offered as definitive.)").strip()
        abstained = True
        notes.append("downgraded to abstention: no valid citation")

    if len(answer.strip()) < MIN_ANSWER_CHARS:
        answer = ("The agent could not produce a usable answer to this question from the "
                  "rulebook.")
        abstained, citations = True, []
        notes.append("downgraded to abstention: answer below the length floor")

    return {"id": qid, "answer": answer, "citations": citations,
            "abstained": bool(abstained)}, notes
