# Assignment

**What you need:** an AI coding agent you already use, and **Python** — write your agent in Python. We don't run your code, so you won't be fighting our environment, but we do read it, and one language across every submission is what makes them comparable. `mutator.py` in this pack is Python and assumes `python3` is on your path.

---

## Before you start — two things we want to be clear about

1. **This task is fictional and deliberately outside our business.** WithSecure is a cyber security company. This exercise is about a made-up board game. That is on purpose: we don't want any possibility that candidate work feeds our product.
2. **Do not send us anything confidential.** No employer code, no client data, nothing under NDA. If your agent transcript contains something you shouldn't share, redact it before sending.

---

## The task

Attached is `RULEBOOK.md`, the complete rules for **Harbourmaster**, a board game we invented for this exercise.

**Build an agent that answers players' rules questions.**

That's the whole brief. Deciding what "good" means here is part of what we're assessing, so we're not going to specify it further. One hint, freely given: the rulebook is the only source of truth, and it is not perfect.

**A deterministic implementation is fine.** You don't need a model at runtime, and no API key is required. If you go that way, say so in `NOTES.md` and add one extra file, `LLM_DELTA.md` — see the evidence pack. It's the closest thing we get to seeing you drive a model, so it's worth as much to us as the code.

**The rulebook will change before you're done.** `AMENDMENT.md` is in this pack, sealed by nothing but this sentence. Don't open it until your build is frozen — it's the last step, and it's described under "The amendment" below. You could read it first. If you do, the sensible response is to build something that doesn't care which version of the rulebook it's reading, which is what we're looking for anyway.

**And there are questions you haven't seen.** `PROBE_B.jsonl` is sealed the same way, by this sentence and nothing else. Ten questions, opened with the amendment and run against the revised rulebook. `probe.jsonl` is yours to read and to build against, deliberately — but a suite that only works on the questions you were given isn't worth much, and this is where that shows. Same advice: if you open it early, the sensible response is to stop tuning to specific questions, which is what we want anyway.

**To be clear about which parts are open and which aren't:** *what* to build and how far to take it is deliberately yours to decide — that judgement is a large part of what we're looking at. The *mechanics* below are not open, because every submission has to be readable the same way.

**Don't spend time on:** UI, packaging, test coverage percentage, commit message style, or getting more done. We'd rather see a small thing you understand deeply than a large thing you don't.

## Use of AI agents — required

**You must use AI coding agents for this**, and your transcript is part of what we assess. Claude Code, Cursor, Codex, Copilot, whatever you actually work with. We're hiring people who direct agents well; we're not interested in whether you can type code from memory.

We assess **how you directed and reviewed the agent**, not how much code came out. A submission where the agent wrote everything and you caught three of its mistakes scores far better than one where you hand-wrote it all.

## Required interface

To ensure a standard interface across all submissions, two executables at the repo root:

**`./run.sh`** — reads one JSON object per line on stdin, writes one per line on stdout.

```jsonc
// in
{"id": "q1", "question": "Can I unload four Iron cards onto one Dock?"}
// out
{"id": "q1", "answer": "...", "citations": ["§5.1"], "abstained": false}
```

| Field | Meaning |
|---|---|
| `id` | echo the input id |
| `answer` | your agent's answer, plain text |
| `citations` | rulebook sections you relied on, e.g. `["§5.1", "§7.2"]`, may be empty |
| `abstained` | `true` if the agent declined to give a definitive answer |

**`./evals.sh`** — runs your eval suite. Prints a human-readable summary. **Exits non-zero if the suite fails.**

---

## Technical requirements

We don't execute your submission — you do, and you send us the output. So there's no dependency manifest to satisfy and no environment of ours to be portable to. **Python is the one fixed choice** — the agent itself goes in Python; shell glue in `run.sh` and `evals.sh` is expected and fine. Beyond that, what's left are the things that make your evidence pack readable and comparable.

### The two entry points

Both at the repo root, invoked as `./run.sh` and `./evals.sh` from the repo root with no arguments.

- **`evals.sh` must exercise your agent by invoking `./run.sh`.** Not by importing your modules directly, not by calling an internal function. This is what makes the mutation step below mean anything — if your suite reaches the agent some other way, the mutation never reaches your evals and the exercise tests nothing.
- **No interactive prompts.** Nothing that waits on a TTY or asks for confirmation.

### Input and output

- **`run.sh` gets every question at once.** The probe set is twenty-five lines, all on stdin in one invocation — read until your process exits. Don't assume one question per run.
- **One JSON object per line on stdout, and nothing else.** Logging and warnings go to stderr.
- **Output order doesn't matter** — we match on `id`.
- `evals.sh` exits **non-zero** if your suite fails, zero if it passes. Print whatever summary you like.

