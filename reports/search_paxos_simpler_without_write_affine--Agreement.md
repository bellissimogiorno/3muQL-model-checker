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

axiom SPaxPropose_back: ∀ v. propose(v) ⇀ leader
axiom SPaxWrite_back: ∀ v. write(v) ⇀ leader ∧ ∃Q ((latest x = v. ◇accept(x)) ∨ propose(v) ∧ ¬T(once(∃ x. ◇accept(x))))
axiom SPaxAccept_back: ∀ v. accept(v) ⇀ ∃Q◇write(v)
axiom SPaxDecide_back: ∀ v. decide(v) ⇀ ∃Q□accept(v)
axiom SPaxWrite_forward: ultimately(leader → (∃ v. write(v)))
axiom SPaxAccept_forward: ultimately((∃ v. ∃Q◇write(v)) → (∃ v. accept(v)))
axiom SPaxDecide_forward: ultimately((∃ v. ∃Q□accept(v)) → (∃ v. decide(v)))
axiom SLdrExist: TF(leader) ∧ T(∃Q◇leader)
axiom SLdrCorrect: infinitely(∃Q◇(leader ∧ (∀ v. TF(propose(v))) ∧ (∀ v. TF(write(v))) ∧ (∀ v. TF(decide(v)))))
axiom SPaxPCorrect: ∃Q□(∀ v. TF(accept(v)))
axiom SPax2Twined: ∀ v. ∃Q□accept(v) ⇀ ∀Q◇accept(v)

property Validity: ∀ v. decide(v) ⇀ past(∃Q◇(leader ∧ propose(v)))
property Agreement: ∀ v. ∀ w. past(∃Q◇decide(v)) ∧ ∃Q◇decide(w) ⇀ v = w
property Termination: infinitely(∀Q□(∃ v. decide(v)))
```
