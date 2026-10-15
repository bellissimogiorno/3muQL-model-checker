/** Independent SVG semantics, XML safety and geometry checks.
 * Run: node tests/browser/model-svg.mjs
 * Python's standard XML parser checks exported markup; no browser DOM is used.
 */
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import test from "node:test";

const moduleURL = source => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const dataURL = moduleURL(await readFile(new URL("../../web/model-data.js", import.meta.url), "utf8"));
const { createModelIndex } = await import(dataURL);
const svgSource = (await readFile(new URL("../../web/model-svg.js", import.meta.url), "utf8"))
  .replaceAll('"./model-data.js"', JSON.stringify(dataURL));
const { modelDiagramSvg, ATOMS_PER_PAGE } = await import(moduleURL(svgSource));

const XML_READER = `
import json, sys, xml.etree.ElementTree as ET
root = ET.fromstring(sys.stdin.buffer.read())
def visible(e):
 if e.tag.rsplit("}", 1)[-1] in {"title", "desc"}: return ""
 return " ".join([e.text or ""] + [visible(child) for child in e])
def node(e):
 return {"tag": e.tag, "attrs": e.attrib, "text": " ".join(e.itertext()),
         "visible": visible(e), "children": [node(c) for c in e]}
print(json.dumps({"tag": root.tag, "attrs": root.attrib,
 "text": " ".join(root.itertext()), "visible": visible(root),
 "elements": [node(e) for e in root.iter()]}))
`;

function xml(svg) {
  const result = spawnSync(process.env.PYTHON || "python3", ["-c", XML_READER], {
    input: svg, encoding: "utf8", maxBuffer: 8 * 1024 * 1024,
  });
  assert.equal(result.status, 0, result.stderr || String(result.error));
  return JSON.parse(result.stdout);
}

function safeXML(svg) {
  const parsed = xml(svg);
  assert.equal(parsed.tag, "{http://www.w3.org/2000/svg}svg");
  const allowed = new Set(["svg", "title", "desc", "g", "defs", "style", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "tspan", "clipPath"]);
  for (const element of parsed.elements) {
    const tag = element.tag.replace(/^\{[^}]+\}/, "");
    assert.ok(allowed.has(tag), `Unexpected SVG element ${tag}`);
    for (const [name, value] of Object.entries(element.attrs)) {
      assert.doesNotMatch(name, /(?:^|\})on/i, `Active attribute ${name}`);
      assert.doesNotMatch(name, /(?:^|\})href$/i, `Link attribute ${name}`);
      assert.doesNotMatch(value, /(?:javascript:|url\(\s*["']?https?:)/i);
    }
  }
  return parsed;
}

const report = async name => JSON.parse(await readFile(new URL(`../../reports/${name}.countermodel.json`, import.meta.url), "utf8"));

function smallModel({ points = ["a", "b", "c"], stages = 2, time = "finite", failure = true } = {}) {
  return {
    scope: { points, values: ["unit"], stages, time, quorums: [[points[0]], [...points]] },
    valuation: Array.from({ length: stages }, (_, stage) => points.map((point, number) => ({
      predicate: "live", args: [], time: stage, point, value: ["t", "b", "f"][(number + stage) % 3],
    }))).flat(),
    ...(failure ? { failure: { time: 0, point: points.at(-1), quorum: [points[0]], value: "f" }, property: "Claim" } : {}),
  };
}

function draw(model, options = {}) {
  const index = createModelIndex(model);
  assert.equal(index.valid, true, index.issues.join("; "));
  const result = modelDiagramSvg(index, { atomKey: index.atoms[0]?.key, time: 0, quorumIndex: 0, width: 800, propertyName: model.property || "", ...options });
  return { ...result, index, parsed: safeXML(result.svg) };
}

test("every saved countermodel produces standalone, inactive, well-formed SVG", async () => {
  const files = (await readdir(new URL("../../reports/", import.meta.url)))
    .filter(name => name.endsWith(".countermodel.json"));
  assert.ok(files.length >= 22, "Expected the complete existing witness corpus");
  for (const filename of files) {
    const model = JSON.parse(await readFile(new URL(`../../reports/${filename}`, import.meta.url), "utf8"));
    const index = createModelIndex(model);
    const result = draw(model, { time: model.failure.time, quorumIndex: index.failure.quorumIndex });
    assert.ok(result.description.trim(), filename);
    assert.ok(Number.isFinite(result.width) && result.width > 0, filename);
    assert.ok(Number.isFinite(result.height) && result.height > 0, filename);
    assert.ok(result.parsed.elements.some(element => element.tag.endsWith("}title")), filename);
    assert.ok(result.parsed.elements.some(element => element.tag.endsWith("}desc")), filename);
  }
});

test("XML metacharacters and active-looking names remain inert text", () => {
  const hostilePoint = '</text><script>alert("point")</script>&';
  const hostileAtom = '<image href="https://example.invalid/pixel" onload="alert(1)"/>';
  const model = smallModel({ points: [hostilePoint, "ordinary"], stages: 1 });
  model.valuation.forEach(row => { row.predicate = hostileAtom; });
  model.property = '<foreignObject onload="alert(2)">Claim</foreignObject>';
  const result = draw(model);
  assert.ok(result.parsed.text.includes(hostilePoint), "Participant name must remain available as text");
  assert.ok(result.parsed.text.includes(JSON.stringify(hostileAtom)), "Predicate name must remain available in canonical quoted form");
  assert.doesNotMatch(result.svg, /<(?:script|image|foreignObject)(?:\s|>)/i);
});

test("non-XML characters cannot corrupt an SVG download", () => {
  const point = "before\u0000\u0001\ud800\ufffeafter";
  const result = draw(smallModel({ points: [point, "ordinary"], stages: 1 }));
  assert.ok(result.parsed.text.includes("before"));
  assert.ok(result.parsed.text.includes("after"));
  assert.doesNotMatch(result.svg, /[\u0000\u0001\ufffe]/);
});

test("visible geometry stays inside the declared canvas at mobile and desktop widths", () => {
  const model = smallModel({ points: Array.from({ length: 6 }, (_, number) => `participant_${number}`) });
  for (const width of [320, 375, 480, 800, 1200]) {
    const result = draw(model, { width });
    const [x0, y0, viewWidth, viewHeight] = result.parsed.attrs.viewBox.trim().split(/\s+/).map(Number);
    assert.equal(x0, 0);
    assert.equal(y0, 0);
    assert.equal(viewWidth, result.width);
    assert.equal(viewHeight, result.height);
    for (const element of result.parsed.elements) {
      const attrs = element.attrs;
      const tag = element.tag.replace(/^\{[^}]+\}/, "");
      if (tag === "rect" && !String(attrs.width).includes("%") && !String(attrs.height).includes("%")) {
        const [x, y, width, height] = [attrs.x || 0, attrs.y || 0, attrs.width, attrs.height].map(Number);
        assert.ok(x >= -1 && y >= -1 && x + width <= viewWidth + 1 && y + height <= viewHeight + 1,
          `Rectangle exceeds ${viewWidth}×${viewHeight}: ${JSON.stringify(attrs)}`);
      }
      for (const name of ["x1", "x2", "cx"]) if (attrs[name] !== undefined) {
        assert.ok(Number(attrs[name]) >= 0 && Number(attrs[name]) <= viewWidth, `${name} outside canvas`);
      }
      for (const name of ["y1", "y2", "cy"]) if (attrs[name] !== undefined) {
        assert.ok(Number(attrs[name]) >= 0 && Number(attrs[name]) <= viewHeight, `${name} outside canvas`);
      }
    }
  }
});

