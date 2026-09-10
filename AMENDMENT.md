# Harbourmaster — errata, v1.2 → v1.3

**Don't open this until your build is frozen.** It's the last step. See `BRIEF.md`, "The amendment".

The publisher has issued a revised rulebook. `errata/RULEBOOK_v1.3.md` in this pack is the complete replacement text. Four things changed.

---

### 1 · §4.2 — the Spice sentence is struck

*Players reported two different scores for the same card.* The sentence "Spice is the most valuable trade good in the harbour and counts double when scored" has been removed from §4.2. The §7.1 table is the scoring rule.

### 2 · §5.1 — the unload limit drops from three to two

*Playtesting found the Harbourmaster token was changing hands too rarely to matter.* §5.1 now reads "more than **two** Cargo cards".

### 3 · §9 — the Lighthouse is added

*A new tile ships with the second printing.* New §9, plus §2.5 in setup and a line in §1 components.

### 4 · Everything else is unchanged

§4.1 (Draw Pile) and §6.2 (Storms) are untouched, including anything you found wrong in them.

---

## Applying it

From your repo root:

```sh
mv RULEBOOK.md errata/RULEBOOK_v1.2.md
mv errata/RULEBOOK_v1.3.md RULEBOOK.md
```

That leaves exactly one `RULEBOOK.md` where there was one before — v1.2 is kept in `errata/` if you want to read the two side by side for the `DEFECTS.md` delta.

**Change no code.** Not one line. If your design treats the rulebook as data, this is the whole job. If it doesn't, that's a real result and we want to read it — see the brief.

Then re-run both entry points and paste the raw output under `## Amendment` in `EVIDENCE.md`:

```sh
./run.sh < probe.jsonl
./evals.sh
```

---

## One more step, and then you're done

With v1.3 in place and the amendment block written, open `PROBE_B.jsonl` — ten questions you haven't seen. Run them against the same frozen build, under v1.3:

```sh
./run.sh < PROBE_B.jsonl
```

**Still no code changes.** Paste the raw output under `## Probe B` in `EVIDENCE.md`, with a `Predicted:` line above it and one paragraph underneath naming which of your own eval cases would have caught a wrong answer — and which of the ten have no case behind them at all. See `BRIEF.md`, "Probe B".

Then you're finished. Don't go back and fix anything Probe B exposed; tell us about it instead. That's the more useful artifact, and going back and patching is the one thing that makes this step worthless.
