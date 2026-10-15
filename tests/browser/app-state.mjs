/** Startup, run settings and draft checks for the real page controller with DOM/network doubles.
 * Run: node tests/browser/app-state.mjs. These do not test browser rendering.
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = (await readFile(new URL("../../web/app.js", import.meta.url), "utf8"))
  .replace(/^import .* from "\.\/editor\.js";$/m, "")
  .replace(/^import .* from "\.\/model-view\.js";$/m, "")
  .replace(/^import .* from "\.\/notation\.js";$/m, "")
  .replaceAll("import.meta.url", '"https://example.test/muql-explorer/app.js"');
const key = "muql-explorer-draft-v1";
const notationSource = await readFile(new URL("../../web/notation.js", import.meta.url), "utf8");
const { formulaHTML } = await import(`data:text/javascript;base64,${Buffer.from(notationSource).toString("base64")}`);
const theory = '```muql\ntheory "Saved work"\npredicate chosen/1\nproperty P: t\n```\n';
const tick = () => new Promise(resolve => setImmediate(resolve));
const textOf = node => [node.textContent, ...node.children.map(textOf)].join(" ");
const tinyExample = { id: "tiny", group: "Examples", title: "Tiny", file: "tiny.md", mode: "check",
  description: "A small independent tutorial.", hint: "Try the tutorial." };

function target(properties = {}) {
  const listeners = new Map();
  return Object.defineProperties({
    addEventListener(type, callback) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(callback);
    },
    async emit(type, data = {}) {
      for (const callback of listeners.get(type) || []) await callback({ type, target: this, preventDefault() {}, ...data });
    },
  }, Object.getOwnPropertyDescriptors(properties));
}

function element(id = "", focused = () => {}, scrolled = () => {}) {
  let value = "";
  const classes = new Set();
  const attributes = new Map();
  return target({
    id, tagName: id.toUpperCase(), children: [], hidden: false, checked: false, disabled: false,
    min: "0", max: "1000000", open: false, textContent: "",
    get value() { return value; },
    set value(text) { value = String(text); },
    classList: { toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); }, contains: name => classes.has(name) },
    querySelectorAll(selector) {
      const children = this.children.flatMap(child => [child, ...child.querySelectorAll("*")]);
      if (selector === "*") return children;
      if (!selector.startsWith("input")) return [];
      return children.filter(child => child.tagName === "INPUT" && (selector === "input" || (selector === "input:checked" ? child.checked : !child.checked)));
    },
    querySelector(selector) {
      return this.querySelectorAll("*").find(child => selector.startsWith(".")
        ? String(child.className || "").split(/\s+/).includes(selector.slice(1))
        : selector.startsWith("#") && child.id === selector.slice(1)) || null;
    },
    get firstChild() { return this.children[0] || null; },
    append(...children) { this.children.push(...children); },
    prepend(...children) { this.children.unshift(...children); },
    replaceChildren(...children) { this.children = children; },
    setAttribute(name, value) { attributes.set(name, String(value)); },
    getAttribute(name) { return attributes.get(name) ?? null; }, removeAttribute(name) { attributes.delete(name); },
    remove() {}, click() { return this.emit("click"); }, focus() { focused(this); }, scrollIntoView() { scrolled(this); },
  });
}

async function fixture({ draft = { source: theory }, failure, gate, exampleSource = theory,
  examples = [tinyExample], files = {}, confirm = true, fetchGate = {}, restore = true } = {}) {
  const nodes = new Map(), stored = new Map(), writes = [], requests = [], timers = new Map(), workers = [], downloads = [], scrolls = [];
  let timerId = 0, confirms = 0, activeElement;
  const focused = node => { activeElement = node; };
  if (draft !== null) stored.set(key, JSON.stringify(draft));
  function node(id) {
    if (!nodes.has(id)) nodes.set(id, element(id, focused, node => scrolls.push(node)));
    return nodes.get(id);
  }
  // Native textarea.value normalizes CR and CRLF before the page reads it back.
  let editorValue = "";
  Object.defineProperty(node("theory-editor"), "value", {
    get: () => editorValue,
    set: value => { editorValue = String(value).replace(/\r\n?/g, "\n"); },
  });
  node("mode-search").checked = true;
  node("highlight-syntax").checked = true;
  node("solver").value = "builtin";
  for (const id of ["max-points", "max-values", "max-stages", "max-quorums", "max-frames", "max-nodes", "max-decisions", "timeout"]) node(id).value = "1";
  node("run-form").reportValidity = () => true;
  node("run-controls").querySelectorAll = () => ["mode-search", "mode-check", "max-points", "max-values", "max-stages", "max-quorums", "max-frames", "max-nodes", "max-decisions", "timeout", "solver"].map(node);
  const window = target({ confirm(message) { confirms++; return typeof confirm === "function" ? confirm(message) : confirm; } });
  const document = target({
    getElementById: node, body: element("body", focused), querySelector: node, querySelectorAll: () => [],
    createElement: tag => element(tag, focused), createTextNode: text => Object.assign(element(), { textContent: text }),
    get activeElement() { return activeElement; },
    set activeElement(node) { activeElement = node; },
    visibilityState: "visible",
  });
  activeElement = document.body;
  const context = vm.createContext({
    URL: class extends URL {
      static createObjectURL(blob) { downloads.push(blob); return `blob:download-${downloads.length}`; }
      static revokeObjectURL() {}
    }, Blob, performance, console,
    createSourceHighlighter: () => ({ refresh() {}, sync() {} }),
    formulaHTML,
    document,
    window, location: { protocol: "https:" }, matchMedia: () => ({ matches: true }),
    localStorage: {
      getItem: name => stored.get(name) ?? null,
      setItem(name, text) { stored.set(name, text); writes.push(text); },
      removeItem(name) { stored.delete(name); },
    },
    setTimeout(callback) { const id = ++timerId; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); },
    setInterval: () => ++timerId, clearInterval() {}, AbortController,
    Worker: class {
      constructor() { Object.assign(this, target()); workers.push(this); }
      postMessage(request) { requests.push(request); }
      terminate() {}
    },
    async fetch(url) {
      const name = String(url).split("/").at(-1);
      if (gate && name === "config.json") await gate;
      if (fetchGate[name]) await fetchGate[name];
      if (typeof failure === "function" ? failure(name) : name === failure) throw new Error("Offline");
      const content = name === "config.json" ? JSON.stringify({ version: "test", examples: "examples.json" })
        : name === "examples.json" ? JSON.stringify(examples) : files[name] ?? exampleSource;
      return { ok: true, text: async () => content };
    },
  });
  vm.runInContext(source, context, { filename: "web/app.js" });
  await tick();
  // Most state tests exercise custom work. Explicitly take the user action
  // after First steps loads; startup tests pass restore:false to inspect it.
  if (restore && draft && !failure && !gate) {
    const request = requests.at(-1);
    await workers.at(-1).emit("message", { data: { id: request.id, type: "result", result: { ok: true, metadata: declaredMetadata() } } });
    await node("restore-draft").emit("click");
  }
  return {
    node, window, document, stored, writes, requests, downloads, scrolls, confirms: () => confirms,
    async inspected(metadata = declaredMetadata()) {
      const request = requests.at(-1);
      assert.equal(request.type, "inspect");
      await workers.at(-1).emit("message", { data: { id: request.id, type: "result", result: { ok: true, metadata } } });
    },
    async inspectionFailed(message = "Malformed formula") {
      const request = requests.at(-1);
      assert.equal(request.type, "inspect");
      await workers.at(-1).emit("message", { data: { id: request.id, type: "result", result: { ok: false, error: { message } } } });
    },
    async finished(result) {
      const request = requests.at(-1);
      assert.equal(request.type, "run");
      await workers.at(-1).emit("message", { data: { id: request.id, type: "result", result } });
    },
    async choose(id) {
      node("example-select").value = id;
      await node("example-select").emit("change");
      await tick();
    },
    async mode(value) {
      node("mode-search").checked = value === "search";
      node("mode-check").checked = value === "check";
      await node(`mode-${value}`).emit("change");
    },
  };
}

function declaredMetadata() {
  return {
    name: "Saved work", scope_declared: true, predicates: [{ name: "chosen", arity: 1 }],
    scope: { points: ["alice", "bob", "carol"], values: ["red", "blue"], stages: 2, time: "finite", quorums: [["alice", "bob"], ["bob", "carol"], ["alice", "bob", "carol"]] },
    properties: [{ name: "P", formula: "t" }, { name: "Q", formula: "f" }],
    axioms: [{ name: "A", formula: "t" }, { name: "B", formula: "t" }],
  };
}

test("startup failures preserve an existing draft when the page is closed", async () => {
  for (const failure of ["config.json", "examples.json"]) {
    const f = await fixture({ failure });
    assert.match(f.node("boot-error").textContent, /Offline/);
    await f.window.emit("beforeunload");
    assert.equal(JSON.parse(f.stored.get(key)).source, theory);
    assert.deepEqual(f.writes, []);
  }
});

test("startup locks imports and editing until the first example loads and preserves drafts if interrupted", async () => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const f = await fixture({ gate, restore: false });
  assert.equal(f.node("theory-editor").readOnly, true);
  assert.equal(f.node("import-button").disabled, true);
  await f.window.emit("beforeunload");
  assert.deepEqual(f.writes, []);
  release(); await tick();
  assert.equal(f.node("theory-editor").value, theory);
  assert.equal(f.requests.length, 1);
});

test("restored drafts retain source, highlight choice, and inspection settings on close", async () => {
  const f = await fixture({ draft: { source: theory, highlight: false, mode: "search", properties: ["P"], drop: [], limits: { timeout: 7 } } });
  assert.equal(f.node("theory-editor").value, theory);
  assert.equal(f.node("highlight-syntax").checked, false);
  await f.window.emit("beforeunload");
  const saved = JSON.parse(f.stored.get(key));
  assert.equal(saved.source, theory);
  assert.equal(saved.highlight, false);
  assert.equal(saved.limits.timeout, 7);
  assert.deepEqual(saved.properties, ["P"]);
});

test("a first visit begins with the first curated example and does not invent a custom draft", async () => {
  const f = await fixture({ draft: null });
  assert.equal(f.node("theory-editor").value, theory);
  assert.equal(f.stored.has(key), false);
  assert.equal(f.node("example-select").value, "tiny");
  assert.equal(f.node("curated-picker").hidden, false);
  assert.equal(f.node("custom-context").hidden, true);
  assert.equal(f.requests[0].payload.source, theory);
});

test("normalized CRLF examples are not incorrectly treated as edits", async () => {
  const f = await fixture({ draft: null, exampleSource: theory.replaceAll("\n", "\r\n") });
  await f.node("stop-button").emit("click");
  await f.node("load-example").emit("click");
  assert.equal(f.confirms(), 0);
  assert.equal(f.node("theory-editor").value, theory);
});

test("search bounds stay visible and become disabled only for fixed-frame checks", async () => {
  const f = await fixture();
  assert.equal(f.node("run-controls").disabled, true, "Inspection locks the whole form");
  await f.inspected();
  const searchLimits = ["max-points", "max-values", "max-stages", "max-quorums", "max-frames"];
  f.node("max-points").value = "5";
  for (const id of searchLimits) assert.equal(f.node(id).disabled, false);
  assert.equal(f.node("search-bounds").hidden, false);
  assert.match(f.node("bounds-help").textContent, /Maximum sizes.*Smaller frames/);
  await f.mode("check");
  assert.equal(f.node("search-bounds").hidden, false);
  assert.equal(f.node("search-bounds").classList.contains("is-inactive"), true);
  for (const id of searchLimits) assert.equal(f.node(id).disabled, true, id);
  for (const id of ["timeout", "max-nodes", "max-decisions", "solver"]) assert.equal(f.node(id).disabled, false, id);
  assert.match(f.node("scope-note").textContent, /3 participants, 2 values, 2 time stages, 3 quorum generators/);
  assert.match(f.node("bounds-help").textContent, /Not used in this mode/);
  await f.mode("search");
  for (const id of searchLimits) assert.equal(f.node(id).disabled, false, id);
  assert.equal(f.node("search-bounds").classList.contains("is-inactive"), false);
  assert.equal(f.node("max-points").value, "5");
});

test("run requests include size bounds for search and omit them for fixed frames", async () => {
  const values = { max_points: 4, max_values: 3, max_stages: 5, max_quorums: 6, max_frames: 17, timeout: 9, max_nodes: 110, max_decisions: 37 };
  for (const mode of ["search", "check"]) {
    const f = await fixture({ draft: { source: theory, mode, limits: values } });
    await f.inspected();
    await f.node("run-form").emit("submit");
    const request = JSON.parse(JSON.stringify(f.requests.at(-1)));
    assert.equal(request.type, "run");
    assert.equal(request.payload.mode, mode);
    assert.deepEqual(request.payload.limits, mode === "search" ? values : { timeout: 9, max_nodes: 110, max_decisions: 37 });
    assert.equal(f.node("run-controls").disabled, true, "Running locks all controls through their fieldset");
  }
});

test("a fixed-frame draft preserves inactive search bounds across reload and mode changes", async () => {
  const limits = { max_points: 4, max_values: 3, max_stages: 5, max_quorums: 6, max_frames: 17, timeout: 9, max_nodes: 110, max_decisions: 37 };
  const first = await fixture({ draft: { source: theory, mode: "search", limits } });
  await first.inspected();
  await first.mode("check");
  await first.window.emit("beforeunload");
  const saved = JSON.parse(first.stored.get(key));
  assert.equal(saved.mode, "check");
  assert.deepEqual(saved.limits, limits);
  const restored = await fixture({ draft: saved });
  await restored.inspected();
  assert.equal(restored.node("mode-check").checked, true);
  await restored.mode("search");
  for (const [name, value] of Object.entries(limits)) assert.equal(restored.node(name.replaceAll("_", "-")).value, String(value), name);
  await restored.node("run-form").emit("submit");
  assert.deepEqual(JSON.parse(JSON.stringify(restored.requests.at(-1).payload.limits)), limits);
});

test("a theory without a declared frame explains why fixed-frame checking is unavailable", async () => {
  const f = await fixture();
  const metadata = declaredMetadata(); metadata.scope_declared = false;
  await f.inspected(metadata);
  assert.equal(f.node("run-button").disabled, false);
  await f.mode("check");
  assert.equal(f.node("run-button").disabled, true);
  assert.match(f.node("scope-note").textContent, /no declared frame.*Choose Search for a model/);
  assert.doesNotMatch(f.node("scope-note").textContent, /Declared frame:/, "Never present placeholder scope as a declared frame");
  await f.mode("search");
  assert.equal(f.node("run-button").disabled, false);
});

test("search retains every named value and its minimum survives mode changes", async () => {
  const f = await fixture();
  const metadata = declaredMetadata(); metadata.scope.values.push("green");
  await f.inspected(metadata);
  assert.equal(Number(f.node("max-values").min), 3);
  assert.equal(f.node("max-values").value, "3");
  await f.mode("check");
  await f.mode("search");
  assert.equal(Number(f.node("max-values").min), 3);
  assert.equal(f.node("max-values").value, "3");
  await f.node("run-form").emit("submit");
  assert.equal(f.requests.at(-1).payload.limits.max_values, 3);
});

test("unsupported named values explain the browser limit without an impossible numeric field", async () => {
  const f = await fixture();
  f.node("max-values").max = "8";
  const metadata = declaredMetadata(); metadata.scope.values = Array.from({ length: 9 }, (_, index) => `v${index}`);
  await f.inspected(metadata);
  for (const mode of ["search", "check"]) {
    await f.mode(mode);
    assert.equal(f.node("run-button").disabled, true);
    assert.match(f.node("scope-note").textContent, /at most 8 values.*declares 9.*Python package/);
    assert.equal(f.node("max-values").min, 8);
    assert.equal(f.node("max-values").value, "8");
    const requests = f.requests.length;
    await f.node("run-form").emit("submit");
    assert.equal(f.requests.length, requests, "Implicit form submission cannot bypass the scope explanation");
  }
});

test("an oversized declared frame can still be used as a smaller-frame search template", async () => {
  const f = await fixture(); f.node("max-points").max = "6";
  const metadata = declaredMetadata(); metadata.scope.points = Array.from({ length: 7 }, (_, index) => `p${index}`);
  await f.inspected(metadata); await f.mode("check");
  assert.equal(f.node("run-button").disabled, true);
  assert.match(f.node("scope-note").textContent, /at most 6 participants.*declares 7.*Search for a model/);
  await f.mode("search");
  assert.equal(f.node("run-button").disabled, false);
  await f.node("run-form").emit("submit");
  assert.equal(f.requests.at(-1).type, "run");
});

test("scope guidance is rewritten only when its live announcement changes", async () => {
  const f = await fixture(); await f.inspected();
  const note = f.node("scope-note");
  let text = note.textContent, writes = 0;
  Object.defineProperty(note, "textContent", { get: () => text, set(value) { text = value; writes++; } });
  await f.node("properties-none").emit("click");
  await f.node("max-points").emit("change");
  assert.equal(writes, 0, "Unrelated changes should not repeat the scope announcement");
  await f.mode("check");
  assert.equal(writes, 1);
  assert.match(text, /quorum generators/);
  await f.node("properties-all").emit("click");
  assert.equal(writes, 1);
});

test("run summary explains property selection and axiom-only model finding", async () => {
  const f = await fixture(); await f.inspected();
  assert.equal(f.node("run-summary").textContent, "Test 2 properties against 2 retained axioms.");
  const axioms = f.node("axiom-options").querySelectorAll("input");
  axioms[0].checked = false; await axioms[0].emit("change");
  await f.node("properties-none").emit("click");
  assert.equal(f.node("run-summary").textContent, "No properties selected: find a model of the 1 retained axiom.");
  assert.match(f.node("run-button").textContent, /Find an axiom model/);
  await f.node("properties-all").emit("click");
  assert.equal(f.node("run-summary").textContent, "Test 2 properties against 1 retained axiom.");
  await f.node("axioms-all").emit("click");
  assert.equal(f.node("run-summary").textContent, "Test 2 properties against 2 retained axioms.");
});

test("source edits preserve deliberate property and axiom choices across inspection and reload", async () => {
  const f = await fixture(); await f.inspected();
  const properties = f.node("property-options").querySelectorAll("input");
  properties[1].checked = false; await properties[1].emit("change");
  const axioms = f.node("axiom-options").querySelectorAll("input");
  axioms[0].checked = false; await axioms[0].emit("change");
  for (const suffix of ["\nMore prose", "\nMore edits"]) {
    f.node("theory-editor").value += suffix;
    await f.node("theory-editor").emit("input");
  }
  assert.equal(f.node("run-button").disabled, false, "Changed source offers a usable path to refreshing the choices");
  assert.match(f.node("run-button").textContent, /^Update choices before/);
  await f.window.emit("beforeunload");
  const draft = JSON.parse(f.stored.get(key));
  assert.deepEqual(draft.properties, ["P"]);
  assert.deepEqual(draft.drop, ["A"]);
  await f.node("inspect-button").emit("click"); await f.inspected();
  await f.node("run-form").emit("submit");
  const payload = JSON.parse(JSON.stringify(f.requests.at(-1).payload));
  assert.deepEqual(payload.properties, ["P"]);
  assert.deepEqual(payload.drop, ["A"]);
  const restored = await fixture({ draft }); await restored.inspected();
  assert.equal(restored.node("property-options").querySelectorAll("input")[1].checked, false);
  assert.equal(restored.node("axiom-options").querySelectorAll("input")[0].checked, false);
});

test("reinspection removes obsolete choices while preserving an axiom-model investigation", async () => {
  const f = await fixture(); await f.inspected();
  await f.node("properties-none").emit("click");
  const axioms = f.node("axiom-options").querySelectorAll("input");
  axioms[0].checked = false; await axioms[0].emit("change");
  f.node("theory-editor").value += "\nEdited declarations";
  await f.node("theory-editor").emit("input");
  await f.node("inspect-button").emit("click");
  const metadata = declaredMetadata(); metadata.axioms.shift(); metadata.properties.push({ name: "New", formula: "t" });
  await f.inspected(metadata);
  await f.node("run-form").emit("submit");
  const payload = JSON.parse(JSON.stringify(f.requests.at(-1).payload));
  assert.deepEqual(payload.properties, []);
  assert.deepEqual(payload.drop, []);
});

test("importing a different theory starts with its own complete selection", async () => {
  const f = await fixture(); await f.inspected();
  await f.node("properties-none").emit("click");
  const axioms = f.node("axiom-options").querySelectorAll("input");
  axioms[0].checked = false; await axioms[0].emit("change");
  f.node("import-file").files = [{ size: theory.length, text: async () => theory }];
  await f.node("import-file").emit("change"); await f.inspected();
  await f.node("run-form").emit("submit");
  const payload = JSON.parse(JSON.stringify(f.requests.at(-1).payload));
  assert.deepEqual(payload.properties, ["P", "Q"]);
  assert.deepEqual(payload.drop, []);
});

test("hiding or leaving the page flushes the latest edit before the draft debounce", async () => {
  for (const event of ["visibilitychange", "pagehide"]) {
    const f = await fixture(); await f.inspected();
    f.node("theory-editor").value += "\nLatest unsaved edit";
    await f.node("theory-editor").emit("input");
    const before = f.writes.length;
    if (event === "visibilitychange") {
      await f.document.emit(event);
      assert.equal(f.writes.length, before, "Showing the page does not rewrite the draft");
      f.document.visibilityState = "hidden";
      await f.document.emit(event);
    } else await f.window.emit(event);
    assert.equal(f.writes.length, before + 1);
    assert.equal(JSON.parse(f.stored.get(key)).source, f.node("theory-editor").value);
  }
});

test("page lifecycle events preserve startup drafts and respect Forget draft", async () => {
  const failed = await fixture({ failure: "config.json" });
  failed.document.visibilityState = "hidden";
  await failed.document.emit("visibilitychange"); await failed.window.emit("pagehide");
  assert.deepEqual(failed.writes, []);
  assert.equal(JSON.parse(failed.stored.get(key)).source, theory);
  const f = await fixture(); await f.inspected();
  await f.node("forget-draft").emit("click");
  f.node("theory-editor").value += "\nPrivate unsaved edit";
  await f.node("theory-editor").emit("input");
  f.document.visibilityState = "hidden";
  await f.document.emit("visibilitychange"); await f.window.emit("pagehide");
  assert.equal(f.stored.has(key), false);
});

const protocolTheory = '```muql\ntheory "Protocol agreement"\npredicate decide/1\naxiom A: t\naxiom B: t\nproperty P: t\nproperty Q: f\n```\n';
const protocolExample = { id: "protocol", group: "Protocols", title: "Protocol · agreement", file: "protocol.md", mode: "search",
  description: "The protocol and all its axioms.", hint: "Investigate agreement.", properties: ["P"], bounds: { max_points: 3, max_values: 2 } };
const exampleFixture = { draft: null, examples: [tinyExample, protocolExample], files: { "protocol.md": protocolTheory } };
const protocolMetadata = () => ({ ...declaredMetadata(), name: "Protocol agreement", predicates: [{ name: "decide", arity: 1 }] });
function runResult(metadata = declaredMetadata()) {
  return {
    ok: true, metadata,
    report: {
      theory: metadata.name, status: "consistent", scope: metadata.scope,
      properties: [{ name: "P", status: "holds" }], stats: { seconds: 0.25 },
      bounds: { points: [1, 3], values: [2, 2], stages: [1, 2], max_quorums: 8, time: "finite" },
    },
    downloads: [
      { name: "report", filename: "old-report.json", content: '{"theory":"Saved work"}' },
      { name: "theory", filename: "old-theory.md", content: theory },
    ],
  };
}

test("choosing another example loads that theory immediately, before any run", async () => {
  const f = await fixture(exampleFixture); await f.inspected();
  assert.match(f.node("theory-signature").textContent, /Predicates: chosen\/1/);
  await f.choose("protocol");
  assert.equal(f.node("theory-editor").value, protocolTheory);
  assert.equal(f.node("example-select").value, "protocol");
  assert.equal(f.node("example-description").textContent, protocolExample.description);
  assert.equal(f.node("theory-origin").textContent, protocolExample.title);
  assert.equal(f.requests.at(-1).type, "inspect");
  assert.equal(f.requests.at(-1).payload.source, protocolTheory);
  assert.equal(f.node("run-button").disabled, true, "Wait for the new theory's declarations before running");
  await f.inspected(protocolMetadata());
  assert.equal(f.node("loaded-theory").textContent, "Protocol agreement");
  assert.equal(f.node("run-theory").textContent, "Theory to test: Protocol agreement");
  assert.match(f.node("claims-theory").textContent, /Protocol agreement/);
  assert.match(f.node("theory-signature").textContent, /Predicates: decide\/1/);
  assert.doesNotMatch(f.node("theory-signature").textContent, /chosen/);
  await f.node("run-form").emit("submit");
  assert.equal(f.requests.at(-1).payload.source, protocolTheory);
  assert.deepEqual(Array.from(f.requests.at(-1).payload.properties), ["P"]);
});

test("a pending example download cannot run the previous theory under a new selection", async () => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  const f = await fixture({ ...exampleFixture, fetchGate: { "protocol.md": pending } });
  await f.inspected();
  f.node("example-select").value = "protocol";
  const change = f.node("example-select").emit("change");
  await tick();
  assert.equal(f.node("theory-editor").value, theory);
  assert.equal(f.node("loaded-theory").textContent, "Saved work");
  assert.equal(f.node("run-button").disabled, true);
  const count = f.requests.length;
  await f.node("run-form").emit("submit");
  assert.equal(f.requests.length, count, "Submission is blocked even if triggered while the control is disabled");
  release(); await change; await tick();
  assert.equal(f.requests.at(-1).payload.source, protocolTheory);
});

test("cancelling replacement restores the custom selection and preserves the investigation", async () => {
  const f = await fixture({ ...exampleFixture, confirm: false }); await f.inspected();
  f.node("theory-editor").value += "\nMy explanation";
  await f.node("theory-editor").emit("input");
  await f.node("inspect-button").emit("click"); await f.inspected();
  const oldSource = f.node("theory-editor").value, oldDescription = f.node("example-description").textContent;
  const count = f.requests.length;
  await f.choose("protocol");
  assert.equal(f.confirms(), 1);
  assert.equal(f.node("example-select").value, "");
  assert.equal(f.node("theory-editor").value, oldSource);
  assert.equal(f.node("example-description").textContent, oldDescription);
  assert.equal(f.node("theory-origin").textContent, "Edited theory");
  assert.equal(f.requests.length, count);
  assert.equal(f.node("run-theory").textContent, "Theory to test: Saved work");
  assert.equal(f.node("run-button").disabled, false);
});

test("an example download failure restores the loaded selection and description", async () => {
  const f = await fixture({ ...exampleFixture, failure: "protocol.md" }); await f.inspected();
  await f.node("run-form").emit("submit"); await f.finished(runResult());
  const oldResult = f.node("results").firstChild;
  const count = f.requests.length;
  await f.choose("protocol");
  assert.equal(f.node("example-select").value, "tiny");
  assert.equal(f.node("theory-editor").value, theory);
  assert.equal(f.node("example-description").textContent, tinyExample.description);
  assert.equal(f.node("theory-origin").textContent, tinyExample.title);
  assert.equal(f.node("loaded-theory").textContent, "Saved work");
  assert.equal(f.node("run-button").disabled, false);
  assert.equal(f.requests.length, count);
  assert.match(textOf(f.node("error-box")), /Offline/);
  assert.equal(f.document.activeElement, f.node("error-box"), "The failure explanation takes focus priority");
  assert.equal(f.node("result-label").textContent, "Declared frame", "A failed replacement did not change the experiment");
  assert.equal(f.node("results").firstChild, oldResult);
});

test("edited, imported and restored source cannot masquerade as a bundled example", async () => {
  const edited = await fixture(exampleFixture); await edited.inspected();
  edited.node("theory-editor").value += "\nMy custom changes";
  await edited.node("theory-editor").emit("input");
  assert.equal(edited.node("example-select").value, "");
  assert.equal(edited.node("theory-origin").textContent, "Edited theory");
  assert.equal(edited.node("load-example").disabled, true);
  assert.notEqual(edited.node("example-description").textContent, tinyExample.description);
  await edited.window.emit("pagehide");
  assert.equal(JSON.parse(edited.stored.get(key)).example, undefined);

  const imported = await fixture(exampleFixture); await imported.inspected();
  imported.node("import-file").files = [{ name: "my-theory.md", size: protocolTheory.length, text: async () => protocolTheory }];
  await imported.node("import-file").emit("change"); await imported.inspected(protocolMetadata());
  assert.equal(imported.node("example-select").value, "");
  assert.equal(imported.node("theory-origin").textContent, "Opened file: my-theory.md");
  assert.equal(imported.node("run-theory").textContent, "Theory to test: Protocol agreement");
  assert.equal(imported.node("load-example").disabled, true);

  const restored = await fixture({ ...exampleFixture, draft: { source: theory, example: "protocol" } });
  await restored.inspected();
  assert.equal(restored.node("example-select").value, "");
  assert.equal(restored.node("theory-origin").textContent, "Saved draft");
  assert.equal(restored.node("run-theory").textContent, "Theory to test: Saved work");
  assert.equal(restored.node("load-example").disabled, true);
  assert.notEqual(restored.node("example-description").textContent, protocolExample.description);
});

test("a preset that removes an axiom identifies the actual theory and omitted assumption", async () => {
  const weakened = { ...protocolExample, id: "weakened", title: "Protocol · remove A", drop: ["A"] };
  const f = await fixture({ ...exampleFixture, examples: [tinyExample, protocolExample, weakened] }); await f.inspected();
  await f.choose("protocol"); await f.inspected(protocolMetadata());
  assert.equal(f.node("run-omissions").textContent, "All declared axioms are included.");
  await f.choose("weakened"); await f.inspected(protocolMetadata());
  assert.equal(f.node("theory-editor").value, protocolTheory);
  assert.equal(f.node("run-theory").textContent, "Theory to test: Protocol agreement");
  assert.equal(f.node("theory-origin").textContent, weakened.title);
  assert.equal(f.node("run-omissions").textContent, "Removed axioms: A.");
  await f.node("run-form").emit("submit");
  assert.deepEqual(Array.from(f.requests.at(-1).payload.drop), ["A"]);
});

test("changing an experiment closes old results with their own theory and download controls", async () => {
  const f = await fixture(exampleFixture); await f.inspected();
  await f.node("properties-none").emit("click");
  const property = f.node("property-options").querySelectorAll("input")[0]; property.checked = true; await property.emit("change");
  const axiom = f.node("axiom-options").querySelectorAll("input")[0]; axiom.checked = false; await axiom.emit("change");
  await f.node("run-form").emit("submit");
  const result = runResult(); result.metadata = { ...result.metadata, axioms: result.metadata.axioms.slice(1) };
  await f.finished(result);
  const rendered = textOf(f.node("results"));
  assert.match(rendered, /Theory tested: Saved work/);
  assert.match(rendered, /Properties tested: P/);
  assert.match(rendered, /Removed for this run: A/);
  const oldDownload = f.node("results").querySelector("#download-retained-theory");
  assert.ok(oldDownload);
  await f.choose("protocol"); await f.inspected(protocolMetadata());
  assert.equal(f.node("result-label").textContent, "Previous run");
  const previous = f.node("results").querySelector(".previous-results");
  assert.ok(previous, "Previous evidence is visually separated from the new experiment");
  assert.equal(previous.tagName, "DETAILS");
  assert.equal(previous.open, false);
  assert.match(textOf(previous), /Previous run · Saved work/);
  assert.match(textOf(previous), /Theory tested: Saved work/);
  assert.doesNotMatch(textOf(previous), /Theory tested: Protocol agreement/);
  assert.equal(previous.querySelector("#download-retained-theory"), oldDownload, "The old download remains attached to its old result");
  assert.match(textOf(f.node("results")), /No results for the current experiment/);
});

test("numeric input marks results as previous before the field loses focus", async () => {
  const f = await fixture({ draft: { source: theory, mode: "search", properties: ["P"], drop: [] } }); await f.inspected();
  await f.node("run-form").emit("submit"); await f.finished(runResult());
  f.node("max-points").value = "5";
  await f.node("max-points").emit("input");
  assert.equal(f.node("result-label").textContent, "Previous run");
  const previous = f.node("results").querySelector(".previous-results");
  assert.ok(previous);
  assert.match(textOf(previous), /1–3 participants/);
  assert.doesNotMatch(textOf(previous), /1–5 participants/);
  await f.node("max-points").emit("change");
  assert.equal(f.node("results").querySelectorAll("*").filter(node => node.className === "previous-results").length, 1,
    "Input and change events must not repeatedly wrap the same evidence");
});


test("property, axiom, mode and source changes each separate previous results from the current experiment", async () => {
  const changes = {
    async property(f) { await f.node("properties-none").emit("click"); },
    async axiom(f) {
      const input = f.node("axiom-options").querySelectorAll("input")[0];
      input.checked = false; await input.emit("change");
      assert.equal(f.node("run-omissions").textContent, "Removed axioms: A.");
    },
    async mode(f) { await f.mode("check"); },
    async source(f) { f.node("theory-editor").value += "\nAn edited theory"; await f.node("theory-editor").emit("input"); },
  };
  for (const [name, change] of Object.entries(changes)) {
    const f = await fixture({ draft: { source: theory, mode: "search", properties: ["P"], drop: [] } }); await f.inspected();
    await f.node("run-form").emit("submit"); await f.finished(runResult());
    await change(f);
    assert.equal(f.node("result-label").textContent, "Previous run", name);
    const previous = f.node("results").querySelector(".previous-results");
    assert.ok(previous, name);
    assert.equal(previous.open, false, name);
    assert.match(textOf(previous), /Properties tested: P/, name);
    assert.match(textOf(previous), /No axioms removed/, name);
    assert.match(textOf(previous), /1–3 participants/, name);
  }
});


test("adjusting assumptions clears preset guidance and Reset example restores all defaults", async () => {
  const f = await fixture(exampleFixture); await f.inspected();
  await f.choose("protocol"); await f.inspected(protocolMetadata());
  assert.equal(f.node("example-description").textContent, protocolExample.description);
  assert.equal(f.node("example-hint").textContent, protocolExample.hint);
  const axiom = f.node("axiom-options").querySelectorAll("input")[0];
  axiom.checked = false; await axiom.emit("change");
  assert.equal(f.node("example-select").value, "protocol");
  assert.equal(f.node("theory-origin").textContent, `Adjusted example · ${protocolExample.title}`);
  assert.notEqual(f.node("example-description").textContent, protocolExample.description);
  assert.equal(f.node("example-hint").textContent, "");
  assert.equal(f.node("run-omissions").textContent, "Removed axioms: A.");
  assert.equal(f.node("load-example").disabled, false, "Unedited preset source can be reset with its original settings");
  await f.node("load-example").emit("click"); await tick(); await f.inspected(protocolMetadata());
  assert.equal(f.node("example-select").value, "protocol");
  assert.equal(f.node("theory-origin").textContent, protocolExample.title);
  assert.equal(f.node("theory-editor").value, protocolTheory);
  assert.equal(f.node("example-description").textContent, protocolExample.description);
  assert.equal(f.node("example-hint").textContent, protocolExample.hint);
  assert.equal(f.node("run-omissions").textContent, "All declared axioms are included.");
  await f.node("run-form").emit("submit");
  assert.deepEqual(Array.from(f.requests.at(-1).payload.drop), []);
  assert.deepEqual(Array.from(f.requests.at(-1).payload.properties), ["P"]);
});


test("loading or resetting an example restores focus lost when its control was disabled", async () => {
  for (const control of ["example-select", "load-example"]) {
    const f = await fixture(exampleFixture); await f.inspected();
    f.node(control).focus();
    if (control === "example-select") await f.choose("protocol");
    else { await f.node(control).emit("click"); await tick(); }
    // Browsers may blur a disabled select/button to the body. Inspection is
    // still running, so simulate that browser effect before it completes.
    f.document.activeElement = f.document.body;
    await f.inspected(control === "example-select" ? protocolMetadata() : declaredMetadata());
    assert.equal(f.document.activeElement, f.node(control), control);
    assert.equal(f.node(control).disabled, false, control);
  }
});

test("completing an example load does not take focus from a user who moved elsewhere", async () => {
  for (const control of ["example-select", "load-example"]) {
    const f = await fixture(exampleFixture); await f.inspected();
    f.node(control).focus();
    if (control === "example-select") await f.choose("protocol");
    else { await f.node(control).emit("click"); await tick(); }
    f.node("source-details").focus();
    await f.inspected(control === "example-select" ? protocolMetadata() : declaredMetadata());
    assert.equal(f.document.activeElement, f.node("source-details"), control);
  }
});

test("Keep exploring follows the tour, ends at the custom section, and excludes custom source", async () => {
  const examples = [{ ...tinyExample, next: "protocol" }, { ...protocolExample, drop: ["B"] }];
  const f = await fixture({ ...exampleFixture, examples }); await f.inspected();
  f.node("max-points").value = "2"; await f.node("max-points").emit("input");
  await f.node("run-form").emit("submit"); await f.finished(runResult());
  const nextButton = () => f.node("results").querySelector(".next-example")?.children.find(child => child.tagName === "BUTTON");
  assert.equal(nextButton().textContent, protocolExample.title + " →");
  await nextButton().emit("click"); await tick(); await f.inspected(protocolMetadata());
  assert.equal(f.node("theory-editor").value, protocolTheory);
  assert.equal(f.node("example-select").value, "protocol");
  assert.equal(f.node("run-omissions").textContent, "Removed axioms: B.");
  assert.equal(f.node("max-points").value, "3");
  await f.node("run-form").emit("submit"); await f.finished(runResult(protocolMetadata()));
  assert.equal(nextButton().textContent, "Create your own theory →");
  const requestCount = f.requests.length;
  await nextButton().emit("click");
  assert.equal(f.requests.length, requestCount, "Finishing the tour navigates without replacing the current theory");
  assert.equal(f.document.activeElement, f.node("custom-experiment"));
  assert.equal(f.node("theory-editor").value, protocolTheory);
  f.node("theory-editor").value += "\nEdited tutorial\n";
  await f.node("theory-editor").emit("input");
  await f.node("inspect-button").emit("click"); await f.inspected();
  await f.node("run-form").emit("submit"); await f.finished(runResult());
  assert.equal(nextButton(), undefined);
});


test("each visit starts at First steps while curated exploration preserves a saved custom draft", async () => {
  const saved = { source: protocolTheory, properties: ["P"], drop: ["B"], limits: { timeout: 7 } };
  const f = await fixture({ ...exampleFixture, draft: saved, restore: false });
  assert.equal(f.node("example-select").value, "tiny");
  assert.equal(f.node("theory-editor").value, theory);
  assert.equal(f.node("restore-draft").hidden, false);
  await f.inspected();
  await f.window.emit("pagehide");
  await f.choose("protocol"); await f.inspected(protocolMetadata());
  await f.node("properties-none").emit("click");
  await f.window.emit("beforeunload");
  assert.deepEqual(JSON.parse(f.stored.get(key)), saved);
  assert.deepEqual(f.writes, [], "Neither startup, inspection, settings nor lifecycle events should replace saved custom work");
  await f.node("restore-draft").emit("click");
  assert.equal(f.node("theory-editor").value, protocolTheory);
  assert.equal(f.node("curated-picker").hidden, true);
  assert.equal(f.node("custom-context").hidden, false);
  assert.equal(f.node("source-details").open, true);
  await f.inspected(protocolMetadata());
  assert.equal(f.node("run-omissions").textContent, "Removed axioms: B.");
  assert.equal(f.node("timeout").value, "7");
  assert.equal(f.node("restore-draft").hidden, true);
});

test("both Load theory buttons open the same file picker and are locked while the engine is busy", async () => {
  const f = await fixture({ ...exampleFixture });
  for (const id of ["import-button", "load-source"]) assert.equal(f.node(id).disabled, true, id);
  await f.inspected();
  let opened = 0;
  f.node("import-file").addEventListener("click", () => opened++);
  for (const id of ["import-button", "load-source"]) {
    assert.equal(f.node(id).disabled, false, id);
    await f.node(id).emit("click");
  }
  assert.equal(opened, 2);
  await f.node("run-form").emit("submit");
  for (const id of ["import-button", "load-source", "create-theory", "restore-draft"]) assert.equal(f.node(id).disabled, true, id);
});

test("loading a file can be cancelled without losing current edits or a separate saved draft", async () => {
  for (const edited of [false, true]) {
    const f = await fixture({ ...exampleFixture, draft: { source: protocolTheory }, restore: false, confirm: false });
    await f.inspected();
    if (edited) { f.node("theory-editor").value += "\nMy unfinished edit"; await f.node("theory-editor").emit("input"); }
    const before = f.node("theory-editor").value;
    let read = false;
    f.node("import-file").files = [{ name: "other.md", size: 5, text: async () => { read = true; return "other"; } }];
    await f.node("import-file").emit("change");
    assert.equal(f.confirms(), 1);
    assert.equal(read, false);
    assert.equal(f.node("theory-editor").value, before);
    assert.equal(JSON.parse(f.stored.get(key)).source, protocolTheory);
  }
});

test("Create a theory opens an editable custom starter and returning to the tour preserves it", async () => {
  const f = await fixture(exampleFixture); await f.inspected();
  await f.node("create-theory").emit("click");
  const starter = f.node("theory-editor").value;
  assert.match(starter, /theory "My theory"/);
  assert.match(starter, /property Claim: p/);
  assert.equal(f.node("curated-picker").hidden, true);
  assert.equal(f.node("source-details").open, true);
  assert.equal(f.document.activeElement, f.node("theory-editor"));
  await f.inspected({ ...declaredMetadata(), name: "My theory" });
  await f.node("return-examples").emit("click"); await tick(); await f.inspected();
  assert.equal(f.node("example-select").value, "tiny");
  assert.equal(f.node("curated-picker").hidden, false);
  assert.equal(f.node("custom-context").hidden, true);
  assert.equal(JSON.parse(f.stored.get(key)).source, starter);
  assert.equal(f.node("restore-draft").hidden, false);
});

test("a saved draft is protected when cancelling creation of a new theory", async () => {
  const f = await fixture({ ...exampleFixture, draft: { source: protocolTheory }, restore: false, confirm: false });
  await f.inspected();
  await f.node("create-theory").emit("click");
  assert.equal(f.confirms(), 1);
  assert.equal(f.node("theory-editor").value, theory);
  assert.equal(JSON.parse(f.stored.get(key)).source, protocolTheory);
  assert.equal(f.node("curated-picker").hidden, false);
});


test("returning to First steps flushes custom edits before a pending autosave", async () => {
  const f = await fixture(exampleFixture); await f.inspected();
  const edited = theory + "\nAn edit made just before leaving the editor";
  f.node("theory-editor").value = edited; await f.node("theory-editor").emit("input");
  assert.equal(f.stored.has(key), false, "Autosave has not fired yet");
  await f.node("return-examples").emit("click"); await tick(); await f.inspected();
  assert.equal(f.node("theory-editor").value, theory);
  assert.equal(JSON.parse(f.stored.get(key)).source, edited);
  await f.window.emit("pagehide");
  assert.equal(JSON.parse(f.stored.get(key)).source, edited);
});

test("loading unedited files or a just-downloaded source does not claim there are unsaved edits", async () => {
  const f = await fixture(exampleFixture); await f.inspected();
  for (const source of [protocolTheory, theory]) {
    f.node("import-file").files = [{ name: "theory.md", size: source.length, text: async () => source }];
    await f.node("import-file").emit("change"); await f.inspected();
  }
  assert.equal(f.confirms(), 0, "Unedited imported files already have a copy on the device");
  f.node("theory-editor").value += "\nA new edit"; await f.node("theory-editor").emit("input");
  await f.node("save-source").emit("click");
  await f.node("return-examples").emit("click"); await tick(); await f.inspected();
  assert.equal(f.confirms(), 0, "Save theory marks the downloaded source as saved");
});

test("undoing every source edit restores the curated example without resetting deliberate settings", async () => {
  const f = await fixture(exampleFixture); await f.inspected();
  await f.choose("protocol"); await f.inspected(protocolMetadata());
  await f.node("properties-none").emit("click");
  const property = f.node("property-options").querySelectorAll("input")[1];
  property.checked = true; await property.emit("change");
  const axiom = f.node("axiom-options").querySelectorAll("input")[0];
  axiom.checked = false; await axiom.emit("change");
  f.node("max-points").value = "5"; await f.node("max-points").emit("input");
  await f.mode("check");
  const requests = f.requests.length;
  f.node("theory-editor").value += "\nAn experimental change"; await f.node("theory-editor").emit("input");
  assert.equal(f.node("curated-picker").hidden, true);
  await f.node("save-source").emit("click");
  f.node("theory-editor").value = protocolTheory; await f.node("theory-editor").emit("input");
  assert.equal(f.requests.length, requests, "The original declarations were already read successfully");
  assert.equal(f.node("example-select").value, "protocol");
  assert.equal(f.node("curated-picker").hidden, false);
  assert.equal(f.node("custom-context").hidden, true);
  assert.equal(f.node("theory-options").hidden, false);
  assert.equal(f.node("theory-origin").textContent, `Adjusted example · ${protocolExample.title}`);
  assert.equal(f.node("max-points").value, "5");
  assert.equal(f.node("mode-check").checked, true);
  assert.equal(f.node("run-button").type, "submit");
  assert.doesNotMatch(f.node("status-text").textContent, /Update.*choices/);
  const writes = f.writes.length;
  await f.window.emit("pagehide");
  assert.equal(f.writes.length, writes, "Restored curated source must no longer overwrite the separate custom draft");
  await f.node("run-form").emit("submit");
  assert.deepEqual(Array.from(f.requests.at(-1).payload.properties), ["Q"]);
  assert.deepEqual(Array.from(f.requests.at(-1).payload.drop), ["A"]);
});

test("undo restores the exact last preset when two curated examples share one source file", async () => {
  const weakened = { ...protocolExample, id: "weakened", title: "Protocol · remove B", drop: ["B"] };
  const f = await fixture({ ...exampleFixture, examples: [tinyExample, protocolExample, weakened] }); await f.inspected();
  await f.choose("weakened"); await f.inspected(protocolMetadata());
  f.node("theory-editor").value += "\nTemporary edit"; await f.node("theory-editor").emit("input");
  f.node("theory-editor").value = protocolTheory; await f.node("theory-editor").emit("input");
  assert.equal(f.node("example-select").value, "weakened");
  assert.equal(f.node("theory-origin").textContent, weakened.title);
  assert.equal(f.node("example-description").textContent, weakened.description);
  assert.equal(f.node("run-omissions").textContent, "Removed axioms: B.");
  await f.node("run-form").emit("submit");
  assert.deepEqual(Array.from(f.requests.at(-1).payload.properties), ["P"]);
  assert.deepEqual(Array.from(f.requests.at(-1).payload.drop), ["B"]);
});

test("explicitly opened or restored custom source never acquires a preset merely by matching its text", async () => {
  for (const origin of ["import", "restore"]) {
    const f = await fixture({ ...exampleFixture, draft: origin === "restore" ? { source: theory } : null, restore: false });
    await f.inspected();
    if (origin === "import") {
      f.node("import-file").files = [{ name: "my-copy.md", size: theory.length, text: async () => theory }];
      await f.node("import-file").emit("change");
    } else await f.node("restore-draft").emit("click");
    await f.inspected();
    f.node("theory-editor").value += "\nTemporary change"; await f.node("theory-editor").emit("input");
    f.node("theory-editor").value = theory; await f.node("theory-editor").emit("input");
    assert.equal(f.node("example-select").value, "", origin);
    assert.equal(f.node("curated-picker").hidden, true, origin);
    assert.equal(f.node("custom-context").hidden, false, origin);
    assert.match(f.node("run-button").textContent, /^Update choices before/, origin);
  }
});

test("undo after reading edited declarations restores original metadata and surviving choices", async () => {
  const f = await fixture(exampleFixture); await f.inspected();
  await f.choose("protocol"); await f.inspected(protocolMetadata());
  f.node("theory-editor").value = protocolTheory.replace("predicate decide/1", "predicate changed/2");
  await f.node("theory-editor").emit("input");
  await f.node("refresh-choices").emit("click");
  const editedMetadata = { ...protocolMetadata(), name: "Edited protocol", predicates: [{ name: "changed", arity: 2 }],
    properties: [...declaredMetadata().properties, { name: "OnlyInEditedSource", formula: "t" }] };
  await f.inspected(editedMetadata);
  const newProperty = f.node("property-options").querySelectorAll("input")[2];
  newProperty.checked = true; await newProperty.emit("change");
  const axiom = f.node("axiom-options").querySelectorAll("input")[0];
  axiom.checked = false; await axiom.emit("change");
  f.node("theory-editor").value = protocolTheory; await f.node("theory-editor").emit("input");
  assert.equal(f.node("example-select").value, "protocol");
  assert.equal(f.node("loaded-theory").textContent, "Protocol agreement");
  assert.match(f.node("theory-signature").textContent, /decide\/1/);
  assert.doesNotMatch(f.node("theory-signature").textContent, /changed/);
  assert.deepEqual(f.node("property-options").querySelectorAll("input").map(input => input.value), ["P", "Q"]);
  await f.node("run-form").emit("submit");
  assert.equal(f.requests.at(-1).payload.source, protocolTheory);
  assert.deepEqual(Array.from(f.requests.at(-1).payload.properties), ["P"]);
  assert.deepEqual(Array.from(f.requests.at(-1).payload.drop), ["A"]);
});

test("undo identifies an adjusted preset if a selected property disappeared during custom inspection", async () => {
  const f = await fixture(exampleFixture); await f.inspected();
  await f.choose("protocol"); await f.inspected(protocolMetadata());
  f.node("theory-editor").value = protocolTheory.replace("property P: t\n", "");
  await f.node("theory-editor").emit("input");
  await f.node("refresh-choices").emit("click");
  await f.inspected({ ...protocolMetadata(), properties: [{ name: "Q", formula: "f" }] });
  assert.deepEqual(f.node("property-options").querySelectorAll("input:checked"), []);
  f.node("theory-editor").value = protocolTheory; await f.node("theory-editor").emit("input");
  assert.equal(f.node("example-select").value, "protocol");
  assert.equal(f.node("theory-origin").textContent, `Adjusted example · ${protocolExample.title}`);
  assert.notEqual(f.node("example-description").textContent, protocolExample.description);
  assert.equal(f.node("example-hint").textContent, "");
  assert.match(f.node("run-summary").textContent, /^No properties selected/);
  await f.node("run-form").emit("submit");
  assert.deepEqual(Array.from(f.requests.at(-1).payload.properties), []);
});

test("saving an edit then undoing it keeps the curated Keep exploring route", async () => {
  const f = await fixture({ ...exampleFixture, examples: [{ ...tinyExample, next: "protocol" }, protocolExample] });
  await f.inspected();
  f.node("theory-editor").value += "\nSaved variation"; await f.node("theory-editor").emit("input");
  await f.node("custom-save-source").emit("click");
  f.node("theory-editor").value = theory; await f.node("theory-editor").emit("input");
  await f.node("run-form").emit("submit"); await f.finished(runResult());
  const next = f.node("results").querySelector(".next-example")?.children.find(child => child.tagName === "BUTTON");
  assert.ok(next, "The saved download baseline must not decide whether curated navigation exists");
  assert.equal(next.textContent, protocolExample.title + " →");
  await next.emit("click"); await tick(); await f.inspected(protocolMetadata());
  assert.equal(f.node("example-select").value, "protocol");
  assert.equal(f.confirms(), 0, "Returning to the bundled source leaves no custom source to discard");
});

test("custom Save theory downloads the same exact source as the editor button and marks it saved", async () => {
  const f = await fixture(exampleFixture); await f.inspected();
  f.node("theory-editor").value += "\nUnicode ∃ꟴ◇ and my latest edit"; await f.node("theory-editor").emit("input");
  for (const id of ["save-source", "custom-save-source"]) await f.node(id).emit("click");
  assert.equal(f.downloads.length, 2);
  for (const blob of f.downloads) assert.equal(await blob.text(), f.node("theory-editor").value);
  await f.node("reset-custom").emit("click"); await tick(); await f.inspected();
  assert.equal(f.confirms(), 0, "A downloaded theory does not require a warning about unsaved changes");
});

test("both custom return controls restore the last curated preset and flush the latest custom draft", async () => {
  for (const control of ["reset-custom", "return-examples"]) {
    const f = await fixture(exampleFixture); await f.inspected();
    await f.choose("protocol"); await f.inspected(protocolMetadata());
    await f.node("create-theory").emit("click"); await f.inspected({ ...declaredMetadata(), name: "My theory" });
    const edited = f.node("theory-editor").value + "\nMy newest custom note";
    f.node("theory-editor").value = edited; await f.node("theory-editor").emit("input");
    await f.node(control).emit("click"); await tick(); await f.inspected(protocolMetadata());
    assert.equal(f.node("example-select").value, "protocol", control);
    assert.equal(f.node("theory-editor").value, protocolTheory, control);
    assert.equal(f.node("curated-picker").hidden, false, control);
    assert.equal(f.node("restore-draft").hidden, false, control);
    assert.equal(JSON.parse(f.stored.get(key)).source, edited, control);
    await f.window.emit("pagehide");
    assert.equal(JSON.parse(f.stored.get(key)).source, edited, control);
  }
});

test("cancelling custom Reset preserves source and choices, and a failed reset still preserves the latest draft", async () => {
  let consent = false, failReset = false;
  const f = await fixture({ ...exampleFixture, confirm: () => consent, failure: name => failReset && name === "protocol.md" });
  await f.inspected(); await f.choose("protocol"); await f.inspected(protocolMetadata());
  const edited = protocolTheory + "\nKeep my unfinished work";
  f.node("theory-editor").value = edited; await f.node("theory-editor").emit("input");
  await f.node("refresh-choices").emit("click"); await f.inspected(protocolMetadata());
  await f.node("properties-none").emit("click");
  const requests = f.requests.length;
  await f.node("reset-custom").emit("click"); await tick();
  assert.equal(f.confirms(), 1);
  assert.equal(f.node("theory-editor").value, edited);
  assert.equal(f.node("custom-context").hidden, false);
  assert.equal(f.requests.length, requests);
  consent = true; failReset = true;
  await f.node("reset-custom").emit("click"); await tick();
  assert.equal(f.node("theory-editor").value, edited);
  assert.equal(f.node("custom-context").hidden, false);
  assert.equal(f.requests.length, requests);
  assert.equal(JSON.parse(f.stored.get(key)).source, edited);
  assert.deepEqual(JSON.parse(f.stored.get(key)).properties, []);
  assert.match(textOf(f.node("error-box")), /Offline/);
  assert.equal(f.document.activeElement, f.node("error-box"));
});

test("stale Run and Continue actions lead to the visible refresh button before native bound validation", async () => {
  for (const mode of ["search", "check"]) {
    const f = await fixture({ draft: { source: theory, mode } }); await f.inspected();
    f.node("theory-editor").value += "\nA new source edit"; await f.node("theory-editor").emit("input");
    assert.equal(f.node("run-button").disabled, false, mode);
    assert.equal(f.node("run-button").type, "button", "A stale action must bypass browser validation before submit is dispatched");
    assert.match(f.node("run-button").textContent, mode === "check" ? /^Update choices before checking/ : /^Update choices before finding a counterexample/);
    assert.match(f.node("continue-settings").textContent, /^Update choices/);
    assert.doesNotMatch(f.node("status-text").textContent, /^Ready\./);
    assert.equal(f.node("theory-options").hidden, true);
    assert.equal(f.node("refresh-choices").hidden, false);
    f.node("max-points").value = "-1";
    f.node("run-form").reportValidity = () => { throw new Error("Stale bounds must not block the path to Update choices"); };
    const requests = f.requests.length;
    for (const [id, event] of [["run-button", "click"], ["run-form", "submit"], ["continue-settings", "click"]]) {
      f.document.activeElement = f.document.body;
      await f.node(id).emit(event);
      assert.equal(f.requests.length, requests, `${mode}: ${id} must not submit or silently inspect stale source`);
      assert.equal(f.document.activeElement, f.node("refresh-choices"), `${mode}: ${id}`);
      assert.ok(f.scrolls.some(node => node.id === "refresh-choices" || node.id === "workspace" || node.id === "selection-prompt"), "Bring the refresh action into view");
    }
    await f.node("refresh-choices").emit("click");
    assert.equal(f.requests.at(-1).type, "inspect");
    assert.equal(f.requests.at(-1).payload.source, f.node("theory-editor").value);
    assert.equal(f.node("run-button").disabled, true, "Reading still locks the workflow");
    assert.equal(f.node("continue-settings").disabled, true);
    await f.inspected();
    assert.equal(f.node("run-button").type, "submit");
    assert.equal(f.node("run-button").disabled, false);
    assert.match(f.node("continue-settings").textContent, /^Continue to run/);
    assert.match(f.node("status-text").textContent, /^Ready\./);
    let validityChecks = 0;
    f.node("run-form").reportValidity = () => { validityChecks++; return false; };
    const inspectedRequests = f.requests.length;
    await f.node("run-form").emit("submit");
    assert.equal(validityChecks, 1, "Fresh source must still validate its run settings");
    assert.equal(f.requests.length, inspectedRequests, "Invalid fresh settings cannot start a run");
  }
});

test("refresh guidance stays coherent for axiom-model searches, failed reads, and an empty theory", async () => {
  const f = await fixture(); await f.inspected();
  await f.node("properties-none").emit("click");
  f.node("theory-editor").value += "\nMalformed source"; await f.node("theory-editor").emit("input");
  assert.match(f.node("run-button").textContent, /^Update choices before finding an axiom model/);
  await f.node("refresh-choices").emit("click"); await f.inspectionFailed();
  assert.equal(f.node("run-button").disabled, false);
  assert.equal(f.node("run-button").type, "button");
  assert.match(f.node("selection-message").textContent, /could not be read/);
  assert.doesNotMatch(f.node("status-text").textContent, /^Ready\./);
  assert.match(textOf(f.node("error-box")), /Malformed formula/);
  await f.node("run-button").emit("click");
  assert.equal(f.document.activeElement, f.node("refresh-choices"));
  f.node("theory-editor").value = " \n"; await f.node("theory-editor").emit("input");
  for (const id of ["run-button", "continue-theory", "continue-settings", "refresh-choices"]) assert.equal(f.node(id).disabled, true, id);
  assert.doesNotMatch(f.node("status-text").textContent, /^(Ready\.|The request could not)/);
  const requests = f.requests.length;
  await f.node("run-form").emit("submit");
  assert.equal(f.requests.length, requests);
});
