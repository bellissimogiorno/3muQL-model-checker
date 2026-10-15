"""Public-process regressions found during the independent release audit."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AuditCommandLineTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "muql", *map(str, arguments)],
            cwd=ROOT, text=True, capture_output=True, timeout=30,
        )

    def test_replay_budget_can_match_check_and_exhaustion_is_incomplete(self):
        # Negated box makes the fixed-point body nonmonotone and requires
        # both point contexts. Its pre-fixed meet is b, so T(...) is false.
        with tempfile.TemporaryDirectory() as directory:
            theory = Path(directory) / "recurrence.md"
            theory.write_text(
                "```muql\npoints a b\nvalues unit\nstages 1\n"
                "quorums {a,b}\nproperty Goal: T(mu X. !box(X))\n```\n",
                encoding="utf-8",
            )
            witnesses = Path(directory) / "witnesses"
            checked = self.run_cli(
                "check", theory, "--max-mu-contexts", "2",
                "--countermodels", witnesses, "--json", "-",
            )
            self.assertEqual(checked.returncode, 1, checked.stderr)
            self.assertEqual(
                json.loads(checked.stdout)["properties"][0]["status"],
                "counterexample",
            )
            witness = witnesses / "01-Goal.json"
            limited = self.run_cli(
                "replay", theory, witness, "--max-mu-contexts", "1",
            )
            self.assertEqual(limited.returncode, 3, limited.stderr)
            self.assertIn("replay incomplete", limited.stderr)
            self.assertNotIn("VALIDATED", limited.stdout)
            replayed = self.run_cli(
                "replay", theory, witness, "--max-mu-contexts", "2",
            )
            self.assertEqual(replayed.returncode, 0, replayed.stderr)
            self.assertIn("VALIDATED", replayed.stdout)

    def test_invalid_replay_budget_is_a_usage_error(self):
        for limit in ("0", "-1", "nan", "1.5"):
            with self.subTest(limit=limit):
                result = self.run_cli(
                    "replay", "unused.md", "unused.json",
                    "--max-mu-contexts", limit,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("positive integer", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
