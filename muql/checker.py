"""Scoped validity checking, consistency checks, and replayed countermodels."""
from dataclasses import dataclass, field
from copy import deepcopy
from itertools import product
import math
from numbers import Real
from time import monotonic
from .compile import Compiler, ResourceLimit
from .evaluate import Evaluator
from .frame import Frame, FrameLimit
from .backends import resolve_backend, solve
from .theory import validate_theory

TRUTH = ('f', 'b', 't')


def _finite_nonnegative(value):
    """Validate public time limits without leaking float conversion errors."""
    try:
        return (isinstance(value, Real) and not isinstance(value, bool)
                and math.isfinite(value) and value >= 0)
    except OverflowError:
        return False


def _atomic_cell_count(theory, frame, limit):
    """Count complete atomic cells, stopping at ``limit + 1``.

    Counting must not materialize argument tuples or enormous integers just
    to reject an incomplete witness or an over-budget check. Singleton value
    domains require one tuple at every arity, including unused predicates.
    """
    total = 0
    for arity in theory.predicates.values():
        cells = frame.stages * len(frame.points)
        if cells > limit - total:
            return limit + 1
        if len(theory.values) > 1:
            for _ in range(arity):
                cells *= len(theory.values)
                if cells > limit - total:
                    return limit + 1
        total += cells
    return total


@dataclass
class CounterModel:
    """A complete atomic valuation plus an independently checked failure."""
    theory: str
    scope: dict
    valuation: list[dict]
    failure: dict
    axiom_values: dict[str, list[str]]
    property: str
    replayed: bool = True

    def to_dict(self):
        return {'schema': 'muql-countermodel-v1', 'theory': self.theory,
                'scope': self.scope, 'property': self.property,
                'failure': self.failure, 'valuation': self.valuation,
                'axiom_values': self.axiom_values, 'replayed': self.replayed}

    def format(self):
        where = self.failure
        lines = [f'Countermodel for {self.property}: f at stage {where["time"]}, '
                 f'point {where["point"]}, quorum {{{", ".join(where["quorum"])}}}',
                 'All retained axioms are valid (t or b); independently replayed.',
                 '  stage  point          predicate(arguments)             value']
        for row in self.valuation:
            atom = row['predicate'] + '(' + ','.join(row['args']) + ')'
            lines.append(f'  {row["time"]:<6} {row["point"]:<14} {atom:<32} {row["value"]}')
        return '\n'.join(lines)


@dataclass
class PropertyResult:
    name: str
    status: str
    countermodel: CounterModel | None = None
    reason: str = ''

    def to_dict(self):
        result = {'name': self.name, 'status': self.status, 'reason': self.reason}
        if self.countermodel is not None:
            result['countermodel'] = self.countermodel.to_dict()
        return result


@dataclass
class Report:
    status: str
    theory: str
    scope: dict
    properties: list[PropertyResult] = field(default_factory=list)
    consistency_model: list[dict] | None = None
    reason: str = ''
    stats: dict = field(default_factory=dict)

    def to_dict(self):
        return {'schema': 'muql-report-v1', 'status': self.status, 'theory': self.theory,
                'scope': self.scope, 'reason': self.reason,
                'properties': [p.to_dict() for p in self.properties],
                'consistency_model': self.consistency_model, 'stats': self.stats}


def _decode(theory, frame, compiler, assignment):
    def bit(lit):
        value = assignment.get(abs(lit), False)
        return value if lit > 0 else not value
    valuation, rows = {}, []
    for name, arity in theory.predicates.items():
        for t, p, terms in product(range(frame.stages), range(len(frame.points)),
                                   product(theory.values, repeat=arity)):
            key = (name,t,p,terms)
            pair = compiler.cells.get(key, compiler.f)
            value = int(bit(pair[0])) + int(bit(pair[1]))
            valuation[key] = value
            rows.append({'predicate':name,'time':t,'point':frame.points[p],
                         'args':list(terms),'value':TRUTH[value]})
    return valuation, rows


def _replay_axioms(theory, frame, valuation, max_mu_contexts=8):
    evaluator = Evaluator(theory, frame, valuation, nonmonotone_limit=max_mu_contexts)
    seen = {}
    for name, formula in theory.axioms.items():
        values = {evaluator.eval(formula, ctx) for ctx in frame.contexts}
        if 0 in values:
            raise RuntimeError(f'internal validation error: SAT model fails axiom {name!r}')
        seen[name] = [TRUTH[v] for v in sorted(values)]
    return evaluator, seen


