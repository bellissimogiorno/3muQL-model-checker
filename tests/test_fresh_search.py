"""Fresh independent checks of bounded search and saved countermodels.

The modal oracle below works directly on integers and sets. It does not use
MuQL ASTs, the evaluator, compiler, solver, or production frame generation.
"""
from copy import deepcopy
from dataclasses import replace
from itertools import combinations, permutations, product
import random
import unittest
from unittest.mock import patch

from muql import check, loads, replay
from muql.frame_search import iter_quorum_families
from muql.search import search, witness_theory


def scoped(body, points=2, stages=1, family=None, time='finite'):
    names = tuple(f'p{i}' for i in range(points))
    family = family or (tuple(range(points)),)
    quorums = ' '.join('{' + ','.join(names[p] for p in group) + '}' for group in family)
    source = (f'points {" ".join(names)}\nvalues red blue\nstages {stages}\n'
              f'time {time}\nquorums {quorums}\npredicate P/0\n' + body)
    return loads('```muql\n' + source + '\n```')


def labeled_families(points, bound):
    full = frozenset(range(points))
    proper = tuple(frozenset(c) for size in range(1, points)
                   for c in combinations(range(points), size))
    for size in range(min(bound - 1, len(proper)) + 1):
        for chosen in combinations(proper, size):
            family = (*chosen, full)
            if all(a | b in family for a in family for b in family):
                yield family


def canonical(family, points):
    return min(tuple(sorted(sum(1 << labels[p] for p in quorum) for quorum in family))
               for labels in permutations(range(points)))


def expression(rng, depth):
    """A printed expression paired with direct truth functions on frames."""
    if depth == 0:
        token = rng.choice(('P', 'P', 'f', 'b', 't'))
        if token == 'P':
            return token, lambda atoms, family, ctx: atoms[ctx[0], ctx[1]]
        return token, lambda atoms, family, ctx: {'f': 0, 'b': 1, 't': 2}[token]
    op = rng.choice(('not', 'and', 'weak', 'existsQ', 'forallQ', 'diamond', 'box'))
    text, left = expression(rng, depth - 1)
    if op == 'not':
        return f'!({text})', lambda a, f, c: 2 - left(a, f, c)
    if op in ('and', 'weak'):
        other, right = expression(rng, depth - 1)
        combine = min if op == 'and' else lambda x, y: max(2 - x, y)
        return f'({text} {"&" if op == "and" else "->"} {other})', lambda a, f, c: combine(left(a, f, c), right(a, f, c))
    aggregate = max if op in ('existsQ', 'diamond') else min
    def modal(atoms, family, ctx):
        stage, point, quorum = ctx
        contexts = ((stage, point, q) for q in range(len(family))) if op in ('existsQ', 'forallQ') else ((stage, p, quorum) for p in family[quorum])
        return aggregate(left(atoms, family, where) for where in contexts)
    return f'{op}({text})', modal


class FreshFrameSearchTests(unittest.TestCase):
    def test_five_points_three_quorums_against_all_labeled_families(self):
        expected = {canonical(family, 5) for family in labeled_families(5, 3)}
        generated = list(iter_quorum_families(5, 3))
        actual = [canonical(tuple(frozenset(p for p in range(5) if mask & (1 << p))
                                  for mask in family), 5) for family in generated]
        self.assertEqual(set(actual), expected)
        self.assertEqual(len(actual), len(expected))
        self.assertEqual(len(expected), 17)

    def test_quorum_dependent_formulas_against_direct_integer_oracle(self):
        rng = random.Random(20261011)
        cases = []
        for points in (2, 3):
            families = list(labeled_families(points, 4))
            for _ in range(16):
                family = rng.choice(families)
                axiom, ax = expression(rng, 2)
                goal, prop = expression(rng, 3)
                contexts = tuple(product(range(1), range(points), range(len(family))))
                models = [dict(zip(product(range(1), range(points)), values))
                          for values in product(range(3), repeat=points)]
                models = [values for values in models if all(ax(values, family, c) > 0 for c in contexts)]
                expected = ('inconsistent' if not models else 'counterexample'
                            if any(prop(values, family, c) == 0 for values in models for c in contexts)
                            else 'holds')
                theory = scoped(f'axiom A: {axiom}\nproperty Goal: {goal}', points=points, family=family)
                report = check(theory)
                actual = report.status if report.status == 'inconsistent' else report.properties[0].status
                with self.subTest(points=points, family=family, axiom=axiom, goal=goal):
                    self.assertEqual(actual, expected)
                    if actual == 'counterexample':
                        self.assertTrue(replay(theory, report.properties[0].countermodel))
                cases.append(actual)
        self.assertEqual(set(cases), {'inconsistent', 'holds', 'counterexample'})

    def test_search_matches_all_labeled_frames_and_three_valued_atoms(self):
        # Point membership in the current quorum matters in these nested forms.
        formulas = {
            'Exchange': ('existsQ(box(P)) -> forallQ(diamond(P))',
                         lambda a, f, q: max(2 - max(min(a[p] for p in r) for r in f),
                                            min(max(a[p] for p in r) for r in f))),
            'Local': ('diamond(P) -> box(P)',
                      lambda a, f, q: max(2 - max(a[p] for p in f[q]), min(a[p] for p in f[q]))),
            'Distribution': ('existsQ(box(P)) -> existsQ(diamond(P))',
                             lambda a, f, q: max(2 - max(min(a[p] for p in r) for r in f),
                                                max(max(a[p] for p in r) for r in f))),
        }
        expected = dict.fromkeys(formulas, 'holds')
        for points in (1, 2, 3):
            for family in labeled_families(points, 4):
                for atoms in product(range(3), repeat=points):
                    for name, (_, evaluate) in formulas.items():
                        if any(evaluate(atoms, family, q) == 0 for q in range(len(family))):
                            expected[name] = 'counterexample'
        body = '\n'.join(f'property {name}: {formula}' for name, (formula, _) in formulas.items())
        theory = scoped(body)
        report = search(theory, max_points=3, max_values=2, max_stages=1,
                        max_quorums=4, timeout=10, solver='builtin')
        self.assertTrue(report.complete)
        self.assertEqual({r.name: r.status for r in report.properties}, expected)
        for item in report.properties:
            if item.countermodel is not None:
                self.assertTrue(replay(witness_theory(theory, item.countermodel), item.countermodel))


