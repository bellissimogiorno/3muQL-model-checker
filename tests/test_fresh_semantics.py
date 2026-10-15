"""Fresh semantic audit using complete vectors and literal truth tables.

The oracle below uses neither production evaluator helpers nor the compiler's
dependency graph, monotonicity certificate, or leader optimization. Recurrences
enumerate every interpretation on the entire frame, including contexts whose
point is outside the current quorum. The compiler is checked in both directions:
one model must have the expected bits, and forcing any different bit must be
unsatisfiable.
"""

from itertools import product
import random
import unittest
from unittest.mock import patch

from muql.compile import Compiler
from muql.evaluate import EvaluationError, Evaluator
from muql.frame import Frame
from muql.sat import solve
from muql.syntax import Node
from muql.theory import Theory


UNARY = {
    'not': (2, 1, 0), 'T': (0, 0, 2), 'F': (2, 0, 0),
    'B': (0, 2, 0), 'TB': (0, 2, 2), 'TF': (2, 0, 2), 'FB': (2, 2, 0),
}
BINARY = {
    'and': ((0, 0, 0), (0, 1, 1), (0, 1, 2)),
    'or': ((0, 1, 2), (1, 1, 2), (2, 2, 2)),
    'weak': ((2, 2, 2), (1, 1, 2), (0, 1, 2)),
    'strong': ((2, 2, 2), (1, 1, 2), (0, 0, 2)),
    'equiv': ((2, 0, 0), (0, 2, 0), (0, 0, 2)),
    'order': ((2, 2, 2), (0, 2, 2), (0, 0, 2)),
    'xor': ((0, 1, 2), (1, 1, 1), (2, 1, 0)),
}
MODAL = ('diamond', 'box', 'existsQ', 'forallQ', 'somewhere',
         'everywhere', 'quorum', 'contra')
TEMPORAL = ('yesterday', 'tomorrow', 'once', 'past', 'historically',
            'sometime', 'forever', 'infinitely', 'ultimately')


def node(op, *children, value=None):
    return Node(op, tuple(children), value=value)


def make_theory(frame, values=('red', 'blue')):
    return Theory('fresh semantic audit', frame.points, values, frame.stages,
                  tuple(tuple(frame.points[p] for p in q) for q in frame.quorums),
                  {'P': 0, 'Q': 0, 'R': 1}, {}, {}, time=frame.time)


