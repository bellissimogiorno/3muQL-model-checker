/**
 * Index a countermodel without constructing its Cartesian valuation domain.
 *
 * createModelIndex(model) returns snapshots of scope and atoms, exact quorum
 * membership sets, a validated failure context (including quorumIndex), and
 * diagnostics. `valid` means the scope and valuation container are usable;
 * `complete` additionally requires no diagnostic. Missing/ambiguous cells are
 * always null, never false. Completeness can check observed predicates, but
 * cannot detect a predicate omitted entirely without the theory declarations.
 *
 * valueAt(index, atomKey, time, point) reads represented stages only, including
 * for stuttering frames: temporal continuation is a separate semantic rule.
 * The module does not evaluate formulas, infer quorums from generators, or
 * infer message/event edges. Callers should treat returned objects as read-only.
 */

const indexes = new WeakMap();
const TRUTH_VALUES = new Set(["t", "b", "f"]);
const MAX_ROWS = 500_000;
const MAX_ISSUES = 40;

function nameLabel(name) {
  return /^[A-Za-z_][A-Za-z_0-9]*$/.test(name) ? name : JSON.stringify(name);
}

function namesValid(names, { nonempty = false } = {}) {
  return Array.isArray(names) && (!nonempty || names.length > 0)
    && !names.includes(undefined) && names.every(name => typeof name === "string")
    && new Set(names).size === names.length;
}

function sameMembers(left, right) {
  return left.size === right.size && [...left].every(point => right.has(point));
}

/** Display labels quote punctuation so distinct atoms cannot appear identical. */
export function atomLabel(predicate, args) {
  const name = nameLabel(predicate);
  return args.length ? `${name}(${args.map(nameLabel).join(", ")})` : name;
}

