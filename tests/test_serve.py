"""Bash preview startup, failure handling, and real HTTP from another cwd."""

import contextlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener
import zipfile

from tools import serve_site as serve


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")


class ServeHelperTests(unittest.TestCase):
    def test_build_failure_never_starts_server(self):
        for error in [OSError("unreadable"), ValueError("invalid source"), SyntaxError("invalid version")]:
            with self.subTest(error=error), patch.object(serve, "build", side_effect=error), \
                    patch.object(serve, "ThreadingHTTPServer") as server:
                output = io.StringIO()
                with contextlib.redirect_stderr(output):
                    self.assertEqual(serve.build_preview(), 1)
                self.assertIn("Site build failed:", output.getvalue())
                server.assert_not_called()

    def test_busy_port_has_actionable_error(self):
        # Reserve an actual loopback port rather than mocking a bind failure.
        with serve.ThreadingHTTPServer(("127.0.0.1", 0), serve.PreviewHandler) as occupied:
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                result = serve.serve_preview(occupied.server_port)
            self.assertEqual(result, 1)
            self.assertIn("--port 0", output.getvalue())
            self.assertNotIn("Traceback", output.getvalue())

    def test_browser_failure_still_serves_and_interrupt_closes_socket(self):
        for result in [False, serve.webbrowser.Error("browser unavailable")]:
            with self.subTest(result=result), patch.object(serve, "ThreadingHTTPServer") as factory, \
                    patch.object(serve.webbrowser, "open") as browser:
                if isinstance(result, Exception):
                    browser.side_effect = result
                else:
                    browser.return_value = result
                server = factory.return_value
                server.server_address = ("127.0.0.1", 8123)
                server.serve_forever.side_effect = KeyboardInterrupt
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(serve.serve_preview(open_browser=True), 0)
                self.assertEqual(factory.call_args.args[0], ("127.0.0.1", 8000))
                browser.assert_called_once_with("http://127.0.0.1:8123/")
                server.serve_forever.assert_called_once()
                server.__exit__.assert_called_once()
                self.assertIn("Open the address above", output.getvalue())
                self.assertIn("Local preview stopped", output.getvalue())

    def test_interrupt_during_build_returns_to_launcher_cleanly(self):
        with patch.object(serve, "build", side_effect=KeyboardInterrupt), \
                patch.object(serve, "ThreadingHTTPServer") as server:
            self.assertEqual(serve.build_preview(), 130)
            server.assert_not_called()

    def test_direct_helper_invalid_arguments_point_to_launcher(self):
        for args in [[], ["serve", "-1", "0"], ["serve", "65536", "0"], ["serve", "bad", "0"]]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(serve.main(args), 2)
                self.assertIn("bash serve.sh", output.getvalue())


