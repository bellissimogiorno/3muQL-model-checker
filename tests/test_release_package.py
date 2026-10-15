"""Exercise the portable source/site releases as a recipient would use them.

Builds happen in isolated copies. No generated release data in the checkout is
needed or changed, and these tests require neither setuptools nor a browser.
"""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlsplit
import zipfile

from tools.build_release import prepare, release


ROOT = Path(__file__).resolve().parents[1]


class PortableReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A restricted machine may choose cwd as its system temporary directory.
        # Keep the copy below an explicitly excluded tree to avoid copying itself.
        scratch = ROOT / "dist"
        scratch.mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix="muql-release-tests-", dir=scratch)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.prepared = cls.work / "prepared-source"
        cls.prepared.mkdir()
        # Copy the maintained package inputs, never unrelated working files or
        # another concurrently running test's temporary directory.
        for name in (".github", "docs", "examples", "muql", "reports", "tests", "tools", "web"):
            shutil.copytree(ROOT / name, cls.prepared / name, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "*.pyo", "*.egg-info", "node_modules", "_site.zip", "artifacts"))
        for name in (".gitattributes", ".gitignore", "README.md", "LICENSE", "VERSION", "CHANGELOG.md", "CONTRIBUTING.md",
                     "SOURCES.md", "MANIFEST.in", "pyproject.toml", "demo.py", "serve.sh"):
            shutil.copyfile(ROOT / name, cls.prepared / name)
        with contextlib.redirect_stdout(io.StringIO()):
            prepare(cls.prepared)
        cls.version = (cls.prepared / "VERSION").read_text().strip()

    def setUp(self):
        self.temporary_case = tempfile.TemporaryDirectory(dir=self.work)
        self.addCleanup(self.temporary_case.cleanup)
        self.directory = Path(self.temporary_case.name)
        self.root = self.directory / "source with spaces"
        shutil.copytree(self.prepared, self.root)

    def run_tool(self, root, *args):
        env = {key: value for key, value in os.environ.items()
               if key not in {"PYTHONPATH", "PYTHONHOME"}}
        return subprocess.run([sys.executable, "-B", str(root / "tools/build_release.py"), *args],
                              cwd=self.directory, env=env, text=True, capture_output=True, timeout=60)

    def snapshot(self):
        return {path.relative_to(self.root).as_posix():
                (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
                for path in self.root.rglob("*") if path.is_file()}

    def build_archives(self):
        with contextlib.redirect_stdout(io.StringIO()):
            products = release(self.root, python_distributions=False)
        return {path.name: path for path in products}

    def test_source_archive_retains_pages_installation_and_rebuild_inputs_without_private_files(self):
        private_names = [".env", "private-experiment.md", "credentials.json", "private-notes/secret.txt",
                         "muql/__pycache__/cached.pyc", "tools/stale.egg-info/PKG-INFO",
                         "tests/browser/artifacts/private.png", "node_modules/private.js", "build/stale.py",
                         "tools/.env", "muql/.env", "reports/.private/results.json", ".github/.token",
                         "web/.env", "web/.private/config.json", "docs/.private.md", "examples/.draft.md"]
        for name in private_names:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("PRIVATE TEST SENTINEL\n")
        products = self.build_archives()
        archive_path = products[f"3muql-explorer-{self.version}.zip"]
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            prefix = "3muql-explorer/"
            self.assertTrue(all(name.startswith(prefix) for name in names))
            for name in ["index.html", ".nojekyll", ".gitattributes", ".gitignore", ".github/workflows/pages.yml",
                         ".github/workflows/tests.yml", "site/index.html", "site/.nojekyll",
                         "site/.muql-site-build", "site/engine.zip", "muql/_site.zip", "muql/server.py",
                         "pyproject.toml", "MANIFEST.in", "tools/build_release.py", "tools/test_install.py",
                         "examples/voting.md", "docs/browser.md", "serve.sh"]:
                with self.subTest(required=name):
                    self.assertIn(prefix + name, names)
            for name in private_names:
                with self.subTest(private=name):
                    self.assertNotIn(prefix + name, names)
            self.assertFalse(any("/__pycache__/" in name or name.endswith(".pyc") for name in names))
            launcher = archive.getinfo(prefix + "serve.sh")
            self.assertTrue(stat.S_IMODE(launcher.external_attr >> 16) & stat.S_IXUSR)
            with zipfile.ZipFile(io.BytesIO(archive.read(prefix + "muql/_site.zip"))) as installed:
                self.assertEqual(installed.read("index.html"), archive.read(prefix + "site/index.html"))
                self.assertEqual(installed.read("engine.zip"), archive.read(prefix + "site/engine.zip"))
                for name in [".env", ".private/config.json", "docs/.private.md", "examples/.draft.md"]:
                    self.assertNotIn(name, installed.namelist())
        manifest = json.loads((archive_path.parent / f"release-{self.version}.json").read_text())
        self.assertEqual(set(manifest), set(products))
        for name, path in products.items():
            self.assertEqual(manifest[name]["bytes"], path.stat().st_size)
            self.assertEqual(manifest[name]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_unpacked_source_verifies_and_rebuilds_without_original_checkout(self):
        products = self.build_archives()
        recipient = self.directory / "recipient"
        with zipfile.ZipFile(products[f"3muql-explorer-{self.version}.zip"]) as archive:
            archive.extractall(recipient)
        unpacked = recipient / "3muql-explorer"
        # Renaming the producer makes accidental reliance on its files visible.
        self.root.rename(self.directory / "producer-hidden")
        checked = self.run_tool(unpacked, "--check")
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        installed_before = (unpacked / "muql/_site.zip").read_bytes()
        rebuilt = self.run_tool(unpacked, "--prepare-only")
        self.assertEqual(rebuilt.returncode, 0, rebuilt.stdout + rebuilt.stderr)
        self.assertEqual((unpacked / "muql/_site.zip").read_bytes(), installed_before)
        self.assertIn('url=./site/', (unpacked / "index.html").read_text())

    def test_standalone_site_archive_contains_assets_and_an_independently_runnable_engine(self):
        products = self.build_archives()
        site = self.directory / "standalone-site"
        with zipfile.ZipFile(products[f"3muql-explorer-site-{self.version}.zip"]) as archive:
            self.assertIn("index.html", archive.namelist())
            self.assertIn(".nojekyll", archive.namelist())
            self.assertNotIn("pyproject.toml", archive.namelist())
            archive.extractall(site)
        config = json.loads((site / "config.json").read_text())
        self.assertEqual(config["version"], self.version)
        self.assertFalse(urlsplit(config["engine"]).scheme)
        self.assertTrue((site / config["engine"]).is_file())
        examples = json.loads((site / config["examples"]).read_text())
        for example in examples:
            self.assertTrue((site / example["file"]).is_file(), example)
        for name in ["worker.js", "app.js", "style.css", "notation.css", "quorum-superscript.woff", "theories.html"]:
            self.assertTrue((site / name).is_file(), name)
        self.root.rename(self.directory / "producer-hidden")
        script = """import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
import muql
from muql.web import handle_json
request = {"action": "run", "mode": "check", "solver": "builtin", "properties": ["Agreement"],
           "source": pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")}
result = json.loads(handle_json(json.dumps(request)))
assert result["ok"], result
assert result["report"]["properties"][0]["status"] == "holds", result
print(json.dumps({"version": muql.__version__, "module": muql.__file__, "status": "holds"}))
"""
        result = subprocess.run([sys.executable, "-I", "-B", "-c", script,
                                 str(site / config["engine"]), str(site / "examples/voting.md")],
                                cwd=self.directory, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["version"], self.version)
        self.assertIn(str(site / config["engine"]), summary["module"])

    def test_check_accepts_current_release_and_changes_no_files(self):
        before = self.snapshot()
        result = self.run_tool(self.root, "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_redirected_generated_file_is_rejected_before_preparing_assets(self):
        external = self.directory / "external.txt"
        external.write_bytes(b"Keep this unrelated file\n")
        bundle = self.root / "muql/_site.zip"
        bundle.unlink()
        try:
            bundle.symlink_to(external)
        except (NotImplementedError, OSError):
            self.skipTest("symbolic links are not available")
        # A pending source change makes an accidental early prepare observable.
        with (self.root / "web/app.js").open("ab") as stream:
            stream.write(b"\n// Pending source change\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            prepare(self.root)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(external.read_bytes(), b"Keep this unrelated file\n")

    def test_redirected_release_manifest_is_rejected_before_any_build_writes(self):
        products = self.build_archives()
        external = self.directory / "external.json"
        external.write_bytes(b"Keep this unrelated file\n")
        destination = next(iter(products.values())).parent
        manifest = destination / f"release-{self.version}.json"
        manifest.unlink()
        try:
            manifest.symlink_to(external)
        except (NotImplementedError, OSError):
            self.skipTest("symbolic links are not available")
        with (self.root / "web/app.js").open("ab") as stream:
            stream.write(b"\n// Pending source change\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            self.build_archives()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(external.read_bytes(), b"Keep this unrelated file\n")

    def test_check_detects_stale_source_site_and_install_bundle_without_repairing_them(self):
        for name in ["web/app.js", "site/app.js", "muql/_site.zip", "index.html", ".nojekyll"]:
            with self.subTest(stale=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b"\nSTALE TEST DATA\n")
                try:
                    before = self.snapshot()
                    result = self.run_tool(self.root, "--check")
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("Release build failed", result.stderr)
                    self.assertEqual(self.snapshot(), before)
                finally:
                    path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
