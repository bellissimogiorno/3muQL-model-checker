"""Exhaustive small-model checks of the three-valued CNF translation.

These tests fix every atomic cell with SAT unit clauses.  The resulting output
thresholds must equal the independent concrete evaluator and, for core and
fixed-point cases, separately computed truth tables.  Fixed-point oracles below
enumerate the *entire* frame, independently of the compiler's reachable-context
optimization.
"""

from itertools import product
import unittest

from muql.compile import Compiler, ResourceLimit
from muql.evaluate import Evaluator
from muql.frame import Frame
from muql.sat import solve
from muql.syntax import Node, parse_formula
from muql.theory import Theory


def theory_for(frame, values=("red", "blue")):
    return Theory("test", frame.points, values, frame.stages,
                  tuple(tuple(frame.points[p] for p in q) for q in frame.quorums),
                  {"P": 0, "Q": 0, "R": 1}, {}, {}, time=frame.time)


def unary(op, node):
    return Node(op, (node,))


def binary(op, left, right):
    return Node(op, (left, right))


def scalar(op, *args):
    """Direct three-element lattice truth tables, independent of CNF bits."""
    if op == "not":
        return 2 - args[0]
    tests = {"T": {2}, "F": {0}, "B": {1}, "TB": {1, 2}, "TF": {0, 2}, "FB": {0, 1}}
    if op in tests:
        return 2 if args[0] in tests[op] else 0
    a, b = args
    return {
        "and": lambda: min(a, b), "or": lambda: max(a, b),
        "weak": lambda: max(2 - a, b),
        "strong": lambda: max(2 - a, 2 if b == 2 else 0),
        "equiv": lambda: 2 if a == b else 0,
        "order": lambda: 2 if a <= b else 0,
        "xor": lambda: max(min(a, 2 - b), min(2 - a, b)),
    }[op]()


def global_oracle(node, context, frame, valuation, bound=None):
    """Deliberately simple exhaustive semantics for recurrence regression cases."""
    bound = bound or {}
    op, args = node.op, node.args
    time, point, quorum = context
    ev = lambda child, at=context, bindings=bound: global_oracle(child, at, frame, valuation, bindings)
    if op == "pred":
        return valuation[(node.value, time, point, ())]
    if op == "const":
        return {"f": 0, "b": 1, "t": 2}[node.value]
    if op == "var":
        return bound[node.value][context]
    if op in {"not", "T", "F", "B", "TB", "TF", "FB"}:
        return scalar(op, ev(args[0]))
    if op in {"and", "or", "weak", "strong", "equiv", "order", "xor"}:
        return scalar(op, ev(args[0]), ev(args[1]))
    if op in {"diamond", "box"}:
        values = [ev(args[0], (time, p, quorum)) for p in frame.quorums[quorum]]
        return max(values) if op == "diamond" else min(values)
    if op in {"existsQ", "forallQ"}:
        values = [ev(args[0], (time, point, q)) for q in range(len(frame.quorums))]
        return max(values) if op == "existsQ" else min(values)
    if op in {"somewhere", "everywhere", "quorum", "contra"}:
        groups = [[ev(args[0], (time, p, q)) for p in members]
                  for q, members in enumerate(frame.quorums)]
        inner = min if op in {"everywhere", "quorum"} else max
        outer = min if op in {"everywhere", "contra"} else max
        return outer(inner(group) for group in groups)
    if op == "yesterday":
        return 0 if time == 0 else ev(args[0], (time - 1, point, quorum))
    if op == "tomorrow":
        if time + 1 < frame.stages:
            return ev(args[0], (time + 1, point, quorum))
        return ev(args[0]) if frame.time == "stutter" else 0
    if op in {"mu", "nu"}:
        answer = 2 if op == "mu" else 0
        for values in product(range(3), repeat=len(frame.contexts)):
            mapping = dict(zip(frame.contexts, values))
            updated = {**bound, node.value: mapping}
            images = [ev(args[0], at, updated) for at in frame.contexts]
            if op == "mu" and all(a <= b for a, b in zip(images, values)):
                answer = min(answer, mapping[context])
            if op == "nu" and all(a >= b for a, b in zip(images, values)):
                answer = max(answer, mapping[context])
        return answer
    raise AssertionError(f"oracle lacks {op}")