@unittest.skipUnless(BASH, "The local-preview launcher requires Bash")
class ServeLauncherTests(unittest.TestCase):
    def run_launcher(self, *args, env=None):
        return subprocess.run([BASH, str(ROOT / "serve.sh"), *args],
                              capture_output=True, text=True, timeout=10, env=env)

    def test_invalid_ports_fail_before_build_or_interpreter_check(self):
        for value in ["-1", "65536", "not-a-port", "3.5", "", "999999999999999999999999999999"]:
            with self.subTest(value=value):
                result = self.run_launcher("--python", "/missing/python", "--port=" + value)
                self.assertEqual(result.returncode, 2)
                self.assertIn("port number from 0 to 65535", result.stderr)
                self.assertNotIn("Cannot find Python", result.stderr)

    def test_invalid_options_and_missing_values_fail_before_build(self):
        for args in [["--host", "0.0.0.0"], ["unexpected"], ["--port"], ["--python"],
                     ["--python", "--open"], ["--port", "--open"], ["--python="]]:
            with self.subTest(args=args):
                result = self.run_launcher(*args, env={**os.environ, "PYTHON": "/missing/python"})
                self.assertEqual(result.returncode, 2)
                self.assertIn("--help", result.stderr)
                self.assertNotIn("Cannot find Python", result.stderr)

    def test_help_does_not_require_python(self):
        result = self.run_launcher("--help", env={**os.environ, "PYTHON": "/missing/python"})
        self.assertEqual(result.returncode, 0)
        self.assertIn("--python COMMAND", result.stdout)
        self.assertIn("0 chooses a free port", result.stdout)

    def test_missing_interpreter_has_actionable_error(self):
        missing = "/missing/python with spaces"
        for args, env in [(["--python", missing], None),
                          ([], {**os.environ, "PYTHON": missing})]:
            with self.subTest(args=args):
                result = self.run_launcher(*args, env=env)
                self.assertEqual(result.returncode, 1)
                self.assertIn("Cannot find Python executable: " + missing, result.stderr)
                self.assertIn("--python /path/to/python3", result.stderr)

    def test_unusable_interpreter_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "not python"
            executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            executable.chmod(0o755)
            result = self.run_launcher("--python", str(executable))
            self.assertEqual(result.returncode, 1)
            self.assertIn("must be Python 3.10+", result.stderr)
            self.assertIn("--python", result.stderr)

    def test_failed_or_interrupted_build_does_not_start_server(self):
        # A controlled executable makes failures observable at the Bash boundary.
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "test interpreter"
            for status in [1, 7, 130]:
                with self.subTest(status=status):
                    executable.write_text('#!/bin/sh\n[ "$1" = "-c" ] && exit 0\n'
                                          '[ "$2" = "build" ] || { echo "SERVER STARTED"; exit 99; }\n'
                                          f'exit {status}\n', encoding="utf-8")
                    executable.chmod(0o755)
                    result = self.run_launcher("--python", str(executable))
                    self.assertEqual(result.returncode, 0 if status == 130 else status)
                    self.assertNotIn("SERVER STARTED", result.stdout)
                    if status == 130:
                        self.assertIn("Local preview stopped", result.stdout)

    def test_real_preview_from_another_directory_with_available_interpreters(self):
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            package = cwd / "package with spaces"
            package.mkdir()
            for name in ["serve.sh", "VERSION", "pyproject.toml", "README.md", "LICENSE",
                         "CONTRIBUTING.md", "SOURCES.md"]:
                shutil.copy2(ROOT / name, package / name)
            for name in ["muql", "web", "tools", "examples", "docs", "reports"]:
                shutil.copytree(ROOT / name, package / name,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            spaced_python = cwd / "python with spaces"
            spaced_python.symlink_to(sys.executable)
            clean_env = dict(os.environ)
            clean_env.pop("PYTHON", None)
            commands = [(command, ["--python", command], clean_env)
                        for command in ("python3", "python") if shutil.which(command)]
            if shutil.which("python3"):
                commands.append(("default python3", [], clean_env))
            commands.extend([
                ("path with spaces", ["--python", "./python with spaces"], clean_env),
                ("PYTHON variable", [], {**clean_env, "PYTHON": str(spaced_python)}),
                ("argument overrides PYTHON", ["--python", str(spaced_python)],
                 {**clean_env, "PYTHON": "/missing/python"}),
            ])
            opener = build_opener(ProxyHandler({}))
            for label, args, environment in commands:
                with self.subTest(command=label), (cwd / "preview.log").open("w+") as log:
                    process = subprocess.Popen([BASH, str(package / "serve.sh"), *args, "--port", "000"],
                                               cwd=cwd, env=environment, stdout=log, stderr=subprocess.STDOUT)
                    try:
                        deadline = time.monotonic() + 15
                        address = None
                        while time.monotonic() < deadline:
                            log.seek(0)
                            output = log.read()
                            address = re.search(r"Open (http://127\.0\.0\.1:\d+/)", output)
                            if address or process.poll() is not None:
                                break
                            time.sleep(0.03)
                        self.assertIsNotNone(address, output)
                        url = address.group(1)
                        with opener.open(url, timeout=5) as response:
                            self.assertEqual(response.read(), (package / "web/index.html").read_bytes())
                            self.assertEqual(response.headers["Cache-Control"], "no-store")
                        with opener.open(url + "config.json", timeout=5) as response:
                            self.assertEqual(json.load(response)["version"], (package / "VERSION").read_text().strip())
                        with opener.open(url + "engine.zip", timeout=5) as response:
                            with zipfile.ZipFile(io.BytesIO(response.read())) as engine:
                                self.assertIn("muql/web.py", engine.namelist())
                        for private_file in ["serve.sh", "tools/serve_site.py"]:
                            with self.subTest(private_file=private_file), self.assertRaises(HTTPError) as error:
                                opener.open(url + private_file, timeout=5)
                            self.assertEqual(error.exception.code, 404)
                            error.exception.close()
                        if os.name == "posix":
                            process.send_signal(signal.SIGINT)
                            self.assertEqual(process.wait(timeout=5), 0)
                            log.seek(0)
                            self.assertIn("Local preview stopped", log.read())
                    finally:
                        if process.poll() is None:
                            process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
