# Simple: eventual delivery, crashes allowed

The fourth Simple theory (§6.1, pp.47–48) combines eventual synchrony with a
dense set of uncrashed participants for each predicate. Strong backward rules
justify true events; weak forward rules permit crashed outcomes. All source
axioms are retained. Properties are tutorial consequences, and infinite-time
formulas retain the package's documented finite-checking limitations.

Notation: `⇀` is strong implication (`-\` in ASCII), `→` is weak (`->`),
and `∃ꟴ◇` means “some quorum, some point”. All symbols have
[ASCII equivalents](../docs/notation.md); either style is accepted.

```muql
theory "Simple: eventual delivery, crashes allowed"
points a b c
values unit
stages 3
time stutter
quorums {a,b} {a,c} {b,c}
predicate propose/0
predicate accept/0
predicate decide/0

# Backward rules: a true event must be justified.
axiom SimpAccept?: accept ⇀ ∃ꟴ◇(propose)
axiom SimpDecide?: decide ⇀ (propose ∧ ∃ꟴ◇(accept))

# Forward rules: delivery and progress.
axiom SimpAccept!: ultimately(∃ꟴ◇(propose) → accept)
axiom SimpDecide!: ultimately((propose ∧ ∃ꟴ◇(accept)) → decide)

# Each predicate has a dense set of uncrashed participants.
axiom Uncrashed_propose: ∀ꟴ◇(TF(propose))
axiom Uncrashed_accept: ∀ꟴ◇(TF(accept))
axiom Uncrashed_decide: ∀ꟴ◇(TF(decide))

# Tutorial consequences.
property NoInventedDecision: decide ⇀ propose
property EventualProgressRule: ultimately(propose → decide)
```

Weakening a correctness assumption can permit every apparent acceptance to be
`b`. Inspect countermodels' truth values: a valid crashed assertion is not a
successful acceptance or decision.

This example explicitly selects `time stutter`: the final stage has a future
self-loop, while past operators still inspect the displayed finite prefix. It is
a finite temporal **frame**, not an ultimately periodic execution on the paper's
natural-number timeline. Treat any temporal counterexample as a frame result and
check for boundary artifacts before drawing conclusions about the paper.
