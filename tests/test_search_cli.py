"""Real command-line searches, bounded outcomes and reproducible exports."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ONE_FRAME = (
    "--max-points", "1", "--max-values", "1", "--max-stages", "1",
    "--max-quorums", "1", "--solver", "builtin",
)


class SearchCommandLineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write_theory(self, body):
        path = self.root / "input.md"
        path.write_text("```muql\n" + body + "\n```\n", encoding="utf-8")
        return path

    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "muql", *map(str, arguments)],
            cwd=ROOT, text=True, capture_output=True, timeout=30,
        )

    def test_unscoped_listing_and_search_do_not_make_check_accept_missing_scope(self):
        path = self.write_theory("property Always: t")
        listed = self.run_cli("list", path)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("Search template: no fixed scope", listed.stdout)
        checked = self.run_cli("check", path)
        self.assertEqual(checked.returncode, 2)
        self.assertNotIn("Traceback", checked.stderr)
        searched = self.run_cli("search", path, *ONE_FRAME, "--json", "-")
        self.assertEqual(searched.returncode, 0, searched.stderr)
        report = json.loads(searched.stdout)
        self.assertEqual(report["schema"], "muql-search-report-v1")
        self.assertTrue(report["complete"])
        self.assertEqual(report["properties"][0]["status"], "holds")
        self.assertEqual(report["stats"]["frames"], 1)
        human = self.run_cli("search", path, *ONE_FRAME)
        self.assertEqual(human.returncode, 0, human.stderr)
        self.assertIn("HOLDS WITHIN SEARCH BOUNDS", human.stdout)
        self.assertIn("not unbounded proofs", human.stdout)

    def test_search_can_find_a_larger_scope_than_the_input_example(self):
        path = self.write_theory(
            "points alice\nvalues unit\nstages 1\nquorums {alice}\n"
            "predicate P/0\nproperty Global: P -> everywhere(P)"
        )
        fixed = self.run_cli("check", path, "--solver", "builtin", "--json", "-")
        self.assertEqual(fixed.returncode, 0, fixed.stderr)
        searched = self.run_cli(
            "search", path, *ONE_FRAME, "--max-points", "2",
            "--json", "-",
        )
        self.assertEqual(searched.returncode, 1, searched.stderr)
        report = json.loads(searched.stdout)
        result = report["properties"][0]
        self.assertEqual(result["status"], "counterexample")
        self.assertEqual(len(result["countermodel"]["scope"]["points"]), 2)

    def test_exported_theory_preserves_edits_and_replays_without_extra_flags(self):
        path = self.write_theory(
            "predicate P/0\naxiom Required: P\nproperty Delivery: P"
        )
        for edit in (("--drop", "Required"), ("--replace", "Required=TF(P)")):
            with self.subTest(edit=edit):
                directory = self.root / edit[0][2:]
                process = self.run_cli(
                    "search", path, *ONE_FRAME, *edit,
                    "--countermodels", directory, "--json", "-",
                )
                self.assertEqual(process.returncode, 1, process.stderr)
                self.assertEqual(json.loads(process.stdout)["properties"][0]["status"], "counterexample")
                witness = directory / "01-Delivery.json"
                concrete = directory / "01-Delivery.md"
                self.assertTrue((directory / "01-Delivery.txt").is_file())
                self.assertTrue(witness.is_file())
                self.assertTrue(concrete.is_file())
                replayed = self.run_cli("replay", concrete, witness)
                self.assertEqual(replayed.returncode, 0, replayed.stderr)
                self.assertIn("VALIDATED", replayed.stdout)

    def test_frame_cap_keeps_counterexamples_but_reports_incomplete_exit(self):
        path = self.write_theory("property Always: t\nproperty FalseClaim: f")
        process = self.run_cli(
            "search", path, *ONE_FRAME, "--max-points", "2",
            "--max-frames", "1", "--json", "-",
        )
        self.assertEqual(process.returncode, 3, process.stderr)
        report = json.loads(process.stdout)
        self.assertFalse(report["complete"])
        self.assertEqual(report["status"], "unknown")
        self.assertEqual(
            {result["name"]: result["status"] for result in report["properties"]},
            {"Always": "unknown", "FalseClaim": "counterexample"},
        )

    def test_all_inconsistent_frames_do_not_prove_properties(self):
        path = self.write_theory("axiom Impossible: f\nproperty Always: t")
        process = self.run_cli("search", path, *ONE_FRAME, "--json", "-")
        self.assertEqual(process.returncode, 2, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report["status"], "inconsistent")
        self.assertFalse(any(result["status"] == "holds" for result in report["properties"]))

    def test_no_properties_searches_for_an_axiom_model(self):
        path = self.write_theory("predicate P/0\naxiom Required: T(P)")
        process = self.run_cli("search", path, *ONE_FRAME, "--json", "-")
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report["status"], "satisfiable")
        self.assertTrue(report["consistency_model"])
        self.assertTrue(report["consistency_scope"])
        self.assertFalse(report["properties"])

    def test_bound_and_property_errors_are_diagnostics(self):
        path = self.write_theory("property Always: t")
        for option in ("--max-points", "--max-values", "--max-stages", "--max-quorums", "--max-frames"):
            with self.subTest(option=option):
                result = self.run_cli("search", path, option, "0")
                self.assertEqual(result.returncode, 2)
                self.assertIn("positive integer", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        missing = self.run_cli("search", path, *ONE_FRAME, "--property", "Typo")
        self.assertEqual(missing.returncode, 2)
        self.assertIn("Typo", missing.stderr)
        self.assertNotIn("Traceback", missing.stderr)


if __name__ == "__main__":
    unittest.main()
