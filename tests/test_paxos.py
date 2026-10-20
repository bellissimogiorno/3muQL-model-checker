"""Paxos examples, agreement with crashed participants, and axiom mutations."""

from dataclasses import replace
from itertools import product
from pathlib import Path
import unittest

from muql.checker import check, replay
from muql.evaluate import Evaluator
from muql.frame import Frame
from muql.syntax import parse_formula
from muql.theory import load


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def evaluate_countermodel(theory, witness):
    """Decode serialized cells without trusting their reported axiom values."""
    frame = Frame.from_theory(theory)
    valuation = {
        (row["predicate"], row["time"], frame.points.index(row["point"]), tuple(row["args"])):
        {"f": 0, "b": 1, "t": 2}[row["value"]]
        for row in witness.valuation
    }
    return Evaluator(theory, frame, valuation)


class OriginalPaxosExamplesTests(unittest.TestCase):
    def test_all_six_original_theories_have_expected_scoped_results(self):
        examples = (
            "simple_reliable", "simple_crashes", "simple_eventual",
            "simple_eventual_crashes", "paxos", "paxos_simpler",
        )
        for name in examples:
            with self.subTest(theory=name):
                theory = load(EXAMPLES / f"{name}.md")
                report = check(theory)
                self.assertEqual(report.status, "checked", report.reason)
                self.assertIsNotNone(report.consistency_model)
                expected = {property_name: "holds" for property_name in theory.properties}
                self.assertEqual({result.name: result.status for result in report.properties}, expected)
                for result in report.properties:
                    if result.countermodel is not None:
                        self.assertTrue(replay(theory, result.countermodel))

    def test_original_eventual_theories_are_inconsistent_on_finite_dead_ends(self):
        # At the final dead-end stage, sometime(phi) is false for every phi;
        # consequently every ultimately axiom is false.  Do not call this a
        # proof of any correctness property through vacuous implication.
        for name in ("simple_eventual", "simple_eventual_crashes", "paxos", "paxos_simpler"):
            with self.subTest(theory=name):
                theory = replace(load(EXAMPLES / f"{name}.md"), time="finite")
                report = check(theory, properties=[])
                self.assertEqual(report.status, "inconsistent", report.reason)
                self.assertIsNone(report.consistency_model)
                self.assertEqual(report.properties, [])


class AgreementWithCrashesTests(unittest.TestCase):
    def setUp(self):
        self.theory = replace(
            load(EXAMPLES / "paxos_simpler.md"),
            points=("L", "C"),
            quorums=(("L", "C"),),
            stages=3,
            time="stutter",
        )
        self.frame = Frame.from_theory(self.theory)
        valuation = {
            (predicate, stage, point, arguments): 0
            for predicate, arity in self.theory.predicates.items()
            for stage in range(self.frame.stages)
            for point in range(len(self.frame.points))
            for arguments in product(self.theory.values, repeat=arity)
        }
        for stage in range(self.frame.stages):
            valuation[("leader", stage, 0, ())] = 2
            for predicate in ("propose", "write", "accept", "decide"):
                valuation[(predicate, stage, 0, ("red",))] = 2
            valuation[("accept", stage, 1, ("red",))] = 2
            for value in self.theory.values:
                valuation[("decide", stage, 1, (value,))] = 1
        self.evaluator = Evaluator(self.theory, self.frame, valuation)

    def test_constant_witness_satisfies_all_twelve_original_axioms(self):
        self.assertEqual(len(self.theory.axioms), 12)
        for context in self.frame.contexts:
            for name, axiom in self.theory.axioms.items():
                with self.subTest(axiom=name, context=context):
                    value = self.evaluator.eval(axiom, context)
                    self.assertIn(value, (1, 2))
                    expected = 1 if (
                        name == "SPaxDecide!"
                        or (name == "SPaxDecide?" and context[1] == 1)
                    ) else 2
                    self.assertEqual(value, expected)

    def test_agreement_is_valid_with_a_crashed_follower(self):
        for context in self.frame.contexts:
            with self.subTest(context=context):
                self.assertEqual(self.evaluator.eval(self.theory.properties["Agreement"], context), 1)
                self.assertEqual(self.evaluator.eval(self.theory.properties["Validity"], context), 2 if context[1] == 0 else 1)
                self.assertEqual(self.evaluator.eval(self.theory.properties["Termination"], context), 1)
        for stage, point in product(range(self.frame.stages), range(len(self.frame.points))):
            self.assertNotEqual(self.evaluator.valuation[("decide", stage, point, ("blue",))], 2)



class PaxosMutationTests(unittest.TestCase):
    def test_removing_write_uniqueness_permits_two_true_conflicting_decisions(self):
        theory = load(EXAMPLES / "paxos_simpler.md").without("SPaxWrite01")
        report = check(theory, properties=["Agreement"])
        self.assertEqual(report.status, "checked", report.reason)
        result, = report.properties
        self.assertEqual(result.status, "counterexample", result.reason)
        self.assertTrue(replay(theory, result.countermodel))
        evaluator = evaluate_countermodel(theory, result.countermodel)
        # An Agreement failure requires two true decisions of distinct values.
        conflicts = []
        for red, blue in product(theory.values, repeat=2):
            if red == blue:
                continue
            conflict = parse_formula(
                f"T(past(someQuorumSomePoint(decide({red})))) & T(someQuorumSomePoint(decide({blue})))"
            )
            conflicts.extend(ctx for ctx in evaluator.frame.contexts if evaluator.eval(conflict, ctx) == 2)
        self.assertTrue(conflicts)

    def test_removing_accept_provenance_permits_an_unproposed_true_decision(self):
        theory = load(EXAMPLES / "paxos_simpler.md").without("SPaxAccept?")
        report = check(theory, properties=["Validity"])
        self.assertEqual(report.status, "checked", report.reason)
        result, = report.properties
        self.assertEqual(result.status, "counterexample", result.reason)
        self.assertTrue(replay(theory, result.countermodel))
        evaluator = evaluate_countermodel(theory, result.countermodel)
        unsupported = []
        for value in theory.values:
            formula = parse_formula(
                f"T(decide({value})) & !T(past(someQuorumSomePoint(leader & propose({value}))))"
            )
            unsupported.extend(ctx for ctx in evaluator.frame.contexts if evaluator.eval(formula, ctx) == 2)
        self.assertTrue(unsupported)


if __name__ == "__main__":
    unittest.main()