const participants = result => result.parsed.elements.filter(element => "data-point-index" in element.attrs);
const failurePoints = result => participants(result).filter(element => element.attrs["data-failure"] === "true")
  .map(element => Number(element.attrs["data-point-index"]));
const edges = result => result.parsed.elements.filter(element => "data-quorum-edge" in element.attrs)
  .map(element => Number(element.attrs["data-quorum-edge"]));

test("outside-quorum failure retains its participant and never invents membership", async () => {
  const model = await report("simple_without_progress--ProposerDecides");
  assert.deepEqual(model.failure, { time: 0, point: "c", quorum: ["a", "b"], value: "f" });
  const result = draw(model);
  assert.deepEqual(participants(result).map(element => Number(element.attrs["data-point-index"])), [0, 1, 2]);
  assert.deepEqual(participants(result).map(element => element.attrs["data-member"]), ["true", "true", "false"]);
  assert.deepEqual(edges(result), [0, 1]);
  assert.deepEqual(failurePoints(result), [2]);
  assert.match(result.description, /c:.*not a member of Q1; recorded property failure here/);
});

test("failure highlight requires its recorded stage and quorum, independently of selected atom", () => {
  const model = smallModel();
  model.valuation.push(...model.valuation.map(row => ({ ...row, predicate: "other", value: "t" })));
  const otherKey = JSON.stringify(["other", []]);
  for (const atomKey of [JSON.stringify(["live", []]), otherKey]) {
    assert.deepEqual(failurePoints(draw(model, { atomKey })), [2]);
    assert.deepEqual(failurePoints(draw(model, { atomKey, time: 1 })), []);
    assert.deepEqual(failurePoints(draw(model, { atomKey, quorumIndex: 1 })), []);
    assert.deepEqual(failurePoints(draw(model, { atomKey, time: 1, quorumIndex: 1 })), []);
  }
});

test("truth labels follow atomic data and do not change when quorum changes", () => {
  const model = smallModel();
  const first = draw(model);
  const whole = draw(model, { quorumIndex: 1 });
  for (const result of [first, whole]) {
    const labels = participants(result).map(element => element.text);
    for (const [index, expected] of ["t true", "b broken", "f false"].entries()) {
      assert.ok(labels[index].includes(expected), `${expected} not visible at participant ${index}`);
    }
  }
  assert.deepEqual(edges(first), [0]);
  assert.deepEqual(edges(whole), [0, 1, 2]);
  assert.deepEqual(failurePoints(whole), []);
  const next = participants(draw(model, { time: 1 })).map(element => element.text);
  for (const [index, expected] of ["b broken", "f false", "t true"].entries()) assert.ok(next[index].includes(expected));
});

