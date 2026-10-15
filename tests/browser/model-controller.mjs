/** Diagram controller checks with DOM doubles; these do not test rendering.
 * Run: node tests/browser/model-controller.mjs
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const sources = await Promise.all(["model-data", "model-svg", "model-view"].map(name => readFile(new URL(`../../web/${name}.js`, import.meta.url), "utf8")));
const source = sources.map(text => text.replace(/^import .*;\n/gm, "").replace(/^export /gm, "")).join("\n");

function fixture(model, { width = 800, resizeObserver = true, fullModelAction = false } = {}) {
  const env = { width, fontSize: 16, frames: new Map(), observers: [], downloads: [], fullModelRequests: 0, frameId: 0 };
  class Element {
    constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.attributes = new Map(); this.listeners = new Map(); this.parentNode = null; this.hidden = false; this.disabled = false; this.className = ""; this.style = {}; this._text = ""; this._value = undefined; }
    get textContent() { return this._text + this.children.map(child => child.textContent).join(""); }
    set textContent(text) { this.replaceChildren(); this._text = String(text); }
    set innerHTML(_) { throw new Error("The model controller must not insert HTML strings"); }
    get value() { return this._value ?? (this.tagName === "SELECT" ? this.children[0]?.value ?? "" : ""); }
    set value(value) { this._value = String(value); }
    append(...children) {
      for (let child of children) {
        if (typeof child !== "object") { const text = new Element("#text"); text.textContent = child; child = text; }
        child.parentNode = this; this.children.push(child);
      }
    }
    replaceChildren(...children) {
      if (this.children.some(child => child.contains(document.activeElement))) document.activeElement = document.body;
      for (const child of this.children) child.parentNode = null;
      this.children = []; this._text = ""; this.append(...children);
    }
    contains(node) { return node === this || this.children.some(child => child.contains(node)); }
    setAttribute(name, value) { this.attributes.set(name, String(value)); }
    getAttribute(name) { return this.attributes.get(name) ?? null; }
    getBoundingClientRect() { return { width: env.width }; }
    addEventListener(name, listener) { if (!this.listeners.has(name)) this.listeners.set(name, new Set()); this.listeners.get(name).add(listener); }
    removeEventListener(name, listener) { this.listeners.get(name)?.delete(listener); }
    emit(name) { if (this.disabled && name === "click") return; for (const listener of this.listeners.get(name) || []) listener({ type: name, target: this }); }
    focus() { if (!this.disabled) document.activeElement = this; }
    querySelector(selector) {
      const match = /^\[(data-stage|data-atom-index)="(\d+)"\]$/.exec(selector);
      if (!match) throw new Error(`Unhandled selector in DOM double: ${selector}`);
      return descendants(this).find(node => node.getAttribute(match[1]) === match[2]) || null;
    }
  }
  const document = { activeElement: null, createElement: tag => new Element(tag), createTextNode: text => { const node = new Element("#text"); node.textContent = text; return node; } };
  document.body = new Element("body"); document.activeElement = document.body;
  const window = new Element("window");
  const context = vm.createContext({ document, window, console, URL, Blob, setTimeout, getComputedStyle: () => ({ fontSize: `${env.fontSize}px` }),
    requestAnimationFrame(callback) { const id = ++env.frameId; env.frames.set(id, callback); return id; },
    cancelAnimationFrame(id) { env.frames.delete(id); },
    ResizeObserver: resizeObserver ? class {
      constructor(callback) { this.callback = callback; this.disconnected = false; env.observers.push(this); }
      observe(target) { this.target = target; }
      disconnect() { this.disconnected = true; }
    } : undefined,
  });
  vm.runInContext(source, context, { filename: "web/model-view.js (with its real data/SVG dependencies)" });
  const root = context.createModelView(model, { propertyName: model?.property || "Property", onDownload: (...args) => env.downloads.push(args),
    ...(fullModelAction ? { onShowFullModel: () => { env.fullModelRequests++; } } : {}) });
  document.body.append(root);
  return Object.assign(env, { root, document, window,
    all: predicate => descendants(root).filter(predicate),
    find: predicate => descendants(root).find(predicate),
    control(label) {
      const field = descendants(root).find(node => node.tagName === "LABEL" && node.textContent === label);
      assert.ok(field, `Missing label ${label}`);
      const control = descendants(root).find(node => node.id === field.htmlFor);
      assert.ok(control, `Label ${label} has no associated control`); return control;
    },
    button(label) { const node = descendants(root).find(node => node.tagName === "BUTTON" && (node.getAttribute("aria-label") || node.textContent) === label); assert.ok(node, `Missing button ${label}`); return node; },
    get map() { return descendants(root).find(node => node.className === "model-map"); },
    flush() { const callbacks = [...env.frames.values()]; env.frames.clear(); callbacks.forEach(callback => callback()); },
    resize(nextWidth) { env.width = nextWidth; if (env.observers.length) env.observers.filter(observer => !observer.disconnected).forEach(observer => observer.callback()); else window.emit("resize"); },
  });
}
function descendants(root) { return root.children.flatMap(child => [child, ...descendants(child)]); }
function model({ points = ["a", "b", "c"], stages = 3, atoms = ["vote"], failure = true } = {}) {
  const result = { property: "Agreement", scope: { points, values: ["red"], stages, time: "finite", quorums: [[points[0]], [...points]] }, valuation: [] };
  if (failure) result.failure = { time: stages - 1, point: points.at(-1), quorum: [points[0]], value: "f" };
  for (const [atomNumber, predicate] of atoms.entries()) for (let time = 0; time < stages; time++) for (const [pointNumber, point] of points.entries()) {
    result.valuation.push({ predicate, args: [], time, point, value: ["t", "b", "f"][(pointNumber + time + atomNumber) % 3] });
  }
  return result;
}
function change(control, value) { control.value = value; control.emit("change"); }
function selectAtom(f, label) {
  const select = f.control("Atoms shown"), option = select.children.find(node => node.textContent === label);
  assert.ok(option, `Missing atom option ${label}`); change(select, option.value);
}
function svgOf(f) { return decodeURIComponent(f.map.src.slice(f.map.src.indexOf(",") + 1)); }
function overviewCells(f) {
  return [...svgOf(f).matchAll(/data-atom-index="(\d+)" data-value="([tbf?])"/g)].map(match => [Number(match[1]), match[2]]);
}
function visibleSvgText(svg) {
  // Values in <desc>/<title> alone do not constitute a visible diagram.
  return [...svg.matchAll(/<text\b[^>]*>([\s\S]*?)<\/text>/g)].map(match => match[1].replace(/<[^>]+>/g, "")).join("\n");
}
async function witness(name) { return JSON.parse(await readFile(new URL(`../../reports/${name}.countermodel.json`, import.meta.url), "utf8")); }

test("initial diagram uses the recorded failure while including participants outside its quorum", () => {
  const original = model(), before = JSON.stringify(original), f = fixture(original);
  assert.equal(f.control("Stage").value, "2"); assert.equal(f.control("Quorum highlighted").value, "0");
  assert.equal(f.button("Return to failing context").disabled, true);
  selectAtom(f, "vote");
  assert.match(f.map.alt, /a: f \(false\); member of Q1/);
  assert.match(f.map.alt, /b: t \(true\); not a member of Q1/);
  assert.match(f.map.alt, /c: b \(broken\); not a member of Q1; recorded property failure here/);
  assert.equal(JSON.stringify(original), before, "Read-only inspection changed its source model");
});

test("stage and quorum changes update context without inventing property failures", () => {
  const f = fixture(model());
  selectAtom(f, "vote");
  change(f.control("Quorum highlighted"), "1");
  assert.doesNotMatch(f.map.alt, /recorded property failure here/);
  assert.match(f.map.alt, /c: b \(broken\); member of Q2/);
  change(f.control("Stage"), "0");
  assert.match(f.map.alt, /c: f \(false\)/);
  assert.equal(f.button("Return to failing context").disabled, false);
  f.button("Return to failing context").emit("click");
  assert.equal(f.control("Stage").value, "2"); assert.equal(f.control("Quorum highlighted").value, "0");
  assert.match(f.map.alt, /recorded property failure here/);
});

test("large scopes use a bounded stage input and reject blank or invalid stage edits", () => {
  const f = fixture(model({ stages: 201 }));
  const stage = f.control("Stage");
  assert.equal(stage.tagName, "INPUT");
  assert.equal(stage.type, "number");
  assert.equal(stage.min, "0"); assert.equal(stage.max, "200");
  assert.equal(stage.value, "200");
  const before = svgOf(f);
  for (const invalid of ["", " ", "-1", "201", "1.5", "Infinity", "not a number"]) {
    change(stage, invalid);
    assert.equal(stage.value, "200", `Invalid stage ${JSON.stringify(invalid)} changed the view`);
    assert.equal(svgOf(f), before);
  }
  change(stage, "137");
  assert.equal(stage.value, "137");
  assert.match(f.map.alt, /View at stage 137/);
  selectAtom(f, "vote");
  assert.match(f.find(node => node.className === "model-time-details").textContent, /Showing stages 132–143 of 201 stages/);
  f.button("Return to failing context").emit("click");
  assert.equal(stage.value, "200");
});

test("atom selection uses structured keys and preserves the recorded context", () => {
  const f = fixture(model({ atoms: ["vote", 'vote() & <script>'] }));
  const atom = f.control("Atoms shown"); assert.equal(atom.children.length, 3);
  change(atom, JSON.stringify(['vote() & <script>', []]));
  assert.match(f.map.alt, /c: f \(false\)/);
  assert.ok(f.map.alt.includes('vote() & <script>'));
  assert.equal(f.control("Stage").value, "2");
  const svg = decodeURIComponent(f.map.src.split(",").slice(1).join(","));
  assert.ok(svg.includes("&lt;script&gt;")); assert.ok(!svg.includes("<script>"));
});

test("timeline activation retains focus and pressed state on the replacement stage button", () => {
  const f = fixture(model()); selectAtom(f, "vote");
  const before = f.button("View stage 1");
  before.focus(); before.emit("click");
  const after = f.button("View stage 1");
  assert.notEqual(after, before, "Test must exercise the DOM replacement case");
  assert.equal(f.document.activeElement, after);
  assert.equal(after.getAttribute("aria-pressed"), "true");
  assert.equal(f.control("Stage").value, "1");
  const stage = f.control("Stage"); stage.focus(); change(stage, "0");
  assert.equal(f.document.activeElement, stage, "Updating another control stole focus");
});

test("no-predicate frames, axiom models and invalid models have truthful fallback text", () => {
  const empty = fixture(model({ atoms: [] }));
  assert.equal(empty.control("Atoms shown").disabled, true);
  assert.match(empty.map.alt, /No atomic predicates listed/);
  assert.ok(!empty.map.alt.includes("f (false)"));
  assert.equal(empty.find(node => node.className === "model-time-details").hidden, true);
  const axioms = fixture(model({ failure: false }));
  assert.match(axioms.root.textContent, /satisfies all retained axioms/);
  assert.equal(axioms.all(node => node.tagName === "BUTTON" && node.textContent === "Return to failing context").length, 0);
  const malformed = fixture({});
  assert.match(malformed.root.textContent, /diagram is unavailable/i);
  assert.equal(malformed.map, undefined); malformed.root.dispose();
});

test("missing atomic cells remain unlisted rather than being displayed as false", () => {
  const input = model(); input.valuation = input.valuation.filter(row => !(row.time === 2 && row.point === "c"));
  const f = fixture(input);
  selectAtom(f, "vote");
  assert.match(f.root.textContent, /missing or inconsistent/);
  assert.match(f.map.alt, /c: value not listed/);
  assert.ok(f.all(node => node.getAttribute("aria-label") === "Value not listed").length > 0);
});

test("participant and stage pagination remain bounded in a larger model", () => {
  const points = Array.from({ length: 20 }, (_, i) => `p${i}`), f = fixture(model({ points, stages: 250 }));
  selectAtom(f, "vote");
  assert.equal(f.control("Stage").tagName, "INPUT");
  assert.match(f.map.alt, /participants 19–20 of 20/);
  assert.ok(f.all(node => node.tagName === "TD").length <= 72);
  f.button("Previous participants").emit("click");
  assert.match(f.map.alt, /participants 13–18 of 20/);
  change(f.control("Stage"), "12");
  assert.match(f.map.alt, /Stage 12 of/);
  assert.equal(f.all(node => node.tagName === "TD").length, 72);
  change(f.control("Stage"), "-1"); assert.equal(f.control("Stage").value, "12");
  change(f.control("Stage"), "NaN"); assert.equal(f.control("Stage").value, "12");
  f.button("Return to failing context").emit("click");
  assert.equal(f.control("Stage").value, "249");
  assert.match(f.map.alt, /participants 19–20 of 20/);
});

test("atom filtering caps options and retains the selected atom when there is no match", () => {
  const f = fixture(model({ atoms: Array.from({ length: 125 }, (_, i) => `predicate_${i}`), stages: 1 }));
  const atom = f.control("Atoms shown"), filter = f.control("Find an atom");
  assert.equal(atom.children.length, 101);
  filter.value = "predicate_124"; filter.emit("input");
  assert.equal(atom.children.length, 2);
  const match = atom.children.find(option => option.textContent === "predicate_124");
  change(atom, match.value);
  assert.match(f.map.alt, /Selected atom: predicate_124/);
  filter.value = "unmatched"; filter.emit("input");
  assert.equal(atom.children.length, 2); assert.equal(atom.value, match.value);
  assert.equal(atom.children[0].value, "", "Overview must remain available after filtering");
  assert.match(f.root.textContent, /No matching atoms/);
});

test("SVG downloads match the displayed atom, stage, quorum and participant page", () => {
  const f = fixture(model({ atoms: ["vote", "decide"] }));
  selectAtom(f, "decide");
  change(f.control("Stage"), "0"); change(f.control("Quorum highlighted"), "1");
  f.button("Download this view (SVG)").emit("click");
  assert.equal(f.downloads.length, 1);
  const [filename, svg, mime] = f.downloads[0];
  assert.equal(filename, "model-stage-0-Q2.svg"); assert.equal(mime, "image/svg+xml");
  assert.equal(svg, decodeURIComponent(f.map.src.slice(f.map.src.indexOf(",") + 1)));
  assert.match(svg, /Selected atom: decide/); assert.match(svg, /Stage 0 of/);
  assert.match(svg, /Q2 =/); assert.doesNotMatch(svg, /recorded property failure here/);
});

test("responsive redraws coalesce and disposal stops observers and pending frames", () => {
  const f = fixture(model()); f.flush(); assert.equal(f.map.width, 800);
  f.resize(390); f.resize(320); assert.equal(f.frames.size, 1);
  f.flush(); assert.equal(f.map.width, 320);
  f.resize(640); const before = f.map.src;
  f.root.dispose(); f.root.dispose();
  assert.equal(f.frames.size, 0); assert.ok(f.observers.every(observer => observer.disconnected));
  f.resize(900); f.flush(); assert.equal(f.map.src, before);
});

test("window resize fallback is removed on disposal when ResizeObserver is unavailable", () => {
  const f = fixture(model(), { resizeObserver: false }); f.flush();
  assert.equal(f.window.listeners.get("resize").size, 1);
  f.resize(390); f.flush(); assert.equal(f.map.width, 390);
  f.root.dispose(); assert.equal(f.window.listeners.get("resize").size, 0);
  f.resize(800); assert.equal(f.frames.size, 0);
});

test("enlarging text redraws the diagram even when its container width stays fixed", () => {
  const f = fixture(model(), { width: 320 }); f.flush();
  const normalHeight = f.map.height;
  f.fontSize = 32; f.resize(320);
  assert.equal(f.frames.size, 1); f.flush();
  assert.ok(f.map.height > normalHeight);
  assert.equal(f.map.width, 440, "Larger text gets an internally scrollable image rather than shrinking back down");
  assert.equal(f.map.style.width, "440px");
  assert.match(decodeURIComponent(f.map.src), /viewBox="0 0 220 /);
});

test("the stage snapshot shows simultaneous true choices and retains focus when selecting an atom", () => {
  const input = {
    property: "AtMostOne", scope: { points: ["a"], values: ["red", "blue"], quorums: [["a"]], stages: 1, time: "finite" },
    failure: { time: 0, point: "a", quorum: ["a"], value: "f" },
    valuation: ["red", "blue"].map(value => ({ predicate: "chosen", args: [value], point: "a", time: 0, value: "t" })),
  };
  const f = fixture(input), snapshot = f.find(node => node.className.includes("model-snapshot") && node.tagName === "TABLE");
  assert.equal(f.find(node => node.className === "model-snapshot-details").hidden, false);
  const rows = descendants(snapshot).find(node => node.tagName === "TBODY").children;
  assert.equal(rows.length, 2);
  assert.deepEqual(rows.map(row => row.children.map(cell => cell.textContent)), [["chosen(red)", "t"], ["chosen(blue)", "t"]]);
  const before = f.button("Inspect atom: chosen(blue)"); before.focus(); before.emit("click");
  const after = f.button("Inspect atom: chosen(blue)");
  assert.notEqual(after, before); assert.equal(f.document.activeElement, after);
  assert.equal(after.getAttribute("aria-pressed"), "true");
  assert.equal(f.control("Atoms shown").value, JSON.stringify(["chosen", ["blue"]]));
  assert.match(f.map.alt, /Selected atom: chosen\(blue\)/); assert.match(f.map.alt, /a: t \(true\)/);
});

test("the overview and stage snapshot share twelve-atom pages and retain linked selection", () => {
  const f = fixture(model({ atoms: Array.from({ length: 31 }, (_, i) => `p${i}`) }));
  const snapshot = f.find(node => node.className.includes("model-snapshot") && node.tagName === "TABLE");
  const rows = () => descendants(snapshot).find(node => node.tagName === "TBODY").children;
  assert.equal(rows().length, 12); assert.equal(f.button("Previous atoms").disabled, true);
  assert.ok(!f.find(node => node.className === "model-snapshot-details").contains(f.button("Next atoms")), "Diagram paging must be outside the collapsible table");
  f.button("Next atoms").emit("click"); assert.equal(rows().length, 12);
  assert.equal(rows()[0].children[0].textContent, "p12");
  assert.match(visibleSvgText(svgOf(f)), /\bp12\b/); assert.match(visibleSvgText(svgOf(f)), /\bp23\b/);
  assert.doesNotMatch(visibleSvgText(svgOf(f)), /\bp0\b/);
  f.button("Inspect atom: p13").emit("click");
  assert.equal(f.control("Atoms shown").value, JSON.stringify(["p13", []]));
  assert.match(f.map.alt, /Selected atom: p13/);
  change(f.control("Atoms shown"), "");
  assert.equal(rows()[0].children[0].textContent, "p12", "Returning to overview should preserve the inspected atom page");
  f.button("Next atoms").emit("click"); assert.equal(rows().length, 7);
  assert.match(visibleSvgText(svgOf(f)), /\bp30\b/);
  assert.equal(f.button("Next atoms").disabled, true);
  f.button("Previous atoms").emit("click"); assert.equal(rows().length, 12);
});


test("a fresh diagram visibly includes both choices without requiring any atom selection", async () => {
  const f = fixture(await witness("search_choices--AtMostOne"));
  assert.equal(f.control("Atoms shown").value, "");
  assert.equal(f.control("Atoms shown").children[0].textContent, "All atoms");
  const visible = visibleSvgText(svgOf(f));
  assert.match(visible, /chosen\(v0\)/); assert.match(visible, /chosen\(value0\)/);
  assert.equal((visible.match(/\bt true\b/g) || []).length, 2, "Both simultaneous true choices must be drawn, not merely described in hidden metadata");
  selectAtom(f, "chosen(value0)");
  const single = svgOf(f); assert.match(f.map.alt, /Selected atom: chosen\(value0\)/);
  change(f.control("Atoms shown"), "");
  assert.equal(visibleSvgText(svgOf(f)), visible, "Overview should be restored without changing the model");
  assert.notEqual(svgOf(f), single);
  f.button("Download this view (SVG)").emit("click");
  assert.equal(f.downloads[0][1], svgOf(f), "Overview export must be the displayed diagram");
});

test("the default Simpler Paxos overview visibly contains all nine recorded atoms", async () => {
  const f = fixture(await witness("spax_without_write_affine--Agreement"));
  const visible = visibleSvgText(svgOf(f));
  for (const label of ["leader", "propose(red)", "propose(blue)", "write(red)", "write(blue)", "accept(red)", "accept(blue)", "decide(red)", "decide(blue)"]) {
    assert.ok(visible.includes(label), `The default SVG does not visibly include ${label}`);
  }
  assert.equal((visible.match(/\bt true\b/g) || []).length, 9);
  assert.equal(f.button("Next atoms").parentNode.hidden, true, "Nine atoms fit on one complete default page");
});

test("two models with identical first-atom values visibly differ when later atoms differ", async () => {
  const validity = await witness("spax_without_accept_back--Validity");
  const agreement = await witness("spax_without_write_affine--Agreement");
  // Remove the property title as a possible reason for different SVGs.
  validity.property = agreement.property = "Same title";
  const left = fixture(validity), right = fixture(agreement);
  assert.notEqual(visibleSvgText(svgOf(left)), visibleSvgText(svgOf(right)), "Different valuations were hidden by the common leader=true default");
  assert.match(visibleSvgText(svgOf(left)), /\bf false\b/);
  assert.doesNotMatch(visibleSvgText(svgOf(right)), /\bf false\b/);
  selectAtom(left, "leader"); selectAtom(right, "leader");
  assert.equal(svgOf(left), svgOf(right), "The reproducer must really have identical first-atom diagrams");
});

test("overview stages update all atoms, while an individual atom enables its named time trace", () => {
  const f = fixture(model({ atoms: ["vote", "decide"] }));
  const trace = f.find(node => node.className === "model-time-details");
  assert.equal(trace.hidden, true);
  assert.match(f.root.textContent, /Choose an individual atom to inspect its values across time/);
  const failureSvg = svgOf(f);
  assert.deepEqual(overviewCells(f), [[0, "f"], [1, "t"], [0, "t"], [1, "b"], [0, "b"], [1, "f"]]);
  change(f.control("Stage"), "0");
  assert.deepEqual(overviewCells(f), [[0, "t"], [1, "b"], [0, "b"], [1, "f"], [0, "f"], [1, "t"]]);
  assert.notEqual(svgOf(f), failureSvg); assert.equal(f.control("Atoms shown").value, "");
  selectAtom(f, "decide"); assert.equal(trace.hidden, false);
  const caption = descendants(trace).find(node => node.tagName === "CAPTION");
  assert.match(caption.textContent, /decide/);
  assert.match(caption.textContent, /participants 1–3 of 3/i);
  change(f.control("Atoms shown"), ""); assert.equal(trace.hidden, true);
});

const hasClass = (node, name) => node.className.split(/\s+/).includes(name);
const quorumSummary = f => {
  const summary = f.find(node => hasClass(node, "model-quorum-summary"));
  assert.ok(summary, "The selected quorum needs a prominent, persistent summary");
  return summary;
};

test("the exact selected quorum is stated before the picture and changes with quorum selection", () => {
  const input = model(), before = JSON.stringify(input), f = fixture(input);
  const summary = quorumSummary(f);
  const figure = f.find(node => hasClass(node, "model-figure"));
  const ordered = descendants(f.root);
  assert.ok(ordered.indexOf(summary) < ordered.indexOf(figure), "The set must be encountered before the picture");
  const heading = f.find(node => hasClass(node, "model-quorum-heading"));
  const members = f.find(node => hasClass(node, "model-quorum-members"));
  assert.match(heading.textContent, /Selected quorum Q1/);
  assert.equal(members.textContent, "Q1 = {a}");
  const initialValues = overviewCells(f);
  change(f.control("Quorum highlighted"), "1");
  assert.match(heading.textContent, /Selected quorum Q2/);
  assert.equal(members.textContent, "Q2 = {a, b, c}");
  assert.deepEqual(overviewCells(f), initialValues, "Changing quorum must not change recorded atom values");
  change(f.control("Stage"), "0");
  assert.equal(members.textContent, "Q2 = {a, b, c}", "The frame's quorum does not vary by stage");
  f.button("Return to failing context").emit("click");
  assert.equal(members.textContent, "Q1 = {a}");
  assert.equal(JSON.stringify(input), before);
});

test("the quorum summary keeps off-page and hostile member names complete without creating HTML", () => {
  const points = Array.from({ length: 14 }, (_, i) => `participant_${i}`);
  points[0] = '<img src=x onerror="bad()"> & "😀"';
  points[6] = "W".repeat(300);
  const input = model({ points, stages: 1 });
  input.scope.quorums = [[points[0], points[6], points[12]], [points[1], points[2]]];
  input.failure.quorum = [...input.scope.quorums[0]];
  const f = fixture(input);
  const members = f.find(node => hasClass(node, "model-quorum-members"));
  const note = f.find(node => hasClass(node, "model-quorum-note"));
  const exactSet = `Q1 = {${JSON.stringify(points[0])}, ${points[6]}, ${points[12]}}`;
  assert.equal(members.textContent, exactSet);
  assert.equal(members.children.length, 0, "Member names must be literal text, not parsed markup");
  assert.match(note.textContent, /3 participants/);
  assert.match(note.textContent, /2 (?:members? |participants? )?(?:on )?(?:other|another) (?:participant )?pages?/i);
  f.button("Previous participants").emit("click");
  assert.equal(members.textContent, exactSet);
  assert.match(note.textContent, /2 (?:members? |participants? )?(?:on )?(?:other|another) (?:participant )?pages?/i);
  change(f.control("Quorum highlighted"), "1");
  assert.equal(members.textContent, "Q2 = {participant_1, participant_2}");
  assert.match(note.textContent, /2 (?:members? |participants? )?(?:on )?(?:other|another) (?:participant )?pages?/i);
  assert.ok(!quorumSummary(f).textContent.includes(points[0]), "A previous set leaked into the selected quorum summary");
});

test("single-stage or single-quorum controls are disabled independently without disabling meaningful choices", () => {
  const one = model({ points: ["a"], stages: 1, atoms: ["vote", "decide"] });
  one.scope.quorums = [["a"]];
  const fixed = fixture(one);
  assert.equal(fixed.control("Stage").disabled, true);
  assert.equal(fixed.control("Quorum highlighted").disabled, true);
  assert.equal(fixed.control("Atoms shown").disabled, false);
  assert.equal(fixed.control("Stage").value, "0");
  assert.equal(fixed.control("Quorum highlighted").value, "0");
  assert.match(fixed.map.alt, /Stage 0 of 0–0/);
  const stages = model(); stages.scope.quorums = [["a"]];
  const temporal = fixture(stages);
  assert.equal(temporal.control("Stage").disabled, false);
  assert.equal(temporal.control("Quorum highlighted").disabled, true);
  const quorums = fixture(model({ stages: 1 }));
  assert.equal(quorums.control("Stage").disabled, true);
  assert.equal(quorums.control("Quorum highlighted").disabled, false);
});

test("an axiom model uses a neutral context notice, while a recorded counterexample retains its failure notice", () => {
  const axioms = fixture(model({ failure: false }));
  const notice = axioms.find(node => hasClass(node, "model-context"));
  assert.ok(notice, "A satisfying model needs a neutral context notice");
  assert.match(notice.textContent, /satisfies all retained axioms/);
  assert.ok(!axioms.find(node => hasClass(node, "model-failure")), "A satisfying model must not look like a failure");
  const failing = fixture(model());
  assert.match(failing.find(node => hasClass(node, "model-failure")).textContent, /Recorded failure of Agreement/);
});

test("whole-model totals stay fixed as the reader changes and pages the current diagram view", () => {
  const input = model({ points: Array.from({ length: 20 }, (_, i) => `p${i}`), stages: 25,
    atoms: Array.from({ length: 31 }, (_, i) => `atom_${i}`) });
  const before = JSON.stringify(input), f = fixture(input);
  assert.equal(f.find(node => node.tagName === "H4").textContent, "Explore this model");
  const summary = f.find(node => hasClass(node, "model-scope"));
  assert.ok(summary, "Whole-model totals must remain separate from view controls");
  for (const count of ["20 participants", "2 quorums", "25 stages", "31 atoms", "1 value"]) {
    assert.ok(summary.textContent.includes(count), `Missing whole-model total: ${count}`);
  }
  assert.match(f.root.textContent, /Whole model/);
  const fixed = summary.textContent;
  assert.equal(f.control("Atoms shown").children[0].textContent, "All atoms (paged)");
  assert.match(visibleSvgText(svgOf(f)), /View at stage 24/);
  assert.match(f.map.alt, /participants 19–20 of 20/i);
  assert.match(f.map.alt, /atoms 1–12 of 31/i);
  selectAtom(f, "atom_16");
  change(f.control("Stage"), "0"); change(f.control("Quorum highlighted"), "1");
  f.button("Previous participants").emit("click");
  assert.equal(summary.textContent, fixed);
  assert.match(visibleSvgText(svgOf(f)), /View at stage 0/);
  assert.match(f.map.alt, /Selected atom: atom_16/);
  assert.match(f.map.alt, /participants 13–18 of 20/i);
  f.button("Next atoms").emit("click");
  assert.match(f.map.alt, /atoms 25–31 of 31/i);
  assert.equal(summary.textContent, fixed);
  assert.doesNotMatch(f.root.textContent + visibleSvgText(svgOf(f)), /Model state/i,
    "A current view must never be labelled as if it were the complete model");
  assert.equal(JSON.stringify(input), before);
});

test("the full-model action is optional, direct, and does not reset the current view", () => {
  const f = fixture(model(), { fullModelAction: true });
  selectAtom(f, "vote"); change(f.control("Stage"), "0");
  const visible = svgOf(f);
  f.button("Full model data").emit("click");
  assert.equal(f.fullModelRequests, 1);
  assert.equal(svgOf(f), visible, "Opening complete data must not reset the selected view");
  const standalone = fixture(model());
  assert.equal(standalone.all(node => node.tagName === "BUTTON" && node.textContent === "Full model data").length, 0,
    "A standalone renderer must not offer an unconnected full-data action");
});

test("one-stage and no-predicate models still separate whole-model scope from their current view", () => {
  for (const atoms of [["vote"], []]) {
    const input = model({ points: ["a"], stages: 1, atoms }); input.scope.quorums = [["a"]];
    const f = fixture(input);
    const whole = f.find(node => hasClass(node, "model-scope"));
    for (const count of ["1 participant", "1 stage", `${atoms.length} atom`]) assert.ok(whole.textContent.includes(count));
    assert.match(visibleSvgText(svgOf(f)), /View at stage 0/);
    assert.doesNotMatch(f.root.textContent + visibleSvgText(svgOf(f)), /Model state/i);
    assert.equal(f.find(node => hasClass(node, "model-snapshot-details")).hidden, true);
  }
});

test("diagram, stage table and time trace each state the distinct portion they display", () => {
  const f = fixture(model({ points: Array.from({ length: 20 }, (_, i) => `point_${i}`), stages: 25,
    atoms: Array.from({ length: 31 }, (_, i) => `atom_${i}`) }));
  const summary = f.find(node => hasClass(node, "model-view-summary"));
  assert.ok(summary, "The view needs visible coverage beyond the complete-model totals");
  const snapshot = f.find(node => hasClass(node, "model-snapshot-details"));
  const snapshotCaption = () => descendants(snapshot).find(node => node.tagName === "CAPTION").textContent;
  assert.match(summary.textContent, /1 of 25 stages/);
  assert.match(summary.textContent, /1 of 2 quorums/);
  assert.match(summary.textContent, /Participants 19–20 of 20/);
  assert.match(summary.textContent, /Atoms 1–12 of 31/);
  selectAtom(f, "atom_16");
  assert.match(summary.textContent, /1 of 31 atoms/);
  assert.match(snapshotCaption(), /[Aa]toms 13–24 of 31/,
    "The table contains twelve atoms even when the diagram is focused on one");
  assert.match(snapshotCaption(), /[Pp]articipants 19–20 of 20/);
  assert.equal(descendants(snapshot).find(node => node.tagName === "SUMMARY").textContent, "Atom values at stage 24");
  const trace = f.find(node => hasClass(node, "model-time-details"));
  assert.match(trace.textContent, /atom_16/);
  assert.match(trace.textContent, /[Pp]articipants 19–20 of 20/);
  assert.match(trace.textContent, /[Ss]tages? 24(?:–24)?(?: of 0–24)?/);
  change(f.control("Stage"), "0");
  assert.match(trace.textContent, /[Ss]tages 0–11/);
  assert.equal(descendants(snapshot).find(node => node.tagName === "SUMMARY").textContent, "Atom values at stage 0");
  const whole = f.find(node => hasClass(node, "model-scope"));
  assert.match(whole.textContent, /25 stages/); assert.match(whole.textContent, /31 atoms/);
});