def oracle(formula, frame, valuation, values, env=None, bindings=None):
    """Return one truth value for every context, via full lattice semantics."""
    env, bindings = env or {}, bindings or {}
    contexts = tuple(product(range(frame.stages), range(len(frame.points)),
                             range(len(frame.quorums))))
    index = {ctx: i for i, ctx in enumerate(contexts)}
    size = len(contexts)
    op, args = formula.op, formula.args

    def term(arg):
        return arg.value if arg.op == 'literal' else env.get(arg.value, arg.value)

    def child(arg, variables=env, fixed=bindings):
        return oracle(arg, frame, valuation, values, variables, fixed)

    def future(time):
        # Spell out the temporal relation without calling Frame.future.
        return [t for t in range(frame.stages) if t > time or
                (frame.time == 'stutter' and t == time == frame.stages - 1)]

    if op == 'const':
        return ({'f': 0, 'b': 1, 't': 2}[formula.value],) * size
    if op == 'pred':
        return tuple(valuation[(formula.value, t, p, tuple(map(term, args)))]
                     for t, p, q in contexts)
    if op == 'var':
        return bindings[formula.value]
    if op in ('eq', 'neq'):
        return (2 if (term(args[0]) == term(args[1])) == (op == 'eq') else 0,) * size
    if op in UNARY:
        return tuple(UNARY[op][v] for v in child(args[0]))
    if op in BINARY:
        return tuple(BINARY[op][a][b] for a, b in zip(child(args[0]), child(args[1])))
    if op in ('forall', 'exists', 'affine', 'unique'):
        columns = [child(args[0], {**env, formula.value: value}) for value in values]
        result = []
        for i in range(size):
            witnesses = [column[i] for column in columns]
            if op == 'forall':
                result.append(min(witnesses, default=2))
            elif op == 'exists':
                result.append(max(witnesses, default=0))
            else:
                # Direct defining formula ∀a,a'. (P(a) ∧ P(a')) → a=a'.
                affine = min((BINARY['weak'][BINARY['and'][a][b]][2 if j == k else 0]
                              for j, a in enumerate(witnesses)
                              for k, b in enumerate(witnesses)), default=2)
                result.append(affine if op == 'affine' else
                              min(affine, max(witnesses, default=0)))
        return tuple(result)
    if op in ('mu', 'nu'):
        answer = [2 if op == 'mu' else 0] * size
        for candidate in product(range(3), repeat=size):
            image = child(args[0], fixed={**bindings, formula.value: candidate})
            good = (all(a <= b for a, b in zip(image, candidate)) if op == 'mu' else
                    all(a >= b for a, b in zip(image, candidate)))
            if good:
                combine = min if op == 'mu' else max
                answer = [combine(a, b) for a, b in zip(answer, candidate)]
        return tuple(answer)
    if op == 'latest':
        columns = {value: child(args[1], {**env, formula.value: value}) for value in values}
        result = []
        for time, point, quorum in contexts:
            eligible = [past for past in range(time)
                        if any(column[index[past, point, quorum]] == 2
                               for column in columns.values())]
            result.append(2 if eligible and
                          columns[term(args[0])][index[max(eligible), point, quorum]] == 2 else 0)
        return tuple(result)
    if op in MODAL + TEMPORAL:
        body = child(args[0])

        def at(t, p, q):
            return body[index[t, p, q]]

        result = []
        for t, p, q in contexts:
            if op in ('diamond', 'box'):
                row = [at(t, member, q) for member in frame.quorums[q]]
                value = max(row) if op == 'diamond' else min(row)
            elif op in ('existsQ', 'forallQ'):
                row = [at(t, p, other) for other in range(len(frame.quorums))]
                value = max(row) if op == 'existsQ' else min(row)
            elif op in ('somewhere', 'everywhere', 'quorum', 'contra'):
                inner = min if op in ('everywhere', 'quorum') else max
                outer = min if op in ('everywhere', 'contra') else max
                value = outer(inner(at(t, member, other) for member in members)
                              for other, members in enumerate(frame.quorums))
            elif op == 'yesterday':
                value = at(t - 1, p, q) if t else 0
            elif op == 'tomorrow':
                value = (at(t + 1, p, q) if t + 1 < frame.stages else
                         at(t, p, q) if frame.time == 'stutter' else 0)
            elif op in ('once', 'past', 'historically'):
                row = [at(s, p, q) for s in range(t + (op == 'past'))]
                value = min(row, default=2) if op == 'historically' else max(row, default=0)
            elif op == 'sometime':
                value = max((at(s, p, q) for s in future(t)), default=0)
            elif op == 'forever':
                value = min((at(s, p, q) for s in future(t)), default=2)
            elif op == 'infinitely':
                value = min((max((at(u, p, q) for u in future(s)), default=0)
                             for s in future(t)), default=2)
            else:
                value = max((min((at(u, member, other)
                                  for other, members in enumerate(frame.quorums)
                                  for member in members for u in future(s)), default=2)
                             for s in future(t)), default=0)
            result.append(value)
        return tuple(result)
    raise AssertionError(f'oracle does not define {op}')


