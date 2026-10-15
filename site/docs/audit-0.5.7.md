# Fresh package audit: 0.5.6 → 0.5.7

11 October 2026. This audit started from the delivered **0.5.6** archive,
compared all 156 archived files with the working source, and froze a separate
baseline before making changes. Its SHA-256 is
`b6a8d4ca578520313756706f23515579018b99edc46967dd87583cf28aa7c7b8`.
The baseline collected 309 Python tests: 306 passed and three optional native
solver tests were skipped. Passing those tests did not expose the defects below.

The review found and fixed problems in draft preservation, diagnostics,
serialization, public API validation, and resource handling. It also removed
several avoidable sources of quadratic or exponential work. Independent finite
oracles found no disagreement in the supported logical denotations, solver
answers, or shipped protocol examples. This is substantial regression evidence,
not a proof that every possible input and environment is correct.

## Scope and method

Six independent reviews covered the parser and loader; frame/evaluator/compiler;
Boolean solver and native adapter; checking/search/replay; browser and JSON
bridge; and command line, demos, and paper translations. Integration review also
covered the Bash launcher, site and guide generators, package metadata, source
and wheel contents, GitHub workflows, and documentation contracts. Production
changes were reviewed against the frozen baseline before integration.

Expected results came from explicit truth tables, exhaustive valuations,
independent set arithmetic and permutation enumeration, and brute-force Boolean
models. New tests were not limited to copying existing outputs or comparing two
implementations which share the same algorithm. The concrete evaluator remains
independent of the compiler, including its optimized quantifier and quorum tests.

