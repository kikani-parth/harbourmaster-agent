#!/usr/bin/env python3
"""prose_ref_drift -- the mutation this suite deliberately does NOT catch.

Rewrites a section reference inside the ANSWER PROSE to a different section that is
already in that record's own citations array. The citations array is left untouched.

Why the suite misses it, honestly:
  test_citations_exist        passes -- every cited section is real and unchanged.
  test_prose_refs_are_cited   passes -- the drifted ref IS in the citations array.
  test_probe_fixtures         passes -- required citations are all still present, and
                                        no forbidden one was added.

The gap it exploits: the suite checks citations for STRUCTURAL validity -- that they
exist, and that prose and array agree -- and never checks SEMANTIC attribution, that
the claim in the sentence actually comes from the section pinned to it. So the answer
can credit the scoring table for a rule that lives in the Convoy Bonus section, and
every assertion stays green.

The assertion that would close it: a proximity check on attribution. For Q9, require
that "Convoy Bonus" appears within N characters of §7.2, rather than merely requiring
§7.2 somewhere in the citations array.

Usage:  ./run.real.sh | python3 evals/mutation_yours.py
"""
import json
import re
import sys

PROSE_REF = re.compile(r"§\d+(?:\.\d+)?")


def drift(record):
    cites = [c for c in (record.get("citations") or []) if isinstance(c, str)]
    answer = str(record.get("answer") or "")
    if len(cites) < 2:
        return record
    for match in PROSE_REF.finditer(answer):
        current = match.group(0)
        other = next((c for c in cites if c != current), None)
        if current in cites and other:
            record["answer"] = answer[:match.start()] + other + answer[match.end():]
            break
    return record


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        print(json.dumps(drift(json.loads(line)), ensure_ascii=False), flush=True)
    except json.JSONDecodeError:
        print(line, flush=True)
