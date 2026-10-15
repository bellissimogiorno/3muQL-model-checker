"""Audit regressions and exhaustive end-to-end checks against a tiny oracle.

The oracle generates its own expressions and truth functions; it uses neither
the package parser's AST nor the direct evaluator nor the SAT compiler.
"""
import copy
from dataclasses import replace
from itertools import product
import random
import unittest
from unittest.mock import patch

from muql import check, loads, parse_formula, replay
from muql.frame import Frame, FrameLimit


def tiny(body):
    return loads('```muql\npoints a\nvalues x\nstages 1\nquorums {a}\n'
                 'predicate P/1\n' + body + '\n```')


class CheckerAuditTests(unittest.TestCase):
    def test_public_theory_cannot_bypass_signature_validation(self):
        theory = tiny('property Goal: t')
        theory.properties['Goal'] = parse_formula('Missing() ⇀ Missing()')
        with self.assertRaises(ValueError):
            check(theory)
        for changes in ({'predicates': {'P': -1}}, {'time': 'typo'},
                        {'stages': True}, {'values': ('x', 'x')}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                check(replace(tiny('property Goal: t'), **changes))

    def test_resource_budgets_are_typed_not_truthy(self):
        theory = tiny('property Goal: t')
        for key in ('timeout', 'max_nodes', 'max_decisions', 'max_mu_contexts'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                check(theory, **{key: True})
        for key in ('max_nodes', 'max_decisions', 'max_mu_contexts'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                check(theory, **{key: 2.5})

    def test_frame_expansion_limit_is_unknown_not_invalid(self):
        theory = tiny('property Goal: t')
        with patch.object(Frame, 'from_theory', side_effect=FrameLimit('test closure limit')):
            report = check(theory)
        self.assertEqual(report.status, 'unknown')
        self.assertEqual([r.status for r in report.properties], ['unknown'])
        self.assertIn('quorum_generators', report.scope)
        self.assertNotIn('quorums', report.scope)

    def test_huge_unused_arity_is_bounded_before_counting_or_decoding(self):
        theory = replace(tiny('property Goal: t'), predicates={'P': 10**20})
        report = check(theory)
        self.assertEqual(report.status, 'unknown')
        self.assertIn('arity', report.reason)

    def test_zero_timeout_stops_before_frame_expansion(self):
        report = check(tiny('property Goal: t'), timeout=0)
        self.assertEqual(report.status, 'unknown')
        self.assertNotIn('quorums', report.scope)

    def test_serialized_witness_rejects_python_numeric_coercions(self):
        theory = tiny('property Goal: P(x)')
        data = check(theory).properties[0].countermodel.to_dict()
        self.assertTrue(replay(theory, data))
        mutations = [
            lambda d: d['valuation'][0].update(time=False),
            lambda d: d['valuation'][0].update(time=0.0),
            lambda d: d['valuation'][0].update(args='x'),
            lambda d: d['failure'].update(time=False),
            lambda d: d['failure'].update(time=0.0),
            lambda d: d['failure'].update(quorum='a'),
            lambda d: d['failure'].update(quorum=['a', 'a']),
            lambda d: d['scope'].update(stages=True),
            lambda d: d['scope'].update(stages=1.0),
        ]
        for mutate in mutations:
            bad = copy.deepcopy(data)
            mutate(bad)
            with self.subTest(data=bad), self.assertRaises(ValueError):
                replay(theory, bad)

    def test_replay_revalidates_mutated_theory(self):
        theory = tiny('property Goal: P(x)')
        data = check(theory).properties[0].countermodel.to_dict()
        with self.assertRaises(ValueError):
            replay(replace(theory, stages=True), data)

    def test_end_to_end_against_all_valuations_in_small_frames(self):
        rng = random.Random(20261010)
        checked = {'inconsistent': 0, 'holds': 0, 'counterexample': 0}
        for temporal in (False, True):
            stages, points = (2, 1) if temporal else (1, 2)
            for mode in ('finite', 'stutter'):
                contexts = tuple(product(range(stages), range(points)))
                atoms = tuple(product(('P', 'Q'), range(stages), range(points)))
                def expression(depth):
                    if depth == 0 or rng.random() < .2:
                        token = rng.choice(('P', 'Q', 'f', 'b', 't'))
                        if token in ('P', 'Q'):
                            return token + '()', lambda v, t, p, name=token: v[name, t, p]
                        value = {'f': 0, 'b': 1, 't': 2}[token]
                        return token, lambda v, t, p, value=value: value
                    unary = ['!', 'T', 'B', 'someQuorumSomePoint', 'everyQuorumEveryPoint']
                    if temporal:
                        unary += ['once', 'past', 'sometime', 'forever', 'tomorrow', 'yesterday']
                    op = rng.choice(unary + ['&', '|', '->', '⇀', '<=>'])
                    left, evaluate_left = expression(depth - 1)
                    if op in ('&', '|', '->', '⇀', '<=>'):
                        right, evaluate_right = expression(depth - 1)
                        fn = {'&': min, '|': max,
                              '->': lambda a, b: max(2-a, b),
                              '⇀': lambda a, b: max(2-a, 2*int(b == 2)),
                              '<=>': lambda a, b: 2*int(a == b)}[op]
                        return f'({left} {op} {right})', lambda v, t, p: fn(evaluate_left(v, t, p), evaluate_right(v, t, p))
                    def evaluate(v, t, p):
                        if op == '!': return 2-evaluate_left(v, t, p)
                        if op == 'T': return 2*int(evaluate_left(v, t, p) == 2)
                        if op == 'B': return 2*int(evaluate_left(v, t, p) == 1)
                        if op in ('someQuorumSomePoint', 'everyQuorumEveryPoint'):
                            values = [evaluate_left(v, t, member) for member in range(points)]
                            return max(values) if op == 'someQuorumSomePoint' else min(values)
                        if op == 'yesterday': return 0 if t == 0 else evaluate_left(v, t-1, p)
                        if op == 'tomorrow':
                            if t+1 < stages: return evaluate_left(v, t+1, p)
                            return evaluate_left(v, t, p) if mode == 'stutter' else 0
                        times = (range(t) if op == 'once' else range(t+1) if op == 'past'
                                 else [t] if mode == 'stutter' and t == stages-1 else range(t+1, stages))
                        values = [evaluate_left(v, at, p) for at in times]
                        return min(values, default=2) if op == 'forever' else max(values, default=0)
                    return f'!({left})' if op == '!' else f'{op}({left})', evaluate
                for case in range(25):
                    axiom, ax = expression(3)
                    prop, pr = expression(3)
                    valuations = [dict(zip(atoms, values)) for values in product(range(3), repeat=len(atoms))]
                    models = [v for v in valuations if all(ax(v, t, p) != 0 for t, p in contexts)]
                    expected = ('inconsistent' if not models else
                                'counterexample' if any(pr(v, t, p) == 0 for v in models for t, p in contexts)
                                else 'holds')
                    checked[expected] += 1
                    names = ' '.join(f'p{i}' for i in range(points))
                    text = (f'```muql\npoints {names}\nvalues x\nstages {stages}\ntime {mode}\n'
                            f'quorums {{{names.replace(" ", ",")}}}\npredicate P/0\npredicate Q/0\n'
                            f'axiom A: {axiom}\nproperty Goal: {prop}\n```')
                    theory = loads(text)
                    report = check(theory)
                    actual = report.status if report.status == 'inconsistent' else report.properties[0].status
                    with self.subTest(mode=mode, temporal=temporal, case=case, axiom=axiom, prop=prop):
                        self.assertEqual(actual, expected)
                        if expected == 'counterexample': self.assertTrue(replay(theory, report.properties[0].countermodel))
        self.assertTrue(all(checked.values()), checked)


if __name__ == '__main__':
    unittest.main()
