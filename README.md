# 3μQL Explorer

**Play with distributed algorithms as three-valued logical theories.** Put
axioms and correctness properties in a Markdown document, then ask the checker
to find a finite model that satisfies the axioms while falsifying a property.
Let it search bounded domains and quorum families, or choose one scope yourself.
When a countermodel exists, inspect its complete, independently replayed valuation.

3μQL Explorer is a dependency-free Python research and teaching package for
3μQL. It includes all nine protocol theories explicitly axiomatized across
*A declarative approach to specifying Paxos using three-valued modal fixpoint
logic* (Gabbay and Zanolini) and the companion paper,
[*Declarative distributed algorithms as axiomatic theories in three-valued
modal logic over semitopologies*](https://arxiv.org/pdf/2512.21137v3)
(Gabbay, version 3, 13 May 2026).

**Every successful check is limited to its finite frame or search bounds.** The
package is an executable companion to the mathematics, not an unbounded theorem prover.
In particular, the terminal self-loop of `time stutter` does not encode the
paper's full natural-number time with past history. See
[semantics](docs/semantics.md) before interpreting temporal results.

**Release 0.6.10 · Clearer editing and return paths.**
Start at **First steps** and follow **Keep exploring** through the eleven
curated examples. The tour ends at **Custom experiment — create your own
theory**, where you can start, load, or save a theory, restore a saved draft,
or reset to your last curated example. **Load theory** and **Save theory**
also sit together in the source editor. Undoing edits back to an example's
original source restores its curated context. If the source needs checking,
the main run action takes you directly to **Update choices**.
The bundled theory files, displayed formulas, and symbol toolbar now use a
real Unicode superscript Q: `∃ꟴ`, `∀ꟴ`, `∃ꟴ◇`, and the other quorum modalities.
The plain-Q spellings `∃Q` / `∀Q` and ASCII names remain accepted.
Version **0.6.9** is preserved unchanged as the latest pinned baseline;
the earlier **0.6.6** pin is also retained.
The archive expands into `3muql-explorer/`, with its release number in `VERSION`. See
[GitHub setup](docs/github.md) for upload instructions and
[the browser guide](docs/browser.md) for deployment and use. The `search` command
chooses participants, values, stages, and quorum families within explicit
bounds. The core still needs no dependencies; optional PySAT supplies a native
SAT backend. Read and write formulas with
`∀`, `∧`, `→`, and `⇀`, or type their ASCII equivalents. The bundled theories
use Unicode by default. Strong implication is `⇀`, written `-\` in ASCII.
The [notation guide](docs/notation.md) has a copyable symbol table and practical
typing examples. The [fresh package audit](docs/audit-0.6.4.md) records the
findings, fixes, independent checks, measured improvements, and remaining
limits. The [0.5.7 audit](docs/audit-0.5.7.md) and
[original audit](docs/audit.md) remain available for reference.

## Explore in the browser

The new web interface runs the same Python engine on your device. Start with
an example, edit a theory, select properties, and keep or remove individual
axioms. Search can supply the model. Counterexamples open at the recorded
failing context. **Whole model** gives the total numbers of participants,
quorums, stages, atoms, and values; **Full model data** opens the complete scope
and atomic valuation. Below these, the diagram shows one stage and highlights
one quorum, with explicit counts and ranges for the participants and atoms
currently visible. The selected quorum **Q** is shown as a set above the diagram
and inside its SVG; participant cards state whether they belong to it. Each
participant shows named atoms and their `t`, `b`, or `f` values, up to twelve
atoms per page. This makes simultaneous chosen values visible together. Explore
other stages and quorums, then use **Return to failing context**. The linked
tables compare atoms at the selected stage or follow one atom across time;
each table states its own coverage. These are views of the same model.
Smallest-first search can return the same frame for different theories; the
atomic values describe what happens in that frame. Save an SVG of the current
view, or download the complete countermodel and concrete theory for replay
with Python. See
[exploring a counterexample](docs/browser.md#explore-a-counterexample).

The interface follows four steps on one open page: choose a theory, select
claims and assumptions, configure the run, and inspect the results. Source
editing and advanced controls unfold when needed. After editing, update the
choices before running. Keyboard navigation, a persistent Stop control, Unicode
formulas, local drafts, and clear incomplete-search results are included.
The Markdown editor has a compact, visible symbol toolbar, including unique `∃¹` and
affine `∃⁰¹` existence, with mouse, touch, and keyboard insertion. The companion
theory reader shares the explorer’s blue 3μ branding and consistent type scale.
Body text, controls, supporting text, headings, and formulas each have a clear
role; mobile layouts reflow without shrinking the text.
Markdown and executable `muql` blocks are highlighted as you type, with both
Unicode and ASCII notation supported. **Highlight syntax** switches the colors
on or off; ordinary text editing, selection, paste, and undo are retained.
Eleven presets include all five search demonstrations, Voting and Simpler
Paxos comparisons, and tutorials on truth values and quorums. MiniSat is
available as an optional additional browser download.

For a local preview, open a terminal in the package directory and run:

```sh
bash serve.sh
```

The Bash script uses `python3` by default (Python 3.10 or later). Use
`bash serve.sh --python python` to select `python` instead. It uses the selected
interpreter throughout and needs no package installation. It
builds the site and serves it at **http://127.0.0.1:8000/**. Press **Ctrl+C** to
stop; restart after changing source files. Add `--open` to open your browser,
or `--port 8001` to use another port (`--port 0` chooses a free one).

An internet connection is required to load the browser's Python runtime on
first use. To publish, upload this repository, choose
**Settings → Pages → GitHub Actions**, and run the **Browser demo** workflow.
It runs the engine tests and real Chromium/Pyodide browser checks before
deployment. See [the browser guide](docs/browser.md) for the complete workflow.

The browser source and deployment workflow are included. Browser execution
could not be tested in the release-preparation environment: it has no browser
binary. The real browser checks are a required
deployment gate; they are not claimed to have passed locally.

## Start in one command

Use Python 3.10 or later. Unzip the source release, open a terminal in its root,
and run:

```sh
python demo.py
```

The demonstration runs **30 scenarios: 25 fixed-frame checks and five automated
bounded searches**. It checks the theories, removes or weakens selected axioms,
and prints countermodels with explanations. The search examples print copyable
`python -m muql search ...` commands, bounds, results, and any generated witness
scope. They cover an unscoped choice template, Voting, and Simpler Paxos.

Expected outcomes are asserted: a changed result or an unfinished search causes
a nonzero exit. The tour uses the built-in solver, so no installation, internet
access, or external SAT solver is needed. For concise output use
`python demo.py --brief`; add `--output demo-results` to save complete reports
and countermodels, including concrete Markdown theories for search witnesses.
To run just the five automated searches, use `python demo.py --search-only`.
See [the five search demonstrations](docs/search.md#run-the-demonstration-tour).

Let the checker find a scope for a counterexample:

```sh
python -m muql search examples/voting.md --drop Correct --property Agreement --max-points 3 --max-stages 2 --timeout 30 --countermodels witnesses
```

`search` varies the finite frame; `check` uses exactly the frame declared in
the file. The search above keeps Voting's formulas apart from the removed
`Correct` axiom. It chooses new points, stages, and quorum families, and keeps
declared values as a minimum domain. A found countermodel is saved with its
concrete theory so it can be replayed directly:

```sh
python -m muql replay witnesses/01-Agreement.md witnesses/01-Agreement.json
```

The generated Markdown already contains the retained axioms and selected
scope; no `--drop` flag is needed for this replay. You can also start from a
theory with no frame declarations. See [the search guide](docs/search.md) for
an unscoped template, all bounds, model-only search, and result interpretation.

Explore a theory directly:

```sh
python -m muql list examples/voting.md
python -m muql check examples/voting.md
python -m muql check examples/voting.md --drop Correct --property Agreement
python -m muql check examples/bracha_weakened.md --countermodels witnesses
```

A command that finds a counterexample exits with code `1`; that is an expected
result of these weakening experiments. For the shorter installed `muql`
command, use a virtual environment:

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
muql check examples/voting.md
```

For offline editable installation when `setuptools>=61` is already available,
use `python -m pip install -e . --no-build-isolation`. Source execution needs
neither pip nor setuptools.

For the optional native SAT backend, install `python-sat` through the extra:

```sh
python -m pip install '.[sat]'
```

`search` defaults to `--solver auto`: PySAT's MiniSat22 is selected when
available, otherwise the built-in solver is used. `check` defaults to
`--solver builtin`; either command also accepts `--solver pysat` or
`--solver auto`. Requesting `pysat` explicitly without installing it is an
error. Core execution remains dependency-free. See [release validation](docs/validation.md)
for the tested backends.

**Browse the theories:** open [docs/theories.html](docs/theories.html) in your
browser for a readable, offline guide to the 13 paper and tutorial examples,
with a Unicode/ASCII switch. The additional
[unscoped search template](examples/search/choices.md) is included in the demo
and [search guide](docs/search.md). Run the Python commands above to check the
theories; the HTML guide is a reader, with no checker running in the page.

## Your first literate theory

Save the following as `delivery.md`. Only fenced `muql` blocks execute; put
explanatory prose, tables, and references around them as you would in a paper.
Declarations from multiple `muql` blocks are combined.

````markdown
# A tiny reliable delivery theory

Two participants agree on whether a message was sent.

```muql
theory "Tiny delivery"
points alice bob
values unit
stages 1
quorums {alice,bob}
predicate sent/0
predicate received/0

axiom Correct: TF(sent()) ∧ TF(received())
axiom Deliver: ∃ꟴ◇(sent()) ⇀ received()
axiom Justified: received() ⇀ ∃ꟴ◇(sent())

property EveryoneReceives: ∃ꟴ◇(sent()) ⇀ ∀ꟴ□(received())
```
````

Here `∃ꟴ◇` means “some quorum, some point” and `∀ꟴ□` means “every quorum,
every point”. The same delivery axiom can be typed entirely in ASCII:

```muql
axiom Deliver: someQuorumSomePoint(sent()) -\ received()
```

Unicode and ASCII may be mixed within a formula. Save theory files as UTF-8;
the symbols are executable text, so no LaTeX or rendering step is needed.

```sh
python -m muql check delivery.md
python -m muql check delivery.md --drop Deliver
```

The original property holds in this scope. Without `Deliver`, a participant can
send while everyone receives nothing. Dropping an axiom returns a modified
theory for the run; it does not edit your Markdown file.

## Three truth values change the experiments

The truth order is `f < b < t`. Both **`b` and `t` are valid**. The middle value
can represent a crashed computation or conflicting information, according to
the theory; it is not a search timeout or missing solver assignment.

| Unicode | ASCII | Meaning |
|---|---|---|
| `¬P`, `P ∧ Q`, `P ∨ Q` | `!P`, `P & Q`, `P \| Q` | Negation, minimum, maximum |
| `P → Q` | `P -> Q` | Weak implication: `¬P ∨ Q` |
| `P ⇀ Q` | `P -\ Q` | Strong implication: `¬P ∨ T(Q)` |
| ∃ꟴ◇(P), ∀ꟴ□(P) | `someQuorumSomePoint(P)`, `everyQuorumEveryPoint(P)` | Some/all participants |
| ∃ꟴ□(P), ∀ꟴ◇(P) | `quorum(P)`, `someQuorumEveryPoint(P)`, `contra(P)`, `everyQuorumSomePoint(P)` | Some whole quorum / a member of every quorum |
| `◇(P)`, `□(P)` | `diamond(P)`, `somewhere(P)`, `box(P)`, `everywhere(P)` | Some/all points in the current quorum |
| ∃ꟴ(P), ∀ꟴ(P) | `existsQ(P)`, `forallQ(P)` | Some/all quorums, keeping the current point |
| `∀v. P(v)`, `∃v. P(v)` | `forall v. P(v)`, `exists v. P(v)` | Value quantification |
| `∃⁰¹v. P(v)`, `∃¹v. P(v)` | `affine v. P(v)`, `unique v. P(v)` | Three-valued at-most-one / unique existence |
| `μX. P`, `νX. P` | `mu X. P`, `nu X. P` | Pre-fixed meet / post-fixed join semantics |

Truth tests keep their readable names: `T(P)`, `F(P)`, and `B(P)` test for
exactly `t`, `f`, and `b`; `TF(P)`, `TB(P)`, and `FB(P)` test membership.
Temporal operators such as `once(P)` and `past(P)` also keep their names.

For example, `t → b` is `b` and therefore valid, whereas `t ⇀ b` is `f`.
Both `P` and `¬P` are valid when `P=b`. Consequently a countermodel must make a
property **`f`**, rather than merely make its negation valid. Axioms and
properties are evaluated globally at every stage/point/quorum context, including
contexts whose point lies outside the current quorum.

See the [language reference](docs/language.md) and
[precise semantics](docs/semantics.md) for precedence, temporal boundaries,
quorum closure, latest-value selection, and nonpositive fixed points.

## Explore the papers

| Example | Source theory | What to try |
|---|---|---|
| [Truth values and quantifiers](examples/basics.md) | Logic tutorial | Inspect deliberately false conjectures |
| [Fixed points](examples/fixedpoints.md) | Logic tutorial | Compare monotone recurrence with nonpositive mu |
| [Quorum geometry](examples/semitopology.md) | Logic tutorial | Distinguish current-quorum `□` from ∀ꟴ□ |
| [voting](examples/voting.md) | Companion Figure 3 | Drop `Correct`; weaken strong delivery arrows |
| [Bracha broadcast](examples/bracha.md) | Companion Figures 10–11 | Drop echo uniqueness or ready relay |
| [Crusader agreement](examples/crusader.md) | Companion Figures 13–14 | Drop second-echo uniqueness |
| [Simple, reliable](examples/simple_reliable.md) | Paxos §6.1 | Drop the decision progress rule |
| [Simple, crashes](examples/simple_crashes.md) | Paxos §6.1 | Compare true delivery with valid delivery |
| [Simple, eventual](examples/simple_eventual.md) | Paxos §6.1 | Inspect temporal progress |
| [Simple, eventual and crashes](examples/simple_eventual_crashes.md) | Paxos §6.1 | Combine delay and crashes |
| [Declarative Paxos](examples/paxos.md) | Paxos Figure 11 | Remove assumptions unused by the paper's proofs |
| [Simpler Paxos](examples/paxos_simpler.md) | Paxos Figure 12 | Drop write uniqueness or acceptance justification |
| [Bracha weakening](examples/bracha_weakened.md) | Companion §4.3 discussion | Reproduce the existential-delivery counterexample |

The mapping documents record the exact correspondences and modeling choices:
[companion paper](docs/companion-mapping.md), [Paxos paper](docs/paxos-mapping.md).
Protocol properties, tutorial conjectures, and deliberately weakened theories
are identified explicitly.

A particularly small finding concerns the proposed existential weakening in
companion §4.3. For one participant and payloads `red` and `blue`, let
`bcst`, `echo`, and `ready` be `(t,f)`, and let `dlvr` be `(f,b)`.
All axioms of that weakened theory are valid, but the actual red broadcast is
not delivered. The existential rule accepts the blue `b` witness. This refutes
the discussion's weakening claim; the original Bracha forward-delivery axiom
excludes it. The full explanation is in
[the executable example](examples/bracha_weakened.md).

The Paxos examples express `Agreement` with a conjunctive premise: two true
decisions, one now or earlier and one now, must have the same value. The
Simpler Paxos example's three properties—`Validity`, `Agreement`, and
`Termination`—hold in the supplied scope. The
[agreement proof](docs/spax-agreement.md) establishes the Simpler Paxos safety
property for natural-number time separately from these finite checks.

## Commands and reports

```sh
# Display a theory in Unicode, or choose ASCII for copying into a terminal.
python -m muql list examples/voting.md
python -m muql list examples/voting.md --notation ascii

# Weaken two rules without changing the source file.
python -m muql check examples/voting.md \
  --replace 'ObserveForward=quorum(vote()) -> observe()' \
  --replace 'ObserveNotForward=quorum(!vote()) -> !observe()'

# JSON only on stdout, suitable for another program.
python -m muql check examples/voting.md --json -

# Select properties and set explicit search limits.
python -m muql check examples/paxos.md \
  --property Agreement --property Validity --timeout 60
```

`--drop`, `--replace`, and `--property` are repeatable. In a run, removals happen
before replacements; a removed axiom cannot then be replaced. Names are
checked, so a misspelled axiom or property is an error. Use double quotes in
Windows Command Prompt where examples use shell single quotes.

`list` displays Unicode by default and falls back to ASCII if the terminal
cannot encode the symbols. Its `--notation unicode|ascii` option chooses an
explicit output style. Both input styles always remain available. When typing
strong implication in a POSIX shell, single-quote the whole replacement to
preserve its backslash, for example
`--replace 'ObserveForward=quorum(vote()) -\ observe()'`.
`=>` is rejected because that spelling clashes with another implication in
the paper. In older package inputs, change strong-implication operators from
`=>` to `-\` or `⇀`; keep the truth-value equality operator `<=>` unchanged.
See [notation, escaping, and migration](docs/notation.md).

**Migrating from 0.2.x:** `somewhere(P)` now means `◇(P)` and
`everywhere(P)` now means `□(P)`: both range only over the current quorum.
For their former compound meanings, use `someQuorumSomePoint(P)` and
`everyQuorumEveryPoint(P)` respectively. This is a scope change for existing
ASCII input; the bundled Unicode theories retain their original formulas.

The following outcomes describe `check`; the
[search guide](docs/search.md#results-and-completeness) explains results over
an entire bounded frame class.

| Outcome | Meaning | Exit code |
|---|---|---|
| `HOLDS IN SCOPE` | Axioms have a model; no valuation in this frame falsifies the selected property | `0` when all hold |
| `COUNTEREXAMPLE` | A complete valuation satisfies every axiom and makes a property `f` | `1` |
| `INCONSISTENT` | No valuation satisfies the axioms in this frame | `2` |
| Invalid input or file error | The requested run could not be performed | `2` |
| `UNKNOWN` | A time, decision, expansion, or resource limit prevented a complete result | `3` |

If a run contains both a counterexample and an unknown property, exit `3`
indicates the incomplete result; the found countermodel remains in the report.
Consistency is checked first, so contradictory assumptions are never presented
as successful property checks. JSON reports include a schema identifier, scope,
per-property results, a consistency witness when found, timing/search
statistics, and countermodels. `--countermodels DIR` writes readable tables and
JSON witnesses; it creates the directory when a witness exists. Replay one
against the same theory and modifications:

```sh
python -m muql replay examples/bracha_weakened.md witnesses/01-OriginalDeliverForward.json
```

Replay checks the actual valuation and formulas, rather than trusting the saved
`replayed` flag. If the original check needed a larger nonmonotone recurrence
budget, pass the same `--max-mu-contexts N` to `replay`. An insufficient replay
budget exits `3` (incomplete); it does not label the witness invalid.

Search can grow exponentially with participants, values, stages, quorums, and
formula structure. Start with small scopes and increase them deliberately.
For `check`, `--timeout` applies separately to frame construction, compilation,
and each SAT query. For `search`, it is shared across frame enumeration and
checking. Both are cooperative limits, not hard process time or memory limits;
parsing and file output are outside the search budget. A Python or native
operation can overrun until the next checkpoint. `--max-decisions`,
`--max-nodes`, and `--max-mu-contexts` provide additional limits. The search
guide distinguishes mathematical bounds from limits that leave a search
incomplete. Macro expansion has a separate input work limit, described in the
language reference.

## Python API

```python
from muql import check, load

original = load("examples/voting.md")
weakened = original.without("Correct")
report = check(weakened, properties=["Agreement"])

for result in report.properties:
    print(result.name, result.status)
    if result.countermodel is not None:
        print(result.countermodel.format())
        data = result.countermodel.to_dict()
```

Use `loads(markdown)` for a string, `theory.replace(name, formula)` for a new
formula, and `report.to_dict()` for serialization. `without` and `replace`
return new theories. `replay(theory, saved_countermodel_dict)` independently
rechecks a saved witness against the supplied theory; use the same weakening
when replaying a weakened theory's witness.

To vary frames, use `search` and load an optional unscoped template with
`for_search=True`:

```python
from muql import load, search

theory = load("examples/voting.md", for_search=True).without("Correct")
report = search(theory, properties=["Agreement"],
                max_points=3, max_stages=2, timeout=30)
print(report.status, report.complete)
```

`search(theory, properties=[])` looks for a model of the axioms. For one
declared frame, `check(..., total_timeout=30)` optionally adds a shared
cooperative deadline to its per-phase `timeout`. The [search API guide](docs/search.md#python-api)
shows how to save concrete witness theories and interpret incomplete results.

Use `format_formula(node)` for Unicode output, or
`format_formula(node, notation="ascii")` for ASCII. Both are available from
`muql`; formatting changes the spelling of a formula, not its meaning.
The [notation guide](docs/notation.md) shows Python and JSON examples that
preserve the backslash in `-\`.

The modules keep parsing, frame construction, direct evaluation, SAT encoding,
SAT search, orchestration, and presentation separate. Countermodels are
re-evaluated independently before they are returned. The release includes
exhaustive small-case checks and regression tests:

```sh
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and source-transcription
standards. The [release validation](docs/validation.md) records the tested environment and
results; [SOURCES.md](SOURCES.md) identifies the exact paper versions. Original
package code and documentation are [MIT licensed](LICENSE).
