"""Independent front-end audit: rejection, hygiene, and bounded expansion."""

from dataclasses import replace
import random
import unittest

from muql.syntax import FormulaError, Node, format_formula, parse_formula
from muql.theory import TheoryError, loads, validate_theory


FRAME = """points alice
values red blue
stages 2
quorums {alice}
predicate P/1
predicate Live/0
"""


def document(body, frame=FRAME):
    return "```muql\n" + frame + body + "\n```\n"


class MacroAuditTests(unittest.TestCase):
    def test_unused_arguments_are_still_checked(self):
        for argument in ("misspelled", "'unknown'"):
            with self.subTest(argument=argument), self.assertRaises(TheoryError):
                loads(document(f"let Ignore(v): t\nproperty Goal: Ignore({argument})"))

    def test_unused_nested_macro_and_unused_parameter_are_checked(self):
        with self.assertRaisesRegex(TheoryError, "free or undeclared"):
            loads(document("let Ignore(v): t\nlet NeverCalled: Ignore(typo)\nproperty Goal: t"))

    def test_valid_unused_arguments_accept_literals_and_bound_variables(self):
        theory = loads(document("let Ignore(v): t\nproperty Goal: forall w. Ignore(w) & Ignore('red')"))
        self.assertEqual(theory.properties["Goal"], parse_formula("forall w. t & t"))

    def test_unused_api_argument_cannot_disappear_before_sort_check(self):
        theory = loads(document("let Ignore(v): t\naxiom A: t"))
        for argument in (Node("const", value="t"), Node("term", value="undeclared")):
            with self.subTest(argument=argument), self.assertRaises(TheoryError):
                theory.replace("A", Node("pred", (argument,), "Ignore"))

    def test_fresh_binders_avoid_all_declarations_not_only_used_names(self):
        frame = FRAME.replace("values red blue", "values red blue x_local1")
        frame += "predicate x_local2/0\n"
        theory = loads(document("let Some: exists x. P(x)\nproperty Goal: Some", frame))
        binder = theory.properties["Goal"]
        self.assertNotIn(binder.value, theory.values)
        self.assertNotIn(binder.value, theory.predicates)
        self.assertEqual(binder.args[0].args[0].value, binder.value)

    def test_fresh_binders_avoid_unused_formal_parameters(self):
        theory = loads(document("let Some: exists x. P(x)\nlet Wrapper(x_local1): Some\nproperty Goal: Wrapper(red)"))
        self.assertEqual(theory.properties["Goal"].op, "exists")

    def test_macro_value_parameters_must_not_shadow_declared_names(self):
        for name in ("red", "Live"):
            with self.subTest(name=name), self.assertRaisesRegex(TheoryError, "shadows"):
                loads(document(f"let Hidden({name}): t\nproperty Goal: t"))

    def test_latest_and_fixedpoint_binders_preserve_lexical_references(self):
        theory = loads(document("""let Last(v): latest w = v. P(w)
let Iterate: mu X. Live | yesterday(X)
property LastUnderBinder: forall w. Last(w)
property IterateUnderBinder: mu X. Iterate | X"""))
        outer = theory.properties["LastUnderBinder"]
        latest = outer.args[0]
        self.assertNotEqual(latest.value, outer.value)
        self.assertEqual(latest.args[0], Node("term", value=outer.value))
        self.assertEqual(latest.args[1].args[0], Node("term", value=latest.value))
        outer_fixed = theory.properties["IterateUnderBinder"]
        inner_fixed, outer_reference = outer_fixed.args[0].args
        self.assertNotEqual(inner_fixed.value, outer_fixed.value)
        self.assertEqual(outer_reference, Node("var", value=outer_fixed.value))
        self.assertEqual(inner_fixed.args[0].args[1].args[0], Node("var", value=inner_fixed.value))

    def test_exponential_macro_expansion_has_a_frontend_budget(self):
        declarations = ["let M0: t"]
        declarations.extend(f"let M{i}: M{i - 1} & M{i - 1}" for i in range(1, 25))
        with self.assertRaisesRegex(TheoryError, "macro expansion.*work limit"):
            loads(document("\n".join(declarations) + "\nproperty Goal: M24"))


