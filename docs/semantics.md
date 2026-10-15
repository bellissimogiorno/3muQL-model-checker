# What the checker establishes

3μQL Explorer is an **exact finite-scope model finder and validity checker**.
`check` uses a declared nonempty set of points, nonempty finite value domain,
finite temporal frame, and semitopology. `search` chooses those structures
within explicit bounds. In either case, the engine encodes three-valued
interpretations of the predicate cells as SAT, rather than sampling executions
or enumerating every atomic valuation one by one.

A `holds` result means that all interpretations satisfying the axioms make the
property valid at every context **in the displayed scope** for `check`, or
throughout the **complete bounded frame class** for `search`. It is not a theorem
for larger domains or the papers' unbounded natural-number time. A
`counterexample` supplies an actual falsifying interpretation for this scope.
For static formulas the finite structure is also an ordinary model of the
papers' semantics. Temporal countermodels need a separate natural-time argument
before they can refute an infinite-time statement.

## The bounded search class

Search ranges from one point and one stage through their inclusive bounds.
Declared values remain distinct and supply the minimum value-domain size;
fresh names extend that domain up to its bound. If none are declared, search
starts with a nonempty domain of generated values. Formulas cannot acquire
undeclared constants merely by mentioning a free name.

For each point count, the structural search visits all union-closed families
of nonempty subsets containing the whole point set, up to point isomorphism,
with at most `max_quorums` nonempty members. Empty opens are implicit. This
does not assume majority quorums, upward closure, or intersections. Point
renaming preserves the available formula language, so isomorphic frames need
only one representative. Every candidate then receives an ordinary exact
finite-scope SAT check.

Declared `points`, `stages`, and `quorums` are not restrictions on `search`.
The formulas and finite/stutter time convention are retained, and an axiom
such as `twined(3)` still filters the admissible models. Increasing the value
bound extends the declared domain; lowering it below that domain is an error.

The point/value/stage/quorum maxima define the mathematical class. Time,
frame-count, enumeration, compilation, and solver budgets limit the work.
An unfinished obligation yields `unknown`. A `holds` property requires
complete coverage and at least one axiom model; if every frame is inconsistent,
the bounded theory is reported as `inconsistent`, without proving its properties.
A replayed counterexample remains decisive even if other frames are unvisited.
With no selected properties, search stops at the first checked axiom model.
See [the search guide](search.md) for defaults, reporting, and witness exports.

## Truth and validity

The ordered truth values are `f < b < t`. Conjunction is minimum, disjunction is
maximum, and negation interchanges `t` and `f` while fixing `b`.
Both **`b` and `t` are valid**. An axiom requires validity, not truth. A property
fails exactly when its value is `f`; the engine must search for `F(property)`,
not merely `¬property`. For example, `b` and `¬b` are both valid.

| Input | `¬` | `T` | `F` | `B` | `TB` | `TF` | `FB` |
|---|---|---|---|---|---|---|---|
| `f` | `t` | `f` | `t` | `f` | `f` | `t` | `t` |
| `b` | `b` | `f` | `f` | `t` | `t` | `f` | `t` |
| `t` | `f` | `t` | `f` | `f` | `t` | `t` | `f` |