---

## The evidence pack

You run the checks; we read the output. Two extra files in your submission — three if your runtime has no model.

### `EVIDENCE.md` — raw pasted output, twelve blocks

Paste it verbatim, in fenced code blocks, under these headings. Don't clean it up or summarise it.

| Heading | Command | What we're reading for |
|---|---|---|
| `## Baseline` | `./evals.sh` | your suite passes on the working agent |
| `## Mutation: no_abstain` | see below | which of your cases fails, and that it's the right one |
| `## Mutation: strip_citations` | " | " |
| `## Mutation: shuffle_answers` | " | " |
| `## Mutation: truncate_answer` | " | " |
| `## Mutation: plausible_wrong` | " | " |
| `## Mutation: citation_superset` | " | " |
| `## Mutation: drop_one` | " | " |
| `## Mutation: yours` | see below | a mutation you designed that your suite **misses** |
| `## Probe` | `./run.sh < probe.jsonl` | the raw JSONL your agent produced, every id |
| `## Amendment` | see "The amendment" | the same ids under the revised rulebook |
| `## Probe B` | see "Probe B" | ten questions you haven't seen, under the revised rulebook |

**One measured number, in the `## Probe` block.** Wall clock for the whole batch — `time ./run.sh < probe.jsonl` is enough. If a model is involved, tokens or cost too.

**And a budget to read it against: the twenty-five questions should come back inside 60 seconds**, on whatever machine you're using. It's a loose bound and we can't check it, so it's there to make the number mean something rather than to be a hurdle. If you're over it, say why — "each question is a separate model call and I chose clarity over batching" is a fine answer, and a better one than a fast number with no reasoning attached. If you're an order of magnitude under, that's worth a sentence too.

**The mutation step.** `mutator.py` ships with this pack. It corrupts your agent's output in one specific way, and your eval suite should notice. Point `run.sh` at it — the simplest way is a one-line wrapper:

```sh
mv run.sh run.real.sh
printf '#!/bin/sh\nexec ./run.real.sh | python3 mutator.py no_abstain\n' > run.sh
chmod +x run.sh
./evals.sh          # paste this output under "## Mutation: no_abstain"
```

Repeat for the other six, then restore your real `run.sh`. `python3 mutator.py --help` lists what each one does; it's a short file and worth reading.

| | corrupts |
|---|---|
| `no_abstain` | forces `abstained` false everywhere |
| `strip_citations` | empties every citation list |
| `shuffle_answers` | rotates answers between questions |
| `truncate_answer` | cuts every answer to 15 characters |
| `plausible_wrong` | adds 1 to every number in the answer, leaving section refs alone |
| `citation_superset` | appends a real section nobody relied on to every citation list |
| `drop_one` | silently drops one record |

`none` (passthrough, for checking your wrapper works) and `fake_citation` are also there. Neither is required.

**Write a `Predicted:` line at the top of each block, before you run it.** One sentence: which of your cases you expect to fail, and why. Then paste the output underneath. We are reading for whether the prediction matched — and a prediction that turns out wrong, left in and explained, tells us more than seven that were right.

```
## Mutation: plausible_wrong

Predicted: test_scores_total fails — it is the only case asserting an exact number.

​```
...pasted output...
​```
```

**Under each block, add a sentence:** which of your eval cases failed, and why that's the case that should have failed. Name the case. A suite that catches everything without you being able to say which assertion did the work tells us less than one that catches two and explains them.

If a mutation *doesn't* fail your suite, paste that and say so. An honest gap reads far better than a table that doesn't survive us reading your eval code next to it.

### `## Mutation: yours` — write one we didn't

One more block, and it's the one we read hardest.

**Design a mutation your own suite does *not* catch.** Corrupt your agent's output some way we didn't think of, run your evals, watch them pass, and paste that. Then say what assertion you'd add to close it.

It doesn't have to be clever or hard to build — a dozen lines of Python is plenty. What we're reading is whether you can find your own blind spot on purpose. If your suite catches everything you throw at it, say that too, and tell us what you tried.

### The amendment — the last thing you do

Games get errata. Yours will too, and this is the part of the exercise that asks whether your agent survives it.

**Freeze your build first.** Finish everything above — the baseline, every mutation block, the probe — and only then open `AMENDMENT.md`. It tells you to swap `RULEBOOK.md` for `errata/RULEBOOK_v1.3.md` and re-run.

