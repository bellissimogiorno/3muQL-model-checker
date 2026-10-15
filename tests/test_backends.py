"""Backend protocol tests plus real PySAT checks when that extra is installed.

Fake MiniSat tests validate our adapter's handling of the documented protocol;
they are not evidence that native MiniSat has run.  Native tests are explicitly
skipped when the optional dependency is unavailable.
"""

import copy
import itertools
import random
import unittest
from unittest.mock import patch

from muql import check, loads, replay
from muql.backends import BackendUnavailable, resolve_backend, solve


def satisfies(clauses, assignment):
    return all(any(assignment[abs(v)] == (v > 0) for v in clause)
               for clause in clauses)


class FakeMinisat:
    """Small documented-protocol double with an independent truth-table oracle."""
    instances = []
    script = ()
    on_solve = None
    minimum_budget = 0

    def __init__(self):
        self.instances.append(self)
        self.clauses = []
        self.budgets = []
        self.decisions = 0
        self.scripted = iter(self.script)
        self.closed = False
        self.model = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def add_clause(self, clause):
        self.clauses.append(clause[:])

    def prop_budget(self, budget):
        self.budgets.append(budget)

    def solve_limited(self):
        if type(self).on_solve:
            type(self).on_solve()
        if self.budgets[-1] < type(self).minimum_budget:
            return None
        try:
            status, self.decisions, self.model = next(self.scripted)
            return status
        except StopIteration:
            pass
        variables = sorted({abs(v) for clause in self.clauses for v in clause})
        for bits in itertools.product((False, True), repeat=len(variables)):
            assignment = dict(zip(variables, bits))
            if satisfies(self.clauses, assignment):
                self.model = [v if assignment[v] else -v for v in variables]
                return True
        return False

    def accum_stats(self):
        return {'decisions': self.decisions}

    def get_model(self):
        return self.model


class BackendProtocolTests(unittest.TestCase):
    def setUp(self):
        FakeMinisat.instances = []
        FakeMinisat.script = ()
        FakeMinisat.on_solve = None
        FakeMinisat.minimum_budget = 0

    def test_builtin_default_never_imports_optional_dependency(self):
        with patch('muql.backends._minisat', side_effect=AssertionError('unneeded import')):
            self.assertEqual(solve(1, [[1]]).status, 'sat')
            self.assertEqual(resolve_backend(), 'builtin')

    def test_auto_falls_back_and_explicit_missing_backend_is_clear(self):
        with patch('muql.backends._minisat', side_effect=BackendUnavailable('missing PySAT')):
            self.assertEqual(resolve_backend('auto'), 'builtin')
            self.assertEqual(solve(1, [[1]], backend='auto').status, 'sat')
            with self.assertRaises(BackendUnavailable):
                resolve_backend('pysat')
        for invalid in ('', None, 1, 'minisat22'):
            with self.assertRaises(ValueError):
                resolve_backend(invalid)

    def test_native_round_trip_normalizes_and_preserves_unused_defaults(self):
        clauses = [[1, 1], [-1, 3], [2, -2]]
        original = copy.deepcopy(clauses)
        with patch('muql.backends._minisat', return_value=FakeMinisat):
            result = solve(5, clauses, backend='pysat')
        self.assertEqual(result.status, 'sat')
        self.assertEqual(result.assignment, {1: True, 2: False, 3: True, 4: False, 5: False})
        self.assertEqual(clauses, original)
        self.assertTrue(FakeMinisat.instances[0].closed)

    def test_native_limited_none_is_resumed_not_reported_unsat(self):
        FakeMinisat.script = ((None, 1, None), (None, 2, None), (True, 3, [1]))
        with patch('muql.backends._minisat', return_value=FakeMinisat):
            result = solve(1, [[1]], max_decisions=5, backend='pysat')
        self.assertEqual(result.status, 'sat')
        self.assertEqual(result.decisions, 3)
        self.assertEqual(FakeMinisat.instances[0].budgets, [5, 10, 20])

    def test_native_slices_grow_when_limited_calls_discard_search_progress(self):
        FakeMinisat.minimum_budget = 20_000
        with patch('muql.backends._minisat', return_value=FakeMinisat):
            result = solve(2, [[1, 2]], max_decisions=50_000,
                           timeout=0.1, backend='pysat')
        self.assertEqual(result.status, 'sat')
        self.assertEqual(FakeMinisat.instances[0].budgets, [10_000, 20_000])

    def test_native_slice_growth_stays_within_signed_integer_limit(self):
        FakeMinisat.minimum_budget = 100
        with patch('muql.backends._minisat', return_value=FakeMinisat):
            with patch('muql.backends._MAX_PROPAGATION_SLICE', 8):
                result = solve(2, [[1, 2]], max_decisions=5, backend='pysat')
        self.assertEqual(result.status, 'unknown')
        self.assertIn('propagation-slice', result.reason)
        self.assertEqual(FakeMinisat.instances[0].budgets, [5, 8])

    def test_unknown_at_decision_cap_and_late_native_results_are_discarded(self):
        for status, count in ((None, 2), (True, 3), (False, 3)):
            FakeMinisat.script = ((status, count, [1]),)
            with patch('muql.backends._minisat', return_value=FakeMinisat):
                result = solve(1, [[1]], max_decisions=2, backend='pysat')
            self.assertEqual(result.status, 'unknown')
            self.assertEqual(result.assignment, {})
            self.assertTrue(FakeMinisat.instances[-1].closed)

    def test_native_result_after_elapsed_deadline_is_unknown(self):
        for status in (True, False, None):
            clock = [0.0]
            FakeMinisat.script = ((status, 0, [1]),)
            FakeMinisat.on_solve = lambda: clock.__setitem__(0, 2.0)
            with patch('muql.backends._minisat', return_value=FakeMinisat):
                with patch('muql.backends.monotonic', side_effect=lambda: clock[0]):
                    result = solve(1, [[1]], timeout=1.0, backend='pysat')
            self.assertEqual(result.status, 'unknown')
            self.assertIn('timeout', result.reason)
            self.assertTrue(FakeMinisat.instances[-1].closed)

    def test_native_loading_and_zero_timeout_use_same_deadline(self):
        clock = [0.0]

        def clauses():
            yield [1]
            clock[0] = 2.0
            yield [-1]

        with patch('muql.backends._minisat', return_value=FakeMinisat):
            self.assertEqual(solve(1, [[1]], timeout=0, backend='pysat').status, 'unknown')
            with patch('muql.backends.monotonic', side_effect=lambda: clock[0]):
                result = solve(1, clauses(), timeout=1.0, backend='pysat')
        self.assertEqual(result.status, 'unknown')
        self.assertEqual(FakeMinisat.instances, [])

    def test_zero_native_decision_cap_is_not_native_unlimited_budget(self):
        with patch('muql.backends._minisat', return_value=FakeMinisat):
            self.assertEqual(solve(2, [[1, 2]], max_decisions=0, backend='pysat').status,
                             'unknown')
            self.assertEqual(solve(2, [[1], [-1, 2]], max_decisions=0,
                                   backend='pysat').status, 'sat')
        self.assertEqual(FakeMinisat.instances, [])

    def test_malformed_inputs_are_not_hidden_by_contradiction_or_tautology(self):
        with patch('muql.backends._minisat', return_value=FakeMinisat):
            for clauses in ([[], [2]], [[1, -1, False]], [[1, 0.0]]):
                with self.assertRaises(ValueError):
                    solve(1, clauses, backend='pysat')
            self.assertEqual(solve(0, [[]], backend='pysat').status, 'unsat')

    def test_native_boolean_witness_is_independently_validated(self):
        for bad_model in (None, [-1]):
            FakeMinisat.script = ((True, 0, bad_model),)
            with patch('muql.backends._minisat', return_value=FakeMinisat):
                with self.assertRaises(RuntimeError):
                    solve(1, [[1]], backend='pysat')
            self.assertTrue(FakeMinisat.instances[-1].closed)

    def test_checker_native_path_preserves_independent_semantic_replay(self):
        theory = loads('```muql\npoints a\nvalues x\nstages 1\nquorums {a}\n'
                       'predicate P/0\naxiom Broken: B(P)\nproperty True: T(P)\n```')
        with patch('muql.backends._minisat', return_value=FakeMinisat):
            report = check(theory, solver='auto')
        self.assertEqual(report.stats['backend'], 'pysat')
        self.assertEqual(report.properties[0].status, 'counterexample')
        self.assertTrue(replay(theory, report.properties[0].countermodel))


