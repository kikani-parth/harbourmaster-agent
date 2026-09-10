"""Derive the rulebook's contradictions once, from the rulebook.

SPEC 6.2 says a contradiction abstains, and SPEC 10 enforces that on the model's own
declaration. Measured: the declaration is evadable -- asked about Spice, Sonnet 5 has
returned `question_class=contradiction` (caught), then `computed` with the conflict
declared (caught), then `direct` with `conflict.kind=none`, denying the contradiction
outright. Nothing keyed on what the model says about itself can catch the third.

So the contradiction is established independently, from the rulebook, before any
question is answered: one call per edition, cached by the rulebook's SHA-256. This is
still pure data -- nothing about Spice appears here, the register is whatever the
loaded file yields, and a new edition's hash produces a fresh analysis automatically.
"""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass

ANALYSIS_VERSION = "6"
TOOL_NAME = "report_contradictions"

_SYSTEM = """\
You are auditing a board-game rulebook for internal contradictions. You are not
answering rules questions.

Report only pairs of sections that CANNOT BOTH BE TRUE. Two sections that both hold at
once are not a contradiction, and the most common mistake here is reporting one of
those. In particular, do NOT report:

- a specific rule that carves an exception from a general one (both hold: the general
  rule applies except where the specific one says otherwise);
- a section that is merely silent on something another section covers;
- a term used without a definition;
- two sections that are simply about different things;
- a cap on a single action mistaken for a cap on an accumulated total. A rule limiting
  what one action may move is not a rule limiting what may be held or accumulated over
  several actions, and the two do not contradict.

Restrict yourself to what the text SAYS. Do not report a contradiction that depends on
reasoning about what is reachable in play -- that one provision would be unusable given
another, that a limit makes an allowance pointless. Those are inferences about the game,
and they are where invented contradictions come from.

A contradiction is two provisions of equal specificity, about the same subject, that
give incompatible results for the same situation.

For each one report:
- sections: the section ids involved, exactly as written in the list below.
- topic_terms: the words a player's question would use to land on this contradiction.
  Take them from the rulebook's own vocabulary -- a suit name, a component, an action.
  These decide whether the contradiction bears on a given question, so be precise: a
  contradiction about how one cargo suit scores must list that suit, not "scoring".
- note: one sentence on why the two cannot both hold.

If the rulebook contains no contradictions, return an empty list. An invented
contradiction is worse than a missed one: it would force the agent to decline a
question the rulebook actually settles.

You may reference only these section ids:

{ids}

## The rulebook

{rulebook}
"""

_TOOL = {
    "tools": [{
        "toolSpec": {
            "name": TOOL_NAME,
            "description": "Report the rulebook's internal contradictions.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "contradictions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sections": {"type": "array", "items": {"type": "string"}},
                                "topic_terms": {"type": "array", "items": {"type": "string"}},
                                "note": {"type": "string"},
                            },
                            "required": ["sections", "topic_terms", "note"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["contradictions"],
                "additionalProperties": False,
            }},
        }
    }],
    "toolChoice": {"tool": {"name": TOOL_NAME}},
}


# NOT verified by a second model call. Three framings were tried -- "can both hold",
# a rebalanced version of it, and "does the rulebook determine a single answer" -- and
# all three reconciled the one contradiction this rulebook actually has, variously as
# base-table-plus-multiplier and as flavour text. Each dropped the true positive 3/3
# while dropping false positives 3/3, which empties the register and is worse than no
# gate at all. Asked in the abstract about two section ids, the model theorises about
# what each section is "for"; asked a concrete question, the answering path declares the
# same conflict reliably (measured 5/5). The gate is therefore left out and false
# positives are contained downstream instead -- see the three conditions in
# validate.check, and the residual risk noted in SPEC 6.2.

@dataclass(frozen=True)
class Contradiction:
    sections: frozenset[str]
    terms: tuple[str, ...]
    note: str

    def bears_on(self, question: str) -> bool:
        """True if a question's wording lands on this contradiction's subject."""
        low = question.lower()
        return any(re.search(rf"\b{re.escape(t.lower())}\b", low)
                   for t in self.terms if t.strip())


def system_text(rulebook) -> str:
    return _SYSTEM.format(ids=" ".join(rulebook.ids), rulebook=rulebook.raw.strip())


def _clean(raw, rulebook) -> list[Contradiction]:
    """Keep only well-formed pairs naming real sections. Junk is dropped, not guessed."""
    from .validate import normalise_citation

    out: list[Contradiction] = []
    for item in (raw or []):
        if not isinstance(item, dict):
            continue
        ids = {normalise_citation(s) for s in (item.get("sections") or [])
               if isinstance(s, str)}
        ids = {i for i in ids if i and i in rulebook.sections}
        terms = tuple(t for t in (item.get("topic_terms") or [])
                      if isinstance(t, str) and t.strip())
        # A pair needs two real sections and at least one term, or it can neither be
        # located in the rulebook nor matched to a question.
        if len(ids) >= 2 and terms:
            out.append(Contradiction(frozenset(ids), terms, str(item.get("note") or "")))
    return out


def _consensus(passes, rulebook, *, log) -> list[dict]:
    """Keep only candidates both audits found, matched on their section set.

    A partial filter, not a guarantee: it has dropped an invented pair, and it has also
    let a plain general/specific pair through when both passes made the same mistake.
    """
    seen = [{frozenset(c.sections): c for c in _clean(p.get("contradictions"), rulebook)}
            for p in passes]
    agreed, dropped = [], []
    for key, first in seen[0].items():
        if all(key in s for s in seen[1:]):
            terms = tuple(dict.fromkeys(t for s in seen for t in s[key].terms))
            agreed.append({"sections": sorted(key), "topic_terms": list(terms),
                           "note": first.note})
        else:
            dropped.append(sorted(key))
    dropped += [sorted(k) for k in seen[1].keys() - seen[0].keys()]
    for pair in dropped:
        print(f"contradictions: dropped {pair} -- found by only 1 of 2 audits", file=log)
    return agreed


def register(client, rulebook, *, log) -> list[Contradiction]:
    """The rulebook's contradictions. One model call per edition, then cached."""
    cache = client.cache_dir / f"contradictions_{rulebook.sha256[:16]}_{ANALYSIS_VERSION}.json"
    if cache.exists():
        try:
            found = _clean(json.loads(cache.read_text()), rulebook)
            print(f"contradictions: {len(found)} known for this rulebook (cached)", file=log)
            return found
        except (OSError, ValueError):
            pass

    try:
        passes = [
            client.invoke(system_text=system_text(rulebook),
                          user_text="Audit the rulebook above.",
                          tool_config=_TOOL, tool_name=TOOL_NAME,
                          cache_tag=f"__contradictions__:{ANALYSIS_VERSION}:{i}")
            for i in range(2)
        ]
        data = {"contradictions": _consensus(passes, rulebook, log=log)}
    except Exception as exc:  # noqa: BLE001
        # No register is the status quo, not a new failure: the answer-side checks in
        # SPEC 10 still run. Never let the audit take the run down with it.
        print(f"warn: contradiction audit failed ({exc.__class__.__name__}: {exc}); "
              "continuing without a register", file=log)
        return []

    raw = data.get("contradictions") or []
    try:
        cache.write_text(json.dumps(raw, ensure_ascii=False))
    except OSError:
        pass
    found = _clean(raw, rulebook)
    for c in found:
        print(f"contradictions: {sorted(c.sections)} on {list(c.terms)} -- {c.note}",
              file=log)
    if not found:
        print("contradictions: none found in this rulebook", file=log)
    return found
