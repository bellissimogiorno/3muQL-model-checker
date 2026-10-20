# A countermodel to the proposed existential delivery weakening

Section 4.3 of [the companion paper, v3](https://arxiv.org/pdf/2512.21137v3)
claims that `BrDeliver!` can be weakened to existential delivery and recovered
from the other axioms. For Figure 10 as printed, the claim fails.

This file contains the same Bracha axioms, except for that one proposed
replacement. A one-participant, two-payload scope already suffices. The singleton
quorum is three-way intersecting, so the failure is unrelated to quorum geometry.

The [notation guide](../docs/notation.md) gives an ASCII equivalent for each
Unicode symbol below. In particular, `→` is weak implication (`->`).

```muql
theory "Bracha with existential delivery"
points alice
values red blue
stages 1
quorums {alice}
predicate bcst/1
predicate echo/1
predicate ready/1
predicate dlvr/1

# Correct means t or f for every payload; faulty means b for every payload.
let EchoCorrect(): ∀ v. TF(echo(v))
let ReadyCorrect(): ∀ v. TF(ready(v))
let BroadcastCorrect(): ∀ v. TF(bcst(v))
let EchoFaulty(): ∀ v. B(echo(v))
let ReadyFaulty(): ∀ v. B(ready(v))
let BroadcastFaulty(): ∀ v. B(bcst(v))

# Three-way quorum intersection.
axiom Intersection: twined(3)

# Backward rules: justify delivery, readiness, and echo.
axiom BrDeliver?: ∀ v. dlvr(v) → ∃ꟴ□(ready(v))
axiom BrReady?: ∀ v. ready(v) → ∃ꟴ□(echo(v))
axiom BrEcho?: ∀ v. echo(v) → ∃ꟴ◇(bcst(v))

# Uniqueness of echoes and of the broadcast value.
axiom BrEchoAffine: ∃⁰¹ v. echo(v)
axiom BrBroadcastUnique: ∃¹ v. ∃ꟴ◇(bcst(v))

# The proposed weakening changes only the delivery rule.
axiom BrDeliverExistential!: (∃ v. ∃ꟴ□(ready(v))) → (∃ v. dlvr(v))
axiom BrReady!: ∀ v. ∃ꟴ□(echo(v)) → ready(v)
axiom BrEcho!: ∀ v. ∃ꟴ◇(bcst(v)) → (∃ w. echo(w))
axiom BrReady!!: ∀ v. ∀ꟴ◇(ready(v)) → ready(v)

# Correctness quorums and predicate-by-predicate uniformity.
axiom BrCorrect: ∃ꟴ□(ReadyCorrect()) ∧ ∃ꟴ□(EchoCorrect())
axiom BrReadyUniform: ReadyCorrect() ∨ ReadyFaulty()
axiom BrEchoUniform: EchoCorrect() ∨ EchoFaulty()
axiom BrBroadcastUniform: ∀ꟴ□(BroadcastCorrect()) ∨ ∀ꟴ□(BroadcastFaulty())

# Properties checked against all the axioms above.
property OriginalDeliverForward: ∀ v. ∃ꟴ□(ready(v)) → dlvr(v)
property BrValidity: ∀ v. ∃ꟴ◇(bcst(v)) → ∀ꟴ□(dlvr(v))
```

One concrete witness is:

| Predicate at alice | red | blue |
|---|---|---|
| `bcst` | t | f |
| `echo` | t | f |
| `ready` | t | f |
| `dlvr` | f | b |

The weakened rule evaluates to `t → b`, hence `b`, a valid value. The backward
delivery rule for blue is `b → f`, also `b`. All other axioms are valid.
Nevertheless, red is genuinely broadcast and is not delivered: `BrValidity`
evaluates to `f`.

The original theory has no uniformity axiom for `dlvr`, so it permits the mixed
`f,b` delivery row when the original forward rule is removed. Adding a
delivery-uniformity assumption rules out this particular witness; retaining
the original `BrDeliver!` also rules it out.

This is a counterexample to a **proposed weakening in the discussion**, not to
the original Bracha correctness results. Solver witnesses may exchange the two
payload names or choose another equivalent violating assignment.