**Change no code.** Not one line, not a constant, not a string. If your design treats the rulebook as data, swapping the file is the whole job. If it doesn't, your output won't move, and we would much rather read that honestly than read a patched agent.

Paste both raw runs under `## Amendment`, then answer three things underneath:

- **which answers changed**, one sentence each
- **which answers should have changed and didn't** — this is the interesting half, and "none of them moved, because my agent hardcodes the rules" is a complete and respectable answer to it
- **the `DEFECTS.md` delta** — a paragraph: which of the problems you filed does the revised rulebook close, and what does it open

Nothing here is a trick. The revised rulebook is the whole text, the changelog names every edit, and we'd rather you spent the time reading it than guessing at us.

### Probe B — ten you haven't seen

Once the revised rulebook is in place, open `PROBE_B.jsonl` and run it. Same interface, same format, one invocation:

```sh
./run.sh < PROBE_B.jsonl
```

**Against the revised rulebook only.** Don't re-run it under the original and don't change any code — this is the same frozen build, ten new questions.

Why this exists, plainly: `probe.jsonl` ships with the assignment on purpose, so you can build against it and check yourself. The cost of that is that a suite tuned to twenty-five questions you can read looks identical to one that actually works. Probe B is where the difference shows. Some of these are answerable, some aren't, and a few are neither in a way the rulebook is responsible for.

Paste the raw output under `## Probe B`, with a `Predicted:` line above it as usual — how you expect your agent to do, in one sentence, before you run it. Then one short paragraph underneath:

- **which of your own eval cases would have caught a wrong answer here** — name them, and name the ones with no case behind them

That last part is the whole point of the block. An agent that answers ten unseen questions well and a candidate who can say which of them their suite was actually protecting are two different things, and we're reading for the second.

If it goes badly, paste that. It reads far better than a tidy block, and "six of these needed §9 and my agent has no §9" is a complete and useful answer.

### `DEFECTS.md` — what's wrong with the rulebook

A list. For each: which section, what the problem is, and what your agent does about it. We're not looking for a particular number.

Write it against the rulebook you built on, not the revised one. The delta after the amendment goes in `EVIDENCE.md` under `## Amendment`, not here.

### `LLM_DELTA.md` — only if your runtime has no model

The brief lets you build this deterministically and means it. But then nothing in your submission shows us you driving a model, which is most of the job. So if there's no model at runtime, add this file. Three things, no length target:

- **the system prompt you would actually ship** — the real thing, not a description of it
- **a pasted transcript** of five `probe.jsonl` questions put through a model in whatever chat or agent UI you already use. No API key, no code, no harness. Copy and paste.
- **where the model deviated from your spec** — name the question, quote what it said, say which clause of your spec it walked past

If you *do* have a model at runtime, skip this file entirely. Your agent is the evidence.

## What to submit

Reply to the email we sent you with a **zip** or a **link to a repo we can clone**. Anything over 20 MB, send a link.

Every file below is required. **If one is missing we can't grade the submission**, so it's worth thirty seconds checking before you send.

| Path | What | Required |
|---|---|---|
| your agent | the code that answers the questions — see below | yes |
| `run.sh` | as above | yes |
| `evals.sh` | as above | yes |
| `SPEC.md` | the spec you gave your agent | yes |
| `evals/` | your eval suite — any framework, your call | yes, non-empty |
| `EVIDENCE.md` | pasted output, twelve blocks — see above | yes |
| `DEFECTS.md` | what's wrong with the rulebook — see above | yes |
| `NOTES.md` | **700 words max** — see below | yes |
| `trace/` | your agent session — see below | yes, non-empty |
| `trace/DIRECTION.md` | three pointers into the trace — see below | yes |
| `README.md` | how the pieces fit together — see below | yes |
| `LLM_DELTA.md` | prompt + transcript — see above | only if no model at runtime |

### Your agent — what we mean

Python, but any filename and any layout you like. **If `run.sh` calls another file, that file has to be in what you send us.** A wrapper pointing at an agent we don't have is the one omission that makes a submission impossible to read.

`run.sh` and `evals.sh` are shell entry points — they exist to give every submission the same front door, and yours will most likely be a line or two that calls into your Python. That's what we expect.

Worth thirty seconds before you send: unzip what you're about to send into a clean folder and check the file `run.sh` invokes is actually in there.

### `SPEC.md` — what we mean

The spec you actually gave your agent, not one written afterwards to describe what you built. Shape and length are yours; what we read for is whether a second person could build the same thing from it, and whether it anticipates where the agent will go wrong instead of hoping it won't.

