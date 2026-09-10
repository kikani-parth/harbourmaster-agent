### 1. What it got wrong

Under v1.2, §4.2 said Spice "counts double when scored" while §7.1's table listed it at face value: a Spice 4 worth either 4 or 8. The v1.3 errata later struck the sentence.

It surfaced during unit-test work I had asked for. The agent did three evasions, first came question_class=contradiction with abstained: false. It declared the contradiction, then ruled anyway. The check was keyed on question_class, so it just reclassified to computed instead. I closed that gap, and it came back with question_class=direct, conflict.kind=none, denying the contradiction while still citing both §4.2 and §7.1. The agent's own line: "No check based on the model's self-report can fire on that." Every check until then had trusted the model about itself.

A fix made things worse, and only measurement caught it. The agent suspected its own prompt change had caused the third evasion. The A/B ran against the change and abstentions fell from 5/5 to 2/5, because closing the scope-narrowing escape had pushed the model into a worse one. It reverted the change, and that A/B was its call, not mine.

The fix I proposed: one more repair call, this time told outright that a contradiction exists, with a deterministic append as fallback. Q4 went from 2/5 on the prompt alone, to 4/5 with validator enforcement, to 5/5 with the register plus the armed repair call. In one of the five, the repair call still denied it, and the deterministic force-abstain saved the answer.


### 2. What I didn't do

I did not fix a known defect as it meant touching a validator, and that meant regenerating the response cache and re-running all nine evidence blocks: every block has to come from one cache state, or the mutations don't compare. So I documented it and froze.

It's the §4.4/§5.1 false positive: the audit calls them a contradiction when they are a general/specific pair composing cleanly to "three without the token." I filed it as B1, with a note. I had built that filter to throw out invented pairs, and it does nothing when both audits invent the same one. It was live on my final cold run.

I left it because it's contained rather than filtered. Forcing an abstention needs three conditions and a veto, and in the baseline run it fired zero times. The obvious fix I had tried and rejected was an adversarial verification pass that reconciled the real Spice contradiction 3/3 and would have emptied the register. The residual risk is a wrong abstention on an answerable question which would be an eval failure, not a silent wrong answer.

Before I opened PROBE_B.jsonl, I rated four risks and put the §4.4/§5.1 false positive at #1, the exact thing I had chosen to ship. It never fired, and nothing over-abstained. Two risks I had rated lower both did.

### 3. Another day

The one that got past everything was QB6: could a Ship at the Lighthouse Sail to an empty Dock and Trade the same turn? No. §4.3 enumerates Sail as Open Sea → unoccupied Dock, or Dock → Open Sea; §9.2 adds only Open Sea ↔ Lighthouse. Lighthouse → Dock is in neither, and my spec's closed-world rule (SPEC §3) confirms it.

What I got back: "Yes... nothing prevents using your Sail action to move from the Lighthouse to any unoccupied Dock tile." It quoted §4.3 verbatim and correctly, then asserted a move its own quotation excludes. Six citations, abstained: false.

I ran the invariants offline over the Probe B output, and not one fired. All nine applicable ones passed; test_probe_fixtures reported zero, because no fixture can apply to an unseen id. It's a correctly-shaped answer stating a rule the rulebook doesn't contain, and everything I had built checks shape.

The problem was that in the Amendment delta, before I opened Probe B, I had flagged this exact gap: "a new place for a careless reader to go wrong." Then the agent went there. The agent is that careless reader.

So what I would build with another day isn't more fixtures but I would extend defects.py instead as it generalises to unseen questions because it's keyed to the rulebook, not the question set. Then I can point it at enumerations and derive the closed lists the rulebook states, like Sail's legal moves, and flag any answer asserting a permission none of them contains.