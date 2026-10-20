"""Scoped validity checking, consistency checks, and replayed countermodels."""
from dataclasses import dataclass, field
from copy import deepcopy
import math
from numbers import Real
from time import monotonic
from .compile import Compiler, ResourceLimit
from .frame import Frame, FrameLimit
from .backends import resolve_backend, solve
from .theory import validate_theory
from .progress import notify

# Re-export the established names so existing Python imports keep working.
from .witness import CounterModel, replay, TRUTH, _atomic_cell_count, _decode, _replay_axioms


def _finite_nonnegative(value):
    """Validate public time limits without leaking float conversion errors."""
    try:
        return (isinstance(value, Real) and not isinstance(value, bool)
                and math.isfinite(value) and value >= 0)
    except OverflowError:
        return False


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


def check(theory, properties=None, *, timeout=30.0, max_decisions=100000,
          max_nodes=500000, max_mu_contexts=8, solver='builtin',
          total_timeout=None, progress=None):
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
    for properties it does not refute. Optional ``progress(snapshot)`` observes
    real phase checkpoints; snapshots are detached and observer errors ignored.
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
    progress_shape = {}
    counterexamples_found = 0
    c = None
    total_decisions = 0

    def announce(phase, property=None):
        if progress is None:
            return
        fields = {**progress_shape, 'counterexamples_found': counterexamples_found,
                  'decisions': total_decisions}
        if c is not None:
            fields.update(variables=c.nvars, clauses=len(c.clauses))
        if property is not None:
            fields['property'] = property
        notify(progress, phase, **fields)

    announce('validating')
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
    progress_shape.update(points=len(theory.points), values=len(theory.values), stages=theory.stages)
    announce('frame')
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
        result = Report('unknown', theory.name, scope,
                      [PropertyResult(name, 'unknown', reason=reason) for name in names],
                      reason=reason, stats={'seconds': round(monotonic()-start, 6),
                                            'backend': selected_solver})
        announce('frame_done')
        return result
    scope = frame.describe()
    scope['values'] = list(theory.values)
    scope.pop('values_note', None)
    scope['claim'] = 'finite-scope validity; no unbounded or natural-time proof'
    report = Report('unknown',theory.name,scope)
    progress_shape['quorums'] = len(frame.quorums)

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
        announce('frame_done')
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
    announce('compiling')
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
    announce('consistency')
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
        announce('replaying')
        valuation, rows = _decode(theory,frame,compiler,baseline.assignment)
        baseline_evaluator, baseline_seen = _replay_axioms(theory,frame,valuation,max_mu_contexts)
        if exhausted():
            return unknown_remaining(0, 'total timeout exhausted during consistency replay')
        report.consistency_model = rows
        for index, name in enumerate(names):
            if exhausted():
                return unknown_remaining(index, 'total timeout exhausted before property search')
            announce('property', name)
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
                announce('replaying', name)
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
                counterexamples_found += 1
                announce('replaying', name)
    record_stats()
    announce('frame_done')
    return report
