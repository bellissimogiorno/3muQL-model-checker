# Voting: why three-way quorum intersection matters

Four participants each cast one Boolean vote. A vote of `b` represents conflicting
messages; an observation of `b` means that no result was observed. These are
different interpretations of the same logical truth value.

This file transcribes Figure 3 and Proposition 2.5.7 of
[Gabbay, arXiv:2512.21137v3](https://arxiv.org/pdf/2512.21137v3), with Unicode symbols
for the connectives. Every axiom is checked at every participant. The quorum
generators are the four three-person subsets; their unions are implicit.

The formulas use Unicode for readability. Every symbol also has an
[ASCII spelling](../docs/notation.md), and the two styles can be mixed.

```muql
theory "Voting"
points alice bob carol dave
values unit
stages 1
quorums {alice,bob,carol} {alice,bob,dave} {alice,carol,dave} {bob,carol,dave}
predicate vote/0
predicate observe/0

# Three-way intersection, followed by backward and forward rules.
axiom Intersection: twined(3)
axiom ObserveBack: observe() → ∃ꟴ□(vote())
axiom ObserveNotBack: ¬observe() → ∃ꟴ□(¬vote())
axiom ObserveForward: ∃ꟴ□(vote()) ⇀ observe()
axiom ObserveNotForward: ∃ꟴ□(¬vote()) ⇀ ¬observe()

# At least one quorum casts unbroken votes.
axiom Correct: ∃ꟴ□(TF(vote()))

# Opposite true observations cannot coexist.
property Agreement: ¬(∃ꟴ◇(T(observe())) ∧ ∃ꟴ◇(T(¬observe())))

# These two are useful forward-delivery checks, directly implied by the axioms.
property UnanimousTrueDelivery: ∃ꟴ□(vote()) ⇀ ∀ꟴ□(observe())
property UnanimousFalseDelivery: ∃ꟴ□(¬vote()) ⇀ ∀ꟴ□(¬observe())
```

`→` (`->`) is weak implication; `⇀` (`-\`) is strong implication. Validity admits `t` and
`b`, but a strong implication with a `t` antecedent requires a `t` consequent.

Try dropping `Correct`: conflicting Byzantine votes can then justify opposite
observations. Or change the forward arrows to `→`, as suggested by Remark
2.5.9 to model unreliable delivery: agreement survives, while a fully observed
result is no longer guaranteed. To study insufficient quorum intersection,
use three participants with the three two-person quorums and drop `Intersection`.
Those quorums intersect pairwise, but all three have empty intersection.
