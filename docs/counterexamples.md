# Counterexamples and what they mean

Every solver-produced countermodel is re-evaluated with a separate concrete
interpreter before export. The Bracha weakening below also has an elementary
argument independent of the SAT solver and of the finite temporal boundary.
Other demonstration scenarios explore deliberate changes to the protocol axioms.

Formulas below use executable Unicode notation: `→` is weak implication,
and `⇀` is strong implication (ASCII `->` and `-\`). See the
[notation guide](notation.md) for the complete symbol table.

## Bracha's proposed existential delivery weakening loses the payload

**Source:** [companion paper, arXiv:2512.21137v3](https://arxiv.org/pdf/2512.21137v3),
Section 4.3, discussion following Figure 10. This is a counterexample to the
suggested weakening, not to the original Figure 10 theory or its main theorems.

The original delivery rule is

```text
∀v. ∃ꟴ□(ready(v)) → dlvr(v)
```

The proposed weaker rule is

```text
(∃v. ∃ꟴ□(ready(v))) → (∃v. dlvr(v))
```

Take one participant and the sole nonempty quorum containing that participant.
There are two payloads, `red` and `blue`.

| Predicate | red | blue |
|---|---|---|
| `bcst` | t | f |
| `echo` | t | f |
| `ready` | t | f |
| `dlvr` | f | b |

All other Figure 10 axioms hold, including its correctness and uniform-fault
conditions for `echo` and `ready`. The frame is 3-twined. The existential
conclusion has value `b`, so the replacement rule is valid: `t → b = b`.
But `dlvr(red)` is `f`. The original delivery rule and the stated validity
property both fail for red.

The missing link is payload preservation. The backwards delivery rule does not
exclude `dlvr(blue)=b`, since its antecedent is not true. No Figure 10 axiom
requires `dlvr` to be uniformly correct or uniformly broken across values.
The original forward rule directly preserves the payload and excludes this
model. Replacing *both* proposed rules still admits the same model.

Run:

```sh
python -m muql check examples/bracha_weakened.md --countermodels out/bracha
```

A counterexample command deliberately exits with status 1. See
[companion-mapping.md](companion-mapping.md) for the axiom-by-axiom mapping and
additional checks of the discussion's implication claims.

## Deliberate experiments in the demonstration

The root `demo.py` also checks ordinary ways of breaking a theory:

- Removing Voting's correct-quorum axiom allows incompatible observations.
- Weakening Voting's strong forward rules preserves agreement but loses its
  strict delivery guarantee.
- Removing Bracha's echo uniqueness permits inconsistent deliveries.
- Weakening Crusader's strong echo provenance permits an output with no true
  matching input; removing its second-echo uniqueness permits conflicting outputs.
- Removing Simpler Paxos's write uniqueness permits two genuinely true decisions;
  removing acceptance provenance permits a decision without a proposal.
- Requiring unique Crusader output fails even in the original theory: `half`
  may coexist with a binary output. This is an intentional feature described in
  the companion paper, not a theorem refutation.

The exact scenarios and expected outcomes are executable in `demo.py`.
