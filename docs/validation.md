# Release validation: 0.6.10

Validated on 14 October 2026 with CPython 3.12.14. This release changes the
browser's editing and continuation controls. The logic engine, theories, and
curated example catalog are unchanged from 0.6.9 (apart from the version).

- **374 Python tests collected: 371 passed, three optional native tests skipped.**
- **181 Node checks passed**, including **50 page-state tests**. Eleven added
  interaction checks cover undo, last-example Reset, paired Save controls,
  preserved drafts, stale-choice navigation, focus, and validation.
- Undo restores the exact originating preset, including presets sharing one
  source file. Cached metadata is used only for that exact source. Saving or
  inspecting an edited version does not lose the original curated identity.
  Imported and restored custom files remain distinct from presets.
- Reset returns to the last curated example, preserves the latest custom draft,
  and leaves the current source intact on cancellation or download failure.
  Both Save controls download identical source and share the saved-file baseline.
- Stale Run and Claims continuation actions focus the visible Update choices
  control without sending a run request. Invalid size fields cannot block that
  navigation. Fresh runs still validate their settings; busy and empty states
  stay guarded. Status text describes the current state without repeatedly
  announcing unchanged messages while typing.
- Version declarations agree at **0.6.10**. The extracted archive builds its
  static site and runs the CLI; its root is **`3muql-explorer/`** and its Bash
  launcher remains executable. Both pinned archives retain their original bytes.

## Latest pinned baseline: 0.6.9

The complete `3muql-explorer-0.6.9.zip` is retained unchanged. This update is a
separate release and does not replace the pinned download. Its SHA-256 is:

```text
da202711a7b21c9f0eb42c09bc1a86ff848c69791b5668316bead323be5f3028
```

The earlier 0.6.6 pin is also retained; its hash appears below. Current test
transcripts: [Python](../reports/tests.txt) and
[JavaScript](../reports/browser-tests.txt). The preserved
[CLI demo transcript](../reports/demo.txt) records all 30 scenarios from 0.6.9.

Chromium is absent locally, so these results do not establish rendered layout
or real Pyodide execution. The deployment suite now has **24 browser scenarios
(25 with the optional native solver)**, including the new edit/undo, Save/Reset,
and stale-choice flow checks. Its script passes syntax checking, but no local
browser pass is claimed. Three optional native Python tests remain skipped.

## Previous release: 0.6.9

Validated on 14 October 2026 with CPython 3.12.14. This release adds executable
superscript-Q notation and changes the curated/custom experiment workflow.

- **374 Python tests collected: 371 passed, three optional native tests skipped.**
- **170 Node checks passed**, including **39 page-state checks**, 13 highlighting
  checks, six notation checks, and the existing editor, worker, and model-view
  checks. Six Python guide checks cover rendering and embedded assets.
- All 13 paper/tutorial theory semantic fingerprints remain unchanged. Both
  superscript and plain-Q source parse to the same formulas; ASCII remains
  supported. Quoted values, comments, and error positions retain their content.
- The complete CLI demo confirms **30 scenarios, 81 property outcomes, and
  22 countermodels**. Every curated browser preset retains its expected results.
- Workflow regressions cover First steps on startup, explicit draft restoration,
  preserving drafts while browsing, flushing recent edits before returning to
  examples, the final custom-section continuation, and both Load theory buttons.
  Unedited loaded files and freshly saved source avoid misleading edit prompts.
- The original one-character font regenerates identically and appears correctly
  in a raster glyph preview. The editor layers share its font stack; the offline
  reader embeds it, and the static site serves it locally.
- Version declarations agree at **0.6.9**. The extracted archive builds its site
  and runs the CLI. Its root remains **`3muql-explorer/`**, with an executable
  Bash launcher. The pinned **0.6.6** archive is byte-for-byte unchanged.

Current transcripts: [Python](../reports/tests.txt),
[JavaScript](../reports/browser-tests.txt), and [CLI demo](../reports/demo.txt).
Chromium is absent locally, so no rendered-page or real Pyodide-browser pass is
claimed. The deployment checks cover the new Unicode glyph and revised workflow.
The optional native Python SAT dependency is also absent; its three tests skip.

