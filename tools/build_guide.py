#!/usr/bin/env python3
"""Regenerate docs/theories.html from the executable examples, without dependencies.

Run ``python tools/build_guide.py`` from the package root. No model-checking
results are inferred or cached here: this is a reader for the parsed theories.
"""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from muql.syntax import format_formula, parse_formula  # noqa: E402
from muql.theory import _blocks, _checked_expand, _DECLARATION, _LABEL, load  # noqa: E402


GROUPS = (
    ("Foundations", ("basics", "semitopology", "fixedpoints")),
    ("Simple protocols", ("simple_reliable", "simple_crashes", "simple_eventual", "simple_eventual_crashes")),
    ("Quorums & agreement", ("voting", "bracha", "bracha_weakened", "crusader")),
    ("Paxos", ("paxos", "paxos_simpler")),
)

SHORT_NAMES = {
    "basics": "Three-valued logic", "semitopology": "Semitopology", "fixedpoints": "Fixed points",
    "simple_reliable": "Reliable delivery", "simple_crashes": "Reliable, with crashes",
    "simple_eventual": "Eventual delivery", "simple_eventual_crashes": "Eventual, with crashes",
    "voting": "Voting", "bracha": "Bracha broadcast", "bracha_weakened": "Bracha: delivery weakening",
    "crusader": "Crusader agreement", "paxos": "Declarative Paxos", "paxos_simpler": "Simpler Paxos",
}

LEGEND = (
    ("¬", "!", "Negation"), ("∧", "&", "Conjunction"), ("∨", "|", "Disjunction"),
    ("⊕", "xor", "Exclusive or"), ("→", "->", "Weak implication"),
    ("⇀", "-\\", "Strong implication"), ("≡", "<=>", "Equivalence"),
    ("≤", "<=", "Truth order"), ("= / ≠", "== / !=", "Value equality / inequality"),
    ("∀ / ∃", "forall / exists", "Value quantification"),
    ("∃⁰¹ / ∃¹", "affine / unique", "Affine / unique quantification"),
    ("μ / ν", "mu / nu", "Fixed-point binders"),
    ("◇", "diamond / somewhere", "Some point in the current quorum"),
    ("□", "box / everywhere", "Every point in the current quorum"),
    ("∃ꟴ / ∀ꟴ", "existsQ / forallQ", "Quorum quantification"),
    ("∃ꟴ□", "quorum / someQuorumEveryPoint", "Some quorum, every point"),
    ("∀ꟴ◇", "contra / everyQuorumSomePoint", "Every quorum, some point"),
    ("∃ꟴ◇", "someQuorumSomePoint", "Some quorum, some point"),
    ("∀ꟴ□", "everyQuorumEveryPoint", "Every quorum, every point"),
)


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def formula_html(text: str) -> str:
    """Typeset quorum operators without changing copied or executable text.

    Keep this small presentation scan in step with web/notation.js. Quoted
    values and comments are opaque: their contents are not logical operators.
    Every source character is escaped before trusted presentation markup is
    introduced; the source itself is never interpreted as HTML.
    """
    parts, offset = [], 0
    while offset < len(text):
        start = offset
        character = text[offset]
        if character in "\"'":
            quote_character = character
            offset += 1
            while offset < len(text):
                if text[offset] == "\\":
                    offset = min(len(text), offset + 2)
                elif text[offset] == quote_character:
                    offset += 1
                    break
                else:
                    offset += 1
            parts.append(escape(text[start:offset]))
        elif character == "#" or text.startswith("//", offset):
            while offset < len(text) and text[offset] not in "\r\n":
                offset += 1
            parts.append(escape(text[start:offset]))
        elif character in "∃∀" and text[offset + 1:offset + 2] in {"Q", "ꟴ"}:
            mark = '<sup class="quorum-mark">Q</sup>' if text[offset + 1] == "Q" else "ꟴ"
            parts.append(f'<span class="quorum-quantifier">{character}{mark}</span>')
            offset += 2
        else:
            parts.append(escape(character))
            offset += 1
    return "".join(parts)


