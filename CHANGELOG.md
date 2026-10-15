# Changelog

## 0.7.1 — 2026-10-15

- Make `3muql` the primary installed command, including `3muql serve`; retain
  `muql` as a compatibility alias for existing scripts. Keep Python imports,
  `python -m muql`, and the `muql-explorer` distribution identity unchanged.
- Use the canonical command in help, installation guides and CI checks.
  Exercise both installed entry points and preserve the 0.7.0 release artifacts.
- Quote ambiguous atom arguments, participant names and quorum members in the
  complete model tables so distinct legal names and tuples remain distinguishable.
- Prevent background autosave in an older browser tab from replacing a newer
  saved draft written by another tab. Keep drafts separate by application path
  and expose conflicting work as restorable or downloadable recovery copies.
- Normalize generated archive metadata and generated text line endings across
  platforms. Add Git attributes to retain LF text even with `core.autocrlf=true`.
  Validate required release files and reject symbolic-link paths before copying
  handover artifacts; exclude unintended hidden files from release trees and
  reject example references to files omitted by that filtering.
- Enforce the original hashes of all seven preserved release artifacts,
  including the four 0.7.0 distributions.
- Recheck the delivered release independently and record fresh validation
  evidence and remaining execution limits for this update.

## 0.7.0 — 2026-10-15

- Ship the interactive browser app as generated `site/`, with a root landing
  page and `.nojekyll`, so a Pages branch deployment opens the tool directly.
  Provide a **Deploy explorer** Actions workflow that builds and validates a
  fresh site before publishing it at the Pages root.
- Include the browser application in the Python distribution. Add
  `muql serve --port 0 --open` and `python -m muql serve` for a cross-platform,
  loopback-only launcher that works after installation and from source.
- Provide source ZIP, installable wheel, source distribution, and standalone
  static-site ZIP, with one release-building command and generated-file drift
  checks. Preserve standard-library-only CLI execution and source previews.
- Keep the browser runtime pinned to Pyodide 314.0.7. Add explicit HTTPS or
  relative runtime mirrors and local runtime bundling for offline static
  deployments; the default distribution downloads the runtime on first use.
- Preserve the existing engine semantics, Unicode/ASCII notation, curated
  examples, and four-step interface. Extend release, installation, serving,
  runtime-configuration, and deployment regression checks.
- Update the portable handover and documentation. Record completed validation
  and unavailable real-browser checks in [release validation](docs/validation.md);
  require real Chromium/Pyodide checks in the Pages deployment workflow.

Earlier entries below describe their own releases and are retained as history.

## 0.6.10 — 2026-10-14

- Pin the complete 0.6.9 release unchanged and deliver these refinements as a
  separate release, retaining the earlier 0.6.6 pin too.
- Restore the curated context when edits are undone back to the example's
  exact source. Keep the last curated example separate from the saved-file
  baseline, and preserve the user's selected claims and run settings.
- Put Save theory beside Load theory in the custom section. Add a Reset action
  that returns to the last curated example with safeguards for edited source.
- Make the main run action guide users to Update choices while source changes
  are pending. Keep the claims continuation and status message consistent with
  this state, and prevent stale source from reaching the checker.
- Extend interaction regressions for undo, saved source, reset, keyboard focus,
  and refreshing choices in both search and fixed-frame modes.

## 0.6.9 — 2026-10-14

- Use a real Unicode superscript Q (`ꟴ`) in bundled theory files, Unicode
  formatter output, and symbol insertion. Accept both `∃ꟴ` / `∀ꟴ` and the
  existing plain-Q and ASCII spellings without changing their meaning.
- Provide a small bundled font for the superscript character in the explorer
  and offline reader. Preserve literal values and source-editor alignment.
- Start each visit at First steps. Follow the curated examples through Crusader
  agreement, then continue to a separate custom-experiment section.
- Keep saved custom work available to restore explicitly; browsing the curated
  tour does not replace it. Identify custom source separately from presets.
