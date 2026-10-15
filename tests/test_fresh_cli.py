"""Fresh process-boundary regressions: lossless JSON on limited terminals."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FreshCommandLineTests(unittest.TestCase):
    def test_human_output_preserves_outcomes_on_an_ascii_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unicode.md"
            path.write_text(
                '```muql\ntheory "Théorie α"\npoints "α"\nvalues "β"\n'
                'stages 1\nquorums {"α"}\npredicate P/1\n'
                'property Holds: t\nproperty Refuted: P("β")\n```\n',
                encoding="utf-8",
            )
            environment = {**os.environ, "PYTHONIOENCODING": "ascii"}
            listed = subprocess.run(
                [sys.executable, "-m", "muql", "list", str(path)], cwd=ROOT,
                capture_output=True, timeout=30, env=environment,
            )
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn(b"Th\\xe9orie \\u03b1", listed.stdout)
            self.assertIn(b"Points: \\u03b1", listed.stdout)
            self.assertIn(b"P('\\u03b2')", listed.stdout)
            for command in ("check", "search"):
                bounds = ("--max-points", "1", "--max-values", "1",
                          "--max-stages", "1", "--solver", "builtin") if command == "search" else ()
                for name, limits, code, status in (
                    ("Holds", (), 0, "HOLDS"),
                    ("Refuted", (), 1, "COUNTEREXAMPLE"),
                    ("Refuted", ("--max-nodes", "1"), 3, "UNKNOWN"),
                ):
                    with self.subTest(command=command, status=status):
                        process = subprocess.run(
                            [sys.executable, "-m", "muql", command, str(path),
                             *bounds, "--property", name, *limits], cwd=ROOT,
                            capture_output=True, timeout=30, env=environment,
                        )
                        self.assertEqual(process.returncode, code, process.stderr)
                        self.assertEqual(process.stderr, b"")
                        output = process.stdout.decode("ascii")
                        self.assertIn("Th\\xe9orie \\u03b1", output)
                        self.assertIn(status, output)

    def test_unicode_json_retains_all_outcomes_on_an_ascii_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unicode.md"
            source = (
                '```muql\ntheory "Théorie α"\npoints "α"\nvalues "β"\n'
                'stages 1\nquorums {"α"}\npredicate P/1\n'
                'property Holds: P("β") ∨ ¬P("β")\n'
                'property Refuted: P("β")\n```\n'
            )
            path.write_text(source, encoding="utf-8")
            for command in ("check", "search"):
                bounds = ("--max-points", "1", "--max-values", "1",
                          "--max-stages", "1", "--solver", "builtin") if command == "search" else ()
                for name, limits, code, status in (
                    ("Holds", (), 0, "holds"),
                    ("Refuted", (), 1, "counterexample"),
                    ("Refuted", ("--max-nodes", "1"), 3, "unknown"),
                ):
                    with self.subTest(command=command, status=status):
                        exports = Path(directory) / command
                        process = subprocess.run(
                            [sys.executable, "-m", "muql", command, str(path),
                             *bounds, "--property", name, *limits, "--json", "-",
                             "--countermodels", str(exports)],
                            cwd=ROOT, capture_output=True, timeout=30,
                            env={**os.environ, "PYTHONIOENCODING": "ascii"},
                        )
                        self.assertEqual(process.returncode, code, process.stderr)
                        self.assertEqual(process.stderr, b"")
                        # Parse bytes exactly as an ASCII-only consumer does.
                        report = json.loads(process.stdout.decode("ascii"))
                        self.assertEqual(report["theory"], "Théorie α")
                        self.assertEqual(report["properties"][0]["status"], status)
                        if command == "check":
                            self.assertEqual(report["scope"]["points"], ["α"])
                            self.assertEqual(report["scope"]["values"], ["β"])
                        else:
                            self.assertEqual(report["bounds"]["named_values"], ["β"])
                        if status == "counterexample":
                            witness = report["properties"][0]["countermodel"]
                            self.assertEqual(witness["valuation"][0]["args"], ["β"])
                            witness_path = Path(directory) / "witness.json"
                            witness_path.write_text(json.dumps(witness), encoding="utf-8")
                            concrete = exports / "01-Refuted.md" if command == "search" else path
                            replayed = subprocess.run(
                                [sys.executable, "-m", "muql", "replay", str(concrete),
                                 str(witness_path)], cwd=ROOT, capture_output=True,
                                timeout=30,
                            )
                            self.assertEqual(replayed.returncode, 0, replayed.stderr)

    def test_utf8_stdout_keeps_readable_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unicode.md"
            path.write_text(
                '```muql\ntheory "Théorie"\npoints "α"\nvalues "β"\n'
                'stages 1\nquorums {"α"}\nproperty Holds: t\n```\n',
                encoding="utf-8",
            )
            process = subprocess.run(
                [sys.executable, "-m", "muql", "check", str(path), "--json", "-"],
                cwd=ROOT, capture_output=True, timeout=30,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            text = process.stdout.decode("utf-8")
            self.assertIn('"theory": "Théorie"', text)
            self.assertIn('"α"', text)
            self.assertEqual(json.loads(text)["scope"]["values"], ["β"])


if __name__ == "__main__":
    unittest.main()