test("an empty atomic signature still draws the frame and recorded failure", () => {
  const model = smallModel();
  model.valuation = [];
  const result = draw(model);
  assert.match(result.description, /No atomic predicates/);
  assert.equal(participants(result).length, 3);
  assert.deepEqual(edges(result), [0]);
  assert.deepEqual(failurePoints(result), [2]);
  for (const participant of participants(result)) assert.match(participant.text, /no atoms/);
});

test("a missing atomic cell is visibly unavailable, never silently false", () => {
  const model = smallModel();
  model.valuation = model.valuation.filter(row => row.point !== "b" || row.time !== 0);
  const result = draw(model);
  assert.match(participants(result)[1].text, /value not listed/);
  assert.doesNotMatch(participants(result)[1].text, /f false/);
});

test("participant pagination states its exact extent and keeps global membership indices", () => {
  const model = smallModel({ points: Array.from({ length: 14 }, (_, number) => `p${number}`), stages: 1 });
  for (const [pointStart, expectedIndices] of [[0, [0, 1, 2, 3, 4, 5]], [6, [6, 7, 8, 9, 10, 11]], [12, [12, 13]]]) {
    const result = draw(model, { pointStart, quorumIndex: 1 });
    assert.deepEqual(participants(result).map(element => Number(element.attrs["data-point-index"])), expectedIndices);
    assert.deepEqual(edges(result), expectedIndices);
    assert.ok(result.description.includes(`Showing participants ${pointStart + 1}–${expectedIndices.at(-1) + 1} of 14`));
  }
  const last = draw(model, { pointStart: 12 });
  assert.deepEqual(edges(last), []);
  assert.deepEqual(failurePoints(last), [13]);
  assert.deepEqual(failurePoints(draw(model, { pointStart: 0 })), []);
});

test("models with no recorded failure never acquire a failure marker", () => {
  const model = smallModel({ failure: false });
  const result = draw(model);
  assert.deepEqual(failurePoints(result), []);
  assert.doesNotMatch(result.description, /property failure here/);
});

test("invalid selections are rejected rather than depicting a different model context", () => {
  const index = createModelIndex(smallModel());
  for (const options of [{ time: -1 }, { time: 2 }, { time: 0.5 }, { quorumIndex: -1 }, { quorumIndex: 2 }, { pointStart: -1 }, { pointStart: 3 }, { atomKey: "unknown" }]) {
    assert.throws(() => modelDiagramSvg(index, options), /outside the model/i);
  }
});

test("standalone descriptions preserve temporal horizon and the finite or stuttering boundary", () => {
  for (const time of ["finite", "stutter"]) {
    const model = smallModel({ stages: 3, time });
    for (const stage of [0, 2]) {
      const result = draw(model, { time: stage });
      assert.ok(result.description.includes(`Stage ${stage} of 0–2; ${time} time.`));
      const boundary = time === "finite"
        ? "The final stage has no successor."
        : "The final stage has itself as its successor.";
      assert.ok(result.description.includes(boundary));
      assert.ok(result.parsed.elements.find(element => element.tag.endsWith("}desc")).text.includes(boundary));
    }
  }
});

test("enlarged text scales physical SVG dimensions while retaining semantic facts", () => {
  const model = smallModel({ points: Array.from({ length: 6 }, (_, number) => `p${number}`) });
  for (const width of [320, 800]) {
    const ordinary = draw(model, { width });
    const enlarged = draw(model, { width, textScale: 2 });
    const [x, y, logicalWidth, logicalHeight] = enlarged.parsed.attrs.viewBox.split(/\s+/).map(Number);
    assert.deepEqual([x, y], [0, 0]);
    assert.equal(enlarged.width, logicalWidth * 2);
    assert.equal(enlarged.height, logicalHeight * 2);
    assert.equal(Number(enlarged.parsed.attrs.width), enlarged.width);
    assert.equal(Number(enlarged.parsed.attrs.height), enlarged.height);
    assert.equal(enlarged.description, ordinary.description);
    assert.deepEqual(failurePoints(enlarged), failurePoints(ordinary));
    assert.deepEqual(edges(enlarged), edges(ordinary));
  }
});

function minimumTextWidth(text, fontSize) {
  return [...text].reduce((size, character) => size + fontSize *
    (/\p{Unified_Ideograph}/u.test(character) ? 1 : /[WM]/.test(character) ? 0.75 : 0.4), 0);
}

test("long CJK and wide Latin participant labels fit their cards while full names remain accessible", () => {
  for (const name of ["參與者漢字名稱資料網絡邏輯模型驗證測試", "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW"]) {
    const points = Array.from({ length: 6 }, (_, number) => `${name}${number}`);
    const model = smallModel({ points, stages: 1 });
    for (const width of [320, 800]) {
      const result = draw(model, { width });
      for (const participant of participants(result)) {
        const number = Number(participant.attrs["data-point-index"]);
        const label = participant.children.find(child => child.tag.endsWith("}text"));
        const fontSize = Number(label.attrs["font-size"]);
        // Conservative glyph-width lower bounds catch character-count clipping
        // without prescribing a particular wrapping or truncation algorithm.
        const minimumWidth = minimumTextWidth(label.text, fontSize);
        const cardWidth = Math.max(...participant.children.filter(child => child.tag.endsWith("}rect"))
          .map(child => Number(child.attrs.width)));
        assert.ok(minimumWidth <= cardWidth, `Label ${label.text} is wider than its ${cardWidth}px card`);
        assert.ok(participant.children.find(child => child.tag.endsWith("}title")).text.includes(points[number]));
        assert.ok(result.description.includes(points[number]));
      }
    }
  }
});

