"""Independent, direct denotations of the nine printed protocol theories.

These checks deliberately do not use the compiler's truth helpers or the
evaluator's syntax traversal for their expected values. The reference formulas
were transcribed afresh from Paxos Figures 11/12 and section 6.1, and companion
Figures 3/10/11/13/14. They compare every named axiom and property, including on
invalid valuations; merely checking a few successful models would miss many
translation mistakes. The finite temporal conventions are explicit below.
"""

from dataclasses import replace
from functools import lru_cache
from itertools import product
from pathlib import Path
import random
import unittest

from muql.evaluate import Evaluator
from muql.frame import Frame
from muql.theory import load


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
F, B, T = range(3)
WEAK = ((T, T, T), (B, B, T), (F, B, T))
STRONG = ((T, T, T), (B, B, T), (F, F, T))


def weak(a, b):
    return WEAK[a][b]


def strong(a, b):
    return STRONG[a][b]


def meet(xs):
    return min(xs, default=T)


def join(xs):
    return max(xs, default=F)


def crisp(condition):
    return T if condition else F


def affine(row):
    # Companion Fig. 6; the diagonal terms are t.
    return meet(weak(min(a, b), crisp(i == j))
                for i, a in enumerate(row) for j, b in enumerate(row))


@lru_cache(None)
def leader_unique(row):
    # Direct meet of all pre-fixed functions of X |-> !diamond(leader & X).
    # Outside-quorum coordinates do not affect the outer diamond.
    prefixed = []
    for candidate in product(range(3), repeat=len(row)):
        body = T - join(min(a, b) for a, b in zip(row, candidate))
        if all(body <= x for x in candidate):
            prefixed.append(candidate)
    return join(meet(x[i] for x in prefixed) for i in range(len(row)))