- Put Load theory beside Save theory in the editor as well as in the custom
  section, with confirmation before replacing edited source.
- Preserve the pinned 0.6.6 archive and the CLI, model search, and check workflows.

## 0.6.8 — 2026-10-14

- Superscript the Q in displayed quorum quantifiers, including compound
  modalities, throughout the explorer, symbol toolbar, and offline theory reader.
- Share safe presentation markup and CSS between the explorer and reader.
  Preserve the exact formula text when copied, inserted, exported, or switched
  between Unicode and ASCII. Keep quoted values and comments literal.
- Preserve ordinary monospaced source editing, all accepted syntax, CLI output,
  and engine semantics. Keep the pinned 0.6.6 archive unchanged.
- Document the distinction between printed notation and source spelling, and
  add focused escaping, literal-value, toolbar, guide, and round-trip checks.

## 0.6.7 — 2026-10-13

- Preserve the 0.6.6 release unchanged as a pinned baseline; deliver this UI
  refinement separately.
- Give Continue to claims, Continue to run settings, Run, and Keep exploring
  the same primary blue styling and a shared minimum 52px click area.
- Separate continuation actions from the preceding controls with consistent
  spacing. Use full-width actions on narrow screens and let long titles wrap.
- Preserve keyboard focus, disabled states, reduced-motion navigation, existing
  button/link semantics, and the complete curated tour. Add a visible border
  for the main actions in forced-color mode.

## 0.6.6 — 2026-10-13

- Give every curated example a Keep exploring destination. Preserve the initial
  tour and extend it through all eleven presets in picker order, returning
  from Crusader agreement to the introductory choices example.
- Keep the tour available after changing properties, assumptions, or bounds
  while the example’s source is unchanged. Preserve source-edit safeguards,
  immediate loading, and separation of previous results.
- Check that every preset belongs to the same complete tour, and verify button
  navigation after adjusting an experiment.

## 0.6.5 — 2026-10-13

- Load examples immediately on selection, removing the separate preview state.
  Keep the previous theory on cancellation or download failure; lock Run while
  loading and protect edited source before replacement. Reset restores defaults.
- Identify edited source, imported files, saved drafts, and adjusted experiments
  explicitly. Clear preset hints when they no longer describe the experiment.
- Display the loaded predicate signature, and identify the theory in Claims
  and beside Run. Show selected property names and removed axioms prominently;
  open Assumptions for presets with excluded axioms.
- Move old results into a closed Previous run disclosure as soon as source,
  assumptions, claims, mode, or numeric settings change. Preserve their exact
  theory/report downloads and record the original run settings and axiom names.
- Explain that successful checks give finite evidence and different property
  cards can contain different models. Label the choices example as a standalone
  logic tutorial. Preserve diagram exploration, core semantics, and CLI behavior.
- Cover loading, failure, cancellation, restoration, adjusted presets, reset,
  prior-result isolation, numeric input and keyboard focus with regressions.
  Update the browser workflow guide and real-browser deployment checks.

## 0.6.4 — 2026-10-13

- Audit semantics, parser, solver, search, replay, CLI, browser, diagrams,
  packaging and documentation against a frozen 0.6.3 release. Preserve every
  example and replay all 22 archived witnesses; document evidence and limits
  in [the fresh audit](docs/audit-0.6.4.md).
- Preserve chosen properties and dropped axioms across source edits and draft
  reloads; flush recent edits when the page is hidden or left.
- Explain unsupported browser scopes before running, avoid impossible numeric
  inputs, and distinguish declared quorum generators from the complete family.
- Retain the selected stage after an invalid numeric edit; keep the selected
  atom visible in forced-color mode and make scope guidance accessible.
- Preserve CLI result codes when Unicode names cannot be displayed by the
  terminal, using readable escapes for unsupported characters.
- Generate quorum closure from the original generators; cache independent
  nested recurrences without caching changing outer dependencies; reuse an
  already replayed consistency model when it refutes a selected property.
  Keep independent failure checks, resource limits, and isolated witness data.