def check(theory, properties=None, *, timeout=30.0, max_decisions=100000,
          max_nodes=500000, max_mu_contexts=8, solver='builtin',
          total_timeout=None):
    """Search all valuations in one declared finite scope.

    ``holds`` means no countervaluation in this scope, and only follows a
    successful consistency check. ``unknown`` is never converted to a pass.
    Timeout applies separately to frame construction, compilation and each SAT
    query. Optional ``total_timeout`` additionally covers the whole call,
    including checkpoints after concrete replay; expensive Python/native
    operations are cooperative and can finish after the deadline, but their
    late result is reported as unknown. Parsing and output remain separate.
    ``solver='auto'`` uses optional PySAT when available, otherwise built-in.
    A consistency model that also refutes a selected property is reused after
    independently checking that failure; further SAT queries are only needed
    for properties it does not refute.
    """
    if (not _finite_nonnegative(timeout)
            or type(max_decisions) is not int or max_decisions < 0
            or type(max_nodes) is not int or max_nodes < 1
            or type(max_mu_contexts) is not int or max_mu_contexts < 1):
        raise ValueError('resource limits must be nonnegative (node/context limits positive)')
    if total_timeout is not None and not _finite_nonnegative(total_timeout):
        raise ValueError('total_timeout must be finite and nonnegative, or None')
    start = monotonic()
    deadline = start + total_timeout if total_timeout is not None else math.inf
    validate_theory(theory)
    selected_solver = resolve_backend(solver)

    def exhausted():
        return total_timeout is not None and monotonic() >= deadline

    def phase_timeout():
        return min(timeout, max(0.0, deadline - monotonic()))

    if isinstance(properties, str):
        raise ValueError('properties must be a sequence of names, not a single string')
    names = list(theory.properties) if properties is None else list(properties)
    if any(not isinstance(name, str) for name in names):
        raise ValueError('property names must be strings')
    missing = set(names) - theory.properties.keys()
    if missing: raise ValueError('unknown properties: ' + ', '.join(sorted(missing)))
    try:
        frame = Frame.from_theory(theory, deadline=min(start + timeout, deadline))
    except FrameLimit as error:
        # Closure was not completed. Record the requested generators without
        # representing them as the computed semitopology.
        scope = {'points': list(theory.points), 'values': list(theory.values),
                 'quorum_generators': [list(q) for q in theory.quorums],
                 'stages': theory.stages, 'time': theory.time,
                 'claim': 'frame construction incomplete; no validity result'}
        reason = 'total timeout exhausted' if exhausted() else str(error)
        return Report('unknown', theory.name, scope,
                      [PropertyResult(name, 'unknown', reason=reason) for name in names],
                      reason=reason, stats={'seconds': round(monotonic()-start, 6),
                                            'backend': selected_solver})
    scope = frame.describe()
    scope['values'] = list(theory.values)
    scope.pop('values_note', None)
    scope['claim'] = 'finite-scope validity; no unbounded or natural-time proof'
    report = Report('unknown',theory.name,scope)
    c = None
    total_decisions = 0

    def record_stats():
        report.stats = {'seconds': round(monotonic()-start, 6),
                        'backend': selected_solver, 'decisions': total_decisions}
        if c is not None:
            report.stats.update(variables=c.nvars, clauses=len(c.clauses))

    def unknown_remaining(index, reason):
        report.status = 'unknown'
        report.reason = reason
        report.properties.extend(PropertyResult(name, 'unknown', reason=reason)
                                 for name in names[index:])
        record_stats()
        return report

    if exhausted():
        return unknown_remaining(0, 'total timeout exhausted after frame construction')
    if frame.stages * len(frame.points) * len(frame.quorums) > max_nodes:
        return unknown_remaining(0, 'context count exceeds the node budget before compilation')
    if any(arity > max_nodes for arity in theory.predicates.values()):
        return unknown_remaining(0, 'predicate arity exceeds the node budget for complete atomic cells')
    if _atomic_cell_count(theory, frame, max_nodes) > max_nodes:
        return unknown_remaining(0, 'complete atomic valuation exceeds the node budget')
    compiler = Compiler(theory,frame,timeout=phase_timeout(),max_nodes=max_nodes,max_mu_contexts=max_mu_contexts)
    c = compiler.circuit
    try:
        for formula in theory.axioms.values():
            # Quantify globally over all n,p,O, including p outside O.
            for ctx in frame.contexts:
                c.add_clause(compiler.eval(formula,ctx)[0])
        # Compile every selected property before solving to share the circuit.
        failures = {}
        for name in names:
            failures[name] = c.or_(*(-compiler.eval(theory.properties[name],ctx)[0]
                                    for ctx in frame.contexts))
        compiler.budget(force=True)
    except (ResourceLimit, RecursionError) as error:
        reason = ('total timeout exhausted' if exhausted() else
                  str(error) or 'formula exceeds Python recursion depth')
        return unknown_remaining(0, reason)
    if exhausted():
        return unknown_remaining(0, 'total timeout exhausted after compilation')
    baseline = solve(c.nvars,c.clauses,timeout=phase_timeout(),max_decisions=max_decisions,
                     backend=selected_solver)
    total_decisions = baseline.decisions
    if exhausted():
        return unknown_remaining(0, 'total timeout exhausted during consistency search')
    if baseline.status == 'unsat':
        report.status = 'inconsistent'
        report.reason = ('No valuation satisfies every axiom in this scope. No properties are reported as proved. '
                         'Check the frame, truth requirements, and temporal boundary.')
    elif baseline.status == 'unknown':
        report.reason = 'axiom consistency unknown: ' + baseline.reason
        report.properties = [PropertyResult(name,'unknown',reason=report.reason) for name in names]
    else:
        report.status = 'checked'
        valuation, rows = _decode(theory,frame,compiler,baseline.assignment)
        baseline_evaluator, baseline_seen = _replay_axioms(theory,frame,valuation,max_mu_contexts)
        if exhausted():
            return unknown_remaining(0, 'total timeout exhausted during consistency replay')
        report.consistency_model = rows
        for index, name in enumerate(names):
            if exhausted():
                return unknown_remaining(index, 'total timeout exhausted before property search')
            # All selected properties are already in the baseline circuit. If
            # that complete assignment satisfies this failure literal, it is
            # also a candidate countermodel; another SAT search adds no evidence.
            # Still evaluate the property's actual failure independently below.
            failure = failures[name]
            reuse_baseline = baseline.assignment[abs(failure)] == (failure > 0)
            if reuse_baseline:
                result = baseline
            else:
                result = solve(c.nvars, [*c.clauses,[failure]],timeout=phase_timeout(),
                               max_decisions=max_decisions,backend=selected_solver)
                total_decisions += result.decisions
            if exhausted():
                return unknown_remaining(index, 'total timeout exhausted during property search')
            if result.status == 'unsat':
                report.properties.append(PropertyResult(name,'holds',reason='No countermodel in the declared scope.'))
            elif result.status == 'unknown':
                report.properties.append(PropertyResult(name,'unknown',reason=result.reason))
                report.status = 'unknown'
            else:
                if reuse_baseline:
                    evaluator, seen = baseline_evaluator, baseline_seen
                    # Reports expose mutable JSON-style rows. Keep each saved
                    # witness independent of the consistency model and siblings.
                    rows = deepcopy(report.consistency_model)
                else:
                    valuation, rows = _decode(theory,frame,compiler,result.assignment)
                    evaluator, seen = _replay_axioms(theory,frame,valuation,max_mu_contexts)
                failed = next((ctx for ctx in frame.contexts if evaluator.eval(theory.properties[name],ctx) == 0),None)
                if exhausted():
                    return unknown_remaining(index, 'total timeout exhausted during countermodel replay')
                if failed is None:
                    raise RuntimeError(f'internal validation error: no failure for {name!r}')
                t,p,q = failed
                witness = CounterModel(theory.name,scope,rows,
                    {'time':t,'point':frame.points[p],
                     'quorum':[frame.points[x] for x in sorted(frame.quorums[q])],'value':'f'},
                    deepcopy(seen) if reuse_baseline else seen,name)
                report.properties.append(PropertyResult(name,'counterexample',witness))
    record_stats()
    return report