test("long wide-character atom titles wrap within the picture and retain their full description", () => {
  for (const predicate of ["漢字名稱".repeat(30), "W".repeat(120)]) {
    const model = smallModel();
    model.valuation.forEach(row => { row.predicate = predicate; });
    for (const width of [320, 800]) {
      const result = draw(model, { width });
      const lines = result.parsed.elements.filter(element => element.tag.endsWith("}text") && element.attrs["font-size"] === "18");
      assert.ok(lines.length > 0);
      for (const line of lines) assert.ok(minimumTextWidth(line.text, 18) <= width - 48,
        `Atom title exceeds its text area: ${line.text}`);
      assert.ok(result.description.includes(predicate));
    }
  }
});

const overview = (model, options = {}) => draw(model, { atomKey: null, ...options });
const descendants = element => [element, ...element.children.flatMap(descendants)];
const visibleTexts = element => descendants(element).filter(item => item.tag.endsWith("}text"));
const atomRows = point => descendants(point).filter(item => "data-atom-index" in item.attrs);

function manyAtoms(count = 25, options = {}) {
  const model = smallModel(options);
  const original = model.valuation;
  model.valuation = Array.from({ length: count }, (_, atom) => original.map(row => ({
    ...row, predicate: `atom_${String(atom).padStart(2, "0")}`,
    value: ["t", "b", "f"][(atom + row.time + model.scope.points.indexOf(row.point)) % 3],
  }))).flat();
  return model;
}

test("the default overview makes both conflicting choices visible together", async () => {
  const model = await report("search_choices--AtMostOne");
  const index = createModelIndex(model);
  // This call intentionally omits atomKey: a first-atom-only default caused the
  // reported regression even when its hidden table contained the right model.
  const result = modelDiagramSvg(index);
  const parsed = safeXML(result.svg);
  const point = participants({ parsed })[0];
  for (const label of ["chosen(v0)", "chosen(value0)"]) {
    assert.ok(point.visible.includes(label), `${label} must be in the visible participant card`);
  }
  assert.equal((point.visible.match(/t true/g) || []).length, 2);
  assert.doesNotMatch(parsed.visible, /no atomic predicates|no atoms/i);
});

test("default Paxos diagrams expose all nine atoms, including both decision values", async () => {
  for (const name of ["spax_without_accept_back--Validity", "spax_without_write_affine--Agreement"]) {
    const model = await report(name);
    const result = overview(model);
    assert.equal(result.index.atoms.length, 9);
    const point = participants(result)[0];
    for (const atom of result.index.atoms) {
      assert.ok(point.visible.includes(atom.label), `${name}: ${atom.label} hidden in overview`);
    }
    assert.ok(point.visible.includes("decide(red)"));
    assert.ok(point.visible.includes("decide(blue)"));
    assert.equal((point.visible.match(/\b[tbf] (?:true|broken|false)\b/g) || []).length, 9);
  }
});

test("models sharing the first atom still have different visible default assignments", async () => {
  const left = await report("spax_without_accept_back--Validity");
  const right = await report("spax_without_write_affine--Agreement");
  assert.deepEqual(left.valuation[0], right.valuation[0], "This fixture must reproduce the first-atom collision");
  const leftNodes = participants(overview(left)).map(point => point.visible);
  const rightNodes = participants(overview(right)).map(point => point.visible);
  assert.notDeepEqual(leftNodes, rightNodes,
    "A changed heading or hidden description cannot fix an identical-looking participant diagram");
  // Equal assignments should stay equal: the renderer must not manufacture
  // differences simply because a property's name or identity changes.
  const relabelled = { ...left, property: "Another property on this same model" };
  assert.deepEqual(participants(overview(relabelled)).map(point => point.visible), leftNodes);
});

test("a selected atom remains named inside every participant card", () => {
  const model = smallModel();
  const result = draw(model);
  for (const point of participants(result)) assert.ok(point.visible.includes("live"));
});

test("overview atom pagination is bounded and explicitly states each displayed range", () => {
  assert.equal(ATOMS_PER_PAGE, 12);
  const model = manyAtoms(25);
  for (const [atomStart, end] of [[0, 12], [12, 24], [24, 25]]) {
    const result = overview(model, { atomStart });
    const expected = result.index.atoms.slice(atomStart, end).map(atom => atom.label);
    const hidden = result.index.atoms.filter((_, number) => number < atomStart || number >= end);
    for (const point of participants(result)) {
      for (const label of expected) assert.ok(point.visible.includes(label), `${label} missing on page ${atomStart}`);
      for (const atom of hidden) assert.ok(!point.visible.includes(atom.label), `${atom.label} leaked into page ${atomStart}`);
      assert.equal((point.visible.match(/\b[tbf] (?:true|broken|false)\b/g) || []).length, end - atomStart);
    }
    const extent = new RegExp(`atoms ${atomStart + 1}[–−-]${end} of 25`, "i");
    assert.match(result.description, extent);
    assert.match(result.parsed.visible, extent);
    assert.doesNotMatch(result.parsed.visible, /all 25 atoms|all atoms shown/i);
  }
});

