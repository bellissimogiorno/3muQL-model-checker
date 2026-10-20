"""Compare the audited closure/cache changes: python3 tools/benchmark_semantics.py.

The reference methods use an uncached closure loop and evaluator cache rule.
Every timing constructs a fresh frame/evaluator. Medians exclude theory parsing.
These timings are audit evidence, not timing-dependent regression tests.
"""
from itertools import product
from dataclasses import replace
from pathlib import Path
import sys
import json
from statistics import median
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from muql.evaluate import Evaluator
from muql.frame import Frame
from muql.syntax import Node, parse_formula
from muql.theory import Theory, load


class PriorEvaluator(Evaluator):
    def _eval(self, node, ctx, env, bound):
        key = (node, ctx, tuple(sorted(env.items())))
        if not bound and key in self._memo:
            return self._memo[key]
        result = self._compute(node, ctx, env, bound)
        if not bound:
            self._memo[key] = result
        return result


def prior_closure(theory):
    index = {p: i for i, p in enumerate(theory.points)}
    opens = {frozenset(), frozenset(range(len(theory.points)))}
    opens.update(frozenset(index[p] for p in q) for q in theory.quorums)
    pending = list(opens)
    operations = 0
    while pending:
        q = pending.pop()
        for r in tuple(opens):
            operations += 1
            union = q | r
            if union not in opens:
                opens.add(union)
                pending.append(union)
    return Frame(theory.points,
                 tuple(sorted(opens - {frozenset()}, key=lambda q: (len(q), tuple(sorted(q))))),
                 theory.stages, theory.time)


def time_case(theory, frame, formulas, repeats=7):
    atoms = {(name, t, p, args): (t + p + len(args)) % 3
             for name, arity in theory.predicates.items()
             for t, p in product(range(frame.stages), range(len(frame.points)))
             for args in product(theory.values, repeat=arity)}
    result = {"repetitions": repeats, "contexts": len(frame.contexts), "formulas": len(formulas)}
    outputs = []
    for label, cls in (("before", PriorEvaluator), ("after", Evaluator)):
        times = []
        for _ in range(repeats):
            evaluator = cls(theory, frame, atoms)
            start = perf_counter()
            out = [evaluator.eval(f, c) for f in formulas for c in frame.contexts]
            times.append(perf_counter() - start)
        result[label + "_seconds"] = times
        result[label + "_median_seconds"] = median(times)
        outputs.append(out)
    assert outputs[0] == outputs[1]
    return result


report = {"replay": {}, "closure": {}}
for path in ("examples/basics.md", "examples/fixedpoints.md", "examples/paxos.md"):
    theory = load(ROOT / path)
    frame = Frame.from_theory(theory)
    report["replay"][path] = time_case(theory, frame,
        list(theory.axioms.values()) + list(theory.properties.values()))

frame = Frame(("p",), (frozenset({0}),), 40)
theory = Theory("benchmark", ("p",), ("red", "blue"), 40, (("p",),), {"P": 0}, {}, {})
report["replay"]["40-stage monotone"] = time_case(theory, frame,
    [parse_formula("mu X. P | yesterday(X)"), parse_formula("nu X. P & tomorrow(X)")])
frame = Frame(("p",), (frozenset({0}),), 1)
theory = replace(theory, stages=1)
report["replay"]["outer-dependent nested"] = time_case(theory, frame,
    [parse_formula(s) for s in ("mu X. (mu Y. X | !Y)", "nu X. (mu Y. X | !Y)")], 30)
formula = Node("pred", value="P")
for i in range(8):
    name = f"X{i}"
    formula = Node("mu", (Node("and", (Node("not", (Node("var", value=name),)), formula)),), name)
report["replay"]["independent 8 nested"] = time_case(theory, frame, [formula], 3)

points = tuple(map(str, range(10)))
theory = Theory("closure", points, ("v",), 1, tuple((p,) for p in points), {}, {}, {})
frames = []
for label, closure in (("before", prior_closure), ("after", Frame.from_theory)):
    times = []
    for _ in range(5):
        start = perf_counter()
        frame = closure(theory)
        times.append(perf_counter() - start)
    report["closure"][label + "_seconds"] = times
    report["closure"][label + "_median_seconds"] = median(times)
    frames.append(frame)
assert frames[0] == frames[1]
report["closure"].update(points=10, generators=10, quorums=len(frame.quorums), repetitions=5)
print(json.dumps(report, indent=2))
