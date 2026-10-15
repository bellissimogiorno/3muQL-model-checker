# Fresh package audit: 0.6.3 → 0.6.4

13 October 2026. This review started from the delivered **0.6.3** source archive,
froze a separate copy, and inspected the current source rather than assuming
that previous audits or passing tests established correctness. The archive's
SHA-256 is
`10d92e5d3858579d7c302a3d239e7ee70653819a10f9b5e1ea03a94d9ba1db8f`.
Its original suite still passed: 351 tests collected, 348 passed, and three
optional native-backend tests skipped.

The audit found and corrected interface, diagnostics, accessibility, and
verification defects. It also removed three specific sources of unnecessary
mathematical work. No new logical soundness error was found in the supported
semantics, solver answers, or protocol examples. That is the result of the
checks below, not a proof of correctness for every input or platform.

## Coverage and method

Six parallel source reviews and an integration review covered these boundaries:

| Area | Review and independent checks |
| --- | --- |
| Input and notation | Tokenization, source positions, macro hygiene, binding, reserved names, expansion limits, direct API validation, Unicode/ASCII formatting, and the rejected `=>` alias. |
| Finite semantics | Three-valued validity, nested quorum modalities, points outside quorums, finite/stutter temporal boundaries, latest true values, affine/unique existence, monotone and nonmonotone recurrences. |
| Frames and search | Union closure, exact enumeration up to point renaming, nonempty domains, named values, partial results, limits, and consistency before validity. |
| SAT and replay | Watched-literal propagation, conflict learning, restarts, native adapter validation, independent witness evaluation, complete atomic valuations, deadlines, and mutable result isolation. |
| Browser controller | Source/selection/draft state, JSON request mapping, cancellation, stale results, downloads, highlighting, worker lifecycle, and browser scope limits. |
| Model views and UI | Exact recorded cells and quorum membership, failure markers, view coverage, pagination, SVG escaping, keyboard order, labels, text scaling, forced colors, responsive CSS, and the shared 3μ branding. |
| Distribution | CLI exit codes and encoding, wheel and source contents, offline guide, deterministic build assets, destination safety, Bash launcher, loopback serving, version agreement, documentation links, and deployment gates. |

Expected mathematical values came from direct truth tables, explicit valuation
enumeration, all unions of generator subfamilies, and labelled families compared
under every point permutation. Tests also compare the compiler with a separate
concrete evaluator; these implementations continue to have separate semantic
algorithms. Tests using DOM or solver doubles are distinguished from actual
browser or native-solver execution.

The supplied Paxos PDF matches the identity recorded in [SOURCES.md](../SOURCES.md).
Figures 5, 6, 11 and 12, and the four Simple variants in Section 6.1 were checked
visually against the package's definitions and translations. The existing
natural-time Simpler Paxos agreement argument was reviewed separately from the
finite checker. Fresh retrieval of the pinned companion paper was unavailable;
its executable theories were checked against the retained direct-denotation
oracles and unchanged source fingerprints, not represented as a new inspection
of that PDF. None of the 14 example files was changed.

## Confirmed findings and fixes

Severity describes the affected workflow; these findings do not imply that
previously replayed mathematical counterexamples were invalid.

| ID | Impact | Problem and correction |
| --- | --- | --- |
| A1 | Medium: experiment state | Editing even Markdown prose discarded selected properties and re-enabled dropped axioms after reinspection. Preserve choices by name across edits and draft reloads; a different imported file starts a fresh selection. Obsolete names disappear, and changed source still requires review before running. |
| A2 | Medium: browser workflow | Nine named values produced an impossible Values field with minimum 9 and maximum 8. Explain browser limits beside the controls and disable the incompatible run; larger concrete frames can still be searched at smaller sizes when their named value domain permits it. Keep the backend's independent validation. |
| A3 | Medium: draft durability | A recent edit depended on a debounced save or `beforeunload`. Also flush when the page is hidden or left, preserving the startup and Forget draft guards. This closes a lifecycle gap; actual mobile-browser behavior still needs browser validation. |
| A4 | Medium: CLI outcome | Valid Unicode theory names made human-readable commands fail with exit 2 on ASCII terminals. A shared output helper escapes unsupported characters while retaining the real result code. UTF-8 output and lossless JSON output retain their own formats. |
| A5 | Low: mathematical clarity | The declared-frame note counted quorum generators as the whole quorum family. Name them as generators and explain union closure. Result scopes and diagrams continue to report the actual family. |
| A6 | Low: diagram navigation | Clearing the numeric stage field in a large model selected stage 0 because `Number("")` is zero. Invalid edits now retain the current stage; valid selections and return-to-failure behavior are preserved. |
| A7 | Accessibility | Selected-atom styling relied on colors that forced-color mode can replace. Add an outline, as already used for the current stage. Scope-limit guidance has a polite live announcement and describes the Run button; unchanged guidance is not repeatedly announced. |
| A8 | Verification gate | Two browser assertions expected obsolete quorum wording, and another counted incidental tables despite lazy valuation rendering. Assert the intended model-view and Full model data behavior, including keyboard focus and preserved selection. |
| A9 | Distribution verification | Installed CLI checks ran inside the checkout, which could shadow the installed package. Run them outside the source tree, and extend the configured Python matrix to cover 3.10–3.14. Only the local interpreter is claimed as tested here. |
| A10 | Presentation and documentation | The offline reader lacked the matching favicon; embed the explorer's exact SVG while keeping the reader self-contained. Correct the unscoped demo's displayed minimum from zero values to one, and remove stale references to a superseded Simpler Paxos presentation. |
| A11 | Medium: published documentation | Documentation links worked in the source tree but nine destinations were missing from the generated site, including the reader, provenance, licence and audit evidence. Publish an explicit list of required public files, retain both reader locations, reject symbolic links, and test actual references from the built site. Other repository files and arbitrary report exports remain excluded. |

