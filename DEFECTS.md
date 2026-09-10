# DEFECTS — RULEBOOK.md v1.2

Running register, maintained as findings accumulate. Written against **v1.2**, the edition
the agent was built on — not the revised one. The post-amendment delta belongs in
`EVIDENCE.md` under `## Amendment`.

For each: the section, the problem, and what the agent does about it. The "what the agent
does" column is always a **class** of behaviour from `SPEC.md` §4–§6, never a special case
keyed to the defect. Nothing in this register appears in code; if it did, the amendment
would expose it, because a rulebook that repaired the defect would still produce the old
behaviour.

Each entry's **Agent** line is marked *observed* where a probe question exercises it, with
the question named, or *specified, untested* where the behaviour follows from `SPEC.md` but
no question in `probe.jsonl` reaches it. Nine of the twenty entries are exercised by a probe
question; eleven are not, which is worth knowing before reading that column as a
description of what the agent has been seen to do rather than what it should do.

Classes: **Contradiction** (abstain, §6.2) · **General/specific** (answer definitively,
§6.1) · **Undefined term** (abstain, A3) · **Silence** (abstain, A1) · **Ambiguous scope**
(answer with the reading stated, or abstain if the readings differ materially)

---

## A. Contradictions — sections that cannot both be true

### A1. §4.2 vs §7.1 — Spice scores double, and also does not
§4.2 states "Spice is the most valuable trade good in the harbour and counts double when
scored." §7.1's scoring table gives Spice as "face value". Both speak directly to how
Spice scores at the moment of unloading. They cannot both hold.

**Consequences:** a Spice 4 is worth 4 or 8 (probe Q4); two Spice 3s are worth 6 or 12
(probe Q18).