test("overview labels and values change with stage while quorum membership stays separate", () => {
  const model = manyAtoms(3);
  const current = overview(model);
  const next = overview(model, { time: 1 });
  assert.notDeepEqual(participants(current).map(point => point.visible), participants(next).map(point => point.visible));
  assert.deepEqual(edges(current), edges(next));
  assert.deepEqual(failurePoints(current), [2]);
  assert.deepEqual(failurePoints(next), []);
  const whole = overview(model, { quorumIndex: 1 });
  for (const [number, point] of participants(current).entries()) {
    // Compare visible atom rows independently of the property-failure marker.
    assert.deepEqual(atomRows(point).map(row => row.visible), atomRows(participants(whole)[number]).map(row => row.visible));
  }
  assert.deepEqual(edges(whole), [0, 1, 2]);
});

test("overview keeps a failing participant outside the selected quorum visible", async () => {
  const model = await report("simple_without_progress--ProposerDecides");
  const result = overview(model);
  assert.deepEqual(edges(result), [0, 1]);
  assert.deepEqual(failurePoints(result), [2]);
  const outside = participants(result)[2];
  assert.equal(outside.attrs["data-member"], "false");
  for (const atom of result.index.atoms.slice(0, ATOMS_PER_PAGE)) {
    assert.ok(outside.visible.includes(atom.label), `${atom.label} omitted outside the quorum`);
  }
});

test("overview distinguishes a missing cell from an atom whose value is false", () => {
  const model = manyAtoms(2);
  model.valuation = model.valuation.filter(row => !(row.predicate === "atom_00" && row.point === "b" && row.time === 0));
  const point = participants(overview(model))[1];
  assert.ok(point.visible.includes("atom_00"));
  assert.ok(point.visible.includes("atom_01"));
  assert.match(point.visible, /\?|not listed|unlisted/);
  assert.equal((point.visible.match(/f false/g) || []).length, 1);
});

test("overview escapes hostile and long atom names without losing their complete accessible labels", () => {
  const model = manyAtoms(3, { stages: 1 });
  const predicates = [
    '</text><script>alert("atom")</script>&',
    "漢字名稱".repeat(30),
    "WWWWMMMM".repeat(20),
  ];
  for (const row of model.valuation) row.predicate = predicates[Number(row.predicate.slice(-2))];
  for (const width of [220, 320, 800]) {
    const result = overview(model, { width });
    assert.doesNotMatch(result.svg, /<(?:script|image|foreignObject)(?:\s|>)/i);
    for (const point of participants(result)) {
      for (const atom of result.index.atoms) {
        assert.ok(point.text.includes(atom.label), `Complete label missing at width ${width}`);
        assert.ok(result.description.includes(atom.label), `Complete description missing at width ${width}`);
      }
      assert.equal((point.visible.match(/\b[tbf] (?:true|broken|false)\b/g) || []).length, 3);
    }
  }
});

test("overview cards keep readable text within their bounds without row overlap", () => {
  const model = manyAtoms(12, { points: Array.from({ length: 6 }, (_, number) => `p${number}`) });
  for (const width of [220, 320, 800]) for (const textScale of [1, 2]) {
    const result = overview(model, { width, textScale });
    const [, , viewWidth, viewHeight] = result.parsed.attrs.viewBox.split(/\s+/).map(Number);
    const cardBounds = [];
    for (const point of participants(result)) {
      const rect = point.children.filter(child => child.tag.endsWith("}rect") && child.attrs.fill !== "none")
        .sort((left, right) => Number(right.attrs.width) * Number(right.attrs.height)
          - Number(left.attrs.width) * Number(left.attrs.height))[0];
      assert.ok(rect, "Each participant needs a visible card");
      const box = Object.fromEntries(["x", "y", "width", "height"].map(key => [key, Number(rect.attrs[key]) || 0]));
      assert.ok(box.x >= 0 && box.y >= 0 && box.x + box.width <= viewWidth && box.y + box.height <= viewHeight,
        `Card leaves canvas: ${width}px, scale ${textScale}`);
      cardBounds.push(box);
      const textBounds = [];
      for (const label of visibleTexts(point).filter(item => !/^Property false(?: here)?$/.test(item.visible))) {
        const size = Number(label.attrs["font-size"]);
        assert.ok(size >= 14, `Unreadably small ${size}px text: ${label.visible}`);
        const estimate = minimumTextWidth(label.visible, size);
        const anchor = label.attrs["text-anchor"];
        const x = Number(label.attrs.x) - (anchor === "middle" ? estimate / 2 : anchor === "end" ? estimate : 0);
        const baseline = Number(label.attrs.y);
        assert.ok(x >= box.x - 1 && x + estimate <= box.x + box.width + 1,
          `${label.visible} cannot fit horizontally in its ${box.width}px card at ${width}px, scale ${textScale}`);
        assert.ok(baseline - size * 0.8 >= box.y && baseline + size * 0.2 <= box.y + box.height,
          `${label.visible} cannot fit vertically within its card`);
        textBounds.push({ x, y: baseline - size * 0.8, width: estimate, height: size, text: label.visible });
      }
      for (const [number, first] of textBounds.entries()) for (const second of textBounds.slice(number + 1)) {
        const overlaps = first.x < second.x + second.width && second.x < first.x + first.width
          && first.y < second.y + second.height && second.y < first.y + first.height;
        assert.ok(!overlaps, `Text overlaps: ${first.text} / ${second.text} at ${width}px, scale ${textScale}`);
      }
    }
    for (const [number, first] of cardBounds.entries()) for (const second of cardBounds.slice(number + 1)) {
      assert.ok(!(first.x < second.x + second.width && second.x < first.x + first.width
        && first.y < second.y + second.height && second.y < first.y + first.height), "Participant cards overlap");
    }
  }
});

