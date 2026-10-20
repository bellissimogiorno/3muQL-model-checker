# Simple: reliable delivery, no crashes

The first Simple theory in §6.1 of the Paxos paper (p.46) abstracts a protocol in
which anyone may propose, everyone accepts a proposal, and a proposer decides
when someone accepts. There is only one unnamed value, so all three predicates
are nullary. These are the five exact axioms. The two properties below are
small tutorial consequences, not named theorems from the paper.

Notation: `⇀` is strong implication (`-\` in ASCII), `→` is weak (`->`),
and `∃ꟴ◇` means “some quorum, some point”. All symbols have
[ASCII equivalents](../docs/notation.md); either style is accepted.

```muql
theory "Simple: reliable delivery, no crashes"
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
axiom SimpAccept!: ∃ꟴ◇(propose) ⇀ accept
axiom SimpDecide!: (propose ∧ ∃ꟴ◇(accept)) ⇀ decide

# All three predicates are uncrashed.
axiom Correct: TF(propose) ∧ TF(accept) ∧ TF(decide)

# Tutorial consequences.
property NoInventedDecision: decide ⇀ propose
property ProposerDecides: propose ⇀ decide
```

Try removing `SimpDecide!`: a true proposal can coexist with acceptance
and a false decision. No axiom requires anyone to propose, so unconditional
termination is intentionally not asserted.
