# Harbourmaster rules agent

Answers players' rules questions from `RULEBOOK.md`, cites the sections it relied on, and
abstains when the rulebook cannot settle a question. A model (Bedrock, Sonnet 5 with a Sonnet
4.6 failover) drafts each ruling; a deterministic validator enforces the contract. Neither is
trusted to do the other's job. `SPEC.md` is the binding spec: §2 rulebook, §3–8 answering
policy, §9 model calls, §10 validator, §12 evals.

## Layout

| Path | Role |
|---|---|
| `run.sh` → `harbourmaster/cli.py` | JSONL on stdin → JSONL on stdout; repair loop, thread pool, stderr logs |
| `harbourmaster/rulebook.py` | parses the section index from the markdown; no game facts |
| `harbourmaster/prompt.py` | system prompt (policy) and the forced `submit_ruling` tool schema |
| `harbourmaster/model.py` | Bedrock Converse, failover, response cache, tool-leak salvage |
| `harbourmaster/validate.py` | `check()` finds problems; `finalise()` applies fallbacks |
| `harbourmaster/defects.py` | per-edition contradiction audit (the "register"), cached by rulebook hash |
| `evals.sh` → `evals/runner.py` | runs `./run.sh` on probe.jsonl and on `evals/fixtures/tiny_rulebook.md` |
| `evals/cases.py` | invariants (any question) and fixtures (the 25 known questions) |
| `evals/test_units.py` | unit tests; the only eval file that imports the package |

## Running (Windows, Git Bash)

```sh
aws sso login --profile ta-dev && export AWS_PROFILE=ta-dev
./run.sh < probe.jsonl > out.jsonl 2> err.txt   # stdout = records only; logs on stderr
./evals.sh                                       # exits non-zero on failure
PYTHONUTF8=1 .venv/Scripts/python.exe -m unittest evals.test_units -v
```

- The scripts pick `.venv/Scripts/python.exe` and set `PYTHONUTF8=1` themselves.
- Windows Python can't see Git Bash's `/tmp`: keep scratch output in the repo (untracked) or
  pass Windows paths.
- `.cache/` holds model responses, keyed on rulebook hash + question + `PROMPT_VERSION` +
  model + inference config + repair text. A warm run makes 0 model calls. To force live
  calls, move `.cache` aside; never delete it.

**Expected baseline:** `RULEBOOK.md` is v1.3 (after the amendment), so `./evals.sh` gives
**12/13**. `test_probe_fixtures` fails with v1.2-era expectations for Q4, Q18, Q19 and Q25.
That's known; don't change fixtures unless asked.

## Hard rules

- **The rulebook is data.** No game facts in code: no section numbers, suits, values or rule
  text. Section ids come only from `rulebook.py`'s parse.
- **Evals reach the agent only through `./run.sh`** (a subprocess). Only `test_units.py` imports
  `harbourmaster`.
- **stdout carries only records** with exactly `id`, `answer`, `citations`, `abstained`, and
  every input id gets exactly one record, even on failure (degrade, never crash).
- **A hard `Problem` must never reach stdout.** Every hard code needs a fallback in `finalise()`.
- **Coercion is one-way:** the validator may force an abstention, never a definitive answer.
- Changing prompt text means bumping `PROMPT_VERSION` (prompt.py); changing the audit prompt
  means bumping `ANALYSIS_VERSION` (defects.py). Both are part of the cache keys.
- Don't edit the brief's inputs (`RULEBOOK.md`, `errata/`, `probe.jsonl`, `PROBE_B.jsonl`,
  `mutator.py`) or the write-ups (`EVIDENCE.md`, `NOTES.md`, `DEFECTS.md`, `trace/`) unless
  asked.
- Shell scripts stay LF (`.gitattributes`); `core.autocrlf` is on.

## How to work here

1. Read the relevant code and SPEC section first, then propose a plan (files, approach, test)
   and wait for approval.
2. Test first: a failing unit test in `evals/test_units.py`, or a case in `evals/cases.py`,
   before the fix.
3. Minimal diffs; no drive-by refactors or renames.
4. Show evidence: paste the test and eval output rather than asserting it passes.
