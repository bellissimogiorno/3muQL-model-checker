#!/usr/bin/env python3
"""Check the repository's three release identifiers without importing MuQL.

Run ``python tools/check_version.py`` before building or publishing a release.
VERSION, the static [project].version in pyproject.toml, and the literal
muql.__version__ must agree. Release identifiers use the form MAJOR.MINOR.PATCH.
This checker uses only the Python 3.10 standard library.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
_RELEASE = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def _release(value: object, source: str) -> str:
    if not isinstance(value, str) or _RELEASE.fullmatch(value) is None:
        raise ValueError(f"{source}: expected a release version such as 0.4.2 (MAJOR.MINOR.PATCH)")
    return value


def _project_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    sections = re.findall(
        r"^[ \t]*\[project\][ \t]*(?:#[^\r\n]*)?\r?\n(.*?)(?=^[ \t]*\[|\Z)",
        text, flags=re.MULTILINE | re.DOTALL,
    )
    if len(sections) != 1:
        raise ValueError(f"{path}: expected one [project] section")
    declarations = re.findall(r"^[ \t]*version[ \t]*=[ \t]*([^\r\n]*)$", sections[0], re.MULTILINE)
    if len(declarations) != 1:
        raise ValueError(f"{path}: expected one static version declaration in [project]")
    match = re.fullmatch(r"(['\"])([0-9]+\.[0-9]+\.[0-9]+)\1[ \t]*(?:#[^\r\n]*)?", declarations[0])
    if match is None:
        raise ValueError(f"{path}: [project].version must be a quoted MAJOR.MINOR.PATCH release")
    return _release(match[2], f"{path} [project].version")


def _package_version(path: Path) -> str:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    declarations = []
    for statement in module.body:
        if isinstance(statement, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "__version__"
                   for target in statement.targets):
                declarations.append(statement.value)
        elif isinstance(statement, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(statement.target, ast.Name) and statement.target.id == "__version__":
                if isinstance(statement, ast.AugAssign):
                    raise ValueError(f"{path}: __version__ must be a single literal assignment")
                declarations.append(statement.value)
    if len(declarations) != 1:
        raise ValueError(f"{path}: expected one literal __version__ assignment")
    try:
        value = ast.literal_eval(declarations[0])
    except (ValueError, TypeError, SyntaxError) as error:
        raise ValueError(f"{path}: __version__ must be a literal release string") from error
    return _release(value, f"{path} __version__")


def check_version(root: str | Path = ROOT) -> str:
    """Return the agreed release version, or raise on missing/mismatched data."""
    root = Path(root)
    versions = {
        "VERSION": _release((root / "VERSION").read_text(encoding="utf-8").strip(), "VERSION"),
        "pyproject.toml [project].version": _project_version(root / "pyproject.toml"),
        "muql/__init__.py __version__": _package_version(root / "muql" / "__init__.py"),
    }
    if len(set(versions.values())) != 1:
        details = "; ".join(f"{name}={version}" for name, version in versions.items())
        raise ValueError("release versions do not agree: " + details)
    return versions["VERSION"]


def main() -> int:
    try:
        version = check_version()
    except (OSError, ValueError, SyntaxError) as error:
        print(f"Version check failed: {error}", file=sys.stderr)
        return 1
    print(f"Versions agree: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
