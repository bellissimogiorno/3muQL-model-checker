# Generated finite model scope

This standalone theory retains the searched axioms and properties.
Its explicit frame can be checked again or used to replay the accompanying witness.

```muql
theory 'Simpler Declarative Paxos (Figure 12)'
points 'p0'
values 'red' 'blue'
stages 1
time stutter
quorums {'p0'}
predicate leader/0
predicate propose/1
predicate write/1
predicate accept/1
predicate decide/1

axiom SPaxPropose?: ∀ v. propose(v) ⇀ leader
axiom SPaxWrite?: ∀ v. write(v) ⇀ leader ∧ ∃ꟴ ((latest x = v. ◇accept(x)) ∨ propose(v) ∧ ¬T(once(∃ x. ◇accept(x))))
axiom SPaxAccept?: ∀ v. accept(v) ⇀ ∃ꟴ◇write(v)
axiom SPaxDecide?: ∀ v. decide(v) ⇀ ∃ꟴ□accept(v)
axiom SPaxWrite!: ultimately(leader → (∃ v. write(v)))
axiom SPaxAccept!: ultimately((∃ v. ∃ꟴ◇write(v)) → (∃ v. accept(v)))
axiom SPaxDecide!: ultimately((∃ v. ∃ꟴ□accept(v)) → (∃ v. decide(v)))
axiom SLdrExist: TF(leader) ∧ T(∃ꟴ◇leader)
axiom SLdrCorrect: infinitely(∃ꟴ◇(leader ∧ (∀ v. TF(propose(v))) ∧ (∀ v. TF(write(v))) ∧ (∀ v. TF(decide(v)))))
axiom SPaxPCorrect: ∃ꟴ□(∀ v. TF(accept(v)))
axiom SPax2Twined: ∀ v. ∃ꟴ□accept(v) ⇀ ∀ꟴ◇accept(v)

property Validity: ∀ v. decide(v) ⇀ past(∃ꟴ◇(leader ∧ propose(v)))
property Agreement: ∀ v. ∀ w. past(∃ꟴ◇decide(v)) ∧ ∃ꟴ◇decide(w) ⇀ v = w
property Termination: infinitely(∀ꟴ□(∃ v. decide(v)))
```
