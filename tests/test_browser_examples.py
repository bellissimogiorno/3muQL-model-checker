"""The browser's shipped presets reproduce the documented desktop outcomes.

Expected property results are explicit fixtures, not computed by another call
to the checker. This also exercises the page's actual example catalog, source
files, and initial resource controls through its Python JSON boundary.
"""

from html.parser import HTMLParser
import json
from pathlib import Path
import unittest

from muql.theory import loads
from muql.web import handle_json


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "choices": ("counterexample", {"AtMostOne": "counterexample"}),
    "voting": ("complete", {
        "Agreement": "holds", "UnanimousTrueDelivery": "holds",
        "UnanimousFalseDelivery": "holds",
    }),
    "voting-without-correct": ("counterexample", {"Agreement": "counterexample"}),
    "paxos": ("complete", {"Agreement": "holds"}),
    "paxos-without-write": ("counterexample", {"Agreement": "counterexample"}),
    "basics": ("checked", {
        "BrokenIsDesignated": "holds", "BrokenIsTrue": "counterexample",
        "ExcludedMiddle": "holds", "CrispExcludedMiddle": "counterexample",
        "WeakDefinition": "holds", "StrongDefinition": "holds",
        "WeakCurrying": "holds", "StrongCurrying": "counterexample",
        "DesignatedUnique": "holds", "UniqueIsCrisp": "counterexample",
        "TrueWitness": "counterexample", "AtMostOneActuallyTrue": "holds",
    }),
    "semitopology": ("checked", {
        "SomewhereDefinition": "holds", "EverywhereDefinition": "holds",
        "QuorumDefinition": "holds", "ContraDefinition": "holds",
        "LocalJoinBelowGlobalJoin": "holds", "GlobalMeetBelowLocalMeet": "holds",
        "PairwiseIntersection": "holds", "TripleIntersection": "holds",
        "CurrentBoxIsGlobal": "counterexample", "SharedPointAgreement": "holds",
    }),
    "fixedpoints": ("checked", {
        "InclusivePast": "holds", "StrictPast": "holds", "StrictFuture": "holds",
        "FutureGreatest": "holds", "EmptyPastRecurrence": "holds",
        "NonmonotoneMeet": "holds", "UnfoldingRequiresMonotonicity": "counterexample",
        "NegationMeet": "holds",
    }),
    "paxos-full": ("checked", {
        "Validity": "holds", "Agreement": "holds", "Termination": "holds",
        "DecidingQuorum": "holds",
    }),
    "bracha": ("checked", {
        "BrValidity": "holds", "BrNoDup": "holds", "BrIntegrity": "holds",
        "BrConsistency": "holds", "BrTotality": "holds",
    }),
    "crusader": ("checked", {
        "CaAgree": "holds", "CaValid1": "holds", "CaValid2": "holds", "CaLive": "holds",
    }),
}


class _InitialLimits(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag != "input" or attributes.get("type") != "number":
            return
        self.values[attributes["id"].replace("-", "_")] = int(attributes["value"])


class BrowserExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = json.loads((ROOT / "web/examples.json").read_text(encoding="utf-8"))
        parser = _InitialLimits()
        parser.feed((ROOT / "web/index.html").read_text(encoding="utf-8"))
        cls.limits = parser.values

    def test_catalog_has_distinct_presets_and_valid_tour_links(self):
        identifiers = [example["id"] for example in self.examples]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(set(identifiers), set(EXPECTED))
        for example in self.examples:
            with self.subTest(example=example["id"]):
                self.assertTrue(example["title"])
                self.assertTrue(example["description"])
                self.assertIn(example["mode"], ("check", "search"))
                path = (ROOT / example["file"]).resolve()
                self.assertIn(ROOT, path.parents)
                self.assertTrue(path.is_file())
                if "next" in example:
                    self.assertIn(example["next"], identifiers)
                    self.assertNotEqual(example["next"], example["id"])
        # The curated sequence starts at First steps and ends after the final
        # example, where the page offers a separate custom-theory section.
        self.assertEqual(identifiers[0], "choices")
        self.assertEqual(identifiers[-1], "crusader")
        successors = {example["id"]: example.get("next") for example in self.examples}
        visited = []
        current = identifiers[0]
        while current is not None and current not in visited:
            visited.append(current)
            current = successors[current]
        self.assertEqual(visited, identifiers)
        self.assertIsNone(current)

    def test_all_presets_have_their_documented_results_and_downloads(self):
        for example in self.examples:
            with self.subTest(example=example["id"]):
                source = (ROOT / example["file"]).read_text(encoding="utf-8")
                original = loads(source, for_search=True)
                request = {
                    "action": "run", "source": source, "mode": example["mode"],
                    "properties": example.get("properties"), "drop": example.get("drop", []),
                    "limits": {**self.limits, **example.get("bounds", {})}, "solver": "builtin",
                }
                result = json.loads(handle_json(json.dumps(request)))
                self.assertTrue(result["ok"], result)
                report = result["report"]
                expected_status, expected_properties = EXPECTED[example["id"]]
                self.assertEqual(report["status"], expected_status, report.get("reason"))
                self.assertEqual({item["name"]: item["status"] for item in report["properties"]},
                                 expected_properties)
                if expected_status == "complete":
                    self.assertTrue(report["complete"])
                self.assertIsNotNone(report["consistency_model"])
                downloads = {item["name"]: item for item in result["downloads"]}
                self.assertEqual(json.loads(downloads["report"]["content"]), report)
                retained = loads(downloads["theory"]["content"], for_search=True)
                self.assertEqual(retained.axioms,
                                 original.without(*example.get("drop", [])).axioms)
                self.assertEqual(retained.properties, original.properties)
                # In particular, the unscoped choices template retains its
                # value domain and time convention without gaining a frame.
                self.assertEqual(retained.scope_declared, original.scope_declared)
                self.assertEqual(retained.values, original.values)
                self.assertEqual(retained.time, original.time)
                failures = [name for name, status in expected_properties.items()
                            if status == "counterexample"]
                expected_downloads = {"report", "theory"}
                for name in failures:
                    expected_downloads.update((f"witness-{name}-theory", f"witness-{name}-countermodel"))
                self.assertEqual(set(downloads), expected_downloads)


if __name__ == "__main__":
    unittest.main()
