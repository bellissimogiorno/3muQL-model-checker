# A semitopology is not an upward-closed quorum system

Run `python -m muql check examples/semitopology.md`. The nonempty opens
are exactly `{a}` and `{a,b,c}`. The generator `{a}` and the whole point
set are already closed under unions; `{a,b}` and `{a,c}` are not added.
Every nonempty open contains `a`, so every finite collection of these
opens has a nonempty intersection.

Here `◇` and `□` range over points in the current quorum; `∃ꟴ` and `∀ꟴ`
range over nonempty quorums. The combined symbols compose these operations:
`∃ꟴ□(live)` means some quorum is entirely live. See the
[notation guide](../docs/notation.md) for all four combinations and ASCII spellings.

The ASCII aliases `somewhere` and `everywhere` mean `◇` and `□`, respectively:
they keep the current quorum. Use `someQuorumSomePoint` for `∃ꟴ◇` and
`everyQuorumEveryPoint` for `∀ꟴ□` when the formula must also range over quorums.

```muql
theory "Current quorums and a non-upward-closed semitopology"
points a b c
values unit
stages 1
quorums {a}
predicate live/0
```

These properties expose the exact definitions of the compound modalities.
The selected open stays visible while evaluating the nested body. The
current point may be outside that open.

```muql
property SomewhereDefinition: ∃ꟴ◇(live) ≡ ∃ꟴ(◇(live))
property EverywhereDefinition: ∀ꟴ□(live) ≡ ∀ꟴ(□(live))
property QuorumDefinition: ∃ꟴ□(live) ≡ ∃ꟴ(□(live))
property ContraDefinition: ∀ꟴ◇(live) ≡ ∀ꟴ(◇(live))
property LocalJoinBelowGlobalJoin: ◇(live) ≤ ∃ꟴ◇(live)
property GlobalMeetBelowLocalMeet: ∀ꟴ□(live) ≤ □(live)
property PairwiseIntersection: twined(2)
property TripleIntersection: twined(3)
```

A current-quorum box is not the same as a global box. For example, if `a`
is true and `b` is false, `□(live)` at open `{a}` is true, while
`∀ꟴ□(live)` is false. The checker finds a witness to the following
deliberately false proposed identity.

```muql
property CurrentBoxIsGlobal: □(live) ≡ ∀ꟴ□(live)
```

For this particular semitopology, a quorum of `live` implies that every
quorum contains some `live` point: the shared point `a` is the reason.
The crisp order property below preserves the entire truth-value comparison.

```muql
property SharedPointAgreement: ∃ꟴ□(live) ≤ ∀ꟴ◇(live)
```

`CurrentBoxIsGlobal` is the only expected failure. Try replacing the frame
with `quorums {a} {b}`: `PairwiseIntersection`, `TripleIntersection`, and
`SharedPointAgreement` then fail. That experiment changes the model frame;
an axiom cannot make an objectively false frame fact true.
