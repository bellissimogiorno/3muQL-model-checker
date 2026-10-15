"""Semantic model-search tests using tiny mathematical cases and witnesses."""

from copy import deepcopy
from itertools import combinations, product
import unittest
from unittest.mock import patch

from muql.checker import PropertyResult, check, replay
from muql.search import format_theory, search, witness_theory
from muql.theory import TheoryError, loads


def template(body):
    return loads("```muql\n" + body + "\n```", for_search=True)


def bounded(theory, **overrides):
    options = dict(max_points=1, max_values=len(theory.values), max_stages=1,
                   max_quorums=1, max_frames=100, timeout=10, solver="builtin")
    options.update(overrides)
    return search(theory, **options)


def results(report):
    return {item.name: item for item in report.properties}


def all_labeled_families(npoints):
    """Independent powerset oracle; no production frame generator is used."""
    full = frozenset(range(npoints))
    proper = [frozenset(group) for size in range(1, npoints)
              for group in combinations(range(npoints), size)]
    for included in product((False, True), repeat=len(proper)):
        family = {full} | {group for group, take in zip(proper, included) if take}
        if all(left | right in family for left in family for right in family):
            yield family


class SemanticSearchTests(unittest.TestCase):
    def test_nullary_modal_results_match_independent_all_valuations_oracle(self):
        theory = template("""predicate P/0
axiom Crisp: everywhere(TF(P))
property Global: somewhere(P) -> everywhere(P)
property Overlap: quorum(P) -> contra(P)
property Reflexive: somewhere(P) -> somewhere(P)""")
        expected = {name: "holds" for name in theory.properties}
        # Enumerate every labeled family on 1/2 points and all 3-valued atoms.
        # Compute the three goals directly from meets/joins, independently of
        # AST evaluation, compilation, the solver, and isomorphism pruning.
        for npoints in (1, 2):
            for family in all_labeled_families(npoints):
                for atoms in product(range(3), repeat=npoints):
                    if 1 in atoms:  # Exactly the Crisp axiom's models.
                        continue
                    some, every = max(atoms), min(atoms)
                    quorum = max(min(atoms[p] for p in group) for group in family)
                    contra = min(max(atoms[p] for p in group) for group in family)
                    values = {"Global": max(2 - some, every),
                              "Overlap": max(2 - quorum, contra),
                              "Reflexive": max(2 - some, some)}
                    for name, value in values.items():
                        if value == 0:
                            expected[name] = "counterexample"
        report = bounded(theory, max_points=2, max_quorums=3)
        self.assertTrue(report.complete)
        self.assertEqual({item.name: item.status for item in report.properties}, expected)
        for item in report.properties:
            if item.countermodel is None:
                continue
            witness = item.countermodel
            atoms = {row["point"]: {"f": 0, "b": 1, "t": 2}[row["value"]]
                     for row in witness.valuation}
            self.assertNotIn(1, atoms.values())
            if item.name == "Global":
                value = max(2 - max(atoms.values()), min(atoms.values()))
            else:
                quorum = max(min(atoms[p] for p in group) for group in witness.scope["quorums"])
                contra = min(max(atoms[p] for p in group) for group in witness.scope["quorums"])
                value = max(2 - quorum, contra)
            self.assertEqual(value, 0)

    def test_point_growth_reveals_a_model_impossible_at_one_point(self):
        theory = template("predicate P/0\nproperty Goal: somewhere(P) -> everywhere(P)")
        small = bounded(theory)
        self.assertTrue(small.complete)
        self.assertEqual(small.properties[0].status, "holds")
        larger = bounded(theory, max_points=2)
        self.assertEqual(larger.properties[0].status, "counterexample")
        self.assertEqual(len(larger.properties[0].countermodel.scope["points"]), 2)

    def test_value_growth_reveals_inequality(self):
        theory = template("property Goal: forall x. forall y. x == y")
        self.assertEqual(bounded(theory).properties[0].status, "holds")
        larger = bounded(theory, max_values=2)
        self.assertEqual(larger.properties[0].status, "counterexample")
        self.assertEqual(len(larger.properties[0].countermodel.scope["values"]), 2)

    def test_explicit_named_values_stay_distinct_when_the_domain_grows(self):
        theory = template("values red blue\nproperty Goal: forall x. (x == red) | (x == blue)")
        self.assertEqual(bounded(theory).properties[0].status, "holds")
        larger = bounded(theory, max_values=3)
        witness = larger.properties[0].countermodel
        self.assertIsNotNone(witness)
        self.assertEqual(witness.scope["values"][:2], ["red", "blue"])
        self.assertEqual(len(set(witness.scope["values"])), 3)
        self.assertTrue(replay(witness_theory(theory, witness), witness))

    def test_stage_growth_reveals_a_strict_past(self):
        theory = template("property Goal: !once(t)")
        self.assertEqual(bounded(theory).properties[0].status, "holds")
        larger = bounded(theory, max_stages=2)
        witness = larger.properties[0].countermodel
        self.assertIsNotNone(witness)
        self.assertEqual(witness.scope["stages"], 2)
        self.assertEqual(witness.failure["time"], 1)

    def test_quorum_growth_reveals_disjoint_opens(self):
        theory = template("property Goal: twined(2)")
        small = bounded(theory, max_points=2, max_quorums=2)
        self.assertTrue(small.complete)
        self.assertEqual(small.properties[0].status, "holds")
        large = bounded(theory, max_points=2, max_quorums=3)
        witness = large.properties[0].countermodel
        self.assertIsNotNone(witness)
        self.assertEqual(len(witness.scope["quorums"]), 3)
        self.assertTrue(any(not set(left).intersection(right)
                            for left in witness.scope["quorums"]
                            for right in witness.scope["quorums"]))

    def test_declared_frame_does_not_restrict_model_search(self):
        theory = template("""points original
values red
stages 9
quorums {original}
predicate P/0
property Goal: somewhere(P) -> everywhere(P)""")
        report = bounded(theory, max_points=2)
        witness = report.properties[0].countermodel
        self.assertIsNotNone(witness)
        self.assertEqual(witness.scope["stages"], 1)
        self.assertEqual(witness.scope["values"], ["red"])
        self.assertEqual(len(witness.scope["points"]), 2)

    def test_time_convention_is_preserved(self):
        finite = bounded(template("property Goal: !sometime(t)"))
        stutter = bounded(template("time stutter\nproperty Goal: !sometime(t)"))
        self.assertEqual(finite.properties[0].status, "holds")
        self.assertEqual(stutter.properties[0].status, "counterexample")
        self.assertEqual(stutter.properties[0].countermodel.scope["time"], "stutter")

    def test_multiple_properties_can_have_different_minimal_witnesses(self):
        theory = template("""predicate P/0
property Points: somewhere(P) -> everywhere(P)
property Values: forall x. forall y. x == y
property Time: !once(t)""")
        report = bounded(theory, max_points=2, max_values=2, max_stages=2)
        self.assertEqual(report.status, "counterexample")
        found = results(report)
        self.assertEqual({item.status for item in report.properties}, {"counterexample"})
        self.assertEqual(len(found["Points"].countermodel.scope["points"]), 2)
        self.assertEqual(len(found["Values"].countermodel.scope["values"]), 2)
        self.assertEqual(found["Time"].countermodel.scope["stages"], 2)
        for item in report.properties:
            candidate = witness_theory(theory, item.countermodel)
            self.assertEqual(set(candidate.properties), set(theory.properties))
            self.assertTrue(replay(candidate, item.countermodel))

    def test_nonvacuity_requires_an_axiom_model_somewhere_in_bounds(self):
        theory = template("""predicate P/0
axiom TwoKinds: somewhere(T(P)) & somewhere(F(P))
property Goal: t""")
        impossible = bounded(theory)
        self.assertTrue(impossible.complete)
        self.assertEqual(impossible.status, "inconsistent")
        self.assertEqual(impossible.properties[0].status, "inconsistent")
        possible = bounded(theory, max_points=2)
        self.assertTrue(possible.complete)
        self.assertEqual(possible.properties[0].status, "holds")
        self.assertGreater(possible.stats["inconsistent_frames"], 0)
        self.assertIsNotNone(possible.consistency_model)

    def test_no_property_selection_finds_an_axiom_model(self):
        theory = template("predicate P/0\naxiom TrueP: T(P)\nproperty Ignored: f")
        report = bounded(theory, properties=[])
        self.assertEqual(report.status, "satisfiable")
        self.assertEqual(report.properties, [])
        self.assertTrue(report.consistency_model)
        self.assertTrue(all(row["value"] == "t" for row in report.consistency_model))
        impossible = bounded(template("axiom False: f"), max_points=2)
        self.assertEqual(impossible.status, "inconsistent")
        self.assertTrue(impossible.complete)