class InputAuditTests(unittest.TestCase):
    def test_quoted_braces_and_comment_characters_in_quorum_names(self):
        frame = 'points "a{b}" "c}d{" "e#//f"\nvalues red\nstages 1\nquorums {"a{b}","e#//f"} {"c}d{"}\n'
        theory = loads(document("property Goal: t", frame))
        self.assertEqual(theory.quorums, (("a{b}", "e#//f"), ("c}d{",)))

    def test_quorum_separators_cannot_be_silently_discarded(self):
        for sets in (",{alice}", "{alice},", "{alice},,,", "{alice}, ,{alice}", "{{alice}}", "{alice}{alice}"):
            with self.subTest(sets=sets), self.assertRaises(TheoryError):
                loads(document("property Goal: t", FRAME.replace("quorums {alice}", "quorums " + sets)))

    def test_quorum_separator_commas_and_whitespace_are_supported(self):
        frame = "points a b\nvalues red\nstages 1\nquorums {a} , {b}\n"
        self.assertEqual(loads(document("property Goal: t", frame)).quorums, (("a",), ("b",)))

    def test_malformed_api_ast_is_rejected_before_macro_walk(self):
        theory = loads(document("axiom A: t"))
        invalid = [
            Node("and", ("not-a-node", Node("const", value="t"))),
            Node("not", None),
            Node("const", value=[]),
            Node([], ()),
            Node("pred", [Node("term", value="red")], "P"),
            Node("and", (Node("const", value="t"), Node("const", value="t")), "ignored"),
            Node("pred", (Node("term", value=[]),), "P"),
        ]
        for node in invalid:
            with self.subTest(node=repr(node)), self.assertRaises(TheoryError):
                theory.replace("A", node)

    def test_deep_source_and_ast_report_input_errors(self):
        for text in ("!" * 5000 + "t", "(" * 5000 + "t" + ")" * 5000, "t ⇀ " * 5000 + "t"):
            with self.subTest(prefix=text[:12]), self.assertRaisesRegex(FormulaError, "nesting"):
                parse_formula(text)
        with self.assertRaisesRegex(TheoryError, "nesting"):
            loads(document("property Goal: " + " & ".join(["t"] * 5000)))
        node = Node("const", value="t")
        for _ in range(5000):
            node = Node("not", (node,))
        theory = loads(document("axiom A: t"))
        with self.assertRaisesRegex(TheoryError, "nesting"):
            theory.replace("A", node)

    def test_oversized_integer_diagnostics_remain_input_errors(self):
        # Python limits decimal conversions on supported modern runtimes.
        import sys
        get_limit = getattr(sys, "get_int_max_str_digits", None)
        if get_limit is None or not get_limit():
            self.skipTest("runtime does not limit integer conversion")
        digits = "1" * (get_limit() + 1)
        with self.assertRaisesRegex(FormulaError, "integer is too large"):
            parse_formula(f"twined({digits})")
        for replacement in (("stages 2", f"stages {digits}"), ("predicate P/1", f"predicate P/{digits}")):
            with self.subTest(kind=replacement[0]), self.assertRaisesRegex(TheoryError, "integer is too large"):
                loads(document("property Goal: t", FRAME.replace(*replacement)))

    def test_malformed_token_sequences_only_raise_formula_errors(self):
        randomizer = random.Random(828183)
        tokens = ["t", "P", "X", "red", "forall", "mu", "latest", "not", "T", "twined", "0", "==", "⇀", "&", "(", ")", ",", ".", ";", "=", "!", "//comment\n", "'red'"]
        for _ in range(3000):
            text = " ".join(randomizer.choices(tokens, k=randomizer.randrange(1, 22)))
            try:
                tree = parse_formula(text)
            except FormulaError:
                continue
            self.assertEqual(parse_formula(format_formula(tree)), tree)

    def test_executable_fences_ignore_nested_examples_and_preserve_locations(self):
        prefix = "````markdown\n```muql\nproperty Hidden: f\n```\n````\n"
        source = prefix + document("property Goal: T(t) # inline comment")
        self.assertEqual(set(loads(source).properties), {"Goal"})
        source += "\n```muql\nproperty Bad:\n\n    @\n```\n"
        with self.assertRaises(TheoryError) as caught:
            loads(source, "audit.md")
        self.assertEqual(caught.exception.line, source.splitlines().index("    @") + 1)
        self.assertEqual(caught.exception.column, 5)


class PublicTheoryValidationTests(unittest.TestCase):
    def test_direct_dataclass_changes_cannot_bypass_frontend_validation(self):
        theory = loads(document("axiom A: t\nproperty Goal: t"))
        changes = [
            {"stages": True}, {"stages": 1.5}, {"stages": 0},
            {"values": ("red", "red")}, {"values": ()}, {"values": "red"},
            {"points": ("alice", 2)}, {"points": ("",)},
            {"time": "cyclic"}, {"time": []},
            {"quorums": ((),)}, {"quorums": (("absent",),)},
            {"quorums": (("alice",), ("alice",))},
            {"predicates": {"P": -1}}, {"predicates": {"P": True}},
            {"predicates": {"P": 1.5}}, {"predicates": {"T": 0}},
            {"predicates": {"not-a-name": 0}},
            {"properties": {"Goal": Node("pred", value="Unlisted")}},
            {"properties": {"A": Node("const", value="t")}},
            {"properties": {"Bad Label": Node("const", value="t")}},
            {"locations": {"A": False}}, {"name": ""}, {"source": 7},
        ]
        for fields in changes:
            with self.subTest(fields=fields), self.assertRaises(TheoryError):
                validate_theory(replace(theory, **fields))

    def test_shallow_mutation_is_detected_without_reloading(self):
        theory = loads(document("property Goal: t"))
        theory.predicates["Extra"] = -1
        with self.assertRaisesRegex(TheoryError, "nonnegative integer"):
            validate_theory(theory)


if __name__ == "__main__":
    unittest.main()