class CompiledSemanticsTests(unittest.TestCase):
    def assert_models(self, frame, nodes, expected=None, *, max_mu_contexts=8):
        theory = theory_for(frame)
        compiler = Compiler(theory, frame, max_mu_contexts=max_mu_contexts)
        results = {(node, context): compiler.eval(node, context)
                   for node in nodes for context in frame.contexts}
        cells = tuple(sorted(compiler.cells))
        self.assertLessEqual(len(cells), 6, "exhaustive test accidentally became too large")
        for values in product(range(3), repeat=len(cells)):
            valuation = dict(zip(cells, values))
            fixed = []
            for key, value in valuation.items():
                low, high = compiler.cells[key]
                fixed.extend([[low if value >= 1 else -low], [high if value == 2 else -high]])
            answer = solve(compiler.circuit.nvars, compiler.circuit.clauses + fixed)
            self.assertEqual(answer.status, "sat", (values, answer.reason))
            evaluator = Evaluator(theory, frame, valuation, nonmonotone_limit=max_mu_contexts)
            disagreement = []
            for (node, context), pair in results.items():
                bits = [answer.assignment[abs(bit)] == (bit > 0) for bit in pair]
                self.assertIn(tuple(bits), {(False, False), (True, False), (True, True)}, str(node))
                got = sum(bits)
                wanted = evaluator.eval(node, context)
                detail = (str(node), context, valuation)
                self.assertEqual(got, wanted, detail)
                if expected is not None:
                    self.assertEqual(got, expected(node, context, valuation), detail)
                disagreement.extend(-bit if truth else bit
                                    for bit, truth in zip(pair, (wanted >= 1, wanted == 2)))
            # It is not sufficient that one model happens to have the expected
            # outputs: rule out every assignment disagreeing at any output bit.
            opposite = solve(compiler.circuit.nvars, compiler.circuit.clauses + fixed + [disagreement])
            self.assertEqual(opposite.status, "unsat", (valuation, opposite.reason))

    def test_all_boolean_and_three_valued_tables(self):
        frame = Frame(("p",), (frozenset({0}),), 1)
        p, q = Node("pred", value="P"), Node("pred", value="Q")
        nodes = [unary(op, p) for op in ("not", "T", "F", "B", "TB", "TF", "FB")]
        nodes += [binary(op, p, q) for op in ("and", "or", "weak", "strong", "equiv", "order", "xor")]
        def expected(node, context, valuation):
            args = [valuation[(a.value, 0, 0, ())] for a in node.args]
            return scalar(node.op, *args)
        self.assert_models(frame, nodes, expected)

    def test_quantifiers_affinity_and_unique_preserve_broken(self):
        frame = Frame(("p",), (frozenset({0}),), 1)
        nodes = [parse_formula(f"{op} v. R(v)") for op in ("forall", "exists", "affine", "unique")]
        def expected(node, context, valuation):
            a, b = (valuation[("R", 0, 0, (v,))] for v in ("red", "blue"))
            affine = 2 - min(a, b)
            return {"forall": min(a, b), "exists": max(a, b), "affine": affine,
                    "unique": min(max(a, b), affine)}[node.op]
        self.assert_models(frame, nodes, expected)

    def test_context_modalities_keep_the_selected_quorum(self):
        frame = Frame(("a", "b"), (frozenset({0}), frozenset({1}), frozenset({0, 1})), 1)
        p = Node("pred", value="P")
        modalities = ("diamond", "box", "existsQ", "forallQ", "somewhere", "everywhere", "quorum", "contra")
        nodes = [unary(op, p) for op in modalities]
        # Exercise every public spelling through parsing as well as direct ASTs.
        named = ("diamond", "somewhere", "box", "everywhere", "quorum",
                 "someQuorumEveryPoint", "contra", "everyQuorumSomePoint",
                 "someQuorumSomePoint", "everyQuorumEveryPoint")
        nodes += [parse_formula(f"{op}({body})") for op in named
                  for body in ("P", "diamond(P)", "box(P)")]
        nodes += [unary(outer, binary("weak", p, unary(inner, p)))
                  for outer in modalities for inner in ("diamond", "box")]
        self.assert_models(frame, nodes, lambda n, c, v: global_oracle(n, c, frame, v))

    def test_temporal_operators_and_sugar_on_both_boundary_modes(self):
        for mode in ("finite", "stutter"):
            frame = Frame(("p",), (frozenset({0}),), 3, mode)
            p = Node("pred", value="P")
            nodes = [unary(op, p) for op in ("yesterday", "tomorrow", "once", "past", "historically",
                                            "sometime", "forever", "infinitely", "ultimately")]
            def expected(node, context, valuation):
                values = [valuation[("P", t, 0, ())] for t in range(3)]
                def future(t):
                    return [2] if t == 2 and mode == "stutter" else list(range(t + 1, 3))
                def apply(op, t):
                    if op == "yesterday": return 0 if t == 0 else values[t - 1]
                    if op == "tomorrow": return values[t + 1] if t < 2 else (values[t] if mode == "stutter" else 0)
                    if op == "once": return max(values[:t], default=0)
                    if op == "past": return max(values[:t + 1], default=0)
                    if op == "historically": return min(values[:t], default=2)
                    if op == "sometime": return max((values[s] for s in future(t)), default=0)
                    if op == "forever": return min((values[s] for s in future(t)), default=2)
                    if op == "infinitely": return min((apply("sometime", s) for s in future(t)), default=2)
                    if op == "ultimately": return max((apply("forever", s) for s in future(t)), default=0)
                    raise AssertionError(op)
                return apply(node.op, context[0])
            with self.subTest(mode=mode):
                self.assert_models(frame, nodes, expected)

    def test_latest_is_crisp_and_ignores_broken_candidates(self):
        frame = Frame(("p",), (frozenset({0}),), 3)
        nodes = [parse_formula(f"latest v = {value}. R(v)") for value in ("red", "blue")]
        def expected(node, context, valuation):
            desired = node.args[0].value
            for time in range(context[0] - 1, -1, -1):
                candidates = {v for v in ("red", "blue") if valuation[("R", time, 0, (v,))] == 2}
                if candidates:
                    return 2 if desired in candidates else 0
            return 0
        self.assert_models(frame, nodes, expected)

    def test_scalar_mu_nu_including_all_nonpositive_connectives(self):
        frame = Frame(("p",), (frozenset({0}),), 1)
        x, p = Node("var", value="X"), Node("pred", value="P")
        bodies = [x] + [unary(op, x) for op in ("not", "T", "F", "B", "TB", "TF", "FB")]
        bodies += [binary(op, left, right) for op in ("and", "or", "weak", "strong", "equiv", "order", "xor")
                   for left, right in ((x, p), (p, x))]
        nodes = [Node(op, (body,), "X") for body in bodies for op in ("mu", "nu")]
        self.assert_models(frame, nodes, lambda n, c, v: global_oracle(n, c, frame, v))

    def test_general_fixed_points_match_full_frame_enumeration(self):
        frame = Frame(("a", "b"), (frozenset({0}), frozenset({0, 1})), 1)
        nodes = [parse_formula(text) for text in (
            "mu X. !(P & X)",
            "nu X. !(P | X)",
            "mu X. !diamond(P & X)",
            "mu X. !diamond((!!P) & X)",
            "mu X. !box(P | X)",
            "nu X. !existsQ(X)",
            "mu X. (P | existsQ(box(X)))",
        )]
        self.assert_models(frame, nodes, lambda n, c, v: global_oracle(n, c, frame, v))

    def test_monotone_temporal_recursion(self):
        frame = Frame(("a",), (frozenset({0}),), 3)
        nodes = [parse_formula(text) for text in (
            "mu X. (P | yesterday(X))", "nu X. (P & tomorrow(X))",
            "mu X. !(P & yesterday(X))", "nu X. !(P | tomorrow(X))",
        )]
        self.assert_models(frame, nodes, lambda n, c, v: global_oracle(n, c, frame, v))

    def test_nested_binding_and_cache_cannot_capture_outer_fixed_value(self):
        frame = Frame(("a",), (frozenset({0}),), 1)
        nodes = [parse_formula(text) for text in (
            "mu X. (mu Y. (X | !Y))",
            "nu X. (mu Y. (X | !Y))",
            "mu X. (nu Y. (X & !Y))",
            "nu X. (nu Y. (X & !Y))",
            "mu X. (P | (mu Y. (X & Y)))",
            "nu X. (P & (nu Y. (X | Y)))",
            "mu X. (B(X) | (nu Y. (X & !Y)))",
        )]
        self.assert_models(frame, nodes, lambda n, c, v: global_oracle(n, c, frame, v))

    def test_value_environment_is_part_of_cache_key(self):
        frame = Frame(("p",), (frozenset({0}),), 1)
        nodes = [parse_formula(text) for text in (
            "forall v. (mu X. (R(v) | X))",
            "exists v. (mu X. (R(v) | X))",
            "forall v. (mu X. !(R(v) & X))",
            "exists v. (mu X. !(R(v) & X))",
        )]
        self.assert_models(frame, nodes)

    def test_nonmonotone_resource_limit_is_explicit(self):
        frame = Frame(("a", "b"), (frozenset({0, 1}),), 1)
        compiler = Compiler(theory_for(frame), frame, max_mu_contexts=1)
        with self.assertRaises(ResourceLimit):
            compiler.eval(parse_formula("mu X. !box(X)"), (0, 0, 0))


