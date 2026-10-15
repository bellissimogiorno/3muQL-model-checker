#!/usr/bin/env python3
"""Run the real Playwright/Pyodide suite against one release delivery route.

python tools/test_browser.py --target actions --native
python tools/test_browser.py --target branch
python tools/test_browser.py --target installed --python /path/to/venv/bin/python

Requires Node, Playwright 1.62.1, Chromium, and access to the pinned Pyodide
runtime. No mock runtime or solver is substituted. An unavailable prerequisite
is a failed check. The installed target must have the wheel installed first.
"""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading

if __package__:
    from .build_site import build
else:
    from build_site import build

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *_args):
        pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", choices=("actions", "branch", "installed"), default="actions")
    parser.add_argument("--native", action="store_true", help="also require the optional browser MiniSat solver")
    parser.add_argument("--python", default=sys.executable, help="installed Python executable for --target installed")
    args = parser.parse_args(argv)
    artifacts = ROOT / "tests/browser/artifacts" / args.target
    artifacts.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "MUQL_BROWSER_ARTIFACTS": str(artifacts),
           "MUQL_BROWSER_NATIVE": "1" if args.native else "0"}
    # Resolve the executable before changing cwd; never rely on the checkout
    # being importable when checking an installed wheel.
    # Do not resolve symlinks: a venv's python may link to the system binary,
    # but its original path is what selects the installed environment.
    python = os.path.abspath(shutil.which(args.python) or args.python)
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    process = server = thread = None
    try:
        with tempfile.TemporaryDirectory(prefix="browser-check-", dir=dist) as temporary:
            temporary = Path(temporary)
            if args.target == "installed":
                process_env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
                process = subprocess.Popen([python, "-I", "-m", "muql", "serve", "--port", "0"],
                                           cwd=temporary, env=process_env, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, text=True, bufsize=1)
                messages = queue.Queue()
                def consume():
                    for line in process.stdout:
                        messages.put(line)
                    messages.put(None)
                thread = threading.Thread(target=consume, daemon=True)
                thread.start()
                url = None
                while url is None:
                    line = messages.get(timeout=30)
                    if line is None:
                        raise ValueError("Installed preview exited before announcing its URL")
                    print(line, end="")
                    match = re.search(r"http://127\.0\.0\.1:\d+/", line)
                    if match:
                        url = match[0]
            else:
                project = temporary / "3muQL-model-checker"
                if args.target == "actions":
                    build(project)
                else:
                    project.mkdir()
                    shutil.copyfile(ROOT / "index.html", project / "index.html")
                    shutil.copyfile(ROOT / ".nojekyll", project / ".nojekyll")
                    shutil.copytree(ROOT / "site", project / "site")
                server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(temporary)))
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                url = f"http://127.0.0.1:{server.server_port}/3muQL-model-checker/"
            print(f"Real browser target {args.target}: {url}", flush=True)
            env["MUQL_WEB_URL"] = url
            try:
                completed = subprocess.run(["node", str(ROOT / "tests/browser/smoke.mjs")],
                                           cwd=ROOT, env=env, timeout=900)
                return completed.returncode
            finally:
                # Stop serving before TemporaryDirectory removes the tree,
                # including on Windows where open files prevent deletion.
                if server is not None:
                    server.shutdown()
                    server.server_close()
                if process is not None and process.poll() is None:
                    process.send_signal(signal.SIGINT) if os.name != "nt" else process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                if thread is not None:
                    thread.join(timeout=2)
                if process is not None:
                    process.stdout.close()
    except (OSError, ValueError, queue.Empty, subprocess.SubprocessError) as error:
        print(f"Browser verification failed: {error}", file=sys.stderr)
        return 1
    finally:
        # Startup failures happen before the inner cleanup is entered.
        if server is not None:
            server.server_close()
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