try:
    NATIVE_AVAILABLE = resolve_backend('pysat') == 'pysat'
except BackendUnavailable:
    NATIVE_AVAILABLE = False


@unittest.skipUnless(NATIVE_AVAILABLE, 'optional python-sat dependency is unavailable')
class RealNativeBackendTests(unittest.TestCase):
    def test_real_minisat_large_easy_formula_survives_limited_call_restarts(self):
        # More propagations than the initial slice, but no difficult reasoning.
        # A fixed slice can repeatedly discard all non-root progress here.
        clauses = [[2 * i + 1, 2 * i + 2] for i in range(6_000)]
        result = solve(12_000, clauses, timeout=10, backend='pysat')
        self.assertEqual(result.status, 'sat')
        self.assertTrue(satisfies(clauses, result.assignment))

    def test_real_minisat_matches_independent_small_cnf_truth_tables(self):
        rng = random.Random(20261011)
        for nvars in range(1, 9):
            for _ in range(30):
                clauses = [[rng.choice((-1, 1)) * rng.randrange(1, nvars + 1)
                            for _ in range(rng.randrange(1, 5))]
                           for _ in range(rng.randrange(0, 5 * nvars))]
                expected = any(satisfies(clauses, dict(enumerate(bits, 1)))
                               for bits in itertools.product((False, True), repeat=nvars))
                result = solve(nvars, clauses, backend='pysat')
                self.assertEqual(result.status, 'sat' if expected else 'unsat')
                if expected:
                    self.assertTrue(satisfies(clauses, result.assignment))

    def test_real_minisat_cooperates_with_short_timeout_on_hard_contradiction(self):
        pigeons, holes = 21, 20
        variable = lambda p, h: p * holes + h + 1
        clauses = [[variable(p, h) for h in range(holes)] for p in range(pigeons)]
        clauses += [[-variable(p, h), -variable(q, h)]
                    for h in range(holes) for p in range(pigeons)
                    for q in range(p + 1, pigeons)]
        result = solve(pigeons * holes, clauses, timeout=0.02, backend='pysat')
        self.assertEqual(result.status, 'unknown')
        self.assertEqual(result.assignment, {})


if __name__ == '__main__':
    unittest.main()
