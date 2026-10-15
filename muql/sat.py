"""Dependency-free Boolean circuits and a deterministic SAT solver.

``Circuit`` emits Tseitin clauses: its size is linear in the number of distinct
gates, rather than exponential in a formula's Boolean expansion.  ``solve``
uses watched literals, first-UIP clause learning, saved branching phases, and
activity-based variable selection.  Configured time or decision exhaustion is
*unknown*, never an unsatisfiability result.

Literals are nonzero signed integers.  Variable ``v`` is represented by ``v``
and its negation by ``-v``.  Assignments map positive variable IDs to booleans.
"""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from numbers import Real
import time
from typing import Iterable


class Circuit:
    """Build a hash-consed Boolean circuit in conjunctive normal form.

    Variable 1 is reserved and asserted true.  Accordingly ``true == 1`` and
    ``false == -1`` are valid literals wherever a formula literal is expected.
    ``new_var`` always allocates a fresh variable, even for a repeated name.
    Names are optional display metadata available as ``names[id]``.
    """

    true = 1
    false = -1

    def __init__(self) -> None:
        self.nvars = 1
        self.clauses: list[list[int]] = [[self.true]]
        self.names: dict[int, str] = {self.true: "true"}
        self._gates: dict[tuple[object, ...], int] = {}

    def new_var(self, name: str | None = None) -> int:
        """Allocate a fresh positive literal, optionally with a display name."""
        self.nvars += 1
        if name is not None:
            self.names[self.nvars] = name
        return self.nvars

    def _validate(self, literal: int) -> None:
        if not isinstance(literal, int) or isinstance(literal, bool):
            raise TypeError("a literal must be a nonzero integer")
        if literal == 0 or abs(literal) > self.nvars:
            raise ValueError(f"literal {literal} is outside 1..{self.nvars}")

    def add_clause(self, *literals: int) -> None:
        """Assert a disjunction; an empty clause makes the circuit inconsistent."""
        seen: set[int] = set()
        satisfied = False
        for literal in literals:
            self._validate(literal)
            if literal == self.true or -literal in seen:
                satisfied = True
            elif literal != self.false:
                seen.add(literal)
        if not satisfied:
            self.clauses.append(sorted(seen))

    def and_(self, *literals: int) -> int:
        """Return a literal equivalent to the conjunction of ``literals``."""
        seen: set[int] = set()
        impossible = False
        for literal in literals:
            self._validate(literal)
            if literal == self.false or -literal in seen:
                impossible = True
            elif literal != self.true:
                seen.add(literal)
        if impossible:
            return self.false
        if not seen:
            return self.true
        if len(seen) == 1:
            return next(iter(seen))
        inputs = tuple(sorted(seen))
        key = ("and", *inputs)
        if key in self._gates:
            return self._gates[key]
        output = self.new_var()
        self._gates[key] = output
        self.clauses.extend([[-output, literal] for literal in inputs])
        self.clauses.append([output, *(-literal for literal in inputs)])
        return output

    def or_(self, *literals: int) -> int:
        """Return a literal equivalent to the disjunction of ``literals``."""
        # Sharing conjunctions also shares their De Morgan duals.
        for literal in literals:
            self._validate(literal)
        return -self.and_(*(-literal for literal in literals))

    def iff(self, left: int, right: int) -> int:
        """Return a literal equivalent to Boolean equivalence."""
        self._validate(left)
        self._validate(right)
        if left == right:
            return self.true
        if left == -right:
            return self.false
        if left == self.true:
            return right
        if right == self.true:
            return left
        if left == self.false:
            return -right
        if right == self.false:
            return -left
        # XNOR(-a, -b) == XNOR(a, b); a single negative input negates it.
        negative = (left < 0) != (right < 0)
        inputs = tuple(sorted((abs(left), abs(right))))
        key = ("iff", *inputs)
        if key not in self._gates:
            output = self.new_var()
            a, b = inputs
            self._gates[key] = output
            self.clauses.extend([
                [-output, -a, b], [-output, a, -b],
                [output, a, b], [output, -a, -b],
            ])
        output = self._gates[key]
        return -output if negative else output

    def implies(self, left: int, right: int) -> int:
        """Return a literal equivalent to material implication."""
        self._validate(left)
        self._validate(right)
        return self.or_(-left, right)


@dataclass(frozen=True)
class SolveResult:
    """A SAT result; ``assignment`` is populated only for ``status == 'sat'``."""

    status: str
    assignment: dict[int, bool]
    decisions: int
    reason: str


class _Timeout(Exception):
    pass