def _replay_saved(theory, countermodel, *, max_mu_contexts=8):
    """Validate a saved countermodel against the *supplied* theory.

    This ignores the serialized ``replayed`` flag and verifies the complete
    valuation, all axioms at all contexts, and the named property's failure.
    """
    validate_theory(theory)
    if type(max_mu_contexts) is not int or max_mu_contexts < 1:
        raise ValueError('max_mu_contexts must be a positive integer')
    data = countermodel.to_dict() if isinstance(countermodel,CounterModel) else countermodel
    if not isinstance(data, dict): raise ValueError('countermodel must be a JSON object')
    if data.get('schema') != 'muql-countermodel-v1': raise ValueError('unsupported countermodel schema')
    frame = Frame.from_theory(theory)
    scope = data.get('scope',{})
    if (not isinstance(scope, dict) or type(scope.get('stages')) is not int
            or not _string_list(scope.get('points'))
            or not _string_list(scope.get('values'))
            or not isinstance(scope.get('quorums'), list)
            or not all(_string_list(q) for q in scope['quorums'])):
        raise ValueError('malformed countermodel scope')
    if any(scope.get(k) != v for k,v in frame.describe().items() if k != 'values_note') or scope.get('values') != list(theory.values):
        raise ValueError('countermodel scope does not match theory')
    valuation = {}
    if not isinstance(data.get('valuation'), list):
        raise ValueError('countermodel valuation must be a list of cells')
    if _atomic_cell_count(theory, frame, len(data['valuation'])) != len(data['valuation']):
        raise ValueError('countermodel must contain exactly every atomic cell')
    point_index = {name: index for index, name in enumerate(frame.points)}
    values = set(theory.values)
    for row in data['valuation']:
        if (not isinstance(row, dict) or not isinstance(row.get('predicate'), str)
                or type(row.get('time')) is not int or not isinstance(row.get('point'), str)
                or not _string_list(row.get('args')) or row.get('value') not in TRUTH):
            raise ValueError('malformed countermodel cell')
        if (row['predicate'] not in theory.predicates
                or not 0 <= row['time'] < frame.stages
                or row['point'] not in point_index
                or len(row['args']) != theory.predicates[row['predicate']]
                or any(value not in values for value in row['args'])):
            raise ValueError('countermodel contains an undeclared atomic cell')
        key = (row['predicate'],row['time'],point_index[row['point']],tuple(row['args']))
        if key in valuation: raise ValueError('duplicate countermodel cell')
        valuation[key] = TRUTH.index(row['value'])
    # Every row is a distinct member of the finite atomic signature, and the
    # cardinality matches, so no second Cartesian set is needed for completeness.
    name = data['property']
    if not isinstance(name, str): raise ValueError('countermodel property must be a name')
    if name not in theory.properties: raise ValueError(f'unknown property {name!r}')
    failure = data['failure']
    if (not isinstance(failure, dict) or type(failure.get('time')) is not int
            or not isinstance(failure.get('point'), str)
            or not _string_list(failure.get('quorum'))
            or len(set(failure['quorum'])) != len(failure['quorum'])):
        raise ValueError('malformed countermodel failure context')
    if (not 0 <= failure['time'] < frame.stages
            or failure['point'] not in point_index
            or any(point not in point_index for point in failure['quorum'])):
        raise ValueError('claimed property failure is outside the finite frame')
    qset = frozenset(point_index[p] for p in failure['quorum'])
    ctx = (failure['time'],point_index[failure['point']],frame.quorums.index(qset))
    if failure.get('value') != 'f':
        raise ValueError('claimed property failure must have value f')
    evaluator, _ = _replay_axioms(theory,frame,valuation,max_mu_contexts)
    if evaluator.eval(theory.properties[name],ctx) != 0:
        raise ValueError('claimed property failure does not replay')
    return True


def _string_list(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def replay(theory, countermodel, *, max_mu_contexts=8):
    """Independently verify a serialized complete countermodel.

    Raises ValueError for malformed data or an invalid witness. Does not trust
    any self-reported replay flag or previously recorded axiom values.
    """
    try:
        return _replay_saved(theory, countermodel, max_mu_contexts=max_mu_contexts)
    except FrameLimit:
        raise
    except (KeyError, IndexError, TypeError, AttributeError, RuntimeError) as error:
        raise ValueError(f'invalid countermodel: {error}') from error
