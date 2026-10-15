"""Serve the installed browser application without a source checkout or Bash.

The release bundles its generated public site as package data. Only those
files are extracted, to a temporary directory, and exposed on loopback HTTP.
The server never installs packages or downloads the browser's Python runtime.
"""

from __future__ import annotations

from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
import webbrowser
import zipfile

from . import __version__


class SiteError(ValueError):
    """The installed site is absent, unsafe, or inconsistent with the engine."""


def _archive_members(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
    """Validate every path before writing, including Windows path aliases."""
    result = []
    seen: dict[str, bool] = {}
    reserved = {"con", "prn", "aux", "nul"}
    reserved.update(f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10))
    for member in archive.infolist():
        name = member.orig_filename
        parts = name.rstrip("/").split("/")
        mode = stat.S_IFMT(member.external_attr >> 16)
        if (not name or name.startswith("/") or "\\" in name or ":" in name or "\0" in name
                or any(part in {"", ".", ".."} or part.endswith((".", " "))
                       or part.split(".", 1)[0].casefold() in reserved for part in parts)
                or mode not in {0, stat.S_IFREG, stat.S_IFDIR}
                or (mode == stat.S_IFDIR and not member.is_dir())):
            raise SiteError(f"The bundled browser site contains an unsafe archive entry: {name!r}.")
        path = PurePosixPath(*parts)
        key = str(path).casefold()
        if key in seen:
            raise SiteError(f"The bundled browser site contains a duplicate archive path: {name!r}.")
        seen[key] = member.is_dir()
        result.append((member, path))
    for member, path in result:
        if any(seen.get(str(parent).casefold()) is False for parent in path.parents if str(parent) != "."):
            raise SiteError(f"The bundled browser site has conflicting archive paths: {member.filename!r}.")
    return result


@contextmanager
def bundled_site():
    """Yield a checked public site and remove all temporary files afterwards."""
    resource = resources.files("muql").joinpath("_site.zip")
    try:
        stream = resource.open("rb")
    except FileNotFoundError as error:
        raise SiteError("The bundled browser site is missing. Install the complete release wheel "
                        "or unpack the complete source release.") from error
    with stream, tempfile.TemporaryDirectory(prefix="muql-site-") as directory:
        root = Path(directory)
        try:
            with zipfile.ZipFile(stream) as archive:
                members = _archive_members(archive)
                for member, relative in members:
                    target = root.joinpath(*relative.parts)
                    if member.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(member) as source, target.open("xb") as destination:
                            shutil.copyfileobj(source, destination)
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as error:
            raise SiteError(f"The bundled browser site archive cannot be read: {error}") from error
        if not (root / "index.html").is_file():
            raise SiteError("The bundled browser site has no index.html. Reinstall the complete release.")
        try:
            config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as error:
            raise SiteError("The bundled browser site has no readable config.json. Reinstall the complete release.") from error
        if not isinstance(config, dict) or config.get("version") != __version__:
            raise SiteError(f"The bundled browser site does not match installed version {__version__}. "
                            "Reinstall the complete release.")
        yield root


class SiteHandler(SimpleHTTPRequestHandler):
    """Serve public assets without persistent caching or directory listings."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def list_directory(self, path):
        self.send_error(404, "No page at this address")
        return None


def serve(port: int = 8000, open_browser: bool = False) -> int:
    """Serve the bundled application until Ctrl+C; return a CLI exit code."""
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        print("Port must be an integer from 0 to 65535; use 0 to choose a free port.", file=sys.stderr)
        return 2
    try:
        with bundled_site() as root:
            handler = partial(SiteHandler, directory=str(root))
            try:
                server = ThreadingHTTPServer(("127.0.0.1", port), handler)
            except OSError as error:
                print(f"Cannot start the local explorer on port {port}: {error}\n"
                      "Re-run with --port 0 to choose a free port.", file=sys.stderr)
                return 1
            with server:
                url = f"http://127.0.0.1:{server.server_address[1]}/"
                print(f"3muQL Explorer {__version__}\nOpen {url}\n"
                      "Press Ctrl+C to stop.\n"
                      "The browser needs internet access to load its Python runtime on first use.", flush=True)
                if open_browser:
                    try:
                        opened = webbrowser.open(url)
                    except (webbrowser.Error, OSError):
                        opened = False
                    if not opened:
                        print("Could not open a browser automatically. Open the address above.", flush=True)
                server.serve_forever()
    except KeyboardInterrupt:
        print("\nLocal explorer stopped.", flush=True)
    except (OSError, SiteError) as error:
        print(f"Cannot load the local explorer: {error}", file=sys.stderr)
        return 1
    return 0
