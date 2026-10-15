# Simple: eventual delivery, no crashes

This is the third Simple theory (§6.1, p.47). An initial period may lose messages;
eventually the forward rules apply at every point in every quorum forever. The logical model has no
explicit messages. `ultimately` expresses the network assumption.

The original theory is about infinite natural time. This literate input retains
its temporal formulas in Unicode notation; finite checking must be interpreted
according to the package's stated temporal support and boundaries. The added
properties are tutorial consequences of the intended infinite theory.

Notation: `⇀` is strong implication (`-\` in ASCII), `→` is weak (`->`),
and `∃ꟴ◇` means “some quorum, some point”. All symbols have
[ASCII equivalents](../docs/notation.md); either style is accepted.

```muql
theory "Simple: eventual delivery, no crashes"
points a b c
values unit
stages 3
time stutter
quorums {a,b} {a,c} {b,c}
predicate propose/0
predicate accept/0
predicate decide/0

# Backward rules: a true event must be justified.
axiom SimpAccept_back: accept ⇀ ∃ꟴ◇(propose)
axiom SimpDecide_back: decide ⇀ (propose ∧ ∃ꟴ◇(accept))

# Forward rules: delivery and progress.
axiom SimpAccept_forward: ultimately(∃ꟴ◇(propose) ⇀ accept)
axiom SimpDecide_forward: ultimately((propose ∧ ∃ꟴ◇(accept)) ⇀ decide)

# All three predicates are uncrashed.
axiom Correct: TF(propose) ∧ TF(accept) ∧ TF(decide)

# Tutorial consequences.
property NoInventedDecision: decide ⇀ propose
property EventualProgressRule: ultimately(propose ⇀ decide)
```

A proposal during the unreliable period need not lead to a decision. The second
property says that the progress implication eventually stabilizes; it does not
assume proposals occur or that an initial proposal is retried forever.

This example explicitly selects `time stutter`: the final stage has a future
self-loop, while past operators still inspect the displayed finite prefix. It is
a finite temporal **frame**, not an ultimately periodic execution on the paper's
natural-number timeline. Treat any temporal counterexample as a frame result and
check for boundary artifacts before drawing conclusions about the paper.
