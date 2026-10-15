"""Shared deadlines must never turn late computation into a reported proof."""

import time
import unittest
from unittest.mock import patch

from muql import check, loads
from muql import checker


def theory(properties='property A: t\nproperty B: P\nproperty C: t'):
    return loads('```muql\npoints a\nvalues x\nstages 1\nquorums {a}\n'
                 'predicate P/0\n' + properties + '\n```')


class SharedDeadlineTests(unittest.TestCase):
    def test_total_timeout_validation_and_zero_budget(self):
        for value in (-1, True, float('inf'), float('nan'), '1'):
            with self.assertRaises(ValueError):
                check(theory(), total_timeout=value)
        result = check(theory(), total_timeout=0)
        self.assertEqual(result.status, 'unknown')
        self.assertTrue(all(p.status == 'unknown' for p in result.properties))
        self.assertEqual(result.stats['backend'], 'builtin')

    def test_each_query_receives_only_remaining_total_budget(self):
        clock = [time.monotonic()]
        limits = []
        original = checker.solve

        def solve(*args, **kwargs):
            limits.append(kwargs['timeout'])
            result = original(*args, **kwargs)
            clock[0] += 0.2
            return result

        with patch('muql.checker.monotonic', side_effect=lambda: clock[0]):
            with patch('muql.checker.solve', side_effect=solve):
                # The baseline sets P false, so !P needs a separate query;
                # a property already false in that model may now reuse it.
                report = check(theory('property A: t\nproperty B: !P'),
                               timeout=30, total_timeout=1)
        self.assertEqual(report.status, 'checked')
        self.assertEqual(len(limits), 3)
        self.assertTrue(all(0 < limit <= 1 for limit in limits))
        self.assertGreater(limits[0], limits[1])
        self.assertGreater(limits[1], limits[2])

    def test_late_consistency_result_is_unknown_even_if_unsat(self):
        for body in ('property A: t', 'axiom Impossible: f\nproperty A: t'):
            clock = [time.monotonic()]
            original = checker.solve

            def solve(*args, **kwargs):
                result = original(*args, **kwargs)
                clock[0] += 2
                return result

            with patch('muql.checker.monotonic', side_effect=lambda: clock[0]):
                with patch('muql.checker.solve', side_effect=solve):
                    report = check(theory(body), total_timeout=1)
            self.assertEqual(report.status, 'unknown')
            self.assertEqual([p.status for p in report.properties], ['unknown'])
            self.assertIsNone(report.consistency_model)

    def test_late_consistency_replay_does_not_become_pass(self):
        clock = [time.monotonic()]
        original = checker._replay_axioms

        def replay(*args, **kwargs):
            result = original(*args, **kwargs)
            clock[0] += 2
            return result

        with patch('muql.checker.monotonic', side_effect=lambda: clock[0]):
            with patch('muql.checker._replay_axioms', side_effect=replay):
                report = check(theory(), total_timeout=1)
        self.assertEqual(report.status, 'unknown')
        self.assertIsNone(report.consistency_model)
        self.assertTrue(all(p.status == 'unknown' for p in report.properties))
        self.assertIn('consistency replay', report.reason)

    def test_late_countermodel_replay_preserves_earlier_results_only(self):
        clock = [time.monotonic()]
        original = checker._replay_axioms
        calls = []

        def replay(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(True)
            if len(calls) == 2:
                clock[0] += 2
            return result

        with patch('muql.checker.monotonic', side_effect=lambda: clock[0]):
            with patch('muql.checker._replay_axioms', side_effect=replay):
                report = check(theory('property A: t\nproperty B: !P\nproperty C: t'),
                               total_timeout=1)
        self.assertEqual(report.status, 'unknown')
        self.assertEqual([p.status for p in report.properties], ['holds', 'unknown', 'unknown'])
        self.assertTrue(all(p.countermodel is None for p in report.properties))
        self.assertIsNotNone(report.consistency_model)
        self.assertIn('countermodel replay', report.reason)

    def test_late_property_unsat_is_unknown_not_holds(self):
        clock = [time.monotonic()]
        original = checker.solve
        calls = []

        def solve(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(True)
            if len(calls) == 2:
                clock[0] += 2
            return result

        with patch('muql.checker.monotonic', side_effect=lambda: clock[0]):
            with patch('muql.checker.solve', side_effect=solve):
                report = check(theory('property A: t'), total_timeout=1)
        self.assertEqual(report.status, 'unknown')
        self.assertEqual(report.properties[0].status, 'unknown')
        self.assertIn('property search', report.reason)

    def test_no_total_timeout_preserves_separate_phase_limits(self):
        clock = [time.monotonic()]
        original = checker._replay_axioms

        def replay(*args, **kwargs):
            result = original(*args, **kwargs)
            clock[0] += 1000
            return result

        with patch('muql.checker.monotonic', side_effect=lambda: clock[0]):
            with patch('muql.checker._replay_axioms', side_effect=replay):
                report = check(theory('property A: t'), timeout=30)
        self.assertEqual(report.status, 'checked')
        self.assertEqual(report.properties[0].status, 'holds')


if __name__ == '__main__':
    unittest.main()