The supplied Paxos PDF was checked against the semantic definitions and visually
at Figures 11 and 12. Simple's four variants were checked against Section 6.1.
The pinned [companion paper, version 3](https://arxiv.org/pdf/2512.21137v3) was
reopened for Voting, Bracha, Crusader, and the weakening experiment. Source
identity and the finite-scoping choices remain in [SOURCES.md](../SOURCES.md).
No example formula or protocol axiom needed alteration.

## Confirmed findings and corrections

Severity concerns the affected interface, not the correctness of every previous
reported model-checking result.

| ID | Impact | Problem in 0.5.6 | Correction |
| --- | --- | --- | --- |
| F1 | High: user data | Closing the browser during failed or incomplete startup could overwrite an existing draft with the initially empty editor. | Save only after source has been restored, loaded, or deliberately edited; disable source editing/import while initialization is pending. |
| F2 | Medium: diagnostics | Declaration slices lost their original columns; some multiline formula headers also displaced errors. | Carry statement offsets through list, quorum and formula parsing; map them back to document coordinates. |
| F3 | Medium: browser navigation | Python counts Unicode characters and supports more line separators than the browser's old LF/UTF-16 calculation. Error jumps could select the wrong character. | A pure editor helper maps Python positions to native textarea offsets and selects complete characters. |
| F4 | Low: workflow | CRLF files looked edited immediately after loading because textareas normalize line endings. | Record the normalized textarea value as the unchanged-source baseline. |
| F5 | Medium: machine output | Unicode reports on ASCII stdout failed with exit 2 instead of emitting JSON and the actual checking result code. | Check encodability before writing; use lossless JSON escapes only when needed. UTF-8 output remains readable. |
| F6 | Medium: Python API state | Frozen frame objects could retain mutable caller-owned lists/sets, invalidating cached contexts or intersections after mutation. | Snapshot points and quorums into immutable containers at construction. |
| F7 | Medium: limits | Noninteger evaluator contexts were accepted; NaN/infinite enumeration limits could bypass the intended bound. Some huge timeouts leaked conversion errors. | Validate actual integer contexts/limits and consistently reject invalid timeouts with controlled errors. |
| F8 | Medium: deadline contract | The low-level solver could return a root-level UNSAT result just after its deadline. | Check the clock immediately before that return, as already done for SAT. The late answer becomes `unknown`; this was not a false Boolean inconsistency result. |
| F9 | Medium: resource use | Zero timeout still allocated solver arrays proportional to the declared variable count. | Return `unknown` before allocating state or consuming clauses. |
| F10 | Medium: replay | Even an incomplete witness triggered construction of the entire Cartesian set of required atomic cells. Huge signatures could overflow or consume excessive memory. | First count cells with a bound; validate distinct rows against the signature and compare cardinalities. Check malformed failure contexts before semantic evaluation. |
| F11 | Medium: serialization | Some semantically valid direct-API value terms could not be exported as reparsable theory source. | Quote names that need literal syntax and disambiguate explicit value equality from prefix keywords; preserve meaning through export and reload. |
| F12 | Low: build diagnostics | A malformed example `next` value could escape validation as an unhandled `TypeError`. Source-directory symlinks escaped descendant-only checks. | Validate reference types and source roots before copying; preserve the previous build on failure. |
| F13 | Deployment configuration | The Pages build job lacked read permission for Pages metadata needed by `configure-pages` on private repositories. | Grant `pages: read` to the build job. Deployment write permissions stay confined to the deployment job. |

F13 follows the documented [GitHub Pages API permission requirement](https://docs.github.com/en/rest/pages/pages#get-a-github-pages-site)
and the action's [reported private-repository failure](https://github.com/actions/configure-pages/issues/188).
It was checked against the workflow and permission contract; no live repository
deployment was performed. The ordinary test workflow now explicitly requests
only repository read permission.

The regression tests reproduce the concrete failure cases. The parser, solver,
evaluator, replay and page-state fixes have tests which fail against the frozen
baseline. Browser controller tests use DOM/network doubles; they do not establish
actual rendered alignment or browser runtime behavior.

## Cleaner structure and measured performance

The changes reuse small helpers for whitespace scanning, source coordinates,
bounded atomic-cell counting, and limit validation. Formula-validation tables
are now constructed once instead of once per visited AST node. SAT limits and
checker/search limits deliberately retain separate contracts: low-level SAT
allows positive infinity, while public bounded checking/search require finite
time budgets.

Affine existence is the negation of the second-largest truth value among its
witnesses. Unique existence combines that with their maximum. The compiler
uses a linear lattice fold; the independent evaluator counts true and designated
witnesses. This replaces pairwise expansion without collapsing the broken value
or changing meaning. A point common to all quorums also certifies every required
intersection, avoiding unnecessary exponential work in concrete `twined` replay.

| Workload | 0.5.6 | 0.5.7 | Evidence |
| --- | ---: | ---: | --- |
| Compile affine existence over 300 values | 90,303 variables; 359,103 clauses | 2,391 variables; 5,671 clauses | Exact circuit sizes; one/two-value sizes unchanged |
| Same compilation, local median | 530 ms | 6.2 ms | Five fresh compilers per size |
| Parse a 40,000-name declaration | 413 ms | 21.7 ms | Median of five runs; index-based scanning |
| Validate an 8,191-node AST | 16.8 ms | 3.3 ms | Median of five runs; shared validation tables |
| Replay a complete 64,000-cell witness | 204 ms; 20.23 MB traced peak | 74 ms; 12.79 MB traced peak | Five runs; indexed lookup and no second Cartesian set |
| Zero-timeout SAT with 100,000 variables | 16.83 MB traced allocation | 1.6 KB | Allocation removed before state construction |
| Replay `twined(15)` with 30 quorums sharing a point | Up to 155,117,520 subfamily intersections | One common-intersection scan | Regression forbids entering the combinatorial enumeration |

These are illustrative measurements on CPython 3.12.14 in this environment,
not universal speed promises. Memory figures are incremental `tracemalloc`
peaks, not process RSS. Raw measurements are included in
[audit-benchmarks.json](../reports/audit-benchmarks.json).
A 103-formula SAT corpus retains identical status, decisions, and assignments;
its roughly 0.29-second median is essentially unchanged. A broad solver rewrite
or additional runtime dependency was not justified.

## Independent checks and regression evidence

- **35,916 semantic comparisons across 411 models**, checked against a separate
  complete-vector oracle and both compiled truth thresholds. The 822 SAT checks
  force each valuation and then test whether any compiled output can disagree.
- Every assignment over value domains of sizes 1–5 for quantifiers; finite and
  stuttering time; nested modal/temporal operations; contexts outside their
  quorum; monotone and nonmonotone least/greatest recurrences, including nesting.
- All 256 three-point generator families for union closure and 508 direct
  repeated-quorum intersection checks.
- All 729 partial assignments of a six-variable CNF; 210 seeded CNFs with
  exhaustive Boolean models; 279 learned clauses checked for entailment and
  assertion/backtracking invariants, including 233 from satisfiable inputs.
- Independent enumeration of 271 labeled five-point families with at most
  three nonempty quorums: exactly 17 isomorphism classes. Existing exhaustive
  coverage of all families through four points is retained.
- Thirty-two generated modal theories and a separate bounded-search oracle;
  inconsistent, holds, counterexample and unknown outcomes; tampered witnesses
  with matching row counts cannot bypass replay validation.
- Voting checked over 19,683 valuations across its original and two altered
  theories. Returned witnesses are evaluated by the direct rules, independent
  of the parser, compiler, evaluator and SAT solver.
- Every shipped example retains its scopes and formula ASTs. All 30 demos retain
  their expected 81 property results and 22 countermodels. Both newly generated
  and all 22 baseline saved countermodels replay against their exact theories.
- CLI subprocesses cover both notations, Unicode JSON on restricted stdout,
  result exit codes, altered axioms, witness exports and replay. The Bash launcher
  retains interpreter selection, real local HTTP, spaces in paths, no-cache
  responses, source isolation and clean interruption.
- Browser-independent tests cover escaping, tokenization, native editor state,
  composition/high-contrast fallbacks, startup/draft state, source positions,
  worker lifecycle, retries, stale requests, cancellation, and bridge exports.

**Final totals:** 351 Python tests collected: 348 passed, three optional native tests skipped. All **45 Node tests** and all **30 demos**
pass. The extracted release repeats the complete Python suite and demo; the
installed wheel is checked outside the checkout, including all saved witness
replays. See [release validation](validation.md) for commands and transcripts.

## Preserved behavior and limits

The package still supports the CLI, Python API, browser explorer, offline reader,
and `bash serve.sh` launcher. Unicode and ASCII notation remain equivalent;
strong implication is only `⇀` or `-\`, and `=>` remains rejected. Current-quorum
`somewhere`/`everywhere` meanings are unchanged. The conjunctive Agreement property
and all protocol axioms are retained. The blue μ branding, compact symbol bar,
type scale, hanging step numbers, native textarea, and syntax highlighting remain.
Report schemas and serialized witnesses remain compatible.

No regression was found by these comparisons. These limits remain explicit:

- A fresh Chromium download attempt returned HTTP 403. No actual browser,
  screenshot, native textarea rendering/IME session, or real Pyodide run was
  available here. The Pages workflow requires 21 real-browser scenarios, or
  22 including MiniSat, before deployment; they are supplied, not locally passed.
- A fresh workspace-only PySAT installation attempt failed. Three real-native
  integration tests remain skipped. Adapter doubles and built-in SAT oracles do
  not replace native runtime verification; the native CI job is still required.
- Python 3.12.14 ran locally. Production files also parse under the Python 3.10
  grammar, but that is not execution on 3.10 or 3.13; the CI matrix covers them.
- No GitHub deployment was performed. Actions, browser/CDN behavior, and private
  repository settings require verification in the destination repository.
- Finite and bounded search results do not prove unbounded distributed protocols.
  UNSAT results have no separate proof certificate. Nonmonotone recurrence can
  require exponential enumeration and continues to return `unknown` at its limits.
- Native deadlines remain cooperative. Browser cancellation terminates its
  worker, but neither interface supplies a general hard memory cap. Replaying a
  legitimately huge witness can still be expensive.
- Human-readable CLI labels require a compatible terminal encoding. Formula
  notation can fall back to ASCII; JSON now escapes Unicode losslessly when needed.