def intro_html(markdown: str) -> str:
    """Render introductory paragraphs as escaped text, with safe inline markup.

    This intentionally is not a general Markdown renderer. The linked original
    contains the entire commentary. HTML and unsupported Markdown stay text.
    """
    introductory = re.split(r"^ {0,3}(?:`{3,}|~{3,})", markdown, maxsplit=1, flags=re.M)[0]
    introductory = re.sub(r"^# [^\n]*\n?", "", introductory)
    token = re.compile(r"`([^`]+)`|\[([^\]]+)\]\(([^\s)]+)\)|\*\*([^*]+)\*\*")

    def inline(text: str) -> str:
        parts, end = [], 0
        for match in token.finditer(text):
            parts.append(escape(text[end:match.start()]))
            code, label, url, strong = match.groups()
            if code is not None:
                parts.append(f"<code>{formula_html(code)}</code>")
            elif strong is not None:
                parts.append(f"<strong>{escape(strong)}</strong>")
            elif url is not None and (url.startswith(("https://", "http://", "#")) or not re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", url)) and not url.startswith("//"):
                if not url.startswith(("https://", "http://", "#")):
                    url = "../examples/" + url
                parts.append(f'<a href="{escape(url)}">{escape(label)}</a>')
            else:
                parts.append(escape(match.group()))
            end = match.end()
        parts.append(escape(text[end:]))
        return "".join(parts)

    return "\n".join(f"<p>{inline(' '.join(paragraph.splitlines()))}</p>" for paragraph in re.split(r"\n\s*\n", introductory.strip()) if paragraph.strip())


def source_formulas(markdown: str, theory) -> dict[str, dict]:
    """Keep the author's macro references, checking them against loaded formulas.

    Reuse the loader's fence/comment scanner, then group declarations without
    interpreting them a second time. ``load`` has already validated the entire
    source. Comparing expansions guards against accidental display drift.
    """
    declarations = []
    pending = []
    for row, _ in _blocks(markdown, theory.source):
        if not row.strip():
            continue
        if _DECLARATION.match(row.strip()):
            if pending:
                declarations.append("\n".join(pending))
            pending = [row.strip()]
        else:
            pending.append(row)
    if pending:
        declarations.append("\n".join(pending))
    result = {"axiom": {}, "property": {}}
    for declaration in declarations:
        match = re.fullmatch(rf"(axiom|property)\s+({_LABEL})\s*:\s*(.*)", declaration, re.S)
        if match:
            kind, label, text = match.groups()
            node = parse_formula(text)
            loaded = theory.axioms if kind == "axiom" else theory.properties
            if _checked_expand(node, theory, theory.locations[label]) != loaded[label]:
                raise ValueError(f"source and loaded formula differ: {kind} {label}")
            result[kind][label] = node
    if result["axiom"].keys() != theory.axioms.keys() or result["property"].keys() != theory.properties.keys():
        raise ValueError(f"source formula labels differ from the loaded theory: {theory.name}")
    return result


def build() -> tuple[str, int]:
    entries, navigation, articles, formula_data = [], [], [], []
    expected = {stem for _, stems in GROUPS for stem in stems}
    actual = {path.stem for path in (ROOT / "examples").glob("*.md")}
    if expected != actual:
        raise ValueError(f"update GROUPS for the current examples: missing={actual - expected}, absent={expected - actual}")

    def rows(formulas: dict, kind: str) -> str:
        rendered = []
        for label, node in formulas.items():
            forms = {notation: format_formula(node, notation=notation) for notation in ("unicode", "ascii")}
            for notation, text in forms.items():
                if parse_formula(text) != node:
                    raise ValueError(f"{kind} {label} does not round-trip in {notation}")
            index = len(formula_data)
            formula_data.append(forms)
            rendered.append(f'<div class="formula-row"><span class="formula-label">{escape(label)}</span><div class="formula" data-formula="{index}">{formula_html(forms["unicode"])}</div></div>')
        return "\n".join(rendered) or '<p class="empty-group">No axioms are declared; these properties explore the logic directly.</p>'

    for group, stems in GROUPS:
        links = []
        for stem in stems:
            path = ROOT / "examples" / f"{stem}.md"
            theory = load(path)
            markdown = path.read_text(encoding="utf-8")
            originals = source_formulas(markdown, theory)
            definitions = {f"{name}({', '.join(macro.parameters)})": macro.body for name, macro in theory._macros.items()}
            definition_rows = rows(definitions, "definition") if definitions else ""
            definition_section = (f'<section class="formula-group definitions" aria-labelledby="definitions-{stem}"><div class="group-title"><h3 id="definitions-{stem}">Definitions</h3><span>{len(definitions)}</span></div><p class="definition-note">Named abbreviations used below. The checker expands each definition before checking the theory.</p>{definition_rows}</section>' if definitions else "")
            axiom_rows, property_rows = rows(originals["axiom"], "axiom"), rows(originals["property"], "property")
            entries.append({"id": stem, "search": " ".join((group, theory.name, stem, markdown, " ".join(theory.axioms), " ".join(theory.properties), " ".join(format_formula(node, notation="ascii") for node in (*definitions.values(), *originals["axiom"].values(), *originals["property"].values())))).casefold()})
            links.append(f'<a class="theory-link" href="#{stem}" data-theory="{stem}"><span>{escape(SHORT_NAMES[stem])}</span><span class="nav-count">{len(theory.axioms) + len(theory.properties)}</span></a>')
            time_explanation = ("The final stage repeats in the declared stuttering frame." if theory.time == "stutter" else "Time ends at the final stage in the declared finite frame.")
            predicates = ", ".join(f"{name}/{arity}" for name, arity in theory.predicates.items())
            quorums = " · ".join("{" + ", ".join(q) + "}" for q in theory.quorums)
            first = " is-active" if len(articles) == 0 else ""
            articles.append(f'''<article class="theory{first}" id="{stem}" aria-labelledby="title-{stem}">
<div class="eyebrow">{escape(group)}<span class="source-tag">{escape(stem)}.md</span></div>
<h2 id="title-{stem}">{escape(theory.name)}</h2>
<div class="intro">{intro_html(markdown)}</div>
<a class="source-link" href="../examples/{stem}.md">Read the complete literate source <span aria-hidden="true">↗</span></a>
<div class="scope-grid" aria-label="Declared scope">
<div><span class="scope-value">{len(theory.points)}</span><span class="scope-label">participants</span></div>
<div><span class="scope-value">{len(theory.values)}</span><span class="scope-label">values</span></div>
<div><span class="scope-value">{theory.stages}</span><span class="scope-label">stages · {escape(theory.time)}</span></div>
<div><span class="scope-value">{len(theory.quorums)}</span><span class="scope-label">declared quorums</span></div>
</div>
<details class="frame"><summary>Inspect the declared frame</summary><dl>
<dt>Participants</dt><dd>{escape(', '.join(theory.points))}</dd>
<dt>Values</dt><dd>{escape(', '.join(theory.values))}</dd>
<dt>Quorums</dt><dd>{escape(quorums)}</dd>
<dt>Predicates</dt><dd>{escape(predicates)}</dd>
<dt>Time</dt><dd>{escape(time_explanation)}</dd>
</dl><p>The checker takes the union closure of the declared quorums. See <a href="semantics.md">the semantics reference</a> for the frame interpretation.</p></details>
{definition_section}
<section class="formula-group" aria-labelledby="axioms-{stem}"><div class="group-title"><h3 id="axioms-{stem}">Axioms</h3><span>{len(theory.axioms)}</span></div>{axiom_rows}</section>
<section class="formula-group properties" aria-labelledby="properties-{stem}"><div class="group-title"><h3 id="properties-{stem}">Properties to check</h3><span>{len(theory.properties)}</span></div>{property_rows}</section>
<section class="run-box" aria-label="Run this theory"><span class="eyebrow">Explore this theory</span><p class="run-intro">This page is an offline reader. Run either command from the package directory to check the formulas.</p>
<div class="run-options">
<div class="run-option"><h4>Check declared frame</h4><code>python -m muql check examples/{stem}.md</code><p>Use exactly the participants, values, stages, and quorum generators declared above.</p></div>
<div class="run-option"><h4>Search for countermodels</h4><code>python -m muql search examples/{stem}.md</code><p>Vary finite frames automatically, keeping the named values and time convention. Defaults: up to 3 participants, {max(2, len(theory.values))} values, 3 stages, and 8 nonempty quorums.</p></div>
</div><p class="run-footer">Automatic search has a 30-second total budget and a 1,000-frame limit by default. <a href="search.md">Choose bounds and save countermodels <span aria-hidden="true">↗</span></a></p></section>
</article>''')
        navigation.append(f'<section class="nav-group"><h3>{escape(group)}</h3>{"".join(links)}</section>')

    legend = "\n".join(f"<tr><td class=\"symbol\">{formula_html(symbol)}</td><td><code>{escape(ascii_symbol)}</code></td><td>{escape(label)}</td></tr>" for symbol, ascii_symbol, label in LEGEND)
    data = json.dumps({"theories": entries, "formulas": formula_data}, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    # Keep the reader self-contained while sharing the explorer's exact icon.
    icon = "data:image/svg+xml," + quote((ROOT / "web" / "icon.svg").read_text(encoding="utf-8"), safe="")
    notation_script = (ROOT / "web" / "notation.js").read_text(encoding="utf-8").replace("export function formulaHTML(", "function formulaHTML(", 1)
    notation_css = (ROOT / "web" / "notation.css").read_text(encoding="utf-8")
    quorum_font = base64.b64encode((ROOT / "web" / "quorum-superscript.woff").read_bytes()).decode("ascii")
    notation_css = notation_css.replace('url("quorum-superscript.woff")', f'url("data:font/woff;base64,{quorum_font}")')
    document = TEMPLATE.replace("@@NAVIGATION@@", "\n".join(navigation)).replace("@@ARTICLES@@", "\n".join(articles)).replace("@@LEGEND@@", legend).replace("@@DATA@@", data).replace("@@COUNT@@", str(len(entries))).replace("@@ICON@@", icon).replace("@@NOTATION_CSS@@", notation_css).replace("@@NOTATION_SCRIPT@@", notation_script)
    return document, len(entries)


TEMPLATE = r'''<!doctype html>
<!-- Generated by python tools/build_guide.py. Edit the generator or examples, then regenerate. -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>Theory guide · 3μQL Explorer</title>
<link rel="icon" type="image/svg+xml" href="@@ICON@@">
<style>
@@NOTATION_CSS@@
:root {
  color-scheme: light;
  --paper: #ffffff; --ink: #192435; --muted: #536278;
  --blue: #2457d6; --blue-dark: #1744b5; --wash: #f5f8fd;
  --line: #e0e6ef; --input-line: #8594a9; --soft-blue: #edf3ff;
  --math: "MuQL Quorum", "Cambria Math", "STIX Two Math", "DejaVu Serif", Georgia, serif;
  --sans: "MuQL Quorum", Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --mono: "MuQL Quorum", ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  --text-small: .875rem;
  --text-body: 1rem;
  --text-lead: 1.125rem;
  --text-section: 1.5rem;
  --text-title: clamp(2rem, 4vw, 2.5rem);
  --text-math: 1.125rem;
  font-size: 100%;
  font-family: var(--sans);
  line-height: 1.6;
}
* { box-sizing: border-box; }
html { scroll-padding-top: 24px; }
body { margin: 0; font-size: var(--text-body); color: var(--ink); background: var(--paper); }
a { color: var(--blue); text-decoration-thickness: 1px; text-underline-offset: 4px; }
a:hover { color: var(--blue-dark); }
button, input { font: inherit; font-size: var(--text-body); line-height: 1.5; max-width: 100%; }
button, input, a, summary { touch-action: manipulation; }
button, summary { cursor: pointer; }
:focus-visible { outline: 3px solid var(--blue); outline-offset: 4px; }
code { font-family: var(--mono); font-size: inherit; overflow-wrap: anywhere; }
h1, h2, h3, h4 { line-height: 1.2; }
.skip-link { position: fixed; top: -90px; left: 16px; z-index: 10; padding: 12px 20px; background: white; }
.skip-link:focus { top: 12px; }
.site-header, .masthead, .layout { width: min(1080px, calc(100% - 80px)); margin-inline: auto; }
.site-header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px 24px; min-height: 90px; padding-block: 16px; border-bottom: 1px solid var(--line); }
.brand { line-height: 1.5; display: inline-flex; align-items: center; gap: 10px; font-size: var(--text-lead); font-weight: 700; white-space: nowrap; }
.brand strong { font-weight: 400; }
.brand-mark { display: grid; place-items: center; flex: none; width: 2.625rem; height: 2.625rem; border-radius: .5625rem; background: var(--blue); color: white; font-family: Georgia, serif; font-size: 1.8rem; line-height: 1; padding-bottom: .1875rem; }
.site-header nav { display: flex; flex-wrap: wrap; align-items: center; gap: 0 24px; font-size: var(--text-small); line-height: 1.5; }
.site-header nav a { display: inline-flex; align-items: center; min-height: 44px; color: var(--muted); text-decoration: none; }
.site-header nav a:hover { color: var(--blue); text-decoration: underline; }
.masthead { padding-block: 48px 36px; border-bottom: 1px solid var(--line); }
.masthead-inner { display: flex; justify-content: space-between; align-items: center; gap: 40px; }
h1 { font-size: var(--text-title); font-weight: 600; line-height: 1.2; letter-spacing: -.035em; margin: 0 0 14px; }
.masthead p { max-width: 680px; margin: 0; color: var(--muted); }
.truth-key { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; min-width: 220px; max-width: 300px; }
.truth-key span { border: 1px solid var(--line); border-radius: 6px; background: var(--wash); padding: 6px 10px; font-size: var(--text-small); white-space: nowrap; }
.truth-key b { font: 600 var(--text-body)/1.5 var(--mono); margin-right: 5px; }
.truth-note { flex-basis: 100%; text-align: right; font-size: var(--text-small); color: var(--muted); }
.layout { display: grid; grid-template-columns: 228px minmax(0, 1fr); gap: 40px; }
.sidebar { padding: 30px 7px; margin-inline: -7px; position: sticky; top: 0; max-height: 100vh; overflow: auto; align-self: start; }
.search-label { display: block; line-height: 1.5; font-size: var(--text-body); font-weight: 600; margin-bottom: 8px; }
.search { width: 100%; min-height: 46px; border: 1px solid var(--input-line); border-radius: 7px; padding: 10px 12px; background: white; color: var(--ink); font-size: var(--text-body); }
.search::placeholder { color: var(--muted); }
.search-status { color: var(--muted); font-size: var(--text-small); margin: 8px 0 24px; min-height: 20px; }
.nav-group { margin: 0 0 20px; }
.nav-group h3 { font-size: var(--text-small); font-weight: 600; color: var(--muted); margin: 0 10px 6px; }
.theory-link { display: flex; gap: 10px; align-items: center; justify-content: space-between; min-height: 44px; padding: 10px; border-radius: 6px; text-decoration: none; font-size: var(--text-small); line-height: 1.5; overflow-wrap: anywhere; margin: 2px 0; color: var(--muted); }
.theory-link:hover { color: var(--blue); background: var(--wash); }
.theory-link[aria-current="page"] { background: var(--soft-blue); color: var(--blue); font-weight: 600; }
.nav-count { flex-shrink: 0; font-size: var(--text-small); font-variant-numeric: tabular-nums; }
.sidebar-footer { border-top: 1px solid var(--line); padding: 16px 10px; font-size: var(--text-small); color: var(--muted); }
.sidebar-footer a { display: inline-flex; align-items: center; min-height: 44px; }
main { min-width: 0; padding: 30px 0 48px; }
.toolbar { display: flex; align-items: flex-start; flex-wrap: wrap; justify-content: space-between; gap: 16px; padding-bottom: 26px; border-bottom: 1px solid var(--line); margin-bottom: 30px; }
.view-note { flex: 1 1 300px; font-size: var(--text-body); color: var(--muted); margin: 0; max-width: 580px; }
.notation { display: flex; gap: 3px; border: 1px solid var(--input-line); border-radius: 7px; padding: 3px; flex-shrink: 0; }
.notation button { line-height: 1.5; min-height: 44px; border: 0; border-radius: 4px; color: var(--muted); background: white; padding: 8px 14px; font-size: var(--text-body); font-weight: 600; }
.notation button:hover { color: var(--blue); background: var(--wash); }
.notation button[aria-pressed="true"] { background: var(--blue); color: white; }
.notation button:focus-visible { outline-offset: 1px; }
.eyebrow { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; font-size: var(--text-small); font-weight: 600; color: var(--blue); }
.source-tag { color: var(--muted); font-size: var(--text-small); font-weight: 400; overflow-wrap: anywhere; }
.theory { margin-bottom: 40px; }
.theory h2 { font-size: var(--text-section); font-weight: 600; letter-spacing: -.035em; margin: 10px 0 18px; }
.intro { font-size: var(--text-body); line-height: 1.6; color: var(--muted); }
.intro p { margin: 0 0 12px; }
.intro code { background: var(--wash); border-radius: 3px; padding: 2px 4px; }
.source-link { line-height: 1.5; display: inline-flex; align-items: center; gap: 8px; min-height: 44px; font-size: var(--text-body); margin: 0 0 20px; }
.scope-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid var(--line); border-radius: 8px; background: var(--wash); }
.scope-grid > div { min-width: 0; padding: 18px 16px; border-right: 1px solid var(--line); }
.scope-grid > div:last-child { border-right: 0; }
.scope-value { display: block; font-size: var(--text-section); font-weight: 600; line-height: 1.2; font-variant-numeric: tabular-nums; }
.scope-label { display: block; overflow-wrap: anywhere; font-size: var(--text-small); color: var(--muted); }
.frame { margin: 8px 0 30px; color: var(--muted); font-size: var(--text-body); }
summary { line-height: 1.5; min-height: 44px; padding: 10px 0; font-weight: 600; }
summary:hover { color: var(--blue); }
.frame dl { display: grid; grid-template-columns: 100px minmax(0, 1fr); gap: 8px 14px; border-left: 2px solid var(--line); padding-left: 16px; }
.frame dt { font-weight: 600; overflow-wrap: anywhere; }
.frame dd { margin: 0; overflow-wrap: anywhere; }
.formula-group { margin-top: 30px; }
.group-title { display: flex; flex-wrap: wrap; gap: 10px; align-items: baseline; border-bottom: 1px solid var(--line); padding-bottom: 12px; }
.group-title h3 { font-size: var(--text-lead); font-weight: 600; margin: 0; }
.group-title > span { color: var(--muted); font-size: var(--text-small); }
.formula-row { padding: 16px 0 20px; border-bottom: 1px solid var(--line); }
.formula-label { display: block; font-size: var(--text-small); color: var(--muted); font-weight: 600; margin-bottom: 6px; overflow-wrap: anywhere; }
.formula { font: var(--text-math)/1.7 var(--math); white-space: pre-wrap; overflow-wrap: anywhere; font-variant-ligatures: none; color: var(--ink); }
.ascii .formula { font: var(--text-body)/1.7 var(--mono); }
.properties .formula-label { color: var(--blue); }
.empty-group, .definition-note { color: var(--muted); font-size: var(--text-body); }
.definition-note { margin: 12px 0 4px; }
.definitions .formula-row { padding-block: 12px; }
.run-box { margin: 32px 0; padding: 24px; border-radius: 8px; background: var(--wash); }
.run-box p { font-size: var(--text-body); color: var(--muted); margin: 0; }
.run-box .run-intro { margin: 8px 0 20px; }
.run-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.run-option { min-width: 0; border: 1px solid var(--line); border-radius: 7px; background: white; padding: 16px; }
.run-option h4 { font-size: var(--text-body); font-weight: 600; margin: 0; }
.run-option code { display: block; font-size: var(--text-body); line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; margin: 12px 0; }
.run-box .run-footer { margin-top: 20px; font-size: var(--text-small); }
.legend { border-top: 1px solid var(--line); margin-top: 32px; padding-top: 8px; }
.legend summary { font-size: var(--text-body); }
.legend-intro { font-size: var(--text-body); color: var(--muted); }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--text-body); margin: 12px 0; }
th { text-align: left; color: var(--muted); font-size: var(--text-body); font-weight: 600; background: var(--wash); }
th, td { padding: 12px; border-bottom: 1px solid var(--line); }
.symbol { font: var(--text-math)/1.7 var(--math); white-space: nowrap; }
td code { font-size: var(--text-body); }
.scope-note { font-size: var(--text-body); color: var(--muted); margin-top: 32px; border-top: 1px solid var(--line); padding-top: 20px; }
.scope-note strong { color: var(--ink); }
.no-results { font-size: var(--text-body); padding: 24px 0; }
.js .theory:not(.is-active), .js-only { display: none; }
[hidden] { display: none !important; }
.js .js-only { display: block; }
.js .notation { display: flex; }
@media (max-width: 1000px) {
  .layout { grid-template-columns: 210px minmax(0, 1fr); gap: 28px; }
  .truth-key { display: none; }
  .scope-grid > div { padding: 14px 12px; }
  .run-options { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 800px) {
  .site-header, .masthead, .layout { width: calc(100% - 40px); }
  .layout { grid-template-columns: 190px minmax(0, 1fr); gap: 24px; }
  .scope-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .scope-grid > div:nth-child(2) { border-right: 0; }
  .scope-grid > div:nth-child(-n+2) { border-bottom: 1px solid var(--line); }
}
@media (max-width: 680px) {
  .site-header, .masthead, .layout { width: calc(100% - 32px); }
  .site-header { min-height: 76px; gap: 8px 16px; }
  .site-header nav { gap: 0 16px; }
  .masthead { padding-block: 32px 24px; }
  .layout { display: block; }
  .sidebar { position: static; max-height: none; padding-block: 24px 0; }
  .sidebar nav { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px; }
  .nav-group { margin-bottom: 10px; }
  .sidebar-footer { padding: 12px 0; }
  .search-status { margin-bottom: 18px; }
  main { padding-top: 20px; }
  .toolbar { margin-bottom: 24px; padding-bottom: 24px; }
  .source-tag { display: none; }
  .frame dl { grid-template-columns: 85px minmax(0, 1fr); }
  .run-box { padding: 20px 16px; }
}
@media print {
  body { background: white; }
  .site-header, .masthead, .layout { width: 100%; }
  .site-header { min-height: 0; border: 0; }
  .site-header nav, .brand-mark { display: none; }
  .masthead { padding: 16px 0; background: none; }
  .layout { display: block; }
  .sidebar, .toolbar, .legend, .run-box, .source-link { display: none !important; }
  .formula-row { break-inside: avoid; }
  .scope-grid { background: none; }
  main { padding-top: 16px; }
  .truth-key { display: none; }
}
</style>
<script>document.documentElement.classList.add('js');</script>
</head>
<body>
<a class="skip-link" href="#main">Skip to the theory</a>
<header class="site-header"><div class="brand"><span class="brand-mark" aria-hidden="true">3μ</span><span>3μQL <strong>Explorer</strong></span></div><nav aria-label="Resources"><a href="language.md">Syntax reference</a><a href="../README.md">Package guide</a></nav></header>
<div class="masthead"><div class="masthead-inner"><div><h1>Theory guide</h1><p>Explore the axioms, inspect their scope, and read each property in the paper’s notation. Every formula comes from an executable literate theory.</p></div><div class="truth-key" aria-label="Three truth values"><span><b>t</b> true</span><span><b>b</b> broken</span><span><b>f</b> false</span><div class="truth-note">Both t and b are designated (valid).</div></div></div></div>
<div class="layout">
<aside class="sidebar" aria-label="Choose a theory">
<div class="js-only"><label for="search" class="search-label">Find a theory or formula</label><input id="search" class="search" type="search" placeholder="Try Agreement or quorum…" autocomplete="off"><p id="search-status" class="search-status" role="status">@@COUNT@@ theories</p></div>
<nav aria-label="Theories">@@NAVIGATION@@</nav>
<div class="sidebar-footer">@@COUNT@@ examples · fully offline<br><a href="language.md">Syntax reference</a> · <a href="../README.md">Package guide</a></div>
</aside>
<main id="main" tabindex="-1">
<div class="toolbar"><p class="view-note">Read each theory’s formulas with their named definitions. Labels and declared scopes match the literate sources; the notation switch preserves every formula’s meaning.</p><div class="notation js-only" role="group" aria-label="Formula notation"><button type="button" data-notation="unicode" aria-pressed="true">Unicode</button><button type="button" data-notation="ascii" aria-pressed="false">ASCII</button></div></div>
<p id="no-results" class="no-results" hidden>No theories match your search. Try a predicate, property label, or logical symbol.</p>
@@ARTICLES@@
<details class="legend"><summary>Symbol reference</summary><p class="legend-intro">Unicode and ASCII may be freely mixed in a theory. Strong implication is <span class="symbol">⇀</span> or <code>-\</code>; weak implication is <span class="symbol">→</span> or <code>-&gt;</code>. Temporal operators and truth-value tests retain their readable names.</p><div class="table-wrap"><table><thead><tr><th>Unicode</th><th>ASCII</th><th>Meaning</th></tr></thead><tbody>@@LEGEND@@</tbody></table></div><p class="legend-intro">See <a href="language.md">the full syntax reference</a> for precedence, binding, truth tests, and temporal operators.</p></details>
<p class="scope-note"><strong>Read the scope with the result.</strong> <code>check</code> uses the declared finite frame; <code>search</code> varies frames within the selected bounds. Both retain the stated finite or stuttering time convention. A successful finite check or completed bounded search is not an unbounded theorem. A search that stops at a resource limit may be incomplete, and the guide does not assert that every listed property holds.</p>
<noscript><p>JavaScript is disabled: all theories are shown in Unicode. Navigation links still work.</p></noscript>
</main>
</div>
<script id="guide-data" type="application/json">@@DATA@@</script>
<script>
'use strict';
@@NOTATION_SCRIPT@@
const data = JSON.parse(document.getElementById('guide-data').textContent);
const articles = Array.from(document.querySelectorAll('.theory'));
const links = Array.from(document.querySelectorAll('.theory-link'));
const search = document.getElementById('search');
const status = document.getElementById('search-status');
const noResults = document.getElementById('no-results');
let current = articles[0].id;
function selectTheory(id, updateHash) {
  if (!articles.some(article => article.id === id)) return;
  current = id;
  articles.forEach(article => article.classList.toggle('is-active', article.id === id));
  links.forEach(link => {
    if (link.dataset.theory === id) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  if (updateHash) {
    try { history.replaceState(null, '', '#' + id); }
    catch (_) { location.hash = id; }
  }
}
function filterTheories() {
  const query = search.value.trim().toLocaleLowerCase();
  const visible = new Set(data.theories.filter(theory => theory.search.includes(query)).map(theory => theory.id));
  links.forEach(link => { link.hidden = !visible.has(link.dataset.theory); });
  document.querySelectorAll('.nav-group').forEach(group => { group.hidden = !Array.from(group.querySelectorAll('a')).some(link => !link.hidden); });
  status.textContent = visible.size + (visible.size === 1 ? ' theory' : ' theories') + (query ? ' match' + (visible.size === 1 ? 'es' : '') : '');
  noResults.hidden = visible.size !== 0;
  if (!visible.size) articles.forEach(article => article.classList.remove('is-active'));
  else selectTheory(visible.has(current) ? current : visible.values().next().value, false);
}
links.forEach(link => link.addEventListener('click', event => {
  event.preventDefault();
  selectTheory(link.dataset.theory, true);
  document.getElementById('main').focus({preventScroll: true});
  if (window.innerWidth < 681) document.getElementById('main').scrollIntoView({block:'start'});
  else window.scrollTo({top:0});
}));
document.querySelectorAll('[data-notation]').forEach(button => button.addEventListener('click', () => {
  const notation = button.dataset.notation;
  document.body.classList.toggle('ascii', notation === 'ascii');
  document.querySelectorAll('[data-notation]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
  document.querySelectorAll('[data-formula]').forEach(formula => { formula.innerHTML = formulaHTML(data.formulas[Number(formula.dataset.formula)][notation]); });
}));
function fromHash() {
  let id;
  try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return; }
  if (articles.some(article => article.id === id)) {
    if (search.value) { search.value = ''; filterTheories(); }
    selectTheory(id, false);
  }
}
search.addEventListener('input', filterTheories);
window.addEventListener('hashchange', fromHash);
selectTheory(current, false);
fromHash();
</script>
</body>
</html>
'''


if __name__ == "__main__":
    document, count = build()
    target = ROOT / "docs" / "theories.html"
    target.write_text(document, encoding="utf-8", newline="\n")
    print(f"Built {target.relative_to(ROOT)} from {count} theories.")
