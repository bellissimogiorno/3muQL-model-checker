"""Internal build/HTTP support for the Bash local-preview launcher."""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import webbrowser

if __package__:
    from .build_site import build
else:
    from build_site import build


ROOT = Path(__file__).resolve().parents[1]


class PreviewHandler(SimpleHTTPRequestHandler):
    """Always fetch the current build when refreshing a local preview."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def build_preview() -> int:
    try:
        build()
    except (OSError, ValueError, SyntaxError) as error:
        print(f"Site build failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        # The Bash launcher prints the clean interruption message.
        return 130
    return 0


def serve_preview(port: int = 8000, open_browser: bool = False) -> int:
    try:
        handler = partial(PreviewHandler, directory=str(ROOT / "dist" / "site"))
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError as error:
            print(f"Cannot start the local preview on port {port}: {error}\n"
                  "Re-run with --port 0 to choose a free port.", file=sys.stderr)
            return 1

        with server:
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            print(f"\nOpen {url}\n"
                  "Press Ctrl+C to stop. Re-run this command after changing source files.\n"
                  "The browser needs internet access to load its Python runtime on first use.",
                  flush=True)
            if open_browser:
                try:
                    opened = webbrowser.open(url)
                except webbrowser.Error:
                    opened = False
                if not opened:
                    print("Could not open a browser automatically. Open the address above.", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        print("\nLocal preview stopped.", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["build"]:
        return build_preview()
    if len(args) == 3 and args[0] == "serve" and args[2] in ("0", "1"):
        try:
            port = int(args[1])
        except ValueError:
            port = -1
        if 0 <= port <= 65535:
            return serve_preview(port, args[2] == "1")
    print("Use bash serve.sh to start the local preview.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
