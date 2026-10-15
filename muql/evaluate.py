"""Independent, concrete semantics for finite 3muQL models.

The SAT compiler does not supply truth tables or evaluation routines to this
module.  Countermodels can therefore be replayed against a second implementation.
Truth values are ordered integers: ``0`` (false), ``1`` (broken), ``2`` (true).
Both broken and true are designated: satisfaction means ``value != 0``.

``mu X. body`` denotes the meet of *all* pre-fixed points, including when
``body`` is not monotone.  Bottom iteration is used only after a conservative
monotonicity check.  Small nonmonotone recurrences are enumerated exactly; a
larger unsupported recurrence raises an explicit error, never an approximation.
"""

from __future__ import annotations

from itertools import combinations, product
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping

from .syntax import Node

if TYPE_CHECKING:
    from .frame import Frame
    from .theory import Theory

FALSE, BROKEN, TRUE = 0, 1, 2
Context = tuple[int, int, int]
Atom = tuple[str, int, int, tuple[str, ...]]
Environment = Mapping[str, str]
Bindings = Mapping[str, Mapping[Context, int]]


class EvaluationError(ValueError):
    """A concrete formula or model cannot be evaluated as supplied."""


class FixedPointLimitError(EvaluationError):
    """Exact nonmonotone fixed-point enumeration exceeds its explicit budget."""


def _contains(node: Node, variable: str) -> bool:
    """Whether a fixed-point variable occurs free in a syntax tree."""
    if node.op == "var":
        return node.value == variable
    if node.op in {"mu", "nu"} and node.value == variable:
        return False
    return any(_contains(child, variable) for child in node.args)


def _polarities(node: Node, variable: str) -> frozenset[int]:
    """Conservative occurrence signs; zero means monotonicity is unknown."""
    if not _contains(node, variable):
        return frozenset()
    if node.op == "var":
        return frozenset({1})
    if node.op in {"not", "F", "FB"}:
        return frozenset(-sign for sign in _polarities(node.args[0], variable))
    if node.op in {"weak", "strong"}:
        left = {-sign for sign in _polarities(node.args[0], variable)}
        return frozenset(left | set(_polarities(node.args[1], variable)))
    if node.op in {"B", "TF", "equiv", "order", "xor", "affine", "unique", "latest"}:
        return frozenset({0})
    return frozenset(sign for child in node.args for sign in _polarities(child, variable))


