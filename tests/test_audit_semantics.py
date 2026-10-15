"""Fresh audit oracles: explicit truth tables and whole-frame enumeration.

These tests deliberately do not import the production recurrence analysis or
its dependency closure. The full-frame oracle enumerates *every* assignment,
including for monotone bodies and nested recurrences.
"""
from itertools import product
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from muql.compile import Compiler, ResourceLimit, positive
from muql.evaluate import Evaluator, _polarities
from muql.frame import Frame, FrameLimit
from muql.sat import solve
from muql.syntax import Node, parse_formula


# Figure 1, independently transcribed from the rendered source PDF, with
# row/column order f,b,t. Equiv is Fig. 2; order/xor are documented extensions.
UNARY = {'not': (2, 1, 0), 'T': (0, 0, 2), 'F': (2, 0, 0),
         'B': (0, 2, 0), 'TB': (0, 2, 2), 'TF': (2, 0, 2), 'FB': (2, 2, 0)}
BINARY = {'and': ((0, 0, 0), (0, 1, 1), (0, 1, 2)),
          'or': ((0, 1, 2), (1, 1, 2), (2, 2, 2)),
          'weak': ((2, 2, 2), (1, 1, 2), (0, 1, 2)),
          'strong': ((2, 2, 2), (1, 1, 2), (0, 0, 2)),
          'equiv': ((2, 0, 0), (0, 2, 0), (0, 0, 2)),
          'order': ((2, 2, 2), (0, 2, 2), (0, 0, 2)),
          'xor': ((0, 1, 2), (1, 1, 1), (2, 1, 0))}


def reference(node, ctx, frame, valuation, values=('red', 'blue'), env=None, bindings=None):
    """Small, deliberately unoptimized interpretation of Fig. 5/6."""
    env, bindings = env or {}, bindings or {}
    op, args = node.op, node.args
    time, point, quorum = ctx
    def ev(child, at=ctx, variables=env, fixed=bindings):
        return reference(child, at, frame, valuation, values, variables, fixed)
    def term(child):
        return child.value if child.op == 'literal' else env.get(child.value, child.value)
    if op == 'const': return {'f': 0, 'b': 1, 't': 2}[node.value]
    if op == 'var': return bindings[node.value][ctx]
    if op == 'pred': return valuation[(node.value, time, point, tuple(map(term, args)))]
    if op in UNARY: return UNARY[op][ev(args[0])]
    if op in BINARY: return BINARY[op][ev(args[0])][ev(args[1])]
    if op in {'eq', 'neq'}: return 2 * ((term(args[0]) == term(args[1])) == (op == 'eq'))
    if op in {'forall', 'exists'}:
        answers = [ev(args[0], variables={**env, node.value: value}) for value in values]
        return min(answers) if op == 'forall' else max(answers)
    if op in {'diamond', 'box'}:
        answers = [ev(args[0], (time, p, quorum)) for p in frame.quorums[quorum]]
        return max(answers) if op == 'diamond' else min(answers)
    if op in {'existsQ', 'forallQ'}:
        answers = [ev(args[0], (time, point, q)) for q in range(len(frame.quorums))]
        return max(answers) if op == 'existsQ' else min(answers)
    if op in {'yesterday', 'tomorrow'}:
        if op == 'yesterday':
            return ev(args[0], (time - 1, point, quorum)) if time else 0
        if time + 1 < frame.stages: return ev(args[0], (time + 1, point, quorum))
        return ev(args[0]) if frame.time == 'stutter' else 0
    if op in {'mu', 'nu'}:
        answer = 2 if op == 'mu' else 0
        for candidate in product(range(3), repeat=len(frame.contexts)):
            mapping = dict(zip(frame.contexts, candidate))
            image = [ev(args[0], at, fixed={**bindings, node.value: mapping})
                     for at in frame.contexts]
            if op == 'mu' and all(a <= b for a, b in zip(image, candidate)):
                answer = min(answer, mapping[ctx])
            if op == 'nu' and all(a >= b for a, b in zip(image, candidate)):
                answer = max(answer, mapping[ctx])
        return answer
    raise AssertionError(f'unimplemented independent oracle operation {op}')


def theory(frame):
    return SimpleNamespace(points=frame.points, stages=frame.stages, time=frame.time,
                           quorums=tuple(tuple(frame.points[p] for p in q) for q in frame.quorums),
                           values=('red', 'blue'), predicates={'P': 0, 'A': 1})


