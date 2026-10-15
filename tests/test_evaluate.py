"""Concrete semantic tests against paper truth tables and direct enumeration."""

from itertools import product
import random
from types import SimpleNamespace
import unittest

from muql.evaluate import Evaluator, EvaluationError, FixedPointLimitError
from muql.frame import Frame
from muql.syntax import parse_formula


def make_evaluator(*, points=2, stages=1, values=("red", "blue"), quorums=None,
                   time="finite", atoms=None, predicates=None):
    names = tuple(f"p{i}" for i in range(points))
    if quorums is None:
        quorums = (frozenset(range(points)),)
    frame = Frame(names, tuple(map(frozenset, quorums)), stages, time)
    theory = SimpleNamespace(values=values, predicates=predicates or {"P": 0, "A": 1})
    valuation = {
        (predicate, stage, point, arguments): 0
        for predicate, arity in theory.predicates.items()
        for stage in range(stages)
        for point in range(points)
        for arguments in product(values, repeat=arity)
    }
    valuation.update(atoms or {})
    return Evaluator(theory, frame, valuation)


def truth(evaluator, formula, ctx=(0, 0, 0)):
    return evaluator.eval(parse_formula(formula), ctx)


class TruthTableTests(unittest.TestCase):
    def test_paper_binary_truth_tables(self):
        evaluator = make_evaluator()
        # Figure 1, rows and columns in the order f, b, t.
        tables = {
            "&": ((0, 0, 0), (0, 1, 1), (0, 1, 2)),
            "|": ((0, 1, 2), (1, 1, 2), (2, 2, 2)),
            "->": ((2, 2, 2), (1, 1, 2), (0, 1, 2)),
            "⇀": ((2, 2, 2), (1, 1, 2), (0, 0, 2)),
            "<=>": ((2, 0, 0), (0, 2, 0), (0, 0, 2)),
            "<=": ((2, 2, 2), (0, 2, 2), (0, 0, 2)),
        }
        for operator, table in tables.items():
            for row, left in enumerate(("f", "b", "t")):
                for column, right in enumerate(("f", "b", "t")):
                    with self.subTest(operator=operator, left=left, right=right):
                        self.assertEqual(truth(evaluator, f"{left} {operator} {right}"), table[row][column])

    def test_paper_unary_truth_tables(self):
        evaluator = make_evaluator()
        tables = {"T": (0, 0, 2), "F": (2, 0, 0), "B": (0, 2, 0),
                  "TB": (0, 2, 2), "TF": (2, 0, 2), "FB": (2, 2, 0)}
        for operator, table in tables.items():
            for index, value in enumerate(("f", "b", "t")):
                self.assertEqual(truth(evaluator, f"{operator}({value})"), table[index])
        for index, value in enumerate(("f", "b", "t")):
            self.assertEqual(truth(evaluator, f"!{value}"), 2 - index)

    def test_equality_uses_values_and_lexical_value_bindings(self):
        evaluator = make_evaluator()
        self.assertEqual(truth(evaluator, "forall x. exists y. x == y"), 2)
        self.assertEqual(truth(evaluator, "exists x. forall y. x == y"), 0)
        self.assertEqual(truth(evaluator, "red != blue"), 2)
        self.assertEqual(truth(evaluator, "forall red. red == 'red'"), 0)

    def test_affine_and_unique_retain_broken_truth_values(self):
        for red, blue in product(range(3), repeat=2):
            evaluator = make_evaluator(atoms={
                ("A", 0, 0, ("red",)): red,
                ("A", 0, 0, ("blue",)): blue,
            })
            affine = 2 - min(red, blue)
            with self.subTest(red=red, blue=blue):
                self.assertEqual(truth(evaluator, "affine x. A(x)"), affine)
                self.assertEqual(truth(evaluator, "unique x. A(x)"), min(max(red, blue), affine))

    def test_missing_and_invalid_atoms_fail_explicitly(self):
        evaluator = make_evaluator()
        valuation = dict(evaluator.valuation)
        valuation.pop(("P", 0, 0, ()))
        evaluator = Evaluator(evaluator.theory, evaluator.frame, valuation)
        with self.assertRaisesRegex(EvaluationError, "missing atom"):
            truth(evaluator, "P")
        valuation[("P", 0, 0, ())] = 3
        evaluator = Evaluator(evaluator.theory, evaluator.frame, valuation)
        with self.assertRaisesRegex(EvaluationError, "invalid truth value"):
            truth(evaluator, "P")


