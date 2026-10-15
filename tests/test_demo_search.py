"""Run the automatic-search tour and replay the exact artifacts it exports."""

import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

import demo
from muql import load


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SEARCH = {
    "search_choices": {"AtMostOne": "counterexample"},
    "search_voting": {
        "Agreement": "holds",
        "UnanimousTrueDelivery": "holds",
        "UnanimousFalseDelivery": "holds",
    },
    "search_voting_without_correct": {"Agreement": "counterexample"},
    "search_paxos_simpler": {"Agreement": "holds"},
    "search_paxos_simpler_without_write_affine": {"Agreement": "counterexample"},
}


class DemoSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.outside = Path(cls.directory.name)
        cls.output = cls.outside / "results"
        cls.process = subprocess.run(
            [sys.executable, str(ROOT / "demo.py"), "--search-only", "--brief",
             "--output", "results"],
            cwd=cls.outside, text=True, capture_output=True, timeout=60,
        )
        if cls.process.returncode != 0:
            raise AssertionError(
                f"Search tour exited {cls.process.returncode}:\n"
                + cls.process.stdout + cls.process.stderr
            )
        cls.reports = {
            name: json.loads((cls.output / f"{name}.json").read_text(encoding="utf-8"))
            for name in EXPECTED_SEARCH
        }

    def test_real_search_results_match_independent_expectations(self):
        self.assertEqual(len(list(self.output.glob("search_*.json"))), 8)
        for name, expected in EXPECTED_SEARCH.items():
            with self.subTest(scenario=name):
                report = self.reports[name]
                self.assertEqual(report["schema"], "muql-search-report-v1")
                self.assertEqual(
                    {item["name"]: item["status"] for item in report["properties"]},
                    expected,
                )
                self.assertEqual(
                    report["status"],
                    "counterexample" if "counterexample" in expected.values() else "complete",
                )
                self.assertEqual(report["stats"]["solver"], "builtin")
                self.assertGreater(report["stats"]["frames"], 0)
        choice = self.reports["search_choices"]["properties"][0]["countermodel"]
        self.assertEqual(len(choice["scope"]["points"]), 1)
        self.assertEqual(len(choice["scope"]["values"]), 2)
        self.assertEqual(len(choice["valuation"]), 2)
        self.assertTrue(all(cell["value"] == "t" for cell in choice["valuation"]))

    def test_registered_tour_keeps_fixed_examples_and_adds_five_searches(self):
        fixed = demo.fixed_scenarios()
        searches = demo.search_scenarios()
        all_cases = demo.scenarios()
        self.assertEqual(len(fixed), 25)
        self.assertEqual(len(searches), 5)
        self.assertEqual(len(all_cases), 30)
        self.assertEqual({case.key for case in searches}, set(EXPECTED_SEARCH))
        self.assertEqual(len({case.key for case in all_cases}), 30)
        self.assertTrue(all(case.search_bounds is None for case in fixed))
        self.assertTrue(all(case.search_bounds is not None for case in searches))
        self.assertEqual(sum(len(case.expected) for case in all_cases), 81)
        self.assertEqual(sum(
            status == "counterexample"
            for case in all_cases for status in case.expected.values()
        ), 22)

    def test_generated_theories_replay_without_reapplying_mutations(self):
        count = 0
        for name, report in self.reports.items():
            for item in report["properties"]:
                if item["status"] != "counterexample":
                    continue
                count += 1
                stem = f"{name}--{item['name']}"
                concrete = self.output / f"{stem}.md"
                witness = self.output / f"{stem}.countermodel.json"
                self.assertTrue(concrete.is_file(), concrete)
                self.assertEqual(
                    json.loads(witness.read_text(encoding="utf-8")), item["countermodel"],
                )
                theory = load(concrete)
                self.assertTrue(theory.scope_declared)
                if name == "search_voting_without_correct":
                    self.assertNotIn("Correct", theory.axioms)
                if name == "search_paxos_simpler_without_write_affine":
                    self.assertNotIn("SPaxWrite01", theory.axioms)
                lines = [line for line in self.process.stdout.splitlines()
                         if "Replay: " in line and f"{stem}.md" in line]
                self.assertEqual(len(lines), 1, self.process.stdout)
                command = shlex.split(lines[0].split("Replay: ", 1)[1])
                command[0] = sys.executable
                replayed = subprocess.run(
                    command,
                    cwd=ROOT, text=True, capture_output=True, timeout=30,
                )
                self.assertEqual(replayed.returncode, 0, replayed.stderr)
                self.assertIn("VALIDATED", replayed.stdout)
        self.assertEqual(count, 3)

    def test_brief_output_still_exposes_search_commands_and_discovered_scopes(self):
        output = self.process.stdout
        self.assertIn("5 scenarios, 7 property results, 3 countermodels", output)
        self.assertIn("All expected outcomes confirmed.", output)
        self.assertIn("python -m muql search", output)
        self.assertIn("examples/search/choices.md", output)
        self.assertIn("quorums", output.lower())
        self.assertIn("bounds", output.lower())
        self.assertIn("Bounds: 1..1 points; 1..2 values; 1..1 stages;", output)
        self.assertNotIn("0..2 values", output)
        self.assertEqual(output.count("Found scope:"), 3)
        # The complete atom rows belong to the non-brief compact witness.
        self.assertNotIn(
            "Every retained axiom is valid; this complete valuation was independently replayed.",
            output,
        )

    def test_printed_choices_command_reproduces_the_countermodel(self):
        lines = [line for line in self.process.stdout.splitlines()
                 if "python -m muql search" in line and "examples/search/choices.md" in line]
        self.assertEqual(len(lines), 1, self.process.stdout)
        line = lines[0]
        command = shlex.split(line[line.index("python -m muql search"):])
        command[0] = sys.executable
        reproduced = subprocess.run(
            [*command, "--json", "-"], cwd=ROOT,
            text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(reproduced.returncode, 1, reproduced.stderr)
        report = json.loads(reproduced.stdout)
        self.assertEqual(report["properties"][0]["name"], "AtMostOne")
        self.assertEqual(report["properties"][0]["status"], "counterexample")

    def test_unknown_searches_fail_the_tour(self):
        process = subprocess.run(
            [sys.executable, str(ROOT / "demo.py"), "--search-only", "--brief",
             "--timeout", "1e-20"],
            cwd=self.outside, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertIn("UNKNOWN", process.stdout)
        self.assertIn("FAILED scenarios:", process.stdout)
        self.assertNotIn("All expected outcomes confirmed.", process.stdout)
        self.assertNotIn("Traceback", process.stderr)


if __name__ == "__main__":
    unittest.main()
