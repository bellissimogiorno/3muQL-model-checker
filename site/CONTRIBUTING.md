# Contributing

Use Python 3.10 or newer. The core runtime and Python tests use the standard library.
Browser integration tests additionally require Node, Playwright, and Chromium.
Real engine integration needs the pinned Pyodide runtime (normally downloaded
from the CDN); the diagram browser tests run locally without Pyodide.
See [release validation](docs/validation.md) for completed checks and limitations
of the 0.7.6 release environment.

```sh
python tools/check_version.py
python -m unittest discover -s tests -v
python demo.py
python tools/build_guide.py
python tools/build_release.py --prepare-only
python tools/build_release.py --check
```

Run these commands from the repository root. For the installed `3muql` command,
use a virtual environment and `python -m pip install -e .`. The `muql`
command is a compatibility alias; Python imports and `python -m muql` use the
module name `muql`.

The repository release number is recorded in `VERSION`. When making a release,
update it together with `[project].version` in `pyproject.toml` and
`muql.__version__` in `muql/__init__.py`. The version check runs in CI and fails
if these disagree. Source execution and installed wheels retain the same version.
The generated browser snapshot is included in both the source and wheel; keep
it synchronized after edits with the release commands above.
See [GitHub setup](docs/github.md) for the repository layout and first upload.

## Build and verify a portable release

After updating the source, version, and documentation:

```sh
python tools/check_version.py
python tools/build_release.py --prepare-only
python tools/build_release.py --check
python -m unittest discover -s tests -v
python demo.py --brief
python tools/build_release.py
```

The preparation and drift check use only the standard library. Preparation
regenerates tracked `site/`, `muql/_site.zip`, the root landing page, and
`.nojekyll`. The default build additionally uses `setuptools>=61` and `wheel`
in the active interpreter to build Python distributions; it does not download
or install build dependencies. Install those build tools beforehand if needed.
`--skip-python` produces only the source and static-site archives; do not use
it for the complete handover.

The release products appear in `dist/releases/`:

| Product | Purpose |
| --- | --- |
| `3muql-explorer-0.7.6.zip` | Complete portable source tree, including generated browser snapshots |
| `3muql-explorer-site-0.7.6.zip` | Static website; `index.html` is at the ZIP root |
| `muql_explorer-0.7.6-py3-none-any.whl` | Offline installation without build tools |
| Python source distribution (`.tar.gz`) | Installation or rebuilding with setuptools |

Keep private files, virtual environments, temporary build outputs, and report
exports out of releases. Include all four current distributions and their
checksums in the outer handover. The archive filename carries the version; the source ZIP
expands into the stable `3muql-explorer/` directory. The hidden-path allowlist
retains `.github/` and its ordinary descendants, `.gitattributes`, `.gitignore`, `.nojekyll`,
`site/.nojekyll`, and `site/.muql-site-build`; other hidden files are excluded.
Non-hidden files within the packaged directories remain included. Keep the supplied
`.gitattributes`: it preserves LF text while leaving archive/font bytes untouched,
so Git line-ending conversion cannot make a clean checkout look stale.

The installed application must work outside its source checkout. Use
`tools/test_install.py` to exercise a clean offline wheel installation, CLI
checking/search/replay, and the bundled HTTP app from an unrelated working
directory:

```sh
python tools/test_install.py dist/releases/muql_explorer-0.7.6-py3-none-any.whl
```

This covers packaging and serving; the real browser commands below separately
establish Python-in-WebAssembly execution.

The recommended Pages workflow deploys a fresh generated site at the project
root only after its real-browser gate passes. The alternative branch route
uses the tracked root landing page and `site/`. See [GitHub setup](docs/github.md)
for these distinct publication settings.

## Progress and execution budgets

Progress observers are optional. Their checkpoints describe actual engine
work; they do not change the requested bounded result or bypass independent
witness replay. Keep worker messages tied to the active request, ignore old
messages after Stop/restart, and keep progress snapshots separate from reports.
Do not derive a completion percentage or model total from frame counts.

The browser UI accepts any finite positive budget with a 10-second default.
The Python bridge accepts finite nonnegative budgets, including zero for an
immediate bounded attempt. Preserve
the separate 90-second startup deadline, bounded watchdog intervals for long
budgets, serialization allowance and reachable Stop control. Test long-budget
arithmetic with controlled clocks rather than waiting through long runs.

