"""Fresh frontend audit: source coordinates and lossless source handling."""

from dataclasses import replace
import unittest

from muql import check, format_theory, replay
from muql.syntax import RESERVED, FormulaError, Node, format_formula, parse_formula
from muql.theory import TheoryError, loads


FRAME = "points alice bob\nvalues red blue\nstages 1\nquorums {alice,bob}\n"


def document(body="property Goal: t", frame=FRAME):
    return "# Audit\n\n```muql\n" + frame + body + "\n```\n"


class SourceCoordinatesTests(unittest.TestCase):
    def assert_location(self, text, expected_line, expected_column, message):
        with self.assertRaisesRegex(TheoryError, message) as caught:
            loads(text, source="coordinates.md")
        self.assertEqual(caught.exception.source, "coordinates.md")
        self.assertEqual((caught.exception.line, caught.exception.column),
                         (expected_line, expected_column))

    def test_name_list_diagnostics_include_declaration_prefix_and_indentation(self):
        for declaration in ("points alice,", "    values red,", "\tvalues\tred,"):
            with self.subTest(declaration=declaration):
                text = document(frame=declaration + "\n")
                self.assert_location(text, 4, len(declaration) + 1, "after comma")

    def test_invalid_name_and_missing_separator_have_absolute_columns(self):
        for declaration, bad_token in (
            ("points alice @", "@"),
            ('  values "red"blue', "blue"),
            ('\tvalues\t"😀" @', "@"),
        ):
            with self.subTest(declaration=declaration):
                self.assert_location(document(frame=declaration + "\n"), 4,
                                     declaration.index(bad_token) + 1,
                                     "invalid declaration|separate names")

    def test_empty_and_invalid_quoted_name_locations(self):
        for declaration, quote in (("values red ''", "''"),
                                   ('  points "\\xZZ"', '"')):
            with self.subTest(declaration=declaration):
                self.assert_location(document(frame=declaration + "\n"), 4,
                                     declaration.index(quote) + 1,
                                     "cannot be empty|invalid quoted name")

    def test_quorum_inner_errors_include_outer_declaration_and_set_offsets(self):
        for declaration, marker in (
            ("quorums {alice,,bob}", ",bob"),
            ("  quorums {alice} , {bob,,alice}", ",alice"),
            ('\tquorums\t{"😀",@}', "@"),
        ):
            with self.subTest(declaration=declaration):
                self.assert_location(document(frame=declaration + "\n"), 4,
                                     declaration.index(marker) + 1,
                                     "invalid declaration")

    def test_quorum_outer_error_columns(self):
        for declaration, column, message in (
            ("quorums {alice}{bob}", 16, "separate quorum"),
            ("  quorums {alice},", 19, "after comma"),
            ("quorums {alice", 9, "unclosed quorum"),
            ("quorums {{alice}}", 10, "nested quorum"),
        ):
            with self.subTest(declaration=declaration):
                self.assert_location(document(frame=declaration + "\n"), 4,
                                     column, message)

    def test_multiline_declaration_header_keeps_actual_formula_location(self):
        for header in ("property\n  Goal: @", "let Pair(\n  x, y\n): @"):
            with self.subTest(header=header):
                source = document(header)
                line = source.splitlines().index(next(row for row in source.splitlines() if "@" in row)) + 1
                column = source.splitlines()[line - 1].index("@") + 1
                self.assert_location(source, line, column, "unexpected character")

    def test_non_lf_document_lines_and_non_bmp_characters(self):
        for separator in ("\r\n", "\r", "\u0085", "\u2028", "\u2029"):
            with self.subTest(separator=repr(separator)):
                source = document('property Goal: "😀" = red & @')
                line = source.splitlines().index('property Goal: "😀" = red & @') + 1
                column = source.splitlines()[line - 1].index("@") + 1
                self.assert_location(source.replace("\n", separator), line, column,
                                     "unexpected character")


