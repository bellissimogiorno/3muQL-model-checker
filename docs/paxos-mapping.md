# Reading the Paxos examples against the paper

The supplied paper is *A declarative approach to specifying Paxos using
three-valued modal fixpoint logic*, Murdoch J. Gabbay and Luca Zanolini. Its
printed page numbers are used below. The package contains all six protocol
theories explicitly axiomatized in that paper. Mathematical formulas have been
transcribed; the surrounding explanation and finite scopes are tutorial material.

| Source theory | Location | Literate input |
|---|---|---|
| Simple, reliable delivery and no crashes | §6.1, p.46 | `examples/simple_reliable.md` |
| Simple, reliable delivery and crashes | §6.1, p.47 | `examples/simple_crashes.md` |
| Simple, eventual delivery and no crashes | §6.1, p.47 | `examples/simple_eventual.md` |
| Simple, eventual delivery and crashes | §6.1, pp.47–48 | `examples/simple_eventual_crashes.md` |
| Declarative Paxos, TyPax | Definition 6.3.1, Figure 11, pp.49–50 | `examples/paxos.md` |
| Simpler Declarative Paxos, TySPax | Definition 8.2.1, Figure 12, pp.67–68 | `examples/paxos_simpler.md` |

## Symbols and exact scope

The executable theories use Unicode symbols, with named temporal operators
where those are easier to type and distinguish. The [notation guide](notation.md)
lists equivalent ASCII spellings: strong implication `⇀` is written `-\`.
For modalities, `somewhere` / `everywhere` mean current-quorum `◇` / `□`;
the compound `∃ꟴ◇` / `∀ꟴ□` use `someQuorumSomePoint` /
`everyQuorumEveryPoint`. This distinction matters for nested formulas.

| Paper notation | Executable input | Meaning |
|---|---|---|
| t, b, f | `t`, `b`, `f` | True, crashed, false; t and b are valid |
| negation, conjunction, disjunction | `¬P`, `P ∧ Q`, `P ∨ Q` | Kleene truth-order operations |
| weak implication, strong implication | `P → Q`, `P ⇀ Q` | True P requires valid Q / true Q |
| literal equivalence | `P ≡ Q` | Equality of truth values, including b |
| T, F, B, TF, TB, FB | `T(P)`, `F(P)`, etc. | Two-valued tests of P's truth value |
| diamond, box | `◇(P)`, `□(P)` | Some / every point in the current quorum |
| existential/universal quorum modality | `∃ꟴ(P)`, `∀ꟴ(P)` | Some / every nonempty open set, retaining current point |
| existential quorum then diamond | `∃ꟴ◇(P)` | P at some point in some quorum |
| universal quorum then box | `∀ꟴ□(P)` | P at every point in every quorum |
| existential quorum then box | `∃ꟴ□(P)` | A quorum whose members all satisfy P |
| universal quorum then diamond | `∀ꟴ◇(P)` | Every quorum has a member satisfying P |
| strict past R | `once(P)` | P at a strictly earlier stage |
| inclusive past R | `past(P)` | P now or at an earlier stage |
| sometime, forever | `sometime(P)`, `forever(P)` | Strict future operators |
| infinitely, ultimately | `infinitely(P)`, `ultimately(P)` | Repeated occurrence / eventual global permanence |
| affine and unique existence | `∃⁰¹v. P(v)`, `∃¹v. P(v)` | Paper's three-valued at-most-one / exactly-one formulas |
| most recently true value | `latest v = w. P(v)` | Was w true at the latest earlier stage with any true value? |
| mu | `μX. P` | Meet of all pre-fixed valuations; a least fixed point when monotone |

The source typesets its two past operators similarly; their bounds in Figure 6
are the reliable distinction. `once` uses `n' < n`; `past` uses `n' ≤ n`.
The latest-value operator always searches strictly earlier stages and ignores
crashed values when selecting the latest true stage.

Quorum modalities keep the distinction between the current point and current
quorum. A context may contain a point outside its quorum (Definition 3.2.4).
The package checks axioms at every point/quorum combination. This matters for
nested modalities, even though atomic predicates do not depend on the quorum.

## TyPax axiom labels

Question marks in the paper identify backward rules; exclamation marks identify
forward rules. The parser accepts these marks and hyphens directly
in axiom and property labels, for example `axiom PaxWrite?: ...` and
`axiom PaxDecide-not-L!: ...`. Quote such labels in shell arguments, as in
`--drop 'PaxWrite?'`.

The bundled theories use these direction marks directly. The negated-leader
rules use the hyphenated stem `PaxDecide-not-L`. The following table describes
the executable labels, which can be used in `--drop` and `--replace`.

| Figure 11 label | File label |
|---|---|
| PaxPropose? | `PaxPropose?` |
| PaxSend? | `PaxSend?` |
| PaxWrite? | `PaxWrite?` |
| PaxAccept? | `PaxAccept?` |
| PaxDecideL? | `PaxDecideL?` |
| PaxDecide-not-L? | `PaxDecide-not-L?` |
| PaxPropose! | `PaxPropose!` |
| PaxSend! | `PaxSend!` |
| PaxWrite! | `PaxWrite!` |
| PaxAccept! | `PaxAccept!` |
| PaxDecideL! | `PaxDecideL!` |
| PaxDecide-not-L! | `PaxDecide-not-L!` |
| LdrExist, LdrUniq, LdrCorrect | Unchanged |
| PaxPCorrect, PaxPropose01, PaxWrite01 | Unchanged |
| Pax2Twined, PaxNontriv | Unchanged |

There are 20 named axioms. `PaxPCorrect` is one conjunction of five independent
correct-quorum requirements, not one shared correct quorum. In the Simple
examples, the paper's Uncrashed schema is instead expanded into three named
instances so individual assumptions can be removed.

Figure 12 uses the same `?`/`!` convention for its four backward and
three forward axioms. The remaining five labels are unchanged. TySPax has 12
axioms total.

## Four details that are easy to change accidentally

1. **Latest quorum history.** Figure 11's `PaxWrite?` and Figure 12's `SPaxWrite?`
   use `latest x = v. ◇(accept(x))`. The selected quorum stays fixed while
   time is searched. `◇(latest x = v. accept(x))` instead searches each
   participant's history separately and may accept a stale value (§6.6.1).
2. **Existential progress.** The forward rules say that some value progresses;
   they do not universally preserve the triggering value. Replacing them with
   per-value implications makes a stronger theory (§6.4.4).
3. **Crash-sensitive uniqueness.** `∃⁰¹` may evaluate to b; two true witnesses
   make it false. Counting valid witnesses would wrongly count crashed values as
   successful choices (Definition 4.6.2, Lemma 4.6.5).
4. **Nonpositive μ.** `LdrUniq` is `◇(μX. ¬◇(leader ∧ X))`.
   With a two-valued leader predicate it evaluates to t/b/f for zero/one/multiple
   leaders in the current quorum. It is not an ordinary monotone fixed-point
   iteration (§6.6.3, Corollary 6.6.6).

`Pax2Twined` and `SPax2Twined` are properties specifically of `accept(v)`.
They are weaker than demanding that every pair of quorums intersect. The default
majority frames do intersect, so removing these axioms on those frames is not an
effective weakening. Use a disjoint-quorum frame to see what they prevent.

## Correctness formulas and what they claim

| Property | Paper | Content |
|---|---|---|
| `Validity` | Theorem 7.2.3; 8.2.2(1) | A true decision has a true leader proposal now or earlier |
| `Agreement` | Theorem 7.3.6; 8.2.2(2) | Conjunctive-premise encoding of agreement between true decisions |
| `Termination` | Theorem 7.4.7; 8.2.2(3) | Infinitely often, every participant has a valid decision value |
| `DecidingQuorum` | Remark 7.4.8, TyPax only | Infinitely often, a quorum has true decisions |

Both Paxos examples use this `Agreement` formula:

```text
∀v. ∀w.
  (past(∃ꟴ◇(decide(v))) ∧ ∃ꟴ◇(decide(w))) ⇀ v = w
