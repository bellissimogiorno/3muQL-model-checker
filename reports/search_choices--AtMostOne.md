# Generated finite model scope

This standalone theory retains the searched axioms and properties.
Its explicit frame can be checked again or used to replay the accompanying witness.

```muql
theory 'Correct choices need not be unique'
points 'p0'
values 'v0' 'value0'
stages 1
time finite
quorums {'p0'}
predicate chosen/1

axiom Correct: ∀ v. TF(chosen(v))

property AtMostOne: ∃⁰¹ v. chosen(v)
```