`P → Q` means `¬P ∨ Q`. `P ⇀ Q` means `¬P ∨ T(Q)`.
Their ASCII spellings are `->` and `-\`, respectively; the
[notation guide](notation.md) lists all equivalent spellings.
The latter has a true conclusion whenever its premise is true and the whole
implication is valid. It does **not** behave like classical implication when
nested: `t ⇀ (b ⇀ f)` is `f`, whereas `(t ∧ b) ⇀ f` is `b`.
This is why the Simpler Paxos agreement property joins its two premises with
conjunction before a single strong implication.

`P ≡ Q` is literal equality of the two truth values: it returns `t` or `f`.
`P ≤ Q` is a **crisp lattice-order assertion**. The paper also discusses a
three-valued internal order connective that is `b` at `(b,b)`. Our `≤` (ASCII `<=`)
returns `t` there; both have the same designated cases, but cannot be substituted
inside arbitrary surrounding formulas. To reproduce the paper's internal order,
write `(P ⇀ Q) ∧ (TB(P) → Q)`.

## Contexts and quorums

A context is `(stage, point, quorum)`. **The point need not be in the quorum.**
Atomic predicates depend on stage, point, and value arguments, not the quorum.
The frame adds the whole space and empty set to the supplied quorum generators,
then closes under unions. Empty opens are excluded from modal quantification.
No upward closure or intersection closure is imposed.

| Expression | Evaluation at `(n,p,O)` |
|---|---|
| `◇(P)` | Maximum over `q in O` of `P(n,q,O)` |
| `□(P)` | Minimum over `q in O` of `P(n,q,O)` |
| `∃ꟴ(P)` | Maximum over nonempty open `U` of `P(n,p,U)` |
| `∀ꟴ(P)` | Minimum over nonempty open `U` of `P(n,p,U)` |
| `∃ꟴ□(P)` | `∃ꟴ(□(P))` |
| `∀ꟴ◇(P)` | `∀ꟴ(◇(P))` |
| `∃ꟴ◇(P)` | `∃ꟴ(◇(P))` |
| `∀ꟴ□(P)` | `∀ꟴ(□(P))` |

The ASCII names `somewhere` and `everywhere` are aliases for `◇` and `□`,
so they retain the current quorum. The compounds `∃ꟴ◇` and `∀ꟴ□` are
`someQuorumSomePoint` and `everyQuorumEveryPoint`. `quorum` and
`someQuorumEveryPoint` both mean `∃ꟴ□`; `contra` and
`everyQuorumSomePoint` both mean `∀ꟴ◇`. Earlier releases assigned the
compound meanings to `somewhere` and `everywhere`; see the
[migration guide](notation.md#compatibility-and-migration) before reusing
old ASCII formulas.

The compound operators keep the changed quorum while evaluating their bodies.
Replacing `∃ꟴ◇` with a point-only loop is wrong for a quorum-dependent
body. The companion paper's formulas have no such dependence, so the operators
agree with its global modalities.

`twined(k)` is a crisp assertion that every choice of `k` nonempty open sets
has nonempty intersection. Its use is an explicit finite-frame assertion,
representing the corresponding frame condition, not a quantifier over unknown
semitopologies. Deleting a `twined` axiom does not change a fixed frame. To test
a quorum assumption, supply different generators too.

## Quantifiers

`∀` is minimum over the value domain; `∃` is maximum.

```text
∃⁰¹v. P(v)  ≡  ∀v. ∀w. (P(v) ∧ P(w)) → v = w
 ∃¹v. P(v)  ≡  (∃v. P(v)) ∧ (∃⁰¹v. P(v))