## Previous release: 0.6.8

Validated on 14 October 2026 with CPython 3.12.14. This release changes only
quorum-quantifier presentation, leaving executable notation and logic unchanged.

## Typesetting checks

- **372 Python tests collected: 369 passed, three optional native tests skipped.**
- **161 Node checks passed**, including five new notation checks and all 32
  page-state checks. The Python suite adds five guide-rendering checks.
- All six quorum forms, both diamond spellings, ordinary variable quantifiers,
  escaped quoted values, comments, incomplete quotes, and hostile HTML preserve
  their exact text. Only operator Q markers receive superscript markup.
- Every generated formula retains its Unicode/ASCII round-trip. The guide's
  complete formula/search data is byte-for-byte identical to 0.6.7. Initial
  offline HTML and the live notation toggle share the same typography.
- All six toolbar labels use superscript Q but retain their original insertion
  strings. The editable source highlighter remains unchanged, preserving its
  exact textarea metrics. No syntax, model, solver, or CLI behavior changes.
- The source archive includes the shared renderer/CSS and their tests. The
  extracted package builds its site; its CLI reports version **0.6.8**.
- The pinned **0.6.6** ZIP remains byte-for-byte unchanged. Its recorded hash
  appears in the previous release notes below.

Current suite transcripts: [Python](../reports/tests.txt) and
[JavaScript](../reports/browser-tests.txt).
Real-browser rendering remains unavailable locally because Chromium is absent.
The existing browser tests now also check raised Q geometry and restoration
of superscripts after ASCII/Unicode switching; no local browser pass is claimed.

## Previous release: 0.6.7

Validated on 13 October 2026. This update changes the visual emphasis of the
four next-step actions. It preserves their labels, destinations, native
button/link behavior, loading safeguards, and keyboard focus handling.

## Pinned baseline

The original `3muql-explorer-0.6.6.zip` is preserved unchanged. The 0.6.7 UI
update is a separate release. The pinned archive's SHA-256 is:

```text
2aeb93a44c1dc570d73ee7f0ec3e4e1bd676b76f3b64e3b8616c0ad84f87cd97
```

## Workflow checks

- All **32 page-state tests pass**, including next-example navigation, focus
  restoration, adjusted experiments, and previous-result isolation.
- All **12 site-build tests pass**, including documentation links and safe,
  deterministic packaging. The extracted release builds the site successfully.
- Static inspection confirms that all four main actions use the same primary
  style and retain their native button/link roles. CSS gives them a minimum
  height of 52px, full available width below 560px, and a visible border in
  forced-color mode. Existing focus outlines and reduced motion remain active.
- Version declarations agree at **0.6.7**. Engine code (except the version
  declaration), theories, CLI, and the curated tour are byte-for-byte identical
  to the pinned baseline. Its ZIP hash is verified before and after packaging.
- This is a presentation-only change. The broader validation records below
  remain the baseline; no full engine rerun was needed. Chromium remains
  unavailable locally, so rendered-browser appearance is not claimed as tested.

## Previous release: 0.6.6

Validated on 13 October 2026. This release extends the curated tour without
changing any logic-engine behavior or example theory.

### Tour checks

- Both curated-example tests pass: every preset has a valid continuation, the
  tour visits all eleven in picker order before returning to the start, and
  all eleven presets retain their documented engine outcomes and downloads.
- All **32 page-state tests pass**, including navigation after adjusting run
  settings, loading the next preset's actual source and omitted axioms,
  returning to the start, and excluding edited custom source from the tour.
- Version declarations agree at **0.6.6** and the static site builds with all
  eleven presets. The source ZIP retains its `3muql-explorer/` directory.
- The broader 0.6.5 validation below remains the baseline. Full engine and
  browser-unit suites were not repeated for this navigation-only change.
  Real-browser rendering remains unavailable locally; no new browser pass
  is claimed.

Reproduce the targeted checks:

```sh
python3 -m unittest discover -s tests -p 'test_browser_examples.py' -v
node tests/browser/app-state.mjs
node tests/browser/notation.mjs
python3 tools/check_version.py
python3 tools/build_site.py
```