- Avoid unnecessary atom scans in default views. Give the offline guide the
  explorer's exact embedded 3μ favicon.
- Include missing public documentation and audit evidence in the static site;
  check links from the built output and preserve both theory-reader locations.
  Keep unrelated repository files and arbitrary report exports excluded.
- Correct obsolete browser assertions and strengthen full-data keyboard,
  scope, and high-contrast checks. Run installed-package CI outside the source
  checkout and include Python 3.10–3.14 in its matrix.
- Add independent closure, recurrence, witness-reuse, deadline, encoding and
  five-point enumeration regressions, plus reproducible benchmark scripts.

## 0.6.3 — 2026-10-13

- Separate **Whole model** totals from the current diagram view. State the
  displayed stage, quorum, participant range, and atom range, with direct
  access to **Full model data** independent of the exploration controls.
- Replace ambiguous model-state wording with **View at stage N** in diagrams
  and **Atom values at stage N** for the linked table. Give the table its own
  coverage label, and explain how it relates to a focused single-atom diagram.
- Label controls **Stage**, **Atoms shown**, and **Quorum highlighted**; explain
  that changing the highlighted quorum leaves atomic truth values unchanged.
  Distinguish **All atoms** from **All atoms (paged)** for larger models.
- Place **Download this view (SVG)** beside the diagram, with an explicit scope
  note. Preserve the complete valuation, replay downloads, and existing model
  exploration, failure markers, pagination, engine, and CLI behavior.
- Use **3μQL Explorer** consistently in page titles and current documentation;
  update the explorer and theory reader's blue badge and favicon to **3μ**.

## 0.6.2 — 2026-10-13

- Explain that **Search up to** supplies maximum sizes for generated frames,
  with smaller frames tried first. Keep these controls visible but disabled
  in **Check this frame**, along with search-only quorum and frame limits.
- Show the declared frame's sizes when checking, and summarize selected
  properties and retained axioms before running. Preserve search bounds when
  switching modes and restoring a saved draft.
- Make the selected quorum **Q** prominent as an explicit set above the model
  diagram and in SVG exports. Label participant cards **In Q** or **Outside Q**,
  and report quorum members outside the current participant page.
- Disable stage and quorum selectors when only one choice exists. Give axiom
  models a neutral exploration context while preserving counterexample failure
  markers, named atomic values, replay downloads, the Python engine and CLI.

## 0.6.1 — 2026-10-13

- Show named atoms and their truth values together in participant cards by
  default, with twelve atoms per page. The choice example's simultaneous chosen
  values and the small Simpler Paxos example's nine atoms are visible at once.
- Add **All atoms at this stage** to the Atom selector. Keep an individual
  atom's name inside each card, and show its time grid when selected.
- Keep atom page controls available outside the folded snapshot table and
  export the displayed overview or individual atom to SVG.
- Explain why smallest-first search can return the same frame for different
  counterexamples, and why increasing upper bounds need not produce a larger
  model. Preserve the engine, CLI, search behavior, and replay formats.

## 0.6.0 — 2026-10-12

- Add an interactive model diagram to counterexamples and axiom models. Select
  an atom, time stage, and actual quorum; inspect participant truth values and
  exact membership, with a linked table across time.
- Start at the recorded failure context, show its participant even outside the
  selected quorum, and provide a return action after exploration. Atomic values
  and property failure remain distinct; the diagram performs no new evaluation.
- Retain the full valuation and replay downloads, and add a standalone SVG
  download of the displayed view with an accessible description.
- Use labelled native controls, keyboard focus preservation, text and color,
  responsive layouts, enlarged text support, bounded pages and atom filtering.
  Build each view only when opened and release its resize observer on a new run.
- Keep the logic engine, CLI, source theories, witness schemas and search
  behavior unchanged. Package the source under `3muql-explorer/`.

## 0.5.8 — 2026-10-11

- Replace the two-part landing-page heading with one bold title:
  “3μQL: three-valued fixpoint quorum logic”.

## 0.5.7 — 2026-10-11