class SearchResourceTests(unittest.TestCase):
    def test_frame_budget_leaves_unsearched_scope_unknown(self):
        theory = template("predicate P/0\nproperty Goal: somewhere(P) -> everywhere(P)")
        report = bounded(theory, max_points=2, max_frames=1)
        self.assertEqual(report.status, "unknown")
        self.assertFalse(report.complete)
        self.assertEqual(report.properties[0].status, "unknown")
        self.assertEqual(report.stats["frames"], 1)
        self.assertIsNotNone(report.consistency_model)

    def test_compilation_limit_does_not_become_a_bounded_proof(self):
        theory = template("predicate P/0\nproperty Goal: T(P) | !T(P)")
        report = bounded(theory, max_nodes=1)
        self.assertEqual(report.status, "unknown")
        self.assertFalse(report.complete)
        self.assertEqual(report.properties[0].status, "unknown")

    def test_zero_search_time_produces_no_claim(self):
        report = bounded(template("property Goal: t"), timeout=0)
        self.assertEqual(report.status, "unknown")
        self.assertEqual(report.stats["frames"], 0)
        self.assertEqual(report.properties[0].status, "unknown")

    def test_later_counterexample_resolves_earlier_unknown_obligation(self):
        theory = template("""predicate P/0
property FailsLater: somewhere(P) -> everywhere(P)
property Always: t""")

        def limited_first_frame(candidate, properties, **kwargs):
            checked = check(candidate, properties, **kwargs)
            if len(candidate.points) == 1:
                checked.status = "unknown"
                checked.properties = [PropertyResult("FailsLater", "unknown", reason="test decision limit"),
                                      next(item for item in checked.properties if item.name == "Always")]
            return checked

        # The first frame's deliberately unresolved query should not prevent a
        # later genuine countermodel from discharging that same obligation.
        with patch("muql.search.check", side_effect=limited_first_frame):
            report = bounded(theory, max_points=2)
        self.assertEqual(report.stats["unknown_frames"], 1)
        self.assertEqual(results(report)["FailsLater"].status, "counterexample")
        self.assertEqual(results(report)["Always"].status, "holds")
        self.assertEqual(report.status, "complete")
        self.assertTrue(report.complete)

    def test_later_holds_does_not_erase_an_earlier_unknown_scope(self):
        theory = template("predicate P/0\nproperty Unfinished: P -> P\nproperty Always: t")

        def limited_first_frame(candidate, properties, **kwargs):
            checked = check(candidate, properties, **kwargs)
            if len(candidate.points) == 1:
                checked.status = "unknown"
                checked.properties = [PropertyResult("Unfinished", "unknown", reason="test decision limit"),
                                      next(item for item in checked.properties if item.name == "Always")]
            return checked

        with patch("muql.search.check", side_effect=limited_first_frame):
            report = bounded(theory, max_points=2)
        self.assertEqual(report.status, "unknown")
        self.assertFalse(report.complete)
        self.assertEqual(results(report)["Unfinished"].status, "unknown")
        self.assertEqual(results(report)["Always"].status, "holds")

    def test_invalid_bounds_and_property_selections_are_rejected(self):
        theory = template("values red blue\nproperty Goal: t")
        bad = [{"max_points": True}, {"max_points": 0}, {"max_values": 1},
               {"max_values": 2.5}, {"max_stages": -1}, {"max_quorums": 0},
               {"max_frames": False}, {"max_nodes": 0}, {"max_mu_contexts": 0},
               {"max_decisions": -1}, {"max_decisions": True},
               {"timeout": float("nan")}, {"timeout": float("inf")},
               {"timeout": -1}, {"timeout": True}, {"solver": "missing"},
               {"properties": "Goal"}, {"properties": [1]}, {"properties": ["Absent"]}]
        for override in bad:
            with self.subTest(override=override), self.assertRaises(ValueError):
                bounded(theory, **override)