## Performance and modularity

**Generate unions from the original generators.** Every open is a union of a
subfamily of the generators. Adjoining one original generator at a time reaches
every such union; combining every generated open with every other generated
open repeats work. The implementation now uses the former method, retaining
the exact output order, size cap, and deadline checkpoints. An independent
subfamily oracle checks 84 generator families on one through seven points,
and boundary tests cover exact caps and deadline expiry.

**Cache independent nested recurrences.** An inner `μ` or `ν` whose free
fixpoint variables do not include any active outer binding has the same result
for every candidate of that outer recurrence. Cache that result by formula,
context, and value environment. Outer-dependent recurrences remain uncached
under their changing bindings. Independent direct enumeration checks mixed
`μ`/`ν` nesting; another check varies both context and quantified values.
An initial broader cache slowed an ordinary temporal benchmark, so it was
rejected in favor of this narrower change.

**Reuse already validated counterexamples.** All selected property circuits
are present in the consistency assignment. When its failure literal is true,
the assignment can answer that property without another SAT call. The concrete
evaluator still checks the property's failure. Properties not refuted by this
model receive their normal separate query. Deadline checks remain in place,
statistics count actual work once, and each exported witness gets independent
mutable rows and axiom summaries. A different valid counterexample may be
returned; model identity is not a stable interface.

Measured examples and methodology are recorded in
[the benchmark evidence](../reports/audit-0.6.4-benchmarks.json). They are
workload-specific measurements, not a claim that every run becomes faster.
For example, 12 distinct conjectures dropped from a seven-run median of
73.6 ms to 26.9 ms, with SAT calls reduced from 13 to one. Cases whose
consistency model does not refute a property retain the original search path.

| Measured workload | Before median | After median |
| --- | ---: | ---: |
| Ten singleton generators, 1,023 quorums | 167.819 ms | 3.848 ms |
| Eight independent nested recurrences | 82.903 ms | 0.456 ms |
| Forty-stage monotone recurrences | 25.168 ms | 25.722 ms |
| Small outer-dependent nested recurrences | 0.068 ms | 0.078 ms |

The last two rows expose the trade-off: ordinary cases need not improve, and
checking structural dependencies has a small cost. The discarded broad cache
had a much larger regression. The final targeted changes preserve exactness
while addressing expensive cases. To reproduce the measurements, run
`python3 tools/benchmark_semantics.py` and `python3 tools/benchmark_search.py`.
For the checking baseline, pass `--package /path/to/0.6.3` to the latter.

The diagram also skips full atom-list scans when no atom or filter is selected.
No percentage improvement is claimed for this small allocation reduction.

The existing module boundaries are appropriate: syntax/loading, frames,
compiler, independent evaluator, Boolean solver, search/check orchestration,
JSON bridge, and separate model data/SVG/DOM modules. Small helpers centralize
CLI output, selection capture, browser eligibility, and structural recurrence
dependencies. No framework, dependency, broad solver heuristic, or speculative
module split was introduced. Lazy/paged rendering and disposal remain intact.

## Integrated verification

- **367 Python tests collected: 364 passed, three optional native tests skipped.**
  Sixteen tests were added; existing deadline fixtures were adjusted to continue
  exercising separate SAT calls, with explicit tests added for model reuse.
- **143 Node checks passed**, including editor/highlighting, page state,
  worker protocol, model data, SVG, controller, and page integration.
- **30 demo scenarios, 81 property outcomes, and 22 countermodels** retain their
  expected results. All 22 archived 0.6.3 witnesses replay with the final engine.
- All **14 example files** are byte-identical to 0.6.3. Their formulas round-trip
  in both Unicode and ASCII; fixed-scope theory exports also reload unchanged.
- The new independent search oracle enumerates every labelled five-point
  union-closed family with at most four nonempty opens, then compares all 120
  point permutations: exactly **49 classes**, matching production output
  with no duplicate classes.
- Version declarations agree. The final wheel installs without dependencies
  and is exercised outside the source tree. Site generation, the offline guide,
  source archive contents, launcher permissions, relative documentation links,
  and HTML ID/label references are checked. All 252 relative Markdown/HTML
  references in the generated site resolve to published destinations.
- The launcher tests start a real loopback server, including alternate working
  directories and paths with spaces, and check interpreter selection, serving
  boundaries, failures, and clean shutdown.

The transcripts are [Python](../reports/tests.txt),
[JavaScript](../reports/browser-tests.txt), and [demo](../reports/demo.txt).
The source archive retains the `3muql-explorer/` root. Runtime APIs, CLI names,
notation, report schemas, finite-time conventions, and source theory meanings
are preserved.

## Remaining limits

**Actual browser rendering remains unverified locally.** Playwright is present,
but a real launch fails because the Chromium executable is absent. No browser
screenshots, keyboard interactions, mobile layouts, forced-color rendering,
Pyodide execution, or browser MiniSat success are claimed. The corrected
deployment gates provide 18 standalone diagram scenarios and 21 engine/UI
scenarios, or 22 including MiniSat; these still need to run in CI.

The optional native Python SAT backend is also absent. An ordinary package
availability check found no installable distribution in this environment.
Protocol-double tests do not substitute for native execution. CI has a separate
native-solver job. Other configured Python versions were not executed locally.

The engine remains a finite checker with cooperative budgets, no hard process
memory limit, and no independently checkable UNSAT certificate. A `holds`
result concerns only the declared frame or exhausted search bounds. The stutter
frame is not an encoding of arbitrary natural-number time with past history.
These mathematical and resource limits are unchanged; see
[semantics](semantics.md) and [release validation](validation.md).
