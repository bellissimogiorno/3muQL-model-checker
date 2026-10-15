# Declarative Bracha Broadcast

One sender broadcasts a payload. Participants may echo it, become ready, and
deliver it. The four predicates record the declarative outcome, rather than a
sequence of message arrivals.

The axioms below transcribe Figure 10 of
[Gabbay, arXiv:2512.21137v3](https://arxiv.org/pdf/2512.21137v3). The properties
are Figure 11. The three-way intersection assumption from Remark 4.2.1 is
explicit. Names ending `Back` correspond to the paper's `?`, names ending
`Forward` to `!`, and `Relay` to `!!`.

Read `∃ꟴ□` as “some quorum, every point”, `∃ꟴ◇` as “some quorum, some point”,
and `∀ꟴ□` as “every quorum, every point”. The [notation guide](../docs/notation.md) lists their ASCII
spellings and explains the remaining symbols.

```muql
theory "Bracha Broadcast"
points alice bob carol dave
values red blue
stages 1
quorums {alice,bob,carol} {alice,bob,dave} {alice,carol,dave} {bob,carol,dave}
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
axiom BrDeliverBack: ∀ v. dlvr(v) → ∃ꟴ□(ready(v))
axiom BrReadyBack: ∀ v. ready(v) → ∃ꟴ□(echo(v))
axiom BrEchoBack: ∀ v. echo(v) → ∃ꟴ◇(bcst(v))

# Uniqueness of echoes and of the broadcast value.
axiom BrEchoAffine: ∃⁰¹ v. echo(v)
axiom BrBroadcastUnique: ∃¹ v. ∃ꟴ◇(bcst(v))

# Forward rules and the ready relay.
axiom BrDeliverForward: ∀ v. ∃ꟴ□(ready(v)) → dlvr(v)
axiom BrReadyForward: ∀ v. ∃ꟴ□(echo(v)) → ready(v)
axiom BrEchoForward: ∀ v. ∃ꟴ◇(bcst(v)) → (∃ w. echo(w))
axiom BrReadyRelay: ∀ v. ∀ꟴ◇(ready(v)) → ready(v)

# Correctness quorums and predicate-by-predicate uniformity.
axiom BrCorrect: ∃ꟴ□(ReadyCorrect()) ∧ ∃ꟴ□(EchoCorrect())
axiom BrReadyUniform: ReadyCorrect() ∨ ReadyFaulty()
axiom BrEchoUniform: EchoCorrect() ∨ EchoFaulty()
axiom BrBroadcastUniform: ∀ꟴ□(BroadcastCorrect()) ∨ ∀ꟴ□(BroadcastFaulty())

# Properties checked against all the axioms above.
property BrValidity: ∀ v. ∃ꟴ◇(bcst(v)) → ∀ꟴ□(dlvr(v))
property BrNoDup: ∃⁰¹ v. dlvr(v)
property BrIntegrity: ∀ v. dlvr(v) → ∃ꟴ◇(bcst(v))
property BrConsistency: ∃⁰¹ v. ∃ꟴ◇(dlvr(v))
property BrTotality: ∀ v. ∃ꟴ◇(dlvr(v)) → ∀ꟴ□(dlvr(v))
```

`∃⁰¹ v. echo(v)` permits at most one **true** echo. A faulty participant may
return `b` for every payload. An affine formula can itself be `b`, which is
valid. Replacing it by a Boolean count of non-false echoes changes the theory.

The correctness quorums for `echo` and `ready` may differ. The uniformity axioms
apply separately to each predicate. The paper does not impose uniformity on
`dlvr`; that detail matters in [the weakening example](bracha_weakened.md).

Try removing `BrEchoAffine` to see why echo uniqueness matters. Removing
`BrReadyRelay` illustrates how totality can fail even though integrity and
consistency remain constrained. The checker reports only the selected finite
scope; absence of a countermodel is not an unbounded proof.