class AuditSemanticsTests(unittest.TestCase):
    def compare(self, frame, formulas, valuations, *, oracle=reference):
        nodes = [parse_formula(n) if isinstance(n, str) else n for n in formulas]
        model = theory(frame)
        compiler = Compiler(model, frame, timeout=float('inf'))
        outputs = [(node, ctx, compiler.eval(node, ctx)) for node in nodes for ctx in frame.contexts]
        for valuation in valuations:
            fixed = []
            for atom, (low, high) in compiler.cells.items():
                value = valuation[atom]
                fixed.extend([[low if value else -low], [high if value == 2 else -high]])
            result = solve(compiler.circuit.nvars, compiler.circuit.clauses + fixed)
            self.assertEqual(result.status, 'sat')
            concrete = Evaluator(model, frame, valuation)
            differs = []
            for node, ctx, pair in outputs:
                expected = oracle(node, ctx, frame, valuation)
                actual = tuple(result.assignment[abs(bit)] == (bit > 0) for bit in pair)
                desired = (expected > 0, expected == 2)
                self.assertEqual(actual, desired, (str(node), ctx, valuation))
                self.assertEqual(concrete.eval(node, ctx), expected, (str(node), ctx, valuation))
                differs.extend(-bit if truth else bit for bit, truth in zip(pair, desired))
            result = solve(compiler.circuit.nvars, compiler.circuit.clauses + fixed + [differs])
            self.assertEqual(result.status, 'unsat', result.reason)

    def test_every_unary_three_valued_function_under_mu_and_nu(self):
        # Every function on THREE has a case decomposition using F/B/T tests.
        # This exercises all 27 functions, including all nonmonotone maps.
        x = Node('var', value='X')
        cases = []
        expected = {}
        for table in product(range(3), repeat=3):
            parts = [Node('and', (Node(test, (x,)), Node('const', value='fbt'[value])))
                     for test, value in zip(('F', 'B', 'T'), table)]
            body = Node('or', (parts[0], Node('or', tuple(parts[1:]))))
            for kind in ('mu', 'nu'):
                node = Node(kind, (body,), 'X')
                cases.append(node)
                expected[node] = (min(v for v in range(3) if table[v] <= v) if kind == 'mu'
                                  else max(v for v in range(3) if v <= table[v]))
        frame = Frame(('a',), (frozenset({0}),), 1)
        self.compare(frame, cases, [{}], oracle=lambda node, *unused: expected[node])

    def test_generated_scalar_recurrences_and_monotonicity_certificates(self):
        rng = random.Random(20261010)
        frame = Frame(('a',), (frozenset({0}),), 1)
        x, p = Node('var', value='X'), Node('pred', value='P')
        leaves = [x, p] + [Node('const', value=v) for v in 'fbt']
        def generate(depth):
            if depth == 0 or rng.random() < .2: return rng.choice(leaves)
            if rng.random() < .45: return Node(rng.choice(tuple(UNARY)), (generate(depth-1),))
            return Node(rng.choice(tuple(BINARY)), (generate(depth-1), generate(depth-1)))
        bodies = [generate(4) for _ in range(250)]
        valuations = [{('P', 0, 0, ()): value} for value in range(3)]
        for body in bodies:
            if positive(body, 'X') or _polarities(body, 'X') <= {1}:
                for valuation in valuations:
                    image = [reference(body, (0,0,0), frame, valuation,
                                       bindings={'X': {(0,0,0): value}}) for value in range(3)]
                    self.assertEqual(image, sorted(image), str(body))
        self.compare(frame, [Node(kind, (body,), 'X') for body in bodies for kind in ('mu', 'nu')], valuations)

    def test_nested_modal_fixedpoints_against_entire_frame_enumeration(self):
        frame = Frame(('a', 'b'), (frozenset({0, 1}),), 1)
        formulas = [
            'mu X. !(mu Y. (X | diamond(Y)))',
            'nu X. (mu Y. (X | !diamond(Y)))',
            'mu X. (nu Y. (P & X & !box(Y)))',
            'nu X. !(nu Y. !(X | box(Y)))',
            'mu X. (P | (mu Y. (!X & diamond(Y))))',
            'nu X. (B(X) | (mu Y. (P | box(Y))))',
            'mu X. (mu X. !diamond(P & X))',
        ]
        vals = [{('P', 0, point, ()): value for point, value in enumerate(assignment)}
                for assignment in product(range(3), repeat=2)]
        self.compare(frame, formulas, vals)

    def test_nested_temporal_fixedpoints_against_entire_frame_enumeration(self):
        formulas = [
            'mu X. !(mu Y. (P | X | tomorrow(Y)))',
            'nu X. (mu Y. (tomorrow(X) | !yesterday(Y)))',
            'mu X. (nu Y. !(yesterday(X) & tomorrow(Y)))',
            'mu X. (X | (nu X. !tomorrow(X)))',
        ]
        vals = [{('P', stage, 0, ()): value for stage, value in enumerate(assignment)}
                for assignment in product(range(3), repeat=2)]
        for mode in ('finite', 'stutter'):
            frame = Frame(('a',), (frozenset({0}),), 2, mode)
            self.compare(frame, formulas, vals)

    def test_value_binding_inside_and_outside_nested_recurrence(self):
        frame = Frame(('a',), (frozenset({0}),), 1)
        formulas = [
            'forall v. mu X. (A(v) | (exists v. (A(v) & X)))',
            'exists v. nu X. !(A(v) & (forall v. (A(v) | X)))',
            'mu X. forall v. (mu Y. (A(v) | X | !Y))',
            'forall v. mu X. (exists v. (A(v) | (nu Y. (X & !Y))))',
        ]
        vals = [{('A', 0, 0, (value,)): answer for value, answer in zip(('red', 'blue'), assignment)}
                for assignment in product(range(3), repeat=2)]
        self.compare(frame, formulas, vals)

    def test_evaluator_owns_an_immutable_snapshot(self):
        frame = Frame(('a',), (frozenset({0}),), 1)
        atom = ('P', 0, 0, ())
        original = {atom: 0}
        evaluator = Evaluator(theory(frame), frame, original)
        formula = parse_formula('P')
        self.assertEqual(evaluator.eval(formula, (0,0,0)), 0)
        original[atom] = 2
        self.assertEqual(evaluator.eval(formula, (0,0,0)), 0)
        with self.assertRaises(TypeError): evaluator.valuation[atom] = 2
        with self.assertRaises(AttributeError): evaluator.valuation = original
        self.assertEqual(Evaluator(theory(frame), frame, original).eval(formula, (0,0,0)), 2)

    def test_frame_rejects_invalid_relational_frame_configurations(self):
        cases = [((), (frozenset({0}),), 1, 'finite'),
                 (('a', 'a'), (frozenset({0}),), 1, 'finite'),
                 (('a',), (), 1, 'finite'),
                 (('a',), (frozenset(),), 1, 'finite'),
                 (('a',), (frozenset({1}),), 1, 'finite'),
                 (('a',), (frozenset({0}),), True, 'finite'),
                 (('a',), (frozenset({0}),), 1, 'typo')]
        for config in cases:
            with self.subTest(config=config), self.assertRaises(ValueError): Frame(*config)

    def test_quorum_budget_is_a_resource_limit_and_checks_deadline(self):
        frame = Frame(('a','b','c'), tuple(frozenset({i}) for i in range(3)), 1)
        with self.assertRaises(FrameLimit): Frame.from_theory(theory(frame), max_quorums=4)
        with patch('muql.frame.monotonic', return_value=10):
            with self.assertRaisesRegex(FrameLimit, 'timeout'):
                Frame.from_theory(theory(frame), deadline=9)
        self.assertEqual(len(Frame.from_theory(theory(frame)).quorums), 7)

    def test_twined_matches_all_repeated_choices_on_all_three_point_families(self):
        opens = [frozenset(i for i in range(3) if mask & (1 << i)) for mask in range(1,8)]
        for mask in range(1, 1 << len(opens)):
            family = tuple(q for i,q in enumerate(opens) if mask & (1 << i))
            frame = Frame(('a','b','c'), family, 1)
            for n in range(1,5):
                expected = all(set.intersection(*map(set, qs)) for qs in product(family, repeat=n))
                self.assertEqual(frame.twined(n), expected, (family, n))

    def test_twined_cannot_bypass_compiler_timeout(self):
        frame = Frame(('a','b','c'), (frozenset({0,1}), frozenset({0,2}), frozenset({1,2})), 1)
        compiler = Compiler(theory(frame), frame, timeout=float('inf'))
        compiler.deadline = 1
        compiler.steps = 1  # Exercise the explicit twined checkpoint, not the first eval check.
        with patch('muql.compile.monotonic', return_value=2):
            with self.assertRaisesRegex(ResourceLimit, 'timeout'):
                compiler.eval(parse_formula('twined(2)'), (0,0,0))

    def test_twined_replay_reuses_frame_constant_across_contexts(self):
        frame = Frame(('a','b'), (frozenset({0}), frozenset({0,1})), 2)
        evaluator = Evaluator(theory(frame), frame, {})
        node = parse_formula('twined(2)')
        self.assertEqual(evaluator.eval(node, frame.contexts[0]), 2)
        with patch('muql.evaluate.combinations', side_effect=AssertionError('repeated frame test')):
            for ctx in frame.contexts[1:]:
                self.assertEqual(evaluator.eval(node, ctx), 2)

    def test_zero_compiler_timeout_is_immediate_and_invalid_limits_rejected(self):
        frame = Frame(('a',), (frozenset({0}),), 1)
        compiler = Compiler(theory(frame), frame, timeout=0)
        with self.assertRaisesRegex(ResourceLimit, 'timeout'):
            compiler.eval(parse_formula('t'), (0,0,0))
        for options in ({'timeout': -1}, {'timeout': float('nan')},
                        {'max_nodes': 0}, {'max_mu_contexts': 1.5}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                Compiler(theory(frame), frame, **options)


if __name__ == '__main__':
    unittest.main()
