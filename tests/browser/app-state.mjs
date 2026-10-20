/** Startup, run settings and draft checks for the real page controller with DOM/network doubles.
 * Run: node tests/browser/app-state.mjs. These do not test browser rendering.
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import { randomUUID } from "node:crypto";

const source = (await readFile(new URL("../../web/app.js", import.meta.url), "utf8"))
  .replace(/^import .* from "\.\/editor\.js";$/m, "")
  .replace(/^import .* from "\.\/model-view\.js";$/m, "")
  .replace(/^import .* from "\.\/model-data\.js";$/m, "")
  .replace(/^import .* from "\.\/notation\.js";$/m, "")
  .replace(/^import .* from "\.\/progress\.js";$/m, "")
  .replaceAll("import.meta.url", '"https://example.test/muql-explorer/app.js"');
const legacyKey = "muql-explorer-draft-v1";
const key = `${legacyKey}:/muql-explorer/`;
const modelSource = await readFile(new URL("../../web/model-data.js", import.meta.url), "utf8");
const { atomLabel, nameLabel } = await import(`data:text/javascript;base64,${Buffer.from(modelSource).toString("base64")}`);
const notationSource = await readFile(new URL("../../web/notation.js", import.meta.url), "utf8");
const { formulaHTML } = await import(`data:text/javascript;base64,${Buffer.from(notationSource).toString("base64")}`);
const progressSource = await readFile(new URL("../../web/progress.js", import.meta.url), "utf8");
const progressHelpers = await import(`data:text/javascript;base64,${Buffer.from(progressSource).toString("base64")}`);
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
  examples = [tinyExample], files = {}, confirm = true, fetchGate = {}, restore = true,
  sharedStorage, appPath = "/muql-explorer/", storageFailure = false, insecureCrypto = false } = {}) {
  const nodes = new Map(), stored = sharedStorage || new Map(), writes = [], requests = [], timers = new Map(), intervals = new Map(), workers = [], downloads = [], scrolls = [], timerDelays = [];
  let timerId = 0, confirms = 0, activeElement, now = 0;
  const focused = node => { activeElement = node; };
  const scopedKey = `${legacyKey}:${appPath}`;
  if (draft !== null && !stored.has(scopedKey)) stored.set(scopedKey, JSON.stringify(draft));
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
  node("timeout").max = "";
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
    crypto: insecureCrypto ? {} : { randomUUID }, atomLabel, nameLabel, ...progressHelpers,
    URL: class extends URL {
      static createObjectURL(blob) { downloads.push(blob); return `blob:download-${downloads.length}`; }
      static revokeObjectURL() {}
    }, Blob, performance: { now: () => now }, console,
    createSourceHighlighter: () => ({ refresh() {}, sync() {} }),
    formulaHTML,
    document,
    window, location: { protocol: "https:" }, matchMedia: () => ({ matches: true }),
    localStorage: {
      get length() { return stored.size; },
      key: index => [...stored.keys()][index] ?? null,
      getItem: name => stored.get(name) ?? null,
      setItem(name, text) { if (storageFailure) throw new Error("Storage unavailable"); stored.set(name, text); if (name === scopedKey) writes.push(text); },
      removeItem(name) { stored.delete(name); },
    },
    setTimeout(callback, delay) { const id = ++timerId; timerDelays.push(delay); timers.set(id, { callback, at: now + delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    setInterval(callback, delay) { const id = ++timerId; intervals.set(id, { callback, delay, at: now + delay }); return id; },
    clearInterval(id) { intervals.delete(id); }, AbortController,
    Worker: class {
      constructor() { Object.assign(this, target()); workers.push(this); }
      postMessage(request) { requests.push(request); }
      terminate() { this.terminated = true; }
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
  vm.runInContext(source.replaceAll('https://example.test/muql-explorer/app.js', `https://example.test${appPath}app.js`), context, { filename: "web/app.js" });
  await tick();
  // Most state tests exercise custom work. Explicitly take the user action
  // after First steps loads; startup tests pass restore:false to inspect it.
  if (restore && draft && !failure && !gate) {
    const request = requests.at(-1);
    await workers.at(-1).emit("message", { data: { id: request.id, type: "result", result: { ok: true, metadata: declaredMetadata() } } });
    await node("restore-draft").emit("click");
  }
  return {
    node, window, document, stored, writes, requests, downloads, scrolls, workers, timerDelays, confirms: () => confirms,
    advance(milliseconds) {
      const end = now + milliseconds;
      while (true) {
        const next = [...timers.entries(), ...intervals.entries()].filter(([, value]) => value.at <= end).sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
        if (!next) break;
        const [id, timer] = next;
        now = timer.at;
        if (intervals.has(id)) timer.at += timer.delay;
        else timers.delete(id);
        timer.callback();
      }
      now = end;
    },
    async message(data, worker = workers.at(-1)) {
      await worker.emit("message", { data: { id: requests.at(-1).id, ...data } });
    },
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

test("symbolic labels survive checkbox selection, draft restoration and the worker request", async () => {
  const metadata = declaredMetadata();
  metadata.axioms[0].name = "PaxWrite?";
  metadata.axioms[1].name = "PaxWrite!";
  metadata.properties[0].name = "Goal?";
  metadata.properties[1].name = "Goal!";
  const f = await fixture(); await f.inspected(metadata);
  const properties = f.node("property-options").querySelectorAll("input");
  properties[1].checked = false; await properties[1].emit("change");
  const axioms = f.node("axiom-options").querySelectorAll("input");
  axioms[0].checked = false; await axioms[0].emit("change");
  await f.window.emit("beforeunload");
  const draft = JSON.parse(f.stored.get(key));
  assert.deepEqual(draft.properties, ["Goal?"]);
  assert.deepEqual(draft.drop, ["PaxWrite?"]);
  const restored = await fixture({ draft }); await restored.inspected(metadata);
  assert.equal(restored.node("property-options").querySelectorAll("input")[1].checked, false);
  assert.equal(restored.node("axiom-options").querySelectorAll("input")[1].checked, true);
  await restored.node("run-form").emit("submit");
  const payload = JSON.parse(JSON.stringify(restored.requests.at(-1).payload));
  assert.deepEqual(payload.properties, ["Goal?"]);
  assert.deepEqual(payload.drop, ["PaxWrite?"]);
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
  assert.deepEqual(JSON.parse(f.stored.get(key)), { forgotten: true });
});

test("closing an unchanged tab cannot replace a newer draft from another tab", async () => {
  const sharedStorage = new Map();
  const a = await fixture({ sharedStorage }); await a.inspected();
  const b = await fixture({ sharedStorage }); await b.inspected();
  const fresh = theory.replace("Saved work", "New work in A");
  a.node("theory-editor").value = fresh; await a.node("theory-editor").emit("input");
  await a.window.emit("pagehide");
  const writes = b.writes.length;
  for (const event of ["pagehide", "beforeunload"]) await b.window.emit(event);
  b.document.visibilityState = "hidden"; await b.document.emit("visibilitychange");
  assert.equal(b.writes.length, writes);
  assert.equal(JSON.parse(sharedStorage.get(key)).source, fresh);
});

test("concurrent dirty tabs preserve both sources and recover settings without replacing the main draft", async () => {
  const sharedStorage = new Map();
  const a = await fixture({ sharedStorage }); await a.inspected();
  const b = await fixture({ sharedStorage }); await b.inspected();
  const first = theory.replace("Saved work", "A edits"), second = theory.replace("Saved work", "B edits");
  for (const [f, text] of [[a, first], [b, second]]) {
    f.node("theory-editor").value = text; await f.node("theory-editor").emit("input");
    f.node("timeout").value = f === b ? "17" : "11";
    await f.window.emit("pagehide");
  }
  assert.equal(JSON.parse(sharedStorage.get(key)).source, first);
  assert.match(b.node("draft-status").textContent, /Another tab/);
  assert.equal(b.node("draft-recovery").hidden, false);
  const copies = [...sharedStorage.entries()].filter(([name]) => name.startsWith(`${key}:copy:`)).map(([, data]) => JSON.parse(data).draft);
  assert.ok(copies.some(copy => copy.source === first));
  assert.ok(copies.some(copy => copy.source === second && copy.limits.timeout === 17));
  // A fresh visit can download or restore the losing tab's complete work.
  const reopened = await fixture({ sharedStorage, restore: false }); await reopened.inspected();
  const restore = reopened.node("draft-recovery-actions").children.find(node => node.textContent === "Restore recovery copy 1");
  await restore.emit("click"); await reopened.inspected();
  assert.equal(reopened.node("theory-editor").value, second);
  assert.equal(reopened.node("timeout").value, "17");
  assert.equal(JSON.parse(sharedStorage.get(key)).source, first);
});

test("drafts from separate project paths cannot overwrite each other", async () => {
  const sharedStorage = new Map();
  const a = await fixture({ sharedStorage }); await a.inspected();
  const b = await fixture({ sharedStorage, appPath: "/different-project/" }); await b.inspected();
  b.node("theory-editor").value = theory.replace("Saved work", "Other project");
  await b.node("theory-editor").emit("input"); await b.window.emit("pagehide");
  assert.equal(JSON.parse(sharedStorage.get(key)).source, theory);
  assert.match(JSON.parse(sharedStorage.get(`${legacyKey}:/different-project/`)).source, /Other project/);
});

test("legacy drafts migrate without deletion and scoped Forget suppresses remigration", async () => {
  const legacy = JSON.stringify({ source: theory, highlight: false, limits: { timeout: 7 } });
  const sharedStorage = new Map([[legacyKey, legacy]]);
  const f = await fixture({ sharedStorage, draft: null, restore: false }); await f.inspected();
  assert.equal(f.node("restore-draft").hidden, false);
  await f.node("restore-draft").emit("click"); await f.inspected();
  assert.equal(JSON.parse(sharedStorage.get(key)).source, theory);
  assert.equal(sharedStorage.get(legacyKey), legacy);
  await f.node("forget-draft").emit("click");
  assert.equal([...sharedStorage.keys()].some(name => name.startsWith(`${key}:copy:`)), false);
  const fresh = await fixture({ sharedStorage, draft: null, restore: false }); await fresh.inspected();
  assert.equal(fresh.node("restore-draft").hidden, true);
  assert.equal(sharedStorage.get(legacyKey), legacy);
});

test("full recovery storage retains every copy and leaves unsaved work editable with guidance", async () => {
  const sharedStorage = new Map(Array.from({ length: 20 }, (_, index) => [`${key}:copy:${index}`,
    JSON.stringify({ savedAt: "2026-10-15", draft: { source: theory + index } })]));
  const before = new Map(sharedStorage);
  const f = await fixture({ sharedStorage }); await f.inspected();
  f.node("theory-editor").value = theory + "\nLatest unsaved edit";
  await f.node("theory-editor").emit("input"); await f.window.emit("pagehide");
  assert.match(f.node("draft-status").textContent, /recovery storage is full/);
  assert.match(f.node("theory-editor").value, /Latest unsaved edit/);
  assert.equal(f.node("theory-editor").readOnly, false);
  for (const [name, value] of before) assert.equal(sharedStorage.get(name), value);
  assert.equal([...sharedStorage.keys()].filter(name => name.startsWith(`${key}:copy:`)).length, 20);
});

test("storage failure leaves the open source editable and offers an explicit download fallback", async () => {
  const f = await fixture({ storageFailure: true }); await f.inspected();
  assert.match(f.node("draft-status").textContent, /Draft not saved.*Save theory/);
  assert.equal(f.node("theory-editor").value, theory);
  assert.equal(f.node("theory-editor").readOnly, false);
});

test("custom drafts remain usable on plain HTTP without crypto.randomUUID", async () => {
  const f = await fixture({ insecureCrypto: true }); await f.inspected();
  f.node("theory-editor").value = theory + "\nSaved without secure-context crypto";
  await f.node("theory-editor").emit("input"); await f.window.emit("pagehide");
  assert.match(JSON.parse(f.stored.get(key)).source, /Saved without secure-context crypto/);
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

const searchProgress = (overrides = {}) => ({ phase: "consistency", frame: 3,
  points: 2, values: 2, stages: 1, quorums: 2,
  frames_completed: 2, frames_consistent: 1, frames_inconsistent: 0, frames_unknown: 1,
  counterexamples_found: 0, variables: 12, clauses: 30, ...overrides });

async function running({ timeout = 600, mode = "search" } = {}) {
  const f = await fixture({ draft: { source: theory, mode, limits: { timeout } } });
  await f.inspected(); await f.node("run-form").emit("submit");
  await f.message({ type: "started" });
  return f;
}

test("progress parsing accepts only usable snapshots and never invents unavailable counts", () => {
  const { readProgress } = progressHelpers;
  for (const value of [null, [], "phase", {}, { phase: "finished" },
    { phase: "compiling", frame: 0 }, { phase: "compiling", points: -1 },
    { phase: "compiling", variables: Infinity }, { phase: "property", property: null },
    { phase: "property", property: "" }, { phase: "property", decisions: 1.1 },
    { phase: "frame", frames_completed: Number.MAX_SAFE_INTEGER + 1 },
    { phase: "frame", frames_consistent: "2" }]) assert.equal(readProgress(value), null);
  assert.deepEqual(readProgress({ phase: "compiling", variables: 0, clauses: 0, extra: "ignored" }),
    { phase: "compiling", variables: 0, clauses: 0 });
  assert.equal(readProgress(searchProgress({ frames_completed: 1 }), searchProgress()), null);
  assert.equal(readProgress(searchProgress({ counterexamples_found: 0 }), searchProgress({ counterexamples_found: 1 })), null);
});

test("live progress appears at the controls, results, and activity bar before completion", async () => {
  const f = await running();
  const focus = f.document.activeElement, scrolls = f.scrolls.length;
  await f.message({ type: "progress", progress: searchProgress() });
  assert.equal(f.node("run-progress").hidden, false);
  assert.match(f.node("progress-phase").textContent, /axioms have a model/);
  assert.match(f.node("progress-frame").textContent, /Frame 3: 2 participants · 2 values · 1 time stage · 2 quorums/);
  assert.match(f.node("progress-counts").textContent, /2 frames completed · 1 frame with an axiom model/);
  assert.match(f.node("progress-note").textContent, /axiom model can also have incomplete checks/);
  assert.match(textOf(f.node("results")), /2 frames completed/);
  assert.match(f.node("activity-detail").textContent, /2 frames completed · run 0s · limit 600s/);
  assert.equal(f.node("run-controls").disabled, true);
  assert.equal(f.node(".results-panel").getAttribute("aria-busy"), "true");
  assert.equal(f.document.activeElement, focus);
  assert.equal(f.scrolls.length, scrolls, "Progress must not navigate or steal focus");
  f.advance(4500);
  assert.match(f.node("progress-timing").textContent, /Run elapsed 4s.*4s in this phase/);
  assert.equal(f.node("progress-counts").textContent, "2 frames completed · 1 frame with an axiom model · 0 inconsistent · 1 with incomplete checks");
  assert.match(f.node("progress-work").textContent, /12 solver variables · 30 clauses/);
  assert.doesNotMatch(f.node("progress-work").textContent, /decisions/);
});

test("phase clocks reset for a new phase, property, or candidate size but not repeated counters", async () => {
  const f = await running();
  await f.message({ type: "progress", progress: searchProgress() });
  f.advance(3000);
  await f.message({ type: "progress", progress: searchProgress({ frames_completed: 3 }) });
  assert.match(f.node("progress-timing").textContent, /3s in this phase/);
  f.advance(500);
  await f.message({ type: "progress", progress: searchProgress({ phase: "property", property: "P", frames_completed: 3 }) });
  f.advance(1500);
  assert.match(f.node("progress-phase").textContent, /property “P”/);
  assert.match(f.node("progress-timing").textContent, /Run elapsed 5s.*1s in this phase/);
  await f.message({ type: "progress", progress: searchProgress({ phase: "property", property: "Q", frames_completed: 3 }) });
  f.advance(500);
  assert.match(f.node("progress-timing").textContent, /0s in this phase/);
  await f.message({ type: "progress", progress: { phase: "enumerating", points: 3, values: 2, stages: 1 } });
  f.advance(2000);
  assert.match(f.node("progress-frame").textContent, /^Candidate size: 3 participants/);
  await f.message({ type: "progress", progress: { phase: "enumerating", points: 4, values: 2, stages: 1 } });
  f.advance(500);
  assert.match(f.node("progress-frame").textContent, /^Candidate size: 4 participants/);
  assert.match(f.node("progress-timing").textContent, /0s in this phase/);
});

test("visual clocks update without frequent live announcements", async () => {
  const f = await running();
  const starting = f.node("status-text").textContent;
  await f.message({ type: "progress", progress: searchProgress() });
  f.advance(4500);
  assert.equal(f.node("status-text").textContent, starting);
  f.advance(500);
  const announced = f.node("status-text").textContent;
  assert.match(announced, /axioms have a model.*2 frames completed/);
  await f.message({ type: "progress", progress: searchProgress({ phase: "property", property: "P" }) });
  f.advance(4500);
  assert.equal(f.node("status-text").textContent, announced);
  f.advance(500);
  assert.match(f.node("status-text").textContent, /property “P”/);
  const unchanged = f.node("status-text").textContent;
  f.advance(10000);
  assert.equal(f.node("status-text").textContent, unchanged, "Clock-only changes are not announcements");
});

test("rapid progress is coalesced while Stop retains the most recent unpainted snapshot", async () => {
  const f = await running();
  await f.message({ type: "progress", progress: searchProgress() });
  const first = f.node("progress-counts").textContent;
  for (let frames = 3; frames <= 1000; frames++) {
    await f.message({ type: "progress", progress: searchProgress({ frames_completed: frames, frame: frames + 1 }) });
  }
  assert.equal(f.node("progress-counts").textContent, first, "Burst events must not repaint every snapshot");
  await f.node("stop-button").emit("click");
  assert.match(f.node("progress-counts").textContent, /^1000 frames completed/);
  assert.match(textOf(f.node("results")), /1000 frames completed/);
});

test("coalesced updates catch up on the visual clock during a long synchronous phase", async () => {
  const f = await running();
  await f.message({ type: "progress", progress: searchProgress() });
  await f.message({ type: "progress", progress: searchProgress({ phase: "property", property: "Long check" }) });
  f.advance(500);
  assert.match(f.node("progress-phase").textContent, /Long check/);
  f.advance(2000);
  assert.match(f.node("progress-timing").textContent, /2s in this phase/);
});

test("manual Stop freezes observed progress without exposing a witness or claiming completion", async () => {
  const f = await running();
  await f.message({ type: "progress", progress: searchProgress({ phase: "replaying", counterexamples_found: 1 }) });
  f.advance(1500);
  const worker = f.workers.at(-1), id = f.requests.at(-1).id;
  await f.node("floating-stop").emit("click");
  assert.equal(worker.terminated, true);
  assert.equal(f.node("result-label").textContent, "Incomplete");
  assert.match(textOf(f.node("results")), /Incomplete · stopped.*Last phase: Independently verifying/s);
  assert.match(f.node("progress-findings").textContent, /Verified counterexamples reported: 1/);
  assert.match(textOf(f.node("results")), /No downloadable witness or report was returned/);
  assert.equal(f.node("results").querySelectorAll("*").some(node => node.tagName === "BUTTON"), false);
  assert.equal(f.node("run-controls").disabled, false);
  assert.equal(f.node(".results-panel").getAttribute("aria-busy"), "false");
  const frozen = textOf(f.node("results")), timing = f.node("progress-timing").textContent;
  f.advance(20000);
  await f.message({ id, type: "progress", progress: searchProgress({ frames_completed: 10 }) }, worker);
  await f.message({ id, type: "result", result: runResult() }, worker);
  assert.equal(textOf(f.node("results")), frozen);
  assert.equal(f.node("progress-timing").textContent, timing);
  assert.equal(f.downloads.length, 0);
});

test("a new run clears interrupted progress and rejects messages from the terminated worker", async () => {
  const f = await running();
  await f.message({ type: "progress", progress: searchProgress({ counterexamples_found: 1 }) });
  const oldWorker = f.workers.at(-1), oldId = f.requests.at(-1).id;
  await f.node("stop-button").emit("click");
  f.node("timeout").value = "700"; await f.node("timeout").emit("input");
  assert.equal(f.node("run-progress").hidden, true);
  assert.equal(f.node("result-label").textContent, "Previous interrupted run");
  await f.node("run-form").emit("submit"); await f.message({ type: "started" });
  assert.equal(f.node("progress-counts").hidden, true);
  assert.match(f.node("progress-findings").textContent, /No verified counterexample update/);
  await f.message({ type: "progress", progress: searchProgress() }, oldWorker);
  await f.message({ id: oldId, type: "progress", progress: searchProgress() });
  assert.equal(f.node("progress-counts").hidden, true);
  assert.equal(f.node("result-label").textContent, "Running");
  await f.message({ type: "progress", progress: { phase: "validating" } });
  assert.match(f.node("progress-phase").textContent, /validating/);
});

test("malformed and stale progress cannot alter a current run or unlock its controls", async () => {
  const f = await running();
  await f.message({ type: "progress", progress: searchProgress() });
  const counts = f.node("progress-counts").textContent;
  for (const progress of [null, [], { phase: "complete" }, searchProgress({ points: NaN }),
    searchProgress({ frames_completed: 1 }), searchProgress({ counterexamples_found: -1 }),
    searchProgress({ property: 12 })]) {
    await f.message({ type: "progress", progress });
  }
  await f.message({ id: -1, type: "progress", progress: searchProgress({ frames_completed: 10 }) });
  f.advance(500);
  assert.equal(f.node("progress-counts").textContent, counts);
  assert.equal(f.node("run-controls").disabled, true);
});

test("inspection ignores run progress and keeps its own startup clock", async () => {
  const f = await fixture();
  await f.message({ type: "started" });
  await f.message({ type: "progress", progress: searchProgress() });
  f.advance(3000);
  assert.equal(f.node("run-progress").hidden, true);
  assert.match(f.node("activity-detail").textContent, /Reading elapsed 3s · separate 90s limit/);
  assert.equal(f.node("run-controls").disabled, true);
  await f.inspected();
  assert.equal(f.node("run-controls").disabled, false);
});

test("fixed-frame progress and report preparation omit unavailable search counters", async () => {
  const f = await running({ mode: "check" });
  await f.message({ type: "progress", progress: { phase: "compiling", points: 3, values: 2, stages: 2, quorums: 3 } });
  assert.match(f.node("progress-frame").textContent, /^Current frame: 3 participants/);
  assert.equal(f.node("progress-counts").hidden, true);
  assert.equal(f.node("progress-work").hidden, true);
  assert.match(f.node("progress-findings").textContent, /No verified counterexample update yet/);
  f.advance(100);
  await f.message({ type: "progress", progress: { phase: "preparing_results", counterexamples_found: 1 } });
  assert.equal(f.node("progress-phase").textContent, "Preparing reports and downloads");
  assert.equal(f.node("result-label").textContent, "Running");
  assert.match(f.node("progress-findings").textContent, /Verified counterexamples reported: 1/);
  assert.equal(f.node("results").querySelectorAll("*").some(node => node.tagName === "BUTTON"), false);
  await f.finished(runResult());
  assert.equal(f.node("run-progress").hidden, true);
  assert.equal(f.node("results").querySelector("#result-progress"), null);
  const result = textOf(f.node("results"));
  await f.message({ type: "progress", progress: { phase: "compiling" } });
  assert.equal(textOf(f.node("results")), result);
  assert.equal(f.node("run-progress").hidden, true);
});

test("startup has a separate 90-second limit and does not consume the chosen run budget", async () => {
  const f = await fixture({ draft: { source: theory, limits: { timeout: 10 } } });
  await f.inspected(); await f.node("run-form").emit("submit");
  f.advance(80000);
  assert.match(f.node("progress-timing").textContent, /Startup elapsed 1m 20s.*chosen run limit 10s starts after loading/);
  await f.message({ type: "started" });
  await f.message({ type: "progress", progress: { phase: "compiling" } });
  f.advance(10000);
  assert.equal(f.node("result-label").textContent, "Running", "Allow the completed report one second to serialize");
  assert.match(f.node("progress-timing").textContent, /Run elapsed 10s/);
  f.advance(1000);
  assert.equal(f.node("result-label").textContent, "Incomplete");
  assert.match(textOf(f.node("results")), /time limit reached.*Last phase: Building/s);
  assert.match(f.node("progress-timing").textContent, /Run elapsed 11s/);
});

test("a stalled startup stops at 90 seconds regardless of a long run budget", async () => {
  const f = await fixture({ draft: { source: theory, limits: { timeout: 600 } } });
  await f.inspected(); await f.node("run-form").emit("submit");
  f.advance(89999);
  assert.equal(f.node("result-label").textContent, "Running");
  f.advance(1);
  assert.equal(f.node("result-label").textContent, "Incomplete");
  assert.match(textOf(f.node("results")), /engine took too long to start/);
  assert.match(f.node("progress-timing").textContent, /Startup elapsed 1m 30s/);
});

test("duplicate started messages do not reset the run clock or watchdog", async () => {
  const f = await running({ timeout: 10 });
  f.advance(9000); await f.message({ type: "started" });
  f.advance(2000);
  assert.equal(f.node("result-label").textContent, "Incomplete");
  assert.match(f.node("progress-timing").textContent, /Run elapsed 11s/);
});

test("saved long and extreme finite time limits restore and use bounded watchdog slices", async () => {
  for (const timeout of [600, 2147484, Number.MAX_VALUE]) {
    const f = await running({ timeout });
    assert.equal(Number(f.node("timeout").value), timeout);
    assert.equal(f.requests.at(-1).payload.limits.timeout, timeout);
    f.advance(120000);
    assert.equal(f.node("result-label").textContent, "Running");
    assert.ok(f.timerDelays.every(delay => Number.isFinite(delay) && delay > 0 && delay <= 60000));
    await f.finished(runResult());
    assert.equal(f.node("run-controls").disabled, false);
  }
  const { deadlineDelay } = progressHelpers;
  assert.equal(deadlineDelay(Number.MAX_VALUE, 120), 60000);
  assert.equal(deadlineDelay(600, 590), 10000);
  assert.equal(deadlineDelay(600, 600, 1), 1000);
  assert.equal(deadlineDelay(600, 601, 1), 0);
  assert.equal(deadlineDelay(Number.MIN_VALUE, 0), 1);
});

test("the page accepts positive fractional budgets and rejects nonfinite or nonpositive scripted values", async () => {
  const html = await readFile(new URL("../../web/index.html", import.meta.url), "utf8");
  const input = html.match(/<input id="timeout"[^>]+>/)[0];
  assert.doesNotMatch(input, /\bmax=/);
  assert.match(input, /step="any"/);
  const f = await fixture(); await f.inspected();
  const before = f.requests.length;
  for (const value of ["", "0", "-1", "Infinity", "NaN", "1e999"]) {
    f.node("timeout").value = value;
    await f.node("run-form").emit("submit");
    assert.equal(f.requests.length, before, value);
    assert.match(textOf(f.node("error-box")), /finite number of seconds greater than zero/);
  }
  f.node("timeout").value = "0.000001";
  await f.node("run-form").emit("submit"); await f.message({ type: "started" });
  assert.equal(f.requests.length, before + 1);
  f.advance(2000);
  assert.equal(f.node("result-label").textContent, "Incomplete");
});

test("an unexpected worker failure retains its last progress as incomplete", async () => {
  const f = await running();
  await f.message({ type: "progress", progress: searchProgress() });
  await f.workers.at(-1).emit("error");
  assert.equal(f.node("result-label").textContent, "Incomplete");
  assert.match(textOf(f.node("results")), /engine stopped before returning a result.*2 frames completed/s);
  assert.match(f.node("progress-note").textContent, /No downloadable witness or report was returned/);
});
