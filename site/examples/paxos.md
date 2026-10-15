# Declarative Paxos — the complete Figure 11 theory

This is a direct transcription of **TyPax**, Definition 6.3.1 and Figure 11
(pp.49–50) of the attached paper, *A declarative approach to specifying Paxos using
three-valued modal fixpoint logic*, by Murdoch J. Gabbay and Luca Zanolini.
It includes all 20 named axioms, including the `send` step and the nonpositive
`μ` expression for leader uniqueness.

A point is a participant. A stage is a ballot or logical round, not a message or
machine instruction. `b` means a computation has crashed; both `b` and `t` count
as valid. Consequently, `P → Q` permits a crashed conclusion, while `P ⇀ Q`
requires a true conclusion whenever `P` is true.

The finite scope below chooses three participants, two ordinary values and the
special value `undef`. The three pair quorums generate the usual majority
semitopology. The checker reports results for its documented finite temporal
semantics; these are **not proofs of the paper's infinite-time theorems**.

Notation: `⇀` is strong implication (`-\` in ASCII), `→` is weak (`->`),
and `∃ꟴ◇` means “some quorum, some point”. All symbols have
[ASCII equivalents](../docs/notation.md); either style is accepted.

```muql
theory "Declarative Paxos (Figure 11)"
points a b c
values red blue undef
stages 3
time stutter
quorums {a,b} {a,c} {b,c}
predicate leader/0
predicate propose/1
predicate send/1
predicate write/1
predicate accept/1
predicate decide/1

# Backward rules: the evidence required to justify an event.
axiom PaxPropose_back: ∀ v. propose(v) ⇀ (leader ∧ v ≠ undef)
axiom PaxSend_back:
  ∀ v. send(v) ⇀ (
    ∃ꟴ◇(∃ x. propose(x))
    ∧ ((latest x = v. accept(x))
       ∨ (¬T(once(∃ x. accept(x))) ∧ v = undef))
  )
axiom PaxWrite_back:
  ∀ v. write(v) ⇀ (
    leader ∧ ∃ꟴ(
      □(∃ x. send(x))
      ∧ ((latest x = v. ◇(accept(x)))
         ∨ (propose(v) ∧ ¬T(once(∃ x. ◇(accept(x))))))
    )
  )
axiom PaxAccept_back: ∀ v. accept(v) ⇀ ∃ꟴ◇(write(v))
axiom PaxDecideL_back: ∀ v. leader ⇀ (decide(v) ⇀ ∃ꟴ□(accept(v)))
axiom PaxDecideNotL_back: ∀ v. ¬leader ⇀ (decide(v) ⇀ ∃ꟴ◇(leader ∧ decide(v)))

# Forward rules: progress, subject to the eventual-delivery assumption.
axiom PaxPropose_forward: leader → (∃ v. propose(v))
axiom PaxSend_forward: ultimately(∃ꟴ◇(∃ v. propose(v)) → (∃ v. send(v)))
axiom PaxWrite_forward:
  ultimately(
    (leader ∧ ∃ꟴ□(∃ v. send(v)) ∧ (∃ v. propose(v))) → (∃ v. write(v))
  )
axiom PaxAccept_forward: ultimately((∃ v. ∃ꟴ◇(write(v))) → (∃ v. accept(v)))
axiom PaxDecideL_forward:
  ultimately((leader ∧ (∃ v. ∃ꟴ□(accept(v)))) → (∃ v. decide(v)))
axiom PaxDecideNotL_forward:
  ultimately(
    (¬leader ∧ ∃ꟴ◇(leader ∧ (∃ v. decide(v)))) → (∃ v. decide(v))
  )

# Leadership and recurring correct leaders.
axiom LdrExist: TF(leader) ∧ T(∃ꟴ◇(leader))
axiom LdrUniq: ◇(μ X. ¬◇(leader ∧ X))
axiom LdrCorrect:
  infinitely(∃ꟴ◇(
    leader ∧ (∀ v. TF(propose(v))) ∧ (∀ v. TF(write(v))) ∧ (∀ v. TF(decide(v)))
  ))

# Correctness, uniqueness, and quorum intersection.
axiom PaxPCorrect:
  ∃ꟴ□(∀ v. TF(propose(v))) ∧ ∃ꟴ□(∀ v. TF(send(v)))
  ∧ ∃ꟴ□(∀ v. TF(accept(v))) ∧ ∃ꟴ□(∀ v. TF(write(v)))
  ∧ ∃ꟴ□(∀ v. TF(decide(v)))
axiom PaxPropose01: ∃⁰¹ v. propose(v)
axiom PaxWrite01: ∃⁰¹ v. write(v)
axiom Pax2Twined: ∀ v. ∃ꟴ□(accept(v)) ⇀ ∀ꟴ◇(accept(v))
axiom PaxNontriv: ∃ v. v ≠ undef

# Safety and liveness properties.
property Validity: ∀ v. decide(v) ⇀ past(∃ꟴ◇(leader ∧ propose(v)))
property Agreement:
  ∀ v. ∀ w. (past(∃ꟴ◇(decide(v))) ∧ ∃ꟴ◇(decide(w))) ⇀ v = w
property Termination: infinitely(∀ꟴ□(∃ v. decide(v)))
property DecidingQuorum: infinitely(∃ꟴ□(T(∃ v. decide(v))))
```

`Validity`, `Agreement`, and `Termination` transcribe Theorems 7.2.3, 7.3.6, and
7.4.7. `DecidingQuorum` transcribes the stronger liveness observation in Remark
7.4.8. The package's finite result must be read with the temporal limitations
reported by the checker.

The `latest` in `PaxWrite_back` encloses `◇`: it finds the latest acceptance
anywhere in the selected quorum. Moving `◇` outside `latest` would choose
an individual participant's latest acceptance, which may be stale. Section 6.6.1
explicitly warns about that change.

`LdrUniq` is intentionally nonpositive. Under `TF(leader)`, its value for a quorum
is `t`, `b`, or `f` when that quorum has zero, one, or at least two leaders
(Corollary 6.6.6). A checker that requires every axiom to be `t` would reject the
intended one-leader model.

Try removing `PaxWrite01` to permit conflicting writes. For cross-stage quorum
failures, use a frame with disjoint quorums and remove `Pax2Twined`; deleting that
axiom on this majority frame has no effect because the frame already implies it.
The paper also identifies `PaxSend_back` and `PaxPropose01` as unnecessary for
its correctness proofs (§8.1.1), a useful positive weakening experiment.

This example explicitly selects `time stutter`: the final stage has a future
self-loop, while past operators still inspect the displayed finite prefix. It is
a finite temporal **frame**, not an ultimately periodic execution on the paper's
natural-number timeline. Treat any temporal counterexample as a frame result and
check for boundary artifacts before drawing conclusions about the paper.
