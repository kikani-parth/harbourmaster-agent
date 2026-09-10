# Harbourmaster rules agent

Answers players' rules questions about Harbourmaster from `RULEBOOK.md`, cites the
sections it relied on, and abstains when the rulebook cannot settle the question.

A model reads and reasons; a deterministic validator enforces the contract. Neither is
trusted to do the other's job — which is why the agent can fail over to a different model
without weakening any guarantee.

## Where the agent lives

`run.sh` is shell glue only. The agent is Python, in `harbourmaster/`.

| Path | What it does |
|---|---|
| `run.sh` | entry point: JSONL on stdin → JSONL on stdout, diagnostics on stderr |
| `evals.sh` | runs the eval suite; exits non-zero on failure |
| `harbourmaster/cli.py` | stdin/stdout loop, repair loop, thread pool, stderr metrics |
| `harbourmaster/rulebook.py` | parses the rulebook into a section index — **no game facts** |
| `harbourmaster/prompt.py` | system prompt (the SPEC's policy) + tool schema |
| `harbourmaster/model.py` | Bedrock Converse, model failover, response cache, token accounting |
| `harbourmaster/validate.py` | the deterministic checks: citations, quotations, abstention, length |
| `harbourmaster/defects.py` | independent audit of the rulebook's contradictions, run once per edition and cached |
| `evals/cases.py` | invariants (any input, any rulebook) + fixtures (the 25 known questions) |
| `evals/runner.py` | invokes `./run.sh` as a subprocess and reports |
| `evals/test_units.py` | unit tests for internals the run.sh-driven cases can't reach |
| `evals/fixtures/tiny_rulebook.md` | a different game, to prove the rulebook is data |
| `evals/mutation_yours.py` | the mutation the suite deliberately does not catch |
| `SPEC.md` | the spec the agent was built to, written before the code |
| `DEFECTS.md` | what is wrong with the rulebook, and what the agent does about each |
| `EVIDENCE.md` | pasted output: baseline, mutations, probe |

## Things worth knowing before reading

**The rulebook is never referenced from code.** No constant, table or branch encodes a
game value. `rulebook.py` discovers section ids by parsing, so a revised edition that adds
`§9.5` makes it citable with no code change. `evals/fixtures/tiny_rulebook.md` is a
different game with different numbers, and the suite asserts the answers follow *it* —
that case fails immediately if any Harbourmaster fact is baked in.

**Model:** `eu.anthropic.claude-sonnet-5` in `eu-west-1`, with
`eu.anthropic.claude-sonnet-4-6` as failover, both constants at the top of
`harbourmaster/model.py`.
Sonnet 5 rejects `temperature` and `top_p` outright, so there is no sampling knob — see
`SPEC.md` 9.1, and 15 for everything build step 0 contradicted.

**Answers are cached on disk** under `.cache/`, keyed on the rulebook's SHA-256 plus the
question, prompt version, model and inference config. This exists so the nine mutation
runs differ only by the mutation rather than by model drift. It is **not shipped**, is
only ever populated by real runs, and a rulebook swap invalidates every entry. A cold
probe run takes ~30s; a warm one ~1s.

**`boto3` lives in `.venv/`,** which is also not shipped. `run.sh` prefers
`.venv/bin/python3`, honours `$HARBOURMASTER_PYTHON`, and falls back to `python3`.

**stderr carries no AWS account identifiers** — only model id and region — because
`EVIDENCE.md` involves pasting real output.
