"""Installed browser launch: safe package data, loopback HTTP and cleanup."""

import contextlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener
import zipfile

from muql import cli, server


ROOT = Path(__file__).resolve().parents[1]


def write_site(package, *, version=None, extras=(), omit=()):
    """A deliberately tiny site: validation never relies on generated output."""
    files = {
        "index.html": "<!doctype html><title>Installed explorer</title>",
        "config.json": json.dumps({"version": server.__version__ if version is None else version,
                                   "engine": "engine.zip", "pyodide": "https://example.invalid/"}),
        "engine.zip": b"test engine archive",
        "app.js": "export const test = true;\n",
        "examples/demo.md": "# Public example\n",
    }
    with zipfile.ZipFile(package / "_site.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            if name not in omit:
                archive.writestr(name, content)
        for name, content in extras:
            archive.writestr(name, content)
    return files


class BundledSiteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.package = Path(self.temporary.name)
        self.patch = patch.object(server.resources, "files", return_value=self.package)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_resources_are_extracted_and_removed_on_normal_and_exceptional_exit(self):
        write_site(self.package)
        for fail in (False, True):
            with self.subTest(fail=fail):
                try:
                    with server.bundled_site() as site:
                        self.assertTrue((site / "index.html").is_file())
                        self.assertEqual((site / "examples/demo.md").read_text(), "# Public example\n")
                        self.assertNotEqual(site, self.package)
                        if fail:
                            raise RuntimeError("consumer failed")
                except RuntimeError:
                    self.assertTrue(fail)
                self.assertFalse(site.exists())
        server.resources.files.assert_called_with("muql")

    def test_missing_archive_has_actionable_error_without_server_start(self):
        with patch.object(server, "ThreadingHTTPServer") as http, contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(server.serve(), 1)
        self.assertIn("bundled browser site is missing", output.getvalue())
        self.assertIn("complete release", output.getvalue())
        http.assert_not_called()

    def test_invalid_archive_is_reported_without_traceback(self):
        (self.package / "_site.zip").write_bytes(b"not a zip file")
        with contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(server.serve(), 1)
        self.assertIn("cannot be read", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_version_mismatch_and_missing_required_assets_fail(self):
        for options, expected in [({"version": "0.0.0"}, "does not match installed version"),
                                  ({"omit": ("index.html",)}, "no index.html"),
                                  ({"omit": ("config.json",)}, "no readable config.json")]:
            with self.subTest(options=options):
                write_site(self.package, **options)
                with self.assertRaisesRegex(server.SiteError, expected), server.bundled_site():
                    self.fail("Invalid site was accepted")

    def test_bad_configuration_shapes_are_rejected(self):
        for content in ["not json", "[]", "null", '{"version": 7}', '{"version": "0.0.0"}']:
            with self.subTest(content=content):
                write_site(self.package, omit=("config.json",), extras=[("config.json", content)])
                with self.assertRaises(server.SiteError), server.bundled_site():
                    self.fail("Invalid site was accepted")

    def test_unsafe_archive_members_are_rejected_before_any_extraction(self):
        names = ["../escape", "/escape", "folder/../../escape", "folder\\escape",
                 "C:/escape", "file:stream", "a//b", "./file", "folder/./file",
                 "folder/../file", "file.", "file ", "CON", "nul.txt", "folder/LPT1.md"]
        for name in names:
            with self.subTest(name=name):
                write_site(self.package, extras=[(name, "unsafe")])
                with patch.object(zipfile.ZipFile, "open", side_effect=AssertionError("Extraction started")):
                    with self.assertRaisesRegex(server.SiteError, "unsafe archive entry"), server.bundled_site():
                        self.fail("Unsafe site was accepted")

    def test_symlinks_and_special_files_are_rejected(self):
        for mode in [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR]:
            with self.subTest(mode=mode):
                info = zipfile.ZipInfo("shortcut")
                info.create_system = 3
                info.external_attr = (mode | 0o777) << 16
                write_site(self.package, extras=[(info, "../../private")])
                with self.assertRaisesRegex(server.SiteError, "unsafe archive entry"), server.bundled_site():
                    self.fail("Unsafe site was accepted")

    def test_duplicate_case_alias_and_file_directory_conflict_are_rejected(self):
        for extras in [[("INDEX.HTML", "collision")], [("assets", "file"), ("assets/app.js", "child")]]:
            with self.subTest(extras=extras):
                write_site(self.package, extras=extras)
                with self.assertRaisesRegex(server.SiteError, "duplicate|conflicting"), server.bundled_site():
                    self.fail("Ambiguous site was accepted")

    def test_real_http_serves_public_assets_and_never_exposes_source(self):
        files = write_site(self.package)
        (self.package / "secret.txt").write_text("Private package sibling")
        opener = build_opener(ProxyHandler({}))
        with server.bundled_site() as site:
            from functools import partial
            with server.ThreadingHTTPServer(("127.0.0.1", 0), partial(server.SiteHandler, directory=str(site))) as http:
                thread = threading.Thread(target=http.serve_forever, daemon=True)
                thread.start()
                url = f"http://127.0.0.1:{http.server_port}/"
                try:
                    for path, expected in [("", files["index.html"]), ("app.js", files["app.js"]),
                                           ("engine.zip", files["engine.zip"]), ("examples/demo.md", files["examples/demo.md"])]:
                        with self.subTest(path=path), opener.open(url + path, timeout=5) as response:
                            self.assertEqual(response.read(), expected.encode() if isinstance(expected, str) else expected)
                            self.assertEqual(response.headers["Cache-Control"], "no-store")
                    for path in ["secret.txt", "server.py", "muql/server.py", "../secret.txt",
                                 "%2e%2e/secret.txt", "examples/", "_site.zip"]:
                        with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                            opener.open(url + path, timeout=5)
                        self.assertEqual(error.exception.code, 404)
                        error.exception.close()
                finally:
                    http.shutdown()
                    thread.join(timeout=5)
        self.assertFalse(site.exists())

    def test_busy_port_reports_a_free_port_option_and_cleans_up(self):
        write_site(self.package)
        with server.ThreadingHTTPServer(("127.0.0.1", 0), server.SiteHandler) as occupied:
            with contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(server.serve(occupied.server_port), 1)
        self.assertIn("--port 0", output.getvalue())

    def test_browser_failure_and_interrupt_close_server_and_remove_site(self):
        write_site(self.package)
        for result in [False, server.webbrowser.Error("not available"), OSError("not available")]:
            with self.subTest(result=result), patch.object(server, "ThreadingHTTPServer") as factory, \
                    patch.object(server.webbrowser, "open") as browser, contextlib.redirect_stdout(io.StringIO()) as output:
                if isinstance(result, Exception):
                    browser.side_effect = result
                else:
                    browser.return_value = result
                http = factory.return_value
                http.server_address = ("127.0.0.1", 8123)
                http.serve_forever.side_effect = KeyboardInterrupt
                self.assertEqual(server.serve(open_browser=True), 0)
                self.assertEqual(factory.call_args.args[0], ("127.0.0.1", 8000))
                site = Path(factory.call_args.args[1].keywords["directory"])
                self.assertFalse(site.exists())
                browser.assert_called_once_with("http://127.0.0.1:8123/")
                http.__exit__.assert_called_once()
                self.assertIn("Open the address above", output.getvalue())
                self.assertIn("Local explorer stopped", output.getvalue())


class InstalledServeCommandTests(unittest.TestCase):
    def test_cli_dispatch_preserves_arguments_and_exit_status(self):
        with patch.object(server, "serve", return_value=7) as run:
            self.assertEqual(cli.main(["serve", "--port", "0", "--open"]), 7)
            run.assert_called_once_with(port=0, open_browser=True)
        with patch.object(server, "serve", return_value=0) as run:
            self.assertEqual(cli.main(["serve"]), 0)
            run.assert_called_once_with(port=8000, open_browser=False)

    def test_invalid_ports_fail_before_site_access(self):
        for value in ["-1", "65536", "1.5", "bad", "", "99999999999999999999999999"]:
            with self.subTest(value=value), patch.object(server, "serve") as run, \
                    contextlib.redirect_stderr(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as error:
                    cli.main(["serve", "--port=" + value])
                self.assertEqual(error.exception.code, 2)
                self.assertIn("0 to 65535", output.getvalue())
                run.assert_not_called()
        for value in [-1, 65536, 1.5, "8000", True]:
            with self.subTest(direct=value), patch.object(server.resources, "files") as files, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(server.serve(value), 2)
                files.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "Process SIGINT cleanup uses POSIX signal delivery")
    def test_module_launch_from_unrelated_directory_leaves_no_files_and_cleans_temporary_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installation = root / "installed package with spaces"
            installation.mkdir()
            shutil.copytree(ROOT / "muql", installation / "muql",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_site.zip"))
            files = write_site(installation / "muql")
            cwd = root / "unrelated directory"
            cwd.mkdir()
            temporary_sites = root / "runtime temporary files"
            temporary_sites.mkdir()
            env = {**os.environ, "PYTHONPATH": str(installation), "PYTHONDONTWRITEBYTECODE": "1",
                   "TMPDIR": str(temporary_sites), "TEMP": str(temporary_sites), "TMP": str(temporary_sites)}
            with (root / "server.log").open("w+") as log:
                process = subprocess.Popen([sys.executable, "-m", "muql", "serve", "--port", "0"],
                                           cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 10
                    match = None
                    while time.monotonic() < deadline:
                        log.seek(0)
                        text = log.read()
                        match = re.search(r"Open (http://127\.0\.0\.1:\d+/)", text)
                        if match or process.poll() is not None:
                            break
                        time.sleep(0.03)
                    self.assertIsNotNone(match, text)
                    opener = build_opener(ProxyHandler({}))
                    with opener.open(match.group(1), timeout=5) as response:
                        self.assertEqual(response.read(), files["index.html"].encode())
                    self.assertEqual(len(list(temporary_sites.iterdir())), 1)
                    process.send_signal(signal.SIGINT)
                    self.assertEqual(process.wait(timeout=5), 0)
                    self.assertEqual(list(cwd.iterdir()), [])
                    self.assertEqual(list(temporary_sites.iterdir()), [])
                    log.seek(0)
                    self.assertIn("Local explorer stopped", log.read())
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