test("every saved witness overview renders precisely its recorded atom values", async () => {
  const files = (await readdir(new URL("../../reports/", import.meta.url)))
    .filter(name => name.endsWith(".countermodel.json"));
  for (const filename of files) {
    const model = JSON.parse(await readFile(new URL(`../../reports/${filename}`, import.meta.url), "utf8"));
    const index = createModelIndex(model);
    const result = overview(model, { time: model.failure.time, quorumIndex: index.failure.quorumIndex });
    for (const point of participants(result)) {
      const pointName = model.scope.points[Number(point.attrs["data-point-index"])];
      const rows = atomRows(point);
      assert.equal(rows.length, Math.min(index.atoms.length, ATOMS_PER_PAGE), filename);
      for (const row of rows) {
        const atom = index.atoms[Number(row.attrs["data-atom-index"])];
        const stored = model.valuation.find(cell => cell.predicate === atom.predicate
          && JSON.stringify(cell.args) === JSON.stringify(atom.args)
          && cell.time === model.failure.time && cell.point === pointName);
        assert.ok(stored, `${filename}: expected fixture cell at ${pointName}/${atom.label}`);
        assert.equal(row.attrs["data-value"], stored.value, `${filename}: ${pointName}/${atom.label}`);
        assert.ok(row.text.includes(atom.label));
        assert.ok(row.visible.includes({ t: "t true", b: "b broken", f: "f false" }[stored.value]),
          `${filename}: ${pointName}/${atom.label} has the wrong visible truth value`);
      }
    }
  }
});

const quorumBanner = result => {
  const banner = result.parsed.elements.find(element => "data-quorum-set" in element.attrs);
  assert.ok(banner, "The selected quorum must be stated in a visible banner inside the exported picture");
  return banner;
};

test("the visible quorum set and each participant's membership agree exactly with the selected frame quorum", () => {
  const model = smallModel({ points: ["alice", "bob", "carol"], stages: 1 });
  model.scope.quorums = [["bob"], ["alice", "carol"]];
  model.failure.quorum = ["bob"];
  // The renderer must use scope.quorums, not reconstruct a majority or copy
  // unrelated metadata describing how the frame might have been generated.
  model.metadata = { generators: [["alice", "bob", "carol"]], quorum_type: "majority" };
  for (const [quorumIndex, expectedPoints] of [[0, [1]], [1, [0, 2]]]) {
    const result = overview(model, { quorumIndex });
    const q = `Q${quorumIndex + 1}`;
    const banner = quorumBanner(result);
    assert.match(banner.visible, new RegExp(`Highlighted quorum ${q}`));
    assert.ok(banner.visible.includes(`${q} = {${model.scope.quorums[quorumIndex].join(", ")}}`));
    assert.deepEqual(edges(result), expectedPoints);
    for (const [pointIndex, point] of participants(result).entries()) {
      const expected = expectedPoints.includes(pointIndex) ? `In ${q}` : `Outside ${q}`;
      assert.ok(visibleTexts(point).some(label => label.visible === expected),
        `${model.scope.points[pointIndex]} needs an explicit ${expected} label, independent of colour`);
      assert.equal(point.attrs["data-member"], String(expectedPoints.includes(pointIndex)));
    }
  }
});

test("a paginated diagram names the complete quorum even when every member is on another page", () => {
  const model = smallModel({ points: Array.from({ length: 14 }, (_, i) => `p${i}`), stages: 1 });
  model.scope.quorums = [["p0", "p6", "p12"], ["p0", "p1"]];
  model.failure.quorum = ["p0", "p6", "p12"];
  for (const [pointStart, expectedEdge] of [[0, 0], [6, 6], [12, 12]]) {
    const result = overview(model, { pointStart });
    const visible = quorumBanner(result).visible;
    assert.ok(visible.includes("Q1 = {p0, p6, p12}"));
    assert.match(visible, /3 participants/);
    assert.match(visible, /2 (?:members? |participants? )?(?:on )?(?:other|another) (?:participant )?pages?/i);
    assert.deepEqual(edges(result), [expectedEdge]);
  }
  const emptyPage = overview(model, { pointStart: 12, quorumIndex: 1 });
  assert.ok(quorumBanner(emptyPage).visible.includes("Q2 = {p0, p1}"));
  assert.deepEqual(edges(emptyPage), []);
  assert.ok(participants(emptyPage).every(point => point.visible.includes("Outside Q2")));
  assert.deepEqual(failurePoints(emptyPage), []);
});

