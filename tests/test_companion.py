"""Paper-level regression tests, including a concrete discussion counterexample."""

from dataclasses import replace
from pathlib import Path
import unittest

from muql.checker import check, replay
from muql.evaluate import Evaluator
from muql.frame import Frame
from muql.syntax import parse_formula
from muql.theory import load


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class CompanionExamplesTests(unittest.TestCase):
    def test_original_theories_are_consistent_and_properties_hold_in_scope(self):
        for name, count in (("voting", 3), ("bracha", 5), ("crusader", 4)):
            with self.subTest(theory=name):
                report = check(load(EXAMPLES / f"{name}.md"))
                self.assertEqual(report.status, "checked")
                self.assertIsNotNone(report.consistency_model)
                self.assertEqual(len(report.properties), count)
                self.assertTrue(all(p.status == "holds" for p in report.properties))

    def test_existential_delivery_counterexample_is_found_and_replays(self):
        theory = load(EXAMPLES / "bracha_weakened.md")
        report = check(theory)
        self.assertEqual(report.status, "checked")
        self.assertEqual(len(report.properties), 2)
        for result in report.properties:
            with self.subTest(property=result.name):
                self.assertEqual(result.status, "counterexample")
                self.assertTrue(replay(theory, result.countermodel.to_dict()))

    def test_exact_section_4_3_witness_against_all_retained_axioms(self):
        theory = load(EXAMPLES / "bracha_weakened.md")
        frame = Frame.from_theory(theory)
        valuation = {
            (predicate, 0, 0, (value,)): 2 if value == "red" else 0
            for predicate in ("bcst", "echo", "ready")
            for value in ("red", "blue")
        }
        valuation.update({
            ("dlvr", 0, 0, ("red",)): 0,
            ("dlvr", 0, 0, ("blue",)): 1,
        })
        evaluator = Evaluator(theory, frame, valuation)
        for context in frame.contexts:
            for name, axiom in theory.axioms.items():
                with self.subTest(axiom=name, context=context):
                    expected = 1 if name in {"BrDeliver?", "BrDeliverExistential!"} else 2
                    self.assertEqual(evaluator.eval(axiom, context), expected)
            for name, prop in theory.properties.items():
                with self.subTest(property=name, context=context):
                    self.assertEqual(evaluator.eval(prop, context), 0)

    def test_weak_delivery_preserves_agreement_but_loses_guaranteed_observation(self):
        theory = (
            load(EXAMPLES / "voting.md")
            .replace("Observe!", "quorum(vote()) -> observe()")
            .replace("ObserveNot!", "quorum(!vote()) -> !observe()")
        )
        report = check(theory, properties=["Agreement", "UnanimousTrueDelivery"])
        self.assertEqual(report.status, "checked")
        self.assertEqual(
            {p.name: p.status for p in report.properties},
            {"Agreement": "holds", "UnanimousTrueDelivery": "counterexample"},
        )

    def test_crusader_output_uniqueness_is_an_extra_false_conjecture(self):
        original = load(EXAMPLES / "crusader.md")
        theory = replace(original, properties={
            "OutputUnique": parse_formula("affine v. output(v)"),
            "CaAgree": original.properties["CaAgree"],
        })
        report = check(theory)
        self.assertEqual(report.status, "checked")
        self.assertEqual(
            {p.name: p.status for p in report.properties},
            {"OutputUnique": "counterexample", "CaAgree": "holds"},
        )


if __name__ == "__main__":
    unittest.main()
