"""Search templates remain distinct from explicitly scoped checking inputs."""

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from muql.checker import check
from muql.syntax import parse_formula
from muql.theory import TheoryError, load, loads, validate_theory


def document(body):
    return "```muql\n" + body + "\n```\n"


LOGIC = """predicate P/1
let Correct(v): TF(P(v))
axiom CorrectAll: forall v. Correct(v)
property Reflexive: forall v. P(v) -> P(v)
"""

SCOPE = """points alice bob
values red blue
stages 2
quorums {alice} {bob}
"""


class SearchInputTests(unittest.TestCase):
    def test_check_loader_still_requires_the_whole_scope(self):
        with self.assertRaisesRegex(TheoryError, "missing required declaration"):
            loads(document(LOGIC))
        with self.assertRaisesRegex(TheoryError, "missing required declaration.*quorums"):
            loads(document(SCOPE.replace("quorums {alice} {bob}\n", "") + LOGIC))

    def test_scope_free_search_input_is_valid_but_cannot_be_checked_directly(self):
        template = loads(document(LOGIC), for_search=True)
        self.assertFalse(template.scope_declared)
        self.assertEqual(template.points, ("p0",))
        self.assertEqual(template.values, ("v0",))
        self.assertEqual(template.stages, 1)
        self.assertEqual(template.quorums, (("p0",),))
        self.assertEqual(template.time, "finite")
        validate_theory(template, require_scope=False)
        with self.assertRaisesRegex(TheoryError, "no complete declared scope"):
            validate_theory(template)
        with self.assertRaisesRegex(TheoryError, "use model search"):
            check(template)

    def test_search_candidate_can_supply_a_concrete_scope(self):
        template = loads(document(LOGIC), for_search=True)
        candidate = replace(template, points=("a", "b"), values=("red", "blue"),
                            stages=2, quorums=(("a",), ("b",)), scope_declared=True)
        validate_theory(candidate)
        report = check(candidate)
        self.assertEqual(report.status, "checked")
        self.assertEqual(report.properties[0].status, "holds")
        self.assertFalse(template.scope_declared)

    def test_explicit_values_are_all_retained_including_unused_names(self):
        template = loads(document("values red blue unused\ntime stutter\n" + LOGIC), for_search=True)
        self.assertEqual(template.values, ("red", "blue", "unused"))
        self.assertEqual(template.time, "stutter")
        self.assertFalse(template.scope_declared)

    def test_partial_scope_preserves_valid_explicit_fields(self):
        template = loads(document("points bob alice\nstages 7\n" + LOGIC), for_search=True)
        self.assertEqual(template.points, ("bob", "alice"))
        self.assertEqual(template.quorums, (("bob", "alice"),))
        self.assertEqual(template.stages, 7)
        self.assertFalse(template.scope_declared)

    def test_explicit_full_scope_remains_usable_for_check(self):
        scoped = loads(document(SCOPE + LOGIC), for_search=True)
        self.assertTrue(scoped.scope_declared)
        self.assertEqual(scoped, loads(document(SCOPE + LOGIC)))
        validate_theory(scoped)

    def test_value_constants_require_an_explicit_declaration(self):
        for formula in ("P(red)", "P(v0)", "P('v0')", "v0 == v0"):
            with self.subTest(formula=formula), self.assertRaisesRegex(TheoryError, "undeclared"):
                loads(document("predicate P/1\nproperty Goal: " + formula), for_search=True)
        template = loads(document("values red\npredicate P/1\nproperty Goal: P(red)"), for_search=True)
        self.assertEqual(template.values, ("red",))

    def test_unused_macros_and_arguments_do_not_infer_constants(self):
        for extra in ("let Unused: P(v0)", "let Ignore(v): t\nlet Unused: Ignore(v0)"):
            with self.subTest(extra=extra), self.assertRaisesRegex(TheoryError, "undeclared"):
                loads(document("predicate P/1\n" + extra + "\nproperty Goal: t"), for_search=True)

    def test_placeholder_cannot_shadow_any_used_or_unused_binder(self):
        body = """predicate P/1
predicate v0/0
let Unused(v1): exists v2. P(v1) & P(v2)
property Goal: forall v3. P(v3) -> P(v3)
"""
        template = loads(document(body), for_search=True)
        self.assertEqual(template.values, ("v4",))
        validate_theory(template, require_scope=False)

    def test_quorums_do_not_implicitly_declare_points(self):
        for quorum in ("{alice}", "{p0}"):
            with self.subTest(quorum=quorum), self.assertRaisesRegex(TheoryError, "explicit points declaration"):
                loads(document("quorums " + quorum + "\n" + LOGIC), for_search=True)

    def test_explicit_scope_errors_remain_errors_in_search_mode(self):
        for declaration in ("stages 0", "points alice alice", "values red red", "time forever", "points alice\nquorums {bob}"):
            with self.subTest(declaration=declaration), self.assertRaises(TheoryError):
                loads(document(declaration + "\n" + LOGIC), for_search=True)

    def test_without_and_replace_preserve_the_template_marker(self):
        template = loads(document(LOGIC), for_search=True)
        weakened = template.without("CorrectAll")
        altered = template.replace("CorrectAll", "exists v. Correct(v)")
        self.assertFalse(weakened.scope_declared)
        self.assertFalse(altered.scope_declared)
        self.assertEqual(altered.axioms["CorrectAll"], parse_formula("exists v. TF(P(v))"))
        self.assertEqual(template.axioms["CorrectAll"].op, "forall")
        validate_theory(weakened, require_scope=False)
        validate_theory(altered, require_scope=False)

    def test_file_loading_forwards_search_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "search.md"
            path.write_text(document(LOGIC), encoding="utf-8")
            self.assertFalse(load(path, for_search=True).scope_declared)
            with self.assertRaisesRegex(TheoryError, "missing required declaration"):
                load(path)

    def test_mode_and_marker_require_booleans(self):
        for flag in (1, "false", None):
            with self.subTest(flag=flag), self.assertRaises(TypeError):
                loads(document(LOGIC), for_search=flag)
        template = loads(document(LOGIC), for_search=True)
        with self.assertRaisesRegex(TheoryError, "scope_declared must be a boolean"):
            validate_theory(replace(template, scope_declared=1), require_scope=False)
        with self.assertRaises(TypeError):
            validate_theory(template, require_scope="false")


if __name__ == "__main__":
    unittest.main()
