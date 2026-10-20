#!/usr/bin/env python3
"""Install a wheel offline into a fresh venv and exercise it outside the source.

Usage: python tools/test_install.py dist/releases/muql_explorer-0.7.3-py3-none-any.whl
Uses only the standard library and the pip bundled with Python's venv module.
This tests local installation/HTTP, not browser rendering or WebAssembly.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener
import venv
import zipfile
import io

ROOT = Path(__file__).resolve().parents[1]


def verify(wheel: Path) -> None:
    wheel = wheel.resolve()
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValueError("Supply an existing wheel file")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    with tempfile.TemporaryDirectory(prefix="muql-install-") as temporary:
        work = Path(temporary)
        environment = work / "environment"
        venv.EnvBuilder(with_pip=True).create(environment)
        executable = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        command = environment / ("Scripts/3muql.exe" if os.name == "nt" else "bin/3muql")
        alias = environment / ("Scripts/muql.exe" if os.name == "nt" else "bin/muql")
        cwd = work / "unrelated-directory"
        cwd.mkdir()
        env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
        def run(args, expected=0):
            result = subprocess.run([str(arg) for arg in args], cwd=cwd, text=True,
                                    capture_output=True, timeout=90, env=env)
            print("$ " + " ".join(str(arg) for arg in args))
            print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
            if result.returncode != expected:
                raise AssertionError(f"Expected exit {expected}, got {result.returncode}")
            return result
        run([executable, "-m", "pip", "install", "--no-index", "--no-deps", wheel])
        info = run([executable, "-I", "-c",
                    "import json, muql; print(json.dumps([muql.__version__, muql.__file__]))"])
        installed_version, installed_path = json.loads(info.stdout)
        assert installed_version == version
        assert Path(installed_path).resolve().is_relative_to(environment.resolve())
        for invocation in ([command], [alias], [executable, "-I", "-m", "muql"]):
            assert run([*invocation, "--version"]).stdout.strip() == f"3muql {version}"
            assert "usage: 3muql " in run([*invocation, "--help"]).stdout
            assert "usage: 3muql serve" in run([*invocation, "serve", "--help"]).stdout
        run([alias, "check", ROOT / "examples/voting.md", "--property", "Agreement"])
        run([command, "check", ROOT / "examples/voting.md"])
        output = cwd / "witnesses"
        run([command, "search", ROOT / "examples/search/choices.md", "--property", "AtMostOne",
             "--max-points", "1", "--max-values", "2", "--max-stages", "1",
             "--timeout", "15", "--countermodels", output], expected=1)
        witnesses = list(output.glob("*.json"))
        assert witnesses, "Search did not export a witness"
        for witness in witnesses:
            run([command, "replay", witness.with_suffix(".md"), witness])

        before = sorted(str(path.relative_to(cwd)) for path in cwd.rglob("*"))
        server = subprocess.Popen([str(command), "serve", "--port", "0"],
                                  cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, bufsize=1, env=env)
        lines = queue.Queue()
        def consume():
            for line in server.stdout:
                lines.put(line)
            lines.put(None)
        reader = threading.Thread(target=consume, daemon=True)
        reader.start()
        transcript = []
        try:
            url = None
            while url is None:
                line = lines.get(timeout=30)
                if line is None:
                    raise AssertionError("Server exited before announcing its URL: " + "".join(transcript))
                transcript.append(line)
                print(line, end="")
                match = re.search(r"http://127\.0\.0\.1:\d+/", line)
                if match:
                    url = match[0]
            client = build_opener(ProxyHandler({}))
            def get(name):
                with client.open(url + name, timeout=10) as response:
                    assert response.status == 200
                    assert "no-store" in response.headers.get("Cache-Control", "")
                    return response.read()
            assert b'theory-editor' in get("")
            config = json.loads(get("config.json"))
            assert config["version"] == version
            assert b"loadPyodide" in get("worker.js")
            assert b'from "./progress.js"' in get("app.js")
            assert b"export function readProgress" in get("progress.js")
            assert b"property" in get("examples/voting.md")
            assert get("quorum-superscript.woff")[:4] == b"wOFF"
            assert b"<html" in get("theories.html")
            with zipfile.ZipFile(io.BytesIO(get(config["engine"]))) as engine:
                assert version.encode() in engine.read("muql/__init__.py")
                assert b"def notify(" in engine.read("muql/progress.py")
            for name in ("pyproject.toml", "muql/server.py", "../pyproject.toml"):
                try:
                    client.open(url + name, timeout=10)
                except HTTPError as error:
                    assert error.code == 404
                else:
                    raise AssertionError(f"Installed preview exposed {name}")
            print("Installed browser site: all requested assets returned HTTP 200; source files are not served.")
        finally:
            if server.poll() is None:
                if os.name != "nt":
                    server.send_signal(signal.SIGINT)
                else:
                    server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
                raise AssertionError("Server did not stop")
            reader.join(timeout=2)
            server.stdout.close()
        assert before == sorted(str(path.relative_to(cwd)) for path in cwd.rglob("*")), "Server wrote to the caller's directory"
        if os.name != "nt":
            assert server.returncode == 0, f"Server interrupt exit code: {server.returncode}"
    print("PASS: clean offline wheel installation, 3muql + muql compatibility, CLI check/search/replay, and 3muql serve HTTP preview.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    try:
        verify(args.wheel)
    except (OSError, ValueError, AssertionError, subprocess.SubprocessError, queue.Empty) as error:
        print(f"Installation verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
