"""From-scratch SAT audit: independent truth rows, encoding and numeric edges.

The truth-row oracle uses integer bitsets and does not call either Circuit or
the SAT solver.  Encoding checks enumerate auxiliary assignments directly, so
an encoder defect cannot be masked by a corresponding SAT solver defect.
"""

import heapq
import itertools
import math
import random
import unittest
from unittest.mock import patch

from muql.sat import Circuit, _Solver, solve


def truth_rows(nvars, clauses):
    """Return the bitset of all satisfying truth-table rows of a finite CNF."""
    universe = (1 << (1 << nvars)) - 1
    columns = [universe // ((1 << (1 << v)) + 1) << (1 << v)
               for v in range(nvars)]
    rows = universe
    for clause in clauses:
        clause_rows = 0
        for literal in clause:
            column = columns[abs(literal) - 1]
            clause_rows |= column if literal > 0 else universe ^ column
        rows &= clause_rows
    return rows


def holds(clauses, assignment):
    return all(any(assignment[abs(literal)] == (literal > 0)
                   for literal in clause) for clause in clauses)


class IndependentEncodingAudit(unittest.TestCase):
    def test_all_signed_constant_repeated_and_empty_gate_inputs(self):
        literal_choices = (1, -1, 2, -2, 3, -3, 4, -4)
        for operation, widths in (("and_", range(4)), ("or_", range(4)),
                                  ("iff", (2,)), ("implies", (2,))):
            for width in widths:
                for inputs in itertools.product(literal_choices, repeat=width):
                    circuit = Circuit()
                    for _ in range(3):
                        circuit.new_var()
                    output = getattr(circuit, operation)(*inputs)
                    for values in itertools.product((False, True), repeat=3):
                        base = {1: True, **dict(enumerate(values, 2))}
                        arguments = [base[abs(v)] == (v > 0) for v in inputs]
                        if operation == "and_":
                            expected = all(arguments)
                        elif operation == "or_":
                            expected = any(arguments)
                        elif operation == "iff":
                            expected = arguments[0] == arguments[1]
                        else:
                            expected = not arguments[0] or arguments[1]
                        extensions = []
                        for auxiliary in itertools.product(
                                (False, True), repeat=circuit.nvars - 4):
                            assignment = {**base, **dict(enumerate(auxiliary, 5))}
                            if holds(circuit.clauses, assignment):
                                extensions.append(assignment)
                        self.assertEqual(len(extensions), 1,
                                         (operation, inputs, values))
                        actual = extensions[0][abs(output)] == (output > 0)
                        self.assertEqual(actual, expected,
                                         (operation, inputs, values))

    def test_clause_simplification_preserves_every_truth_row(self):
        for width in range(4):
            for inputs in itertools.product((1, -1, 2, -2, 3, -3), repeat=width):
                circuit = Circuit()
                circuit.new_var()
                circuit.new_var()
                circuit.add_clause(*inputs)
                self.assertEqual(truth_rows(3, circuit.clauses),
                                 truth_rows(3, [[1], list(inputs)]), inputs)


