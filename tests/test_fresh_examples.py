"""Exhaustive Voting oracle transcribed directly from the paper's truth tables.

Enumerate all 3**8 valuations in the shipped four-participant scope without
using the parser, compiler, evaluator, SAT solver, or stored reports for the
expected outcomes. Compare every reported witness with the same direct rules.
"""

from itertools import combinations, product
from pathlib import Path
import unittest

from muql import check, load


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
FALSE, BROKEN, TRUE = range(3)
WEAK = ((TRUE, TRUE, TRUE), (BROKEN, BROKEN, TRUE), (FALSE, BROKEN, TRUE))
STRONG = ((TRUE, TRUE, TRUE), (BROKEN, BROKEN, TRUE), (FALSE, FALSE, TRUE))
QUORUMS = tuple(combinations(range(4), 3))


def voting_truths(votes, observations, *, drop_correct=False, weak_forward=False):
    """Figure 3, Proposition 2.5.7, and the two explicit forward consequences."""
    positive = max(min(votes[p] for p in quorum) for quorum in QUORUMS)
    negative = max(min(TRUE - votes[p] for p in quorum) for quorum in QUORUMS)
    correct = any(all(votes[p] != BROKEN for p in quorum) for quorum in QUORUMS)
    forward = WEAK if weak_forward else STRONG
    valid = (drop_correct or correct) and all(
        min(WEAK[observed][positive], WEAK[TRUE - observed][negative],
            forward[positive][observed], forward[negative][TRUE - observed]) != FALSE
        for observed in observations
    )
    properties = {
        "Agreement": FALSE if TRUE in observations and FALSE in observations else TRUE,
        "UnanimousTrueDelivery": STRONG[positive][min(observations)],
        "UnanimousFalseDelivery": STRONG[negative][min(TRUE - x for x in observations)],
    }
    return valid, properties


class FreshExampleTests(unittest.TestCase):
    def test_voting_and_its_mutations_against_every_possible_valuation(self):
        original = load(EXAMPLES / "voting.md")
        variations = (
            (original, {}),
            (original.without("Correct"), {"drop_correct": True}),
            (original.replace("ObserveForward", "quorum(vote()) -> observe()")
             .replace("ObserveNotForward", "quorum(!vote()) -> !observe()"),
             {"weak_forward": True}),
        )
        for theory, options in variations:
            with self.subTest(options=options):
                models = []
                for cells in product(range(3), repeat=8):
                    valid, properties = voting_truths(cells[:4], cells[4:], **options)
                    if valid:
                        models.append(properties)
                self.assertTrue(models)
                expected = {
                    name: "counterexample" if any(m[name] == FALSE for m in models) else "holds"
                    for name in ("Agreement", "UnanimousTrueDelivery", "UnanimousFalseDelivery")
                }
                report = check(theory)
                self.assertEqual(report.status, "checked", report.reason)
                self.assertEqual({result.name: result.status for result in report.properties}, expected)

                def direct_witness(rows):
                    cells = {(row["predicate"], row["point"]):
                             {"f": FALSE, "b": BROKEN, "t": TRUE}[row["value"]]
                             for row in rows}
                    self.assertEqual(len(cells), 8)
                    votes = tuple(cells["vote", point] for point in theory.points)
                    observed = tuple(cells["observe", point] for point in theory.points)
                    return voting_truths(votes, observed, **options)

                self.assertTrue(direct_witness(report.consistency_model)[0])
                for result in report.properties:
                    if result.countermodel is not None:
                        valid, properties = direct_witness(result.countermodel.valuation)
                        self.assertTrue(valid)
                        self.assertEqual(properties[result.name], FALSE)


if __name__ == "__main__":
    unittest.main()
