# Simpler Declarative Paxos — the complete Figure 12 theory

This is **TySPax**, Definition 8.2.1 and Figure 12 (pp.67–68) of the attached
Paxos paper. All 12 axioms are present. This is the paper's own abstraction:
`send` and `undef` disappear, leaders need not be unique, and all writes at a
stage must agree globally. The forward write rule is also changed, so this theory
is not obtained merely by deleting some TyPax axioms.

The scope is finite. The safety formulas include history from time zero, while
infinite-time liveness remains subject to the checker limitations documented in
the main README. A finite result does not establish Theorem 8.2.2 unboundedly.

Notation: `⇀` is strong implication (`-\` in ASCII), `→` is weak (`->`),
and `∃ꟴ◇` means “some quorum, some point”. All symbols have
[ASCII equivalents](../docs/notation.md); either style is accepted.

```muql
theory "Simpler Declarative Paxos (Figure 12)"
points a b c
values red blue
stages 3
time stutter
quorums {a,b} {a,c} {b,c}
predicate leader/0
predicate propose/1
predicate write/1
predicate accept/1
predicate decide/1

# Backward rules: the evidence required to justify an event.
axiom SPaxPropose?: ∀ v. propose(v) ⇀ leader
axiom SPaxWrite?:
  ∀ v. write(v) ⇀ (
    leader ∧ ∃ꟴ(
      (latest x = v. ◇(accept(x)))
      ∨ (propose(v) ∧ ¬T(once(∃ x. ◇(accept(x)))))
    )
  )
axiom SPaxAccept?: ∀ v. accept(v) ⇀ ∃ꟴ◇(write(v))
axiom SPaxDecide?: ∀ v. decide(v) ⇀ ∃ꟴ□(accept(v))

# Forward rules: progress, subject to the eventual-delivery assumption.
axiom SPaxWrite!: ultimately(leader → (∃ v. write(v)))
axiom SPaxAccept!: ultimately((∃ v. ∃ꟴ◇(write(v))) → (∃ v. accept(v)))
axiom SPaxDecide!: ultimately((∃ v. ∃ꟴ□(accept(v))) → (∃ v. decide(v)))

# Leadership and recurring correct leaders.
axiom SLdrExist: TF(leader) ∧ T(∃ꟴ◇(leader))
axiom SLdrCorrect:
  infinitely(∃ꟴ◇(
    leader ∧ (∀ v. TF(propose(v))) ∧ (∀ v. TF(write(v))) ∧ (∀ v. TF(decide(v)))
  ))

# Correctness, uniqueness, and quorum intersection.
axiom SPaxPCorrect: ∃ꟴ□(∀ v. TF(accept(v)))
axiom SPaxWrite01: ∃⁰¹ v. ∃ꟴ◇(write(v))
axiom SPax2Twined: ∀ v. ∃ꟴ□(accept(v)) ⇀ ∀ꟴ◇(accept(v))

# Safety and liveness properties.
property Validity: ∀ v. decide(v) ⇀ past(∃ꟴ◇(leader ∧ propose(v)))
property Agreement:
  ∀ v. ∀ w. (past(∃ꟴ◇(decide(v))) ∧ ∃ꟴ◇(decide(w))) ⇀ v = w
property Termination: infinitely(∀ꟴ□(∃ v. decide(v)))
```

The properties express validity, agreement, and termination from Theorem 8.2.2.
`Agreement` states that a true decision now or earlier agrees with any true
decision now. Its two premises are combined with conjunction before a single
strong implication. All twelve Figure 12 axioms are present.
See [the natural-time agreement proof](../docs/spax-agreement.md).

Integrity is discussed in
the paper as an interpretation of repeated decisions plus agreement; it is not a
separate at-most-once machine-execution property (§7.1.2).

`SPaxPCorrect` only requires a correct accepting quorum. The full Paxos theory's
stronger deciding-quorum observation is not silently imported here. Distinct
predicates and distinct stages may have different sets of crashed participants.

Useful experiments are removing `SPaxWrite01` (simultaneous disagreement),
`SPaxAccept?` (decisions without a proposal), or a progress axiom (stalled
computation). To expose a missing intersection requirement, change the quorums
to `{a} {b} {c}` and remove `SPax2Twined`; the default majority frame itself
already guarantees that rule.

This example explicitly selects `time stutter`: the final stage has a future
self-loop, while past operators still inspect the displayed finite prefix. It is
a finite temporal **frame**, not an ultimately periodic execution on the paper's
natural-number timeline. Treat any temporal counterexample as a frame result and
check for boundary artifacts before drawing conclusions about the paper.
