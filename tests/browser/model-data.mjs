/** Pure countermodel indexing checks. Run: node tests/browser/model-data.mjs */
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../../web/model-data.js", import.meta.url), "utf8");
const { createModelIndex, valueAt, atomLabel } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const clone = value => JSON.parse(JSON.stringify(value));
const key = (predicate, args = []) => JSON.stringify([predicate, args]);

function fixture({ stages = 2, time = "finite", values = ["red", "blue"] } = {}) {
  const scope = { points: ["a", "b", "c"], quorums: [["a", "b"], ["a", "b", "c"]], values, stages, time };
  const valuation = [];
  for (let stage = 0; stage < stages; stage++) {
    for (let point = 0; point < scope.points.length; point++) {
      valuation.push({ predicate: "live", args: [], time: stage, point: scope.points[point], value: ["t", "b", "f"][(stage + point) % 3] });
    }
  }
  return { scope, valuation, failure: { time: 0, point: "c", quorum: ["b", "a"], value: "f" } };
}

test("all shipped witnesses retain every exact atom, cell and failure context", async () => {
  const directory = new URL("../../reports/", import.meta.url);
  const filenames = (await readdir(directory)).filter(name => name.endsWith(".countermodel.json"));
  assert.equal(filenames.length, 22, "every shipped countermodel must be checked");
  for (const filename of filenames) {
    const model = JSON.parse(await readFile(new URL(filename, directory), "utf8"));
    const index = createModelIndex(model);
    assert.equal(index.valid, true, filename);
    assert.equal(index.complete, true, `${filename}: ${index.issues.join("; ")}`);
    assert.deepEqual(index.scope, Object.fromEntries(["points", "quorums", "values", "stages", "time"].map(name => [name, model.scope[name]])), filename);
    assert.equal(index.atoms.length, new Set(model.valuation.map(row => key(row.predicate, row.args))).size, filename);
    for (const row of model.valuation) assert.equal(valueAt(index, key(row.predicate, row.args), row.time, row.point), row.value, filename);
    const failure = index.failure;
    assert.equal(failure.time, model.failure.time, filename);
    assert.equal(failure.point, model.failure.point, filename);
    assert.equal(failure.value, model.failure.value, filename);
    assert.deepEqual([...index.quorumMembers[failure.quorumIndex]].sort(), [...model.failure.quorum].sort(), filename);
  }
});

test("failure quorum matches sets and permits an external failure participant", () => {
  const index = createModelIndex(fixture());
  assert.equal(index.complete, true);
  assert.equal(index.failure.quorumIndex, 0);
  assert.equal(index.failure.point, "c");
  assert.equal(index.quorumMembers[0].has("c"), false);
  assert.deepEqual(index.scope.quorums, [["a", "b"], ["a", "b", "c"]]);
  assert.equal(index.quorumMembers.length, 2, "no superset or intersection closure may be fabricated");
  const before = clone(index.failure);
  assert.equal(valueAt(index, key("live"), 1, "a"), "b");
  assert.deepEqual(index.failure, before, "browsing another stage cannot move the original failure");
});

test("zero predicates is a complete model without fabricated atoms", () => {
  const model = fixture();
  model.valuation = [];
  const index = createModelIndex(model);
  assert.equal(index.complete, true);
  assert.deepEqual(index.atoms, []);
  assert.equal(valueAt(index, key("live"), 0, "a"), null);
});

