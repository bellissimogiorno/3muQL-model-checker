"""Small, bounded JSON interface shared by the browser worker and its tests.

Only literate MuQL declarations are interpreted. Requests never contain Python
code. The browser must run this module in a worker and terminate that worker
to stop an operation: the engine's ordinary deadlines are cooperative.
"""

from __future__ import annotations

import json
import math
import re

from .backends import BackendUnavailable
from .checker import check
from .search import format_theory, search, witness_theory
from .syntax import FormulaError, format_formula
from .theory import TheoryError, loads


MAX_SOURCE_CHARS = 250_000
# A character may take six bytes when JSON escapes Unicode. Allow that form
# without allowing an arbitrarily large request before parsing starts.
MAX_REQUEST_CHARS = MAX_SOURCE_CHARS * 6 + 50_000
_REQUEST_KEYS = frozenset({
    "action", "source", "mode", "properties", "drop", "limits", "solver",
})
_INTEGER_LIMITS = {
    "max_points": (1, 6, 3),
    "max_values": (1, 8, 2),
    "max_stages": (1, 12, 3),
    "max_quorums": (1, 64, 8),
    "max_frames": (1, 5_000, 500),
    "max_nodes": (1, 500_000, 500_000),
    "max_decisions": (0, 1_000_000, 100_000),
    "max_mu_contexts": (1, 12, 8),
}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"The request contains the field {key!r} more than once.")
        result[key] = value
    return result


def _finite_json(value):
    raise ValueError(f"{value} is not a valid finite JSON number.")


def _names(value, label, *, optional=False):
    if optional and value is None:
        return None
    if (not isinstance(value, list)
            or any(not isinstance(name, str) or not name for name in value)):
        raise ValueError(f"{label} must be a list of names" + (" or null." if optional else "."))
    if len(set(value)) != len(value):
        raise ValueError(f"{label} contains a repeated name.")
    return value


def _request(data):
    if not isinstance(data, dict):
        raise ValueError("The request must be a JSON object.")
    unknown = data.keys() - _REQUEST_KEYS
    if unknown:
        raise ValueError("Unrecognized request field(s): " + ", ".join(sorted(unknown)) + ".")
    if data.get("action") not in ("inspect", "run"):
        raise ValueError("Choose the inspect or run action.")
    source = data.get("source")
    if not isinstance(source, str):
        raise ValueError("The theory must be supplied as Markdown text.")
    if len(source) > MAX_SOURCE_CHARS:
        raise ValueError(f"This browser demo accepts theories up to {MAX_SOURCE_CHARS:,} characters. "
                         "Use the Python package for larger files.")
    mode = data.get("mode", "check")
    if mode not in ("check", "search"):
        raise ValueError("Choose check for a declared scope or search to find a scope.")
    solver = data.get("solver", "builtin")
    if solver not in ("builtin", "pysat"):
        raise ValueError("Choose the builtin or pysat solver.")
    properties = _names(data.get("properties"), "Properties", optional=True)
    dropped = _names(data.get("drop", []), "Dropped axioms")
    supplied_limits = data.get("limits", {})
    if not isinstance(supplied_limits, dict):
        raise ValueError("Limits must be a JSON object.")
    unknown = supplied_limits.keys() - (_INTEGER_LIMITS.keys() | {"timeout"})
    if unknown:
        raise ValueError("Unrecognized limit(s): " + ", ".join(sorted(unknown)) + ".")
    limits = {}
    for name, (minimum, maximum, default) in _INTEGER_LIMITS.items():
        value = supplied_limits.get(name, default)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"{name} must be a whole number from {minimum:,} to {maximum:,}.")
        limits[name] = value
    timeout = supplied_limits.get("timeout", 10)
    if (type(timeout) not in (int, float) or not 0 <= timeout <= 120
            or not math.isfinite(timeout)):
        raise ValueError("timeout must be a finite number from 0 to 120 seconds.")
    limits["timeout"] = timeout
    return source, mode, properties, dropped, solver, limits


def _metadata(theory):
    return {
        "name": theory.name,
        "predicates": [{"name": name, "arity": arity}
                       for name, arity in theory.predicates.items()],
        "scope_declared": theory.scope_declared,
        "scope": {"points": list(theory.points), "values": list(theory.values),
                  "stages": theory.stages, "quorums": [list(q) for q in theory.quorums],
                  "time": theory.time},
        "axioms": [{"name": name, "formula": format_formula(formula)}
                   for name, formula in theory.axioms.items()],
        "properties": [{"name": name, "formula": format_formula(formula)}
                       for name, formula in theory.properties.items()],
    }