- Audit the complete package against a frozen 0.5.6 release, with independent
  semantic, solver, search, paper-example, browser-state, and CLI checks. Add
  42 Python regression/oracle tests and seven Node tests; retain every example
  formula and all 30 demonstration outcomes.
- Preserve saved browser drafts during incomplete or failed startup. Correct
  Unicode error selections and avoid false edit warnings after CRLF imports.
- Preserve exact declaration/formula error positions. Make large declaration
  parsing linear and reuse AST validation metadata.
- Compile and evaluate affine/unique existence in linear time while preserving
  three-valued semantics. Shortcut quorum-intersection replay when every quorum
  shares a point.
- Replay witnesses with bounded cell counting and indexed validation instead of
  materializing a second Cartesian set. Reject malformed or incomplete evidence
  before expensive semantic work.
- Snapshot frame inputs, validate evaluator contexts and resource limits, enforce
  the solver deadline on final UNSAT, and avoid allocating SAT state at zero timeout.
- Emit complete, lossless JSON on ASCII stdout. Make direct-API value names
  round-trip through theory export, including explicit equality with keyword names.
- Validate malformed example references and symlinked source roots in site builds.
  Grant the Pages build job the read permission needed for private-repository
  metadata; retain deployment writes in the deployment job.
- Document findings, benchmarks, preserved behavior, and unverified browser/native
  environments in [the fresh audit](docs/audit-0.5.7.md).

## 0.5.6 — 2026-10-11

- Place the four step numbers alongside their headings, hanging in the left
  margin and inheriting the heading font, size, weight, and line height. Keep
  this alignment when headings wrap and on narrow screens.
- Replace `serve.py` with the Bash launcher `serve.sh`. Default to `python3`;
  support `--python python` or an interpreter path while retaining `--port`,
  `--open`, automatic rebuilding, and Ctrl+C shutdown.

## 0.5.5 — 2026-10-11

- Highlight Markdown structure and MuQL declarations, operators, strings, and
  comments in the source editor, supporting both Unicode and ASCII notation.
- Enable highlighting by default, with a **Highlight syntax** switch whose
  setting is saved with the local draft.
- Keep native text editing, selection, paste, and undo; retain the shared type
  scale and align highlighting as text wraps, scrolls, or the editor is resized.
- Use readable plain text during input composition, in forced-color modes, or
  when a source is too large to highlight comfortably. Highlighting does not
  change the source, downloads, or the Python parser’s validation.

## 0.5.4 — 2026-10-11

- Compact the 24-symbol editor toolbar into closely spaced rows, replacing
  separate group-heading rows with subtle separators and retaining keyboard navigation.
- Use 32px pointer targets and 44px targets on touch devices; keep every symbol visible.
- Apply the same deliberate type scale to the explorer and standalone reader:
  16px body and controls, 14px supporting text, 18px formulas and minor headings,
  24px section headings, and 32–40px page titles at the standard browser setting.
- Respect the browser’s default text size, remove mobile text shrinking, and
  reflow navigation, labels, and controls to accommodate readable text.

## 0.5.3 — 2026-10-11

- Match the companion theory reader to the explorer’s white-and-blue visual
  style, system typography, and blue μ logo; preserve offline use and notation switching.
- Use consistent step numbers 1, 2, 3, 4 throughout the explorer.
- Attach an always-visible toolbar to the open Markdown editor, with all 24
  canonical logic symbols, including unique and affine existence.
- Add grouped symbols, readable names and ASCII hints, 44px touch targets,
  arrow-key navigation, and cursor-aware insertion with focus returned to the editor.

## 0.5.2 — 2026-10-11

- Add `serve.py` to build and serve the browser explorer in one command with
  either `python3` or `python`, using the chosen interpreter throughout.
- Support `--port` (including automatic free-port selection) and `--open`.
  Bind locally, print the address, avoid stale cached assets, and stop with Ctrl+C.
- Update local preview instructions and include the launcher in source releases.

## 0.5.1 — 2026-10-11