```

These are definitional identities, with each side scoped separately. Here `w`
is fresh. Affine existence excludes two **true** witnesses. It does not
exclude several `b` witnesses. An all-`b` unary predicate satisfies `∃¹`
with designated value `b`. `∃¹v. T(P(v))` expresses a true unique
witness, with every other witness untrue.

## Time: two explicit finite interpretations

The papers use stages `0,1,2,...` without a final stage. This package does not
claim to implement their general infinite-time model theory. It supplies two
useful, explicit finite frames.

**`time finite` (default):** stages are `0,...,H-1`. `yesterday` is `f` at zero;
`tomorrow` is `f` at the last stage. Strict future ranges over later displayed
stages. The empty maximum is `f` and the empty minimum is `t`. Hence a globally
asserted `ultimately(P)` is inconsistent: at the final stage there is no future.
The checker reports inconsistency rather than vacuous success.

**`time stutter`:** the final stage has a successor edge to itself. Future
operators include that state, even when evaluated at the final state. Past
operators continue to inspect the displayed prefix. This is a finite temporal
frame, **not an ultimately constant natural-number execution or a lasso model
checker**. In particular, `yesterday(tomorrow(P))` need not equal `P`, and a
past-dependent formula at a repeated final state need not describe the
corresponding natural-time history. It is useful for exploring the full printed
Paxos formulas while keeping their eventual-progress axioms satisfiable.

The output always includes the time mode. The examples say which conclusions
are finite-frame checks. The documented Bracha weakening counterexample is
static, so it does not rest on a temporal boundary artifact. The Simpler Paxos
agreement proof is a separate induction over natural-number time.

| Expression | Meaning |
|---|---|
| `once(P)` | Maximum strictly before now; `f` initially |
| `past(P)` | Maximum up to and including now |
| `historically(P)` | Minimum strictly before now; `t` initially |
| `sometime(P)` | Maximum over strictly future reachable states |
| `forever(P)` | Minimum over strictly future reachable states |
| `infinitely(P)` | `forever(sometime(P))` |
| `ultimately(P)` | `sometime(∀ꟴ□(forever(P)))` |
| `latest v = w. P(v)` | At the latest strictly earlier stage where some `P(v)` is **true**, test `T(P(w))`; otherwise `f` |

Neither `latest` nor its existence test treats `b` as a successful observation.

## General `μ`, including nonpositive bodies

The definition is the paper's meet of pre-fixed points:

```text
μX. P = meet { k : Context → {f,b,t} | P[X := k] ≤ k }
```

For a monotone body this is the least fixed point, obtained exactly by iteration
from all-`f`. A context product with `K` cells has lattice height `2K+1`, so
`2K` iterations suffice. A syntactic monotonicity certificate is conservative.
For arbitrary bodies, the engine enumerates all pre-fixed valuations of the
closed recurrence dependency set and takes their meet. It does not assume that
this meet is itself a fixed point: `μX. ¬X` is `b`, but other nonpositive
examples need not even be pre-fixed at their meet.

A proven closed form handles the paper's nonpositive leader test
`μX. ¬◇(A ∧ X)` when `A` has no free `X`. Exhaustive tests compare it
with the definition for all small three-valued leader assignments, including
points outside the current quorum. General nonmonotone enumeration is limited
to eight dependent contexts by default. Exceeding the limit yields `unknown`,
never a guessed answer. Larger limits are possible through the Python API.

`ν` is an extension: the join of post-fixed points, giving the greatest fixed
point for monotone bodies. It is not a separate primitive in the attached paper.
There is no executable syntax for the paper's arbitrary denotational constants
`κ : Context → 3`; these are a semantic device, not an effective input
language. Finite atomic valuations can be inspected through countermodel files
and the concrete evaluator.

## Checking and trust boundaries

1. The parser expands value-parameter macros and rejects unresolved names.
2. The compiler encodes each truth value using two Boolean threshold bits.
3. The selected SAT backend first checks axiom consistency: the built-in
   pure-Python CDCL solver, or optional PySAT MiniSat22.
4. For each property, it searches for a valuation with a false property at
   some context, while enforcing every axiom at every context.
5. Every SAT consistency witness and countermodel is replayed by a separate
   concrete three-valued evaluator. The saved countermodel records all atomic
   cells and a falsifying context, plus each axiom's observed truth values.

An inconsistent theory is reported as `inconsistent`, not `holds`. Timeouts,
decision limits, and unsupported-size exact recurrences are `unknown`. Tests
include independent exhaustive Boolean checks, exact truth tables, recurrence
enumeration, compiler/evaluator differential checks, and source-linked regressions.
The solver is tested software, not a formally verified prover; UNSAT results do
not include a separately checkable proof certificate. No correctness claim is
made for an imperative implementation of any protocol.

`check` defaults to the built-in solver. `search` defaults to `auto`, which
selects PySAT when available and otherwise uses the built-in solver. Optional
native SAT models are checked against their Boolean clauses as well as replayed
in the three-valued evaluator. Native limits use bounded propagation slices;
an interrupted or over-budget result is `unknown`, never an UNSAT conclusion.
See [validation](validation.md) for the backends actually tested in this release.

The public `check`, `search`, and `replay` APIs revalidate their `Theory`, including callers'
direct dataclass construction and edits to its dictionaries. Saved countermodel
times must be JSON integers, and argument/quorum fields must be arrays of names;
Python's equality between booleans, floats, and integers is not accepted as a
substitute for those field types. Descriptive saved flags and axiom summaries
are not evidence: replay recomputes the mathematical conditions.

The lower-level concrete evaluator snapshots its valuation immutably. Construct
a new evaluator for a changed model. `Frame(...)` accepts a basic explicit
relational family; `Frame.from_theory(...)`, used by public checking, constructs
the semitopological union closure. Closure is capped at 4,096 nonempty opens.
Exceeding that cap returns `unknown` from `check`, with the requested generators
rather than a falsely complete quorum list.

For `check`, `timeout` applies separately to frame construction, formula
compilation, and each SAT call; by itself it excludes concrete replay. The
optional Python `total_timeout` adds a shared deadline with checkpoints after
replay. `search` shares its `timeout` across frame enumeration and checking,
using the remaining budget for each candidate. Parsing and file output are
outside these checking budgets.

All deadlines are cooperative: an expensive Python operation, concrete replay,
or native solver slice can overrun before a checkpoint is reached. A result
returned after a candidate's total deadline is reported as unknown. There is
no hard process time or memory limit. The Python APIs accept zero seconds as
an immediate timeout; the CLI requires positive seconds. Nonmonotone replay
has its own configurable context limit. Front-end
expansion/nesting limits reject the input with a diagnostic, rather than return
a result for a theory that was not loaded. See [the audit](audit.md).

See [language.md](language.md) for syntax and [counterexamples.md](counterexamples.md)
for the findings.
