"""Fresh solver checks with exhaustive assignments independent of the encoder.

The public solver is stateless: assumptions are supplied as additional unit
clauses. Repeated calls must not retain earlier assumptions or learned clauses.
"""

import copy
import itertools
import math
import random
import unittest
from unittest.mock import patch

from muql import backends
from muql.sat import _Solver, solve


def holds(clauses, assignment):
    return all(any(assignment[abs(literal)] == (literal > 0)
                   for literal in clause) for clause in clauses)


def models(nvars, clauses):
    return [assignment for bits in itertools.product((False, True), repeat=nvars)
            if holds(clauses, assignment := dict(enumerate(bits, 1)))]


class FreshSolverAudit(unittest.TestCase):
    def test_repeated_solves_with_every_small_partial_assignment(self):
        base = [[1, 2], [-1, 3], [-2, 4], [-3, -4, 5], [3, -5, 6]]
        unchanged = copy.deepcopy(base)
        expected = models(6, base)
        for index, choices in enumerate(itertools.product((None, False, True), repeat=6)):
            assumptions = [[variable if value else -variable]
                           for variable, value in enumerate(choices, 1) if value is not None]
            clauses = base + assumptions
            extensions = [assignment for assignment in expected if holds(assumptions, assignment)]
            # Exercise one-shot iterables as well as reusable input lists.
            supplied = clauses if index % 2 else (iter(clause) for clause in clauses)
            result = solve(6, supplied, timeout=math.inf)
            self.assertEqual(result.status, "sat" if extensions else "unsat", choices)
            if extensions:
                self.assertIn(result.assignment, extensions)
            bounded = solve(6, clauses, timeout=math.inf, max_decisions=index % 3)
            self.assertLessEqual(bounded.decisions, index % 3)
            if bounded.status == "sat":
                self.assertIn(bounded.assignment, extensions)
            elif bounded.status == "unsat":
                self.assertFalse(extensions)
            else:
                self.assertEqual(bounded.assignment, {})
            self.assertEqual(base, unchanged)

    def test_learned_clauses_are_asserting_and_hold_in_every_original_model(self):
        rng = random.Random(202610111)
        original_analyze = _Solver.analyze
        learned_count = 0
        nonvacuous_count = 0
        for nvars in range(4, 10):
            for _ in range(35):
                clauses = [[variable * rng.choice((-1, 1))
                            for variable in rng.sample(range(1, nvars + 1), 3)]
                           for _ in range(int(3.8 * nvars))]
                expected = models(nvars, clauses)

                def analyze(solver, conflict):
                    nonlocal learned_count, nonvacuous_count
                    learned, level = original_analyze(solver, conflict)
                    learned_count += 1
                    nonvacuous_count += bool(expected)
                    self.assertEqual(solver.levels[abs(learned[0])], len(solver.trail_limits))
                    self.assertEqual(solver.value(learned[0]), -1)
                    self.assertTrue(all(solver.levels[abs(literal)] < len(solver.trail_limits)
                                        for literal in learned[1:]))
                    self.assertEqual(level, max((solver.levels[abs(literal)]
                                                 for literal in learned[1:]), default=0))
                    self.assertTrue(all(holds([learned], assignment) for assignment in expected))
                    return learned, level

                with patch.object(_Solver, "analyze", analyze):
                    result = solve(nvars, clauses, timeout=math.inf)
                self.assertEqual(result.status, "sat" if expected else "unsat")
                if expected:
                    self.assertIn(result.assignment, expected)
        self.assertGreater(learned_count, 100)
        self.assertGreater(nonvacuous_count, 50)

    def test_invalid_timeouts_have_one_public_contract(self):
        for operation in (solve, backends.solve):
            for timeout in (True, False, None, "1", 1j, float("nan"), -1, -math.inf,
                            10**400, -(10**400)):
                with self.subTest(operation=operation.__module__, timeout=timeout):
                    with self.assertRaises(ValueError):
                        operation(0, [], timeout=timeout)
            for timeout in (1, 0.5, math.inf):
                self.assertEqual(operation(0, [], timeout=timeout).status, "sat")

    def test_zero_timeout_does_not_allocate_solver_state_or_read_input(self):
        def unreadable():
            raise AssertionError("zero timeout must not consume the CNF")
            yield []

        with patch("muql.sat._Solver", side_effect=AssertionError("unnecessary allocation")):
            for operation in (solve, backends.solve):
                result = operation(10**9, unreadable(), timeout=0)
                self.assertEqual(result.status, "unknown")
                self.assertEqual(result.assignment, {})
                self.assertEqual(result.decisions, 0)

    def test_root_conflict_after_deadline_is_unknown(self):
        clock = [0.0]
        original_propagate = _Solver.propagate
        reached = []

        def expire_on_root_conflict(solver):
            conflict = original_propagate(solver)
            if conflict is not None and not solver.trail_limits:
                reached.append(True)
                clock[0] = 2.0
            return conflict

        with patch("muql.sat.time.monotonic", side_effect=lambda: clock[0]):
            with patch.object(_Solver, "propagate", expire_on_root_conflict):
                result = solve(2, [[1, 2], [1, -2], [-1, 2], [-1, -2]], timeout=1)
        self.assertTrue(reached)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.assignment, {})
        self.assertEqual(result.reason, "timeout exhausted")


if __name__ == "__main__":
    unittest.main()