## Previous release: 0.6.5

Validated on 13 October 2026 with CPython 3.12.14. This release clarifies the
browser workflow. The core parser, evaluator, compiler, solver, search, replay,
and CLI are unchanged from the [0.6.4 audit](audit-0.6.4.md); the Python web
bridge additionally returns predicate names and arities for display.

### Baseline checks

- **367 Python tests collected: 364 passed, three optional native tests skipped.**
- **155 Node checks passed**, including **31 page-state regressions**. Twelve
  new page-state checks cover immediate loading, pending downloads, cancellation,
  failure rollback, source/preset identity, omitted axioms, adjusted experiments,
  Reset, previous results, numeric input, and keyboard focus.
- Selecting Simpler Paxos changes the actual source and all twelve assumptions;
  the version without write uniqueness visibly identifies the excluded axiom.
  Modified source, imports, and restored drafts cannot inherit preset claims.
- Previous-run disclosures retain the original source/report downloads. Every
  source, selection, mode, or bounds change separates the current experiment
  from old evidence, including numeric input before it loses focus.
- The metadata boundary verifies the actual predicate signature. The full
  Python suite continues to cover semantics, search, replay, CLI, examples,
  launcher, documentation links, packaging, and deterministic site generation.
- All **30 demo scenarios, 81 property outcomes, and 22 countermodels** retain
  their expected results; the CLI demo independently replays its witnesses.
- Version declarations agree at **0.6.5**. The archive retains the
  **`3muql-explorer/`** root and executable Bash launcher. The extracted package
  builds its static site and runs the CLI.

Current suite transcripts: [Python](../reports/tests.txt) and
[JavaScript](../reports/browser-tests.txt), and [CLI demo](../reports/demo.txt).
The preceding full audit's independent model replay and measured performance
results remain in [the audit](audit-0.6.4.md) and
[benchmark evidence](../reports/audit-0.6.4-benchmarks.json).

## Execution limits

**Actual browser execution is unavailable locally:** Chromium is absent.
Controller tests use DOM/network doubles; they do not establish rendered
layout, mobile interaction, or real Pyodide execution. The deployment gates
now include **18 standalone diagram scenarios** and **23 runtime/UI scenarios**
(24 with MiniSat), with new immediate-loading and previous-result checks. Those
real-browser checks must run in CI; no local rendered-browser pass is claimed.

The optional native Python SAT dependency is absent; three tests are explicitly
skipped. The Python 3.10–3.14 CI matrix was not run locally. Passing tests are
finite evidence, not formal verification or an unbounded protocol proof.

## Reproduce the release checks

