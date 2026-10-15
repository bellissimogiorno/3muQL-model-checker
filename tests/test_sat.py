"""Independent truth-table checks for the circuit encoder and SAT engine."""

import itertools
import random
import unittest
from unittest.mock import patch

from muql.sat import Circuit, solve


def satisfies(clauses, assignment):
    return all(any(assignment[abs(lit)] == (lit > 0) for lit in clause) for clause in clauses)


def brute_force(nvars, clauses):
    for values in itertools.product((False, True), repeat=nvars):
        assignment = dict(enumerate(values, start=1))
        if satisfies(clauses, assignment):
            return assignment
    return None


class CircuitTests(unittest.TestCase):
    def test_constants_and_hash_consing(self):
        circuit = Circuit()
        a, b = circuit.new_var("a"), circuit.new_var("b")
        self.assertEqual(circuit.and_(), circuit.true)
        self.assertEqual(circuit.or_(), circuit.false)
        self.assertEqual(circuit.and_(a, a, circuit.true), a)
        self.assertEqual(circuit.and_(a, -a), circuit.false)
        self.assertEqual(circuit.or_(a, -a), circuit.true)
        self.assertEqual(circuit.and_(a, b), circuit.and_(b, a, a))
        self.assertEqual(circuit.or_(-a, -b), -circuit.and_(a, b))
        self.assertEqual(circuit.iff(a, b), circuit.iff(-b, -a))
        self.assertEqual(circuit.iff(a, -b), -circuit.iff(a, b))

    def test_every_gate_by_truth_table(self):
        for left, right in itertools.product((False, True), repeat=2):
            for operation, expected in (
                ("and_", left and right), ("or_", left or right),
                ("iff", left == right), ("implies", not left or right),
            ):
                with self.subTest(left=left, right=right, operation=operation):
                    circuit = Circuit()
                    a, b = circuit.new_var(), circuit.new_var()
                    out = getattr(circuit, operation)(a, b)
                    fixed = [[a if left else -a], [b if right else -b]]
                    good = [[out if expected else -out]]
                    bad = [[-out if expected else out]]
                    self.assertEqual(solve(circuit.nvars, circuit.clauses + fixed + good).status, "sat")
                    self.assertEqual(solve(circuit.nvars, circuit.clauses + fixed + bad).status, "unsat")

    def test_nested_circuit(self):
        circuit = Circuit()
        a, b, c = [circuit.new_var() for _ in range(3)]
        out = circuit.iff(circuit.implies(a, b), circuit.or_(-a, b))
        circuit.add_clause(-out)
        self.assertEqual(solve(circuit.nvars, circuit.clauses).status, "unsat")

    def test_clause_simplification(self):
        circuit = Circuit()
        a = circuit.new_var()
        circuit.add_clause(a, -a)
        circuit.add_clause(circuit.true)
        self.assertEqual(circuit.clauses, [[1]])
        circuit.add_clause(circuit.false, a, a)
        self.assertEqual(circuit.clauses[-1], [a])
        circuit.add_clause()
        self.assertEqual(solve(circuit.nvars, circuit.clauses).status, "unsat")

    def test_invalid_literal_is_not_hidden_by_simplification(self):
        circuit = Circuit()
        for operation in (circuit.and_, circuit.or_, circuit.add_clause):
            with self.assertRaises(ValueError):
                operation(circuit.true, 100)


