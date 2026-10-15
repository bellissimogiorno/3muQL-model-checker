# Fixed points, recurrences, and a nonmonotone warning

Run `python -m muql check examples/fixedpoints.md`. The scope has three
stages and one point. Stutter mode makes the final stage its own future
successor. `pulse` is unconstrained, so recurrence identities are tested
against every three-valued pulse sequence in this scope.

Use `μ` for a least fixed point and `ν` for a greatest fixed point;
ASCII `mu` and `nu` work identically. Temporal operators keep their readable
word names. See the [notation guide](../docs/notation.md) for every spelling.

```muql
theory "Fixed points on a finite context lattice"
points alice
values unit
stages 3
time stutter
quorums {alice}
predicate pulse/0
```

The least recurrence that remembers a current or earlier pulse is precisely
`past(pulse)`. Moving the pulse inside `yesterday` excludes the present and
gives `once(pulse)`. For the future recurrences below, the stuttering final
stage gives the expected least and greatest fixed-point characterizations.

```muql
property InclusivePast: (μ X. pulse ∨ yesterday(X)) ≡ past(pulse)
property StrictPast: (μ X. yesterday(pulse ∨ X)) ≡ once(pulse)
property StrictFuture: (μ X. tomorrow(pulse ∨ X)) ≡ sometime(pulse)
property FutureGreatest: (ν X. tomorrow(pulse ∧ X)) ≡ forever(pulse)
property EmptyPastRecurrence: (μ X. yesterday(X)) ≡ f
```

The paper defines `μ` as the meet of **all pre-fixed points**, even for
nonmonotone bodies. The package implements that definition exactly within
its stated finite resource budget. It does not silently apply monotone
iteration to a nonmonotone formula.

For `μ X. F(X)`, both `b` and `t` are pre-fixed points: `F(b)=f ≤ b`
and `F(t)=f ≤ t`. The value `f` is not pre-fixed, since `F(f)=t`.
Their meet is therefore `b`, but `F(b)=f`. This provides an explicit
counterexample to unconditional unfolding of a nonmonotone `μ`.

```muql
property NonmonotoneMeet: (μ X. F(X)) ≡ b
property UnfoldingRequiresMonotonicity: (μ X. F(X)) ≡ F(μ X. F(X))
property NegationMeet: (μ X. ¬X) ≡ b
```

`UnfoldingRequiresMonotonicity` is the only expected failure. It is a
deliberately invalid proposed law, not a counterexample to the paper's
definition. `ν` is the package's dual convenience; its general definition
uses the join of post-fixed points.

Experiment: change `time stutter` to `time finite`. The future recurrence
`FutureGreatest` can fail at the terminal boundary, where `forever` takes
the empty meet `t`, but `tomorrow` is `f`. A temporal-frame boundary is
part of the model, not an implementation detail.