class ModalTests(unittest.TestCase):
    def test_point_aliases_stay_in_current_quorum(self):
        evaluator = make_evaluator(quorums=({0}, {1}, {0, 1}), atoms={("P", 0, 0, ()): 2})
        # P is false throughout the selected {p1}, but true in another quorum.
        for formula in ("somewhere(P)", "diamond(P)", "◇P", "somewhere(box(P))"):
            with self.subTest(formula=formula):
                self.assertEqual(truth(evaluator, formula, (0, 1, 1)), 0)
        for formula in ("someQuorumSomePoint(P)", "∃Q◇P", "someQuorumSomePoint(box(P))"):
            with self.subTest(formula=formula):
                self.assertEqual(truth(evaluator, formula, (0, 1, 1)), 2)
        # P is true throughout the selected {p0}, but false in another quorum.
        for formula in ("everywhere(P)", "box(P)", "□P", "everywhere(diamond(P))"):
            with self.subTest(formula=formula):
                self.assertEqual(truth(evaluator, formula, (0, 0, 0)), 2)
        for formula in ("everyQuorumEveryPoint(P)", "∀Q□P", "everyQuorumEveryPoint(diamond(P))"):
            with self.subTest(formula=formula):
                self.assertEqual(truth(evaluator, formula, (0, 0, 0)), 0)

    def test_point_need_not_be_in_current_quorum(self):
        evaluator = make_evaluator(quorums=({0}, {1}, {0, 1}), atoms={("P", 0, 0, ()): 2})
        outside = (0, 1, 0)
        self.assertEqual(truth(evaluator, "P", outside), 0)
        self.assertEqual(truth(evaluator, "diamond(P)", outside), 2)
        self.assertEqual(truth(evaluator, "existsQ(P)", outside), 0)

    def test_compound_modalities_retain_the_changed_quorum(self):
        evaluator = make_evaluator(quorums=({0}, {1}, {0, 1}), atoms={("P", 0, 0, ()): 2})
        # At initial quorum {p1}, box(P) is false.  someQuorumSomePoint must change the
        # quorum as well as the point, reaching the singleton {p0}.
        self.assertEqual(truth(evaluator, "someQuorumSomePoint(box(P))", (0, 1, 1)), 2)
        self.assertEqual(truth(evaluator, "everyQuorumEveryPoint(diamond(P))", (0, 0, 0)), 0)
        self.assertEqual(truth(evaluator, "quorum(box(P))", (0, 1, 1)), 2)
        self.assertEqual(truth(evaluator, "contra(diamond(P))", (0, 0, 0)), 0)

    def test_compound_definitions_for_all_three_valued_assignments(self):
        definitions = {"someQuorumSomePoint": "existsQ(diamond(P))", "everyQuorumEveryPoint": "forallQ(box(P))",
                       "quorum": "existsQ(box(P))", "contra": "forallQ(diamond(P))"}
        for a, b in product(range(3), repeat=2):
            evaluator = make_evaluator(quorums=({0}, {1}, {0, 1}), atoms={
                ("P", 0, 0, ()): a, ("P", 0, 1, ()): b,
            })
            for short, expanded in definitions.items():
                for ctx in evaluator.frame.contexts:
                    self.assertEqual(truth(evaluator, f"{short}(P)", ctx), truth(evaluator, expanded, ctx))

    def test_three_way_intersection_is_stronger_than_pairwise(self):
        evaluator = make_evaluator(points=3, quorums=({0, 1}, {0, 2}, {1, 2}, {0, 1, 2}))
        self.assertEqual(truth(evaluator, "twined(2)"), 2)
        self.assertEqual(truth(evaluator, "twined(3)"), 0)