test("quorum banners bound long visible member lists while preserving every exact name safely", () => {
  const points = ["</text><script>bad()</script>&", ...Array.from({ length: 19 }, (_, i) => `參與者_${i}_${"W".repeat(90)}`)];
  const model = smallModel({ points, stages: 1 });
  for (const width of [220, 320, 800]) {
    const result = overview(model, { width, quorumIndex: 1, pointStart: 12 });
    const banner = quorumBanner(result);
    assert.ok(banner.visible.length < 1200, "A long quorum must not expand the SVG without a bound");
    assert.match(banner.visible, /full (?:member )?list in description/i);
    assert.ok(visibleTexts(banner).length <= 12, "The quorum banner needs a bounded number of visible lines");
    for (const point of points) assert.ok(result.description.includes(point), "The accessible/exported set must remain complete");
    assert.deepEqual(edges(result), [12, 13, 14, 15, 16, 17]);
    assert.doesNotMatch(result.svg, /<(?:script|image|foreignObject)(?:\s|>)/i);
  }
});

test("quorum set notation distinguishes punctuation inside a participant name from set separators", () => {
  const points = ["a, b", "a", "b", "{x}", 'quote"slash\\'];
  const result = overview(smallModel({ points, stages: 1 }), { width: 1600, quorumIndex: 1 });
  const expected = `Q2 = {${JSON.stringify(points[0])}, a, b, ${JSON.stringify(points[3])}, ${JSON.stringify(points[4])}}`;
  assert.ok(quorumBanner(result).visible.includes(expected), "Quoted names should make the visible set unambiguous");
  assert.ok(result.description.includes(expected));
  assert.deepEqual(edges(result), [0, 1, 2, 3, 4]);
  assert.equal(participants(result).length, 5, "A comma inside one name must not manufacture another participant");
});

test("quorum banner text and cards do not overlap at narrow widths or enlarged text sizes", () => {
  const model = manyAtoms(12, { points: ["參與者漢字".repeat(15), "W".repeat(120), "third"], stages: 1 });
  for (const width of [220, 320, 800]) for (const textScale of [1, 2]) {
    const result = overview(model, { width, textScale, quorumIndex: 1 });
    const banner = quorumBanner(result);
    const rectangles = descendants(banner).filter(element => element.tag.endsWith("}rect"));
    assert.ok(rectangles.length > 0, "The quorum banner needs a clear visual frame");
    const frame = rectangles.sort((a, b) => Number(b.attrs.width) * Number(b.attrs.height)
      - Number(a.attrs.width) * Number(a.attrs.height))[0];
    const box = Object.fromEntries(["x", "y", "width", "height"].map(key => [key, Number(frame.attrs[key]) || 0]));
    const bounds = visibleTexts(banner).map(label => {
      const size = Number(label.attrs["font-size"]), estimate = minimumTextWidth(label.visible, size);
      assert.ok(size >= 14, `Quorum text is too small: ${label.visible}`);
      const x = Number(label.attrs.x) - (label.attrs["text-anchor"] === "middle" ? estimate / 2 : label.attrs["text-anchor"] === "end" ? estimate : 0);
      const y = Number(label.attrs.y) - size * 0.8;
      assert.ok(x >= box.x - 1 && x + estimate <= box.x + box.width + 1,
        `Quorum text leaves its frame: ${label.visible} at width ${width}, scale ${textScale}`);
      assert.ok(y >= box.y && y + size <= box.y + box.height,
        `Quorum text leaves its frame vertically: ${label.visible}`);
      return { x, y, width: estimate, height: size, text: label.visible };
    });
    for (const [number, first] of bounds.entries()) for (const second of bounds.slice(number + 1)) {
      assert.ok(!(first.x < second.x + second.width && second.x < first.x + first.width
        && first.y < second.y + second.height && second.y < first.y + first.height),
      `Quorum text overlaps: ${first.text} / ${second.text}`);
    }
    const firstCardTop = Math.min(...participants(result).flatMap(point => point.children
      .filter(child => child.tag.endsWith("}rect")).map(rect => Number(rect.attrs.y))));
    assert.ok(box.y + box.height < firstCardTop, "Quorum banner overlaps participant cards");
  }
});

const coverage = result => {
  const group = result.parsed.elements.find(element => "data-view-coverage" in element.attrs);
  assert.ok(group, "The exported diagram needs visible coverage before its quorum banner");
  return group;
};

test("a paginated multistage export visibly identifies precisely the selected view", () => {
  const model = manyAtoms(25, { points: Array.from({ length: 14 }, (_, i) => `p${i}`), stages: 3 });
  const result = overview(model, { time: 2, atomStart: 12, pointStart: 6, quorumIndex: 1 });
  assert.match(result.parsed.visible, /View at stage 2/);
  assert.doesNotMatch(result.parsed.visible, /Model state/);
  for (const expected of ["1 of 3 stages shown", "Participants 7–12 of 14", "Atoms 13–24 of 25"]) {
    assert.ok(coverage(result).visible.includes(expected), `Missing current-view coverage: ${expected}`);
  }
  assert.match(quorumBanner(result).visible, /Highlighted quorum Q2/);
  assert.match(quorumBanner(result).visible, /1 of 2 quorums shown/);
  assert.match(result.description, /selected view, not a whole-model overview/);
  assert.match(result.description, /Stage 2 of 0–2/);
  assert.match(result.description, /Selecting another quorum changes membership highlighting, not atomic values/);
  assert.equal(atomRows(participants(result)[0]).length, 12);
  assert.equal(participants(result).length, 6);
});