def _browser_scope(theory, mode):
    sizes = {"values": len(theory.values)}
    if mode == "check":
        sizes.update(points=len(theory.points), stages=theory.stages,
                     quorums=len(theory.quorums))
    for name, size in sizes.items():
        maximum = _INTEGER_LIMITS["max_" + name][1]
        if size > maximum:
            raise ValueError(f"This browser demo supports at most {maximum} {name}; "
                             f"the theory declares {size}. Use the Python package for larger scopes.")


def _retained_markdown(theory):
    if theory.scope_declared:
        return format_theory(theory)
    # Search templates must remain templates: do not export the loader's
    # placeholder frame as though the user had supplied a concrete scope.
    lines = ["# Retained theory for model search", "",
             "This template retains the enabled axioms and all properties.",
             "Its scope is chosen by bounded model search.", "", "```muql",
             f"theory {theory.name!r}",
             "values " + " ".join(map(repr, theory.values)), f"time {theory.time}"]
    lines.extend(f"predicate {name}/{arity}" for name, arity in theory.predicates.items())
    for kind, formulas in (("axiom", theory.axioms), ("property", theory.properties)):
        lines.append("")
        lines.extend(f"{kind} {name}: {format_formula(formula)}"
                     for name, formula in formulas.items())
    lines.extend(["```", ""])
    return "\n".join(lines)


def _json(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n"


def _downloads(theory, report, max_mu_contexts):
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", theory.name).strip("-_")[:70] or "theory"
    stem = "muql-" + slug

    def item(name, label, filename, mime, content):
        return {"name": name, "label": label, "filename": filename,
                "mime": mime, "content": content}

    downloads = [
        item("report", "Full report (.json)", stem + "--report.json", "application/json",
             _json(report.to_dict())),
        item("theory", "Retained theory (.md)", stem + "--theory.md", "text/markdown",
             _retained_markdown(theory)),
    ]
    for index, result in enumerate(report.properties, 1):
        if result.countermodel is None:
            continue
        scoped = witness_theory(theory, result.countermodel, max_mu_contexts=max_mu_contexts)
        witness_stem = f"{stem}--{index:02d}-{result.name}"
        downloads.extend([
            item("witness-" + result.name + "-theory", f"{result.name}: replay theory (.md)",
                 witness_stem + ".md", "text/markdown", format_theory(scoped)),
            item("witness-" + result.name + "-countermodel", f"{result.name}: countermodel (.json)",
                 witness_stem + ".countermodel.json", "application/json",
                 _json(result.countermodel.to_dict())),
        ])
    return downloads


def _handle(data):
    source, mode, properties, dropped, solver, limits = _request(data)
    theory = loads(source, for_search=data["action"] == "inspect" or mode == "search")
    if data["action"] == "inspect":
        return {"ok": True, "metadata": _metadata(theory)}
    _browser_scope(theory, mode)
    theory = theory.without(*dropped)
    if "max_values" not in data.get("limits", {}):
        limits["max_values"] = max(2, len(theory.values))
    if mode == "search":
        report = search(theory, properties, solver=solver, **limits)
    else:
        options = {name: limits[name] for name in
                   ("timeout", "max_decisions", "max_nodes", "max_mu_contexts")}
        report = check(theory, properties, solver=solver,
                       total_timeout=limits["timeout"], **options)
    return {"ok": True, "report": report.to_dict(), "metadata": _metadata(theory),
            "downloads": _downloads(theory, report, limits["max_mu_contexts"])}


def handle_json(request: str) -> str:
    """Return an inspection or bounded run as JSON, including readable errors.

    ``properties: null`` selects all declared properties. An explicit empty
    list selects none, asking only whether the retained axioms have a model.
    Error line and column numbers, when present, refer to the user's Markdown.
    ``ok`` means a request was handled, not that a property holds: callers must
    display the report's separate statuses and its finite-scope qualification.
    """
    try:
        if not isinstance(request, str):
            raise ValueError("The request must be JSON text.")
        if len(request) > MAX_REQUEST_CHARS:
            raise ValueError("The request is too large for this browser demo.")
        data = json.loads(request, object_pairs_hook=_object, parse_constant=_finite_json)
        result = _handle(data)
    except json.JSONDecodeError:
        result = {"ok": False, "error": {"message": "The request is not valid JSON."}}
    except (TheoryError, FormulaError) as error:
        result = {"ok": False, "error": {"message": error.message,
                                         "line": error.line, "column": error.column}}
    except BackendUnavailable:
        result = {"ok": False, "error": {"message": "The accelerated solver is unavailable. "
                                         "Choose the built-in solver and try again."}}
    except (MemoryError, RecursionError):
        result = {"ok": False, "error": {"message": "This theory exceeded the browser's available "
                                         "memory or nesting depth. Try a smaller theory or scope."}}
    except (ValueError, TypeError, RuntimeError) as error:
        result = {"ok": False, "error": {"message": str(error)}}
    return _json(result)
