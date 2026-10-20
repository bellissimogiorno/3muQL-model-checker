"""Progress observes actual work without changing witnesses or conclusions."""

from copy import deepcopy
import time
import unittest
from unittest.mock import patch

from muql import check, loads
from muql import checker
from muql.search import search
from muql.frame_search import iter_quorum_families


def theory(body='property Fails: P\nproperty Holds: t'):
    return loads('```muql\npoints a b\nvalues red\nstages 1\n'
                 'quorums {a} {b}\npredicate P/0\n' + body + '\n```')


def semantic(report):
    result = deepcopy(report.to_dict())
    result['stats'].pop('seconds', None)
    return result


class ProgressTests(unittest.TestCase):
    def test_fixed_frame_events_precede_solver_and_replay_and_count_verified_witnesses(self):
        events = []
        original_solve, original_replay = checker.solve, checker._replay_axioms

        def solve(*args, **kwargs):
            self.assertIn(events[-1]['phase'], ('consistency', 'property'))
            self.assertIn('variables', events[-1])
            self.assertIn('clauses', events[-1])
            return original_solve(*args, **kwargs)

        def replay(*args, **kwargs):
            self.assertEqual(events[-1]['phase'], 'replaying')
            self.assertEqual(events[-1]['counterexamples_found'], 0)
            return original_replay(*args, **kwargs)

        with patch('muql.checker.solve', side_effect=solve), patch('muql.checker._replay_axioms', side_effect=replay):
            report = check(theory(), progress=events.append)
        self.assertEqual([item.status for item in report.properties], ['counterexample', 'holds'])
        self.assertEqual(events[0]['phase'], 'validating')
        self.assertEqual(events[-1]['phase'], 'frame_done')
        self.assertEqual(events[-1]['counterexamples_found'], 1)
        self.assertEqual(events[-1]['quorums'], 3, 'Report computed closure, not two generators')
        self.assertEqual(events[-1]['decisions'], report.stats['decisions'])
        self.assertTrue(all('frames_completed' not in event for event in events))
        self.assertTrue(all('status' not in event for event in events))

    def test_observer_mutation_and_errors_do_not_modify_input_or_result(self):
        source = theory()
        before = deepcopy(source)
        expected = semantic(check(source))

        def mutate(snapshot):
            snapshot.clear()
            snapshot.update(points=['tampered'], counterexamples_found=999)

        def failed(snapshot):
            mutate(snapshot)
            raise RuntimeError('auxiliary observer failure')

        for observer in (mutate, failed, 123):
            with self.subTest(observer=observer):
                self.assertEqual(semantic(check(source, progress=observer)), expected)
                self.assertEqual(source, before)

    def test_search_counters_are_cumulative_and_match_final_report(self):
        events = []
        report = search(theory(), max_points=1, max_values=1, max_stages=2,
                        solver='builtin', progress=events.append)
        done = [event for event in events if event['phase'] == 'frame_done']
        self.assertEqual([event['frame'] for event in done], [1, 2])
        self.assertEqual([event['frames_completed'] for event in done], [1, 2])
        self.assertEqual([event['frames_consistent'] for event in done], [1, 2])
        self.assertEqual([event['counterexamples_found'] for event in done], [1, 1])
        self.assertEqual(events[-1]['frames_completed'], report.stats['frames'])
        self.assertEqual(events[-1]['decisions'], report.stats['decisions'])
        for field in ('frames_completed', 'frames_consistent', 'frames_inconsistent',
                      'frames_unknown', 'counterexamples_found', 'decisions'):
            values = [event[field] for event in events]
            self.assertEqual(values, sorted(values), field)
        self.assertTrue(all('status' not in event and 'holds' not in event for event in events))
        self.assertTrue(all(isinstance(value, (str, int)) for event in events for value in event.values()))
        self.assertEqual(len({id(event) for event in events}), len(events))

    def test_candidate_dimensions_are_announced_before_family_enumeration(self):
        events = []

        def enumerate_families(points, max_quorums, **kwargs):
            snapshot = events[-1]
            self.assertEqual(snapshot['phase'], 'enumerating')
            self.assertEqual(snapshot['points'], points)
            self.assertIn('values', snapshot)
            self.assertIn('stages', snapshot)
            for unknown in ('frame', 'quorums', 'variables', 'clauses', 'property'):
                self.assertNotIn(unknown, snapshot)
            return iter_quorum_families(points, max_quorums, **kwargs)

        with patch('muql.search.iter_quorum_families', side_effect=enumerate_families):
            search(theory('property Holds: t'), max_points=2, max_values=1,
                   max_stages=1, solver='builtin', progress=events.append)
        self.assertTrue(any(event.get('points') == 2 for event in events))

    def test_inconsistent_and_limited_frames_are_counted_without_success_claims(self):
        for body, options, counter in (
            ('axiom Impossible: f\nproperty Claim: t', {}, 'frames_inconsistent'),
            ('property Claim: P', {'max_nodes': 1}, 'frames_unknown'),
        ):
            events = []
            report = search(theory(body), max_points=1, max_values=1, max_stages=2,
                            solver='builtin', progress=events.append, **options)
            self.assertEqual(events[-1][counter], report.stats['frames'])
            self.assertEqual(events[-1]['counterexamples_found'], 0)
            self.assertEqual(events[-1]['frames_consistent'], 0)

    def test_zero_budget_reports_no_completed_frame_or_counterexample(self):
        events = []
        report = search(theory(), timeout=0, progress=events.append)
        self.assertEqual(report.status, 'unknown')
        self.assertTrue(events)
        self.assertTrue(all(event['frames_completed'] == 0 for event in events))
        self.assertTrue(all(event['counterexamples_found'] == 0 for event in events))

    def test_late_replay_never_emits_a_verified_counterexample(self):
        clock = [time.monotonic()]
        events = []
        original = checker._replay_axioms

        def late(*args, **kwargs):
            result = original(*args, **kwargs)
            clock[0] += 2
            return result

        with patch('muql.checker.monotonic', side_effect=lambda: clock[0]), patch('muql.checker._replay_axioms', side_effect=late):
            report = check(theory(), total_timeout=1, progress=events.append)
        self.assertEqual(report.status, 'unknown')
        self.assertTrue(all(event['counterexamples_found'] == 0 for event in events))
        self.assertEqual(events[-1]['phase'], 'frame_done')

    def test_search_observer_failure_preserves_results_and_earlier_snapshots(self):
        source = theory()
        options = dict(max_points=1, max_values=1, max_stages=2, solver='builtin')
        expected = semantic(search(source, **options))
        events = []

        def failed(snapshot):
            events.append(deepcopy(snapshot))
            snapshot.clear()
            raise RuntimeError('observer failure')

        actual = semantic(search(source, progress=failed, **options))
        self.assertEqual(actual, expected)
        self.assertEqual(events[0]['frames_completed'], 0)
        self.assertEqual(events[-1]['frames_completed'], 2)

    def test_progress_does_not_add_checker_clock_reads(self):
        counts = []
        for observer in (None, lambda snapshot: None):
            with patch('muql.checker.monotonic', wraps=time.monotonic) as clock:
                check(theory(), progress=observer)
            counts.append(clock.call_count)
        self.assertEqual(counts[0], counts[1])


if __name__ == '__main__':
    unittest.main()
