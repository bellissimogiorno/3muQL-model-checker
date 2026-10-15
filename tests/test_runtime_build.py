"""Runtime location, self-contained packaging, and non-destructive validation."""

import contextlib
import io
import json
from pathlib import Path
import unittest

import test_site_build as site_fixture
from tools.build_site import PYODIDE_CORE_FILES, PYODIDE_URL, PYODIDE_VERSION, build


class RuntimeBuildTests(unittest.TestCase):
    setUp = site_fixture.SiteBuildTests.setUp

    def build(self, output=None, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return build(output, root=self.root, **kwargs)

    def runtime(self):
        directory = Path(self.temporary.name) / "pyodide"
        directory.mkdir(exist_ok=True)
        for name in PYODIDE_CORE_FILES:
            (directory / name).write_bytes(b"test runtime asset\n")
        (directory / "pyodide-lock.json").write_text(json.dumps({
            "info": {"version": PYODIDE_VERSION},
            "packages": {},
        }))
        return directory

    def snapshot(self, output):
        return {path.relative_to(output).as_posix(): path.read_bytes()
                for path in output.rglob("*") if path.is_file()}

    def test_default_cdn_and_safe_mirror_urls(self):
        for url, expected in (
            (None, PYODIDE_URL),
            ("https://runtime.example/pyodide", "https://runtime.example/pyodide/"),
            ("https://runtime.example:8443/pyodide/", "https://runtime.example:8443/pyodide/"),
            ("runtime/pyodide", "runtime/pyodide/"),
            ("./runtime/pyodide/", "./runtime/pyodide/"),
        ):
            with self.subTest(url=url):
                output = self.build(pyodide_url=url)
                config = json.loads((output / "config.json").read_text())
                self.assertEqual(config["pyodide"], expected)
                self.assertFalse((output / "runtime").exists())

    def test_unsafe_urls_preserve_previous_output(self):
        output = self.build()
        before = self.snapshot(output)
        for url in (
            "", "http://runtime.example/", "file:///runtime/", "javascript:alert(1)",
            "//runtime.example/", "/runtime/", "../runtime/", "runtime/../pyodide/",
            "runtime/%2e%2e/pyodide/", "%2Fruntime/", "runtime\\pyodide/",
            "runtime/%5cpyodide/", "runtime/%00/", "runtime/%GG/",
            "https://user:password@runtime.example/", "https://@runtime.example/",
            "https://runtime.example/?token=x", "https://runtime.example/#version",
            "https://runtime.example/?", "https://runtime.example/#",
            "https://runtime.example:wrong/", "https:///runtime/", " runtime/",
            "https://runtime.example/\npyodide/",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.build(pyodide_url=url)
            self.assertEqual(self.snapshot(output), before)

    def test_bundled_runtime_uses_project_relative_path_and_keeps_optional_packages(self):
        runtime = self.runtime()
        (runtime / "python_sat-test.whl").write_bytes(b"optional solver package")
        (runtime / "LICENSE").write_text("Runtime license")
        (runtime / "extra").mkdir()
        (runtime / "extra" / "LICENSE").write_text("Optional package license")
        default = self.build()
        engine = (default / "engine.zip").read_bytes()
        output = self.build(pyodide_dir=runtime)
        config = json.loads((output / "config.json").read_text())
        self.assertEqual(config["pyodide"], "runtime/pyodide/")
        for source in runtime.rglob("*"):
            if source.is_file():
                self.assertEqual((output / "runtime/pyodide" / source.relative_to(runtime)).read_bytes(), source.read_bytes())
        self.assertEqual((output / "engine.zip").read_bytes(), engine)
        before = self.snapshot(output)
        self.build(pyodide_dir=runtime, check=True)
        self.assertEqual(self.snapshot(output), before)
        self.build()
        self.assertFalse((output / "runtime").exists(), "Returning to a CDN build must remove obsolete runtime files")

    def test_missing_empty_wrong_version_and_malformed_runtime_preserve_output(self):
        output = self.build()
        before = self.snapshot(output)
        for name in PYODIDE_CORE_FILES:
            runtime = self.runtime()
            (runtime / name).unlink()
            with self.subTest(missing=name), self.assertRaisesRegex(ValueError, "core file"):
                self.build(pyodide_dir=runtime)
            self.assertEqual(self.snapshot(output), before)
            runtime = self.runtime()
            (runtime / name).write_bytes(b"")
            with self.subTest(empty=name), self.assertRaisesRegex(ValueError, "core file"):
                self.build(pyodide_dir=runtime)
            self.assertEqual(self.snapshot(output), before)
        for lock in ("not JSON", "[]", "{}", '{"info":null}', '{"info":{"version":"0.0.0"}}'):
            runtime = self.runtime()
            (runtime / "pyodide-lock.json").write_text(lock)
            with self.subTest(lock=lock), self.assertRaisesRegex(ValueError, "lockfile"):
                self.build(pyodide_dir=runtime)
            self.assertEqual(self.snapshot(output), before)
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.build(pyodide_dir=runtime / "missing")
        self.assertEqual(self.snapshot(output), before)

    def test_runtime_options_are_mutually_exclusive(self):
        output = self.build()
        before = self.snapshot(output)
        with self.assertRaisesRegex(ValueError, "either"):
            self.build(pyodide_url=PYODIDE_URL, pyodide_dir=self.runtime())
        self.assertEqual(self.snapshot(output), before)

    def test_runtime_cannot_overlap_output(self):
        runtime = self.runtime()
        for output in (runtime, runtime / "site"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.build(output, pyodide_dir=runtime)
        output = self.build()
        nested_runtime = output / "runtime/pyodide"
        nested_runtime.mkdir(parents=True)
        before = self.snapshot(output)
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.build(pyodide_dir=nested_runtime)
        self.assertEqual(self.snapshot(output), before)

    def test_runtime_symlinks_and_symlinked_ancestors_are_rejected(self):
        runtime = self.runtime()
        output = self.build()
        before = self.snapshot(output)
        link = runtime / "extra.whl"
        try:
            link.symlink_to(runtime / "pyodide.mjs")
        except (NotImplementedError, OSError):
            self.skipTest("symbolic links are not available")
        with self.assertRaisesRegex(ValueError, "symbolic links"):
            self.build(pyodide_dir=runtime)
        link.unlink()
        link = runtime.parent / "redirect"
        link.symlink_to(runtime, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symbolic links"):
            self.build(pyodide_dir=link)
        (runtime / "nested").mkdir()
        with self.assertRaisesRegex(ValueError, "symbolic links"):
            self.build(pyodide_dir=link / "nested")
        self.assertEqual(self.snapshot(output), before)


if __name__ == "__main__":
    unittest.main()