test("atom keys and readable labels distinguish commas, parentheses, quotes and Unicode", () => {
  const values = ["a,b", "a", "b", 'a"b', "μ", "😀", ""];
  const model = fixture({ stages: 1, values });
  model.valuation = [];
  for (const point of model.scope.points) {
    model.valuation.push({ predicate: "p(a)", args: [], time: 0, point, value: "b" });
    for (const arg of values) model.valuation.push({ predicate: "p", args: [arg], time: 0, point, value: "t" });
    for (const first of values) for (const second of values) model.valuation.push({ predicate: "pair", args: [first, second], time: 0, point, value: "f" });
  }
  const index = createModelIndex(model);
  assert.equal(index.complete, true, index.issues.join("; "));
  assert.equal(new Set(index.atoms.map(atom => atom.key)).size, 57);
  assert.equal(new Set(index.atoms.map(atom => atom.label)).size, 57);
  assert.equal(atomLabel("p(a)", []), '"p(a)"');
  assert.equal(atomLabel("p", ["a,b"]), 'p("a,b")');
  assert.equal(atomLabel("p", ["a", "b"]), "p(a, b)");
  assert.equal(atomLabel("p", ["μ"]), 'p("μ")');
  assert.equal(valueAt(index, key("pair", ["a,b", "μ"]), 0, "a"), "f");
  assert.equal(valueAt(index, key("p(a)"), 0, "a"), "b");
});

test("finite and stuttering time expose exactly the represented stages", () => {
  for (const time of ["finite", "stutter"]) {
    const index = createModelIndex(fixture({ time }));
    assert.equal(index.complete, true);
    assert.equal(index.scope.time, time);
    assert.equal(valueAt(index, key("live"), 1, "b"), "f");
    for (const invalid of [-1, 2, 1.5, "1", NaN, Infinity]) assert.equal(valueAt(index, key("live"), invalid, "a"), null);
  }
});

test("missing cells and wholly omitted argument tuples are flagged, never false", () => {
  const model = fixture();
  model.valuation.splice(1, 1);
  let index = createModelIndex(model);
  assert.equal(index.valid, true);
  assert.equal(index.complete, false);
  assert.match(index.issues.join(" "), /incomplete/);
  assert.equal(valueAt(index, key("live"), 0, "b"), null);
  assert.equal(valueAt(index, key("live"), 0, "c"), "f");

  const tuples = fixture();
  for (const row of tuples.valuation) row.args = ["red"];
  index = createModelIndex(tuples);
  assert.equal(index.complete, false);
  assert.match(index.issues.join(" "), /omits argument tuples/);
  assert.equal(valueAt(index, key("live", ["blue"]), 0, "a"), null);
});

test("all duplicate cells are unavailable even if their values agree", () => {
  for (const value of ["t", "b", "f"]) {
    const model = fixture();
    model.valuation.push({ ...model.valuation[0], value });
    const index = createModelIndex(model);
    assert.equal(index.valid, true);
    assert.equal(index.complete, false);
    assert.match(index.issues.join(" "), /duplicates a cell/);
    assert.equal(valueAt(index, key("live"), 0, "a"), null);
    assert.equal(valueAt(index, key("live"), 0, "b"), "b");
  }
});

test("invalid rows and inconsistent predicate arities produce bounded diagnostics", () => {
  const variants = [null, [], {}, { value: "unknown" }, { time: -1 }, { time: 0.5 }, { time: 2 }, { point: "outside" }, { args: ["outside"] }, { args: new Array(1) }, { predicate: 9 }];
  for (const change of variants) {
    const model = fixture();
    model.valuation[0] = change && !Array.isArray(change) ? { ...model.valuation[0], ...change } : change;
    if (change && Object.keys(change).length === 0) model.valuation[0] = {};
    const index = createModelIndex(model);
    assert.equal(index.complete, false, JSON.stringify(change));
    assert.equal(valueAt(index, key("live"), 0, "a"), null, JSON.stringify(change));
  }
  const model = fixture();
  model.valuation.push({ ...model.valuation[0], args: ["red"] });
  model.valuation.push(...new Array(100).fill(null));
  const index = createModelIndex(model);
  assert.match(index.issues.join(" "), /inconsistent argument counts/);
  assert.ok(index.issues.length <= 41);
  assert.match(index.issues.at(-1), /additional data issue/);
});