class FrameTests(unittest.TestCase):
    def test_union_closure_does_not_invent_intersections_or_supersets(self):
        original = Frame(("a", "b", "c", "d"), (frozenset({0, 1}), frozenset({1, 2})), 1)
        frame = Frame.from_theory(theory_for(original))
        self.assertEqual(set(frame.quorums), {frozenset({0, 1}), frozenset({1, 2}),
                                              frozenset({0, 1, 2}), frozenset({0, 1, 2, 3})})
        self.assertNotIn(frozenset({1}), frame.quorums)
        self.assertNotIn(frozenset({0, 1, 3}), frame.quorums)

    def test_twined_is_n_way_intersection_with_repetition(self):
        frame = Frame(("a", "b", "c"), (frozenset({0, 1}), frozenset({0, 2}),
                                           frozenset({1, 2}), frozenset({0, 1, 2})), 1)
        self.assertTrue(frame.twined(1))
        self.assertTrue(frame.twined(2))
        self.assertFalse(frame.twined(3))
        self.assertFalse(frame.twined(20))

    def test_contexts_include_points_outside_the_quorum(self):
        frame = Frame(("a", "b"), (frozenset({0}), frozenset({0, 1})), 2)
        self.assertEqual(len(frame.contexts), 8)
        self.assertIn((0, 1, 0), frame.contexts)


if __name__ == "__main__":
    unittest.main()
