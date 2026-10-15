"""Release audit: exact generator closure and recurrence-cache boundaries."""

from itertools import product
import random
import unittest
from unittest.mock import patch

from muql.evaluate import Evaluator
from muql.frame import Frame, FrameLimit
from muql.syntax import Node, parse_formula
from muql.theory import Theory


def theory_for(points, generators, *, values=("red", "blue")):
    return Theory("release audit", points, values, 1,
                  tuple(tuple(points[p] for p in group) for group in generators),
                  {"P": 0, "R": 1}, {}, {})


class GeneratorClosureTests(unittest.TestCase):
    def test_generated_opens_equal_unions_of_all_generator_subfamilies(self):
        rng = random.Random(20261013)
        for size in range(1, 8):
            points = tuple(f"p{i}" for i in range(size))
            subsets = [frozenset(i for i in range(size) if mask & (1 << i))
                       for mask in range(1, 1 << size)]
            for _ in range(12):
                generators = rng.sample(subsets, min(len(subsets), rng.randrange(1, 10)))
                # Direct definition: take every subfamily, then its union.
                expected = {frozenset(range(size))}
                for choices in product((False, True), repeat=len(generators)):
                    union = frozenset(p for group, selected in zip(generators, choices)
                                      if selected for p in group)
                    if union:
                        expected.add(union)
                frame = Frame.from_theory(theory_for(points, generators))
                self.assertEqual(set(frame.quorums), expected)
                self.assertEqual(frame.quorums,
                                 tuple(sorted(expected, key=lambda q: (len(q), tuple(sorted(q))))))

    def test_closure_limits_remain_exact_at_the_boundary(self):
        points = tuple(f"p{i}" for i in range(9))
        theory = theory_for(points, [frozenset({i}) for i in range(9)])
        self.assertEqual(len(Frame.from_theory(theory, max_quorums=511).quorums), 511)
        with self.assertRaisesRegex(FrameLimit, "union closure exceeds 510"):
            Frame.from_theory(theory, max_quorums=510)
        with self.assertRaisesRegex(FrameLimit, "input exceeds 8"):
            Frame.from_theory(theory, max_quorums=8)

    def test_generator_expansion_checks_the_deadline_during_work(self):
        points = tuple(f"p{i}" for i in range(10))
        theory = theory_for(points, [frozenset({i}) for i in range(10)])
        with patch("muql.frame.monotonic", side_effect=(0.0, 2.0)):
            with self.assertRaisesRegex(FrameLimit, "timeout"):
                Frame.from_theory(theory, deadline=1.0)


class RecurrenceMemoTests(unittest.TestCase):
    def test_independent_nested_recurrences_do_not_repeat_exponentially(self):
        frame = Frame(("p",), (frozenset({0}),), 1)
        theory = theory_for(frame.points, frame.quorums)
        formula = Node("pred", value="P")
        for index in range(10):
            name = f"X{index}"
            formula = Node("mu", (Node("and", (
                Node("not", (Node("var", value=name),)), formula)),), name)
        for truth in range(3):
            evaluator = Evaluator(theory, frame, {("P", 0, 0, ()): truth})
            with patch.object(evaluator, "_compute", wraps=evaluator._compute) as compute:
                self.assertEqual(evaluator.eval(formula, (0, 0, 0)), 0 if truth == 0 else 1)
                # Ten one-cell recurrences need only a linear number of
                # evaluations. The uncached implementation made 354,289.
                self.assertLess(compute.call_count, 150)

    def test_outer_dependent_nested_recurrences_match_direct_enumeration(self):
        frame = Frame(("p",), (frozenset({0}),), 1)
        theory = theory_for(frame.points, frame.quorums)

        def scalar(formula, atom, variables):
            op, args = formula.op, formula.args
            if op == "pred":
                return atom
            if op == "var":
                return variables[formula.value]
            if op == "not":
                return 2 - scalar(args[0], atom, variables)
            if op in ("and", "or"):
                values = [scalar(arg, atom, variables) for arg in args]
                return min(values) if op == "and" else max(values)
            candidates = []
            for truth in range(3):
                image = scalar(args[0], atom, {**variables, formula.value: truth})
                if (image <= truth) if op == "mu" else (truth <= image):
                    candidates.append(truth)
            return min(candidates) if op == "mu" else max(candidates)

        for outer, inner, connective, negated in product(
                ("mu", "nu"), ("mu", "nu"), ("&", "|"), (False, True)):
            reference = "!X" if negated else "X"
            formula = parse_formula(f"{outer} X. P | ({inner} Y. {reference} {connective} !Y)")
            for truth in range(3):
                evaluator = Evaluator(theory, frame, {("P", 0, 0, ()): truth})
                self.assertEqual(evaluator.eval(formula, (0, 0, 0)), scalar(formula, truth, {}),
                                 (str(formula), truth))

    def test_closed_recurrence_cache_retains_context_and_value_environment(self):
        frame = Frame(("a", "b"), (frozenset({0, 1}),), 1)
        theory = theory_for(frame.points, frame.quorums)
        valuation = {("R", 0, point, (value,)): truth
                     for point, truths in enumerate(((2, 1), (0, 2)))
                     for value, truth in zip(theory.values, truths)}
        evaluator = Evaluator(theory, frame, valuation)
        formula = parse_formula("mu Y. Y | (forall v. (mu X. R(v) | X))")
        self.assertEqual(evaluator.eval(formula, (0, 0, 0)), 1)
        self.assertEqual(evaluator.eval(formula, (0, 1, 0)), 0)


if __name__ == "__main__":
    unittest.main()