- Replace the split dashboard with an open, single-column, four-step workflow:
  choose a theory, select claims and assumptions, run, and inspect results.
- Use a white canvas, restrained blue accents, lighter dividers, and more space.
  Fold source editing and advanced settings until needed.
- Add persistent step navigation, keyboard-aware Continue actions, an explicit
  current-theory label, and automatic source opening for errors and imports.
- Require refreshed choices after source edits before a run can start. Keep
  cancellation and recovery available while reading a theory or running it.
- Preserve the Python engine, CLI, API, all examples, and replay formats.

## 0.5.0 — 2026-10-11

- Add a browser explorer with eleven presets, a Unicode/ASCII theory editor,
  axiom and property controls, bounded search, and fixed-frame checking.
- Run the shared Python engine in a reusable Pyodide module worker; keep the
  page responsive and support Stop, hard time limits, and optional MiniSat.
- Show concrete scopes, paginated atomic valuations, per-property outcomes,
  and replayable Markdown/JSON downloads. Preserve honest incomplete results.
- Add responsive layouts, keyboard and screen-reader support, mobile Stop
  controls, local drafts, file import, and explicit previous-result labels.
- Build the static site without external build dependencies; include a Pages
  workflow gated on engine tests and real browser integration tests.
- Browser/runtime downloads were blocked locally. Real browser checks are
  provided as a required deployment gate, not claimed as locally passed.

## 0.4.2 — 2026-10-11

- Package the repository under the stable top-level directory `muql-explorer/`.
- Add a root `VERSION` file and a dependency-free consistency check, run by CI,
  for the repository, package metadata, and runtime versions.
- Include GitHub upload instructions and an assessment of a live GitHub Pages
  demo using Pyodide. No website is deployed by this release.
- Deliver source files, tests, documentation, and reference reports; keep built
  distributions and local build output out of the repository archive.
- Preserve the checker, search behavior, and all 30 demonstration scenarios.

## 0.4.1 — 2026-10-11

- Include five automated bounded searches in the default `python demo.py` tour:
  an unscoped choice template, Voting with and without its correctness axiom,
  and Simpler Paxos with and without write uniqueness.
- Print copyable search commands, bounds, results, and generated witness scopes.
  Save concrete Markdown theories alongside search witness JSON with `--output`.
- Add `python demo.py --search-only` to run just the five automated searches.
- Add `examples/search/choices.md` alongside the 13 paper and tutorial examples.
  Use the built-in solver throughout the demo for dependency-free execution.
- The tour now covers 30 scenarios, 81 property results, and 22 countermodels.

## 0.4.0 — 2026-10-11

- Add `search` to find countermodels across bounded point, value, stage, and
  quorum domains, without requiring a declared frame. With no properties,
  search for a model of the axioms.
- Enumerate union-closed quorum families containing the whole point set,
  up to point isomorphism, visiting small domains and simpler families first.
  Report incomplete searches as unknown and distinguish an empty bounded
  model class from successful property checks.
- Preserve declared values as distinct domain members; choose fresh names for
  additional values and generated points. Export concrete Markdown theories
  alongside countermodel JSON and text for direct replay.
- Add optional PySAT MiniSat22 support. Search defaults to automatic backend
  selection; fixed-frame checking retains the dependency-free built-in default.
- Add a shared cooperative search deadline and optional `total_timeout` for
  the `check` API. Keep all thirteen bundled theories and their notation unchanged.

## 0.3.2 — 2026-10-11

- Use conjunction-premise `Agreement` consistently in both Paxos examples;
  keep all protocol axioms unchanged.
- Streamline the demonstration to 25 scenarios, 74 property results, and
  19 countermodels.
- Update the agreement proof note, documentation, theory guide, and reports.

## 0.3.1 — 2026-10-11

- Use conjunction-premise `Agreement` in Simpler Paxos. The default theory
  checks `Validity`, `Agreement`, and `Termination`.
- Keep all twelve Simpler Paxos axioms unchanged and document the natural-time
  agreement proof.