class _Solver:
    def __init__(self, nvars: int, deadline: float, max_decisions: int) -> None:
        self.nvars = nvars
        self.deadline = deadline
        self.max_decisions = max_decisions
        self.decisions = 0
        self.clauses: list[list[int]] = []
        self.watches: list[list[int]] = [[] for _ in range(2 * (nvars + 1))]
        self.values = [0] * (nvars + 1)
        self.levels = [0] * (nvars + 1)
        self.reasons: list[int | None] = [None] * (nvars + 1)
        self.phase = [-1] * (nvars + 1)
        self.activity = [0.0] * (nvars + 1)
        # Activity is only a heuristic.  Its floating-point values can underflow
        # during rescaling, so zero activity must not make a variable disappear
        # from the search.  Track occurrence independently of activity.
        self.occurring_variables: set[int] = set()
        self.increment = 1.0
        self.heap: list[tuple[float, int]] = []
        self.trail: list[int] = []
        self.trail_limits: list[int] = []
        self.qhead = 0
        self.work = 0

    def check_time(self, force: bool = False) -> None:
        self.work += 1
        if (force or self.work % 256 == 0) and time.monotonic() >= self.deadline:
            raise _Timeout

    @staticmethod
    def index(literal: int) -> int:
        return 2 * abs(literal) + (literal < 0)

    def value(self, literal: int) -> int:
        value = self.values[abs(literal)]
        return value if literal > 0 else -value

    def enqueue(self, literal: int, reason: int | None) -> bool:
        variable = abs(literal)
        value = 1 if literal > 0 else -1
        if self.values[variable]:
            return self.values[variable] == value
        self.values[variable] = value
        self.levels[variable] = len(self.trail_limits)
        self.reasons[variable] = reason
        self.trail.append(literal)
        return True

    def add(self, clause: list[int]) -> int:
        index = len(self.clauses)
        self.clauses.append(clause)
        self.occurring_variables.update(abs(literal) for literal in clause)
        if len(clause) >= 2:
            self.watches[self.index(clause[0])].append(index)
            self.watches[self.index(clause[1])].append(index)
        return index

    def propagate(self) -> int | None:
        """Propagate the trail, returning a conflicting clause if one exists."""
        while self.qhead < len(self.trail):
            self.check_time(force=True)
            false_literal = -self.trail[self.qhead]
            self.qhead += 1
            watched = self.watches[self.index(false_literal)]
            position = 0
            while position < len(watched):
                self.check_time()
                clause_id = watched[position]
                clause = self.clauses[clause_id]
                if clause[0] == false_literal:
                    clause[0], clause[1] = clause[1], clause[0]
                first = clause[0]
                if self.value(first) == 1:
                    position += 1
                    continue
                replacement = 2
                while replacement < len(clause):
                    self.check_time()
                    if self.value(clause[replacement]) != -1:
                        break
                    replacement += 1
                if replacement < len(clause):
                    new_literal = clause[replacement]
                    clause[1], clause[replacement] = new_literal, false_literal
                    watched[position] = watched[-1]
                    watched.pop()
                    self.watches[self.index(new_literal)].append(clause_id)
                    continue
                position += 1
                if not self.enqueue(first, clause_id):
                    return clause_id
        return None

    def bump(self, variable: int) -> None:
        self.activity[variable] += self.increment
        if self.activity[variable] > 1e100:
            self.activity = [value * 1e-100 for value in self.activity]
            self.increment *= 1e-100
            self.heap = [(-self.activity[v], v) for v in self.occurring_variables
                         if not self.values[v]]
            heapq.heapify(self.heap)
        else:
            heapq.heappush(self.heap, (-self.activity[variable], variable))

    def analyze(self, conflict: int) -> tuple[list[int], int]:
        """Derive a first unique implication point (first-UIP) learned clause."""
        learned = [0]
        seen: set[int] = set()
        pending = 0
        pivot = 0
        cursor = len(self.trail) - 1
        current_level = len(self.trail_limits)
        while True:
            for literal in self.clauses[conflict]:
                self.check_time()
                variable = abs(literal)
                if variable == abs(pivot) or variable in seen or not self.levels[variable]:
                    continue
                seen.add(variable)
                self.bump(variable)
                if self.levels[variable] == current_level:
                    pending += 1
                else:
                    learned.append(literal)
            while abs(self.trail[cursor]) not in seen:
                self.check_time()
                cursor -= 1
            pivot = self.trail[cursor]
            cursor -= 1
            seen.remove(abs(pivot))
            pending -= 1
            if pending == 0:
                break
            reason = self.reasons[abs(pivot)]
            if reason is None:
                raise RuntimeError("SAT solver invariant violated during conflict analysis")
            conflict = reason
        learned[0] = -pivot
        backtrack_level = 0
        if len(learned) > 1:
            position = max(range(1, len(learned)), key=lambda i: self.levels[abs(learned[i])])
            learned[1], learned[position] = learned[position], learned[1]
            backtrack_level = self.levels[abs(learned[1])]
        self.increment /= 0.95
        return learned, backtrack_level

    def backtrack(self, level: int) -> None:
        if len(self.trail_limits) <= level:
            return
        boundary = self.trail_limits[level]
        for literal in self.trail[boundary:]:
            self.check_time()
            variable = abs(literal)
            self.phase[variable] = self.values[variable]
            self.values[variable] = 0
            self.levels[variable] = 0
            self.reasons[variable] = None
            heapq.heappush(self.heap, (-self.activity[variable], variable))
        del self.trail[boundary:]
        del self.trail_limits[level:]
        self.qhead = min(self.qhead, len(self.trail))

    def choose(self) -> int | None:
        while self.heap:
            self.check_time()
            priority, variable = heapq.heappop(self.heap)
            if not self.values[variable] and priority == -self.activity[variable]:
                return variable
        return None

    def run(self) -> SolveResult:
        conflicts = 0
        restart_limit = 100
        next_restart = restart_limit
        while True:
            self.check_time(force=True)
            conflict = self.propagate()
            if conflict is not None:
                if not self.trail_limits:
                    self.check_time(force=True)
                    return SolveResult("unsat", {}, self.decisions, "conflict at decision level zero")
                learned, level = self.analyze(conflict)
                self.backtrack(level)
                clause_id = self.add(learned)
                if not self.enqueue(learned[0], clause_id):
                    raise RuntimeError("SAT solver invariant violated by learned clause")
                conflicts += 1
                if conflicts >= next_restart:
                    self.backtrack(0)
                    restart_limit = int(restart_limit * 1.5)
                    next_restart = conflicts + restart_limit
                continue
            variable = self.choose()
            if variable is None:
                assignment = {v: self.values[v] == 1 for v in range(1, self.nvars + 1)}
                self.check_time(force=True)
                return SolveResult("sat", assignment, self.decisions, "satisfying assignment found")
            if self.decisions >= self.max_decisions:
                return SolveResult("unknown", {}, self.decisions, "decision budget exhausted")
            self.decisions += 1
            self.trail_limits.append(len(self.trail))
            self.enqueue(variable if self.phase[variable] > 0 else -variable, None)