class SourceModel:
    def __init__(self, theory, frame, valuation, natural_constant=False):
        self.theory, self.frame, self.valuation = theory, frame, valuation
        self.values = theory.values
        self.points = range(len(frame.points))
        self.natural_constant = natural_constant

    def atom(self, pred, n, p, v=None):
        args = () if v is None else (v,)
        return self.valuation[pred, 0 if self.natural_constant else n, p, args]

    def some(self, fn):
        return join(fn(p) for p in self.points)

    def all(self, fn):
        return meet(fn(p) for p in self.points)

    def quorum(self, fn):
        return join(meet(fn(p) for p in q) for q in self.frame.quorums)

    def contra(self, fn):
        return meet(join(fn(p) for p in q) for q in self.frame.quorums)

    def correct(self, pred, n, p):
        return crisp(all(self.atom(pred, n, p, v) != B for v in self.values))

    def faulty(self, pred, n, p):
        return crisp(all(self.atom(pred, n, p, v) == B for v in self.values))

    def future(self, n):
        if self.natural_constant:
            # Used only for time-invariant bodies in the explicit infinite
            # witness: one representative stands for every strict future time.
            return (n + 1,)
        return range(n + 1, self.frame.stages) if n < self.frame.stages - 1 else (n,)

    def ultimately(self, fn, n):
        return join(self.all(lambda p: meet(fn(k, p) for k in self.future(j)))
                    for j in self.future(n))

    def infinitely(self, fn, n):
        return meet(join(fn(k) for k in self.future(j)) for j in self.future(n))

    def latest(self, fn, n, v):
        # Source Figure 6: only strictly earlier *true* events reset recency.
        times = [k for k in range(n) if any(fn(k, w) == T for w in self.values)]
        return crisp(bool(times) and fn(times[-1], v) == T)

    def no_previous(self, fn, n):
        return crisp(not any(fn(k, v) == T for k in range(n) for v in self.values))

    def values_at(self, name, ctx):
        n, p, qi = ctx
        a = lambda pred, v=None: self.atom(pred, n, p, v)
        row = lambda pred: [a(pred, v) for v in self.values]
        sq = lambda pred, v: self.some(lambda x: self.atom(pred, n, x, v))
        q = lambda pred, v: self.quorum(lambda x: self.atom(pred, n, x, v))
        cq = lambda pred, v: self.contra(lambda x: self.atom(pred, n, x, v))
        every = lambda pred, v: self.all(lambda x: self.atom(pred, n, x, v))
        intersection = crisp(all(set.intersection(*(set(q) for q in qs))
                                 for qs in product(self.frame.quorums, repeat=3)))

        if name == "voting":
            voteq = self.quorum(lambda x: self.atom("vote", n, x))
            notvoteq = self.quorum(lambda x: T - self.atom("vote", n, x))
            return {
                "Intersection": intersection,
                "Observe?": weak(a("observe"), voteq),
                "ObserveNot?": weak(T - a("observe"), notvoteq),
                "Observe!": strong(voteq, a("observe")),
                "ObserveNot!": strong(notvoteq, T - a("observe")),
                "Correct": self.quorum(lambda x: crisp(self.atom("vote", n, x) != B)),
                "Agreement": crisp(not (any(self.atom("observe", n, x) == T for x in self.points)
                                         and any(self.atom("observe", n, x) == F for x in self.points))),
                "UnanimousTrueDelivery": strong(voteq, self.all(lambda x: self.atom("observe", n, x))),
                "UnanimousFalseDelivery": strong(notvoteq, self.all(lambda x: T - self.atom("observe", n, x))),
            }
        if name in {"bracha", "bracha_weakened"}:
            result = {
                "Intersection": intersection,
                "BrDeliver?": meet(weak(a("dlvr", v), q("ready", v)) for v in self.values),
                "BrReady?": meet(weak(a("ready", v), q("echo", v)) for v in self.values),
                "BrEcho?": meet(weak(a("echo", v), sq("bcst", v)) for v in self.values),
                "BrEchoAffine": affine(row("echo")),
                "BrBroadcastUnique": min(join(sq("bcst", v) for v in self.values),
                                         affine([sq("bcst", v) for v in self.values])),
                "BrReady!": meet(weak(q("echo", v), a("ready", v)) for v in self.values),
                "BrEcho!": meet(weak(sq("bcst", v), join(row("echo"))) for v in self.values),
                "BrReady!!": meet(weak(cq("ready", v), a("ready", v)) for v in self.values),
                "BrCorrect": min(self.quorum(lambda x: self.correct("ready", n, x)),
                                 self.quorum(lambda x: self.correct("echo", n, x))),
                "BrReadyUniform": max(self.correct("ready", n, p), self.faulty("ready", n, p)),
                "BrEchoUniform": max(self.correct("echo", n, p), self.faulty("echo", n, p)),
                "BrBroadcastUniform": max(self.all(lambda x: self.correct("bcst", n, x)),
                                          self.all(lambda x: self.faulty("bcst", n, x))),
                "BrValidity": meet(weak(sq("bcst", v), every("dlvr", v)) for v in self.values),
            }
            delivery = meet(weak(q("ready", v), a("dlvr", v)) for v in self.values)
            if name == "bracha_weakened":
                result.update({"BrDeliverExistential!": weak(join(q("ready", v) for v in self.values), join(row("dlvr"))),
                              "OriginalDeliverForward": delivery})
            else:
                result.update({"BrDeliver!": delivery, "BrNoDup": affine(row("dlvr")),
                              "BrIntegrity": meet(weak(a("dlvr", v), sq("bcst", v)) for v in self.values),
                              "BrConsistency": affine([sq("dlvr", v) for v in self.values]),
                              "BrTotality": meet(weak(sq("dlvr", v), every("dlvr", v)) for v in self.values)})
            return result
        if name == "crusader":
            result = {
                "Intersection": intersection,
                "CaEcho1?": meet(strong(a("echo1", v), sq("input", v)) for v in self.values),
                "CaEcho2?": meet(weak(a("echo2", v), q("echo1", v)) for v in self.values),
                "CaOutput?": meet(weak(a("output", v), q("echo2", v)) for v in ("zero", "one")),
                "CaOutputHalf?": weak(a("output", "half"), min(q("echo1", "zero"), q("echo1", "one"))),
                "CaEcho1!": meet(weak(max(a("input", v), cq("echo1", v)), a("echo1", v)) for v in self.values),
                "CaEcho2!": weak(join(q("echo1", v) for v in self.values), join(row("echo2"))),
                "CaOutput!": meet(weak(q("echo2", v), a("output", v)) for v in self.values),
                "CaOutputHalf!": weak(min(q("echo1", "zero"), q("echo1", "one")), a("output", "half")),
                "CaCorrect": self.quorum(lambda x: meet(self.correct(pred, n, x) for pred in self.theory.predicates)),
                "CaInput": min(max(min(a("input", "zero"), T-a("input", "one")),
                                   min(T-a("input", "zero"), a("input", "one"))), T-a("input", "half")),
                "CaEcho2Affine": affine(row("echo2")),
                "CaAgree": meet(strong(min(sq("output", v), sq("output", w)), crisp(v == w or "half" in (v, w)))
                                for v, w in product(self.values, repeat=2)),
                "CaValid1": meet(strong(min(crisp(every("input", v) != F), a("output", w)), crisp(v == w))
                                 for v, w in product(self.values, repeat=2)),
                "CaValid2": meet(strong(sq("output", v), max(sq("input", v), crisp(v == "half"))) for v in self.values),
                "CaLive": self.all(lambda x: join(self.atom("output", n, x, v) for v in self.values)),
            }
            for pred, label in (("input", "Input"), ("echo1", "Echo1"), ("echo2", "Echo2"), ("output", "Output")):
                result["Ca" + label + "Uniform"] = max(self.correct(pred, n, p), self.faulty(pred, n, p))
            return result
        if name.startswith("simple_"):
            crashes = name in {"simple_crashes", "simple_eventual_crashes"}
            eventual = name in {"simple_eventual", "simple_eventual_crashes"}
            arrow = weak if crashes else strong
            accept = lambda k, x: arrow(self.some(lambda y: self.atom("propose", k, y)), self.atom("accept", k, x))
            decide = lambda k, x: arrow(min(self.atom("propose", k, x), self.some(lambda y: self.atom("accept", k, y))),
                                        self.atom("decide", k, x))
            result = {
                "SimpAccept?": strong(a("accept"), self.some(lambda x: self.atom("propose", n, x))),
                "SimpDecide?": strong(a("decide"), min(a("propose"), self.some(lambda x: self.atom("accept", n, x)))),
                "SimpAccept!": self.ultimately(accept, n) if eventual else accept(n, p),
                "SimpDecide!": self.ultimately(decide, n) if eventual else decide(n, p),
                "NoInventedDecision": strong(a("decide"), a("propose")),
            }
            if crashes:
                for pred in self.theory.predicates:
                    result["Uncrashed_" + pred] = self.contra(lambda x: crisp(self.atom(pred, n, x) != B))
            else:
                result["Correct"] = meet(crisp(a(pred) != B) for pred in self.theory.predicates)
            if eventual:
                result["EventualProgressRule"] = self.ultimately(lambda k, x: arrow(self.atom("propose", k, x), self.atom("decide", k, x)), n)
            else:
                result["ProposerDecidesOrCrashes" if crashes else "ProposerDecides"] = arrow(a("propose"), a("decide"))
            return result

        # Paxos source Figures 11 and 12; all temporal functions above operate
        # directly on rows and never evaluate package ASTs.
        simpler = name == "paxos_simpler"
        prefix = "SPax" if simpler else "Pax"
        writes = []
        for v in self.values:
            options = []
            for selected in self.frame.quorums:
                acc = lambda k, w: join(self.atom("accept", k, x, w) for x in selected)
                choice = max(self.latest(acc, n, v), min(a("propose", v), self.no_previous(acc, n)))
                if not simpler:
                    choice = min(choice, meet(join(self.atom("send", n, x, w) for w in self.values) for x in selected))
                options.append(choice)
            writes.append(strong(a("write", v), min(a("leader"), join(options))))
        result = {
            prefix + "Propose?": meet(strong(a("propose", v), min(a("leader"), T if simpler else crisp(v != "undef"))) for v in self.values),
            prefix + "Write?": meet(writes),
            prefix + "Accept?": meet(strong(a("accept", v), sq("write", v)) for v in self.values),
            prefix + "Accept!": self.ultimately(lambda k, x: weak(join(self.some(lambda y: self.atom("write", k, y, v)) for v in self.values),
                                                                        join(self.atom("accept", k, x, v) for v in self.values)), n),
            ("S" if simpler else "") + "LdrExist": min(crisp(a("leader") != B), crisp(self.some(lambda x: self.atom("leader", n, x)) == T)),
            ("S" if simpler else "") + "LdrCorrect": self.infinitely(lambda k: self.some(lambda x: min(self.atom("leader", k, x),
                                       meet(self.correct(pred, k, x) for pred in ("propose", "write", "decide")))), n),
            prefix + "2Twined": meet(strong(q("accept", v), cq("accept", v)) for v in self.values),
            "Validity": meet(strong(a("decide", v), join(self.some(lambda x: min(self.atom("leader", k, x), self.atom("propose", k, x, v)))
                                                         for k in range(n + 1))) for v in self.values),
            "Agreement": meet(strong(min(join(self.some(lambda x: self.atom("decide", k, x, v)) for k in range(n + 1)),
                                         sq("decide", w)), crisp(v == w)) for v, w in product(self.values, repeat=2)),
            "Termination": self.infinitely(lambda k: self.all(lambda x: join(self.atom("decide", k, x, v) for v in self.values)), n),
        }
        if simpler:
            result.update({
                "SPaxDecide?": meet(strong(a("decide", v), q("accept", v)) for v in self.values),
                "SPaxWrite!": self.ultimately(lambda k, x: weak(self.atom("leader", k, x), join(self.atom("write", k, x, v) for v in self.values)), n),
                "SPaxDecide!": self.ultimately(lambda k, x: weak(join(self.quorum(lambda y: self.atom("accept", k, y, v)) for v in self.values),
                                                                   join(self.atom("decide", k, x, v) for v in self.values)), n),
                "SPaxPCorrect": self.quorum(lambda x: self.correct("accept", n, x)),
                "SPaxWrite01": affine([sq("write", v) for v in self.values]),

            })
        else:
            result.update({
                "PaxSend?": meet(strong(a("send", v), min(join(sq("propose", w) for w in self.values),
                                  max(self.latest(lambda k, w: self.atom("accept", k, p, w), n, v),
                                      min(self.no_previous(lambda k, w: self.atom("accept", k, p, w), n), crisp(v == "undef"))))) for v in self.values),
                "PaxDecideL?": meet(strong(a("leader"), strong(a("decide", v), q("accept", v))) for v in self.values),
                "PaxDecide-not-L?": meet(strong(T-a("leader"), strong(a("decide", v), self.some(lambda x: min(self.atom("leader", n, x), self.atom("decide", n, x, v))))) for v in self.values),
                "PaxPropose!": weak(a("leader"), join(row("propose"))),
                "PaxSend!": self.ultimately(lambda k, x: weak(join(self.some(lambda y: self.atom("propose", k, y, v)) for v in self.values), join(self.atom("send", k, x, v) for v in self.values)), n),
                "PaxWrite!": self.ultimately(lambda k, x: weak(min(self.atom("leader", k, x), self.quorum(lambda y: join(self.atom("send", k, y, v) for v in self.values)), join(self.atom("propose", k, x, v) for v in self.values)), join(self.atom("write", k, x, v) for v in self.values)), n),
                "PaxDecideL!": self.ultimately(lambda k, x: weak(min(self.atom("leader", k, x), join(self.quorum(lambda y: self.atom("accept", k, y, v)) for v in self.values)), join(self.atom("decide", k, x, v) for v in self.values)), n),
                "PaxDecide-not-L!": self.ultimately(lambda k, x: weak(min(T-self.atom("leader", k, x), self.some(lambda y: min(self.atom("leader", k, y), join(self.atom("decide", k, y, v) for v in self.values)))), join(self.atom("decide", k, x, v) for v in self.values)), n),
                "LdrUniq": leader_unique(tuple(self.atom("leader", n, x) for x in sorted(self.frame.quorums[qi]))),
                "PaxPCorrect": meet(self.quorum(lambda x: self.correct(pred, n, x)) for pred in ("propose", "send", "accept", "write", "decide")),
                "PaxPropose01": affine(row("propose")), "PaxWrite01": affine(row("write")),
                "PaxNontriv": crisp(any(v != "undef" for v in self.values)),
                "DecidingQuorum": self.infinitely(lambda k: self.quorum(lambda x: crisp(join(self.atom("decide", k, x, v) for v in self.values) == T)), n),
            })
        return result