test("a focused export names its one atom without presenting the current atom page as visible", () => {
  const model = manyAtoms(25);
  const key = JSON.stringify(["atom_24", []]);
  const result = draw(model, { atomKey: key, atomStart: 12, time: 1 });
  assert.match(result.parsed.visible, /View at stage 1/);
  assert.match(coverage(result).visible, /1 of 25 atoms shown/);
  assert.doesNotMatch(coverage(result).visible, /Atoms 13–24/);
  const bannerTop = Number(quorumBanner(result).children.find(element => element.tag.endsWith("}rect")).attrs.y);
  assert.ok(result.parsed.elements.some(element => element.tag.endsWith("}text")
    && element.visible.includes("Atom: atom_24") && Number(element.attrs.y) < bannerTop),
  "The focused atom must be named above the quorum, not just in an invisible description");
  for (const point of participants(result)) {
    assert.match(point.visible, /atom_24/);
    assert.doesNotMatch(point.visible, /atom_00|atom_12/);
  }
  assert.match(result.description, /Selected atom: atom_24\. 1 of 25 atoms shown/);
});

test("singleton coverage confirms all available stages and quorums are represented without invented omissions", () => {
  const model = smallModel({ points: ["only"], stages: 1 });
  model.scope.quorums = [["only"]];
  for (const atomKey of [null, JSON.stringify(["live", []])]) {
    const result = draw(model, { atomKey });
    assert.match(result.parsed.visible, /View at stage 0/);
    assert.match(coverage(result).visible, /1 of 1 stage shown/);
    assert.match(coverage(result).visible, /Participants 1–1 of 1/);
    assert.match(quorumBanner(result).visible, /1 of 1 quorum shown/);
    assert.doesNotMatch(result.description, /on other participant pages/);
    assert.match(coverage(result).visible, atomKey === null ? /Atoms 1–1 of 1/ : /1 of 1 atom shown/);
  }
});

test("an empty signature retains view coverage while explaining the absence of atom values", () => {
  const model = smallModel({ stages: 3 });
  model.valuation = [];
  const result = overview(model, { time: 1 });
  assert.match(result.parsed.visible, /View at stage 1/);
  assert.match(coverage(result).visible, /1 of 3 stages shown/);
  assert.match(coverage(result).visible, /No atomic predicates listed/);
  assert.doesNotMatch(coverage(result).visible, /1 of 0 atoms|Atoms 1–0/);
  assert.match(quorumBanner(result).visible, /1 of 2 quorums shown/);
  assert.equal(participants(result).length, 3);
});

test("coverage describes selected recorded atoms without claiming incomplete values are complete", () => {
  const model = manyAtoms(2);
  model.valuation = model.valuation.filter(row => !(row.predicate === "atom_00" && row.time === 1 && row.point === "b"));
  const result = overview(model, { time: 1 });
  assert.equal(result.index.complete, false);
  assert.match(coverage(result).visible, /Atoms 1–2 of 2/);
  assert.match(participants(result)[1].visible, /\? unlisted/);
  assert.match(result.description, /atom_00: value not listed/);
  assert.doesNotMatch(result.description, /complete (?:model|valuation)|all values shown/i);
});

test("coverage and focused labels fit before the quorum banner at narrow and enlarged sizes", () => {
  const model = manyAtoms(25, { points: Array.from({ length: 14 }, (_, i) => `p${i}`), stages: 3 });
  model.property = "A long property title with many words to wrap across narrow exports";
  model.valuation.forEach(row => { if (row.predicate === "atom_24") row.predicate = "漢字W".repeat(40); });
  for (const atomKey of [null, JSON.stringify(["漢字W".repeat(40), []])]) {
    for (const width of [220, 320, 800]) for (const textScale of [1, 2]) {
      const result = draw(model, { atomKey, atomStart: 12, time: 2, pointStart: 6, width, textScale });
      const [, , viewWidth] = result.parsed.attrs.viewBox.split(/\s+/).map(Number);
      const bannerTop = Number(quorumBanner(result).children.find(element => element.tag.endsWith("}rect")).attrs.y);
      const headerLabels = result.parsed.elements.filter(element => element.tag.endsWith("}text") && Number(element.attrs.y) < bannerTop);
      assert.ok(headerLabels.length >= 4);
      let previousBottom = 0;
      for (const label of headerLabels) {
        const size = Number(label.attrs["font-size"]), estimate = minimumTextWidth(label.visible, size);
        const x = Number(label.attrs.x), baseline = Number(label.attrs.y);
        assert.ok(x >= 0 && x + estimate <= viewWidth,
          `Header leaves canvas at ${width}px, scale ${textScale}: ${label.visible}`);
        assert.ok(baseline - size * 0.8 >= previousBottom, `Header lines overlap: ${label.visible}`);
        previousBottom = baseline + size * 0.2;
      }
      assert.ok(previousBottom < bannerTop, "Coverage must not overlap the quorum banner");
    }
  }
});
