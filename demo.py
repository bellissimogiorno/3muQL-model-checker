#!/usr/bin/env python3
"""Run fixed-frame checks and automatic model searches without dependencies.

Run ``python demo.py`` from any working directory. Use ``--brief`` to hide
atomic tables, ``--search-only`` for automatic searches, or ``--output DIR``
to save complete reports and replayable search countermodels.
The process exits nonzero if any expected result changes or remains unknown.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import json
import math
from pathlib import Path
import shlex
import sys
from time import monotonic

from muql import (Theory, check, format_theory, load, parse_formula, search,
                  witness_theory)

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    explanation: str
    theory: Theory
    expected: dict[str, str]
    properties: tuple[str, ...] | None = None
    expected_status: str = "checked"
    search_bounds: dict[str, int] | None = None
    command: tuple[str, ...] = ()


def _baseline(filename: str, *, failures: tuple[str, ...] = (), explanation: str = "") -> Scenario:
    theory = load(ROOT / "examples" / f"{filename}.md")
    return Scenario(
        filename, theory.name, explanation, theory,
        {name: "counterexample" if name in failures else "holds" for name in theory.properties},
    )


def fixed_scenarios() -> list[Scenario]:
    """Keep published formulas and tutorial modifications visibly separate."""
    cases = [
        _baseline("voting", explanation="All original voting axioms; four participants and three-person quorums."),
        _baseline("bracha", explanation="All original Bracha broadcast axioms; two payloads."),
        _baseline("crusader", explanation="All original Crusader axioms; zero, half and one are distinct payloads."),
        _baseline("simple_reliable"),
        _baseline("simple_crashes"),
        _baseline("simple_eventual"),
        _baseline("simple_eventual_crashes"),
        _baseline("paxos", explanation="All 20 Figure 11 axioms. Temporal results concern the displayed finite stutter frame."),
        _baseline("paxos_simpler", explanation=(
            "All 12 Figure 12 axioms. Agreement combines its decision premises with conjunction. "
            "All three correctness properties hold in scope. See docs/spax-agreement.md.")),
        _baseline("bracha_weakened", failures=("OriginalDeliverForward", "BrValidity"), explanation=(
            "The companion paper's Section 4.3 existential delivery weakening admits a wrong-payload "
            "crashed witness. This contradicts the weakening claim, not the original Bracha theorem.")),
    ]
    voting = cases[0].theory
    bracha = cases[1].theory
    crusader = cases[2].theory
    simple = cases[3].theory
    paxos = cases[7].theory
    spax = replace(cases[8].theory, points=("a",), quorums=(("a",),), stages=1)
    cases.extend([
        Scenario("voting_without_correct", "Voting: remove the correct quorum", "Change: drop Correct. Faulty votes can support opposite observations.",
                 voting.without("Correct"), {"Agreement": "counterexample"}, ("Agreement",)),
        Scenario("voting_unreliable", "Voting: weaken both delivery arrows", "Change: weaken ⇀ to → in ObserveForward and ObserveNotForward. Agreement survives, but guaranteed true delivery does not.",
                 voting.replace("ObserveForward", "quorum(vote()) -> observe()").replace("ObserveNotForward", "quorum(!vote()) -> !observe()"),
                 {"Agreement": "holds", "UnanimousTrueDelivery": "counterexample"}, ("Agreement", "UnanimousTrueDelivery")),
        Scenario("bracha_without_echo_affine", "Bracha: remove echo uniqueness", "Change: drop BrEchoAffine. Different values can become delivered.",
                 bracha.without("BrEchoAffine"), {"BrConsistency": "counterexample"}, ("BrConsistency",)),
        Scenario("bracha_without_relay", "Bracha: remove the ready relay", "Change: drop BrReadyRelay. Delivery at one participant need not spread to everyone.",
                 bracha.without("BrReadyRelay"), {"BrTotality": "counterexample"}, ("BrTotality",)),
        Scenario("crusader_weak_echo_back", "Crusader: weaken echo justification", "Change: replace strong echo1 justification by weak implication. A crashed input can support a true echo.",
                 crusader.replace("CaEcho1Back", "forall v. echo1(v) -> someQuorumSomePoint(input(v))"), {"CaValid2": "counterexample"}, ("CaValid2",)),
        Scenario("crusader_without_echo_affine", "Crusader: remove second-echo uniqueness", "Change: drop CaEcho2Affine. Opposite binary outputs become possible.",
                 crusader.without("CaEcho2Affine"), {"CaAgree": "counterexample"}, ("CaAgree",)),
        Scenario("simple_without_progress", "Simple: remove decision progress", "Change: drop SimpDecide_forward. A valid proposal and acceptance need not lead to a decision.",
                 simple.without("SimpDecide_forward"), {"ProposerDecides": "counterexample"}, ("ProposerDecides",)),
        Scenario("paxos_unused_axioms", "Paxos: remove two proof-unused axioms", "Change: drop PaxSend_back and PaxPropose01 (paper Section 8.1.1). All selected properties still hold in scope.",
                 paxos.without("PaxSend_back", "PaxPropose01"), {name: "holds" for name in paxos.properties}),
        Scenario("spax_without_write_affine", "Simpler Paxos: remove write uniqueness", "Scope: one participant, two values, one stutter stage. Change: drop SPaxWrite01. Agreement now fails: two true decisions can disagree.",
                 spax.without("SPaxWrite01"), {"Agreement": "counterexample"}, ("Agreement",)),
        Scenario("spax_without_accept_back", "Simpler Paxos: remove acceptance justification", "Scope: one participant, two values, one stutter stage. Change: drop SPaxAccept_back. A value can be decided without a proposal.",
                 spax.without("SPaxAccept_back"), {"Validity": "counterexample"}, ("Validity",)),
    ])
    cases.extend([
        Scenario("crusader_output_not_unique", "Crusader: test output uniqueness", "No axiom is removed. Add the tutorial conjecture affine v. output(v). The paper intentionally allows a binary output together with half.",
                 replace(crusader, properties={"OutputAffine": parse_formula("affine v. output(v)")}),
                 {"OutputAffine": "counterexample"}),
        Scenario("paxos_finite_boundary", "Paxos: expose the terminal boundary", "Change only time stutter to time finite. Strict temporal progress makes the terminal frame inconsistent. This is a boundary artifact, not a paper counterexample.",
                 replace(paxos, time="finite"), {}, expected_status="inconsistent"),
    ])
    tutorials = [
        _baseline("basics", failures=("BrokenIsTrue", "CrispExcludedMiddle", "StrongCurrying", "UniqueIsCrisp", "TrueWitness"),
                  explanation="Truth-value and quantifier experiments. Intentionally false conjectures expose three-valued distinctions."),
        _baseline("fixedpoints", failures=("UnfoldingRequiresMonotonicity",),
                  explanation="Monotone recurrences and a nonpositive mu. A pre-fixed meet need not satisfy an unfolding equality."),
        _baseline("semitopology", failures=("CurrentBoxIsGlobal",),
                  explanation="Quorum generators are union-closed, not upward-closed. Current-quorum box differs from ∀Q□."),
    ]
    return [*tutorials, *cases]


def search_scenarios() -> list[Scenario]:
    """Small, reproducible searches whose equivalent CLI commands are shown."""
    def case(key, title, explanation, filename, bounds, expected, *, drop=(), properties=None):
        theory = load(ROOT / filename, for_search=True).without(*drop)
        command = ["python", "-m", "muql", "search", filename]
        for name in drop:
            command.extend(("--drop", name))
        for name in properties or ():
            command.extend(("--property", name))
        for name, value in bounds.items():
            command.extend(("--" + name.replace("_", "-"), str(value)))
        command.extend(("--solver", "builtin"))
        return Scenario(key, title, explanation, theory, expected, properties,
                        "complete" if "holds" in expected.values() else "counterexample",
                        bounds, tuple(command))

    return [
        case("search_choices", "Search: start with just the logic",
             "No frame is supplied. Two-valued choices need not be unique: search discovers a two-value countermodel.",
             "examples/search/choices.md", {"max_points": 1, "max_values": 2, "max_stages": 1},
             {"AtMostOne": "counterexample"}),
        case("search_voting", "Search: Voting across a bounded frame class",
             "Keep every axiom. Search all permitted quorum families and domain sizes; all three properties hold within these bounds.",
             "examples/voting.md", {"max_points": 3, "max_values": 2, "max_stages": 2},
             {"Agreement": "holds", "UnanimousTrueDelivery": "holds", "UnanimousFalseDelivery": "holds"}),
        case("search_voting_without_correct", "Search: discover a Voting countermodel",
             "Drop Correct. Search chooses the participants, quorum family and valuation that falsify agreement.",
             "examples/voting.md", {"max_points": 3, "max_values": 2, "max_stages": 2},
             {"Agreement": "counterexample"}, drop=("Correct",), properties=("Agreement",)),
        case("search_paxos_simpler", "Search: Simpler Paxos agreement",
             "Keep all twelve axioms. Agreement holds throughout the bounded class, using the theory's stutter convention.",
             "examples/paxos_simpler.md", {"max_points": 2, "max_values": 2, "max_stages": 3},
             {"Agreement": "holds"}, properties=("Agreement",)),
        case("search_paxos_simpler_without_write_affine", "Search: remove Simpler Paxos write uniqueness",
             "Drop SPaxWrite01. Search supplies a frame and two disagreeing decisions; every retained axiom is valid.",
             "examples/paxos_simpler.md", {"max_points": 2, "max_values": 2, "max_stages": 3},
             {"Agreement": "counterexample"}, drop=("SPaxWrite01",), properties=("Agreement",)),
    ]


def scenarios() -> list[Scenario]:
    """The complete default tour, including both checking and model finding."""
    return [*fixed_scenarios(), *search_scenarios()]


def _compact_witness(model) -> str:
    """Print every atom, grouping value arguments into readable predicate rows."""
    location = model.failure
    lines = [
        f"    False at stage {location['time']}, point {location['point']}, quorum {{{','.join(location['quorum'])}}}.",
        "    Every retained axiom is valid; this complete valuation was independently replayed.",
    ]
    rows: dict[tuple[int, str, str], list[str]] = {}
    for cell in model.valuation:
        key = (cell["time"], cell["point"], cell["predicate"])
        args = ",".join(cell["args"])
        rows.setdefault(key, []).append(f"{args}={cell['value']}" if args else cell["value"])
    for (stage, point, predicate), values in sorted(rows.items()):
        lines.append(f"    {stage:>2}  {point:<7} {predicate:<10} " + ", ".join(values))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", action="store_true", help="show outcomes and explanations without atomic tables")
    parser.add_argument("--search-only", action="store_true", help="run only the five automatic model-search examples")
    parser.add_argument("--output", type=Path, metavar="DIR", help="save reports and countermodel JSON; include concrete theories for search witnesses")
    parser.add_argument("--timeout", type=float, default=30.0, metavar="SECONDS", help="seconds per fixed-check phase or per complete automatic search (default: 30)")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a finite positive number")
    start = monotonic()
    cases = search_scenarios() if args.search_only else scenarios()
    failures = []
    property_count = 0
    countermodel_count = 0
    print("3μQL Explorer — executable paper tour", flush=True)
    print("Automatic searches choose frames within bounds; fixed checks use their displayed scopes.")
    print("Stutter frames are not natural-number-time encodings. See docs/semantics.md.")
    print("The tour includes deliberate failures, axiom experiments, and complete countermodels.")
    for number, case in enumerate(cases, 1):
        print(f"\n[{number}/{len(cases)}] {case.title}", flush=True)
        if case.explanation:
            print(case.explanation)
        theory = case.theory
        if case.search_bounds is None:
            print(f"Scope: points={len(theory.points)}, values={len(theory.values)}, stages={theory.stages}, time={theory.time}; axioms={len(theory.axioms)}.")
            report = check(theory, properties=case.properties, timeout=args.timeout)
        else:
            bounds = case.search_bounds
            print(f"Bounds: 1..{bounds['max_points']} points; {max(1, len(theory.values))}..{bounds['max_values']} values; "
                  f"1..{bounds['max_stages']} stages; at most 8 quorums; time={theory.time}.")
            print(f"Budget: {args.timeout:g} seconds total; 1000 frames. Solver: builtin.")
            print("Command (from the package root):")
            print("  " + shlex.join((*case.command, "--timeout", f"{args.timeout:g}")))
            report = search(theory, properties=case.properties, timeout=args.timeout,
                            solver="builtin", **bounds)
            print(f"  Frames checked: {report.stats['frames']}; "
                  f"with axiom models: {report.stats['consistent_frames']}; "
                  f"incomplete checks: {report.stats['unknown_frames']}.")
            print("  " + report.reason)
        actual = {result.name: result.status for result in report.properties}
        matched = report.status == case.expected_status and actual == case.expected
        if report.status == "inconsistent":
            print("  INCONSISTENT: " + report.reason)
        if not matched:
            failures.append(case.key)
            print(f"  UNEXPECTED: report={report.status}; expected={case.expected}; actual={actual}")
            if report.reason:
                print(f"  {report.reason}")
        for result in report.properties:
            property_count += 1
            label = {"holds": "holds within search bounds" if case.search_bounds is not None else "holds in scope",
                     "counterexample": "counterexample", "unknown": "UNKNOWN",
                     "inconsistent": "no axiom model within bounds"}[result.status]
            print(f"  {result.name}: {label}")
            if result.countermodel is not None:
                countermodel_count += 1
                if case.search_bounds is not None:
                    scope = result.countermodel.scope
                    quorums = " ".join("{" + ",".join(quorum) + "}" for quorum in scope["quorums"])
                    print(f"    Found scope: {len(scope['points'])} point(s), {len(scope['values'])} value(s), "
                          f"{scope['stages']} stage(s); quorums {quorums}.")
                if not args.brief:
                    print(_compact_witness(result.countermodel))
        print("  Expected outcomes confirmed." if matched else "  Regression or incomplete search.", flush=True)
        if args.output:
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / f"{case.key}.json").write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
            for result in report.properties:
                if result.countermodel is not None:
                    (args.output / f"{case.key}--{result.name}.countermodel.json").write_text(
                        json.dumps(result.countermodel.to_dict(), indent=2) + "\n", encoding="utf-8")
                    if case.search_bounds is not None:
                        concrete = witness_theory(theory, result.countermodel)
                        theory_path = args.output / f"{case.key}--{result.name}.md"
                        theory_path.write_text(format_theory(concrete), encoding="utf-8")
                        witness_path = args.output / f"{case.key}--{result.name}.countermodel.json"
                        print("  Replay: " + shlex.join(("python", "-m", "muql", "replay",
                                                        str(theory_path.resolve()), str(witness_path.resolve()))))
    elapsed = monotonic() - start
    print(f"\n{len(cases)} scenarios, {property_count} property results, {countermodel_count} countermodels; {elapsed:.2f}s.")
    if args.output:
        print(f"Complete reports and witnesses saved to {args.output.resolve()}")
    if failures:
        print("FAILED scenarios: " + ", ".join(failures))
        return 1
    print("All expected outcomes confirmed. Edit a theory or use --drop/--replace to continue exploring.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"demo: {error}", file=sys.stderr)
        raise SystemExit(2)
    except KeyboardInterrupt:
        print("demo: interrupted", file=sys.stderr)
        raise SystemExit(3)
