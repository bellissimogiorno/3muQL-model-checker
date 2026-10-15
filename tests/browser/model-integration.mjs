/** Page-to-model-view integration with DOM doubles; no browser rendering.
 * Run: node tests/browser/model-integration.mjs
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const app = await readFile(new URL("../../web/app.js", import.meta.url), "utf8");
const modelSource = await readFile(new URL("../../web/model-data.js", import.meta.url), "utf8");
const { atomLabel, nameLabel } = await import(`data:text/javascript;base64,${Buffer.from(modelSource).toString("base64")}`);
// Execute the actual page helpers. Imports, startup and unrelated controls are
// excluded so the renderer boundary and DOM can be replaced independently.
function definition(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `Missing page helper ${name}`);
  const rest = app.slice(start);
  const firstLine = rest.split("\n", 1)[0];
  if (firstLine.endsWith("}")) return firstLine;
  const end = rest.indexOf("\n}");
  assert.ok(end > 0, `Unclosed page helper ${name}`);
  return rest.slice(0, end + 2);
}
const helpers = ["el", "scopeText", "scopeBox", "valuationTable", "modelEvidence", "clearModelViews"]
  .map(definition).join("\n");

class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.parentElement = null;
    this.attributes = {}; this.listeners = new Map(); this.open = false;
    this.className = ""; this.text = ""; this.root = false;
  }
  get isConnected() { return this.root || !!this.parentElement?.isConnected; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(""); }
  set textContent(value) { this.text = String(value); this.replaceChildren(); }
  append(...children) {
    for (const child of children) { child.parentElement = this; this.children.push(child); }
  }
  replaceChildren(...children) {
    for (const child of this.children) child.parentElement = null;
    this.children = []; this.append(...children);
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  querySelector(selector) {
    assert.equal(selector, "summary", "The integration double only models the full-data summary target");
    return all(this, node => node.tagName === "summary")[0] || null;
  }
  focus() { this.focused = true; }
  scrollIntoView(options) { this.scrolled = options || true; }
  addEventListener(name, callback) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(callback);
  }
  emit(name) { for (const callback of this.listeners.get(name) || []) callback({ target: this }); }
}

function all(root, predicate) {
  return [root, ...root.children.flatMap(child => all(child, predicate))].filter(predicate);
}

function model(count = 3) {
  return {
    scope: { points: ["alice"], values: ["red"], stages: count, time: "finite", quorums: [["alice"]] },
    valuation: Array.from({ length: count }, (_, time) => ({ time, point: "alice", predicate: "P", args: ["red"], value: ["t", "b", "f"][time % 3] })),
  };
}

function fixture({ fail = false } = {}) {
  const calls = [], views = [], downloads = [];
  const document = {
    createElement: tag => new Element(tag),
    createTextNode(text) { const node = new Element("#text"); node.textContent = text; return node; },
  };
  const context = vm.createContext({
    document, atomLabel, nameLabel, download: (...args) => downloads.push(args),
    createModelView(value, options) {
      calls.push({ value, options });
      if (fail) throw new Error("Renderer unavailable");
      const view = new Element("model-view"); view.disposals = 0;
      view.dispose = () => { view.disposals++; };
      views.push(view); return view;
    },
  });
  vm.runInContext(`const modelViews = new Set();\n${helpers}\nfunction registeredViews() { return modelViews.size; }`, context);
  const root = new Element("main"); root.root = true;
  return {
    root, calls, views, downloads, context,
    witness(value = model(), { open = false, propertyName = "Agreement", connected = true } = {}) {
      const details = new Element("details"); details.open = open;
      if (connected) root.append(details);
      context.modelEvidence(details, value, propertyName);
      return { details, exact: details.children.find(child => child.className === "model-exact") };
    },
  };
}

test("closed witnesses defer diagram and exact valuation, then build each only once", () => {
  const f = fixture(); const value = model(); const before = JSON.stringify(value);
  const { details, exact } = f.witness(value);
  assert.equal(f.calls.length, 0);
  assert.equal(all(details, node => node.tagName === "table").length, 0);
  details.open = true; details.emit("toggle");
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].value, value);
  assert.equal(f.calls[0].options.propertyName, "Agreement");
  assert.equal(all(exact, node => node.tagName === "table").length, 0);
  exact.open = true; exact.emit("toggle");
  assert.equal(all(exact, node => node.tagName === "table").length, 1);
  for (const node of [details, exact]) {
    node.open = false; node.emit("toggle"); node.open = true; node.emit("toggle");
  }
  assert.equal(f.calls.length, 1);
  assert.equal(all(exact, node => node.tagName === "table").length, 1);
  assert.equal(JSON.stringify(value), before, "Displaying evidence must not mutate the model");
});

test("initially open witnesses render before insertion and retain the download boundary", () => {
  const f = fixture();
  const { details, exact } = f.witness(model(), { open: true, connected: false, propertyName: "" });
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].options.propertyName, "");
  assert.equal(exact.open, false);
  f.root.append(details); details.emit("toggle");
  assert.equal(f.calls.length, 1);
  f.calls[0].options.onDownload("model.svg", "<svg/>", "image/svg+xml");
  assert.deepEqual(f.downloads, [["model.svg", "<svg/>", "image/svg+xml"]]);
});

test("opening exact evidence exposes every valuation row through the existing pagination", () => {
  const f = fixture(); const { exact } = f.witness(model(205), { open: true });
  assert.equal(all(exact, node => node.tagName === "tbody").length, 0);
  exact.open = true; exact.emit("toggle");
  const body = all(exact, node => node.tagName === "tbody")[0];
  const next = all(exact, node => node.tagName === "button" && node.textContent === "Next rows")[0];
  const previous = all(exact, node => node.tagName === "button" && node.textContent === "Previous rows")[0];
  assert.equal(body.children.length, 100); assert.equal(previous.disabled, true);
  const stages = body.children.map(row => Number(row.children[0].textContent));
  next.emit("click"); stages.push(...body.children.map(row => Number(row.children[0].textContent)));
  next.emit("click"); stages.push(...body.children.map(row => Number(row.children[0].textContent)));
  assert.equal(next.disabled, true); assert.equal(body.children.length, 5);
  assert.deepEqual(stages, Array.from({ length: 205 }, (_, index) => index));
  previous.emit("click"); assert.equal(body.children[0].children[0].textContent, "100");
});

test("renderer failure leaves scope and full valuation open and usable", () => {
  const f = fixture({ fail: true }); const { details, exact } = f.witness(model(), { open: true });
  assert.match(details.textContent, /diagram could not be displayed/);
  assert.equal(exact.open, true);
  assert.match(exact.textContent, /Participants: alice/);
  const body = all(exact, node => node.tagName === "tbody")[0];
  assert.equal(body.children.length, 3);
  assert.deepEqual(body.children.map(row => row.children[3].textContent), ["t true", "b broken", "f false"]);
  assert.equal(f.context.registeredViews(), 0);
  details.emit("toggle"); exact.emit("toggle");
  assert.equal(f.calls.length, 1);
  assert.equal(all(exact, node => node.tagName === "table").length, 1);
});

test("full model data distinguishes legal comma-containing values and quorum members", () => {
  const f = fixture();
  const value = {
    scope: { points: ["a, b", "a", "b"], values: ["a, b", "c", "a", "b, c"],
      stages: 1, time: "finite", quorums: [["a, b"], ["a", "b"]] },
    valuation: [
      { time: 0, point: "a", predicate: "p", args: ["a, b", "c"], value: "t" },
      { time: 0, point: "a", predicate: "p", args: ["a", "b, c"], value: "f" },
    ],
  };
  const { exact } = f.witness(value, { open: true });
  exact.open = true; exact.emit("toggle");
  const rows = all(exact, node => node.tagName === "tbody")[0].children;
  assert.deepEqual(rows.map(row => row.children[2].textContent), ['p("a, b", c)', 'p(a, "b, c")']);
  assert.deepEqual(rows.map(row => row.children[3].textContent), ["t true", "f false"]);
  assert.ok(exact.textContent.includes('Participants: "a, b", a, b'));
  assert.ok(exact.textContent.includes('Quorums: {"a, b"} {a, b}'));
});

test("clearing results disposes each built view and detached toggle events cannot recreate it", () => {
  const f = fixture();
  const first = f.witness(model(), { open: true });
  const second = f.witness(model(), { open: true });
  const unopened = f.witness();
  assert.equal(f.context.registeredViews(), 2);
  f.context.clearModelViews(); f.root.replaceChildren();
  assert.deepEqual(f.views.map(view => view.disposals), [1, 1]);
  assert.equal(f.context.registeredViews(), 0);
  for (const { details, exact } of [first, second, unopened]) {
    details.open = true; details.emit("toggle"); exact.open = true; exact.emit("toggle");
    assert.equal(all(exact, node => node.tagName === "table").length, 0);
  }
  assert.equal(f.calls.length, 2);
  f.context.clearModelViews();
  assert.deepEqual(f.views.map(view => view.disposals), [1, 1]);
});

test("the full-model action opens only its own complete data and keeps the table lazy", () => {
  const f = fixture();
  const first = f.witness(model(205), { open: true });
  const second = f.witness(model(3), { open: true });
  for (const { exact } of [first, second]) {
    assert.equal(exact.open, false);
    assert.equal(all(exact, node => node.tagName === "table").length, 0);
    assert.equal(all(exact, node => node.tagName === "summary")[0].textContent, "Full model data");
  }
  const show = f.calls[0].options.onShowFullModel;
  assert.equal(typeof show, "function", "A model view needs a direct route to its complete data");
  show();
  assert.equal(first.exact.open, true);
  assert.equal(all(first.exact, node => node.tagName === "summary")[0].focused, true,
    "Keyboard users should arrive at the opened complete-data disclosure");
  assert.ok(first.exact.scrolled, "The complete-data destination should be brought into view");
  assert.equal(second.exact.open, false, "The action opened another counterexample's data");
  assert.equal(all(first.exact, node => node.tagName === "table").length, 1);
  assert.equal(all(second.exact, node => node.tagName === "table").length, 0);
  const body = all(first.exact, node => node.tagName === "tbody")[0];
  assert.equal(body.children.length, 100);
  const next = all(first.exact, node => node.tagName === "button" && node.textContent === "Next rows")[0];
  next.emit("click"); next.emit("click");
  assert.equal(body.children.length, 5, "All 205 rows remain reachable, including stages outside the diagram");
  assert.equal(body.children.at(-1).children[0].textContent, "204");
  show(); first.exact.emit("toggle");
  assert.equal(all(first.exact, node => node.tagName === "table").length, 1, "Repeated action must reuse the complete-data table");
});
