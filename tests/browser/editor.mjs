/**
 * Editor state checks using DOM doubles, not browser rendering.
 * Run: node tests/browser/editor.mjs
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const highlighterSource = await readFile(new URL("../../web/highlight.js", import.meta.url), "utf8");
const { highlightSource } = await import(`data:text/javascript;base64,${Buffer.from(highlighterSource).toString("base64")}`);
const controllerSource = (await readFile(new URL("../../web/editor.js", import.meta.url), "utf8"))
  .replace(/^import \{ highlightSource \} from "\.\/highlight\.js";$/m, "")
  .replaceAll("export function ", "function ");

const positions = vm.createContext({});
vm.runInContext(controllerSource, positions);
const sourceSelection = (...args) => [...positions.sourceSelection(...args)];

test("parser positions select whole Unicode characters after supplementary values", () => {
  const source = '```muql\nproperty Broken: p("😀") => p("😀")\n```';
  const column = [...source.split("\n")[1].split("=>")[0]].length + 1;
  const offset = source.indexOf("=>");
  assert.deepEqual(sourceSelection(source, 2, column), [offset, offset + 1]);
  const emoji = source.indexOf("😀");
  assert.deepEqual(sourceSelection(source, 2, [...source.slice(source.indexOf("\n") + 1, emoji)].length + 1), [emoji, emoji + 2]);
});

test("parser positions follow every Python splitlines separator and clamp at line ends", () => {
  for (const separator of ["\n", "\r", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"]) {
    const source = `😀 notes${separator}abc${separator}last`;
    const offset = source.indexOf("abc");
    assert.deepEqual(sourceSelection(source, 2, 2), [offset + 1, offset + 2]);
    assert.deepEqual(sourceSelection(source, 2, 1000), [offset + 3, offset + 3]);
    assert.deepEqual(sourceSelection(source, 1000, 1), [source.length, source.length]);
  }
  assert.deepEqual(sourceSelection("", 1, 1), [0, 0]);
  assert.deepEqual(sourceSelection("abc\n", 2, 1), [4, 4]);
});

function eventTarget(properties = {}) {
  const listeners = new Map();
  return Object.assign({
    addEventListener(type, listener) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(listener);
    },
    emit(type) {
      for (const listener of listeners.get(type) || []) listener({ type, target: this });
    },
  }, properties);
}

function visible(html) {
  return html.replace(/<\/?span(?: class="syntax-[a-z]+")?>/g, "")
    .replace(/&(amp|lt|gt|quot|#39);/g, (_, entity) => ({ amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'" })[entity]);
}

function mount({ value = "# My theory\n\n```muql\nproperty Example: ∃⁰¹ x. p(x)\n```\n", checked = true, forced = false, resizeObserver = true } = {}) {
  const classes = new Set();
  const frame = { classList: { add: name => classes.add(name), remove: name => classes.delete(name) } };
  const editor = eventTarget({
    parentElement: frame, value, clientWidth: 640, clientHeight: 320,
    scrollTop: 39, scrollLeft: 7, selectionStart: 4, selectionEnd: 9, selectionDirection: "backward",
  });
  const layer = { hidden: true, style: {}, scrollTop: 0, scrollLeft: 0 };
  let html = "", htmlWrites = 0;
  const code = {
    rejectHTML: false,
    get innerHTML() { return html; },
    set innerHTML(value) {
      htmlWrites++;
      if (this.rejectHTML) throw new Error("DOM insertion unavailable");
      html = value;
    },
    replaceChildren() { html = ""; },
  };
  const toggle = eventTarget({ checked, disabled: false });
  const disclosure = eventTarget();
  const forcedColors = eventTarget({ matches: forced });
  const window = eventTarget();
  let nextFrame = 0, observedElement, observerCallback;
  const pendingFrames = new Map();
  const context = {
    highlightSource, window,
    matchMedia(query) {
      assert.equal(query, "(forced-colors: active)");
      return forcedColors;
    },
    requestAnimationFrame(callback) {
      const id = ++nextFrame;
      pendingFrames.set(id, callback);
      return id;
    },
    cancelAnimationFrame(id) { pendingFrames.delete(id); },
    ResizeObserver: resizeObserver ? class {
      constructor(callback) { observerCallback = callback; }
      observe(element) { observedElement = element; }
    } : undefined,
  };
  vm.createContext(context);
  vm.runInContext(controllerSource, context, { filename: "web/editor.js" });
  const controller = context.createSourceHighlighter({ editor, layer, code, toggle, disclosure });
  return {
    editor, layer, code, toggle, disclosure, forcedColors, window, controller,
    get highlighted() { return classes.has("syntax-highlighted"); },
    get writes() { return htmlWrites; },
    get pending() { return pendingFrames.size; },
    flushFrame() {
      const callbacks = [...pendingFrames.values()];
      pendingFrames.clear();
      for (const callback of callbacks) callback();
    },
    resize() {
      assert.equal(observedElement, editor);
      observerCallback();
    },
  };
}

function nativeState(editor) {
  return {
    value: editor.value,
    selectionStart: editor.selectionStart,
    selectionEnd: editor.selectionEnd,
    selectionDirection: editor.selectionDirection,
    scrollTop: editor.scrollTop,
    scrollLeft: editor.scrollLeft,
  };
}

function assertPlain(state) {
  assert.equal(state.highlighted, false, "native source must be visible");
  assert.equal(state.layer.hidden, true, "stale decoration must be hidden");
  assert.equal(state.code.innerHTML, "", "stale decoration must be cleared");
}

function assertHighlighted(state) {
  assert.equal(state.highlighted, true);
  assert.equal(state.layer.hidden, false);
  assert.equal(visible(state.code.innerHTML), state.editor.value + "\n", "decoration must reproduce the current source");
}

test("mount and typing decorate exact source without changing the native editor", () => {
  const state = mount({ value: "# <Theory> & notes\n\n```muql\nproperty P: p ⇀ q\n```\n" });
  const before = nativeState(state.editor);
  assertHighlighted(state);
  assert.ok(state.code.innerHTML.includes("&lt;Theory&gt; &amp; notes"));
  assert.deepEqual(nativeState(state.editor), before);
  state.editor.value += "\nAnother `unfinished";
  state.editor.emit("input");
  const afterTyping = nativeState(state.editor);
  state.flushFrame();
  assertHighlighted(state);
  assert.deepEqual(nativeState(state.editor), afterTyping);
});

test("plain-text toggle preserves source, selection and scroll when switched off and on", () => {
  const state = mount();
  const before = nativeState(state.editor);
  state.toggle.checked = false;
  state.toggle.emit("change");
  assertPlain(state);
  assert.deepEqual(nativeState(state.editor), before);
  state.toggle.checked = true;
  state.toggle.emit("change");
  assertHighlighted(state);
  assert.deepEqual(nativeState(state.editor), before);
  assert.equal(state.layer.scrollTop, before.scrollTop);
  assert.equal(state.layer.scrollLeft, before.scrollLeft);
});

test("composition uses native text immediately, then decorates the completed input", () => {
  const state = mount();
  state.editor.value += "∃";
  state.editor.emit("input");
  assert.equal(state.pending, 1);
  state.editor.emit("compositionstart");
  assert.equal(state.pending, 0, "a pending paint must not overwrite composition fallback");
  assertPlain(state);
  state.editor.value += "¹";
  state.editor.emit("input");
  state.flushFrame();
  assertPlain(state);
  state.editor.emit("compositionend");
  assertHighlighted(state);
});

test("forced colours selects native text, including changes while editing", () => {
  const state = mount({ forced: true });
  assertPlain(state);
  state.forcedColors.matches = false;
  state.forcedColors.emit("change");
  assertHighlighted(state);
  state.forcedColors.matches = true;
  state.forcedColors.emit("change");
  assertPlain(state);
  state.editor.value = "Changed in forced colours";
  state.editor.emit("input");
  state.flushFrame();
  assertPlain(state);
  state.forcedColors.matches = false;
  state.forcedColors.emit("change");
  assertHighlighted(state);
});

test("empty, oversized and null-containing input fall back and recover without losing source", () => {
  const state = mount();
  for (const source of ["", "x".repeat(250001), "before\u0000after"]) {
    state.editor.value = source;
    const before = nativeState(state.editor);
    state.editor.emit("input");
    state.flushFrame();
    assertPlain(state);
    assert.deepEqual(nativeState(state.editor), before);
    state.editor.value = "# Recovered";
    state.editor.emit("input");
    state.flushFrame();
    assertHighlighted(state);
  }
});

test("dense token input is rejected before oversized decoration reaches the DOM", () => {
  const state = mount();
  const writes = state.writes;
  state.editor.value = "```muql\n" + "∧".repeat(60000) + "\n```";
  assert.ok(state.editor.value.length < 250000);
  state.editor.emit("input");
  state.flushFrame();
  assertPlain(state);
  assert.equal(state.writes, writes, "oversized markup must not be inserted first");
  assert.equal(state.editor.value, "```muql\n" + "∧".repeat(60000) + "\n```");
  state.editor.value = "# Small again";
  state.controller.refresh();
  assertHighlighted(state);
});

test("decoration insertion failure restores native text and can recover on refresh", () => {
  const state = mount();
  state.code.rejectHTML = true;
  state.editor.value = "# Updated after paint failure";
  const before = nativeState(state.editor);
  state.editor.emit("input");
  state.flushFrame();
  assertPlain(state);
  assert.deepEqual(nativeState(state.editor), before);
  state.code.rejectHTML = false;
  state.controller.refresh();
  assertHighlighted(state);
  assert.deepEqual(nativeState(state.editor), before);
});

test("scroll and both resize paths match the textarea viewport without repainting", () => {
  const state = mount();
  const writes = state.writes;
  assert.deepEqual(state.layer.style, { width: "640px", height: "320px" });
  state.editor.scrollTop = 112;
  state.editor.scrollLeft = 23;
  state.editor.emit("scroll");
  assert.equal(state.layer.scrollTop, 112);
  assert.equal(state.layer.scrollLeft, 23);
  state.editor.clientWidth = 401;
  state.editor.clientHeight = 225;
  state.resize();
  assert.deepEqual(state.layer.style, { width: "401px", height: "225px" });
  state.editor.clientWidth = 290;
  state.window.emit("resize");
  assert.equal(state.layer.style.width, "290px");
  assert.equal(state.writes, writes);
});

test("rapid input coalesces into one paint of the latest source", () => {
  const state = mount();
  const writes = state.writes;
  for (const text of ["First", "Second", "Latest ∃⁰¹"]) {
    state.editor.value = text;
    state.editor.emit("input");
  }
  assert.equal(state.pending, 1);
  assert.equal(state.writes, writes);
  state.flushFrame();
  assert.equal(state.pending, 0);
  assert.equal(state.writes, writes + 1);
  assertHighlighted(state);
  state.editor.emit("input");
  state.flushFrame();
  assert.equal(state.writes, writes + 1, "unchanged source does not require DOM replacement");
});

test("an explicit refresh cancels a pending paint and disclosure refreshes programmatic changes", () => {
  const state = mount();
  state.editor.value = "Typing";
  state.editor.emit("input");
  state.editor.value = "# Loaded from an example";
  state.disclosure.emit("toggle");
  assert.equal(state.pending, 0);
  assertHighlighted(state);
  const writes = state.writes;
  state.flushFrame();
  assert.equal(state.writes, writes);
});

test("without ResizeObserver the native editor remains available and highlighting is disabled", () => {
  const state = mount({ resizeObserver: false });
  assertPlain(state);
  assert.equal(state.toggle.checked, false);
  assert.equal(state.toggle.disabled, true);
  state.editor.value = "I can still edit";
  state.editor.emit("input");
  state.flushFrame();
  assertPlain(state);
  assert.equal(state.editor.value, "I can still edit");
});