class SolverTests(unittest.TestCase):
    def test_empty_and_unit_cases(self):
        self.assertEqual(solve(0, []).status, "sat")
        self.assertEqual(solve(0, [[]]).status, "unsat")
        self.assertEqual(solve(1, [[1], [-1]]).status, "unsat")
        self.assertEqual(solve(3, [[1], [-1, 2], [-2, 3]]).assignment,
                         {1: True, 2: True, 3: True})
        self.assertEqual(solve(3, [[1, -1]]).assignment,
                         {1: False, 2: False, 3: False})

    def test_exhaustive_two_variable_cnfs(self):
        # Every set of non-tautological clauses over two variables (512 CNFs).
        possible = [[]]
        for width in (1, 2):
            for clause in itertools.combinations((1, -1, 2, -2), width):
                if not any(-literal in clause for literal in clause):
                    possible.append(list(clause))
        for mask in range(1 << len(possible)):
            clauses = [c for bit, c in enumerate(possible) if mask & (1 << bit)]
            result = solve(2, clauses)
            expected = brute_force(2, clauses)
            self.assertEqual(result.status, "sat" if expected is not None else "unsat", clauses)
            if expected is not None:
                self.assertTrue(satisfies(clauses, result.assignment))

    def test_seeded_random_cnfs_against_brute_force(self):
        rng = random.Random(4815162342)
        for nvars in range(1, 9):
            for _ in range(130):
                clauses = [[rng.choice((-1, 1)) * rng.randint(1, nvars)
                            for _ in range(rng.randint(1, min(5, nvars + 1)))]
                           for _ in range(rng.randint(0, nvars * 7))]
                original = [clause[:] for clause in clauses]
                result = solve(nvars, clauses)
                expected = brute_force(nvars, clauses)
                self.assertEqual(result.status, "sat" if expected is not None else "unsat", clauses)
                self.assertEqual(clauses, original, "solver mutated caller's clauses")
                if result.status == "sat":
                    self.assertTrue(satisfies(clauses, result.assignment))

    def test_pigeonhole_unsatisfiable(self):
        for pigeons in range(2, 8):
            holes = pigeons - 1
            variable = lambda p, h: p * holes + h + 1
            clauses = [[variable(p, h) for h in range(holes)] for p in range(pigeons)]
            clauses += [[-variable(a, h), -variable(b, h)]
                        for h in range(holes) for a in range(pigeons) for b in range(a + 1, pigeons)]
            result = solve(pigeons * holes, clauses, timeout=15)
            self.assertEqual(result.status, "unsat", (pigeons, result))

    def test_random_three_sat_exercises_conflict_learning(self):
        rng = random.Random(314159)
        for nvars in range(3, 11):
            for _ in range(45):
                clauses = [[v * rng.choice((-1, 1)) for v in rng.sample(range(1, nvars + 1), 3)]
                           for _ in range(int(4.3 * nvars))]
                result = solve(nvars, clauses)
                expected = brute_force(nvars, clauses)
                self.assertEqual(result.status, "sat" if expected is not None else "unsat", clauses)
                if result.status == "sat":
                    self.assertTrue(satisfies(clauses, result.assignment))

    def test_thousands_of_variables(self):
        clauses = [[1]] + [[-v, v + 1] for v in range(1, 5000)]
        result = solve(5000, clauses)
        self.assertEqual(result.status, "sat")
        self.assertTrue(all(result.assignment.values()))

    def test_decision_budget_does_not_claim_unsat(self):
        result = solve(2, [[1, 2]], max_decisions=0)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.assignment, {})
        self.assertEqual(solve(2, [[1], [-1, 2]], max_decisions=0).status, "sat")
        self.assertEqual(solve(1, [[1], [-1]], max_decisions=0).status, "unsat")

    def test_timeout(self):
        self.assertEqual(solve(1, [], timeout=0).status, "unknown")
        ticks = itertools.count()
        with patch("muql.sat.time.monotonic", side_effect=lambda: next(ticks)):
            result = solve(1000, [[1]] + [[-v, v + 1] for v in range(1, 1000)], timeout=20)
        self.assertEqual(result.status, "unknown")

    def test_bad_inputs(self):
        for nvars, clauses in ((-1, []), (1, [[0]]), (1, [[2]]), (1, [[True]])):
            with self.assertRaises(ValueError):
                solve(nvars, clauses)
        with self.assertRaises(ValueError):
            solve(1, [], timeout=-1)
        with self.assertRaises(ValueError):
            solve(1, [], max_decisions=-1)


if __name__ == "__main__":
    unittest.main()
