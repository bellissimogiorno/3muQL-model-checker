# Finding a countermodel automatically

`search` chooses a finite frame and uses SAT to find a valuation that satisfies
every axiom while making a selected property `f`. You supply the formulas and
inclusive size bounds. Every returned countermodel is independently replayed
by the concrete three-valued evaluator.

Use `check` when you want exactly the frame declared in a theory file. Use
`search` when you want the package to vary participants, values, stages, and
quorum families for you.

## Run the demonstration tour

The root demo includes five automated searches alongside its 25 fixed-frame
scenarios. Run it with:

```sh
python demo.py
python demo.py --search-only
python demo.py --brief --output demo-results
```

For each search, the demo prints a copyable `python -m muql search ...` command,
the bounds, the number of frames checked, and the result. When it finds a
countermodel, it also displays the generated scope. The tour uses the built-in
solver for reproducible, dependency-free execution, even if PySAT is installed.
`--search-only` runs just these five cases; without it, the full tour runs.

| Search | Frames checked | Expected outcome |
| --- | ---: | --- |
| [Unscoped choice template](../examples/search/choices.md): one point, at most two values, one stage | 2 | Two chosen values refute `AtMostOne`. |
| Voting: up to three points, two values, two stages | 72 | All three properties hold throughout the bounded frame class. |
| Voting without `Correct` | 4 | A countermodel refutes `Agreement`. |
| Simpler Paxos: up to two points, two values, three stages | 12 | `Agreement` holds throughout the bounded frame class. |
| Simpler Paxos without `SPaxWrite01`: up to two points, two values, three stages | 1 | Two true decisions refute `Agreement` in a one-point, one-stage model. |

The full tour expects **30 scenarios, 81 property results, and 22 countermodels**.
An unexpected outcome or incomplete search makes the demo fail. Bounded
successes remain finite results; the demo does not turn them into unbounded
proofs. `--output` saves each search report and pairs each search witness JSON
with a concrete Markdown theory for direct replay.

For example, after saving the tour to `demo-results`:

```sh
python -m muql replay demo-results/search_choices--AtMostOne.md demo-results/search_choices--AtMostOne.countermodel.json
```

The generated theory already contains the found scope and retained axioms;
no scope edits or axiom-removal flags are needed for replay.

## Start with an existing theory

From the package root:

```sh
python -m muql search examples/voting.md --drop Correct --property Agreement --max-points 3 --max-stages 2 --timeout 30 --countermodels witnesses
```

The search removes Voting's `Correct` axiom and looks for a counterexample to
`Agreement`. Its `--drop`, `--replace`, and `--property` options work as they do
for `check`; they do not edit the input file. A counterexample returns exit
code `1`, an expected result for this experiment.

**Frame declarations are not constraints on `search`.** Existing `points`,
`stages`, and `quorums` declarations are replaced by candidate frames. The
formulas, declared value names, and `time finite` / `time stutter` convention
are retained. Use `check` to retain a particular quorum geometry or number of
stages. An axiom such as `twined(3)` still constrains every candidate model.

## Start with just the logic

The package includes this template as
[examples/search/choices.md](../examples/search/choices.md). You can run it
directly or save the following as `choices.md` and edit it:

````markdown
# Correct choices need not be unique

Every choice is two-valued. Does that force at most one chosen value?

```muql
theory "Correct choices need not be unique"
predicate chosen/1

axiom Correct: ∀v. TF(chosen(v))
property AtMostOne: ∃⁰¹v. chosen(v)
```
````

```sh
python -m muql search examples/search/choices.md --max-points 1 --max-stages 1 --max-values 2 --countermodels choices-witnesses
```

For your own copy:

```sh
python -m muql search choices.md --max-points 1 --max-stages 1 --max-values 2 --countermodels choices-witnesses
```

A single participant can choose both values with truth value `t`; correctness
alone does not enforce uniqueness. No point names, quorum lists, or stage
counts were needed to find that model.

