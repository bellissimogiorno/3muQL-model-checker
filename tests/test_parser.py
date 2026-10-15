"""Syntax, literate-document, and name-resolution regression tests."""

import tempfile
from pathlib import Path
import unittest

from muql.syntax import FormulaError, Node, UNARY, format_formula, parse_formula
from muql.theory import TheoryError, load, loads


FRAME = """points a b c
values red blue undef
stages 3
quorums {a,b} {a,c} {b,c}
predicate vote/1
predicate live/0
"""


def document(body="", frame=FRAME):
    return "# A readable theory\n\n```muql\n" + frame + body + "\n```\n"


class FormulaTests(unittest.TestCase):
    def test_precedence_and_right_associative_implication(self):
        parsed = parse_formula("P | Q & R -> S ⇀ U")
        self.assertEqual(parsed.op, "weak")
        self.assertEqual(parsed.args[0].op, "or")
        self.assertEqual(parsed.args[0].args[1].op, "and")
        self.assertEqual(parsed.args[1].op, "strong")

    def test_binder_extends_right(self):
        self.assertEqual(parse_formula("forall v. P(v) & Q(v)").args[0].op, "and")

    def test_all_unary_operators_round_trip(self):
        for name in UNARY:
            with self.subTest(name=name):
                spelling = {'somewhere': 'someQuorumSomePoint',
                            'everywhere': 'everyQuorumEveryPoint'}.get(name, name)
                node = parse_formula(f"{spelling}(P(red))")
                self.assertEqual(node.op, name)
                self.assertEqual(parse_formula(format_formula(node)), node)

    def test_binary_operators_round_trip(self):
        for operator in ["&", "|", "xor", "->", "⇀", "<=>", "<="]:
            with self.subTest(operator=operator):
                node = parse_formula(f"P {operator} Q")
                self.assertEqual(parse_formula(str(node)), node)

    def test_constants_and_equality(self):
        self.assertEqual(parse_formula("b"), Node("const", value="b"))
        self.assertEqual(parse_formula("red == blue").op, "eq")
        self.assertEqual(parse_formula("'red' != blue").args[0].op, "literal")
        self.assertEqual(parse_formula("P(0, 'a value')").args[1].value, "a value")

    def test_mu_binds_only_its_own_variable(self):
        node = parse_formula("(mu X. P | yesterday(X)) & X")
        self.assertEqual(node.args[0].args[0].args[1].args[0], Node("var", value="X"))
        self.assertEqual(node.args[1], Node("pred", value="X"))

    def test_nonpositive_mu_is_legal(self):
        # The paper gives arbitrary-body mu the meet-of-prefixpoints semantics.
        node = parse_formula("mu X. !X")
        self.assertEqual(node.args[0].args[0].op, "var")

    def test_latest(self):
        node = parse_formula("latest v = undef. P(v)")
        self.assertEqual(node.op, "latest")
        self.assertEqual(node.value, "v")
        self.assertEqual(node.args[0], Node("term", value="undef"))
        self.assertEqual(parse_formula(str(node)), node)

    def test_twined(self):
        self.assertEqual(parse_formula("twined(2)"), Node("twined", value="2"))
        with self.assertRaisesRegex(FormulaError, "positive integer"):
            parse_formula("twined(0)")

    def test_comments_quotes_and_multiline_error(self):
        node = parse_formula("P('a#b') # ignored\n & Q // ignored")
        self.assertEqual(node.args[0].args[0].value, "a#b")
        with self.assertRaises(FormulaError) as caught:
            parse_formula("P &\n @")
        self.assertEqual((caught.exception.line, caught.exception.column), (2, 2))

    def test_bad_syntax_is_not_partially_parsed(self):
        for text in ["", "P Q", "T P", "P(red,)", "forall . P", "P(unknown(red))", "P === Q", "P; Q"]:
            with self.subTest(text=text), self.assertRaises(FormulaError):
                parse_formula(text)

    def test_word_and_symbol_aliases(self):
        self.assertEqual(parse_formula("not P and Q or R"), parse_formula("!P && Q || R"))


