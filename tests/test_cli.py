"""Exercise the public process boundary: status codes, JSON, and saved witnesses."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "muql", *map(str, arguments)], cwd=ROOT,
            text=True, capture_output=True, timeout=30,
        )

    def test_canonical_command_help_version_and_errors(self):
        from muql import __version__

        version = self.run_cli("--version")
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(version.stdout.strip(), f"3muql {__version__}")
        help_result = self.run_cli("serve", "--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("usage: 3muql serve", help_result.stdout)
        invalid = self.run_cli("serve", "--port", "65536")
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("3muql serve: error:", invalid.stderr)
        missing = self.run_cli("check", "this-file-does-not-exist.md")
        self.assertEqual(missing.returncode, 2)
        self.assertIn("3muql:", missing.stderr)

    def test_json_stdout_is_parseable_and_success_is_scoped(self):
        process = self.run_cli("check", "examples/voting.md", "--property", "Agreement", "--json", "-")
        self.assertEqual(process.returncode, 0, process.stderr)
        data = json.loads(process.stdout)
        self.assertEqual(data["schema"], "muql-report-v1")
        self.assertEqual(data["properties"][0]["status"], "holds")
        self.assertEqual(data["scope"]["points"], ["alice", "bob", "carol", "dave"])
        self.assertTrue(data["consistency_model"])

    def test_countermodel_export_and_replay_preserve_the_weakening(self):
        with tempfile.TemporaryDirectory() as directory:
            process = self.run_cli("check", "examples/voting.md", "--drop", "Correct", "--property", "Agreement", "--countermodels", directory)
            self.assertEqual(process.returncode, 1, process.stderr)
            witness = Path(directory) / "01-Agreement.json"
            self.assertTrue(witness.exists())
            replay = self.run_cli("replay", "examples/voting.md", witness, "--drop", "Correct")
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertIn("VALIDATED", replay.stdout)
            original = self.run_cli("replay", "examples/voting.md", witness)
            self.assertEqual(original.returncode, 2, original.stderr)

    def test_inconsistent_input_never_reports_property_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inconsistent.md"
            path.write_text("```muql\npoints a\nvalues unit\nstages 1\nquorums {a}\naxiom Impossible: f\nproperty Claim: t\n```\n", encoding="utf-8")
            process = self.run_cli("check", path, "--json", "-")
            self.assertEqual(process.returncode, 2, process.stderr)
            data = json.loads(process.stdout)
            self.assertEqual(data["status"], "inconsistent")
            self.assertFalse(any(item["status"] == "holds" for item in data["properties"]))

    def test_resource_limit_is_unknown_and_misspelling_is_error(self):
        limited = self.run_cli("check", "examples/voting.md", "--max-decisions", "1", "--json", "-")
        self.assertEqual(limited.returncode, 3, limited.stderr)
        self.assertEqual(json.loads(limited.stdout)["status"], "unknown")
        bad = self.run_cli("check", "examples/voting.md", "--drop", "Correctt")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("Correctt", bad.stderr)
        self.assertNotIn("Traceback", bad.stderr)


if __name__ == "__main__":
    unittest.main()