## Browser development

For a preview of the packaged snapshot, run
`python -m muql serve --port 0 --open`. For source development, run
`bash serve.sh`. It uses `python3` by
default; use `--python python` to select another Python 3.10+ interpreter.
It builds and serves the site;
restart after editing source files. Add `--open` to open your browser or
`--port 0` to choose a free port. Press Ctrl+C to stop.

For the browser integration suite under a GitHub Pages-style project prefix:

```sh
python tools/build_site.py --output dist/muql-explorer
node --experimental-vm-modules tests/browser/worker-protocol.cjs
node tests/browser/highlight.mjs
node tests/browser/notation.mjs
node tests/browser/editor.mjs
node tests/browser/app-state.mjs
node tests/browser/model-data.mjs
node tests/browser/model-svg.mjs
node tests/browser/model-controller.mjs
node tests/browser/model-integration.mjs
npm install --no-save --package-lock=false playwright@1.62.1
npx playwright install chromium
node tests/browser/model-view.mjs
python tools/test_browser.py --target actions --native
python tools/test_browser.py --target branch
# After installing the wheel into a separate virtual environment:
python tools/test_browser.py --target installed --python /path/to/venv/bin/python
```

The Node protocol tests use mocked runtime objects and do not establish
WebAssembly compatibility. The browser smoke suite uses the real worker,
engine, and runtime. The helper
starts and stops its HTTP server automatically: `actions` builds under
`/3muQL-model-checker/`; `branch` follows the supplied root redirect into
`site/`; `installed` launches the wheel's server from an unrelated directory
using the chosen interpreter. Use the actual virtual-environment executable
path for your platform (`Scripts/python.exe` on Windows). `--native` also
requires MiniSat. Running `tests/browser/smoke.mjs` directly remains possible
with `MUQL_WEB_URL` pointing to an already running server and
`MUQL_BROWSER_NATIVE=1` to include MiniSat. The **Deploy explorer** Pages
workflow requires both built-in and native
browser checks before deployment. Screenshots and diagnostic logs go under
`tests/browser/artifacts/`, which is excluded from Git.

The model data and controller tests run in Node; controller tests use DOM
doubles. SVG tests also use Python's standard XML parser (`python3` by default;
set `PYTHON` to choose another interpreter). They check recorded truth values,
exact quorum membership and failure contexts, escaping, geometry, and exports.
`model-view.mjs` starts its own temporary local server and exercises the real
diagram controls in Chromium. It needs neither a site build nor internet access
once Playwright and Chromium are installed. Passing the Node tests does not
establish that browser rendering has passed.

The source-highlighting and notation tests use only Node. They check escaping, token
coverage, exact source preservation, and controller fallbacks with DOM doubles.
The page-state tests cover startup failures, saved drafts, deliberate edits,
and normalized source loading. The real browser suite separately checks native
typing/undo, selection,
scrolling and resizing, composition, forced colors, imports, and draft restore.
Keep the native textarea authoritative and its decorative layer hidden from
assistive technology. Token styles must change color only, so both layers
retain identical text metrics.

The tiny `web/quorum-superscript.woff` supplies the real Unicode superscript Q
in theory source. It has an original outline under the project license and is
embedded in the offline reader. Normal builds need no font tools. To modify
the glyph, install the optional development package `fonttools`, run
`python tools/build_quorum_font.py`, then regenerate the reader with
`python tools/build_guide.py`. Keep the same font stack on both editor layers.

Keep theory content as data. Render names and formulas as text, never HTML.
Check that cancelled, timed-out, stale, and inconsistent results cannot be
mistaken for a completed proof. Preserve keyboard order and the mobile Stop
control. Review screenshots at desktop and narrow mobile widths when browser
execution is available; no automated check replaces a human accessibility review.

Keep model diagrams faithful to recorded data: distinguish the property's
failure context from atomic truth values, preserve participants outside the
selected quorum, and show the selected quorum as an explicit set in both the
page and SVG export. Membership labels must remain readable without color;
pagination must make members outside the displayed page clear. Distinguish whole-model
totals from the current view's stage, highlighted quorum, participants, and
atoms. Keep **Full model data** accessible independently of those controls.
The default view should show named atomic values together, so models with the
same frame can be distinguished; an individual atom must remain clearly named
when selected. Tables must state their own coverage: the stage table may show
an atom page even while the diagram focuses on one atom, and a time table shows
only that selected atom. Never label such a partial view as the whole model.
Keep atom page controls available outside the folded snapshot table. Larger
views should use filtering and pagination, and closed evidence panels should
defer rendering. **Download this view (SVG)** must describe exactly the
displayed selection and remain standalone, escaped, and free of executable
content or external resources. Preserve complete-model and replay downloads
separately from view exports.