- Update source mappings, the theory guide, and release reports.

## 0.3.0 — 2026-10-10

- Make `somewhere(P)` an alias for `diamond(P)` / `◇(P)`, and
  `everywhere(P)` an alias for `box(P)` / `□(P)`. Both now range over points
  in the current quorum.
- Use `someQuorumSomePoint(P)` for `∃Q◇(P)` and
  `everyQuorumEveryPoint(P)` for `∀Q□(P)`. **Migration is required:** replace
  old `somewhere` and `everywhere` compound calls with these explicit names
  to preserve their original scopes.
- Add `someQuorumEveryPoint(P)` as an alias for `quorum(P)` / `∃Q□(P)`, and
  `everyQuorumSomePoint(P)` as an alias for `contra(P)` / `∀Q◇(P)`.
- Clarify the modality tables and migration guidance. Unicode formulas,
  temporal semantics, and the bundled theories' mathematical meanings remain
  unchanged. Strong implication remains `⇀` or `-\`; `=>` is rejected.

## 0.2.1 — 2026-10-10

- Reject `=>` rather than treating it as strong implication: that spelling
  clashes with another implication in the paper.
- Strong implication accepts only Unicode `⇀` or ASCII `-\`. Inputs from
  earlier releases must replace each old `=>` strong-implication operator
  with one of these spellings; `<=>` remains crisp truth-value equality.
- Document the notation distinction and migration in the language reference,
  notation guide, and README.

## 0.2.0 — 2026-10-10

Unicode notation and a clearer reading experience, with the same logic and
finite-scope guarantees as the audited 0.1.1 release.

- Accept Unicode, ASCII or mixed formulas. Strong implication is `⇀` in Unicode
  and `-\` in ASCII; `=>` remains an input compatibility alias.
- Add symbols for connectives, value binders, fixed points and quorum
  modalities, with quote-safe lexing and original source error positions.
- Use Unicode in all 13 theories, group related axioms, and wrap long formulas.
  Baseline checks preserve all 107 axioms, 60 properties, 20 macros and scopes.
- Add a compact, precedence-aware `format_formula` API, Unicode formula display,
  `muql list --notation ascii`, and automatic ASCII fallback on limited consoles.
- Add a complete side-by-side notation reference and an offline theory reader
  with search and a Unicode/ASCII toggle at `docs/theories.html`.
- Retain the prior audit and add notation round-trip, unchanged-theory and
  real CLI regression tests. Regenerate the tour reports and release artifacts.

## 0.1.1 — 2026-10-10

Independent audit release. See [the complete audit](docs/audit.md) for findings,
reproductions, verification, and remaining limits.

- Preserve every live SAT variable when floating-point activity underflows.
- Validate public theories and replacement ASTs before checking or replay.
- Validate macro arguments before expansion, avoid generated-name collisions,
  bound expansion work, and improve recursion/integer diagnostics.
- Parse quoted quorum names and separators correctly.
- Make evaluator valuations immutable snapshots to prevent stale cached results.
- Bound frame closure and intersection work; report incomplete closure as
  unknown; guard huge unused predicate arities; make zero timeouts consistent.
- Validate saved witness field types strictly and add configurable replay
  recurrence budgets with the correct incomplete-result exit code.
- Add independent audit tests and regenerate demonstration reports.

The Bracha weakening example was checked against its source and independently
verified mathematically.

## 0.1.0 — 2026-10-10

First public research release.

- Literate Markdown theories with an ASCII formula language and named axioms.
- Finite spatial, temporal, value-quantified and fixed-point semantics.
- Dependency-free SAT model search and independent countermodel evaluation.
- Command-line and Python APIs, JSON reports, and readable countermodels.
- All nine protocol theories explicitly axiomatized across the two source papers,
  with traceable formula mappings, and a weakening counterexample from the
  companion paper's discussion.
- A runnable demonstration sequence that checks its expected outcomes.

The checker establishes results only for a declared finite frame. In particular,
its terminal stutter frame is not an encoding of all natural-number executions.
