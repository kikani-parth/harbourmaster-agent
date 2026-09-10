"""Eval runner. Exercises the agent ONLY by invoking ./run.sh as a subprocess.

That constraint is what makes the mutation step meaningful: when run.sh is replaced
by a wrapper that pipes the agent's output through mutator.py, this suite sees the
corrupted records exactly as a grader would. Importing the agent's modules would
route around the mutation and test nothing. See SPEC 12.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from evals import cases, test_units  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUN = str(ROOT / "run.sh")
PROBE = ROOT / "probe.jsonl"
SWAP_RULEBOOK = ROOT / "evals" / "fixtures" / "tiny_rulebook.md"
SWAP_PROBE = ROOT / "evals" / "fixtures" / "tiny_probe.jsonl"
DEFAULT_RULEBOOK = ROOT / "RULEBOOK.md"


def invoke(questions_path: pathlib.Path, rulebook_path: pathlib.Path | None = None):
    """Run the agent once, feeding it every question on one stdin."""
    env = dict(os.environ)
    if rulebook_path:
        env["HARBOURMASTER_RULEBOOK"] = str(rulebook_path)
    else:
        env.pop("HARBOURMASTER_RULEBOOK", None)
    proc = subprocess.run(
        [RUN], stdin=questions_path.open("rb"), capture_output=True, cwd=ROOT, env=env,
    )
    records, malformed = [], []
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            malformed.append(line[:120])
    return records, malformed, proc


def questions_in(path: pathlib.Path) -> dict:
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                obj = json.loads(line)
                out[obj["id"]] = obj.get("question")
            except Exception:
                pass
    return out


def main() -> int:
    results = []  # (case_name, scope, failures)

    print("running ./run.sh against probe.jsonl ...", file=sys.stderr)
    probe_records, probe_malformed, probe_proc = invoke(PROBE)
    print(f"  {len(probe_records)} record(s) parsed", file=sys.stderr)

    print("running ./run.sh against the swapped rulebook ...", file=sys.stderr)
    swap_records, swap_malformed, swap_proc = invoke(SWAP_PROBE, SWAP_RULEBOOK)
    print(f"  {len(swap_records)} record(s) parsed", file=sys.stderr)

    probe_qs, swap_qs = questions_in(PROBE), questions_in(SWAP_PROBE)
    probe_ids, swap_ids = list(probe_qs), list(swap_qs)
    probe_text = DEFAULT_RULEBOOK.read_text()
    swap_text = SWAP_RULEBOOK.read_text()

    results.append(("test_stdout_is_pure_jsonl", "probe",
                    [f"non-JSON line on stdout: {m!r}" for m in probe_malformed + swap_malformed]))

    for name, fn in cases.INVARIANTS:
        wants_questions = fn.__code__.co_argcount > 3
        extra_probe = (probe_qs,) if wants_questions else ()
        extra_swap = (swap_qs,) if wants_questions else ()
        results.append((name, "probe",
                        fn(probe_records, probe_ids, probe_text, *extra_probe)))
        results.append((name, "swap",
                        fn(swap_records, swap_ids, swap_text, *extra_swap)))

    # Unit tests of internals the run.sh-driven cases cannot reach. Reported as a
    # separate scope because a mutation corrupts run.sh's output and cannot affect
    # these -- they are expected to pass in every mutation block.
    results.append(("test_units", "unit", test_units.failures()))

    results.append(("test_probe_fixtures", "probe", cases.fixture_failures(probe_records)))
    results.append(("test_answers_follow_swapped_rulebook", "swap",
                    cases.swap_failures(swap_records)))

    # Collapse the two scopes of each invariant into one reported line.
    merged: dict[str, list[str]] = {}
    for name, scope, failures in results:
        merged.setdefault(name, []).extend(f"[{scope}] {f}" for f in failures)

    width = max(len(n) for n in merged)
    failed = 0
    print()
    print("=" * 72)
    for name in merged:
        failures = merged[name]
        if failures:
            failed += 1
            print(f"FAIL  {name:<{width}}  {len(failures)} failure(s)")
            for f in failures[:12]:
                print(f"        - {f}")
            if len(failures) > 12:
                print(f"        ... and {len(failures) - 12} more")
        else:
            print(f"ok    {name}")
    print("=" * 72)
    total = len(merged)
    print(f"{total - failed}/{total} cases passed"
          + (f", {failed} FAILED" if failed else ""))

    if probe_proc.returncode != 0:
        print(f"note: run.sh exited {probe_proc.returncode} on the probe set")
        failed += 1
    if swap_proc.returncode != 0:
        print(f"note: run.sh exited {swap_proc.returncode} on the swap set")
        failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
