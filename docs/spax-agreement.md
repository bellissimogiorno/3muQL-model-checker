# Simpler Paxos: agreement

The [Simpler Paxos example](../examples/paxos_simpler.md) includes the following
`Agreement` property:

```text
TySPax ⊨ ∀v. ∀w.
  (past(∃ꟴ◇(decide(v))) ∧ ∃ꟴ◇(decide(w))) ⇀ v = w
```

If a participant truly decides `v` now or earlier, and a participant truly
decides `w` now, then `v = w`. The participants may be equal. “Truly” means
truth value `t`; a crashed computation with value `b` is valid but is not a
successful decision.

Here `past` includes the present stage, `∃ꟴ◇` means “some quorum, some point”,
and `⇀` is strong implication. For the pointwise decision predicate, `∃ꟴ◇`
is equivalent to “some participant”. The [notation guide](notation.md) lists
Unicode and ASCII spellings.

## Natural-time proof from Figure 12

Work in an arbitrary model of the source theory on natural-number time, with
the paper's fixed semitopology and arbitrary value domain. Only the following
five axioms are needed:

| Paper axiom | Package name | Use |
|---|---|---|
| `(SPaxWrite?)` | `SPaxWrite?` | A true write follows the latest true acceptance within its selected quorum, or a proposal when that quorum has no earlier true acceptance. |
| `(SPaxAccept?)` | `SPaxAccept?` | A true acceptance has a true write of the same value at that stage. |
| `(SPaxDecide?)` | `SPaxDecide?` | A true decision has a true accepting quorum at that stage. |
| `(SPaxWrite01)` | `SPaxWrite01` | At each stage at most one value is truly written anywhere. |
| `(SPax2Twined)` | `SPax2Twined` | A true accepting quorum for a value gives a true acceptance of that value in every nonempty open. |

**Agreement at one stage.** By `(SPaxWrite01)`, any two true writes at a
stage have the same value. By `(SPaxAccept?)`, the same holds of true
acceptances: each has a true write of its value at that stage.

**Persistence after a true decision.** Suppose a participant truly decides
`v` at stage `m`. By `(SPaxDecide?)`, `∃ꟴ□(accept(v))` is true at `m`.
Thus some nonempty open consists entirely of true `v`-acceptances. By
`(SPax2Twined)`, `∀ꟴ◇(accept(v))` is also true at `m`: every nonempty open
contains a participant truly accepting `v` at that stage.

We prove by induction on `n ≥ m` that every true write and every true
acceptance at `n` has value `v`.

* At `n = m`, there is a true acceptance of `v`, hence a true write of `v`
  by `(SPaxAccept?)`. Agreement at one stage gives both assertions.
* Suppose `n > m` and both assertions hold at every stage from `m` to `n−1`.
  Consider a true write of `w` at `n`. By `(SPaxWrite?)`, some nonempty open
  `O` makes its write-justification disjunction true. The branch asserting
  that there is no earlier true acceptance is false, since `O` contains a
  true acceptance of `v` at `m < n`. Therefore `w` must be a most recently
  truly accepted value in `O`.
  The latest stage `k < n` with a true acceptance in `O` exists: there are
  only finitely many preceding natural-number stages, and `m` is one such
  stage. In particular, `m ≤ k < n`. A participant in `O` truly accepts `w`
  at `k`, so the induction hypothesis gives `w = v`. This proves the write
  assertion at `n`. Applying `(SPaxAccept?)` proves the acceptance assertion
  at `n` as well.

Now suppose the two conjuncts in the Agreement antecedent are
true at stage `n`. The first supplies a true decision of `v` at some
`m ≤ n`. The second supplies a true decision of `w` at `n`, hence a true
acceptance of `w` at `n` by `(SPaxDecide?)`. Persistence gives `w = v`.
By the semantics of strong implication, the formula is valid.

This proves the statement for all natural-number stages, with no finiteness
assumption on participants or values. The seven remaining Figure 12 axioms
and the checker's endpoint convention are not needed. The proof uses the
Figure 6 semantics of the most recent strictly earlier **true** acceptance.
Broken acceptances do not reset that latest stage.

## Check the example

From the package root, run:

```sh
python -m muql check examples/paxos_simpler.md --property Agreement
```

`Agreement` holds in the example's declared finite scope. The checker searches
that finite frame; it does not prove validity over natural-number time. The
mathematical argument above establishes that broader statement directly from
the five axioms.

## Source references

References are to the Paxos paper identified in [SOURCES.md](../SOURCES.md):
Figure 12 on page 68 supplies the five axioms; Definition 2.3.1 and
Proposition 2.3.3 give strong implication and its inference principle; Figure 6
gives the inclusive-past and most-recent-true-acceptance semantics; Section 4.6
explains affine existence. Section 7.3 develops the corresponding agreement
reasoning for full Paxos.