Only fenced `muql` blocks execute, as in ordinary literate theories. Templates
can also use `theory`, `let`, `values`, and `time`. Without a `values`
declaration, the search starts with a nonempty domain and generates fresh
names. Without a `time` declaration, it uses `finite`. To refer to particular
payloads such as `red` and `blue`, declare them with `values red blue`;
unbound names in formulas are errors, not implicit constants.

All declared values remain **distinct members of every candidate domain**,
even when a formula does not mention them. Search extends that domain with
fresh names up to `--max-values`. It does not identify two declared values or
silently discard an unused value. Generated names avoid capturing variables
or colliding with the formula's existing names. A value bound smaller than
the number of declared values is an input error.

`list` can display a template. `check` and `replay` require a complete concrete
scope; use the generated witness theory described below for those commands.

## Bounds and budgets

Size bounds are inclusive:

| Option | Default | Meaning |
| --- | --- | --- |
| `--max-points N` | `3` | Search from one participant through `N`. |
| `--max-values N` | The larger of `2` and the declared domain size | Search from the declared domain size through `N`; start at one if no values were declared. |
| `--max-stages N` | `3` | Search from one time stage through `N`. |
| `--max-quorums N` | `8` | Allow at most `N` nonempty quorums in a frame, including the whole point set. |

For each candidate domain size, the checker considers **all union-closed
families of nonempty point sets containing the whole point set**, up to a
permutation of points. Empty opens are implicit and do not count toward
`--max-quorums`. There is no restriction to majority quorums, upward-closed
families, or pairwise-intersecting frames unless a formula imposes one.

Candidate sizes are visited by increasing sum of the point, value, and stage
counts. For each size triple, quorum families with fewer members come first,
starting with the whole-set-only family. This often produces small witnesses;
it does not supply a separate minimality certificate.

Resource budgets govern how much of that mathematical class can be checked:

| Option | Default | Meaning |
| --- | --- | --- |
| `--timeout SECONDS` | `30` | Shared cooperative deadline for frame enumeration and checking. |
| `--max-frames N` | `1000` | Stop after at most `N` checked frames if more remain. |
| `--max-decisions N` | `100000` | Decision budget for each SAT query. |
| `--max-nodes N` | `500000` | Compilation/representation work bound used for each candidate. |
| `--max-mu-contexts N` | `8` | Context limit for exact nonmonotone fixed-point evaluation. |

`--max-quorums` defines the class being searched. `--max-frames` limits work;
reaching it before exhausting that class leaves an incomplete result. The
frame enumerator also has internal representation and candidate-extension
limits. Any such cutoff is reported, never treated as successful completion.

The deadline is cooperative. Individual Python operations, concrete replay,
or native solver slices can run beyond it before a checkpoint is reached;
there is no hard process time or memory limit. Parsing and file output are
outside the search budget. In contrast, `check --timeout` supplies a separate
budget to each checking phase. The Python `check` API optionally accepts a
shared `total_timeout` as well.

## Results and completeness

| Result | What it establishes | Exit code |
| --- | --- | --- |
| `COUNTEREXAMPLE` | A concrete model satisfies every retained axiom and falsifies the named property. | `1` if no selected property remains unknown |
| `HOLDS WITHIN SEARCH BOUNDS` | No candidate in the complete bounded frame class falsifies the property, and an axiom model exists. | `0` when every selected property holds |
| `INCONSISTENT WITHIN BOUNDS` | Every candidate was decided, and no model of the axioms exists within the bounds. No property is reported as proved. | `2` |
| `UNKNOWN` | A deadline or resource limit left part of the search unresolved. | `3` |
| `SATISFIABLE` | With no properties selected, an independently checked model of the axioms was found. | `0` |
| Invalid input | The requested search could not be performed. | `2` |

With several properties, search continues until each has a countermodel or
the bounded class is exhausted, unless a resource limit intervenes. Different
properties can have different countermodels and scopes. If some properties
have witnesses and others remain unknown, the command exits `3`; the witnesses
remain valid and are included in the report.