class TemporalTests(unittest.TestCase):
    def test_strict_and_inclusive_past_and_empty_boundaries(self):
        evaluator = make_evaluator(stages=3, atoms={("P", 0, 0, ()): 2, ("P", 1, 0, ()): 1})
        self.assertEqual(truth(evaluator, "yesterday(P)"), 0)
        self.assertEqual(truth(evaluator, "once(P)"), 0)
        self.assertEqual(truth(evaluator, "past(P)"), 2)
        self.assertEqual(truth(evaluator, "historically(P)"), 2)
        self.assertEqual(truth(evaluator, "once(P)", (2, 0, 0)), 2)
        self.assertEqual(truth(evaluator, "historically(P)", (2, 0, 0)), 1)
        self.assertEqual(truth(evaluator, "tomorrow(P)", (2, 0, 0)), 0)
        self.assertEqual(truth(evaluator, "sometime(P)", (2, 0, 0)), 0)
        self.assertEqual(truth(evaluator, "forever(P)", (2, 0, 0)), 2)

    def test_finite_future_is_strict_and_honors_empty_meets(self):
        evaluator = make_evaluator(stages=3)
        self.assertEqual(truth(evaluator, "sometime(t)"), 2)
        self.assertEqual(truth(evaluator, "infinitely(t)"), 0)
        self.assertEqual(truth(evaluator, "infinitely(f)", (2, 0, 0)), 2)
        self.assertEqual(truth(evaluator, "ultimately(f)"), 2)
        self.assertEqual(truth(evaluator, "ultimately(t)", (2, 0, 0)), 0)

    def test_stutter_tail_is_evaluated_in_the_last_stage(self):
        evaluator = make_evaluator(stages=3, time="stutter", atoms={("P", 2, 0, ()): 1})
        last = (2, 0, 0)
        for operator in ("tomorrow", "sometime", "forever", "infinitely"):
            self.assertEqual(truth(evaluator, f"{operator}(P)", last), 1)
        self.assertEqual(truth(evaluator, "infinitely(P)"), 1)
        self.assertEqual(truth(evaluator, "ultimately(f)"), 0)
        self.assertEqual(truth(evaluator, "yesterday(P)", last), 0)

    def test_latest_ignores_broken_and_chooses_latest_true_stage(self):
        evaluator = make_evaluator(stages=4, atoms={
            ("A", 0, 0, ("red",)): 2,
            ("A", 1, 0, ("blue",)): 2,
            ("A", 2, 0, ("red",)): 1,
        })
        self.assertEqual(truth(evaluator, "latest x = red. A(x)"), 0)
        self.assertEqual(truth(evaluator, "latest x = red. A(x)", (1, 0, 0)), 2)
        self.assertEqual(truth(evaluator, "latest x = red. A(x)", (3, 0, 0)), 0)
        self.assertEqual(truth(evaluator, "latest x = blue. A(x)", (3, 0, 0)), 2)

    def test_latest_before_diamond_differs_from_diamond_before_latest(self):
        evaluator = make_evaluator(stages=3, atoms={
            ("A", 0, 0, ("red",)): 2,
            ("A", 1, 1, ("blue",)): 2,
        })
        self.assertEqual(truth(evaluator, "latest x = red. diamond(A(x))", (2, 0, 0)), 0)
        self.assertEqual(truth(evaluator, "diamond(latest x = red. A(x))", (2, 0, 0)), 2)


class FixedPointTests(unittest.TestCase):
    def test_positive_least_and_greatest_fixed_points(self):
        evaluator = make_evaluator(stages=3, atoms={("P", 0, 0, ()): 2})
        self.assertEqual(truth(evaluator, "mu X. X"), 0)
        self.assertEqual(truth(evaluator, "nu X. X"), 2)
        for ctx in evaluator.frame.contexts:
            self.assertEqual(truth(evaluator, "mu X. yesterday(P | X)", ctx), truth(evaluator, "once(P)", ctx))
            self.assertEqual(truth(evaluator, "mu X. tomorrow(P | X)", ctx), truth(evaluator, "sometime(P)", ctx))

    def test_nonmonotone_meet_is_not_bottom_iteration(self):
        evaluator = make_evaluator()
        self.assertEqual(truth(evaluator, "mu X. !X"), 1)
        self.assertEqual(truth(evaluator, "nu X. !X"), 1)
        # With two points, (f,t), (t,f), and (b,b) are pre-fixed;
        # their componentwise meet is (f,f), which is not a fixed point.
        self.assertEqual(truth(evaluator, "mu X. !diamond(X)"), 0)

    def test_leader_closed_form_matches_exhaustive_prefixpoint_semantics(self):
        for assignment in product(range(3), repeat=3):
            evaluator = make_evaluator(points=4, quorums=({0, 1, 2}, {0, 1, 2, 3}), atoms={
                ("P", 0, point, ()): value for point, value in enumerate(assignment)
            })
            for point in range(4):
                ctx = (0, point, 0)
                optimized = truth(evaluator, "mu X. !diamond(P & X)", ctx)
                # The redundant disjunction deliberately bypasses the schema
                # optimizer, forcing enumeration of all pre-fixed assignments.
                reference = truth(evaluator, "mu X. !diamond((P & X) | f)", ctx)
                with self.subTest(assignment=assignment, point=point):
                    self.assertEqual(optimized, reference)

    def test_shadowed_fixedpoint_variables_are_lexical(self):
        evaluator = make_evaluator()
        self.assertEqual(truth(evaluator, "mu X. (X | (mu X. !X))"), 1)
        self.assertEqual(truth(evaluator, "nu X. (X & (mu Y. X | Y))"), 2)

    def test_nonmonotone_temporal_dependencies_are_exact(self):
        evaluator = make_evaluator(stages=3)
        result = [truth(evaluator, "mu X. !tomorrow(X)", (stage, 0, 0)) for stage in range(3)]
        self.assertEqual(result, [0, 0, 2])
        stuttering = make_evaluator(stages=3, time="stutter")
        self.assertEqual([truth(stuttering, "mu X. !tomorrow(X)", (stage, 0, 0)) for stage in range(3)], [0, 0, 1])

    def test_budget_is_based_on_dependencies_not_whole_frame(self):
        evaluator = make_evaluator(points=10, stages=3)
        self.assertEqual(truth(evaluator, "mu X. !X"), 1)
        with self.assertRaisesRegex(FixedPointLimitError, "dependent contexts"):
            truth(evaluator, "mu X. !someQuorumSomePoint(X)")
        # Positive recurrences do not need nonmonotone enumeration.
        self.assertEqual(truth(evaluator, "mu X. someQuorumSomePoint(X) | P"), 0)


