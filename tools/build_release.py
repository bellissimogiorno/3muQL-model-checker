#!/usr/bin/env python3
"""Prepare the browser bundles and build portable release distributions.

python tools/build_release.py --prepare-only  # standard library only
python tools/build_release.py --check         # detect stale generated assets
python tools/build_release.py                 # also needs setuptools and wheel

No downloads are performed. The default browser runtime is fetched by visitors
from the pinned CDN. Use build_site.py for a mirror or a bundled runtime build.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

if __package__:
    from .build_site import build
    from .check_version import check_version
else:
    from build_site import build
    from check_version import check_version

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist",
             ".pytest_cache", ".mypy_cache", "artifacts"}
TOP_DIRS = {".github", "docs", "examples", "muql", "reports", "tests", "tools", "web", "site"}
TOP_FILES = {".gitattributes", ".gitignore", ".nojekyll", "index.html", "README.md", "LICENSE", "VERSION",
             "CHANGELOG.md", "CONTRIBUTING.md", "SOURCES.md", "MANIFEST.in", "pyproject.toml",
             "demo.py", "serve.sh"}
PUBLIC_HIDDEN_PATHS = {".github", ".gitattributes", ".gitignore", ".nojekyll", "site/.nojekyll",
                       "site/.muql-site-build"}


def _output_path(path: Path, root: Path, *, directory: bool = False) -> None:
    """Reject redirected or nonregular outputs before preparing any assets."""
    parts = path.relative_to(root).parts
    current = root
    for index, part in enumerate(parts):
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Generated release output must not be a symbolic link: {current}")
        if current.exists():
            needs_directory = directory or index < len(parts) - 1
            if not (current.is_dir() if needs_directory else current.is_file()):
                raise ValueError(f"Generated release output has the wrong file type: {current}")


def landing_page(version: str) -> bytes:
    """Branch-based Pages falls straight through to the ready-built site."""
    return ('''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>3μQL Explorer ''' + version + '''</title>
  <meta http-equiv="refresh" content="0; url=./site/">
  <script>
    const destination = new URL("./site/", location.href);
    destination.search = location.search;
    destination.hash = location.hash;
    location.replace(destination.href);
  </script>
</head>
<body><p>Opening <a href="./site/">3μQL Explorer ''' + version + '''</a>…</p>
<noscript><p>The interactive explorer requires JavaScript.</p></noscript></body>
</html>
''').encode("utf-8")


def zip_bytes(files: list[tuple[str, bytes, int]]) -> bytes:
    """Stable ordering, timestamps and modes, independent of checkout mtimes."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data, mode in sorted(files):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = mode << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data, compresslevel=9)
    return output.getvalue()


def site_archive(site: Path) -> bytes:
    files = []
    for path in sorted(site.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Cannot archive a symbolic link: {path}")
        if path.is_file():
            files.append((path.relative_to(site).as_posix(), path.read_bytes(), 0o100644))
    return zip_bytes(files)


def normalize_sdist(path: Path) -> None:
    """Remove build-machine ownership and wall-clock timestamps from tar/gzip."""
    output = io.BytesIO()
    with tarfile.open(path, "r:gz") as source, \
            gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=315532800) as compressed, \
            tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as target:
        for entry in sorted(source.getmembers(), key=lambda item: item.name):
            if not (entry.isfile() or entry.isdir()):
                raise ValueError(f"Unexpected source distribution member: {entry.name}")
            entry.uid = entry.gid = 0
            entry.uname = entry.gname = ""
            entry.mtime = 315532800
            entry.pax_headers = {}
            entry.mode = 0o755 if entry.isdir() or entry.name.endswith("/serve.sh") else 0o644
            data = source.extractfile(entry) if entry.isfile() else None
            try:
                target.addfile(entry, data)
            finally:
                if data is not None:
                    data.close()
    path.write_bytes(output.getvalue())


def source_files(root: Path):
    """Use maintained roots, excluding hidden files and known build products.

    Other visible files within those roots are release inputs; the builder does
    not inspect their contents or decide whether they contain private data.
    """
    def walk(path: Path):
        relative = path.relative_to(root)
        if path.name in SKIP_DIRS or path.name.endswith(".egg-info"):
            return
        if path.name.startswith(".") and relative.as_posix() not in PUBLIC_HIDDEN_PATHS:
            return
        if path.suffix in {".pyc", ".pyo"}:
            return
        if path.is_symlink():
            raise ValueError(f"Release inputs must not be symbolic links: {path}")
        if path.is_dir():
            for child in sorted(path.iterdir()):
                yield from walk(child)
        elif path.is_file():
            yield relative, path

    for name in sorted(TOP_FILES | TOP_DIRS):
        source = root / name
        if not source.exists():
            raise ValueError(f"Release input missing: {name}")
        if source.is_symlink():
            raise ValueError(f"Release inputs must not be symbolic links: {source}")
        yield from walk(source)