test("invalid scope and generators never produce invented quorum diagrams", () => {
  const scopes = [
    null, {}, { points: [] }, { points: ["a", "a"] }, { points: new Array(1) }, { values: [] }, { stages: 0 }, { stages: 1.5 },
    { stages: Number.MAX_SAFE_INTEGER + 1 }, { time: "infinite" }, { quorums: [] }, { quorums: [[]] },
    { quorums: [["outside"]] }, { quorums: [["a", "a"]] }, { quorums: [["a", "b"], ["b", "a"]] },
    { quorums: undefined, quorum_generators: [["a"]] },
  ];
  for (const change of scopes) {
    const model = fixture();
    model.scope = change === null ? null : { ...model.scope, ...change };
    if (change && Object.keys(change).length === 0) model.scope = {};
    const index = createModelIndex(model);
    assert.equal(index.valid, false, JSON.stringify(change));
    assert.equal(index.complete, false);
    assert.equal(index.failure, null);
    assert.deepEqual(index.quorumMembers, []);
    assert.ok(index.issues.length > 0);
  }
});

test("failure metadata is checked separately from usable valuations", () => {
  for (const failure of [[], {}, { time: 9 }, { point: "outside" }, { quorum: ["a", "c"] }, { quorum: [] }, { value: "?" }, { value: "t" }, { value: "b" }]) {
    const model = fixture();
    model.failure = Array.isArray(failure) ? failure : { ...model.failure, ...failure };
    if (!Array.isArray(failure) && Object.keys(failure).length === 0) model.failure = {};
    const index = createModelIndex(model);
    assert.equal(index.valid, true);
    assert.equal(index.complete, false);
    assert.equal(index.failure, null);
    assert.equal(valueAt(index, key("live"), 0, "a"), "t");
  }
  const model = fixture();
  delete model.failure;
  assert.equal(createModelIndex(model).complete, true, "axiom models may have no failure context");
});

test("index snapshots do not retain mutable model arrays or valuation rows", () => {
  const model = fixture();
  const index = createModelIndex(model);
  model.scope.points[0] = "changed";
  model.scope.quorums[0].push("c");
  model.scope.values[0] = "changed";
  model.failure.quorum.pop();
  model.valuation[0].args.push("changed");
  model.valuation[0].value = "f";
  assert.deepEqual(index.scope.points, ["a", "b", "c"]);
  assert.deepEqual(index.scope.quorums[0], ["a", "b"]);
  assert.deepEqual(index.scope.values, ["red", "blue"]);
  assert.deepEqual(index.failure.quorum, ["b", "a"]);
  assert.deepEqual(index.atoms[0].args, []);
  assert.equal(valueAt(index, key("live"), 0, "a"), "t");
});

test("huge advertised domains are diagnosed without Cartesian allocation", () => {
  const model = fixture({ stages: 1 });
  model.scope.stages = Number.MAX_SAFE_INTEGER;
  model.valuation = [{ predicate: "p", args: new Array(1000).fill("red"), time: 0, point: "a", value: "t" }];
  const index = createModelIndex(model);
  assert.equal(index.valid, true);
  assert.equal(index.complete, false);
  assert.equal(index.atoms.length, 1);
  assert.match(index.issues.join(" "), /incomplete/);
  assert.match(index.issues.join(" "), /omits argument tuples/);
  const oversized = fixture();
  oversized.valuation = new Array(500_001);
  const capped = createModelIndex(oversized);
  assert.equal(capped.valid, false);
  assert.deepEqual(capped.atoms, []);
  assert.match(capped.issues.join(" "), /at most 500,000/);
});

test("invalid model containers and absent lookups are safely unavailable", () => {
  for (const model of [null, undefined, [], 7, "text", { ...fixture(), valuation: null }]) {
    const index = createModelIndex(model);
    assert.equal(index.valid, false);
    assert.equal(index.complete, false);
    assert.equal(valueAt(index, key("live"), 0, "a"), null);
  }
  const index = createModelIndex(fixture());
  assert.equal(valueAt(index, "unknown", 0, "a"), null);
  assert.equal(valueAt(index, key("live"), 0, "outside"), null);
  assert.equal(valueAt({}, key("live"), 0, "a"), null);
  assert.equal(valueAt(null, key("live"), 0, "a"), null);
});