class SearchWitnessTests(unittest.TestCase):
    def test_exported_witness_scope_round_trips_and_replays(self):
        theory = template("values red blue\npredicate P/1\nproperty Goal: forall x. P(x)")
        witness = bounded(theory).properties[0].countermodel
        scoped = witness_theory(theory, witness)
        for notation in ("ascii", "unicode"):
            with self.subTest(notation=notation):
                restored = loads(format_theory(scoped, notation=notation))
                self.assertTrue(restored.scope_declared)
                self.assertEqual(restored.axioms, scoped.axioms)
                self.assertEqual(restored.properties, scoped.properties)
                self.assertTrue(replay(restored, witness))

    def test_export_escapes_all_characters_that_split_markdown_lines(self):
        for character in ("\x85", "\u2028", "\u2029", "\n", "\r"):
            with self.subTest(character=repr(character)):
                name = "red" + character + "blue"
                source = "points a\nvalues " + ascii(name) + "\nstages 1\nquorums {a}\nproperty Goal: t"
                scoped = loads("```muql\n" + source + "\n```")
                self.assertEqual(loads(format_theory(scoped)).values, (name,))

    def test_witness_import_rejects_tampered_scope_and_valuation(self):
        theory = template("values red\npredicate P/1\nproperty Goal: P(red)")
        witness = bounded(theory).properties[0].countermodel.to_dict()
        mutations = []
        modified = deepcopy(witness)
        modified["scope"]["values"] = ["different"]
        mutations.append(modified)
        modified = deepcopy(witness)
        modified["scope"]["time"] = "stutter"
        mutations.append(modified)
        modified = deepcopy(witness)
        modified["scope"]["stages"] = True
        mutations.append(modified)
        modified = deepcopy(witness)
        modified["valuation"][0]["value"] = "t"
        mutations.append(modified)
        modified = deepcopy(witness)
        modified["scope"]["quorums"] = [[]]
        mutations.append(modified)
        for data in mutations:
            with self.subTest(data=data), self.assertRaises(ValueError):
                witness_theory(theory, data)

    def test_fresh_domain_names_avoid_formula_and_unused_macro_bindings(self):
        theory = template("""predicate value0/0
let Unused(value1): forall value2. value1 == value2
property Goal: forall value3. forall value4. value3 == value4""")
        report = bounded(theory, max_values=2)
        witness = report.properties[0].countermodel
        self.assertIsNotNone(witness)
        self.assertEqual(witness.scope["values"], ["v0", "value5"])
        scoped = witness_theory(theory, witness)
        restored = loads(format_theory(scoped))
        self.assertTrue(replay(restored, witness))

    def test_scoped_export_refuses_an_uninstantiated_template(self):
        with self.assertRaises(TheoryError):
            format_theory(template("property Goal: t"))


if __name__ == "__main__":
    unittest.main()
