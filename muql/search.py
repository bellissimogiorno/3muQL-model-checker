"""Bounded model finding over finite semitopologies and atomic valuations.

Frames are generated up to point isomorphism. Each frame is handed to the
existing SAT compiler; every witness is checked by the concrete evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from time import monotonic

from .checker import CounterModel, PropertyResult, _finite_nonnegative, check, replay
from .frame import FrameLimit
from .frame_search import iter_quorum_families
from .syntax import format_formula
from .theory import Theory, validate_theory
from .progress import notify


@dataclass
class SearchReport:
    """Results across a bounded class, including any unfinished obligations.

    ``complete`` says the entire frame class was exhausted without unresolved
    checks. A replayed counterexample remains conclusive even when False.
    """
    theory: str
    bounds: dict
    status: str = 'unknown'
    complete: bool = False
    properties: list[PropertyResult] = field(default_factory=list)
    reason: str = ''
    stats: dict = field(default_factory=dict)
    consistency_scope: dict | None = None
    consistency_model: list[dict] | None = None

    def to_dict(self):
        return {'schema': 'muql-search-report-v1', 'theory': self.theory,
                'bounds': self.bounds, 'status': self.status,
                'complete': self.complete, 'reason': self.reason,
                'properties': [result.to_dict() for result in self.properties],
                'stats': self.stats, 'consistency_scope': self.consistency_scope,
                'consistency_model': self.consistency_model}


def _checkpoint(deadline):
    if monotonic() >= deadline:
        raise FrameLimit('total search time budget exhausted')


def _domain(theory, size):
    """Keep named values distinct; avoid capturing any bound variable."""
    values = list(theory.values)
    forbidden = set(values) | set(theory.predicates) | set(theory._macros)
    pending = [*theory.axioms.values(), *theory.properties.values()]
    for macro in theory._macros.values():
        forbidden.update(macro.parameters)
        pending.append(macro.body)
    while pending:
        node = pending.pop()
        if node.value is not None:
            forbidden.add(node.value)
        pending.extend(node.args)
    index = 0
    while len(values) < size:
        name = f'value{index}'
        index += 1
        if name not in forbidden:
            values.append(name)
            forbidden.add(name)
    return tuple(values)


def _sizes(max_points, min_values, max_values, max_stages, deadline):
    """Visit size triples by increasing sum, without an eager Cartesian list."""
    for total in range(2 + min_values, max_points + max_values + max_stages + 1):
        for points in range(max(1, total-max_values-max_stages),
                            min(max_points, total-min_values-1) + 1):
            for values in range(max(min_values, total-points-max_stages),
                                min(max_values, total-points-1) + 1):
                _checkpoint(deadline)
                yield points, values, total-points-values


def search(theory, properties=None, *, max_points=3, max_values=None,
           max_stages=3, max_quorums=8, max_frames=1000, timeout=30.0,
           max_decisions=100000, max_nodes=500000, max_mu_contexts=8,
           solver='auto', progress=None):
    """Find countermodels without a user-supplied frame.

    Points and stages range from one to their inclusive maxima. Declared value
    names remain distinct; fresh values extend that domain up to max_values.
    Quorums range over all union-closed families containing the whole point
    set, with at most max_quorums nonempty members, up to point isomorphism.
    Declared points, stages and quorum generators are not search constraints;
    the theory's finite/stutter time convention and formulas are retained.

    The time budget is shared across enumeration, compilation and SAT queries.
    It is cooperative: concrete witness replay and native solver slices can
    overrun until the next checkpoint. Frame/solver/compilation limits leave
    obligations unknown, never proved. With no selected properties, return
    the first independently checked model of the axioms. Optional
    ``progress(snapshot)`` receives cumulative search counts and actual phase
    checkpoints, never a per-frame validity result presented as a global proof.
    """
    notify(progress, 'validating', frames_completed=0, frames_consistent=0,
           frames_inconsistent=0, frames_unknown=0, counterexamples_found=0,
           decisions=0)
    validate_theory(theory, require_scope=False)
    if max_values is None:
        max_values = max(2, len(theory.values))
    limits = {'max_points': max_points, 'max_values': max_values,
              'max_stages': max_stages, 'max_quorums': max_quorums,
              'max_frames': max_frames, 'max_nodes': max_nodes,
              'max_mu_contexts': max_mu_contexts}
    for name, value in limits.items():
        if type(value) is not int or value < 1:
            raise ValueError(f'{name} must be a positive integer')
    if type(max_decisions) is not int or max_decisions < 0 or not _finite_nonnegative(timeout):
        raise ValueError('timeout and max_decisions must be finite and nonnegative')
    if max_values < len(theory.values):
        raise ValueError(f'max_values must be at least {len(theory.values)} '
                         'to retain all named values')
    if isinstance(properties, str):
        raise ValueError('properties must be a sequence of names, not a single string')
    names = list(theory.properties) if properties is None else list(properties)
    if any(not isinstance(name, str) for name in names):
        raise ValueError('property names must be strings')
    missing = set(names) - theory.properties.keys()
    if missing:
        raise ValueError('unknown properties: ' + ', '.join(sorted(missing)))
    # Repeated CLI --property arguments do not repeat the same SAT obligation.
    names = list(dict.fromkeys(names))
    from .backends import resolve_backend
    backend = resolve_backend(solver)
    start = monotonic()
    deadline = start + timeout
    report = SearchReport(theory.name, {
        'points': [1, max_points], 'values': [len(theory.values), max_values],
        'named_values': list(theory.values), 'stages': [1, max_stages],
        'max_quorums': max_quorums, 'time': theory.time,
        'max_frames': max_frames, 'timeout': timeout,
        'max_decisions': max_decisions, 'max_nodes': max_nodes,
        'max_mu_contexts': max_mu_contexts,
        'frame_class': 'all union-closed nonempty quorum families containing the full point set, up to point isomorphism',
        'claim': 'bounded finite-model search; no unbounded or natural-time proof',
    })
    results = {name: PropertyResult(name, 'unknown') for name in names}
    unresolved: dict[str, str] = {}
    stats = {'frames': 0, 'consistent_frames': 0, 'inconsistent_frames': 0,
             'unknown_frames': 0, 'decisions': 0, 'solver': backend}
    progress_shape = {}
    counterexamples_found = 0

    def announce(phase, detail=None):
        if progress is None:
            return
        fields = {**progress_shape, 'frames_completed': stats['frames'],
                  'frames_consistent': stats['consistent_frames'],
                  'frames_inconsistent': stats['inconsistent_frames'],
                  'frames_unknown': stats['unknown_frames'],
                  'counterexamples_found': counterexamples_found,
                  'decisions': stats['decisions']}
        if detail is not None:
            fields.update({key: detail[key] for key in ('property', 'variables', 'clauses') if key in detail})
            fields['counterexamples_found'] += detail.get('counterexamples_found', 0)
            fields['decisions'] += detail.get('decisions', 0)
        notify(progress, phase, **fields)

    def frame_progress(snapshot):
        # The outer loop counts a completed frame after incorporating its
        # verified report; do not expose the inner frame_done as that count.
        if snapshot['phase'] != 'frame_done':
            announce(snapshot['phase'], snapshot)

    exhausted = False
    stop_reason = ''
    announce('enumerating')
    try:
        for npoints, nvalues, stages in _sizes(max_points, len(theory.values), max_values,
                                               max_stages, deadline):
            # An arbitrarily large requested bound must not trigger an eager
            # allocation before the ordinary node/time budgets can intervene.
            if npoints * stages > max_nodes or nvalues > max_nodes:
                raise FrameLimit('candidate size exceeds the node budget before frame allocation')
            points = tuple(f'p{i}' for i in range(npoints))
            values = _domain(theory, nvalues)
            progress_shape = {'points': npoints, 'values': nvalues, 'stages': stages}
            announce('enumerating')
            for family in iter_quorum_families(npoints, max_quorums, deadline=deadline):
                _checkpoint(deadline)
                if stats['frames'] >= max_frames:
                    raise FrameLimit(f'frame budget exhausted ({max_frames} frames)')
                candidate = replace(theory, points=points, values=values, stages=stages,
                    quorums=tuple(tuple(points[i] for i in range(npoints) if mask & (1 << i))
                                  for mask in family), scope_declared=True)
                remaining = deadline - monotonic()
                active = [name for name in names if results[name].countermodel is None]
                progress_shape = {'frame': stats['frames'] + 1, 'points': npoints,
                                  'values': nvalues, 'stages': stages, 'quorums': len(family)}
                announce('frame')
                observer = {'progress': frame_progress} if progress is not None else {}
                if progress is not None:
                    # Synchronous observation consumes the same time budget.
                    # Keep the established clock path unchanged when disabled.
                    remaining = deadline - monotonic()
                checked = check(candidate, active, timeout=max(0.0, remaining),
                                total_timeout=max(0.0, remaining),
                                max_decisions=max_decisions, max_nodes=max_nodes,
                                max_mu_contexts=max_mu_contexts, solver=backend, **observer)
                stats['frames'] += 1
                stats['decisions'] += checked.stats.get('decisions', 0)
                if checked.status == 'inconsistent':
                    stats['inconsistent_frames'] += 1
                elif checked.consistency_model is not None:
                    stats['consistent_frames'] += 1
                    if report.consistency_model is None:
                        report.consistency_model = checked.consistency_model
                        report.consistency_scope = checked.scope
                if checked.status == 'unknown':
                    stats['unknown_frames'] += 1
                by_name = {item.name: item for item in checked.properties}
                for name in active:
                    item = by_name.get(name)
                    if item is not None and item.countermodel is not None:
                        results[name] = item
                        counterexamples_found += 1
                        unresolved.pop(name, None)
                    elif checked.status != 'inconsistent' and (item is None or item.status != 'holds'):
                        unresolved.setdefault(name, (item.reason if item else checked.reason)
                                              or 'a candidate frame was not decided')
                progress_shape.update({key: checked.stats[key] for key in ('variables', 'clauses') if key in checked.stats})
                announce('frame_done')
                if not names and checked.consistency_model is not None:
                    report.status = 'satisfiable'
                    stop_reason = 'Found an independently checked model of the axioms.'
                    break
                if names and all(item.countermodel is not None for item in results.values()):
                    report.status = 'counterexample'
                    stop_reason = 'Found an independently replayed counterexample for every selected property.'
                    break
                progress_shape = {'points': npoints, 'values': nvalues, 'stages': stages}
                announce('enumerating')
            else:
                continue
            break
        else:
            exhausted = True
    except FrameLimit as error:
        stop_reason = str(error)
    # A completed frame query can finish just after the cooperative deadline.
    # A returned witness is still sound; unfinished properties remain unknown.
    report.complete = exhausted and not unresolved and (bool(names) or stats['unknown_frames'] == 0)
    if exhausted:
        if stats['consistent_frames'] == 0 and stats['unknown_frames'] == 0:
            report.status = 'inconsistent'
            stop_reason = 'No model satisfies the axioms anywhere within these bounds; no property is reported as proved.'
        elif unresolved or (not names and stats['unknown_frames']):
            report.status = 'unknown'
            stop_reason = 'All candidate frames were visited, but some checks exceeded a resource limit.'
        else:
            report.status = 'complete'
            stop_reason = 'Exhausted the bounded frame class. Results apply only within these bounds.'
    for name, item in results.items():
        if item.countermodel is not None:
            continue
        if report.status == 'inconsistent':
            item.status = 'inconsistent'
            item.reason = 'No satisfying model within the search bounds.'
        elif exhausted and name not in unresolved:
            item.status = 'holds'
            item.reason = 'No counterexample in the entire bounded frame class; at least one axiom model exists.'
        else:
            item.status = 'unknown'
            item.reason = unresolved.get(name, stop_reason) or 'search incomplete'
    report.reason = stop_reason
    report.properties = list(results.values())
    stats['seconds'] = round(monotonic() - start, 6)
    report.stats = stats
    return report


def witness_theory(theory, countermodel, *, max_mu_contexts=8):
    """Recover and independently validate a witness's concrete scoped theory.

    Use with ``format_theory`` to save a standalone input for ``check`` or
    ``replay``. Original retained axioms and properties are always preserved.
    """
    validate_theory(theory, require_scope=False)
    data = countermodel.to_dict() if isinstance(countermodel, CounterModel) else countermodel
    if not isinstance(data, dict) or not isinstance(data.get('scope'), dict):
        raise ValueError('countermodel must include a scope object')
    scope = data['scope']
    for name in ('points', 'values', 'quorums'):
        if not isinstance(scope.get(name), list):
            raise ValueError(f'malformed countermodel scope: {name}')
    if (any(not isinstance(value, str) for value in scope['values'])
            or not set(theory.values).issubset(scope['values'])):
        raise ValueError('countermodel must retain all named values')
    if scope.get('time') != theory.time:
        raise ValueError('countermodel time convention does not match the theory')
    if any(not isinstance(quorum, list) for quorum in scope['quorums']):
        raise ValueError('malformed countermodel quorums')
    scoped = replace(theory, points=tuple(scope['points']), values=tuple(scope['values']),
                     stages=scope.get('stages'), quorums=tuple(tuple(q) for q in scope['quorums']),
                     scope_declared=True)
    replay(scoped, data, max_mu_contexts=max_mu_contexts)
    return scoped


def format_theory(theory, *, notation='unicode'):
    """Serialize expanded formulas and an explicit scope as literate Markdown."""
    if notation not in ('unicode', 'ascii'):
        raise ValueError("notation must be 'unicode' or 'ascii'")
    validate_theory(theory)
    # repr escapes every Unicode line separator as well as literal newlines;
    # the loader must not split a quoted name into separate declarations.
    quote = repr if notation == 'unicode' else ascii
    lines = ['# Generated finite model scope', '',
             'This standalone theory retains the searched axioms and properties.',
             'Its explicit frame can be checked again or used to replay the accompanying witness.',
             '', '```muql', f'theory {quote(theory.name)}',
             'points ' + ' '.join(map(quote, theory.points)),
             'values ' + ' '.join(map(quote, theory.values)),
             f'stages {theory.stages}', f'time {theory.time}',
             'quorums ' + ' '.join('{' + ','.join(map(quote, quorum)) + '}'
                                  for quorum in theory.quorums)]
    lines.extend(f'predicate {name}/{arity}' for name, arity in theory.predicates.items())
    for kind, formulas in (('axiom', theory.axioms), ('property', theory.properties)):
        lines.append('')
        lines.extend(f'{kind} {name}: {format_formula(formula, notation=notation)}'
                     for name, formula in formulas.items())
    lines.extend(['```', ''])
    return '\n'.join(lines)
