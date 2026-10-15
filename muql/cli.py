"""Command-line interface for literate finite-model exploration."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys
from typing import Sequence


def _print(text: object = "", *, file=None) -> None:
    """Preserve command outcomes when the terminal cannot display a label.

    Human-readable output uses reversible escapes for unsupported characters;
    UTF-8 terminals and text files retain their original Unicode spelling.
    JSON has its own escaping so that it remains valid machine-readable data.
    """
    stream = sys.stdout if file is None else file
    rendered = str(text)
    encoding = getattr(stream, "encoding", None)
    if encoding:
        rendered = rendered.encode(encoding, errors="backslashreplace").decode(encoding)
    print(rendered, file=stream)


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def _positive_seconds(text: str) -> float:
    try:
        value = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a finite positive number of seconds") from error
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number of seconds")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="muql",
        description="Check three-valued literate theories in a finite scope or search across bounded finite models.",
        epilog="Successful bounded checks are not unbounded proofs. See docs/semantics.md.",
    )
    from . import __version__
    parser.add_argument("--version", action="version", version=f"muql-explorer {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("list", help="show a theory's scope, axioms, and properties")
    inspect.add_argument("file", type=Path, help="UTF-8 Markdown containing fenced muql blocks")
    inspect.add_argument("--notation", choices=("unicode", "ascii"),
                         help="formula display (default: Unicode, with ASCII fallback for limited terminals)")
    check = commands.add_parser(
        "check",
        help="search for a model of the axioms that falsifies a property",
        epilog="Exit codes: 0 all selected properties hold; 1 counterexample; 2 invalid or inconsistent; 3 unknown.",
    )
    _add_search_options(check, solver_default="builtin")
    search = commands.add_parser(
        "search", help="find countermodels by varying finite domains and quorum families",
        epilog="Exit codes: 0 bounds exhausted without a counterexample, or a model found when no properties are selected; 1 counterexample; 2 invalid or every bounded frame inconsistent; 3 incomplete.",
    )
    _add_search_options(search, solver_default="auto", concrete_theories=True)
    search.add_argument("--max-points", type=_positive_int, default=3, metavar="N", help="maximum participants in each searched frame (default: 3)")
    search.add_argument("--max-values", type=_positive_int, default=None, metavar="N", help="maximum value-domain size (default: max(2, number of template values))")
    search.add_argument("--max-stages", type=_positive_int, default=3, metavar="N", help="maximum time stages in each searched frame (default: 3)")
    search.add_argument("--max-quorums", type=_positive_int, default=8, metavar="N", help="maximum nonempty quorums in each searched frame (default: 8)")
    search.add_argument("--max-frames", type=_positive_int, default=1000, metavar="N", help="maximum frames to examine before reporting an incomplete search (default: 1000)")
    replay = commands.add_parser("replay", help="independently validate a saved countermodel")
    replay.add_argument("file", type=Path, help="the original literate theory")
    replay.add_argument("countermodel", type=Path, help="a JSON witness written by --countermodels")
    replay.add_argument("--drop", action="append", default=[], metavar="AXIOM", help="apply the same removals used to produce the witness")
    replay.add_argument("--replace", action="append", default=[], metavar="AXIOM=FORMULA", help="apply the same replacements used to produce the witness")
    replay.add_argument("--max-mu-contexts", type=_positive_int, default=8, metavar="N", help="maximum contexts for general nonpositive fixed points; match an increased check budget (default: 8)")
    return parser


def _add_search_options(command, *, solver_default: str, concrete_theories: bool = False) -> None:
    """Share formula edits, budgets and exports across both checking modes."""
    command.add_argument("file", type=Path, help="UTF-8 Markdown containing fenced muql blocks")
    command.add_argument("--drop", action="append", default=[], metavar="AXIOM", help="remove a named axiom (repeatable)")
    command.add_argument("--replace", action="append", default=[], metavar="AXIOM=FORMULA", help="replace an axiom's formula (repeatable; quote in the shell)")
    command.add_argument("--property", action="append", dest="properties", metavar="NAME", help="select a property (repeatable; default: all)")
    timeout_help = ("total search time budget, checked between operations (default: 30 seconds)"
                    if concrete_theories else "time budget for each checking phase (default: 30 seconds)")
    command.add_argument("--timeout", type=_positive_seconds, default=30.0, metavar="SECONDS", help=timeout_help)
    command.add_argument("--max-decisions", type=_positive_int, default=100000, metavar="N", help="SAT decision budget (default: 100000)")
    command.add_argument("--max-nodes", type=_positive_int, default=500000, metavar="N", help="compilation node budget (default: 500000)")
    command.add_argument("--max-mu-contexts", type=_positive_int, default=8, metavar="N", help="maximum contexts for general nonpositive fixed points (default: 8)")
    command.add_argument("--solver", choices=("auto", "builtin", "pysat"), default=solver_default, help=f"SAT backend (default: {solver_default}); auto uses PySAT when installed")
    command.add_argument("--json", metavar="PATH", help="write the complete JSON report; '-' writes only JSON to stdout")
    export_help = "save each witness as JSON and a readable text table"
    if concrete_theories:
        export_help += ", plus its complete Markdown theory for replay"
    command.add_argument("--countermodels", type=Path, metavar="DIR", help=export_help)


def _exit_code(report) -> int:
    if report.status == "inconsistent":
        return 2
    if report.status == "unknown" or any(item.status == "unknown" for item in report.properties):
        return 3
    return 1 if any(item.status == "counterexample" for item in report.properties) else 0


def _print_report(report) -> None:
    _print(f"{report.theory}")
    _print("Scope: " + ", ".join(f"{key}={value}" for key, value in report.scope.items()))
    _print("Results apply to this finite frame only.")
    if report.status == "inconsistent":
        _print("INCONSISTENT: no model satisfies the axioms in this scope.")
    elif report.status == "unknown":
        _print("UNKNOWN: the search did not establish a complete result.")
    if report.reason:
        _print(report.reason)
    for result in report.properties:
        label = {"holds": "HOLDS IN SCOPE", "counterexample": "COUNTEREXAMPLE", "unknown": "UNKNOWN"}.get(result.status, result.status.upper())
        _print(f"\n{label}: {result.name}")
        if result.reason:
            _print(result.reason)
        if result.countermodel is not None:
            _print(result.countermodel.format())
    if not report.properties and report.status == "checked":
        _print("The axioms are satisfiable; no properties were declared.")


def _print_search_report(report) -> None:
    _print(report.theory)
    bounds = report.bounds
    sizes = []
    for name in ("points", "values", "stages"):
        lower, upper = bounds[name]
        sizes.append(f"{lower}..{upper} {name}")
    sizes.append(f"at most {bounds['max_quorums']} quorums")
    _print("Search bounds: " + " | ".join(sizes))
    _print(f"Time: {bounds['time']}; named values: {', '.join(bounds['named_values'])}")
    _print(f"Search budget: {bounds['timeout']:g} seconds; {bounds['max_frames']} frames.")
    stats = report.stats
    if stats.get("solver"):
        _print(f"Solver: {stats['solver']}")
    _print("Results concern these finite search bounds; they are not unbounded proofs.")
    if report.status == "inconsistent":
        _print("INCONSISTENT WITHIN BOUNDS: no searched frame has a model of the axioms.")
    elif report.status == "unknown":
        _print("UNKNOWN: the search did not establish a complete result within its bounds.")
    elif report.status == "satisfiable":
        _print("SATISFIABLE: a finite model of the axioms was found; no properties were selected.")
        if report.consistency_scope is not None:
            _print_model_scope(report.consistency_scope, label="Model scope")
    if report.reason:
        _print(report.reason)
    _print(
        f"Frames checked: {stats.get('frames', 0)}; "
        f"with axiom models: {stats.get('consistent_frames', 0)}; "
        f"inconsistent: {stats.get('inconsistent_frames', 0)}; "
        f"incomplete checks: {stats.get('unknown_frames', 0)}."
    )
    for result in report.properties:
        label = {"holds": "HOLDS WITHIN SEARCH BOUNDS", "counterexample": "COUNTEREXAMPLE", "unknown": "UNKNOWN"}.get(result.status, result.status.upper())
        _print(f"\n{label}: {result.name}")
        if result.reason:
            _print(result.reason)
        if result.countermodel is not None:
            _print_model_scope(result.countermodel.scope, label="Countermodel scope")
            _print(result.countermodel.format())


def _print_model_scope(scope, *, label: str) -> None:
    _print(f"{label}: points={{{', '.join(scope['points'])}}}; "
          f"values={{{', '.join(scope['values'])}}}; "
          f"stages={scope['stages']}; time={scope['time']}.")
    _print("Quorums: " + " ".join("{" + ", ".join(quorum) + "}" for quorum in scope["quorums"]))


def _save_countermodels(report, directory: Path, *, theory=None, max_mu_contexts=8) -> list[Path]:
    paths = []
    for index, result in enumerate(report.properties, 1):
        if result.countermodel is None:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", result.name)
        stem = directory / f"{index:02d}-{safe_name}"
        json_path = stem.with_suffix(".json")
        text_path = stem.with_suffix(".txt")
        json_path.write_text(json.dumps(result.countermodel.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        text_path.write_text(result.countermodel.format() + "\n", encoding="utf-8")
        paths.extend([json_path, text_path])
        if theory is not None:
            from .search import format_theory, witness_theory
            theory_path = stem.with_suffix(".md")
            concrete = witness_theory(theory, result.countermodel, max_mu_contexts=max_mu_contexts)
            theory_path.write_text(format_theory(concrete), encoding="utf-8")
            paths.append(theory_path)
    return paths


def _display_notation(requested: str | None) -> str:
    if requested is not None:
        return requested
    try:
        "∀∃⁰¹⇀∧¬◇□μ".encode(getattr(sys.stdout, "encoding", None) or "utf-8")
        return "unicode"
    except (UnicodeError, LookupError):
        return "ascii"


def _formula_lines(text: str, width: int = 88) -> list[str]:
    """Wrap only outside quoted values; every line remains safe to copy."""
    breaks = []
    quote = None
    escaped = False
    for i, char in enumerate(text):
        if escaped:
            escaped = False
        elif quote is not None:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char.isspace():
            breaks.append(i)
    lines, start = [], 0
    while len(text) - start > width:
        available = [i for i in breaks if start < i <= start + width]
        if not available:
            available = [i for i in breaks if i > start]
            if not available:
                break
            end = available[0]
        else:
            end = available[-1]
        lines.append(text[start:end].strip())
        start = end + 1
    lines.append(text[start:].strip())
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code; normal errors have no traceback."""
    args = _parser().parse_args(argv)
    # Imported here so --help and --version remain fast and self-contained.
    from . import check, load, replay
    from .evaluate import FixedPointLimitError
    from .frame import FrameLimit
    from .syntax import format_formula

    try:
        theory = load(args.file, for_search=args.command in {"search", "list"})
        if args.command == "list":
            notation = _display_notation(args.notation)
            _print(theory.name)
            if theory.scope_declared:
                _print(f"Points: {', '.join(theory.points)}")
                _print(f"Values: {', '.join(theory.values)}")
                _print(f"Stages: {theory.stages}; time: {theory.time}")
                _print("Quorum generators: " + " ".join("{" + ",".join(q) + "}" for q in theory.quorums))
            else:
                _print("Search template: no fixed scope")
                _print(f"Initial value labels: {', '.join(theory.values)}; time: {theory.time}")
            _print("Predicates: " + ", ".join(f"{name}/{arity}" for name, arity in theory.predicates.items()))
            for kind, formulas in (("Axioms", theory.axioms), ("Properties", theory.properties)):
                _print(f"\n{kind} ({len(formulas)}):")
                for name, formula in formulas.items():
                    _print(f"\n  {name}")
                    for line in _formula_lines(format_formula(formula, notation=notation)):
                        _print(f"    {line}")
            return 0
        theory = theory.without(*args.drop)
        for replacement in args.replace:
            name, separator, formula = replacement.partition("=")
            if not separator or not name.strip() or not formula.strip():
                raise ValueError("--replace expects AXIOM=FORMULA, for example 'Correct=TB(vote())'")
            theory = theory.replace(name.strip(), formula.strip())
        if args.command == "replay":
            data = json.loads(args.countermodel.read_text(encoding="utf-8"))
            replay(theory, data, max_mu_contexts=args.max_mu_contexts)
            _print(f"VALIDATED: {data['property']} is false in this finite countermodel.")
            _print("All retained axioms are valid; every atomic cell was checked independently.")
            return 0
        budgets = dict(timeout=args.timeout, max_decisions=args.max_decisions,
                       max_nodes=args.max_nodes, max_mu_contexts=args.max_mu_contexts,
                       solver=args.solver)
        if args.command == "search":
            from .search import search
            report = search(
                theory, properties=args.properties,
                max_points=args.max_points, max_values=args.max_values,
                max_stages=args.max_stages, max_quorums=args.max_quorums,
                max_frames=args.max_frames, **budgets,
            )
        else:
            report = check(theory, properties=args.properties, **budgets)
        paths = _save_countermodels(
            report, args.countermodels, theory=theory if args.command == "search" else None,
            max_mu_contexts=args.max_mu_contexts,
        ) if args.countermodels else []
        if args.json:
            data = report.to_dict()
            rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
            if args.json == "-":
                # JSON escapes are lossless. Check before writing so a limited
                # terminal cannot leave a truncated report or change its status.
                try:
                    rendered.encode(getattr(sys.stdout, "encoding", None) or "utf-8")
                except (UnicodeError, LookupError):
                    rendered = json.dumps(data, indent=2, ensure_ascii=True) + "\n"
                sys.stdout.write(rendered)
            else:
                Path(args.json).write_text(rendered, encoding="utf-8")
        if args.json != "-":
            (_print_search_report if args.command == "search" else _print_report)(report)
            if args.json:
                _print(f"\nReport saved to {args.json}")
            for path in paths:
                _print(f"Countermodel saved to {path}")
        return _exit_code(report)
    except (FixedPointLimitError, FrameLimit) as error:
        _print(f"muql: {args.command} incomplete: {error}", file=sys.stderr)
        return 3
    except (OSError, ValueError, KeyError, TypeError) as error:
        _print(f"muql: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        _print("muql: interrupted; no complete result", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