def _validate_limits(nvars: int, timeout: float, max_decisions: int) -> None:
    """Keep public solver limits consistent across the built-in and native paths."""
    if not isinstance(nvars, int) or isinstance(nvars, bool) or nvars < 0:
        raise ValueError("nvars must be a nonnegative integer")
    if not isinstance(max_decisions, int) or isinstance(max_decisions, bool) or max_decisions < 0:
        raise ValueError("max_decisions must be a nonnegative integer")
    if not isinstance(timeout, Real) or isinstance(timeout, bool) or timeout < 0:
        raise ValueError("timeout must be nonnegative and not NaN")
    try:
        invalid_timeout = math.isnan(timeout)
    except OverflowError as error:
        raise ValueError("timeout is too large; use math.inf for no time limit") from error
    if invalid_timeout:
        raise ValueError("timeout must be nonnegative and not NaN")


def solve(
    nvars: int,
    clauses: Iterable[Iterable[int]],
    timeout: float = 10.0,
    max_decisions: int = 100_000,
) -> SolveResult:
    """Solve a finite CNF without modifying the supplied clauses.

    ``sat`` supplies a complete assignment (unused variables default to false).
    ``unsat`` means the search has established inconsistency.  ``unknown``
    means the wall-clock timeout or decision budget was exhausted.  A zero
    decision budget still permits unit propagation; a zero timeout immediately
    returns ``unknown``.  ``timeout=math.inf`` disables the time limit.

    Invalid variable IDs, non-real/boolean/NaN/negative timeouts, and invalid
    budgets raise ``ValueError``. A clause may be empty (a contradiction).
    """
    _validate_limits(nvars, timeout, max_decisions)
    if timeout == 0:
        # The declared variable range may be large. An already expired search
        # must not allocate its O(nvars) arrays before returning unknown.
        return SolveResult("unknown", {}, 0, "timeout exhausted")
    solver = _Solver(nvars, time.monotonic() + timeout, max_decisions)
    try:
        solver.check_time(force=True)
        contradictory = False
        for supplied_clause in clauses:
            solver.check_time()
            seen: set[int] = set()
            clause: list[int] = []
            tautology = False
            for literal in supplied_clause:
                solver.check_time()
                if not isinstance(literal, int) or isinstance(literal, bool):
                    raise ValueError("every literal must be a nonzero integer")
                if literal == 0 or abs(literal) > nvars:
                    raise ValueError(f"literal {literal} is outside 1..{nvars}")
                if -literal in seen:
                    tautology = True
                if literal not in seen:
                    seen.add(literal)
                    clause.append(literal)
            if tautology:
                continue
            if not clause:
                contradictory = True
                continue
            clause_id = solver.add(clause)
            for literal in clause:
                solver.activity[abs(literal)] += 1.0
            if len(clause) == 1 and not solver.enqueue(clause[0], clause_id):
                contradictory = True
        solver.check_time(force=True)
        if contradictory:
            return SolveResult("unsat", {}, 0, "contradictory input clauses")
        solver.heap = [(-solver.activity[v], v) for v in solver.occurring_variables
                       if not solver.values[v]]
        heapq.heapify(solver.heap)
        return solver.run()
    except _Timeout:
        return SolveResult("unknown", {}, solver.decisions, "timeout exhausted")
