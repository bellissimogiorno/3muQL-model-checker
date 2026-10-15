# Three values: small surprises you can inspect

Run `python -m muql check examples/basics.md`. Several properties deliberately
fail. These are teaching examples of tempting classical assumptions, not
claims made by either paper.

Our one-point, one-stage scope makes a countermodel a short truth assignment.
The predicates `P`, `Q`, and `R` are unconstrained. Both choices are forced
to the broken value by a crisp `B` test.

The examples use Unicode: `¬`, `∧`, and `∨` mean not, and, and or;
`→` is weak implication, `⇀` is strong implication, and `≡` compares truth
values exactly. ASCII works too: write `!`, `&`, `|`, `->`, `-\`, and `<=>`.
See the [notation guide](../docs/notation.md) for the full side-by-side reference.

```muql
theory "Three values and the meaning of uniqueness"
points alice
values red blue
stages 1
time finite
quorums {alice}
predicate P/0
predicate Q/0
predicate R/0
predicate choice/1

axiom ChoicesBroken: ∀ v. B(choice(v))
```

Satisfaction means `t` or `b`. Consequently the broken constant is valid,
but asserting that it is actually true fails. Excluded middle is designated
for every input, but its value is `b` when `P` is `b`.

```muql
property BrokenIsDesignated: b
property BrokenIsTrue: T(b)
property ExcludedMiddle: P ∨ ¬P
property CrispExcludedMiddle: T(P ∨ ¬P)
property WeakDefinition: (P → Q) ≡ (¬P ∨ Q)
property StrongDefinition: (P ⇀ Q) ≡ (¬P ∨ T(Q))
```

Weak implication curries. Strong implication does not generally curry:
take `P=t`, `Q=b`, and `R=f`. Then `(P ∧ Q) ⇀ R` is `b`, while
`P ⇀ (Q ⇀ R)` is `f`. The truth-value equality below finds such a
countermodel automatically.

```muql
property WeakCurrying: ((P ∧ Q) → R) ≡ (P → (Q → R))
property StrongCurrying: ((P ∧ Q) ⇀ R) ≡ (P ⇀ (Q ⇀ R))
```

The paper defines `∃¹` using weak implication. With both `choice(red)`
and `choice(blue)` equal to `b`, `∃¹ v. choice(v)` is `b`: designated,
although there is no actually true witness. Applying `T` to the predicate
inside the quantifier gives the classical, crisp question.

```muql
property DesignatedUnique: ∃¹ v. choice(v)
property UniqueIsCrisp: T(∃¹ v. choice(v))
property TrueWitness: ∃ v. T(choice(v))
property AtMostOneActuallyTrue: ∃⁰¹ v. T(choice(v))
```

Expected counterexamples: `BrokenIsTrue`, `CrispExcludedMiddle`,
`StrongCurrying`, `UniqueIsCrisp`, and `TrueWitness`. All other properties
hold in this scope. Try removing `ChoicesBroken`: `DesignatedUnique` can
then fail, for example when both choices are `t` or both are `f`.
