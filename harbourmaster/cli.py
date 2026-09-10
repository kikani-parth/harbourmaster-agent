"""Entry point: JSONL on stdin, JSONL on stdout, diagnostics on stderr.

See SPEC.md 1. Two rules dominate this file: every input id gets exactly one output
record, and stdout carries nothing but those records.
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from . import defects, model, prompt, rulebook, validate

MAX_QUESTION_CHARS = 4_000  # SPEC 1: a generous fixed margin, not a cost model.
WORKERS = 8
SALVAGE_ID = re.compile(r'"id"\s*:\s*"([^"]{1,128})"')


def _read_requests(stream, log):
    """Parse stdin. A malformed line yields a salvaged id, or a warning and nothing."""
    requests, malformed = [], 0
    for lineno, line in enumerate(stream, 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            qid = obj["id"]
            question = obj.get("question")
            if not isinstance(qid, str) or not isinstance(question, str):
                raise ValueError("id and question must both be strings")
            requests.append((qid, question))
        except Exception as exc:
            malformed += 1
            salvaged = SALVAGE_ID.search(line)
            if salvaged:
                print(f"warn: line {lineno} malformed ({exc}); abstaining for id "
                      f"{salvaged.group(1)!r}", file=log)
                requests.append((salvaged.group(1), None))
            else:
                print(f"warn: line {lineno} malformed and no id salvageable ({exc}); "
                      "skipped", file=log)
    if malformed:
        print(f"warn: {malformed} malformed input line(s)", file=log)
    return requests


def _severity(problems) -> tuple[int, int]:
    """Rank an attempt: hard problems first, then total. Lower is better."""
    return (sum(1 for p in problems if p.hard), len(problems))


def _answer_one(client, rb, qid, question, log, register=()):
    """One question through the model, the validator, and at most one repair."""
    if question is None:
        return {"id": qid, "abstained": True, "citations": [],
                "answer": "The agent could not read this question: the input line was "
                          "malformed."}

    truncated_from = None
    if len(question) > MAX_QUESTION_CHARS:
        truncated_from = len(question)
        question = question[:MAX_QUESTION_CHARS]
        print(f"warn: {qid} question truncated from {truncated_from} to "
              f"{MAX_QUESTION_CHARS} chars", file=log)

    try:
        ruling = client.ruling(question, truncated_from=truncated_from)
        problems = validate.check(ruling.data, rb, question, register)
        if problems:
            print(f"note: {qid} first attempt: "
                  + "; ".join(f"{p.code}" for p in problems), file=log)
            try:
                retry = client.ruling(question, truncated_from=truncated_from,
                                      repair=validate.repair_note(problems))
                retry_problems = validate.check(retry.data, rb, question, register)
                # Keep the repair only if it is strictly better, weighing severity
                # before count. Comparing counts alone accepted a retry that traded a
                # mechanically-fixable soft problem for a hard fabricated quotation --
                # 2 <= 2 -- and the fabrication reached stdout.
                if _severity(retry_problems) < _severity(problems):
                    ruling, problems = retry, retry_problems
                else:
                    print(f"note: {qid} keeping first attempt; retry was not better "
                          f"({_severity(problems)} -> {_severity(retry_problems)} "
                          "as (hard, total))", file=log)
            except model.ModelUnavailable as exc:
                print(f"warn: {qid} repair attempt failed ({exc})", file=log)
        record, notes = validate.finalise(qid, ruling.data, rb, problems, question)
        for note in notes:
            print(f"note: {qid} {note}", file=log)
        if problems:
            print(f"note: {qid} residual after repair: "
                  + "; ".join(p.code for p in problems), file=log)
        klass = ruling.data.get("question_class")
        _c = ruling.data.get("conflict") or {}
        conflict = (f"{_c.get('kind')} {_c.get('sections')} "
                    f"bears_on_answer={_c.get('bears_on_answer')}: {_c.get('note')}"
                    if isinstance(_c, dict) and _c.get("kind") not in (None, "none")
                    else "")
        print(f"info: {qid} class={klass} abstained={record['abstained']} "
              f"citations={record['citations']} model={ruling.model_id.split('.')[-1]}"
              + (f" | defect: {conflict}" if conflict else ""), file=log)
        return record
    except model.ModelUnavailable as exc:
        print(f"error: {qid} no model available: {exc}", file=log)
        return {"id": qid, "abstained": True, "citations": [], "degraded": True,
                "answer": "The agent could not reach a model, so this question was not "
                          "answered. This is an infrastructure failure, not a ruling."}
    except Exception as exc:  # noqa: BLE001 -- see below
        # SPEC 1 admits no exception to one-record-per-id. Anything unhandled here --
        # a rejected request, a bug in the validator -- must degrade this record rather
        # than kill the worker and lose the whole batch's stdout. Logged loudly so it
        # is never mistaken for a ruling.
        print(f"error: {qid} unhandled {exc.__class__.__name__}: {exc}", file=log)
        return {"id": qid, "abstained": True, "citations": [], "degraded": True,
                "answer": "The agent failed to process this question because of an "
                          "internal error. This is not a ruling."}


def main(argv=None) -> int:
    log = sys.stderr
    started = time.time()

    try:
        rb = rulebook.load(log=log)
    except rulebook.RulebookError as exc:
        # SPEC 2.4: a precondition failure, not a degradation. Records are still
        # emitted for the interface's sake, but they carry a distinct marker and the
        # process exits non-zero.
        print(f"FATAL: {exc}", file=log)
        if exc.diagnostic:
            print(exc.diagnostic, file=log)
        requests = _read_requests(sys.stdin, log)
        for qid, _ in requests:
            print(json.dumps({
                "id": qid,
                "answer": "RULEBOOK PARSE FAILURE: the agent could not parse the "
                          "rulebook's section structure, so no answer is grounded. "
                          "This is not an abstention on the merits.",
                "citations": [], "abstained": True,
            }, ensure_ascii=False), flush=True)
        print(f"FATAL: emitted {len(requests)} ungrounded record(s)", file=log)
        return 2

    requests = _read_requests(sys.stdin, log)
    if not requests:
        print("warn: no questions on stdin", file=log)
        return 0

    client = model.Client(rb, log=log)

    # One audit per rulebook edition, cached by its hash (SPEC 6.2). Established
    # before any question is answered so every answer is checked against the same
    # register, whether it is asked alone or in a batch.
    register = defects.register(client, rb, log=log)

    # The first question runs alone. It discovers any inference parameter the model
    # rejects and populates the prompt cache; firing all 25 at once would instead
    # have every worker pay a cache WRITE and race on the same discovery.
    records = [_answer_one(client, rb, *requests[0], log, register)]
    if len(requests) > 1:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(_answer_one, client, rb, qid, q, log, register)
                       for qid, q in requests[1:]]
            records.extend(f.result() for f in futures)

    degraded = sum(1 for r in records if r.pop("degraded", False))
    for record in records:
        print(json.dumps(record, ensure_ascii=False), flush=True)

    elapsed = time.time() - started
    print(f"summary: {len(records)} record(s) in {elapsed:.1f}s | {client.usage.summary()}",
          file=log)
    abstained = sum(1 for r in records if r["abstained"])
    print(f"summary: abstained {abstained}/{len(records)}", file=log)
    if degraded:
        print(f"summary: {degraded}/{len(records)} record(s) degraded by an "
              "infrastructure or internal failure, not by a ruling", file=log)
    if degraded == len(records):
        # Nothing worked. That is a precondition failure like SPEC 2.4's, not a run
        # with some bad answers in it, and it exits non-zero to say so.
        print("FATAL: no question was answered successfully", file=log)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
