/** Pure source-highlighting checks. Run: node tests/browser/highlight.mjs */
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../../web/highlight.js", import.meta.url), "utf8");
const { highlightSource } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

function visible(html) {
  return html.replace(/<\/?span(?: class="syntax-[a-z]+")?>/g, "")
    .replace(/&(amp|lt|gt|quot|#39);/g, (_, entity) => ({ amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'" })[entity]);
}

function highlights(text, kind, spelling) {
  const escaped = spelling.replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
  assert.ok(highlightSource(text).includes(`<span class="syntax-${kind}">${escaped}</span>`), `${kind}: ${spelling}`);
}

const logic = text => `\`\`\`muql\n${text}\n\`\`\``;

test("preserves source exactly, including whitespace, line endings and unfinished input", () => {
  for (const text of ["", "\n", "\n\n", " \t ", "😀 < > & \" ' \u0000", "# Title\r\n\nText\rEnd\u2028line\u2029last", "```muql\nproperty P: ∃⁰¹ x. p(x)\n", logic('values "unfinished\\'), "```muql\n\tproperty P: t\n\n```\n"]) {
    assert.equal(visible(highlightSource(text)), text);
  }
});

test("highlights Markdown without interpreting embedded HTML", () => {
  highlights("# A heading", "heading", "# A heading");
  highlights("Text `plain <code>` and **bold**.", "code", "`plain <code>`");
  highlights("[a link](https://example.test)", "link", "[a link](https://example.test)");
  highlights("- A list", "markup", "- ");
  assert.equal(highlightSource("property Example: t"), "property Example: t");
  assert.equal(highlightSource("identifier_with_underscores"), "identifier_with_underscores");
});

test("recognises declared names and every declaration keyword", () => {
  for (const word of ["theory", "points", "values", "stages", "time", "quorums", "predicate", "axiom", "property", "let"]) highlights(logic(`${word} Example`), "keyword", word);
  for (const word of ["predicate", "axiom", "property", "let"]) highlights(logic(`  ${word} Example: t`), "name", "Example");
  highlights(logic("stages 123"), "number", "123");
});

test("recognises Unicode and ASCII logic, including unique and affine existence", () => {
  for (const operator of ["¬", "∧", "∨", "⊕", "→", "⇀", "≡", "≤", "≠", "∀", "∃", "∃¹", "∃1", "∃!", "∃⁰¹", "∃01", "μ", "µ", "ν", "□", "◇", "⋄", "∃Q", "∀Q", "∃Q□", "∀Q◇", "∀Q⋄", "∃Q◇", "∃Q⋄", "∀Q□", "<=>", "-\\", "->", "<=", "==", "!=", "&&", "||", "!", "&", "|", "^", "=", "not", "and", "or", "xor", "forall", "exists", "affine", "unique", "mu", "nu"]) highlights(logic(`property P: ${operator} x`), "operator", operator);
});

test("paper-style labels are whole names while formula punctuation keeps its meaning", () => {
  for (const declaration of ["axiom", "property"]) {
    for (const label of ["PaxWrite?", "PaxWrite!", "PaxDecide-not-L!", "_Rule!?-2"]) {
      const text = logic(`  ${declaration} ${label}:!P # direction marks`);
      highlights(text, "name", label);
      highlights(text, "operator", "!");
      highlights(text, "comment", "# direction marks");
      assert.equal(visible(highlightSource(text)), text);
    }
  }
  for (const text of [logic("predicate P!/0"), logic("let P!(): t"), logic("property Goal: P!")]) {
    assert.ok(!highlightSource(text).includes('class="syntax-name">P!</span>'));
  }
});

test("superscript quorum Q is one operator and preserves literal source and spacing", () => {
  for (const operator of ["∃ꟴ", "∀ꟴ", "∃ꟴ□", "∀ꟴ◇", "∀ꟴ⋄", "∃ꟴ◇", "∃ꟴ⋄", "∀ꟴ□"]) {
    const text = logic(`property P: ${operator}(p) ∧ ∀ Q. Q = Q`);
    highlights(text, "operator", operator);
    assert.equal(visible(highlightSource(text)), text);
  }
  for (const value of ['"∃ꟴ□ ∀ꟴ◇"', "'∃Q ∃ꟴ'"]) highlights(logic(`values ${value}`), "string", value);
  highlights(logic("property P: t # ∃ꟴ□ is a comment"), "comment", "# ∃ꟴ□ is a comment");
});

test("recognises builtins, temporal operators and truth constants as whole words", () => {
  for (const builtin of ["T", "F", "B", "TB", "TF", "FB", "diamond", "box", "somewhere", "everywhere", "existsQ", "forallQ", "quorum", "contra", "someQuorumSomePoint", "everyQuorumEveryPoint", "someQuorumEveryPoint", "everyQuorumSomePoint", "yesterday", "tomorrow", "once", "historically", "past", "sometime", "forever", "infinitely", "ultimately", "latest", "twined", "t", "b", "f"]) highlights(logic(`property P: ${builtin}(x)`), "builtin", builtin);
  assert.ok(!highlightSource(logic("property P: tomorrowish & tiny & forage & unique_name")).includes('class="syntax-builtin"'));
});

test("does not colour rejected => as a valid logic operator", () => {
  const html = highlightSource(logic("property P: p => q"));
  assert.ok(html.includes('<span class="syntax-invalid">=&gt;</span>'));
  assert.ok(!html.includes('<span class="syntax-operator">=</span>'));
});

test("comments and escaped quoted values take precedence over operators", () => {
  for (const quote of ['"', "'"]) {
    const value = `${quote}value # // ∃⁰¹ => <script> \\${quote} end${quote}`;
    highlights(logic(`values ${value}`), "string", value);
  }
  for (const comment of ["# property Fake: => <script>", "// property Fake: ∃¹ <script>"]) highlights(logic(`property P: t ${comment}`), "comment", comment);
  const html = highlightSource(logic('values "# // ∃¹" # "ignored"'));
  assert.ok(!html.includes('class="syntax-operator"'));
});

test("only exact lowercase muql fences activate logic highlighting", () => {
  for (const info of ["MUQL", "Muql", "python", "muql extra", "", "{muql}"]) {
    const text = `\`\`\`${info}\nproperty P: ∃¹ x. t\n\`\`\``;
    assert.ok(!highlightSource(text).includes('class="syntax-keyword"'), info);
    assert.equal(visible(highlightSource(text)), text);
  }
  highlights("   ~~~~  muql \nproperty P: t\n~~~~~~", "keyword", "property");
  assert.ok(!highlightSource("    ```muql\nproperty P: t\n    ```").includes('class="syntax-keyword"'));
});

test("fences close only with matching characters, sufficient length and no info", () => {
  const text = "````muql\nproperty First: t\n```\nproperty Short: t\n~~~~\nproperty Other: t\n```` extra\nproperty Info: t\n`````\nproperty Prose: t";
  const html = highlightSource(text);
  for (const name of ["First", "Short", "Other", "Info"]) highlights(text, "name", name);
  assert.ok(html.endsWith("property Prose: t"));
  assert.equal(visible(html), text);
  const nested = "```python\n~~~muql\nproperty Hidden: t\n~~~\n```\n```muql\nproperty Visible: t\n```";
  assert.ok(!highlightSource(nested).includes('class="syntax-name">Hidden'));
  highlights(nested, "name", "Visible");
});

test("escapes hostile text in every highlighting context", () => {
  const attack = '<img src=x onerror="alert(1)">&lt;script&gt;\' </span>';
  for (const text of [attack, `# ${attack}`, `\`${attack}\``, `[${attack}](${attack})`, logic(`# ${attack}`), logic(`values '${attack}'`), logic(attack), `\`\`\` ${attack}\n${attack}\n\`\`\``]) {
    const html = highlightSource(text);
    assert.equal(visible(html), text);
    assert.ok(!/<(?!\/?span\b)/.test(html), html);
    assert.ok(!html.includes('onerror="'));
  }
});

test("preserves all shipped theories and highlights their executable declarations", async () => {
  const folder = new URL("../../examples/", import.meta.url);
  const paths = (await readdir(folder)).filter(name => name.endsWith(".md"));
  paths.push("search/choices.md");
  assert.equal(paths.length, 14);
  for (const path of paths) {
    const text = await readFile(new URL(path, folder), "utf8");
    const html = highlightSource(text);
    assert.equal(visible(html), text, path);
    assert.ok(html.includes('class="syntax-keyword">property</span>'), path);
  }
});

test("handles long lines and incomplete delimiters without runaway scanning", { timeout: 5000 }, () => {
  for (const text of ["[x](".repeat(25000), "` ".repeat(50000), "* _ ".repeat(25000), logic("a".repeat(200000)), logic('"' + "\\\\".repeat(50000)), "<>&".repeat(50000)]) {
    assert.equal(visible(highlightSource(text)), text);
  }
});
