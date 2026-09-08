#!/usr/bin/env python3
"""Corrupts an agent's JSONL output in one specific way.

Sits between the candidate's real agent and their eval suite. Their evals
should notice. If they don't, the evals are theatre.

Usage:  ./run.real.sh | python3 mutator.py <mutation-name>
"""
import json
import re
import sys

MUTATIONS = {
    "none": "passthrough, sanity check that the harness itself is not the problem",
    "no_abstain": "force abstained=false everywhere",
    "strip_citations": "empty every citation list",
    "shuffle_answers": "rotate answers between questions",
    "truncate_answer": "cut every answer to 15 characters",
    "plausible_wrong": "add 1 to every number in the answer, leaving section refs alone",
    "citation_superset": "append a real section nobody relied on to every citation list",
    "drop_one": "silently drop the last record",
    "fake_citation": "replace citations with a section that exists but is irrelevant",
}

# Numbers that are not part of a section reference. The lookbehind keeps §7.1
# intact and the lookahead stops us eating the 1 in 7.1 from the other side —
# a mutation that garbles citations would be caught by the wrong assertion and
# tell us nothing about whether the suite checks values.
BARE_NUMBER = re.compile(r"(?<![§\d.])\b(\d+)\b(?!\.\d)")

# A real section, and one an answer almost never rests on: §7.3 says the Dock
# tile number does not affect scoring.
SPARE_SECTION = "§7.3"


def apply(name, records):
    if name == "none":
        return records
    if name == "no_abstain":
        for r in records:
            r["abstained"] = False
        return records
    if name == "strip_citations":
        for r in records:
            r["citations"] = []
        return records
    if name == "truncate_answer":
        for r in records:
            r["answer"] = str(r.get("answer", ""))[:15]
        return records
    if name == "fake_citation":
        for r in records:
            r["citations"] = [SPARE_SECTION]
        return records
    if name == "plausible_wrong":
        # Every quantity in the answer is off by one, and nothing else changes.
        # Caught only by an assertion on the value. A case checking that the
        # answer contains "points" or "Convoy Bonus" sails straight past it.
        for r in records:
            r["answer"] = BARE_NUMBER.sub(
                lambda m: str(int(m.group(1)) + 1), str(r.get("answer", "")))
        return records
    if name == "citation_superset":
        # The right sections are still there — one wrong one is added. Caught
        # only by an assertion on citation precision. Every suite we have seen
        # checks that citations are non-empty or contain X, never that they
        # contain only what the answer actually rests on.
        for r in records:
            cites = list(r.get("citations") or [])
            if SPARE_SECTION not in cites:
                cites.append(SPARE_SECTION)
            r["citations"] = cites
        return records
    if name == "drop_one":
        # One question silently goes unanswered. Caught only by an assertion
        # that every id came back — completeness, which most suites assume.
        return records[:-1] if records else records
    if name == "shuffle_answers":
        if len(records) < 2:
            return records
        answers = [r.get("answer") for r in records]
        rotated = answers[1:] + answers[:1]
        for r, a in zip(records, rotated):
            r["answer"] = a
        return records
    raise SystemExit(f"mutator: unknown mutation {name!r}")


def usage():
    width = max(len(n) for n in MUTATIONS)
    lines = ["usage: mutator.py <mutation>   (reads JSONL on stdin, writes it on stdout)", ""]
    lines += [f"  {n:<{width}}  {d}" for n, d in MUTATIONS.items()]
    return "\n".join(lines)


def main():
    # --help must not fall through to the stdin read below, or it hangs on a TTY.
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help", "help"):
        print(usage())
        return
    if len(sys.argv) != 2 or sys.argv[1] not in MUTATIONS:
        raise SystemExit(usage())

    records, malformed = [], 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            # Pass malformed lines through untouched — that is the candidate's
            # bug to own, not something this harness should mask or fix.
            malformed += 1
            print(line, flush=True)

    for r in apply(sys.argv[1], records):
        print(json.dumps(r), flush=True)

    if malformed:
        print(f"mutator: {malformed} malformed line(s) passed through", file=sys.stderr)


if __name__ == "__main__":
    main()