class FrontendPreservationTests(unittest.TestCase):
    def test_reserved_value_names_have_symmetric_equality_syntax(self):
        for name in sorted(RESERVED):
            for operator, operation in (("=", "eq"), ("==", "eq"), ("!=", "neq"), ("≠", "neq")):
                with self.subTest(name=name, operator=operator):
                    tree = Node(operation, (Node("term", value=name), Node("term", value="red")))
                    self.assertEqual(parse_formula(f"{name} {operator} red"), tree)
                    for notation in ("ascii", "unicode"):
                        self.assertEqual(parse_formula(format_formula(tree, notation=notation)), tree)

    def test_equality_lookahead_does_not_change_prefix_operators_or_bindings(self):
        for text, operation in (("not P", "not"), ("T(P)", "T"),
                                ("somewhere(P)", "diamond"),
                                ("forall x. P(x)", "forall"),
                                ("mu X. P | X", "mu"),
                                ("latest x = red. P(x)", "latest")):
            with self.subTest(text=text):
                tree = parse_formula(text)
                self.assertEqual(tree.op, operation)
                self.assertEqual(parse_formula(format_formula(tree)), tree)
        with self.assertRaisesRegex(FormulaError, "reserved"):
            parse_formula("forall forall. t")

    def test_direct_api_values_export_check_and_replay_in_both_notations(self):
        for name in ("a b", "😀", "a#//b", "line\u2028separator", "single'quote"):
            with self.subTest(name=name):
                frame = FRAME.replace("values red blue", f"values {name!r} red T forall")
                base = loads(document("predicate P/1\nproperty Goal: t", frame))
                reflexive = Node("eq", (Node("term", value="forall"), Node("term", value="forall")))
                predicate = Node("pred", (Node("term", value=name),), "P")
                unequal = Node("neq", (Node("term", value="T"), Node("term", value="red")))
                theory = replace(base,
                    axioms={"Reflexive": reflexive},
                    properties={"Goal": Node("and", (predicate, unequal))})
                witness = check(theory).properties[0].countermodel
                self.assertIsNotNone(witness)
                for notation in ("ascii", "unicode"):
                    exported = format_theory(theory, notation=notation)
                    if notation == "ascii":
                        self.assertTrue(exported.isascii())
                    restored = loads(exported)
                    self.assertEqual(check(restored).properties[0].status, "counterexample")
                    self.assertTrue(replay(restored, witness))

    def test_large_name_list_preserves_order_and_duplicate_rejection(self):
        names = tuple(f"v{index}" for index in range(20000))
        frame = FRAME.replace("values red blue", "values " + ", ".join(names))
        self.assertEqual(loads(document(frame=frame)).values, names)
        with self.assertRaisesRegex(TheoryError, "duplicate names"):
            loads(document(frame=frame.replace("\nstages", ", v19999\nstages")))

    def test_binary_formatting_preserves_each_association_in_both_notations(self):
        leaves = tuple(Node("pred", value=name) for name in ("P", "Q", "R"))
        operations = ("and", "or", "xor", "weak", "strong", "equiv", "order")
        for outer in operations:
            for inner in operations:
                for left_nested in (True, False):
                    tree = (Node(outer, (Node(inner, leaves[:2]), leaves[2])) if left_nested
                            else Node(outer, (leaves[0], Node(inner, leaves[1:]))))
                    for notation in ("ascii", "unicode"):
                        with self.subTest(outer=outer, inner=inner, left=left_nested,
                                          notation=notation):
                            self.assertEqual(parse_formula(format_formula(tree, notation=notation)), tree)

    def test_strong_implication_alias_stays_rejected_and_quorum_scopes_stay_distinct(self):
        with self.assertRaisesRegex(FormulaError, "not supported"):
            parse_formula("P => Q")
        self.assertEqual(parse_formula("P -\\ Q"), parse_formula("P ⇀ Q"))
        for local, symbol, combined in (("somewhere", "◇", "someQuorumSomePoint"),
                                         ("everywhere", "□", "everyQuorumEveryPoint")):
            self.assertEqual(parse_formula(f"{local}(P)"), parse_formula(f"{symbol}(P)"))
            self.assertNotEqual(parse_formula(f"{local}(P)"), parse_formula(f"{combined}(P)"))


if __name__ == "__main__":
    unittest.main()