def prepare(root: Path = ROOT, *, check: bool = False) -> Path:
    root = root.resolve()
    version = check_version(root)
    for name in ("index.html", ".nojekyll", "muql/_site.zip"):
        _output_path(root / name, root)
    site = root / "site"
    build(site, root=root, check=check)
    expected = {
        root / "index.html": landing_page(version),
        root / ".nojekyll": b"",
        root / "muql" / "_site.zip": site_archive(site),
    }
    for path in expected:
        if path.is_symlink():
            raise ValueError(f"Generated release file must not be a symbolic link: {path}")
    if check:
        changed = [str(path.relative_to(root)) for path, data in expected.items()
                   if not path.is_file() or path.read_bytes() != data]
        if changed:
            raise ValueError("Stale release files: " + ", ".join(changed) +
                             ". Run python tools/build_release.py --prepare-only.")
        print(f"Ready-built browser assets agree with source {version}.")
    else:
        for path, data in expected.items():
            path.write_bytes(data)
        print(f"Prepared branch Pages entry and installed browser assets for {version}.")
    return site


def release(root: Path = ROOT, *, python_distributions: bool = True) -> list[Path]:
    root = root.resolve()
    version = check_version(root)
    destination = root / "dist" / "releases"
    _output_path(destination, root, directory=True)
    outputs = [f"3muql-explorer-{version}.zip", f"3muql-explorer-site-{version}.zip",
               f"release-{version}.json"]
    if python_distributions:
        outputs.extend([f"muql_explorer-{version}-py3-none-any.whl",
                        f"muql_explorer-{version}.tar.gz", f"muql-explorer-{version}.tar.gz"])
    for name in outputs:
        _output_path(destination / name, root)
    site = prepare(root)
    destination.mkdir(parents=True, exist_ok=True)
    files = list(source_files(root))
    # Build in a clean temporary source tree. setuptools must not include stale
    # egg-info, an old local build, or arbitrary files from the caller's cwd.
    with tempfile.TemporaryDirectory(prefix="muql-release-") as temporary:
        staging = Path(temporary)
        clean = staging / "source"
        clean.mkdir()
        for relative, source in files:
            target = clean / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(0o755 if relative.as_posix() == "serve.sh" else 0o644)
        products = staging / "products"
        products.mkdir()
        (products / f"3muql-explorer-{version}.zip").write_bytes(zip_bytes([
            ("3muql-explorer/" + relative.as_posix(), path.read_bytes(),
             0o100755 if relative.as_posix() == "serve.sh" else 0o100644)
            for relative, path in files
        ]))
        (products / f"3muql-explorer-site-{version}.zip").write_bytes(site_archive(site))
        if python_distributions:
            env = {**os.environ, "SOURCE_DATE_EPOCH": "315532800"}
            # setuptools changes sys.argv internally while building a wheel.
            # Capture the destination once so sdist reaches the same directory.
            code = ("from setuptools.build_meta import build_wheel, build_sdist; "
                    "import sys; output = sys.argv[1]; build_wheel(output); build_sdist(output)")
            subprocess.run([sys.executable, "-c", code, str(products)], cwd=clean,
                           env=env, check=True)
            distributions = list(products.glob("*.tar.gz"))
            if len(distributions) != 1 or len(list(products.glob("*.whl"))) != 1:
                raise ValueError("The Python build did not produce exactly one wheel and source distribution")
            normalize_sdist(distributions[0])
            # Older supported setuptools versions use a hyphenated sdist name;
            # keep the handover artifact name stable across backend versions.
            canonical_sdist = products / f"muql_explorer-{version}.tar.gz"
            if distributions[0] != canonical_sdist:
                distributions[0].replace(canonical_sdist)
        artifacts = []
        for path in sorted(products.iterdir()):
            target = destination / path.name
            if target.is_symlink():
                raise ValueError(f"Release output must not be a symbolic link: {target}")
            shutil.copyfile(path, target)
            artifacts.append(target)
    record = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in artifacts}
    manifest = destination / f"release-{version}.json"
    if manifest.is_symlink():
        raise ValueError("Release manifest must not be a symbolic link")
    manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Built {len(artifacts)} release artifacts in {destination}")
    return artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true", help="refresh the tracked site, landing page and package asset ZIP")
    mode.add_argument("--check", action="store_true", help="verify generated files without changing them")
    parser.add_argument("--skip-python", action="store_true", help="build only source and site ZIPs (standard library only)")
    args = parser.parse_args(argv)
    if args.skip_python and (args.prepare_only or args.check):
        parser.error("--skip-python applies only to a full release build")
    try:
        if args.prepare_only or args.check:
            prepare(check=args.check)
        else:
            release(python_distributions=not args.skip_python)
    except (OSError, ValueError, SyntaxError, subprocess.CalledProcessError) as error:
        print(f"Release build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
