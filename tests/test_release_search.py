"""Fresh checks of witness reuse and larger finite frame enumeration.

The enumeration oracle considers all eligible labelled families directly,
then quotients by every point permutation; it shares no augmentation or
incidence canonicalisation with the implementation.
"""

from itertools import combinations, permutations
import time
import unittest
from unittest.mock import patch

from muql import check, loads, replay
from muql import checker
from muql.evaluate import Evaluator
from muql.frame_search import iter_quorum_families


def sample(body):
    return loads('```muql\npoints a b\nvalues red blue\nstages 2\n'
                 'quorums {a} {b}\npredicate P/1\n' + body + '\n```')


class BaselineWitnessReuseTests(unittest.TestCase):
    def test_one_replayed_assignment_can_answer_several_distinct_conjectures(self):
        theory = sample('axiom Negative: forall v. F(P(v))\n'
                        'property Point: P(red)\n'
                        'property Modal: somewhere(P(blue))\n'
                        'property Temporal: past(P(red))\n'
                        'property Holds: !P(blue)')
        with patch('muql.checker.solve', wraps=checker.solve) as solve:
            with patch('muql.checker._replay_axioms', wraps=checker._replay_axioms) as axioms:
                report = check(theory)
        self.assertEqual([p.status for p in report.properties],
                         ['counterexample'] * 3 + ['holds'])
        # Baseline plus the final validity query; the three independently
        # checked counterexamples do not need three further SAT calls.
        self.assertEqual(solve.call_count, 2)
        self.assertEqual(axioms.call_count, 1)
        for prop in report.properties[:3]:
            self.assertTrue(replay(theory, prop.countermodel))
        first, second = (p.countermodel for p in report.properties[:2])
        first.valuation[0]['args'][0] = 'tampered'
        first.valuation[0]['value'] = 't'
        first.axiom_values['Negative'].append('f')
        self.assertNotEqual(first.valuation, report.consistency_model)
        self.assertNotEqual(first.valuation, second.valuation)
        self.assertEqual(second.axiom_values['Negative'], ['t'])
        self.assertTrue(replay(theory, second))

    def test_reused_boolean_witness_still_requires_a_concrete_property_failure(self):
        theory = sample('property Goal: P(red)')
        evaluate = Evaluator.eval

        def reject_failure(evaluator, node, context, env=None):
            if node == theory.properties['Goal']:
                return 2
            return evaluate(evaluator, node, context, env)

        with patch.object(Evaluator, 'eval', reject_failure):
            with self.assertRaisesRegex(RuntimeError, 'no failure'):
                check(theory)

    def test_deadline_after_reused_property_evaluation_preserves_only_earlier_results(self):
        theory = sample('property First: t\nproperty Late: P(red)\nproperty Last: t')
        clock = [time.monotonic()]
        evaluate = Evaluator.eval
        reached = []

        def expire(evaluator, node, context, env=None):
            result = evaluate(evaluator, node, context, env)
            if node == theory.properties['Late']:
                reached.append(True)
                clock[0] += 2
            return result

        with patch('muql.checker.monotonic', side_effect=lambda: clock[0]):
            with patch.object(Evaluator, 'eval', expire):
                report = check(theory, total_timeout=1)
        self.assertTrue(reached)
        self.assertEqual(report.status, 'unknown')
        self.assertEqual([p.status for p in report.properties], ['holds', 'unknown', 'unknown'])
        self.assertTrue(all(p.countermodel is None for p in report.properties))
        self.assertIsNotNone(report.consistency_model)
        self.assertIn('countermodel replay', report.reason)

    def test_baseline_that_does_not_fail_property_requires_another_search(self):
        theory = loads('```muql\npoints a\nvalues red\nstages 1\n'
                       'quorums {a}\npredicate P/0\nproperty Goal: !P\n```')
        with patch('muql.checker.solve', wraps=checker.solve) as solve:
            report = check(theory)
        self.assertEqual(solve.call_count, 2)
        self.assertEqual(report.properties[0].status, 'counterexample')
        self.assertTrue(replay(theory, report.properties[0].countermodel))


class LargerFrameEnumerationTests(unittest.TestCase):
    def test_all_five_point_families_with_at_most_four_nonempty_opens(self):
        npoints, max_quorums = 5, 4
        full = (1 << npoints) - 1
        # Precompute the 120 explicit point-bijection maps independently of
        # the production canonicalisation and reuse them for every family.
        relabelings = [tuple(sum(1 << perm[p] for p in range(npoints) if mask & (1 << p))
                            for mask in range(full + 1))
                      for perm in permutations(range(npoints))]

        def canonical(family):
            return min(tuple(sorted(mapping[mask] for mask in family))
                       for mapping in relabelings)

        expected = set()
        for count in range(max_quorums):
            for proper in combinations(range(1, full), count):
                family = {*proper, full}
                if all(left | right in family for left in family for right in family):
                    expected.add(canonical(family))
        actual = [canonical(family) for family in iter_quorum_families(npoints, max_quorums)]
        self.assertEqual(set(actual), expected)
        self.assertEqual(len(actual), len(set(actual)), 'isomorphic duplicate output')
        self.assertEqual(len(actual), 49)


if __name__ == '__main__':
    unittest.main()
