/** Display markup must preserve source, literal values, and safe HTML. */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../../web/notation.js", import.meta.url), "utf8");
const { formulaHTML } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const textContent = markup => markup.replace(/<\/?(?:span|sup)(?: class="[a-z-]+")?>/g, "")
  .replace(/&(amp|lt|gt|quot|#39);/g, (_, entity) => ({ amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'" })[entity]);

test("all quorum quantifiers raise only Q and retain copyable source text", () => {
  for (const symbol of ["∃Q", "∀Q", "∃Q◇", "∀Q□", "∃Q□", "∀Q◇", "∃Q⋄", "∀Q⋄"]) {
    const text = `${symbol}(P) ∧ ∀ Q. ∃ value. Q = value`;
    const markup = formulaHTML(text);
    assert.equal(textContent(markup), text);
    assert.equal((markup.match(/<sup /g) || []).length, 1);
    assert.ok(markup.includes(`${symbol[0]}<sup class="quorum-mark">Q</sup>`));
    assert.ok(markup.endsWith("∧ ∀ Q. ∃ value. Q = value"));
  }
  assert.equal(formulaHTML("existsQ(P) & forallQ(P)"), "existsQ(P) &amp; forallQ(P)");
});

test("native superscript Q is copied intact and never raised a second time", () => {
  for (const symbol of ["∃ꟴ", "∀ꟴ", "∃ꟴ◇", "∀ꟴ□", "∃ꟴ□", "∀ꟴ◇", "∃ꟴ⋄", "∀ꟴ⋄"]) {
    const text = `${symbol}(P) ∧ ∀ Q. Q = Q`;
    const markup = formulaHTML(text);
    assert.equal(textContent(markup), text);
    assert.ok(markup.startsWith(`<span class="quorum-quantifier">${symbol.slice(0, 2)}</span>`));
    assert.ok(!markup.includes("<sup"));
  }
});

test("quoted values, escaped quotes, comments and unfinished literals remain literal", () => {
  const inputs = [
    'P("∃Q", \'∀Q\')', 'P("escaped \\\" ∃Q")', "P('escaped \\\' ∀Q')",
    '# ∃Q\n// ∀Q', '"unfinished ∃Q', "'unfinished ∀Q", '"unfinished ∃Q' + "\\", "'unfinished ∀Q" + "\\",
    'P("∃ꟴ", \'∀ꟴ\')', '# ∃ꟴ\n// ∀ꟴ', '"unfinished ∃ꟴ' + "\\",
  ];
  for (const text of inputs) {
    const markup = formulaHTML(text);
    assert.equal(textContent(markup), text);
    assert.ok(!markup.includes("<sup"), text);
  }
  const text = '∃Q(P("∀Q")) # ∃Q\n∀Q(t)';
  assert.equal((formulaHTML(text).match(/<sup /g) || []).length, 2);
  assert.equal(textContent(formulaHTML(text)), text);
});

test("user text can never introduce HTML elements or attributes", () => {
  const text = '<img src=x onerror="alert(1)"> & ∃Q(P) </script><sup>Q</sup>';
  const markup = formulaHTML(text);
  assert.equal(textContent(markup), text);
  assert.ok(!/<(?!\/?(?:span|sup)\b)/.test(markup));
  assert.ok(!markup.includes('onerror="'));
  assert.equal((markup.match(/<sup /g) || []).length, 1);
});

test("every generated guide formula keeps its exact Unicode and ASCII text", async () => {
  const guide = await readFile(new URL("../../docs/theories.html", import.meta.url), "utf8");
  const data = JSON.parse(guide.match(/<script id="guide-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  assert.ok(data.formulas.length > 100);
  for (const forms of data.formulas) {
    for (const text of Object.values(forms)) assert.equal(textContent(formulaHTML(text)), text);
    assert.ok(!formulaHTML(forms.ascii).includes("<sup"));
  }
});

test("quorum toolbar labels insert the same native superscript Q shown to the reader", async () => {
  const page = await readFile(new URL("../../web/index.html", import.meta.url), "utf8");
  const buttons = [...page.matchAll(/<button[^>]+data-symbol="([∃∀]ꟴ[◇□]?)"[^>]*>([\s\S]*?)<\/button>/g)];
  assert.equal(buttons.length, 6);
  for (const [, symbol, markup] of buttons) {
    assert.equal(textContent(markup), symbol);
    assert.ok(!markup.includes("<sup"));
  }
});
