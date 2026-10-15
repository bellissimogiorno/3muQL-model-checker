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
axiom ObserveBack: observe → ∃Q□vote
axiom ObserveNotBack: ¬observe → ∃Q□¬vote
axiom ObserveForward: ∃Q□vote ⇀ observe
axiom ObserveNotForward: ∃Q□¬vote ⇀ ¬observe

property Agreement: ¬(∃Q◇T(observe) ∧ ∃Q◇T(¬observe))
property UnanimousTrueDelivery: ∃Q□vote ⇀ ∀Q□observe
property UnanimousFalseDelivery: ∃Q□¬vote ⇀ ∀Q□¬observe
```