class FreshSemanticsTests(unittest.TestCase):
    def compare(self, frame, formulas, valuations, values=('red', 'blue')):
        theory = make_theory(frame, values)
        compiler = Compiler(theory, frame, timeout=60)
        outputs = [(formula, tuple(compiler.eval(formula, ctx) for ctx in frame.contexts))
                   for formula in formulas]
        for valuation in valuations:
            units = []
            for atom, (low, high) in compiler.cells.items():
                value = valuation[atom]
                units += [[low if value >= 1 else -low], [high if value == 2 else -high]]
            result = solve(compiler.circuit.nvars, compiler.circuit.clauses + units)
            self.assertEqual(result.status, 'sat')
            evaluator = Evaluator(theory, frame, valuation)
            wrong = []
            for formula, pairs in outputs:
                expected = oracle(formula, frame, valuation, values)
                for ctx, pair, wanted in zip(frame.contexts, pairs, expected):
                    detail = (formula, ctx, valuation)
                    self.assertEqual(evaluator.eval(formula, ctx), wanted, detail)
                    for literal, bit in zip(pair, (wanted >= 1, wanted == 2)):
                        got = result.assignment[abs(literal)] == (literal > 0)
                        self.assertEqual(got, bit, detail)
                        wrong.append(-literal if bit else literal)
            result = solve(compiler.circuit.nvars, compiler.circuit.clauses + units + [wrong])
            self.assertEqual(result.status, 'unsat', valuation)

    def test_affine_and_unique_exhaustive_domains_one_through_five(self):
        frame = Frame(('p',), (frozenset({0}),), 1)
        body = node('pred', node('term', value='v'), value='R')
        formulas = [node(op, body, value='v') for op in ('forall', 'exists', 'affine', 'unique')]
        for size in range(1, 6):
            values = tuple(f'v{i}' for i in range(size))
            valuations = ({('R', 0, 0, (value,)): truth for value, truth in zip(values, assignment)}
                          for assignment in product(range(3), repeat=size))
            self.compare(frame, formulas, valuations, values)

    def test_affinity_circuit_grows_linearly(self):
        frame = Frame(('p',), (frozenset({0}),), 1)
        body = node('pred', node('term', value='v'), value='R')
        # A resource regression: the former pair expansion exceeded 10,000
        # variables and 39,000 clauses at 100 values.
        for size in (10, 100, 300):
            compiler = Compiler(make_theory(frame, tuple(map(str, range(size)))), frame)
            compiler.eval(node('unique', body, value='v'), (0, 0, 0))
            self.assertLess(compiler.circuit.nvars, 10 * size)
            self.assertLess(len(compiler.circuit.clauses), 30 * size)

    def test_seeded_compositions_cover_modal_temporal_and_value_scopes(self):
        rng = random.Random(20261011)
        p, q = node('pred', value='P'), node('pred', value='Q')
        atoms = [p, q] + [node('const', value=value) for value in ('f', 'b', 't')]
        r = node('pred', node('term', value='v'), value='R')
        atoms += [node(op, r, value='v') for op in ('forall', 'exists', 'affine', 'unique')]
        atoms += [node('latest', node('literal', value='red'), r, value='v')]
        atoms += [node(op, node('literal', value='red'), node('literal', value='blue'))
                  for op in ('eq', 'neq')]
        atoms += [node('forall', node('or', r, node('neq', node('term', value='v'),
                                                  node('literal', value='red'))), value='v'),
                  node('exists', node('and', r, node('eq', node('term', value='v'),
                                                   node('literal', value='blue'))), value='v')]
        # Every operator occurs explicitly; deeper compositions are seeded.
        formulas = atoms + [node(op, rng.choice(atoms)) for op in tuple(UNARY) + MODAL + TEMPORAL]
        formulas += [node(op, p, q) for op in BINARY]
        for _ in range(60):
            if rng.randrange(3):
                formulas.append(node(rng.choice(tuple(UNARY) + MODAL + TEMPORAL),
                                     rng.choice(atoms + formulas)))
            else:
                formulas.append(node(rng.choice(tuple(BINARY)),
                                     rng.choice(atoms + formulas), rng.choice(atoms + formulas)))
        for mode in ('finite', 'stutter'):
            frame = Frame(('a', 'b'), (frozenset({0}), frozenset({1}), frozenset({0, 1})), 3, mode)
            valuations = []
            for _ in range(8):
                valuation = {}
                for t, point in product(range(3), range(2)):
                    for name in ('P', 'Q'):
                        valuation[name, t, point, ()] = rng.randrange(3)
                    for value in ('red', 'blue'):
                        valuation['R', t, point, (value,)] = rng.randrange(3)
                valuations.append(valuation)
            self.compare(frame, formulas, valuations)

    def test_recurrences_against_full_frame_prefixed_and_postfixed_vectors(self):
        x, p = node('var', value='X'), node('pred', value='P')
        rng = random.Random(82421)
        bodies = [node(op, x) for op in tuple(UNARY) + MODAL + TEMPORAL]
        bodies += [node(op, x, p) for op in BINARY]
        bodies += [node(op, p, x) for op in ('weak', 'strong', 'order')]
        bodies += [node('not', node('diamond', node('and', p, x)))]
        bodies += [node('nu', node('or', x, node('var', value='Y')), value='Y'),
                   node('mu', node('not', node('and', x, node('var', value='Y'))), value='Y'),
                   node('mu', node('not', node('var', value='X')), value='X')]
        formulas = [node(binder, body, value='X') for binder in ('mu', 'nu') for body in bodies]
        frames = [Frame(('a', 'b'), (frozenset({0}),), 1),
                  Frame(('a',), (frozenset({0}),), 2),
                  Frame(('a',), (frozenset({0}),), 2, 'stutter')]
        for frame in frames:
            valuations = []
            for assignment in product(range(3), repeat=2):
                atoms = [('P', t, point, ()) for t, point in
                         product(range(frame.stages), range(len(frame.points)))]
                valuations.append(dict(zip(atoms, assignment)))
            self.compare(frame, formulas, valuations)
        # A larger, quorum-sensitive recurrence frame, with selected models.
        frame = Frame(('a', 'b'), (frozenset({0}), frozenset({0, 1})), 1)
        formulas = [node(binder, body, value='X') for binder in ('mu', 'nu')
                    for body in (node('not', node('diamond', x)),
                                 node('strong', node('existsQ', x), p),
                                 node('not', node('diamond', node('and', p, x))))]
        valuations = [{('P', 0, point, ()): rng.randrange(3) for point in range(2)}
                      for _ in range(5)]
        self.compare(frame, formulas, valuations)

    def test_union_closure_matches_all_generator_subsets(self):
        points = ('a', 'b', 'c')
        subsets = [frozenset(p for p in range(3) if mask & (1 << p)) for mask in range(8)]
        for chosen in range(256):
            generators = [q for i, q in enumerate(subsets) if chosen & (1 << i)]
            theory = Theory('closure', points, ('v',), 1,
                            tuple(tuple(points[p] for p in q) for q in generators), {}, {}, {})
            # Every union is the union of some subfamily of the generators.
            expected = {frozenset(range(3))}
            for include in product((False, True), repeat=len(generators)):
                union = frozenset(p for q, enabled in zip(generators, include) if enabled for p in q)
                if union:
                    expected.add(union)
            self.assertEqual(set(Frame.from_theory(theory).quorums), expected)

    def test_frame_snapshots_caller_owned_mutable_containers(self):
        points, first, second = ['a', 'b'], {0}, {0, 1}
        quorums = [first, second]
        frame = Frame(points, quorums, 1)
        contexts = frame.contexts
        self.assertTrue(frame.twined(2))
        points.append('c')
        first.clear()
        second.remove(0)
        quorums.append({2})
        self.assertEqual(frame.points, ('a', 'b'))
        self.assertEqual(frame.quorums, (frozenset({0}), frozenset({0, 1})))
        self.assertEqual(frame.contexts, contexts)
        self.assertTrue(frame.twined(2))

    def test_twined_replay_matches_repeated_choices_and_uses_common_witness(self):
        subsets = [frozenset(p for p in range(3) if mask & (1 << p)) for mask in range(1, 8)]
        for chosen in range(1, 128):
            family = tuple(q for i, q in enumerate(subsets) if chosen & (1 << i))
            frame = Frame(('a', 'b', 'c'), family, 1)
            evaluator = Evaluator(make_theory(frame), frame, {})
            for count in range(1, 5):
                expected = all(any(all(point in q for q in selected) for point in range(3))
                               for selected in product(family, repeat=count))
                self.assertEqual(evaluator.eval(node('twined', value=str(count)), (0, 0, 0)),
                                 2 if expected else 0)
        # Each quorum contains point zero. Enumerating all 15-of-30 subsets
        # would unnecessarily inspect 155,117,520 intersections.
        frame = Frame(tuple(map(str, range(31))),
                      tuple(frozenset({0, p}) for p in range(1, 31)), 1)
        evaluator = Evaluator(make_theory(frame), frame, {})
        with patch('muql.evaluate.combinations', side_effect=AssertionError('needless enumeration')):
            self.assertEqual(evaluator.eval(node('twined', value='15'), (0, 0, 0)), 2)

    def test_evaluator_rejects_noninteger_contexts_and_limits(self):
        frame = Frame(('p',), (frozenset({0}),), 1)
        theory = make_theory(frame)
        evaluator = Evaluator(theory, frame, {})
        for context in ((0.0, 0, 0), (False, 0, 0), (0, 0.5, 0), (0, 0, 0.5)):
            with self.subTest(context=context), self.assertRaises(EvaluationError):
                evaluator.eval(node('const', value='t'), context)
        for limit in (True, False, 0, -1, 1.5, float('inf'), float('nan')):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                Evaluator(theory, frame, {}, nonmonotone_limit=limit)


if __name__ == '__main__':
    unittest.main()