class PaperTranscriptionAuditTests(unittest.TestCase):
    def test_basics_tutorial_exhaustively_against_truth_tables(self):
        theory = load(EXAMPLES / "basics.md")
        frame = Frame.from_theory(theory)
        for ps, qs, rs in product(range(3), repeat=3):
            data = {(pred, 0, 0, ()): val for pred, val in (("P", ps), ("Q", qs), ("R", rs))}
            data.update({("choice", 0, 0, (v,)): B for v in theory.values})
            expected = {
                "BrokenIsDesignated": B, "BrokenIsTrue": F,
                "ExcludedMiddle": max(ps, T-ps), "CrispExcludedMiddle": crisp(ps != B),
                "WeakDefinition": T, "StrongDefinition": T, "WeakCurrying": T,
                "StrongCurrying": crisp(strong(min(ps, qs), rs) == strong(ps, strong(qs, rs))),
                "DesignatedUnique": B, "UniqueIsCrisp": F,
                "TrueWitness": F, "AtMostOneActuallyTrue": T,
            }
            evaluator = Evaluator(theory, frame, data)
            self.assertEqual(set(expected), set(theory.properties))
            for label, formula in theory.properties.items():
                self.assertEqual(evaluator.eval(formula, (0, 0, 0)), expected[label], (ps, qs, rs, label))

    def test_fixedpoint_tutorial_exhaustive_pulses(self):
        theory = load(EXAMPLES / "fixedpoints.md")
        frame = Frame.from_theory(theory)
        for pulse in product(range(3), repeat=3):
            data = {("pulse", n, 0, ()): value for n, value in enumerate(pulse)}
            evaluator = Evaluator(theory, frame, data)
            for ctx in frame.contexts:
                for label, formula in theory.properties.items():
                    # Prefix/suffix min/max recurrences are finite monotone
                    # chains. For F(X), the meet of prefixed values {b,t} is
                    # b while F(b)=f, so the proposed unfolding identity fails.
                    expected = F if label == "UnfoldingRequiresMonotonicity" else T
                    self.assertEqual(evaluator.eval(formula, ctx), expected, (pulse, ctx, label))

    def test_semitopology_tutorial_exhaustively(self):
        theory = load(EXAMPLES / "semitopology.md")
        frame = Frame.from_theory(theory)
        self.assertEqual(frame.quorums, (frozenset({0}), frozenset({0, 1, 2})))
        for live in product(range(3), repeat=3):
            evaluator = Evaluator(theory, frame, {("live", 0, p, ()): value for p, value in enumerate(live)})
            for ctx in frame.contexts:
                for label, formula in theory.properties.items():
                    expected = crisp(min(live[p] for p in frame.quorums[ctx[2]]) == min(live)) if label == "CurrentBoxIsGlobal" else T
                    self.assertEqual(evaluator.eval(formula, ctx), expected, (live, ctx, label))

    def test_example_axioms_and_properties_against_independent_denotations(self):
        rng = random.Random(251221137)
        names = ("voting", "bracha", "bracha_weakened", "crusader", "simple_reliable", "simple_crashes",
                 "simple_eventual", "simple_eventual_crashes", "paxos", "paxos_simpler")
        for name in names:
            theory = load(EXAMPLES / (name + ".md"))
            frame = Frame.from_theory(theory)
            keys = [(pred, n, p, vs) for pred, arity in theory.predicates.items()
                    for n, p, vs in product(range(frame.stages), range(len(frame.points)), product(theory.values, repeat=arity))]
            formulas = {**theory.axioms, **theory.properties}
            for trial in range(15):
                data = {key: (trial if trial < 3 else rng.randrange(3)) for key in keys}
                reference, actual = SourceModel(theory, frame, data), Evaluator(theory, frame, data)
                for ctx in frame.contexts:
                    expected = reference.values_at(name, ctx)
                    self.assertEqual(set(expected), set(formulas), name)
                    for label, formula in formulas.items():
                        with self.subTest(theory=name, trial=trial, context=ctx, formula=label):
                            self.assertEqual(actual.eval(formula, ctx), expected[label])

    def test_bracha_counterexample_with_direct_tables_only(self):
        singleton = load(EXAMPLES / "bracha_weakened.md")
        normal_scope = load(EXAMPLES / "bracha.md")
        four_points = replace(singleton, points=normal_scope.points, quorums=normal_scope.quorums)
        for theory in (singleton, four_points):
            frame = Frame.from_theory(theory)
            data = {(pred, 0, p, (v,)): T if v == "red" else F
                    for pred in ("bcst", "echo", "ready") for v in theory.values
                    for p in range(len(frame.points))}
            for p in range(len(frame.points)):
                data.update({("dlvr", 0, p, ("red",)): F, ("dlvr", 0, p, ("blue",)): B})
            for ctx in frame.contexts:
                result = SourceModel(theory, frame, data).values_at("bracha_weakened", ctx)
                for label in theory.axioms:
                    self.assertNotEqual(result[label], F, label)
                self.assertEqual(result["BrValidity"], F)
                self.assertEqual(result["OriginalDeliverForward"], F)

    def test_simpler_paxos_agreement_with_a_crashed_follower_directly(self):
        theory = replace(load(EXAMPLES / "paxos_simpler.md"), points=("L", "C"), quorums=(("L", "C"),))
        frame = Frame.from_theory(theory)
        data = {(pred, 0, p, vs): F for pred, arity in theory.predicates.items()
                for p, vs in product(range(2), product(theory.values, repeat=arity))}
        data["leader", 0, 0, ()] = T
        for pred in ("propose", "write", "accept", "decide"):
            data[pred, 0, 0, ("red",)] = T
        data["accept", 0, 1, ("red",)] = T
        for value in theory.values:
            data["decide", 0, 1, (value,)] = B
        reference = SourceModel(theory, frame, data, natural_constant=True)
        # At zero the proposal branch applies; at positive times the latest
        # red acceptance applies. These cases cover all natural-number times
        # because every atomic row and every future rule body is constant.
        for n, p in product((0, 1, 2, 10), range(2)):
            result = reference.values_at("paxos_simpler", (n, p, 0))
            for label in theory.axioms:
                self.assertNotEqual(result[label], F, (n, p, label))
            self.assertEqual(result["Agreement"], B)



if __name__ == "__main__":
    unittest.main()
