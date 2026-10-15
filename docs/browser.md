# 3μQL Explorer in your browser

The browser explorer runs the same Python logic engine as the command-line
package. You can load a worked example, edit its theory, check its properties,
or ask the engine to find counterexamples within bounds. Nothing needs to be
installed on the visitor's computer.

## Open the application

After deploying 0.7.1, open
[the GitHub Pages explorer](https://bellissimogiorno.github.io/3muQL-model-checker/).
The recommended Actions deployment opens the application at that address;
the supplied branch-deployment landing page forwards automatically to `site/`.
See [GitHub setup](github.md) to publish the release. Nothing is installed on
the visitor's computer, but the browser downloads its Python runtime on first
use and computes on the visitor's device.

For local use, install the supplied wheel with Python 3.10 or later and run:

```sh
3muql serve --port 0 --open
```

`3muql` is the primary installed command; `muql` remains a compatibility alias.
`python -m muql serve --port 0 --open` is equivalent and also works directly
from the extracted source without installation. The command serves the bundled
application only on `127.0.0.1`, chooses an available port, prints the address,
and opens your default browser. Press Ctrl+C to stop. If automatic browser
opening fails, open the printed address yourself. Use `--port 8000` to request
a fixed port. This launcher needs neither Bash nor a source checkout after
installation. The default browser runtime still needs network access on first
use; the Python CLI needs no network at all.

## A four-step workflow

The explorer follows one vertical sequence on desktop and mobile. The step
navigation stays available as you scroll. Each step’s main action is a solid
blue button: **Continue to claims**, **Continue to run settings**, the **Run**
action, and **Keep exploring**. They share a generous click area and consistent
spacing, and expand to the available width on narrow screens. Keyboard focus
remains visible; following a continuation moves focus to the next section.

1. **Choose a theory.** Each visit starts at **First steps**. Selecting a curated
   example immediately loads its source and settings. **Reset example** restores
   the loaded example’s defaults. The displayed theory name identifies the source
   that will be checked. The first choice example needs no supplied model.
2. **Choose what to test.** Select properties, and expand **Assumptions** to
   remove axioms. **Continue to claims** moves directly to this section.
3. **Set the scope and run.** Choose **Search for a model** and keep the small
   default bounds initially, or **Check this frame** to use the declared frame.
   Review the theory name, selection summary, and any removed axioms beside Run.
   Extra resource limits and the optional solver are under **Advanced limits and
   solver**.
4. **Inspect the results.** Open a counterexample to explore its model diagram
   and values across time. Save a diagram, or download the concrete theory and
   valuation to replay it.

**View or edit the theory** opens the full Markdown source, with **Load theory**
and **Save theory** together in its toolbar. Load opens a Markdown file and asks
before replacing unsaved edits. The editor starts folded so the first experiment
does not require source editing. After changing
source, choose **Update choices** and review the refreshed properties and
assumptions before running. Choices are retained by name. While source changes
are pending, the main run button becomes **Update choices before finding a
counterexample** (with corresponding wording in fixed-frame or axiom-model
mode). It stays clickable and takes you directly to the visible **Update
choices** button in Claims, giving it keyboard focus. The Claims continuation
also directs you to that update, and the status message explains that choices
are out of date. After updating, review the choices and continue to the run
settings. The checker never runs against outdated choices. Errors reopen the
editor and provide a jump to the offending line.
Removed declarations disappear from the choices. If you had selected a subset
of claims, review any newly added claims explicitly. Opening a different file
or loading an example starts with that theory's own selection.
Edited theories, opened files, and restored drafts have a separate custom-source
label; the curated picker is hidden and a return to the last curated example
is available.
They do not retain a preset's description or expected-outcome hints. Loading a
preset over edited source asks before replacing it. Canceling that replacement
or a failed download leaves the previous source and its identity in place.
Changing a preset's properties, assumptions, or run settings marks it as an
adjusted experiment and clears its expected-outcome hint. **Reset example**
restores the original source, selections, and bounds. The loaded theory's
predicate names and arities are visible above the source editor.

Undoing edits back to a curated example's exact original source restores its
picker, description, and place in the tour automatically. It preserves your
selected claims, removed assumptions, and run settings. Previously read choices
can be restored immediately for that exact source; any changed settings keep
the example marked as adjusted. Undo does not turn previous-run evidence into
a new result. Opening an independent custom file does not give it a preset's
identity merely because the text happens to match.

Syntax highlighting is on by default. Markdown headings, links, and code are
colored alongside declarations, operators, strings, and comments inside
`muql` blocks. Unicode and ASCII formulas receive the same treatment. Use
**Highlight syntax** above the editor to turn colors off or on; your preference
is saved with the draft. Text selection, copy and paste, and undo remain the
browser’s ordinary editing controls, and saved files contain the exact source.
Coloring is a reading aid; **Update choices** still checks the theory. During
input composition, in forced-color modes, or for unusually large source, the
editor uses readable plain text.

The compact symbol toolbar is attached to the top of the Markdown editor and
stays visible while the editor is open. Symbols flow in closely spaced rows;
touch devices retain larger tap targets. Its 24 symbols cover logic, value quantifiers
(including unique `∃¹` and affine `∃⁰¹` existence), point and quorum modalities,
and fixed points. Each button shows its name and ASCII spelling on hover or
focus. Click or tap to insert at the cursor, replacing any selected text.
With a keyboard, use Shift+Tab from the editor to enter the toolbar, Left/Right
to browse, Home/End to reach its ends, and Enter or Space to insert. Tab returns
to the editor. Insertion returns focus to the source and requires **Update
choices**, just like typing.

The explorer and theory reader share a small, consistent type scale. At the
standard browser setting, body text and controls are 16px, supporting text is
14px, formulas and minor headings are 18px, section headings are 24px, and page
titles are 32–40px. These sizes follow the browser’s default text size. Narrow
screens reflow the controls instead of reducing the text.

The first example is a standalone uniqueness tutorial, with a `chosen` predicate
and one correctness axiom. It finds two chosen values, disproving uniqueness;
it is not a Paxos theory. Next, compare
**Voting** with its version without `Correct`, or compare the Simpler Paxos
examples with and without write uniqueness. After each run, **Keep exploring**
loads the next curated example. The tour visits all eleven presets in picker
order, ending with **Crusader agreement**. Its final continuation opens
**Custom experiment — create your own theory**, a separate subsection after
Results. Create a starter theory, load your own Markdown file, or restore your
saved draft there. **Save theory** sits beside **Load theory** and downloads
the source currently open in the editor. **Reset to last example** returns to
the last curated example you visited, restoring its source and default settings.
It asks before replacing unsaved edits and preserves the custom draft for later
restoration. The button remains available if you adjust
claims, assumptions, or bounds while keeping the example’s source unchanged.

Theory files, displayed formulas, the symbol toolbar, and the theory reader use
a real Unicode superscript Q in quorum quantifiers: `∃ꟴ`, `∀ꟴ`, `∃ꟴ◇`, and so on.
Copying, saving, and inserting symbols preserve this spelling. The explorer and
offline reader include the glyph so it also displays on systems whose fonts
lack it. The editable Markdown remains literal text, preserving cursor alignment
and selection. Quoted values keep their literal appearance. Plain-Q `∃Q` / `∀Q`
and ASCII names remain accepted for convenient typing.

The examples accept Unicode and ASCII. Strong implication is `⇀` or `-\`;
`=>` is not an alias. Keep a downloaded copy of edits you want to retain.
The first visit downloads Python when the example is read. Stop remains
available during loading and calculation, and does not discard the open theory.

## Check or search?

| Mode | What you provide | What the result covers |
| --- | --- | --- |
| Search for a model | A theory, selected properties, and search bounds | Generated frames and their valuations within those bounds |
| Check this frame | A theory with declared participants, values, stages, and quorums | Every permitted valuation on that fixed frame |

Neither mode requires you to assign predicate truth values by hand. Search
additionally chooses the frame. In search mode the theory's declared frame is
replaced by generated frames; its named values and temporal convention still
constrain the search. The bounds, quorum restrictions, and resource limits
shown with the result are part of its meaning.

**Search up to** sets the maximum number of participants, values, and time
stages in generated frames. These bounds apply to **Search for a model**:
smaller frames are tried first, so increasing a maximum need not change the
model found. Named values and the theory's temporal convention are retained.

In **Check this frame**, these inputs stay visible but are greyed out; the
declared frame's sizes are shown instead. **Quorums per frame** and **Frames
to try** are also disabled in this mode. Time, compilation, and solver limits
apply to both modes. Switching back to search restores its bounds, including
after a saved draft is reopened.
The declared-frame note counts **quorum generators**; their unions are also
quorums. Results show the complete family actually used for the check.

Use the axiom controls to experiment with assumptions. A cleared axiom is
removed from that run; the original example text is available to load again.
Select only the properties you want to investigate, especially for larger
theories. The summary above Run identifies the theory, shows how many properties
and axioms are selected, and names removed axioms. The assumptions open
automatically when a loaded example or reread source has exclusions. With no
properties selected, the run seeks an axiom model. Start
with the supplied bounds and increase them gradually.

### Read the result carefully

- **Counterexample:** a concrete finite model satisfies the retained axioms
  and falsifies the property. Inspect the failing context and valuation, then
  download it if you want to reproduce the result.
- **Holds in scope / within bounds:** no counterexample exists in the stated
  fixed frame or completed bounded search. This is not a proof for arbitrary
  model sizes.
- **Inconsistent:** no model in the completed scope or bounded class satisfies
  the retained axioms. A property holding vacuously is not evidence that the
  intended system has a model.
- **Incomplete:** a time or complexity limit was reached. The unfinished
  search does not establish that the property holds. A counterexample already
  found remains useful if it was returned and validated before the limit.

Each displayed property has its own result. A search can find a counterexample
to one property without resolving all the others. Each counterexample card has
its own model; different cards can have different frames and truth values.

Changing the source, example, selected claims, assumptions, or run settings moves
the existing evidence into a closed **Previous run** disclosure. Current results
remain empty until you run again. Open that disclosure to inspect or download the
previous experiment: its theory, settings, and downloads remain the ones used for
that run. Changing a diagram's stage, atom, or highlighted quorum only changes
its view, so it does not make that result out of date.

## Explore a counterexample

Open a counterexample to **Explore this model**. A model contains its entire
finite frame—participants, value domain, stages, and quorum family—together
with every atom's truth value at every participant and stage. **Whole model**
shows those totals. The diagram and linked tables are views of that model;
changing their controls does not change the model or run another search.

**Full model data**, beside the totals, opens the complete scope and atomic
valuation below. This panel is independent of the diagram's controls. Its
valuation table is paginated, but all recorded rows are available. The complete
valuation is also included in the countermodel JSON download.

The diagram is titled **View at stage N**: it shows one stage and highlights
one quorum. The coverage line gives the selected stage and quorum counts,
participant range, and number or range of atoms shown. Initially, it opens at
the recorded failure's stage and quorum, with the failing participant in view.
Each participant card shows named atoms and their truth values together, up to
twelve atoms per page. Both chosen values in the choice example, and all nine
atoms in the small Simpler Paxos search example, fit in the initial view.
The dashed outline marks the context where the property evaluates to `f`.
That participant can lie outside the highlighted quorum: the logic permits
such contexts.

The highlighted quorum is shown prominently as a set, **Q = {…}**, above the
diagram and inside its SVG. Participant cards say **In Q** or **Outside Q**;
membership lines connect Q to its displayed members. The text above the image
lists every member, and the page notes how many members are outside the current
participant page. Long sets in the SVG are visibly abbreviated; its accessible
description retains the full list. These lines express membership, not messages
between participants. Changing the highlighted quorum changes these lines and
labels, while the atomic truth values stay the same: an atom's value depends
on its participant and stage, not on the quorum used to evaluate a formula.

Use the three labelled controls to explore:

- **Stage** chooses a recorded time. For models with several stages, use
  **Previous stage** or **Next stage**.
- **Atoms shown** starts with **All atoms**, or **All atoms (paged)** when there
  are more than twelve. Choose a predicate and its arguments, such as
  `decide(red)`, to focus on that atom. Its name and `t` (true), `b` (broken), or
  `f` (false) value appear in every participant card. The middle value's
  interpretation depends on the theory. The property failure marker remains
  separate from atomic values.
- **Quorum highlighted** selects from every quorum in the recorded model.
  The prominent set and participant membership labels update with this choice.

The Stage and Quorum highlighted selectors are disabled when the model has only
one stage or quorum. A model of the axioms has the same exploration controls
without a property-failure marker.

**Atom values at stage N** compares the current page of atoms for the displayed
participants. It states its stage, participant range, and atom range separately:
when the diagram focuses on one atom, this table still lists the current atom
page. In the choice example, two chosen values are both marked `t`, explaining
the failure of `AtMostOne`. Select an atom name to focus the diagram on it.
Larger atom sets have twelve rows per page. Atom page controls remain visible
when the table is closed and change both the diagram's overview and the table.
Choose **All atoms** or **All atoms (paged)** to return to the overview.

**Selected atom across time** appears when an individual atom is selected in a
model with more than one stage. It shows that atom's values for the displayed
participants, with an explicit stage range; it is not the whole model. Select
a column heading to move the diagram to that stage. For longer histories,
choosing a stage above moves to the corresponding range of the time table.

**Return to failing context** restores the recorded stage, quorum, and
participant page while keeping your chosen atom. The temporal convention is
shown below the diagram: in **finite** time the last stage has no successor;
in **stutter** time its successor is itself. These are the package's finite
frame conventions, with the past-history limitations described in
[semantics](semantics.md).

**Download this view (SVG)**, below the diagram and paging controls, saves
only the displayed atoms, stage, highlighted quorum, and participant page,
including a text description. Use the countermodel JSON and its concrete
theory for the complete model and replayable evidence.

Each diagram loads when its witness opens; the full valuation loads when its
own panel opens. Larger models use participant pages, stage ranges, an atom
filter, and table pagination; range labels show which entries are visible.
Controls work with a keyboard. Truth values have letters and names as well as
colors, the diagram has a text description, and the time grid is a labelled
table. Layouts adapt to narrow screens and enlarged text.

Similar diagrams do not necessarily mean the result is unchanged. Search tries
small frames first, so different counterexamples can share one participant and
one quorum. Their named atomic values distinguish the models. Increasing an
upper bound permits larger frames but does not force search to use one; choose
**Check this frame** to use the points, values, stages, and quorums declared
in the theory.

## Stop, revise, and run again

**Stop** immediately ends the background worker. Your theory stays in the
editor, and you can change the bounds or assumptions and run again. Stopping
does not produce a completed report or prove any property. Starting again
after a stop recreates Python; cached downloads may make this faster.

Time budgets and complexity bounds keep experiments manageable. They are
limits, not promises that a search will finish. A larger participant bound
can generate many quorum families, and higher bounds can quickly exceed a
phone's available memory or a comfortable waiting time. Small defaults are
intentional. A hard browser stop may end the worker before a partial report
can be returned.

The page allows up to 6 participants, 8 values, 12 stages, 64 quorums per
frame, 5,000 frames, and 120 seconds per run. Additional compilation and solver
limits are available under **Advanced limits and solver**. These are browser
interface caps, not recommended starting sizes; the Python interface supports
larger experiments. The ordinary exact recurrence limit is eight contexts.
If a declared scope exceeds a browser cap, guidance beside the mode controls
explains why Run is unavailable. An oversized frame can be searched at smaller
sizes; a domain with more than eight declared values needs the Python package
or a smaller declared domain, because search retains those distinct values.
The timer starts after loading, with one additional second for report
serialization before a hard worker stop; startup has a separate 90-second
limit. Browser memory remains limited by the device, not a fixed allocation.

The interface uses labelled native controls, keyboard navigation, visible
focus, text as well as color for results, and announcements for execution
status. Controls and result panels adapt to narrow screens. The full theory
reader is available separately when you want to read the bundled axioms and
properties without running them.

## Save and reproduce an experiment

Download your theory before replacing it with another example. The full report
JSON records the results and, for a search, the search bounds. The retained
theory download records the assumptions used in that run. For each
counterexample, save both the generated witness theory (`.md`) and its
countermodel (`.json`).
The generated theory contains the actual finite scope and retained axioms,
so it can be checked independently with the ordinary Python package:

```sh
python -m muql replay witness.md countermodel.json
```

The filenames above are placeholders for your downloaded pair. For a new
check of the witness's scope, run:

```sh
python -m muql check witness.md
```

Opening your witness theory in the browser and selecting **Check this frame** also checks
the generated scope. This starts a new check; the command-line `replay`
operation independently validates the exact downloaded valuation.
The diagram's SVG is a shareable view of the selected context; replay uses the
JSON valuation and Markdown theory.

## Data and first-load requirements

Theory parsing, checking, and search run in the browser. The application does
not send the theory or its results to a solver server. The hosting provider
serves the page and examples, and the first run downloads the pinned Pyodide
Python runtime, version **314.0.7**, from jsDelivr. Those ordinary network requests are still
visible to the relevant hosting providers.

The default distribution needs an internet connection for the first load.
Browser caching may help on later visits, but it does not guarantee offline
availability. A separately bundled runtime can support offline use over local
HTTP; see [runtime hosting](#runtime-hosting-and-offline-use) below.
There is no service worker and no account or server-side experiment store.
The default built-in SAT solver requires no additional package download.
MiniSat is an optional solver choice that downloads Pyodide's `python-sat`
package and checks its bounded solver API before use. If it cannot be loaded,
the interface asks you to choose the built-in solver; it does not silently
change the requested solver.

When local storage is available, custom source and its settings are saved as a
draft in this browser. Each visit starts at First steps; use **Restore saved
draft** in the custom-experiment section to resume your work. Browsing curated
examples does not overwrite that saved draft. Downloads remain the reliable
way to keep a separate copy. Recent edits are also saved when the page becomes
hidden or is left. Drafts are kept separately for each application path within
the browser origin (scheme, host and port). To reuse a local draft across
launches, use a fixed port, such as `3muql serve --port 8000 --open`, and the
same address. `--port 0` may choose a different origin on the next launch.
Existing drafts from older versions remain available at their original origin.

If another tab changes the saved draft, your open work is kept in a separate
**Recovery copies** entry in the custom section. Restore a copy with its settings,
or use **Save recovery theory** to download its source. Up to 20 separate copies
are kept; if storage fills or saving fails, use **Save theory** for your open work.
An unchanged older tab does not overwrite a newer saved draft when hidden or closed.
**Forget saved draft**, under the page's help section, removes this page's draft
and recovery copies and turns off saving for that visit.

Importing a file or loading an example does not upload your theory. Results
are not saved between visits; rerun the restored draft or use saved downloads.

## Publish on GitHub Pages

The source release supplies two supported routes:

| Pages source | Result at the project URL | Files used |
| --- | --- | --- |
| **GitHub Actions** — recommended | Application opens at the project root | Fresh build from `.github/workflows/pages.yml` |
| **Deploy from a branch**, `main`, `/ (root)` | Automatically forwards to `site/` | Supplied `index.html`, `.nojekyll`, and `site/` |

For the recommended route, choose **Settings → Pages → GitHub Actions** and
run **Actions → Deploy explorer → Run workflow**. The workflow builds the site
and requires real Chromium/Pyodide checks under a project prefix before
publishing, including the built-in and native solver paths. The release package
does not update a live repository. Follow [GitHub setup](github.md) for exact
upload instructions, both publication modes, and README-page troubleshooting.

## Develop and preview from source

Use Bash and Python 3.10 or later:

```sh
bash serve.sh
bash serve.sh --python python --port 0 --open
```

The Bash launcher uses `python3` by default; `--python` selects another
interpreter and takes precedence over the `PYTHON` environment variable.
It works from another directory when given the path to `serve.sh`. Each start
rebuilds `dist/site` before serving it, so this is useful while editing `web/`
or the Python engine. Restart after edits. It binds only to your computer and
disables browser caching for preview responses. Press Ctrl+C to stop.

By contrast, `python -m muql serve` serves `muql/_site.zip`, the packaged
snapshot. After source changes, regenerate that snapshot using
`python tools/build_release.py --prepare-only`. Open an HTTP address rather
than double-clicking `index.html`; the application fetches its configuration,
examples, and engine through HTTP.

## How the site is built

`python tools/build_site.py` uses only Python's standard library and downloads
nothing. It copies `web/`, examples, documentation, and the theory reader into
`dist/site`; bundles the Python engine into `engine.zip`; and writes
`config.json` with the release version, relative asset paths, and pinned
runtime URL. The same relative URLs work under a GitHub project prefix or on
another static HTTP host.

```sh
python tools/build_site.py --output dist/site
python tools/build_site.py --output dist/site --check
```

`--check` compares an existing output with a fresh build without modifying it;
use the same runtime options as the original build. Inside this repository,
choose an output directory under `dist/`. The builder replaces only empty
directories or its own marked output, and removes obsolete generated assets.
`tools/build_release.py --prepare-only` manages the tracked release snapshots
in `site/` and `muql/_site.zip`, plus the root landing page. Its `--check` option
checks that these agree with the current source.

The standalone `3muql-explorer-site-0.7.1.zip` contains the deployable static
application. Extract it, then serve the directory containing `index.html`:

```sh
python -m http.server 8000 --bind 127.0.0.1 --directory /path/to/extracted-site
```

Python executes in a module Web Worker. The main page renders controls and
results; terminating the worker implements cancellation without special
cross-origin isolation headers. The shared Python engine is also used by the
CLI; a local HTTP server only serves files and does not perform model checking.
See [the language guide](language.md), [semantics](semantics.md), and
[bounded search](search.md) for the mathematical behavior.

## Runtime hosting and offline use

The default runtime is pinned to **Pyodide 314.0.7** at
`https://cdn.jsdelivr.net/pyodide/v314.0.7/full/`. No Python runtime is embedded
in the default release, and no service worker promises offline availability.
All custom runtime locations must provide the same compatible runtime.

To use an HTTPS mirror or a runtime already served beside the application:

```sh
python tools/build_site.py --output dist/mirrored-site --pyodide-url https://YOUR-HOST/pyodide/v314.0.7/full/
python tools/build_site.py --output dist/relative-site --pyodide-url runtime/pyodide/
```

The second command configures a relative URL only; place the runtime files at
that location before serving the site. HTTPS mirrors must allow cross-origin
browser requests when served on another origin. Changing the URL does not
make missing runtime files available or verify an arbitrary mirror's behavior.

To include a local copy of the runtime in the build:

```sh
python tools/build_site.py --output dist/offline-site --pyodide-dir /path/to/pyodide-314.0.7/full
python tools/build_site.py --output dist/offline-site --pyodide-dir /path/to/pyodide-314.0.7/full --check
python -m http.server 8000 --bind 127.0.0.1 --directory dist/offline-site
```

Supply the complete runtime directory, including its module loaders, WebAssembly
binary, standard-library archive, and `pyodide-lock.json`. The builder copies it
into `runtime/pyodide/` and checks the pinned version. The built-in solver can
then run from a fresh browser session without internet access, provided the
local runtime is complete and the site is served over HTTP. Optional MiniSat
also requires the matching `python-sat` wheel and its dependency wheels in the
runtime directory. Keep the runtime's accompanying license files with a
redistributed copy. Bundling is opt-in because the runtime is much larger than
the explorer itself.

These commands produce a separate site; they do not silently replace the
runtime configuration of the shipped wheel or tracked default `site/`.
Consult [release validation](validation.md) for whether actual browser runtime
execution was possible in the release environment. Structural runtime checks
and mocked worker tests alone cannot establish WebAssembly execution.

## Platform references

- [GitHub: custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Pyodide: deploying the runtime](https://pyodide.org/en/stable/usage/downloading-and-deploying.html)
- [Pyodide: running Python in a worker](https://pyodide.org/en/stable/usage/webworker.html)
