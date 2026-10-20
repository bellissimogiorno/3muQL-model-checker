# Generated finite model scope

This standalone theory retains the searched axioms and properties.
Its explicit frame can be checked again or used to replay the accompanying witness.

```muql
theory 'Voting'
points 'p0' 'p1'
values 'unit'
stages 1
time finite
quorums {'p0','p1'}
predicate vote/0
predicate observe/0

axiom Intersection: twined(3)
axiom Observe?: observe → ∃ꟴ□vote
axiom ObserveNot?: ¬observe → ∃ꟴ□¬vote
axiom Observe!: ∃ꟴ□vote ⇀ observe
axiom ObserveNot!: ∃ꟴ□¬vote ⇀ ¬observe

property Agreement: ¬(∃ꟴ◇T(observe) ∧ ∃ꟴ◇T(¬observe))
property UnanimousTrueDelivery: ∃ꟴ□vote ⇀ ∀ꟴ□observe
property UnanimousFalseDelivery: ∃ꟴ□¬vote ⇀ ∀ꟴ□¬observe
```