```sh
python3 tools/check_version.py
python3 -m unittest discover -s tests -v
python3 demo.py
node tests/browser/highlight.mjs
node tests/browser/editor.mjs
node tests/browser/app-state.mjs
node --experimental-vm-modules tests/browser/worker-protocol.cjs
node tests/browser/model-data.mjs
node tests/browser/model-svg.mjs
node tests/browser/model-controller.mjs
node tests/browser/model-integration.mjs
python3 tools/build_guide.py
python3 tools/build_site.py
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for actual browser checks and
benchmark commands. No runtime dependency was added. The following record is
historical: its release identifiers, test totals, packaging names and claims
apply to the preserved 0.5.7 baseline, not to this release.

## Audited baseline: 0.5.7

Validated on 11 October 2026 with CPython 3.12.14. The package requires Python
3.10 or later; CI is configured for 3.10, 3.12 and 3.13. Only the local 3.12 run
is claimed here. See [the fresh audit](audit-0.5.7.md) for the independent review,
confirmed defects, fixes, measurements, baseline comparisons, and limits. The
[original audit](audit.md) records the earlier 0.1.1 review.

## Results

- **351 tests collected: 348 passed, 3 skipped.**
  The skipped tests require the unavailable optional PySAT dependency. The suite
  includes independent audit, search, deadline, notation, and demo checks.
- `=>` is rejected by the parser, theory loader and CLI; strong implication uses
  only `⇀` or `-\`. Quoted values and comments retain their literal contents.
- The modality aliases in the README match the parser. Tests distinguish
  current-quorum `somewhere` / `everywhere` from the explicit compound modalities,
  including nested formulas and both compiled truth thresholds.
- **30 demonstration scenarios: 25 fixed-frame checks and five automated searches.**
- **81 property results and 22 countermodels**, plus the expected finite-terminal
  inconsistency scenario.
- Every saved countermodel was replayed against its exact demonstration theory,
  including the original scope and axiom removals/replacements. All 22 saved
  0.5.6 witnesses also replay with the new engine.
- The 13 paper and tutorial examples preserve the audited scopes, 107 axiom ASTs and 20 macro
  definitions/parameter lists. Both Paxos examples use conjunction-based
  `Agreement`. The examples contain 59 properties, checked against independent
  denotations and reference fingerprints. Complete ASCII renderings load to
  the same theories. Existing
  ASCII inputs using `somewhere` / `everywhere` require the migration described
  in [notation.md](notation.md#compatibility-and-migration).
- The additional `examples/search/choices.md` is an unscoped template used by
  the default demo; it is separate from the 13 examples in the HTML reader.
- `VERSION`, package metadata, and the runtime version agree at **0.5.7**;
  the version check runs in CI.
- A wheel and source distribution built without network or build isolation
  for packaging verification; build outputs are excluded from the repository ZIP.
- The final wheel installed without dependencies or network in a fresh virtual
  environment. Outside the source checkout, its entry point reports version
  0.5.7, checks Voting and Simpler Paxos Agreement, searches from an unscoped
  template, and replays every saved demo and search witness.
- The final extracted source archive passes the complete test suite and demo.
- The offline HTML reader regenerates deterministically, and both notation
  renderings of every formula round-trip. Its JavaScript syntax, navigation,
  search and notation switching were checked. A browser executable was unavailable,
  so this release does not claim a rendered-browser layout inspection.

The source ZIP extracts into **`muql-explorer/`** and includes `VERSION`,
examples, documentation, tests, GitHub Actions configuration, regenerated
reports, the offline theory reader, and its generator. It excludes `dist/`,
build output, virtual environments, caches, and Git history. The repository
file list was checked with Git to confirm that the version file and CI workflow
are included.

Source execution needs neither pip nor setuptools. A wheel contains the runtime
modules; use this source ZIP for the demo, examples and documentation. See
[GitHub setup](github.md) for upload instructions and the browser-demo assessment.

## Browser explorer

The explorer and offline reader retain the blue μ branding, shared type scale,
compact 24-symbol toolbar, and four headings with hanging numbers and inherited
typography. The editor retains native text input with optional Markdown/MuQL
highlighting. Styles and the generated reader remain unchanged from 0.5.6.
The fresh audit fixes draft loss during startup, Unicode error selection, and
CRLF edit detection. Five new Node page-state tests reproduce startup failures,
draft restoration and saving, deliberate edits after failure, and CRLF loading.
These tests use DOM/network doubles and do not establish rendered behavior.

The Bash launcher `bash serve.sh` still defaults to `python3`; `--python` selects
another interpreter. It builds and serves only generated files on `127.0.0.1`,
with no-cache responses and clean Ctrl+C shutdown.

The release includes eleven example presets, an accessible responsive editor,
selected properties and axioms, fixed checking, bounded model search, optional
MiniSat, worker cancellation, local drafts, and report/witness downloads.
The same Python engine is used by the command line and browser bridge.

Locally completed checks:

- Fifteen bridge tests exercise request limits, source coordinates, finite
  checking, unscoped search, dropped axioms, unknown outcomes, model-only
  requests, retained theories, and independent witness replay.
- Two catalog tests cover all eleven presets with explicit expected outcomes,
  the page's actual default bounds, and exported theory semantics.
- Eight site-build tests check deterministic output, relative reader links,
  stale-asset removal, malformed references, source-root symlink rejection,
  manifest validation, and safe output replacement.
- Twelve local-preview tests check startup and failure paths, both interpreter
  names, a package path containing spaces, real asset downloads, no-cache
  headers, source-file isolation, and clean shutdown.
- Twelve Node tokenizer and thirteen editor-controller tests cover exact source
  preservation, escaping, both notations, source coordinates, native state, and
  fallback behavior. With five page-state and fifteen worker tests, **all 45
  Node tests pass**; these do not require a browser.
- Fifteen Node worker protocol tests use mocked runtime objects to check lazy
  startup, reuse, requests treated as data, native loading and fallback errors,
  version mismatch, concurrent requests, and error recovery.
- JavaScript syntax and HTML nesting/unique IDs were checked. The static site
  builds successfully with only Python's standard library.

**Actual browser execution was not available locally.** No Chromium, Firefox,
or WebKit binary was installed, and browser/runtime dependency downloads
returned HTTP 403. A real Playwright launch failed explicitly for the missing
browser. No screenshot, rendered-layout check, or WebAssembly/MiniSat success
is claimed for this environment.

The Pages workflow requires the real Chromium/Pyodide suite before deployment.
Its twenty-one browser scenarios (twenty-two including MiniSat) cover project-prefix
URLs, all principal search/check workflows, exact downloads, retained-axiom
experiments, model-only requests, incomplete searches, literal HTML rendering,
parser errors, draft preservation after failed startup, Stop/restart, keyboard
operation, and mobile layouts at 390 and
320 pixels. It saves screenshots and diagnostic artifacts for inspection.
These tests are provided but were not locally passed. A successful CI run is
required before treating the browser release as deployment-verified.

The browser's run budget begins after runtime/solver loading. An additional
one second allows report serialization, after which the main thread terminates
the worker. Manual Stop terminates it immediately. Runtime startup has a separate
90-second limit. A terminated run returns no success or proof, and may lose
partial results that were not yet returned. There is no hard browser memory cap.

## Automatic model search

The default `python demo.py` tour runs all five searches below with the built-in
solver. Each case prints a copyable `python -m muql search ...` command, its
bounds, bounded results, and any generated witness scope. `--output` saves
search reports and paired concrete Markdown/JSON witnesses alongside the
fixed-frame reports. `python demo.py --search-only` runs just these five cases.

| Search | Frames checked | Result |
| --- | ---: | --- |
| Unscoped choice template | 2 | Counterexample with two values |
| Voting: up to 3 points, 2 values, 2 stages | 72 | All three properties hold within the bounds |
| Voting without `Correct` | 4 | Agreement counterexample |
| Simpler Paxos: up to 2 points, 2 values, 3 stages | 12 | Agreement holds within the bounds |
| Simpler Paxos without `SPaxWrite01` | 1 | Agreement counterexample |

All three search countermodels replay against their generated Markdown theories.
These are finite searches, including the time conventions recorded in each
report; the witness choices and timings are not a stable interface.

An independent enumerator checked every labeled union-closed quorum family
through four points against enumeration up to isomorphism: the counts
are 1, 3, 14, and 165. The fresh audit also independently enumerates 271 labeled
five-point families with at most three quorums and confirms 17 isomorphism
classes. A separate tiny-model oracle enumerates all three-valued
valuations and computes modal formulas directly. Search agrees with it.
Tests also cover each size dimension, named values, completeness, non-vacuity,
unknown results, partial success, altered axioms, serialization, and tampering.

The optional PySAT MiniSat22 dependency could not be installed in this
environment. A fresh workspace-only installation attempt found no available
distribution; earlier direct package downloads also returned HTTP 403. Native execution and acceleration are therefore **not
claimed as locally verified**. Protocol tests exercise the adapter with an
independent tiny Boolean oracle, including budget exhaustion, resumption with
growing propagation budgets, and rejection of invalid models. Three actual
native integration tests are included and explicitly skipped here. A separate
CI job installs the `sat` extra, requires the native import, and runs the full
suite plus a native search; that CI job was configured but not run locally.

The deadline is cooperative. Tests check that late solver/replay results cannot
become proofs, but there is no hard process-level timeout or memory cap.

## Test inventory

| Area | Tests | Evidence |
|---|---:|---|
| Parser and literate input | 78 | Binding, AST/schema validation, macro hygiene, malformed input, bounded expansion, source locations, direct-API export, reserved value names, and seeded fuzzing |
| Direct evaluator, frame and compiler | 66 | Independent truth tables, full-frame recurrence enumeration, all unary truth functions, temporal/modal boundaries, immutable frame snapshots, optimized quantifiers, and both compiled threshold bits |
| SAT engine, circuits and backends | 45 (3 skipped) | Independently enumerated gate extensions, exhaustive small CNFs, complete bitset truth tables, learned-clause entailment, restarts, numeric underflow, deadline boundaries and resource limits |
| Checker and replay | 24 | Exhaustive small-frame oracle, designated truth, non-vacuity, API validation, malformed evidence and unknown outcomes |
| Paper examples | 18 | Nine theory baselines, 47,220 independent denotation comparisons, agreement with crashed participants, mutations, boundary inconsistency and 19,683 direct Voting valuations |
| Command line | 15 | Real subprocess JSON including ASCII stdout, replay, error/unknown exit codes and recurrence budgets |
| Automatic model search and replay limits | 32 | Independent finite-model oracle, all size dimensions, non-vacuity, property-specific unknowns, fresh names, paired witness export, bounded replay validation and five-point frame classes |
| Demonstration search tour | 6 | All five search outcomes, copyable commands, execution from another directory, direct witness replay, brief output, and failure on incomplete searches |
| Browser JSON bridge | 15 | Strict JSON types and limits, parser locations, retained axioms, model-only search, unknown results and replayable exports |
| Browser example catalog | 2 | Eleven real preset runs with independently specified expected property statuses and retained theory checks |
| Static site builder | 8 | Deterministic bundles, relative links, manifest validation, stale asset removal and safe directory replacement |
| Local preview launcher | 12 | Interpreter selection, real HTTP from another directory, port/build failures, browser fallback, Ctrl+C and generated-file isolation |
| Unicode notation and presentation | 30 | Symbol/ASCII/mixed AST equality, quotes/comments/offsets, both formatter styles and precedence, reference fingerprints, pure-ASCII theories, CLI display/fallback, replacement, rejection of `=>`, exact modality scopes and successful default Simpler Paxos checking |

Passing tests are finite evidence, not a formal proof. SAT witnesses and
countermodels are independently evaluated before being returned; UNSAT answers
have no separately checkable proof certificate. No model-checker result proves
arbitrary network size or natural-number-time correctness. The mathematical
proof of Simpler Paxos agreement is given separately in
[the agreement note](spax-agreement.md); it does not rely on finite
search results.

## Reproduce

```sh
python tools/check_version.py
python -m unittest discover -s tests -v
python demo.py --brief
python demo.py --search-only
python demo.py --output my-reports
python tools/build_guide.py
python tools/build_site.py
node --experimental-vm-modules tests/browser/worker-protocol.cjs
node tests/browser/highlight.mjs
node tests/browser/editor.mjs
node tests/browser/app-state.mjs
```

`reports/tests.txt` and `reports/demo.txt` retain the release transcripts,
including the automated search outcomes. [audit-benchmarks.json](../reports/audit-benchmarks.json)
contains the before/after measurements described in the fresh audit.
JSON reports and `*.countermodel.json` contain complete valuations. Some reports
arise from changes made in `demo.py`; replay requires the same scenario scope
and removals/replacements. For the standalone weakening:

```sh
python -m muql replay examples/bracha_weakened.md \
  reports/bracha_weakened--BrValidity.countermodel.json
```

For an automatically generated frame, replay its accompanying theory:

```sh
python -m muql replay reports/search_choices--AtMostOne.md \
  reports/search_choices--AtMostOne.countermodel.json
```

See [the search guide](search.md) for commands to reproduce bounded searches.

Use `replay --max-mu-contexts N` when the original check required a larger exact
recurrence budget. Insufficient replay resources exit 3, rather than claiming
an invalid witness. Exact witness choices are not a stable interface; the
mathematical outcomes and independently replayed values are.