```

It states that two true decisions agree, including a decision made earlier.
The three Simpler Paxos properties are `Validity`, `Agreement`, and
`Termination`. [The agreement proof](spax-agreement.md) establishes its safety
property for natural-number time independently of the finite checker.
All protocol axioms remain unchanged.

The Simple properties in the examples are tutorial consequences, not additional
named paper theorems. There is no unconditional Simple proposal-liveness axiom.

Integrity is discussed in Remark 7.1.2 as the interpretation of agreement plus
repeated decisions. The paper does not model machine stopping or a literal
at-most-once execution counter, and the package does not invent that assertion.

## Finite frames and the paper's natural-time semantics

The mathematical paper uses all natural-number stages starting at zero. This
package searches finite scopes. The example `stages` and `time` declarations are
checker configuration; they are not axioms from the paper.

Temporal examples choose `time stutter`: the last stage has a future self-loop,
while past operators inspect the displayed finite prefix. This is a finite
bidirectional temporal frame. It is **not** a faithful lasso encoding of an
infinite execution with natural-number past: later visits to a loop state would
have additional history. A finite-frame success is not an unbounded theorem,
and a finite-frame temporal failure is not automatically a counterexample to a
paper theorem. Inspect its boundary behavior first.

With `time finite`, tomorrow at the final stage is false and the future is
truncated. In particular, a strict `ultimately` axiom can become impossible at
the endpoint. Such inconsistency is a boundary artifact, not a defect in the
source theory. The checker must report inconsistent assumptions separately from
properties that survive a search over a nonempty model class.

A genuine counterexample to an unbounded claim needs a separately justified
infinite execution or a proof that its finite prefix cannot be repaired by any
extension. This package is an exploratory finite model finder; its reports
must be read with that scope.

## Experiments suggested by the paper

Section 8.1.1 notes that `PaxSend?` and `PaxPropose01` were unused in its
correctness proofs. Deleting both is therefore a useful positive experiment.
Section 7.3.2 discusses replacing unique leadership with extensional agreement
of leaders' writes:

```text
∀v. leader ⇀ (∃ꟴ◇(leader ∧ write(v)) ⇀ write(v))
```

Combined with `PaxWrite?` and `PaxWrite01`, this suffices for the proof's use
of leader uniqueness. The final TySPax theory takes the abstraction further and
uses `∃⁰¹v. ∃ꟴ◇(write(v))`.

Negative experiments include dropping a backward justification (an invented
value may be accepted), a write-uniqueness rule (two simultaneous decisions), an
intersection requirement on a disjoint frame (two quorum histories diverge), or
a progress condition (a permanently stalled computation). These are failures of
explicitly weakened theories. They should not be described as bugs in either
paper.
