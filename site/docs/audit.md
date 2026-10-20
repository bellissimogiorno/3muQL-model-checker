# Fresh correctness and maintainability audit — 0.7.3

Audited on 19 October 2026 against the supplied 0.7.2 handover, using CPython
3.12.14 and Node 24.19.0 on Linux. The original recorded files were checked
before editing. This release preserves functionality and adds a small module
split, compiler optimizations and reproducible regression evidence.

## Conclusion and scope

No incorrect truth value, invalid returned countermodel, false bounded success,
or incomplete-search-to-success conversion was found in the exercised cases.
The existing suites and independent semantic scripts were rerun against both
the supplied engine and the revised engine. The audit also examined the code
and mathematical invariants listed below; historical logs alone were not
treated as evidence for the current source.

This is finite testing and source review, not a formal verification. The
original source PDFs are absent from the handover. The exact private Paxos draft
cannot be reconstructed from its recorded hash, and retrieval of the pinned
companion paper was unavailable. Accordingly, this audit checks the implementation
against the included semantic specification and executable theories; it does
not independently certify their transcription from the original papers.
The agreement argument was checked against the five included Simpler Paxos
axioms it uses. It remains a separate mathematical argument, not a checker result.

## Invariants examined

| Area | Review and executable checks |
| --- | --- |
| Literate input | Executable fences, operator precedence, quoted values, original error positions, binding/name checks, capture-avoiding macros and rejection of malformed public ASTs. |
| Three-valued logic | Ordered values `f < b < t`, designated `b`/`t`, weak and strong implication, crisp order/equality, and false-property obligations rather than merely designated negations. |
| Quorums | Union closure with the full space, exclusion of the empty open, no implicit upward/intersection closure, and contexts whose point is outside the quorum. |
| Quantification | Min/max quantifiers, three-valued affine/unique existence, and strictly earlier latest-true observations that ignore `b`. |
| Time | Finite endpoints and the final self-successor of stutter frames, including their distinct past history and limitations as models of natural time. |
| Recurrences | Conservative monotonicity certification, product-lattice iteration bounds, exact meets/joins for arbitrary bodies, dependency closure and the special leader formula. |
| SAT | Threshold-bit invariants, gate clauses, watched propagation, learning, backtracking, restarts, assignment completion and explicit unknown outcomes. |
| Checking/search | Consistency before validity, independent witness replay, bounded frame enumeration up to isomorphism, unresolved obligations and cooperative deadlines. |
| Interfaces | CLI outcomes/exports, validated browser requests, progress observation, stale-worker filtering, Stop/restart, saved drafts, escaped labels and model-view coverage. |
| Delivery | Source/site consistency, inclusion of the extracted witness module, isolated installation and loopback serving, deterministic archives, checksums and handbook links. |

The independent frame oracle checks actual isomorphism classes and union
closure, not just counts. Its complete small domains contain 1, 3, 14 and 165
classes on one through four points, including every allowed quorum bound.
The Boolean oracle compares 2,512 CNFs with explicit assignments. Native PySAT
was unavailable; native-path doubles are not native execution evidence.

## Changes

`muql/witness.py` now owns `CounterModel`, complete atomic-cell counting and
decoding, concrete axiom checks and saved-countermodel replay. `checker.py`
keeps phase/deadline orchestration and report construction. All seven moved definitions and the remaining checker definitions were
verified to have identical Python syntax trees before and after extraction. Existing imports from `muql` and `muql.checker`
remain supported. JSON schemas, text tables, complete valuations, and replay
acceptance/rejection are unchanged. Python pickle is not a documented storage
format; use the stable JSON witness format.

The compiler now caches free recurrence names per immutable syntax tree,
within one `Compiler` instance. Repeated iterations no longer rescan a body for
each active variable. Nested binders still remove their own names, and a result
that depends on any active binding remains ineligible for truth-value caching.
Cache lookups also avoid hashing the same syntax-tree key twice on hits.
The concrete evaluator retains its separate implementation. No truth table,
SAT clause construction, frame ordering or solver heuristic was changed.

The new binding regressions reuse a compiler across changing outer fixed-point
and value bindings, exercise binder hiding, and compare nested recurrences
with full-context pre-/post-fixed-point enumeration. In the two-stage cases,
SAT must both produce the expected outputs and reject a disjunction asserting
that any output differs. This tests forced outputs, not one lucky assignment.

## Direct before/after comparison

`tools/audit_equivalence.py` executes the two source trees in separate processes.
Its **138 records match exactly**, after excluding package version and elapsed
report times. They include:

- All 30 demonstration scenarios, their full reports, progress checkpoints,
  witness tables, Unicode/ASCII theory exports and successful replay.
- 88 cumulative CNF fingerprints for a fixed recurrence corpus over temporal
  and spatial frames, including points outside their current quorum.
- Zero-time, decision, node, recurrence and frame cutoffs; inconsistency and
  axiom-only checking; malformed witness rejection; ignored descriptive flags.
- Browser inspection/check/search payloads, complete downloads and progress.

The two normalized record sets have SHA-256
`f4ad9ac13865fc583af1c6e0ee81e9bf44a250a5ebedb61826a6760b1c57a9b6`.
Equal original/revised behavior is a regression check, not independent evidence
that the original behavior was correct. That is why the semantic oracles are
retained and rerun separately. All example files and browser source assets
also retain their original bytes.

## Performance and tradeoffs

`tools/benchmark_compile.py` isolates compilation from parsing, solving and
replay. `tools/benchmark_search.py` measures complete fixed-frame checks.
The handover contains alternating-order, fresh-process measurements and exact
CNF fingerprints in `evidence/compile-benchmarks-0.7.3.json` and
`evidence/check-benchmarks-0.7.3.json`.

In this local run, compilation medians fell by about **13–35%** across the
five measured cases. Complete fixed-frame checks fell by about **5–10%** in
the five search-benchmark cases. These are workload-specific measurements:

| Compilation workload | Original median (ms) | Revised median (ms) |
| --- | --- | --- |
| Fixed-point tutorial | 1.699 | 1.481 |
| Full Paxos | 162.317 | 138.267 |
| Simpler Paxos | 64.095 | 55.441 |
| 16-stage temporal recurrences | 54.208 | 35.493 |
| Nested recurrences | 1.139 | 0.944 |

Four fresh processes per version were run in alternating order, with nine
compilation repetitions per workload. The table uses the median of process
medians. No other workload ran concurrently. The raw records retain all
measurements and identical circuit fingerprints; milliseconds are rounded here.

The extra structural cache uses memory proportional to the analyzed syntax
and its free-name sets. It belongs to a single compilation and is discarded
with it; there is no global cache retaining theories. Faster bounded work can
complete more obligations before a time limit. This does not promise identical
elapsed times or identical timeout outcomes across machines.

## Validation and remaining limits

The [current validation record](validation.md) records the complete Python and
Node suites, demonstrations, semantic oracles, installation and package checks.
The outer handover contains raw logs, source hashes and distribution hashes.
Real Chromium/Pyodide execution remains blocked by missing Chromium; no browser
rendering or WebAssembly success is claimed. The required real-browser CI gates
remain in place. No public site was deployed and no remote Actions success,
native Windows/macOS execution or human accessibility review is claimed.

UNSAT still relies on the solver without a separately checkable proof
certificate. Bounds, cooperative resource limits and finite-time qualifications
are unchanged. `web/app.js` is sizeable, but its interaction state has extensive
regression coverage; a broad rewrite was not needed for this behavior-preserving
audit. See [semantics](semantics.md), [search](search.md), and
[the source provenance](../SOURCES.md) before broadening any correctness claim.
