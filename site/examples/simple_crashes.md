# Simple: reliable delivery, crashes allowed

This is the second Simple theory (§6.1, p.47). The backward implications remain
strong; forward implications become weak so their conclusions may be `b`.
Each predicate has a dense set of uncrashed participants. The paper's Uncrashed
schema is written as three individually named axioms for easier experiments.
The two properties are tutorial consequences.

Notation: `⇀` is strong implication (`-\` in ASCII), `→` is weak (`->`),
and `∃ꟴ◇` means “some quorum, some point”. All symbols have
[ASCII equivalents](../docs/notation.md); either style is accepted.

```muql
theory "Simple: reliable delivery, crashes allowed"
points a b c
values unit
stages 1
quorums {a,b} {a,c} {b,c}
predicate propose/0
predicate accept/0
predicate decide/0

# Backward rules: a true event must be justified.
axiom SimpAccept?: accept ⇀ ∃ꟴ◇(propose)
axiom SimpDecide?: decide ⇀ (propose ∧ ∃ꟴ◇(accept))

# Forward rules: delivery and progress.
axiom SimpAccept!: ∃ꟴ◇(propose) → accept
axiom SimpDecide!: (propose ∧ ∃ꟴ◇(accept)) → decide

# Each predicate has a dense set of uncrashed participants.
axiom Uncrashed_propose: ∀ꟴ◇(TF(propose))
axiom Uncrashed_accept: ∀ꟴ◇(TF(accept))
axiom Uncrashed_decide: ∀ꟴ◇(TF(decide))

# Tutorial consequences.
property NoInventedDecision: decide ⇀ propose
property ProposerDecidesOrCrashes: propose → decide
```

The three dense sets need not coincide. A proposer may have a true proposal and
a crashed decision. Thus changing the second property from weak `→` to strong
`⇀` creates a useful counterexample experiment without changing the theory.