class CompilerDifferentialTests(unittest.TestCase):
    def test_compiled_threshold_bits_match_concrete_denotations(self):
        """Replay one SAT assignment for many diverse formulae and contexts.

        Fixing every input atom means the solver must return precisely the
        evaluator's truth values, including broken values.  This tests more
        than designated satisfaction and exercises both threshold bits.
        """
        from muql.compile import Compiler
        from muql.sat import solve

        formulas = tuple(map(parse_formula, (
            "P", "!P", "P & A(red)", "P | A(red)", "P xor A(red)",
            "P -> A(red)", "P ⇀ A(red)", "P <=> A(red)", "P <= A(red)",
            "T(P)", "F(P)", "B(P)", "TF(P)", "TB(P)", "FB(P)",
            "forall x. A(x)", "exists x. A(x)", "affine x. A(x)", "unique x. A(x)",
            "diamond(P)", "box(P)", "existsQ(box(P))", "forallQ(diamond(P))",
            "someQuorumSomePoint(box(P))", "everyQuorumEveryPoint(diamond(P))", "quorum(P)", "contra(P)",
            "yesterday(P)", "tomorrow(P)", "once(P)", "past(P)", "historically(P)",
            "sometime(P)", "forever(P)", "infinitely(P)", "ultimately(P)",
            "latest x = red. A(x)", "latest x = blue. diamond(A(x))",
            "mu X. P | yesterday(X)", "nu X. P & tomorrow(X)",
            "mu X. !X", "nu X. !X", "mu X. B(X)", "mu X. !tomorrow(X)",
            "mu X. !diamond(P & X)", "mu X. !diamond((P & X) | f)",
            "mu X. (X | (mu X. !X))", "nu X. (X & (mu Y. X | Y))",
        )))
        rng = random.Random(386)
        for time in ("finite", "stutter"):
            for iteration in range(3):
                evaluator = make_evaluator(stages=2, time=time, quorums=({0}, {1}, {0, 1}))
                evaluator = Evaluator(evaluator.theory, evaluator.frame,
                                      {key: rng.randrange(3) for key in evaluator.valuation})
                compiler = Compiler(evaluator.theory, evaluator.frame)
                outputs = [(formula, ctx, compiler.eval(formula, ctx))
                           for formula in formulas for ctx in evaluator.frame.contexts]
                for atom, bits in compiler.cells.items():
                    expected = evaluator.valuation[atom]
                    for bit, enabled in zip(bits, (expected >= 1, expected == 2)):
                        compiler.circuit.add_clause(bit if enabled else -bit)
                result = solve(compiler.circuit.nvars, compiler.circuit.clauses)
                self.assertEqual(result.status, "sat", result.reason)

                def enabled(literal):
                    value = result.assignment[abs(literal)]
                    return value if literal > 0 else not value

                for formula, ctx, bits in outputs:
                    with self.subTest(time=time, iteration=iteration, formula=str(formula), context=ctx):
                        concrete = evaluator.eval(formula, ctx)
                        compiled = int(enabled(bits[0])) + int(enabled(bits[1]))
                        self.assertEqual(concrete, compiled)


if __name__ == "__main__":
    unittest.main()