## What makes a useful change

The [release validation](docs/validation.md) records completed checks and their
limits. `python tools/benchmark_semantics.py` compares closure and recurrence
algorithms; `python tools/benchmark_search.py` measures fixed
checking workloads. Pass `--package /path/to/another/release` to the latter
for a baseline comparison. Timings are diagnostic evidence, not test gates.

A parser or semantics change should include a small mathematical example whose
expected result can be checked independently. Solver changes should preserve
comparison against exhaustive small cases. Countermodels must pass the separate
evaluator before being reported. A configured search timeout, search resource
limit, or unsupported recurrence must produce `unknown`, never `holds`.
Front-end nesting or macro-expansion limits must reject the input clearly
before checking.

For a new paper example, include the paper version, figure/definition or theorem
number, every frame assumption, and any differences from the source. Explain
whether a property is a published claim or a tutorial conjecture. Distinguish
failures of weakened theories from counterexamples to the original statement.
Keep source mappings and mathematical justifications current as draft theories
develop. See [the Simpler Paxos agreement proof](docs/spax-agreement.md) for
an example of a natural-time argument accompanying finite checks.

Documentation and diagnostics are part of the interface. Show an exact command,
the scope, and the meaning of the result. Preserve dependency-free execution of
`python demo.py` and `python -m muql` from a source checkout.

Write the literate examples in Unicode and document their ASCII equivalents.
Use `⇀` / `-\` for strong implication. Keep token aliases separate from quoted
values and comments, retain original error offsets, and require both formatter
styles to round-trip to the same AST. Regenerate the offline theory reader
after changing an example. The semantic fingerprints in
`tests/data/notation-baseline.json` protect the audited theory meanings; update
them only with a justified mathematical change and its source correspondence.

## Comparing a refactor

`python tools/audit_equivalence.py --reference /path/to/reference/source --output comparison.json`
compares deterministic encodings, complete reports/progress and witness exports
in separate processes. Only report elapsed times and the version are excluded.
It is a regression comparison, so run independent semantic tests too.
`python tools/benchmark_compile.py --package /path/to/source` isolates compilation;
alternate source versions in fresh processes and retain raw measurements.

## Reporting a problem

Supply the smallest `.md` input that reproduces it, the complete command,
`python --version`, `python -m muql --version`, and the JSON report if available.
State whether the problem concerns parsing, source transcription, finite
semantics, search, or presentation. Include all relevant axioms rather than
only a failing property.

Before proposing an unbounded theorem counterexample from a temporal run,
inspect the finite boundary semantics described in `docs/semantics.md`.

## Structure

- `muql/syntax.py`, `theory.py`: parsing, names, literate input, immutable edits.
- `muql/frame.py`, `evaluate.py`: explicit frames and direct semantic evaluation.
- `muql/compile.py`, `sat.py`, `checker.py`: encoding, SAT and check orchestration.
- `muql/witness.py`: complete countermodels, SAT decoding and independent saved-model replay.
- `muql/cli.py`: command-line presentation and file export.
- `muql/server.py`, `muql/_site.zip`: loopback launcher and packaged browser app.
- `muql/web.py`: bounded JSON interface for the browser.
- `web/`: accessible page, styles, controller, presets, and Python worker.
- `web/model-data.js`, `model-svg.js`, `model-view.js`: recorded-model indexing,
  standalone diagram rendering, and accessible exploration controls.
- `tools/build_site.py`: static Pages build and optional local runtime bundling.
- `tools/build_release.py`: generated snapshots, drift checks, and release archives.
- `site/`, `index.html`, `.nojekyll`: ready-built branch deployment.
- `.github/workflows/pages.yml`: validated deployment directly at the Pages root.
- `examples/`: executable, explained source theories and experiments.
- `tests/`: regression and independent semantic checks.
- `docs/`: language, semantics, source correspondence, and findings.

The MIT license covers this package's original code and documentation. Source
papers remain works of their respective authors; links identify the originals.