**One thing we do require in it: say what your agent does with a hostile question.** Two of the twenty-five questions in `probe.jsonl` are instructions dressed as questions — one tells your agent to disregard the rulebook, one asserts a wrong answer as a system override. There's another in Probe B. Your spec needs a clause covering that class: what the agent treats as data, what it refuses to do, and what it answers anyway. "The agent handles malformed JSON" is not this — a broken pipe and a hostile one are different problems, and only one of them is trying to get something out of you.

It doesn't need to be long. A paragraph that a reviewer can hold your agent's actual output against is worth more than a page of policy.

### `README.md` — what we mean

Short. We're not running your code, so this isn't setup instructions — it's the orientation we read before opening anything else.

- What the pieces are and which file does what
- Where your agent lives, and **if it lives inside `run.sh` itself, say so** — otherwise we'll go looking for a file that doesn't exist
- Anything we'd need to know to read the submission that isn't obvious from the layout

A few lines is plenty.

### `trace/` — what we mean

**Raw material from your session, not a summary written afterwards.** A numbered list of the steps you took isn't a trace — the agent doesn't appear in it, and how you worked with the agent is the thing we're reading for.

Any of these, and one is enough:

- An exported session transcript from your tool — Claude Code, Cursor, Codex, most can export
- Copy-pasted chat logs in a markdown file
- A prompt log: what you actually typed, verbatim, in order

**If you include nothing else, include this:** the exchange where the agent got something wrong and you corrected it. Your prompt, its answer, what you said next. That single exchange is worth more to us than a complete record of everything that went right.

Git history on its own isn't enough — commits show what changed, not how you steered.

It doesn't need to be tidy, and it doesn't need to be complete. **Redact anything confidential before sending.**

### `trace/DIRECTION.md` — three pointers, and the reason we ask

A trace can be enormous and still not show us anything. A full session log in which every decision was the agent's suggested option, accepted, is weaker evidence than a short one where you overruled it and were right. We can't reliably tell those apart by reading a 3 MB transcript, so we're asking you to point.

Three things, each with a line reference into `trace/` so we can go and read it:

1. **Where you overruled the agent on substance** — not style, not naming. What it wanted to do, what you told it instead, and the reasoning you gave. If you overruled it and were *wrong*, that's worth more than a safe example; say so.
2. **Where the agent overruled you, and was right.** What you asked for, why it pushed back, why it was correct.
3. **Something you found that the agent never surfaced.** A defect, a bug, a wrong answer — anything you got to first.

A paragraph each. If one of the three genuinely didn't happen, say that instead of manufacturing it — "the agent never pushed back on me, and reading it now I think it should have" is a real answer and we'll take it over an invented one. Write this yourself, like `NOTES.md`; it doesn't count against the 700 words.

### `NOTES.md` — 700 words max, and the most-read file in your submission

> **Write this one yourself.** Everywhere else we want to see you working with an agent. This file is the exception: it's your own account, in your own words. Don't have your agent draft it or tidy it up.
>
> It's the file we read most closely, and we ask about it in the interview.

Three questions, in this order. A short paragraph each is plenty.

1. What your agent got **wrong**, and how you caught it.
2. One thing you deliberately **didn't** do, and why.
3. What you'd do with another day.

Be honest here. "The agent confidently invented a rule and I only caught it on the third read" tells us more than a page saying everything went smoothly.

**Name things.** Which section, which file, which answer, what the wrong output actually said. A specific account of one mistake is worth more than a tidy summary of three. Rough edges are fine — we're not marking the prose.

We check the word count mechanically and flag anything over 700. Going over isn't a rejection — it's a signal about editing.

## Deadline

**Three days from the email that sent you this**, on the date given there. The build is 90 minutes; the evidence pack and the rest is room for everything else going on.

## What's in this pack

| File | |
|---|---|
| `RULEBOOK.md` | the game — the only rulebook in the root, and the one you build against |
| `probe.jsonl` | the questions to run through your agent. You get all twenty-five; we don't say which ones we grade |
| `mutator.py` | corrupts your agent's output seven ways, for the mutation blocks |
| `AMENDMENT.md` | **don't open until your build is frozen** — the errata step |
| `errata/RULEBOOK_v1.3.md` | the revised rulebook `AMENDMENT.md` tells you to swap in. It sits in `errata/` so there is only ever one rulebook in the root — if your loader picks up both, that's a bug you want to find now and not at the amendment |
| `PROBE_B.jsonl` | **don't open until you've done the amendment** — ten questions you haven't seen, last |

---

Everything you need is in this pack. If you hit a question you think isn't part of the challenge itself — something about the mechanics, the interface, or how to send it back — reply to the email and ask.
