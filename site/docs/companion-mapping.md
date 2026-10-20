# Companion paper: transcription and scope

These examples target **arXiv:2512.21137v3, 13 May 2026**:
[Declarative distributed algorithms as axiomatic theories in three-valued modal
logic over semitopologies](https://arxiv.org/pdf/2512.21137v3), Murdoch J. Gabbay.
References below are to that version. The executable files reproduce the
mathematical axioms; the surrounding explanation is original.

## Reading the notation

The executable theories use Unicode. Every operator also has a plain ASCII
spelling; see the [notation guide](notation.md). In particular, weak implication
is `→` / `->`, and strong implication is `⇀` / `-\`.

| Paper notation | Executable Unicode | Meaning |
|---|---|---|
| `t`, `b`, `f` | `t`, `b`, `f` | True, middle, false |
| negation | `¬A` | Swap t/f, preserve b |
| conjunction / disjunction | `A ∧ B`, `A ∨ B` | Minimum / maximum in f < b < t |
| weak implication | `A → B` | `¬A ∨ B` |
| strong implication | `A ⇀ B` | `A → T(B)` |
| truth tests | `T(A)`, `F(A)`, `B(A)` | Boolean tests for the indicated value |
| correctness / validity tests | `TF(A)`, `TB(A)` | Boolean membership tests |
| global universal / existential modality | `∀ꟴ□(A)`, `∃ꟴ◇(A)` | Min / max over participants |
| quorum / contraquorum | `∃ꟴ□(A)`, `∀ꟴ◇(A)` | Max-min / min-max over nonempty opens |
| universal / existential quantification | `∀v. A`, `∃v. A` | Min / max over values |
| affine / unique existence | `∃⁰¹v. A`, `∃¹v. A` | Three-valued Figure 6 quantifiers |
| value equality | `v = w` | Boolean equality of payloads |
| `TF[P]` | `∀v. TF(P(v))` | Correctness across all payloads |
| `B[P]` | `∀v. B(P(v))` | Faultiness across all payloads |

The compound operators `∃ꟴ◇` and `∀ꟴ□` have the ASCII names
`someQuorumSomePoint` and `everyQuorumEveryPoint`. The shorter names
`somewhere` and `everywhere` mean current-quorum `◇` and `□`; they are not
substitutes for these global compounds.

A formula is **valid** when its truth value is `t` or `b`. A theory requires
every axiom to be valid at every evaluation context. Refuting a property means
finding a satisfying model in which that property evaluates to `f` at some context;
negating the property and requiring the negation to be valid is insufficient,
because both a formula and its negation can be `b`.

The companion theories are static. Their executable scopes have `stages 1`;
none of their formulas uses a temporal or fixed-point operator. They use only
the spatial/value fragment of the richer language used for the Paxos paper.

The quorum lists are generators of a union-closed family, with the whole
participant set included. The empty open set is not a quorum. These four spatial
modalities are unchanged by taking union closure. The code therefore need not
list every union explicitly.

`twined(3)` explicitly records the ambient requirement that every three
nonempty opens intersect, allowing repetitions. Checking a theory on one such
finite frame does **not** quantify over all three-way-intersecting frames.

## Axiom and property correspondence

Bundled backward and forward axioms use the paper's `?` and `!` direction
marks, including `BrReady!!`. Descriptive ASCII stems distinguish the negated
observation (`ObserveNot?`, `ObserveNot!`) and half-output
(`CaOutputHalf?`, `CaOutputHalf!`) rules; their correspondence to the paper's
negation and prime notation is explicit below. The weakened delivery axiom is
`BrDeliverExistential!`, distinguishing it from `BrDeliver!` in the full theory.

### Voting

[voting.md](../examples/voting.md) uses Figure 3 and Proposition 2.5.7.

| Paper | File declaration |
|---|---|
| Observe? | Observe? |
| Observe¬? | ObserveNot? |
| Observe! | Observe! |
| Observe¬! | ObserveNot! |
| Correct | Correct |
| 3twined semantic schema | Intersection |
| Agreement, Proposition 2.5.7 | Agreement |

The two additional unanimous-delivery checks are consequences of the forward
rules. The distinction between faulty votes and absent observations is from
Remark 2.5.4. The unreliable-delivery variation changes the two strong forward
implications to weak ones, as in Remark 2.5.9.

### Bracha Broadcast

[bracha.md](../examples/bracha.md) uses Figures 10–11, with the frame assumption
from Remark 4.2.1.

| Paper | File declaration |
|---|---|
| BrDeliver? / BrReady? / BrEcho? | BrDeliver? / BrReady? / BrEcho? |
| BrEcho01 / BrBroadcast1 | BrEchoAffine / BrBroadcastUnique |
| BrDeliver! / BrReady! / BrEcho! | BrDeliver! / BrReady! / BrEcho! |
| BrReady!! | BrReady!! |
| BrCorrect | BrCorrect |
| BrCorrect′, separately for ready and echo | BrReadyUniform / BrEchoUniform |
| BrCorrect′′ | BrBroadcastUniform |
| BrValidity, Proposition 4.2.10 | BrValidity |
| BrNoDup / BrConsistency, Proposition 4.2.12 | BrNoDup / BrConsistency |
| BrIntegrity, Proposition 4.2.13 | BrIntegrity |
| BrTotality, Proposition 4.2.14 | BrTotality |

Three details are easy to overlook:

1. The two correctness quorums in `BrCorrect` need not be identical.
2. `BrCorrect′` applies to each named predicate separately.
3. Figure 10 contains **no** correctness/uniformity axiom for `dlvr`.

The affine and unique quantifiers cannot be replaced by Boolean cardinality
constraints on non-false entries. For example, `∃¹v. P(v)` can be `b` when
every payload gives `P(v)=b`, and is therefore valid in that model.

### Crusader Agreement

[crusader.md](../examples/crusader.md) uses Figures 13–14, with the frame
assumption from Remark 5.3.1. `zero`, `half`, and `one` represent exactly the
three payloads 0, 1/2, and 1.

| Paper | File declaration |
|---|---|
| CaEcho1? / CaEcho2? | CaEcho1? / CaEcho2? |
| CaOutput? / CaOutput′? | CaOutput? / CaOutputHalf? |
| CaEcho1! / CaEcho2! | CaEcho1! / CaEcho2! |
| CaOutput! / CaOutput′! | CaOutput! / CaOutputHalf! |
| CaCorrect | CaCorrect |
| CaCorrect′, for each of the four predicates | Four Ca...Uniform axioms |
| CaInput / CaEcho201 | CaInput / CaEcho2Affine |
| CaAgree, Proposition 5.3.3 | CaAgree |
| CaValid1 / CaValid2, Proposition 5.3.6 | CaValid1 / CaValid2 |
| CaLive, Proposition 5.3.11 | CaLive |

Here `CaCorrect` requires a **single common quorum** correct across all four
predicates. `CaEcho1?` uses strong implication; the other backward rules use
weak implication. `CaValid1` tests `TB(∀ꟴ□(input(v)))`, so it includes
participants that are faulty at input while requiring all correct input
participants to share the payload.

`CaLive` states that every participant has a non-false output for some payload
in the completed model. It is the paper's static declarative liveness property,
not a bounded execution-time assertion.

## Findings and interpretation

### Section 4.3: the delivery weakening has a countermodel

[bracha_weakened.md](../examples/bracha_weakened.md) changes only
`BrDeliver!`, replacing

```text
∀v. ∃ꟴ□(ready(v)) → dlvr(v)
```

with the existential weakening discussed in Section 4.3:

```text
(∃v. ∃ꟴ□(ready(v))) → (∃v. dlvr(v))
```

For one participant with its singleton quorum, take:

| Predicate | red | blue |
|---|---|---|
| bcst | t | f |
| echo | t | f |
| ready | t | f |
| dlvr | f | b |

Every retained axiom is valid. The replacement is `t → b = b`; backward
delivery at blue is `b → f = b`. However, the original forward delivery rule
and `BrValidity` are both `f` for red. The original forward rule excludes this
model. The example therefore refutes the **discussion's weakening claim**, not
the original correctness theorem.

The missing `dlvr` uniformity assumption is decisive: the existential witness
can be a different payload with value `b`. Adding such an assumption would
exclude this particular witness, but it would change Figure 10.

Section 4.3 also describes the pointwise echo-forward rule as problematic when
the broadcast antecedent is `b`. The accompanying argument incorrectly treats
`b → f` as invalid. Figure 1 makes it valid, and Lemma 4.2.7(1) actually derives
that pointwise rule. This is a discrepancy in the discussion, not a new failure
of the original protocol axioms.

### Crusader output need not be unique

The additional conjecture `∃⁰¹v. output(v)` is false even in the full
Crusader theory. Example 5.3.4 already points out this behavior. A small witness
has four correct participants, quorum threshold three, two inputs zero and two
inputs one. Every first echo includes both binary values, every second echo can
be one, and every output can include both one and half. Weak agreement permits
that combination. A demo of this conjecture is illustrating an intentional
limitation of the specification.

### What successful checks establish

The original-paper examples are finite model searches over declared
participants, payloads, quorums, and stages. A successful check establishes
absence of a countermodel **in that scope**. It is not a replacement for the
paper's general proofs or its cited Lean formalization. A returned concrete
countermodel, once validated against the formulas, does refute the corresponding
universal implication because it is one model in the stated class.