**Agent (observed, probe Q4 and Q18):** Contradiction → `abstained: true`, both readings and both numbers given, both
sections cited. Per `SPEC.md` §6.3 the agent leans toward §7.1's face value, on the
textual ground that §7.1 presents itself as the dedicated scoring procedure ("When Cargo
is unloaded onto a Dock, score each card using the table below") while §4.2's clause sits
inside a description of the Load action. The lean is stated as a lean; it does not become a
ruling, and no general "tables beat prose" precedence rule is invented to get there.

**Sub-defect:** even under §4.2's reading, "counts double" has undefined scope — does it
double only the card's face value, or also its contribution to the §7.2 Convoy Bonus? The
rulebook gives no way to tell.

**The counter-reading, which is stronger than this entry first allowed.** §7.1's table can
be read as *base* values with §4.2 layering a per-suit multiplier at scoring time — and
§7.2 already layers a Convoy Bonus on that same table, so the table is demonstrably not
the last word on scoring. Under that reading the two compose and a Spice 4 is 8 points,
with no contradiction at all. Against it: the table's own form already carries per-suit
modifiers ("Iron: face value + 1"), which makes "Spice: face value" read as a complete
specification rather than a base awaiting one. Both readings are defensible, and the
choice between them needs a judgement the text does not supply — which is why the
practical consequence is unchanged whichever label is used, and why the agent abstains.
This is recorded because the agent's own contradiction audit produced the counter-reading
unprompted and reconciled the pair on it (SPEC 6.2), and an entry that presents the
conflict as self-evident is overstating its case.

---

## B. General/specific — both hold, one carves an exception

These are **not** defects in the sense of being irresolvable, but they are places where a
careless reader gets the wrong answer from a single section, so they are logged.

### B1. §4.4 vs §5.1 — "any number" vs "more than three only with the token"
§4.4 lets a Trade "unload any number of Cargo cards"; §5.1 permits more than three only to
the Harbourmaster token holder. §4.4 read alone gives the wrong answer.

**Agent (observed, probe Q25 = 3):** General/specific → §5.1 constrains §4.4. Answers definitively,
citing both.

### B2. §3.3 vs §6.4 — roll every turn, except when you don't
§3.3 says the Storm die is rolled at the end of every player's turn; §6.4 says it is not
rolled during a Storm round.

**Agent (observed):** General/specific → §6.4 carves the exception. Answers definitively (probe
Q17 = No), citing both.

---

## C. Undefined terms

### C1. §5.4, §8.2 — "round" is never defined
Both sections turn on it: the Harbourmaster token passes to whoever unloads the largest
cargo "of the round" (§5.4), and at game end "players complete the current round" (§8.2).
The rulebook never says what a round is. §6.3 defines when a **Storm round** ends, which
is a different thing and cannot be borrowed — a Storm round is measured from an arbitrary
player's roll, not from the first player.

**Agent (specified, untested):** Undefined term → abstains on any question whose answer depends on where a round
begins or ends, naming the term and what turns on it.

### C2. §5.4 with §2.4 — "the current first player" is unidentifiable
§2.4 makes one player *both* the token holder *and* the first player, treating them as the
same appointment. §5.4 then moves the token to another player while its own tie-break
refers to "the current first player". Two readings follow, and the rulebook supports
neither over the other: the first player is fixed at setup, or the first player follows the
token. Turn order and §5.4's own tie-break resolve differently depending on which.

**Agent (specified, untested):** Undefined term → abstains on tie-break and turn-order questions that depend on
it. Compounds with C1, since §8.2's "complete the current round" needs a first player to
measure from.

---

## D. Silences — the rulebook simply does not say

### D1. §4.1 — the Draw Pile can be exhausted and nothing says what happens
Draw takes two cards from the Draw Pile. There are 60 Cargo cards, no reshuffle rule, no
discard-pile-becomes-draw-pile rule, and §3.2 and §6.2 both generate discards. Exhaustion
is reachable in normal play.

**Agent (observed, probe Q8):** Silence → `abstained: true`. Does not invent the conventional
"shuffle the discards" rule, which is exactly the plausible-sounding fabrication this class
is meant to prevent.

**Sub-defect:** §4.1 says "take two"; it does not say what happens if exactly one card
remains.

### D2. §6.2 — a Ship in the Open Sea with no Cargo "must discard"
Storm-round ships in the Open Sea "must discard one Cargo card ... from their Ship". A Ship
with no Cargo aboard cannot comply, and no exemption or penalty is stated.

**Agent (observed, probe Q13):** answers definitively — "Nothing happens to your Ship" —
citing §6.2, and does **not** abstain. This entry previously claimed it abstained on the
consequence; it does not, and the claim was written from intent rather than from a run.

On reflection the agent's behaviour is the better reading and this entry was
mis-classified: §6.2 requires discarding a card *from the Ship*, a Ship with none cannot
comply, and no penalty is stated anywhere, so "nothing happens" follows from the plain
text. The genuine gap is narrower than "silence" — the rulebook simply never contemplates
the case, and any reading of it converges on the same outcome.

### D3. §4.2 — no Ship cargo capacity
§4.2 caps a single Load at three cards of one suit. Nothing caps what a Ship may hold in
total, which is what makes §5.1's "more than three" reachable at all. Whether that is
intended or an oversight cannot be determined from the text.

**Agent (specified, untested):** Silence → abstains if asked for a Ship's maximum capacity.

### D4. §4.3 — Dock-to-Dock movement is neither permitted nor forbidden
§4.3 enumerates two moves: Open Sea → Dock, and Dock → Open Sea. A direct Dock → Dock move
is absent. Under the closed-world assumption (`SPEC.md` §3) an unlisted move is not
available, so this reads as settled — but it is listed here because the enumeration looks
like an oversight rather than a decision, and probe Q23 asserts the move as fact.

**Agent (observed, probe Q23):** False premise → corrects the premise (§4.3 permits only Sea↔Dock), then answers
that the question is moot, citing §4.3. Not an abstention.

### D5. §3.1 — "exactly two actions" may be impossible
Two actions are mandatory, and all four can be unavailable: Draw with an empty pile (D1),
Load with no cards or no three of a suit, Sail with every Dock occupied, Trade while not at
a Dock. Nothing says what a player does when fewer than two legal actions exist.

**Agent (specified, untested):** Silence → abstains.

### D6. §5.4 — when the token passes, and what if nobody unloads
Three gaps in one sentence: whether the token moves immediately or at the end of the round
(which determines §5.1 eligibility for the rest of that round), what happens in a round
where nobody unloads, and whether "the single largest cargo of the round" means the largest
single Trade action or a player's round total. "Single largest ... counted as number of
cards" suggests one Trade; "of the round" pulls the other way.

**Agent (specified, untested):** Silence / ambiguous scope → abstains, naming the readings. Compounds with C1.

### D7. §8.1 with §6 — game end inside a Storm round
§8.1 ends the game when a fourth Dock receives Cargo and §8.2 completes the round; §6.2
imposes discards throughout a Storm round. If the trigger fires mid-Storm, whether the
remaining turns still suffer storm discards is unstated.

**Agent (specified, untested):** Silence → abstains.

### D8. §8.4 — the final tie-break can run out
The last tie-break is "the tied player who most recently unloaded cargo". §8.1 guarantees
*someone* unloaded, but not that any *tied* player did. Two tied players who never unloaded
cannot be separated.

**Agent (specified, untested):** Silence → abstains on that branch.

### D9. §2.4 — "most recently travelled by boat" has no fallback
No rule for a tie, or for a table where nobody has.

**Agent (specified, untested):** Silence → abstains.

### D10. §1 — points exist but nothing records them
§7 scores points throughout and §8.4 compares totals, yet §1's component list contains no
score pad, score track or markers. The rulebook has no tracks of any kind, which is also
what settles probe Q2 (a "Tide track") in the negative.

**Agent (specified, untested — probe Q2/Q14/Q19 exercise the closed-world rule but none asks about a score track):** answers definitively that no such component
exists. Logged here because the omission looks unintended.

---

### D11. §6.2 with §6.3 — the discard's timing and frequency are unstated
"During a Storm round, all Ships in the Open Sea must discard one Cargo card" (§6.2), and
a Storm round runs until play returns to whoever rolled the wave (§6.3). Three readings
fit: one simultaneous discard when the storm begins; one discard per Ship per turn for the
duration; or one discard per Ship at the moment its own turn ends. Over a four-player
circuit those differ by several cards. Nor is it stated whether the player who rolled the
wave is affected on the very turn they rolled it, since the round begins at the end of that
turn.

**Agent (observed, probe Q22):** answers definitively that a Ship in the Open Sea must
discard, citing §6.1 and §6.2 — correct on the *who*, which §6.2 does settle, and silent on
the timing, which it does not. A question turning on frequency rather than applicability is
untested.

### D12. §5.1 with §5.4 — the token may never change hands
§5.1 limits a player without the Harbourmaster token to three cards per unload. §5.4 passes
the token to whoever unloads "the single largest cargo of the round, counted as number of
cards". A holder who unloads four or more therefore wins that comparison automatically,
because no one else is permitted to reach four — so the token is self-perpetuating and
§5.4's "passes" may describe something that, after the first round, never happens.

This is a determinate reading rather than an ambiguity, which is why it sits here rather
than under E: the text is clear, and its consequence looks unintended. Filed because a
player asking "how do I take the token?" is owed the observation.

**Agent (specified, untested):** no probe question asks this. The interaction compounds
with D6 and C1, so the abstention criteria would engage on the "of the round" boundary
before this consequence was reached.

## E. Ambiguous scope

### E1. §5.1 — "more than three onto a Dock tile": per action, per turn, or per game?
§7.2 is explicit where it needs to be ("in one Trade action"); §5.1 is not. Read
cumulatively, a token-less player could never bring a Dock tile above three cards across
the whole game — a materially different game from the per-action reading.

**Agent (observed, probe Q25):** Answers definitively because that question specifies "in one Trade
action". Abstains on the cumulative reading if asked, naming the ambiguity.

### E2. §7.2 — is the Convoy Bonus per suit or per Trade action?
"A player who unloads three or more cards of the same suit onto a single Dock in one Trade
action scores a Convoy Bonus of 5 points." A token holder unloading 3 Grain and 3 Iron in
one Trade satisfies the condition twice. Whether that scores 5 or 10 is unstated.

**Agent (observed, probe Q9 and Q21; multi-suit case untested):** answers the single-suit case definitively and
abstains on the multi-suit case, naming both readings.

### E3. §4.2 — mixed-suit Ships
Each Load moves cards "of a single suit", but nothing prevents successive Loads from
putting different suits aboard. Almost certainly intended; noted because §4.2 read alone
suggests a single-suit Ship, and the Convoy Bonus interaction (E2) depends on it.

**Agent (specified, untested):** Answers per the plain reading — the single-suit restriction is per Load action.

---

## F. What the agent's own contradiction audit found

The agent derives a contradiction register from the rulebook at load time (SPEC 6.2). Its
candidates are worth recording next to this register, because two of them are wrong and
knowing *why* is part of trusting the mechanism.

| Candidate | Verdict |
|---|---|
| §4.2 vs §7.1 | **Correct** — A1 above. Found on every observed run. |
| §4.4 vs §5.1 | **Wrong** — this is B1, a general/specific pair that composes to "3 without the token". Survived two-pass consensus on some runs, because both passes made the same mistake. |
| §4.2 vs §5.1 | **Wrong** — inferred that a Ship can hold at most three cards, so §5.1's allowance is unreachable. §4.2 caps a single Load *action*, not the Ship (D3). A play-reachability inference, not a textual conflict. |
| §5.1 vs §5.4 | **Not a contradiction, but a real finding** — the audit surfaced the pair that led to D12 above, which had not been filed by hand. |

The false positives are contained downstream rather than filtered out, because an
adversarial verification pass reconciled A1 itself 3/3 and would have emptied the register
(SPEC 6.2). The residual risk is a wrong abstention on an answerable question, which shows
up as an eval failure rather than a silent wrong answer.

## G. Checked and consistent

Recorded so the register shows what was verified, not only what failed.

- §1: 60 Cargo cards = 4 suits × 5 values × 3 copies. Consistent.
- §2.2: 12 Dock tiles = 6 on the Quay + 6 boxed. Consistent.
- §8.1: a fourth Dock receiving Cargo is reachable with 6 on the Quay. Consistent.
- §1: Storm die, 4 blank + 2 wave = 6 sides. Consistent.
- §1/§2.3: 4 Ship pawns for a 2–4 player game. Consistent.
- §4.3: "any unoccupied Dock tile" and "only one Ship may occupy a Dock tile" are
  redundant but not contradictory.
- §7.1: Iron at "face value + 1" tops out at 6 for an Iron 5. No conflict with §7.2.

---

## H. Not rulebook defects

Logged to keep the register honest about what it is claiming.

Probe Q2 (Tide track), Q14 (Copper suit) and Q19 (Lighthouse tile) name things that do not
exist. That is a property of the **questions**, not a defect in the rulebook — §1 and §7.1
enumerate components and suits exhaustively. The agent answers all three definitively in
the negative (`abstained: false`) under `SPEC.md` §3. D10 is the one place where an
absence in §1 does look like a genuine omission.

Probe Q6, Q16 and Q23 embed false premises. Also a property of the questions; the rulebook
is internally consistent on Iron scoring (§7.1), actions per turn (§3.1) and legal Sail
moves (§4.3).
