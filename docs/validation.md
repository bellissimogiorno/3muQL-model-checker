# Release validation: 0.7.5

Executed on **20 October 2026** with **CPython 3.12.14**, **Node v24.19.0**
and Linux. This release changes 61 backward/forward axiom declarations in ten
bundled theory files to use `?` and `!`, including Bracha's `BrReady!!`.
There are 43 distinct renamed labels, reused by related variants.

| Check | Result and scope |
| --- | --- |
| Python suite | 437 collected: 434 passed, three optional native-PySAT skips. |
| Nine Node suites | 218 passed, including DOM/runtime doubles. |
| Theory identity | All 14 included theory/template files compared with 0.7.4: complete formula trees, macros, scopes, property names and declaration order agree after the explicit axiom-label mapping. Runtime engine source differs only in its version identifier. |
| Original semantic baseline | Original audited hashes in `tests/data/notation-baseline.json` retained; only the listed labels are reversed for that comparison. A separate regression requires the new names in every affected theory. |
| Offline reader | Generator shares the loader's label/declaration grammar; a regression checks the shipped reader against regenerated content. |
| Behavioral comparison | All 138 records agree after the explicit label migration, version and elapsed-time normalization: 30 demonstrations, 88 cumulative CNF fingerprints, reports, progress, exports, replay, cutoffs and browser-bridge results. |
| Demonstrations | 30 scenarios, 81 property results and 22 independently replayed countermodels; reports and saved axiom summaries regenerated with current names. |
| Distribution/installation | Source/site consistency, four distributions, isolated offline wheel and sdist installs, CLI aliases, check/search/replay and installed HTTP serving. Clean sdist rebuild reproduces all four distributions byte for byte. |
| Handover | Twelve builder tests; portable paths, archive/checksum integrity, handbook links, tamper detection and byte-identical repeated builds. |
| Actual browser/runtime | Not executed locally: Chromium is absent. Node doubles and HTTP checks do not establish rendering or WebAssembly execution. The real-browser Actions gate is retained. |
| Optional native PySAT | Unavailable; three optional native tests skipped. |

Current logs: [Python](../reports/tests.txt), [Node](../reports/browser-tests.txt)
and [demonstrations](../reports/demo.txt). The handover's `evidence/README.md`
indexes the explicit migration, comparison, installation and assembly records.

## Reproduce

```sh
python tools/check_version.py
python -m unittest discover -s tests -v
python demo.py
python tools/build_guide.py
python tools/build_release.py --check
python tools/build_release.py
python tools/test_install.py dist/releases/muql_explorer-0.7.5-py3-none-any.whl
python tools/audit_rule_labels.py --reference /path/to/0.7.4/source --output comparison.json
```

Use the Node/browser commands in [Contributing](../CONTRIBUTING.md).
`tests/data/rule-label-renames.json` records every old/new label and affected
file. The comparison normalizes only this explicit migration; it does not
ignore formulas or other substantive fields.

## Interpretation

The preceding [correctness audit](audit.md) and historical independent semantic
oracles remain separately versioned. Those oracle runs were not repeated for
this naming change; the current suites and explicit tree/behavior comparison
were executed on this release. Passing finite checks do not establish an
unbounded theorem or certify transcription from the unavailable original PDFs.
No remote deployment, native Windows/macOS run, other Python version or human
accessibility review is claimed.