class Evaluator:
    """Evaluate closed formulae on a fully specified finite model.

    Parameters
    ----------
    theory:
        Supplies the finite value domain and predicate signature.
    frame:
        Supplies named points, nonempty quorums of point indices, stages, and
        optionally ``time`` (``"finite"`` or ``"stutter"``).
    valuation:
        A complete mapping from ``(predicate, stage, point, arguments)`` to
        ``0``, ``1``, or ``2``.  A missing atom is an error.
    nonmonotone_limit:
        Maximum number of dependent contexts for exact enumeration (default 8,
        hence at most 3**8 candidate valuations per fixed-point evaluation).

    A context is ``(stage, point_index, quorum_index)``.  The point need not
    belong to the quorum.  In stutter mode the final stage has a future self
    loop.  This is a finite temporal-frame semantics, not natural-number time.
    """

    def __init__(
        self,
        theory: "Theory",
        frame: "Frame",
        valuation: Mapping[Atom, int],
        *,
        nonmonotone_limit: int = 8,
    ) -> None:
        self.theory = theory
        self.frame = frame
        self._valuation = MappingProxyType(dict(valuation))
        self.nonmonotone_limit = nonmonotone_limit
        if type(nonmonotone_limit) is not int or nonmonotone_limit < 1:
            raise ValueError("nonmonotone_limit must be a positive integer")
        self._contexts = tuple(product(range(frame.stages), range(len(frame.points)), range(len(frame.quorums))))
        self._memo: dict[tuple[Node, Context, tuple[tuple[str, str], ...]], int] = {}
        self._references: dict[Node, frozenset[str]] = {}
        self._twined_values: dict[int, int] = {}

    @property
    def valuation(self) -> Mapping[Atom, int]:
        """The immutable model snapshot; create a new evaluator to change it."""
        return self._valuation

    def eval(self, node: Node, context: Context, env: Environment | None = None) -> int:
        """Return the exact truth value of ``node`` in the supplied context."""
        if (
            len(context) != 3
            or any(type(index) is not int for index in context)
            or not 0 <= context[0] < self.frame.stages
            or not 0 <= context[1] < len(self.frame.points)
            or not 0 <= context[2] < len(self.frame.quorums)
        ):
            raise EvaluationError(f"context {context!r} is outside the finite frame")
        return self._eval(node, context, env or {}, {})

    def _term(self, node: Node, env: Environment) -> str:
        if node.op == "literal":
            result = node.value
        elif node.op == "term":
            result = env.get(str(node.value), node.value)
        else:
            raise EvaluationError(f"expected a value term, found {node.op!r}")
        if result not in self.theory.values:
            raise EvaluationError(f"value or variable {result!r} is not in the value domain")
        return str(result)

    def _future(self, time: int) -> range | tuple[int, ...]:
        if time == self.frame.stages - 1 and getattr(self.frame, "time", "finite") == "stutter":
            return (time,)
        return range(time + 1, self.frame.stages)

    def _free_references(self, node: Node) -> frozenset[str]:
        """Cache structural binding information separately from truth values."""
        if node not in self._references:
            references = (frozenset({str(node.value)}) if node.op == "var" else
                          frozenset().union(*(self._free_references(child) for child in node.args)))
            if node.op in {"mu", "nu"}:
                references = references - {str(node.value)}
            self._references[node] = references
        return self._references[node]

    def _eval(self, node: Node, ctx: Context, env: Environment, bound: Bindings) -> int:
        key = (node, ctx, tuple(sorted(env.items())))
        # An independent nested recurrence need not
        # be enumerated afresh for every candidate of the outer one. A formula
        # that reads any active binding remains uncached: its value can change
        # between candidates or iterations. Restrict this extra cache to
        # recurrences; checking every small subexpression costs more than it
        # saves in ordinary monotone iteration.
        cacheable = not bound or (node.op in {"mu", "nu"} and
                                  self._free_references(node).isdisjoint(bound))
        if cacheable and key in self._memo:
            return self._memo[key]
        result = self._compute(node, ctx, env, bound)
        if cacheable:
            self._memo[key] = result
        return result

    def _compute(self, node: Node, ctx: Context, env: Environment, bound: Bindings) -> int:
        op, args = node.op, node.args
        time, point, quorum = ctx

        def evaluate(child: Node, at: Context = ctx, variables: Environment = env) -> int:
            return self._eval(child, at, variables, bound)

        if op == "const":
            return {"f": FALSE, "b": BROKEN, "t": TRUE}[str(node.value)]
        if op == "var":
            try:
                return bound[str(node.value)][ctx]
            except KeyError as exc:
                raise EvaluationError(f"unbound fixed-point variable {node.value!r} at {ctx}") from exc
        if op == "pred":
            atom = (str(node.value), time, point, tuple(self._term(term, env) for term in args))
            try:
                result = self.valuation[atom]
            except KeyError as exc:
                raise EvaluationError(f"missing atom in concrete valuation: {atom!r}") from exc
            if type(result) is not int or result not in {FALSE, BROKEN, TRUE}:
                raise EvaluationError(f"atom {atom!r} has invalid truth value {result!r}; expected 0, 1, or 2")
            return result
        if op in {"eq", "neq"}:
            same = self._term(args[0], env) == self._term(args[1], env)
            return TRUE if same == (op == "eq") else FALSE
        if op == "not":
            return TRUE - evaluate(args[0])
        if op in {"T", "F", "B", "TB", "TF", "FB"}:
            selected = {"T": {TRUE}, "F": {FALSE}, "B": {BROKEN}, "TB": {TRUE, BROKEN}, "TF": {TRUE, FALSE}, "FB": {FALSE, BROKEN}}
            return TRUE if evaluate(args[0]) in selected[op] else FALSE
        if op in {"and", "or", "xor", "weak", "strong", "equiv", "order"}:
            left, right = evaluate(args[0]), evaluate(args[1])
            if op == "and":
                return min(left, right)
            if op == "or":
                return max(left, right)
            if op == "xor":
                return max(min(left, TRUE - right), min(TRUE - left, right))
            if op == "weak":
                return max(TRUE - left, right)
            if op == "strong":
                return max(TRUE - left, TRUE if right == TRUE else FALSE)
            if op == "equiv":
                return TRUE if left == right else FALSE
            # ASCII <= is the crisp lattice-order assertion; it does not name
            # the paper's optional three-valued internal implication <=.
            return TRUE if left <= right else FALSE
        if op in {"forall", "exists", "affine", "unique"}:
            values = [evaluate(args[0], variables={**env, str(node.value): value}) for value in self.theory.values]
            if op == "forall":
                return min(values, default=TRUE)
            if op == "exists":
                return max(values, default=FALSE)
            # Distinct witnesses violate affinity at the highest threshold
            # reached by two of them. Counting those witnesses avoids the
            # quadratic pair comparison in its defining formula.
            true_count = values.count(TRUE)
            designated_count = true_count + values.count(BROKEN)
            affine = (FALSE if true_count >= 2 else
                      BROKEN if designated_count >= 2 else TRUE)
            return affine if op == "affine" else min(affine, max(values, default=FALSE))
        if op in {"diamond", "box"}:
            values = (evaluate(args[0], (time, member, quorum)) for member in self.frame.quorums[quorum])
            return max(values, default=FALSE) if op == "diamond" else min(values, default=TRUE)
        if op in {"existsQ", "forallQ"}:
            values = (evaluate(args[0], (time, point, other)) for other in range(len(self.frame.quorums)))
            return max(values, default=FALSE) if op == "existsQ" else min(values, default=TRUE)
        if op in {"somewhere", "everywhere", "quorum", "contra"}:
            # Changing the quorum remains visible while evaluating the body.
            outer = []
            for index, members in enumerate(self.frame.quorums):
                values = [evaluate(args[0], (time, member, index)) for member in members]
                outer.append(max(values, default=FALSE) if op in {"somewhere", "contra"} else min(values, default=TRUE))
            return max(outer, default=FALSE) if op in {"somewhere", "quorum"} else min(outer, default=TRUE)
        if op == "yesterday":
            return FALSE if time == 0 else evaluate(args[0], (time - 1, point, quorum))
        if op == "tomorrow":
            if time + 1 < self.frame.stages:
                return evaluate(args[0], (time + 1, point, quorum))
            return evaluate(args[0]) if getattr(self.frame, "time", "finite") == "stutter" else FALSE
        if op in {"once", "past", "historically"}:
            times = range(time + 1) if op == "past" else range(time)
            values = (evaluate(args[0], (previous, point, quorum)) for previous in times)
            return min(values, default=TRUE) if op == "historically" else max(values, default=FALSE)
        if op in {"sometime", "forever"}:
            values = (evaluate(args[0], (future, point, quorum)) for future in self._future(time))
            return max(values, default=FALSE) if op == "sometime" else min(values, default=TRUE)
        if op == "infinitely":
            return evaluate(Node("forever", (Node("sometime", args),)))
        if op == "ultimately":
            return evaluate(Node("sometime", (Node("everywhere", (Node("forever", args),)),)))
        if op == "latest":
            target, body = self._term(args[0], env), args[1]
            for previous in range(time - 1, -1, -1):
                at = (previous, point, quorum)
                if any(evaluate(body, at, {**env, str(node.value): value}) == TRUE for value in self.theory.values):
                    return TRUE if evaluate(body, at, {**env, str(node.value): target}) == TRUE else FALSE
            return FALSE
        if op in {"mu", "nu"}:
            return self._fixed(node, ctx, env, bound)
        if op == "twined":
            count = int(str(node.value))
            if count < 1:
                raise EvaluationError("twined requires a positive integer")
            if count in self._twined_values:
                return self._twined_values[count]
            requested = count
            # Repetition contributes no extra intersection.  Any smaller
            # selection extends to this size and its intersection can only
            # shrink, so checking distinct maximal selections is sufficient.
            count = min(count, len(self.frame.quorums))
            # A common member witnesses every intersection. Keep this check
            # independent of Frame.twined while avoiding an exponential replay
            # of frames the compiler can certify immediately.
            common = set(self.frame.quorums[0])
            for quorum in self.frame.quorums[1:]:
                common.intersection_update(quorum)
            if common:
                self._twined_values[requested] = TRUE
                return TRUE
            for selection in combinations(self.frame.quorums, count):
                if not set.intersection(*(set(quorum) for quorum in selection)):
                    self._twined_values[requested] = FALSE
                    return FALSE
            self._twined_values[requested] = TRUE
            return TRUE
        raise EvaluationError(f"unsupported formula operation {op!r}")

    def _leader_body(self, body: Node, variable: str) -> Node | None:
        """Recognize the paper's nonmonotone ``!diamond(A & X)`` schema."""
        if body.op != "not" or body.args[0].op != "diamond":
            return None
        conjunction = body.args[0].args[0]
        if conjunction.op != "and":
            return None
        left, right = conjunction.args
        reference = Node("var", value=variable)
        if left == reference:
            left, right = right, left
        if right == reference and not _contains(left, variable):
            return left
        return None

    def _dependencies(self, node: Node, variable: str, ctx: Context) -> set[Context]:
        """Overapproximate contexts at which this body can read ``variable``."""
        if not _contains(node, variable):
            return set()
        op, args = node.op, node.args
        time, point, quorum = ctx
        if op == "var":
            return {ctx}
        if op in {"mu", "nu"}:
            # A nested recurrence can read an outer variable at any context.
            # Keeping all contexts is conservative and avoids assumptions about
            # whether the inner body's own recurrence can reach that context.
            return set(self._contexts)
        if op in {"diamond", "box"}:
            contexts = ((time, member, quorum) for member in self.frame.quorums[quorum])
        elif op in {"existsQ", "forallQ"}:
            contexts = ((time, point, index) for index in range(len(self.frame.quorums)))
        elif op in {"somewhere", "everywhere", "quorum", "contra"}:
            contexts = ((time, member, index) for index, members in enumerate(self.frame.quorums) for member in members)
        elif op == "yesterday":
            contexts = ((time - 1, point, quorum),) if time else ()
        elif op == "tomorrow":
            contexts = ((time + 1, point, quorum),) if time + 1 < self.frame.stages else ((ctx,) if getattr(self.frame, "time", "finite") == "stutter" else ())
        elif op in {"once", "past", "historically", "latest"}:
            contexts = ((previous, point, quorum) for previous in range(time + (op == "past")))
            args = (args[-1],)
        elif op in {"sometime", "forever"}:
            contexts = ((future, point, quorum) for future in self._future(time))
        elif op == "infinitely":
            return self._dependencies(Node("forever", (Node("sometime", args),)), variable, ctx)
        elif op == "ultimately":
            return self._dependencies(Node("sometime", (Node("everywhere", (Node("forever", args),)),)), variable, ctx)
        else:
            contexts = (ctx,)
        return {dependency for at in contexts for child in args for dependency in self._dependencies(child, variable, at)}

    def _fixed(self, node: Node, ctx: Context, env: Environment, bound: Bindings) -> int:
        variable, body = str(node.value), node.args[0]
        if not _contains(body, variable):
            return self._eval(body, ctx, env, bound)
        special = self._leader_body(body, variable) if node.op == "mu" else None
        if special is not None:
            time, point, quorum = ctx
            values = {member: self._eval(special, (time, member, quorum), env, bound) for member in self.frame.quorums[quorum]}
            if point not in values:
                return TRUE - max(values.values(), default=FALSE)
            if any(value == TRUE for member, value in values.items() if member != point):
                return FALSE
            return BROKEN if any(value != FALSE for value in values.values()) else TRUE

        reachable = {ctx}
        pending = [ctx]
        while pending:
            for dependency in self._dependencies(body, variable, pending.pop()):
                if dependency not in reachable:
                    reachable.add(dependency)
                    pending.append(dependency)
        contexts = tuple(sorted(reachable))
        monotone = _polarities(body, variable) <= {1}
        least = node.op == "mu"

        if monotone:
            current = {at: FALSE if least else TRUE for at in contexts}
            # A chain on {f < b < t}**N can change at most 2*N times.
            for _ in range(2 * len(contexts) + 1):
                bindings = {**bound, variable: current}
                following = {at: self._eval(body, at, env, bindings) for at in contexts}
                if current == following:
                    return current[ctx]
                current = following
            raise EvaluationError("internal monotonicity check failed to converge")

        if len(contexts) > self.nonmonotone_limit:
            raise FixedPointLimitError(
                f"exact {node.op} {variable} requires enumerating 3**{len(contexts)} assignments; "
                f"the nonmonotone limit is {self.nonmonotone_limit} dependent contexts"
            )
        answer = TRUE if least else FALSE
        for assignment in product((FALSE, BROKEN, TRUE), repeat=len(contexts)):
            candidate = dict(zip(contexts, assignment))
            bindings = {**bound, variable: candidate}
            if all(
                (self._eval(body, at, env, bindings) <= candidate[at]) if least
                else (candidate[at] <= self._eval(body, at, env, bindings))
                for at in contexts
            ):
                answer = min(answer, candidate[ctx]) if least else max(answer, candidate[ctx])
        return answer