class IndependentSolverAudit(unittest.TestCase):
    def assert_matches_truth_rows(self, nvars, clauses):
        original = [clause[:] for clause in clauses]
        expected = truth_rows(nvars, clauses)
        result = solve(nvars, clauses, timeout=math.inf)
        self.assertEqual(result.status, "sat" if expected else "unsat", clauses)
        self.assertEqual(clauses, original, "caller clauses were mutated")
        if expected:
            self.assertEqual(set(result.assignment), set(range(1, nvars + 1)))
            self.assertTrue(holds(clauses, result.assignment), clauses)
        else:
            self.assertEqual(result.assignment, {})

    def test_all_three_variable_cnfs_with_at_most_three_distinct_clauses(self):
        clauses = [[(v + 1) * sign for v, sign in enumerate(signs) if sign]
                   for signs in itertools.product((-1, 0, 1), repeat=3)]
        for count in range(4):
            for formula in itertools.combinations(clauses, count):
                self.assert_matches_truth_rows(3, list(formula))

    def test_independent_truth_row_oracle_on_seeded_mixed_cnfs(self):
        rng = random.Random(20261010)
        for nvars in range(1, 17):
            for index in range(80):
                width = min(nvars, 3) if index % 2 else None
                clauses = []
                for _ in range(rng.randrange(1, 6 * nvars + 1)):
                    if width:
                        variables = rng.sample(range(1, nvars + 1), width)
                    else:
                        variables = [rng.randrange(1, nvars + 1)
                                     for _ in range(rng.randrange(1, 6))]
                    clauses.append([v * rng.choice((-1, 1)) for v in variables])
                self.assert_matches_truth_rows(nvars, clauses)

    def test_activity_underflow_cannot_remove_live_variables(self):
        solver = _Solver(4, math.inf, 20)
        original = [[1, 2], [3, 4]]
        for clause in original:
            solver.add(clause[:])
        solver.activity[1:] = [1.0] * 4
        solver.heap = [(-1.0, v) for v in range(1, 5)]
        heapq.heapify(solver.heap)
        # Numeric state reached by repeatedly bumping the busy part of a large
        # search while variables 1, 2 and 4 retain only their initial activity.
        # Force only the scale transitions; no thousands-conflict fixture is
        # needed to expose whether a heuristic is allowed to change semantics.
        for _ in range(4):
            solver.increment = 1e101
            solver.bump(3)
        self.assertEqual(solver.activity[1:3], [0.0, 0.0])
        result = solver.run()
        self.assertEqual(result.status, "sat")
        self.assertTrue(holds(original, result.assignment), result)

    def test_rescaling_does_not_make_unused_variables_spend_budget(self):
        solver = _Solver(100, math.inf, 1)
        solver.add([1, 2])
        solver.activity[1] = solver.activity[2] = 1.0
        solver.increment = 1e101
        solver.bump(1)
        result = solver.run()
        self.assertEqual(result.status, "sat")
        self.assertEqual(result.decisions, 1)
        self.assertTrue(holds([[1, 2]], result.assignment))

    def test_restart_search_on_known_pigeonhole_contradiction(self):
        pigeons, holes = 7, 6
        variable = lambda pigeon, hole: pigeon * holes + hole + 1
        clauses = [[variable(p, h) for h in range(holes)] for p in range(pigeons)]
        clauses += [[-variable(p, h), -variable(q, h)]
                    for h in range(holes) for p in range(pigeons)
                    for q in range(p + 1, pigeons)]
        analyses = []
        analyze = _Solver.analyze

        def record_analysis(solver, conflict):
            learned, level = analyze(solver, conflict)
            analyses.append((learned[:], level))
            return learned, level

        with patch.object(_Solver, "analyze", record_analysis):
            result = solve(pigeons * holes, clauses, timeout=math.inf)
        self.assertEqual(result.status, "unsat")
        self.assertGreaterEqual(len(analyses), 100, "fixture must exercise restarts")

    def test_budget_exhaustion_never_claims_unsatisfiability(self):
        for budget in (0, 1, 2):
            clauses = [[1, 2], [3, 4], [5, 6]]
            result = solve(6, clauses, max_decisions=budget)
            self.assertEqual(result.status, "unknown")
            self.assertEqual(result.decisions, budget)
            self.assertEqual(result.assignment, {})

    def test_expiry_during_input_and_each_search_stage_is_unknown(self):
        clock = [0.0]

        def expiring_input():
            yield [1]
            clock[0] = 2.0
            yield [-1]

        with patch("muql.sat.time.monotonic", side_effect=lambda: clock[0]):
            result = solve(1, expiring_input(), timeout=1.0)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.assignment, {})

        # This four-clause formula requires a decision and conflict analysis;
        # without expiration it is unsatisfiable, not merely budget-limited.
        clauses = [[1, 2], [1, -2], [-1, 2], [-1, -2]]
        for stage in ("propagate", "analyze", "backtrack", "choose"):
            clock[0] = 0.0
            entered = []
            method = getattr(_Solver, stage)

            def expire(solver, *args):
                entered.append(True)
                clock[0] = 2.0
                return method(solver, *args)

            with patch("muql.sat.time.monotonic", side_effect=lambda: clock[0]):
                with patch.object(_Solver, stage, expire):
                    result = solve(2, clauses, timeout=1.0)
            self.assertTrue(entered, stage)
            self.assertEqual(result.status, "unknown", (stage, result))
            self.assertEqual(result.assignment, {})

    def test_input_validation_continues_after_tautology_or_contradiction(self):
        for clauses in ([[1, -1, 0]], [[], [2]], [[1], [-1], [True]]):
            with self.assertRaises(ValueError):
                solve(1, clauses, timeout=math.inf)


if __name__ == "__main__":
    unittest.main()