export function createModelIndex(model) {
  const issues = [];
  let omittedIssues = 0;
  const issue = message => {
    if (issues.length < MAX_ISSUES) issues.push(message);
    else omittedIssues++;
  };
  const finish = result => {
    if (omittedIssues) issues.push(`${omittedIssues} additional data issue(s) omitted.`);
    result.complete = result.valid && issues.length === 0;
    return result;
  };
  const emptyScope = { points: [], quorums: [], values: [], stages: 0, time: "finite" };
  const result = { scope: emptyScope, pointNames: [], quorumMembers: [], atoms: [], failure: null, issues, valid: false, complete: false };
  const data = new Map();
  indexes.set(result, data);
  if (!model || typeof model !== "object" || Array.isArray(model)) {
    issue("The model is not an object.");
    return finish(result);
  }
  const scope = model.scope;
  if (!scope || typeof scope !== "object" || Array.isArray(scope)) {
    issue("The model has no usable scope.");
    return finish(result);
  }
  if (!namesValid(scope.points, { nonempty: true })) issue("Participants must be a nonempty list of distinct names.");
  if (!namesValid(scope.values, { nonempty: true })) issue("Values must be a nonempty list of distinct names.");
  if (!Number.isSafeInteger(scope.stages) || scope.stages < 1) issue("The number of stages must be a positive safe integer.");
  if (scope.time !== "finite" && scope.time !== "stutter") issue("Time must be finite or stutter.");
  if (!Array.isArray(scope.quorums) || scope.quorums.length === 0) {
    issue("The model must list its actual quorums; generators alone do not specify a diagram.");
  }
  if (issues.length) return finish(result);

  const pointSet = new Set(scope.points);
  const valueSet = new Set(scope.values);
  const quorumMembers = [];
  const quorumKeys = new Set();
  for (const [number, quorum] of scope.quorums.entries()) {
    if (!namesValid(quorum, { nonempty: true }) || quorum.some(point => !pointSet.has(point))) {
      issue(`Quorum ${number + 1} must contain distinct declared participants and cannot be empty.`);
      continue;
    }
    const key = JSON.stringify([...quorum].sort());
    if (quorumKeys.has(key)) issue(`Quorum ${number + 1} duplicates an earlier quorum.`);
    quorumKeys.add(key);
    quorumMembers.push(new Set(quorum));
  }
  if (issues.length) return finish(result);

  result.scope = {
    points: [...scope.points], values: [...scope.values],
    quorums: scope.quorums.map(quorum => [...quorum]),
    stages: scope.stages, time: scope.time,
  };
  result.pointNames = result.scope.points;
  result.quorumMembers = quorumMembers;
  if (!Array.isArray(model.valuation)) {
    issue("The model has no atomic valuation list.");
    return finish(result);
  }
  if (model.valuation.length > MAX_ROWS) {
    issue(`The diagram supports at most ${MAX_ROWS.toLocaleString("en")} atomic valuation rows. Use the complete JSON download for this model.`);
    return finish(result);
  }
  result.valid = true;

  if (model.failure != null) {
    const failure = model.failure;
    if (typeof failure !== "object" || Array.isArray(failure)
        || !Number.isSafeInteger(failure.time) || failure.time < 0 || failure.time >= scope.stages
        || !pointSet.has(failure.point) || failure.value !== "f"
        || !namesValid(failure.quorum, { nonempty: true })) {
      issue("The failure context is malformed or outside the represented scope.");
    } else {
      const members = new Set(failure.quorum);
      const quorumIndex = quorumMembers.findIndex(quorum => sameMembers(quorum, members));
      if (quorumIndex < 0) issue("The failure context does not name an actual quorum.");
      else result.failure = { time: failure.time, point: failure.point, quorum: [...failure.quorum], value: failure.value, quorumIndex };
    }
  }

  const predicates = new Map();
  for (const [number, row] of model.valuation.entries()) {
    if (!row || typeof row !== "object" || Array.isArray(row)
        || typeof row.predicate !== "string" || !Array.isArray(row.args)
        || row.args.includes(undefined)
        || row.args.some(arg => typeof arg !== "string" || !valueSet.has(arg))
        || !Number.isSafeInteger(row.time) || row.time < 0 || row.time >= scope.stages
        || !pointSet.has(row.point) || !TRUTH_VALUES.has(row.value)) {
      issue(`Atomic valuation row ${number + 1} is malformed or outside the represented scope.`);
      continue;
    }
    let predicate = predicates.get(row.predicate);
    if (!predicate) {
      predicate = { arity: row.args.length, atoms: 0 };
      predicates.set(row.predicate, predicate);
    } else if (predicate.arity !== row.args.length) {
      issue(`Predicate ${nameLabel(row.predicate)} has inconsistent argument counts.`);
      continue;
    }
    const key = JSON.stringify([row.predicate, row.args]);
    let cells = data.get(key);
    if (!cells) {
      cells = new Map();
      data.set(key, cells);
      result.atoms.push({ key, predicate: row.predicate, args: [...row.args], label: atomLabel(row.predicate, row.args) });
      predicate.atoms++;
    }
    const cellKey = JSON.stringify([row.time, row.point]);
    if (cells.has(cellKey)) {
      cells.set(cellKey, null);
      issue(`Atomic valuation row ${number + 1} duplicates a cell; its value is unavailable.`);
    } else cells.set(cellKey, row.value);
  }

  for (const atom of result.atoms) {
    const count = data.get(atom.key).size;
    // Division avoids overflowing when a malformed scope advertises huge time.
    if (count / scope.points.length !== scope.stages) issue(`The valuation of ${atom.label} is incomplete across participants or stages.`);
  }
  for (const [name, predicate] of predicates) {
    // Bounded multiplication detects omitted tuples without generating them.
    let expected = 1;
    for (let arg = 0; arg < predicate.arity; arg++) {
      if (expected > predicate.atoms / scope.values.length) {
        expected = predicate.atoms + 1;
        break;
      }
      expected *= scope.values.length;
    }
    if (expected !== predicate.atoms) issue(`The valuation omits argument tuples for ${nameLabel(name)}.`);
  }
  return finish(result);
}

export function valueAt(index, atomKey, time, point) {
  if (!Number.isSafeInteger(time) || time < 0 || time >= index?.scope?.stages || typeof point !== "string") return null;
  return indexes.get(index)?.get(atomKey)?.get(JSON.stringify([time, point])) ?? null;
}