class TheoryTests(unittest.TestCase):
    def test_frame_and_multiple_blocks(self):
        source = document("axiom Valid: TF(vote(red))") + "Some explanation.\n```muql\nproperty Goal: live -> live\n```\n"
        theory = loads(source, "guide.md")
        self.assertEqual(theory.name, "guide")
        self.assertEqual(theory.points, ("a", "b", "c"))
        self.assertEqual(theory.values, ("red", "blue", "undef"))
        self.assertEqual(theory.stages, 3)
        self.assertEqual(theory.time, "finite")
        self.assertEqual(list(theory.axioms), ["Valid"])
        self.assertEqual(list(theory.properties), ["Goal"])

    def test_stutter_and_quoted_name(self):
        theory = loads(document('theory "Example title"\ntime stutter\nproperty Goal: t'))
        self.assertEqual(theory.name, "Example title")
        self.assertEqual(theory.time, "stutter")

    def test_multiline_formula_location(self):
        source = document("property Goal: live &\n\n    @")
        with self.assertRaises(TheoryError) as caught:
            loads(source, "example.md")
        self.assertEqual(caught.exception.source, "example.md")
        self.assertEqual(caught.exception.line, source.splitlines().index("    @") + 1)
        self.assertEqual(caught.exception.column, 5)

    def test_first_line_formula_error_column(self):
        source = document("property Goal: live & @")
        with self.assertRaises(TheoryError) as caught:
            loads(source)
        self.assertEqual(caught.exception.column, len("property Goal: live & ") + 1)

    def test_indented_formula_error_column(self):
        source = document("    property Goal: live & @")
        with self.assertRaises(TheoryError) as caught:
            loads(source)
        self.assertEqual(caught.exception.column, len("    property Goal: live & ") + 1)

    def test_formula_begins_after_header_line(self):
        source = document("property Goal:\n    live & @")
        with self.assertRaises(TheoryError) as caught:
            loads(source)
        self.assertEqual(caught.exception.line, source.splitlines().index("    live & @") + 1)
        self.assertEqual(caught.exception.column, len("    live & ") + 1)

    def test_ignores_prose_and_other_fences(self):
        text = "```python\npredicate fake/0\n```\n" + document("property Goal: t")
        self.assertEqual(loads(text).predicates, {"vote": 1, "live": 0})

    def test_long_outer_fence_does_not_execute_nested_example(self):
        text = "````markdown\n```muql\ninvalid\n```\n````\n" + document("property Goal: t")
        self.assertIn("Goal", loads(text).properties)

    def test_tilde_fences(self):
        self.assertIn("Goal", loads(document("property Goal: t").replace("```", "~~~")).properties)

    def test_file_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "theory.md"
            path.write_text(document("property Goal: t"), encoding="utf-8")
            self.assertEqual(load(path).source, str(path))

    def test_comments_do_not_damage_quoted_values(self):
        frame = FRAME.replace("values red blue undef", 'values "red#blue" undef // comment')
        theory = loads(document('property Goal: vote("red#blue") -> t # comment', frame))
        self.assertEqual(theory.values, ("red#blue", "undef"))

    def test_macros_expand_nested_and_forward_calls(self):
        theory = loads(document("""let Majority(v): quorum(Confirmed(v))
let Confirmed(v): T(vote(v))
property Goal: forall v. Majority(v) ⇀ quorum(T(vote(v)))"""))
        body = theory.properties["Goal"].args[0]
        self.assertEqual(body.args[0], body.args[1])

    def test_macro_is_capture_avoiding(self):
        theory = loads(document("""let Different(v): exists w. (v != w) & vote(w)
property Goal: forall w. Different(w)"""))
        outer = theory.properties["Goal"]
        inner = outer.args[0]
        self.assertNotEqual(inner.value, "w")
        equality = inner.args[0].args[0]
        self.assertEqual(equality.args[0].value, "w")
        self.assertEqual(equality.args[1].value, inner.value)

    def test_macro_local_binder_does_not_shadow_call_site(self):
        theory = loads(document("""let Any: exists v. vote(v)
property Goal: forall v. Any"""))
        outer = theory.properties["Goal"]
        self.assertNotEqual(outer.value, outer.args[0].value)

    def test_recursive_and_unused_invalid_macros_rejected(self):
        for body, message in [
            ("let Alpha: Beta\nlet Beta: Alpha\nproperty Goal: t", "recursive macro"),
            ("let Bad(v): missing(v)\nproperty Goal: t", "undeclared predicate"),
            ("let Bad(v): vote(w)\nproperty Goal: t", "free or undeclared"),
            ("let Bad(v): forall v. vote(v)\nproperty Goal: t", "shadows"),
            ("let Good(v): vote(v)\nproperty Goal: Good", "expects 1 arguments"),
        ]:
            with self.subTest(body=body), self.assertRaisesRegex(TheoryError, message):
                loads(document(body))

    def test_without_and_replace_are_nondestructive(self):
        theory = loads(document("axiom A: live\nproperty Goal: live"))
        removed = theory.without("A")
        replacement = theory.replace("A", "TF(live)")
        self.assertEqual(theory.axioms["A"].op, "pred")
        self.assertFalse(removed.axioms)
        self.assertEqual(replacement.axioms["A"].op, "TF")
        for operation in [lambda: theory.without("Typo"), lambda: theory.replace("Typo", "t")]:
            with self.assertRaisesRegex(TheoryError, "unknown axiom"):
                operation()

    def test_replacement_checks_and_expands(self):
        theory = loads(document("let Safe(v): TF(vote(v))\naxiom A: t\nproperty Goal: t"))
        self.assertEqual(theory.replace("A", "Safe(red)").axioms["A"].op, "TF")
        with self.assertRaisesRegex(TheoryError, "free or undeclared"):
            theory.replace("A", "vote(v)")
        with self.assertRaisesRegex(TheoryError, "unknown formula operation"):
            theory.replace("A", Node("mystery"))

    def test_name_errors(self):
        for body, message in [
            ("property Goal: absent", "undeclared predicate"),
            ("property Goal: vote", "expects 1 arguments"),
            ("property Goal: vote(v)", "free or undeclared"),
            ("property Goal: vote('green')", "undeclared value"),
            ("property Goal: forall v. exists v. vote(v)", "shadows"),
            ("property Goal: forall red. vote(red)", "shadows"),
            ("predicate quorum/0\nproperty Goal: t", "reserved"),
            ("predicate property/0\nproperty Goal: t", "reserved"),
            ("predicate vote/1\nproperty Goal: t", "duplicate"),
            ("axiom Same: t\nproperty Same: t", "duplicate"),
        ]:
            with self.subTest(body=body), self.assertRaisesRegex(TheoryError, message):
                loads(document(body))

    def test_frame_errors(self):
        for frame, message in [
            (FRAME.replace("stages 3", "stages 0"), "positive integer"),
            (FRAME.replace("stages 3", ""), "missing required"),
            (FRAME + "stages 3\n", "duplicate stages"),
            (FRAME.replace("points a b c", "points a a c"), "duplicate names"),
            (FRAME.replace("{a,b} {a,c} {b,c}", "{a,d}"), "undeclared point"),
            (FRAME.replace("{a,b} {a,c} {b,c}", "{a,b} {b,a}"), "duplicate quorum"),
            (FRAME.replace("{a,b} {a,c} {b,c}", "{}"), "at least one"),
            (FRAME + "time cyclic\n", "finite.*stutter"),
            (FRAME.replace("values red blue undef", 'values red"blue"'), "separate names"),
        ]:
            with self.subTest(frame=frame), self.assertRaisesRegex(TheoryError, message):
                loads(document("property Goal: t", frame))

    def test_no_fence_unclosed_and_unknown_declaration(self):
        for text, message in [
            ("plain prose", "no fenced muql"),
            ("```muql\n" + FRAME, "unclosed"),
            (document("frobnicate yes"), "unknown declaration"),
        ]:
            with self.subTest(text=text), self.assertRaisesRegex(TheoryError, message):
                loads(text)


if __name__ == "__main__":
    unittest.main()