A countermodel is decisive as soon as it has been independently validated.
Search may therefore stop after finding a witness for every selected property
without visiting every frame. In JSON, `complete` means that the entire bounded
frame class was exhausted without unresolved checks; it can be `false` even
when every requested counterexample was found. Per-property results state
what was established. A top-level `complete` status can contain a mixture of
counterexamples and bounded successes.

No bounded success proves arbitrary domain size or natural-number-time
correctness. Temporal witnesses use the selected finite time convention;
see [the semantics reference](semantics.md) before interpreting them as claims
about an infinite execution.

## Save and replay the exact witness

For each countermodel, `--countermodels witnesses` writes three files:

| File | Contents |
| --- | --- |
| `01-Agreement.json` | Complete valuation, concrete scope, and falsifying context. |
| `01-Agreement.txt` | Readable tables of the witness. |
| `01-Agreement.md` | Standalone theory with that frame and the retained formulas. |

The numeric prefix follows the selected property order. Replay the JSON
against its generated Markdown, not against the original template's frame:

```sh
python -m muql replay witnesses/01-Agreement.md witnesses/01-Agreement.json
python -m muql check witnesses/01-Agreement.md --property Agreement
```

The generated theory already reflects axiom removals and replacements. Do not
apply the same `--drop` or `--replace` options again when replaying it. If the
search required a larger `--max-mu-contexts`, supply that limit to replay too.

Use `--json report.json` for the full search report, or `--json -` for JSON
only on standard output. Its schema is `muql-search-report-v1`; it includes
the bounds, per-property results, completion flag, resolved solver, frame
counts, timing, and the first consistency witness. With no properties, the
axiom model is in this JSON report; there are no property-countermodel files
for `--countermodels` to export.

## SAT backends

The core package uses only Python's standard library. Both backends compile
valuations to SAT rather than enumerating every three-valued assignment.
The optional PySAT backend uses native MiniSat22:

```sh
python -m pip install '.[sat]'
python -m muql search choices.md --solver pysat
```

Run the installation command from the package root, preferably in a virtual
environment. It may download dependencies. In Windows Command Prompt, use
double quotes around `.[sat]`.

`search` defaults to `--solver auto`: use PySAT when available, otherwise the
built-in solver. `check` defaults to `--solver builtin`. Both commands accept
all three choices. Explicit `--solver pysat` is an error if PySAT cannot be
loaded; automatic selection falls back to the built-in solver. Reports record
the resolved backend. Every returned witness is checked independently of
which SAT engine produced it.

The optional native dependency was not available in the release environment;
see [validation](validation.md) for the actual test coverage. No native-backend
performance claim is made.

## Python API

```python
import json
from pathlib import Path
from muql import format_theory, load, search, witness_theory

template = load("choices.md", for_search=True)
report = search(template, max_points=1, max_values=2, max_stages=1,
                timeout=30, solver="auto")

Path("search-report.json").write_text(
    json.dumps(report.to_dict(), indent=2), encoding="utf-8"
)
directory = Path("witnesses")
for result in report.properties:
    if result.countermodel is not None:
        directory.mkdir(exist_ok=True)
        stem = directory / result.name
        concrete = witness_theory(template, result.countermodel)
        stem.with_suffix(".md").write_text(format_theory(concrete), encoding="utf-8")
        stem.with_suffix(".json").write_text(
            json.dumps(result.countermodel.to_dict(), indent=2), encoding="utf-8"
        )
```

`loads(markdown, for_search=True)` accepts a template string. `search` also
accepts an ordinary scoped `Theory`; it replaces that theory's point/stage/quorum
declarations as the CLI does. `format_theory` writes expanded formulas and a
complete explicit frame; pass `notation="ascii"` for ASCII output.

By default, all declared properties are selected. Pass `properties=["Goal"]`
to select names, or `properties=[]` to request only a model of the axioms.
A template containing no `property` declarations also requests model search
from the CLI. The same bounds and budgets apply.
