# Release validation

The supplied release is **0.7.6**. Checks were executed on **20 October 2026**
with **CPython 3.12.14**, **Node v24.19.0** and Linux.

| Check | Result and scope |
| --- | --- |
| Python suite | 437 collected: 434 passed, three optional native-PySAT skips. |
| Nine Node suites | 218 passed, including DOM/runtime doubles. |
| Semantic and theory regressions | Truth tables, fixed points, scopes, protocol denotations, saved semantic hashes, paper-style rule names and independent witness replay. |
| CLI demonstrations | 30 scenarios, 81 property results and 22 independently replayed countermodels. |
| Reader and documentation | Shipped reader matches regenerated sources; prominent explorer links and exact authorship statement checked; current-release documentation and links verified. |
| Distribution/installation | Four consistent distributions, isolated offline wheel and sdist installs, CLI aliases, check/search/replay and installed HTTP serving. All four artifacts rebuild byte for byte from the sdist. |
| Handover | Builder tests, portable paths, exact checksum membership, seven handbook sections, local links, tamper detection and byte-identical repeated builds. |
| Actual browser/runtime | Not executed locally: Chromium is unavailable. Node doubles and HTTP checks do not establish rendering or WebAssembly execution. The real-browser Actions gate is retained. |
| Optional native PySAT | Unavailable; three optional native tests skipped. |

Current logs: [Python](../reports/tests.txt), [Node](../reports/browser-tests.txt)
and [demonstrations](../reports/demo.txt). The handover's `evidence/README.md`
indexes current installation, presentation and assembly records.

## Reproduce

```sh
python tools/check_version.py
python tools/build_guide.py
python tools/build_release.py --prepare-only
python -m unittest discover -s tests -v
python demo.py
python tools/build_release.py --check
python tools/build_release.py
python tools/test_install.py dist/releases/muql_explorer-0.7.6-py3-none-any.whl
```

Use the Node/browser commands in [Contributing](../CONTRIBUTING.md).
The [correctness guide](audit.md) states the contracts exercised by the tests.
Passing finite checks is not an unbounded theorem or a certification of
transcription from the unavailable original PDFs. No public deployment, remote
CI success, native Windows/macOS run, other Python version or human
accessibility review is claimed.
