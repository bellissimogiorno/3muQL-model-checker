"""Complete countermodel data, SAT decoding, and independent witness replay.

Witness validation is shared by checking, CLI replay, and browser exports.
It recomputes the mathematical conditions instead of trusting saved flags or
axiom summaries. This module has no dependency on the SAT solver or checker
orchestration; the concrete evaluator remains independent of compilation.
"""
from dataclasses import dataclass
from itertools import product

from .evaluate import Evaluator
from .frame import Frame, FrameLimit
from .theory import validate_theory

TRUTH = ('f', 'b', 't')


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