class FreshWitnessTests(unittest.TestCase):
    def setUp(self):
        self.theory = scoped('axiom Allowed: TB(P)\nproperty Goal: T(P)')
        self.data = check(self.theory).properties[0].countermodel.to_dict()

    def test_same_cardinality_tampering_cannot_replace_a_required_cell(self):
        mutations = (
            lambda d: d['valuation'][0].update(predicate='Missing'),
            lambda d: d['valuation'][0].update(time=-1),
            lambda d: d['valuation'][0].update(time=1),
            lambda d: d['valuation'][0].update(point='missing'),
            lambda d: d['valuation'][0].update(args=['red']),
            lambda d: d['valuation'].__setitem__(0, deepcopy(d['valuation'][1])),
        )
        for mutate in mutations:
            data = deepcopy(self.data)
            mutate(data)
            with self.subTest(data=data['valuation']), self.assertRaises(ValueError):
                replay(self.theory, data)

    def test_argument_domain_and_order_are_verified(self):
        theory = scoped('property Goal: f')
        theory = replace(theory, predicates={'P': 2})
        data = check(theory).properties[0].countermodel.to_dict()
        self.assertTrue(replay(theory, data))
        for arguments in (['red', 'absent'], ['red'], ['red', 'red', 'blue']):
            changed = deepcopy(data)
            changed['valuation'][0]['args'] = arguments
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                replay(theory, changed)
        changed = deepcopy(data)
        changed['valuation'][1]['args'] = changed['valuation'][0]['args'].copy()
        with self.assertRaises(ValueError):
            replay(theory, changed)

    def test_replay_does_not_trust_flags_or_recorded_axiom_values(self):
        data = deepcopy(self.data)
        data.update(replayed=False, axiom_values={'Allowed': ['f']})
        self.assertTrue(replay(self.theory, data))
        data['valuation'][0]['value'] = 'f'
        data.update(replayed=True, axiom_values={'Allowed': ['t']})
        with self.assertRaises(ValueError):
            replay(self.theory, data)

    def test_invalid_failure_context_is_rejected_before_evaluation(self):
        mutations = (
            lambda d: d['failure'].update(time=-1),
            lambda d: d['failure'].update(point='missing'),
            lambda d: d['failure'].update(quorum=['missing']),
            lambda d: d['failure'].update(quorum=[]),
            lambda d: d['failure'].update(value='b'),
            lambda d: d.update(property='Missing'),
        )
        for mutate in mutations:
            data = deepcopy(self.data)
            mutate(data)
            with self.subTest(failure=data['failure']):
                with patch('muql.checker._replay_axioms', side_effect=AssertionError('malformed witness evaluated')):
                    with self.assertRaises(ValueError):
                        replay(self.theory, data)

    def test_incomplete_enormous_signature_is_rejected_without_cartesian_allocation(self):
        theory = replace(self.theory, predicates={'P': 0, 'Unused': 10**20})
        data = deepcopy(self.data)
        # This declared signature has at least 2**(10**20) cells. Its submitted
        # handful of rows already proves incompleteness without enumeration.
        with patch('muql.checker.product', side_effect=AssertionError('atomic signature materialized')):
            with self.assertRaisesRegex(ValueError, 'exactly every atomic cell'):
                replay(theory, data)

    def test_empty_signature_has_a_complete_empty_valuation(self):
        theory = replace(scoped('property Goal: f'), predicates={})
        data = check(theory).properties[0].countermodel.to_dict()
        self.assertEqual(data['valuation'], [])
        self.assertTrue(replay(theory, data))

    def test_unrepresentable_time_limits_raise_value_error(self):
        for option in ('timeout', 'total_timeout'):
            with self.subTest(option=option), self.assertRaises(ValueError):
                check(self.theory, **{option: 10**1000})
        with self.assertRaises(ValueError):
            search(self.theory, timeout=10**1000)


if __name__ == '__main__':
    unittest.main()
