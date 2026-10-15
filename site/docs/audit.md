# MuQL Explorer: independent code audit

10 October 2026. Audited baseline: **0.1.0**. Corrected release: **0.1.1**.

> Code-audit evidence below concerns release 0.1.1; current release results
> are recorded in [validation](validation.md). Release 0.3.2 uses Unicode and
> ASCII notation; see the [notation reference](notation.md).
> The `=>` formulas retained below use historical input syntax. Release 0.2.1
> rejects that spelling; strong implication is now written `⇀` or `-\`.
> Release 0.3.0 also makes `somewhere` and `everywhere` current-quorum
> modalities. Earlier compound meanings require `someQuorumSomePoint` and
> `everyQuorumEveryPoint`; see the notation reference for migration.

The audit found real implementation defects, including a soundness defect in
the low-level SAT solver. All confirmed defects listed below have been fixed
and covered by regression tests. No transcription error was found in the 13
examples. The Bracha weakening counterexample survived independent source
and mathematical checks.

This is a complete review of the package's code and documented contracts, with
finite exhaustive and adversarial validation. It is **not a formal proof** of
the implementation. In particular, an UNSAT answer still has no independently
checkable proof certificate. The package remains a finite-scope research tool.

## Baseline and method

The original source archive was preserved and extracted separately. Its SHA-256
is `79db5843419bb3d32ff5969ba3bce01b612f499a958abb2d0436a6c1d57847cc`.
Its original 106 tests were rerun successfully before relying on their results.
Their success did not reveal the defects below.

Independent review streams examined the parser/loader, concrete semantics and
compiler, SAT engine, source translations, CLI/release, and checker/replay.
Every production module, the root demo, packaging/CI configuration, tests,
example inputs, and documentation contracts were reviewed. Expected values for
new tests were derived independently instead of copied from the implementation.

The attached Paxos PDF was checked against its text extraction and visually
inspected at the critical definitions, axiom figures, and Agreement theorem.
Companion formulas were checked against the official pinned
[v3 PDF](https://arxiv.org/pdf/2512.21137v3) and
[HTML/LaTeX](https://arxiv.org/html/2512.21137v3). Direct local download of that
PDF was unavailable during this audit, and companion screenshots could not be
visually inspected; PDF text and explicit LaTeX were cross-checked instead.
Exact source identity and hashes are recorded in [SOURCES.md](../SOURCES.md).

## Confirmed findings

Severity describes the affected interface. A high-severity low-level defect
does not establish that an existing reported paper result was wrong.

| ID | Severity | Defect in 0.1.0 | Correction in 0.1.1 |
|---|---|---|---|
| A1 | High | SAT activity underflow could remove occurring variables from branching and return an invalid SAT model. | Track variable occurrence independently of floating-point activity. |
| A2 | High | Exported, directly constructed or mutated `Theory` objects bypassed the loader's validation. | Revalidate frame, signature, labels, AST shape, sorts and binding at `check` and `replay` entry. |
| A3 | Medium | Expansion could erase invalid unused macro arguments before validation. | Validate every call and argument before expansion, then validate expanded formulas. |
| A4 | Medium | Mutable evaluator valuations could disagree with cached denotations. | Each evaluator owns an immutable snapshot; changed models require a fresh evaluator. |
| A5 | Medium | Frame closure and intersection enumeration lacked timeout checks; closure exhaustion was classified as invalid input. | Cooperative checkpoints and distinct frame-limit exceptions; incomplete checking reports `unknown`. |
| A6 | Medium | Huge unused predicate arities could hang in preflight counting outside the timeout, or fail in argument-tuple allocation. | Reject oversized arity with `unknown` before counting/decoding; avoid repeated multiplication by one. |
| A7 | Medium | Front-end macro expansion was unbounded; deeply nested syntax or malformed ASTs could leak incidental Python exceptions. | A 100,000-node expansion work budget, pre-expansion AST validation, and localized nesting/integer diagnostics. |
| A8 | Medium | Valid saved models could require a larger recurrence budget than CLI replay allowed; exhaustion was called invalid. | `replay --max-mu-contexts N`; insufficient replay resources exit `3`, not `2`. |
| A9 | Medium | Fresh macro binders could collide with unused declared names or macro parameters, rejecting valid input. | Include all declarations and formal parameters in the fresh-name exclusion set. |
| A10 | Low | Replay accepted malformed field types through Python coercions, such as Boolean/float stages and string argument lists. | Strict serialized field types and duplicate failure-quorum checks. |
| A11 | Low | Quorum splitting mishandled quoted braces and silently discarded stray separator commas. | Quote-aware delimiter parsing and checked separators. |
| A12 | Low | Zero timeout had different meanings in compilation and solving; internal frames accepted invalid time/configuration fields. | Zero consistently means immediate timeout; basic frame and numeric budget validation. |

The concrete evaluator also cached the frame-constant `twined` result to avoid
repeating combinatorial intersection work at every replay context. This is a
performance correction with no change to the mathematical result.

### A1: a search heuristic was allowed to affect satisfiability

The old activity-rescaling code rebuilt the branching heap only for variables
whose activity was nonzero. Repeated multiplication by `1e-100` can underflow
the activity of an unbumped variable to zero. Its clauses still matter.

The deterministic regression initializes the valid private solver state with
clauses `[[1, 2], [3, 4]]` and forces four rescaling transitions by bumping
variable 3. The actual results were:

```text
0.1.0: sat {1: False, 2: False, 3: False, 4: True}
0.1.1: sat {1: False, 2: True,  3: False, 4: True}
```

The old assignment falsifies `[1, 2]`. This reproducer deliberately accelerates
the numerical state transitions; it is not claimed to be a naturally occurring
short CNF that triggers thousands of conflicts. The invariant violation is
demonstrated directly. Occurring variables now remain eligible regardless of
heuristic activity; genuinely unused variables need not consume decisions.

The main checker independently re-evaluates decoded SAT models. That protects
against returning this kind of invalid model, normally by detecting an internal
validation error. This audit did **not** demonstrate a false `holds` result or
an incorrect shipped paper report caused by A1.

Files: `muql/sat.py`, `tests/test_audit_sat.py`.

### A2–A4 and A10: checking the actual input and model

`Theory` is a frozen dataclass, but its dictionaries are mutable. For example,
after loading a valid input, a caller could insert the undeclared formula
`Missing() => Missing()` into its properties. The old checker could report
`holds` for it without rejecting the undeclared predicate. Negative arities,
duplicate value domains, and unsupported time strings also bypassed the
loader. The public engine now validates the supplied theory itself.

The following complete Markdown theory used to load as `property Goal: t`:

````markdown
```muql
points alice
values red blue
stages 1
quorums {alice}
let Ignore(v): t
property Goal: Ignore(misspelled)
```
````

The unused argument concealed an undeclared value. It now receives a source
error. Public replacement ASTs are also checked before expansion can discard
ill-sorted children or unexpected fields.

Separately, a direct evaluator caller could evaluate an atom, mutate
`evaluator.valuation`, and still receive the cached old answer. That mapping is
now read-only. Normal checker runs did not perform this mutation.

Saved-model replay still checks the supplied theory, all atomic cells, every
axiom at every context, and the particular claimed property failure. It now
also rejects malformed JSON representations such as `time: false`,
`time: 0.0`, `args: "x"`, or a string instead of a quorum array. The descriptive
`replayed` flag and stored axiom summaries remain deliberately untrusted.

Files: `muql/theory.py`, `muql/checker.py`, `muql/evaluate.py`; corresponding
`test_audit_parser.py`, `test_audit_checker.py`, `test_audit_semantics.py`.

### A5–A8 and A12: unfinished work must stay unfinished

A union closure above 4,096 nonempty opens used to raise the same kind of
exception as malformed syntax. It now reports `unknown`, recording the
requested generators without presenting them as a completed semitopology.
Closure and compiled intersection checks observe their deadlines.

With one declared value, an unused `predicate P/100000000000000000000` caused
preflight counting to loop over its arity. The original release was stopped
after one second despite `check(..., timeout=.001)`. The corrected checker
returns `unknown` immediately from its arity budget. Zero checking timeout
also stops before constructing a frame.

A chain of doubling macro definitions can expand exponentially before solver
limits apply. Expansion, substitution and renaming now have a per-expansion
work limit. Exceeding a front-end limit rejects the input with exit `2`; it
does not report any property result. This differs from a loaded theory whose
search could not finish, which receives `unknown` and exit `3`.

Replay also needs a resource limit. For example, with nine points in one
quorum, `T(mu X. !box(X))` is false: the meet of its pre-fixed tuples is the
all-`b` tuple. Its complete countermodel has no atoms. Default replay's limit
of eight contexts cannot complete this case; limit nine can. The CLI now
exposes the same recurrence-budget option and calls insufficient resources
incomplete, rather than invalidating a potentially valid witness.

Timeouts remain cooperative, not hard operating-system deadlines. Parsing,
concrete replay and output are not included in a total wall-clock budget.
No process memory bound is claimed. These limits are now explicit in the
README, language reference and semantics documentation.

### A9 and A11: valid quoted names and hygienic expansion

An unused declared value `x_local1` could collide with the generated binder in
`let Some: exists x. P(x)`. Valid input then failed with a shadowing error.
Fresh names now exclude every declared value, predicate, macro and formal
parameter, as well as names appearing in the formula.

Point names such as `"a{b}"` were legal in a `points` declaration but failed
inside `quorums` because braces within quotes were mistaken for delimiters.
Conversely, malformed `quorums ,,{alice},,,,` was accepted. Both paths now obey
the documented naming and separator rules.

## Coverage and independent evidence

Release 0.1.1 had **163 passing tests**, including 57 new audit tests. Counts
below describe that code-audit coverage; they do not quantify the probability
of a remaining bug. See [current validation](validation.md) for the current
suite and demonstration results.

| Area | Fresh evidence |
|---|---|
| Boolean circuit encoding | 1,298 gate constructions × 8 assignments = 10,384 cases; auxiliary assignments enumerated directly without using the SAT solver; 259 clause simplifications checked by complete truth tables. |
| SAT search | All 3,304 three-variable CNFs with at most three distinct non-tautological clauses; 1,280 seeded CNFs through 16 variables against complete bitset truth tables; pigeonhole contradiction exercising 890 conflicts and restarts; every SAT witness checked against original clauses. |
| Fixed points and compiler | All 27 functions `THREE -> THREE` under both binders; 250 generated scalar bodies, both binders and all three atomic values; full-frame enumeration of nested modal/temporal and value-quantified recurrences. Both expected bits are checked and contradictory output bits required UNSAT. |
| Quorum geometry | All 127 nonempty families of nonempty subsets of three points, with repeated-choice intersection definitions for `n=1,2,3,4`. |
| Whole checker | 100 independently generated axiom/property pairs, each checked against all 81 valuations in its small single-quorum frame; finite/stutter modes, consistency, counterexamples and replay. |
| Parser | 19 regressions, 3,000 retained seeded token fuzz cases and successful-tree round trips. Separate audit runs tried 50,000 token sequences and 30,000 malformed declaration tails without unexpected exceptions. |
| Paper translations | 47,760 comparisons against independently transcribed source denotations, including invalid models; all nine theories and the weakening input; exhaustive small tutorial valuations. |
| CLI/release | Actual subprocess exit/status/JSON checks, configurable replay limits, wheel/sdist builds, clean offline installation and installed entry-point checks. |

Every saved demonstration countermodel is replayed against its exact scenario
modifications. See [validation.md](validation.md) for counts, commands, and
release verification.

## Paper translations

All 13 example files were reviewed. The nine theories are the four Simple
variants, full Paxos, Simpler Paxos, Voting, Bracha and Crusader. The remaining
inputs are three tutorials and the explicitly weakened Bracha experiment.
Exact mappings are in
[paxos-mapping.md](paxos-mapping.md) and
[companion-mapping.md](companion-mapping.md).

Source-sensitive checks included weak versus strong arrows, right association,
global versus current-quorum modalities, separate versus common correctness
quorums, three-valued uniqueness, nonmonotone leader uniqueness, strict versus
inclusive time, and the placement of latest-true acceptance inside write rules.

**Bracha weakening:** the independently evaluated `(t,f)` broadcast/echo/ready
and `(f,b)` delivery rows still satisfy the weakened axioms and falsify delivery
of red. Repeating the rows on four participants with three-member quorums also
works. The finding therefore does not depend on a singleton network. It
refutes the suggested existential weakening, not the original theory.

The Bracha derivation is in [counterexamples.md](counterexamples.md). A
separate [agreement proof](spax-agreement.md) establishes Simpler Paxos
agreement on natural-number time.

## Remaining limits and audit conclusion

All confirmed defects found by this audit are addressed. No unresolved
translation or core truth-value/fixed-point implementation discrepancy was
found. The limits relevant to interpreting the release remain:

- Finite scopes do not prove arbitrary-size or infinite-time correctness.
  `time stutter` retains finite past history and is not a lasso semantics for
  natural-number executions with past operators.
- The SAT solver is tested, not formally verified. UNSAT answers have no proof
  certificate; replay validates SAT evidence only. The separate implementations
  and independent test oracles can still share a human transcription error.
- General nonmonotone recurrences and quorum closure are explicitly bounded and
  can be exponential. A conservative dependency set can give `unknown` earlier
  than a more sophisticated engine would.
- Resource limits are cooperative and do not cover every possible allocation
  failure, front-end workload, or replay time. Large valid inputs can be rejected
  by the front-end work/nesting limits. This is not a hardened public service
  for arbitrary untrusted workloads.
- ASCII `<=` is deliberately crisp; it differs from the paper's internal
  three-valued order at `(b,b)`. That distinction, the supported extensions and
  the absence of arbitrary denotational constants are documented.
- Local release validation used CPython 3.12.14. Other versions in the CI matrix
  were not executed locally and are not claimed as verified by this audit.

The appropriate confidence claim is a substantially strengthened, audited
finite-scope implementation with reproducible evidence, rather than a certified
prover or a guarantee that no defects remain.
