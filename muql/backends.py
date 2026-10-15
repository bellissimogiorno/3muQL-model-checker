"""Optional native SAT acceleration behind the audited solver interface.

The dependency-free solver remains the default.  ``auto`` selects PySAT's
MiniSat22 when importable and otherwise uses the built-in solver.  Native
search runs in growing propagation slices, checking its elapsed time and
decision count between slices.  These are cooperative limits: a native slice
can overshoot, but a result observed after a deadline or decision cap is
reported as unknown.  No native decision-budget API is assumed.
"""

from __future__ import annotations

from time import monotonic
from typing import Iterable

from .sat import SolveResult, _validate_limits, solve as builtin_solve

# Stay within a signed native integer even on a 32-bit build.
_MAX_PROPAGATION_SLICE = (1 << 31) - 1


class BackendUnavailable(ValueError):
    """An explicitly requested optional solver could not be imported."""


def _minisat():
    try:
        from pysat.solvers import Minisat22
    except (ImportError, OSError) as error:
        raise BackendUnavailable(
            "PySAT is unavailable; install the optional dependency with "
            "'python -m pip install .[sat]' or select solver='builtin'"
        ) from error
    return Minisat22


def resolve_backend(name: str = "builtin") -> str:
    """Validate a backend name and resolve ``auto`` without changing defaults."""
    if name not in ("builtin", "pysat", "auto"):
        raise ValueError("solver must be 'builtin', 'pysat', or 'auto'")
    if name == "builtin":
        return name
    try:
        _minisat()
    except BackendUnavailable:
        if name == "auto":
            return "builtin"
        raise
    return "pysat"


def solve(nvars: int, clauses: Iterable[Iterable[int]], timeout: float = 10.0,
          max_decisions: int = 100_000, *, backend: str = "builtin") -> SolveResult:
    """Solve CNF using the selected engine and return the common result type.

    PySAT's ``None`` means unknown, never unsatisfiable.  Native decision
    statistics include solver-internal decisions and need not match built-in
    counts.  A native result above ``max_decisions`` is discarded as unknown.
    Zero decisions uses built-in unit propagation because MiniSat interprets
    a zero native budget as unlimited.  Zero timeout immediately means unknown.
    """
    _validate_limits(nvars, timeout, max_decisions)
    selected = resolve_backend(backend)
    if selected == "builtin" or max_decisions == 0:
        return builtin_solve(nvars, clauses, timeout=timeout,
                             max_decisions=max_decisions)
    return _solve_pysat(nvars, clauses, timeout, max_decisions)


def _solve_pysat(nvars, clauses, timeout, max_decisions):
    deadline = monotonic() + timeout
    decisions = 0

    def expired():
        return monotonic() >= deadline

    def unknown(reason):
        return SolveResult("unknown", {}, decisions, reason)

    if expired():
        return unknown("timeout exhausted")
    normalized = []
    occurring = set()
    contradiction = False
    work = 0
    for supplied in clauses:
        if expired():
            return unknown("timeout exhausted while loading CNF")
        seen = set()
        clause = []
        tautology = False
        for literal in supplied:
            work += 1
            if work % 256 == 0 and expired():
                return unknown("timeout exhausted while loading CNF")
            if type(literal) is not int or literal == 0 or abs(literal) > nvars:
                raise ValueError(f"literal {literal!r} is not an integer in +/-1..{nvars}")
            if -literal in seen:
                tautology = True
            if literal not in seen:
                seen.add(literal)
                clause.append(literal)
        if tautology:
            continue
        if not clause:
            contradiction = True
        normalized.append(clause)
        occurring.update(abs(literal) for literal in clause)
    if expired():
        return unknown("timeout exhausted while loading CNF")
    if contradiction:
        return SolveResult("unsat", {}, 0, "contradictory input clauses")

    # Use only documented MiniSat methods.  Bounded slices avoid a background
    # interrupt thread and its lifetime/SIGINT interactions with native solvers.
    # The deadline is also checked after each potentially expensive operation.
    with _minisat()() as engine:
        for clause in normalized:
            engine.add_clause(clause)
            if expired():
                return unknown("timeout exhausted while loading native CNF")
        propagation_budget = min(10_000, max_decisions, _MAX_PROPAGATION_SLICE)
        while True:
            if expired():
                return unknown("timeout exhausted")
            remaining = max_decisions - decisions
            if remaining <= 0:
                return unknown("native decision budget exhausted")
            engine.prop_budget(propagation_budget)
            status = engine.solve_limited()
            decisions = engine.accum_stats().get("decisions", 0)
            if expired():
                return unknown("timeout exhausted")
            if decisions > max_decisions:
                return unknown("native decision budget exhausted")
            if status is None:
                # A limited call may cancel its decision trail before returning.
                # Repeating one small budget can therefore repeat the same work
                # forever, even on independent satisfiable binary clauses. Let
                # subsequent calls get further; propagation counts must not be
                # confused with the independently checked decision-count cap.
                if propagation_budget >= _MAX_PROPAGATION_SLICE:
                    return unknown("native propagation-slice budget exhausted")
                propagation_budget = min(2 * propagation_budget,
                                         _MAX_PROPAGATION_SLICE)
                continue
            if status is False:
                return SolveResult("unsat", {}, decisions,
                                   "MiniSat22 established inconsistency")
            if status is not True:
                raise RuntimeError("native SAT backend returned an invalid status")
            model = engine.get_model()
            if model is None:
                raise RuntimeError("native SAT backend returned SAT without a model")
            assignment = {v: False for v in range(1, nvars + 1)}
            for literal in model:
                if abs(literal) in occurring:
                    assignment[abs(literal)] = literal > 0
            # Validate the Boolean witness as well as the checker's independent
            # three-valued replay, avoiding trust in a malformed native model.
            for clause in normalized:
                if expired():
                    return unknown("timeout exhausted while validating native model")
                if not any(assignment[abs(lit)] == (lit > 0) for lit in clause):
                    raise RuntimeError("native SAT backend returned an invalid model")
            if expired():
                return unknown("timeout exhausted while decoding native model")
            return SolveResult("sat", assignment, decisions,
                               "MiniSat22 satisfying assignment independently checked")
