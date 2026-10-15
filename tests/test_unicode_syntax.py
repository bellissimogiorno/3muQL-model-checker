"""Unicode/ASCII interchange, exact scope, and source-location regressions."""

import unittest

from muql.syntax import BINDERS, RESERVED, UNARY, FormulaError, Node, format_formula, parse_formula


class UnicodeSyntaxTests(unittest.TestCase):
    def assertAliases(self, expected, *spellings):
        tree = parse_formula(expected)
        for source in spellings:
            with self.subTest(source=source):
                self.assertEqual(parse_formula(source), tree)

    def test_binary_and_negation_aliases(self):
        for ascii_source, unicode_source in [
            ("!P", "¬P"), ("P & Q", "P ∧ Q"), ("P | Q", "P ∨ Q"),
            ("P xor Q", "P ⊕ Q"), ("P -> Q", "P → Q"),
            (r"P -\ Q", "P ⇀ Q"), ("P <=> Q", "P ≡ Q"),
            ("P <= Q", "P ≤ Q"), ("red != blue", "red ≠ blue"),
            ("red == blue", "red = blue"),
        ]:
            with self.subTest(ascii=ascii_source):
                self.assertAliases(ascii_source, unicode_source)

    def test_strong_implication_rejects_clashing_notation(self):
        self.assertAliases(r"P -\ Q", "P ⇀ Q")
        self.assertEqual(format_formula(parse_formula(r"P -\ Q")), "P ⇀ Q")
        self.assertEqual(format_formula(parse_formula("P ⇀ Q"), notation="ascii"), r"P -\ Q")
        # These spellings clash with a different implication in the paper.
        for source in ("P => Q", "P=>Q", "P ⇒ Q", "∀ v. P(v) => Q(v)"):
            with self.subTest(source=source), self.assertRaises(FormulaError):
                parse_formula(source)
        with self.assertRaises(FormulaError) as caught:
            parse_formula("P ∧ Q\n => R")
        self.assertEqual((caught.exception.line, caught.exception.column), (2, 2))
        self.assertIn(r"use '-\'", str(caught.exception))
        self.assertEqual(parse_formula("P # => is a comment\n"), parse_formula("P"))

    def test_binder_aliases(self):
        for word, symbols in {
            "forall": ["∀"], "exists": ["∃"],
            "unique": ["∃¹", "∃1", "∃!"], "affine": ["∃⁰¹", "∃01"],
            "mu": ["μ", "µ"], "nu": ["ν"],
        }.items():
            body = "P | X" if word in {"mu", "nu"} else "P(X) & Q(X)"
            self.assertAliases(f"{word} X. {body}", *(f"{symbol} X. {body}" for symbol in symbols))

    def test_modalities_and_compound_aliases(self):
        for word, symbols in {
            "box": ["□"], "diamond": ["◇", "⋄"],
            "existsQ": ["∃Q", "∃ꟴ"], "forallQ": ["∀Q", "∀ꟴ"],
            "quorum": ["∃Q□", "∃ꟴ□"], "contra": ["∀Q◇", "∀Q⋄", "∀ꟴ◇", "∀ꟴ⋄"],
            "someQuorumSomePoint": ["∃Q◇", "∃Q⋄", "∃ꟴ◇", "∃ꟴ⋄"],
            "everyQuorumEveryPoint": ["∀Q□", "∀ꟴ□"],
        }.items():
            for symbol in symbols:
                self.assertAliases(f"{word}(P)", f"{symbol}P", f"{symbol}(P)", f"{symbol} P")
                self.assertAliases(f"{word}(P & Q)", f"{symbol}(P ∧ Q)")
                self.assertAliases(f"{word}(P) & Q", f"{symbol}P ∧ Q")

    def test_named_modalities_still_require_parentheses(self):
        for word in UNARY | {"someQuorumSomePoint", "everyQuorumEveryPoint",
                             "someQuorumEveryPoint", "everyQuorumSomePoint"}:
            with self.subTest(word=word), self.assertRaises(FormulaError):
                parse_formula(f"{word} P")

    def test_mixed_notation_precedence_and_right_association(self):
        self.assertAliases(
            r"!P & Q xor R | S -> U -\ V <= W <=> Z",
            "¬P ∧ Q ⊕ R | S → U ⇀ V ≤ W ≡ Z",
            r"not P && Q ⊕ R or S -> U -\ V ≤ W <=> Z",
        )
        tree = parse_formula(r"P -\ Q → R ⇀ S")
        self.assertEqual(tree.op, "strong")
        self.assertEqual(tree.args[1].op, "weak")
        self.assertEqual(tree.args[1].args[1].op, "strong")

    def test_default_rendering_is_compact_unicode(self):
        node = parse_formula(r"forall v. T(P(v)) & !Q(v) -\ quorum(P(v))")
        self.assertEqual(str(node), "∀ v. T(P(v)) ∧ ¬Q(v) ⇀ ∃ꟴ□P(v)")
        self.assertEqual(format_formula(node, notation="ascii"),
                         r"forall v. T(P(v)) & !Q(v) -\ quorum(P(v))")
        self.assertEqual(str(parse_formula("P & (Q | R)")), "P ∧ (Q ∨ R)")

    def test_plain_and_superscript_quorum_spelling_share_canonical_output(self):
        for operator in ("∃Q", "∀Q", "∃Q□", "∀Q◇", "∀Q□", "∃Q◇"):
            source = f"{operator}(P)"
            expected = operator.replace("Q", "ꟴ") + (" " if operator.endswith("Q") else "") + "P"
            self.assertEqual(format_formula(parse_formula(source)), expected)
            self.assertEqual(format_formula(parse_formula(source.replace("Q", "ꟴ"))), expected)

    def test_round_trip_all_binary_associations(self):
        operators = ("and", "or", "xor", "weak", "strong", "equiv", "order")
        p, q, r = (Node("pred", value=name) for name in ("P", "Q", "R"))
        for outer in operators:
            for inner in operators:
                for tree in (Node(outer, (Node(inner, (p, q)), r)),
                             Node(outer, (p, Node(inner, (q, r))))):
                    for notation in ("unicode", "ascii"):
                        with self.subTest(tree=repr(tree), notation=notation):
                            self.assertEqual(parse_formula(format_formula(tree, notation=notation)), tree)

    def test_round_trip_nested_unary_operators(self):
        for outer in UNARY | {"not"}:
            for inner in UNARY | {"not"}:
                tree = Node(outer, (Node(inner, (Node("pred", value="P"),)),))
                for notation in ("unicode", "ascii"):
                    with self.subTest(outer=outer, inner=inner, notation=notation):
                        self.assertEqual(parse_formula(format_formula(tree, notation=notation)), tree)

    def test_round_trip_binder_scope_latest_and_quoted_values(self):
        formulas = [
            "(forall v. P(v)) & Q", "P & (exists v. Q(v))",
            "(mu X. P | yesterday(X)) & X",
            "mu X. (nu Y. X & tomorrow(Y)) | X",
            "box(forall v. P(v) -> Q(v))",
            "(latest v = undef. P(v)) -> Q",
            "latest v = 'a → b'. P(v) & (v == 'a → b')",
            "forall v. latest w = v. v != w & P(w)",
            "P('literal -\\\\ and => and ∀', 'a\\\'b', 'line\\nend')",
            "forall v. unique w. affine x. P(v, w, x)",
            "T(red == blue) & !('a' != 'b')",
        ]
        for formula in formulas:
            tree = parse_formula(formula)
            for notation in ("unicode", "ascii"):
                with self.subTest(formula=formula, notation=notation):
                    self.assertEqual(parse_formula(format_formula(tree, notation=notation)), tree)

    def test_compound_macros_do_not_replace_distinct_nested_ast(self):
        # quorum(P) and existsQ(box(P)) have distinct ASTs despite equal denotation.
        for nested, compound in [("existsQ(box(P))", "quorum(P)"),
                                 ("forallQ(diamond(P))", "contra(P)"),
                                 ("existsQ(diamond(P))", "someQuorumSomePoint(P)"),
                                 ("forallQ(box(P))", "everyQuorumEveryPoint(P)")]:
            tree = parse_formula(nested)
            self.assertNotEqual(tree, parse_formula(compound))
            self.assertEqual(parse_formula(str(tree)), tree)

    def test_plain_english_modality_aliases_have_exact_canonical_ast(self):
        for op, sources in {
            "diamond": ("somewhere(P)", "diamond(P)", "◇P"),
            "box": ("everywhere(P)", "box(P)", "□P"),
            "somewhere": ("someQuorumSomePoint(P)", "∃Q◇P"),
            "everywhere": ("everyQuorumEveryPoint(P)", "∀Q□P"),
            "quorum": ("someQuorumEveryPoint(P)", "quorum(P)", "∃Q□P"),
            "contra": ("everyQuorumSomePoint(P)", "contra(P)", "∀Q◇P"),
        }.items():
            expected = Node(op, (Node("pred", value="P"),))
            for source in sources:
                with self.subTest(op=op, source=source):
                    self.assertEqual(parse_formula(source), expected)

    def test_source_aliases_do_not_become_canonical_ast_operations(self):
        for name in ("someQuorumSomePoint", "everyQuorumEveryPoint",
                     "someQuorumEveryPoint", "everyQuorumSomePoint"):
            with self.subTest(name=name):
                self.assertIn(name, RESERVED)
                self.assertNotIn(name, UNARY)
                with self.assertRaisesRegex(FormulaError, "reserved word"):
                    parse_formula(f"∀ {name}. P")
                with self.assertRaisesRegex(ValueError, "unknown syntax operation"):
                    format_formula(Node(name, (Node("pred", value="P"),)))

    def test_modality_alias_matching_preserves_near_miss_identifiers(self):
        for name in ("somewhereElse", "everywhere2", "Somewhere",
                     "someQuorumSomePoints", "everyQuorumEveryPoint_2",
                     "somequorumEveryPoint", "everyQuorumSomePointExtra"):
            with self.subTest(name=name):
                self.assertNotIn(name, RESERVED)
                self.assertEqual(parse_formula(name), Node("pred", value=name))
                self.assertEqual(parse_formula(f"{name}(red)"),
                                 Node("pred", (Node("term", value="red"),), name))

    def test_ascii_output_names_quorum_point_modalities_explicitly(self):
        for unicode_source, ascii_source in (
            ("∃Q◇P", "someQuorumSomePoint(P)"),
            ("∀Q□P", "everyQuorumEveryPoint(P)"),
            ("◇P", "diamond(P)"), ("□P", "box(P)"),
            ("∃Q□P", "quorum(P)"), ("∀Q◇P", "contra(P)"),
        ):
            with self.subTest(source=unicode_source):
                tree = parse_formula(unicode_source)
                self.assertEqual(format_formula(tree, notation="ascii"), ascii_source)
                self.assertEqual(parse_formula(ascii_source), tree)

    def test_nested_unicode_quantifiers_are_not_remapped_as_source_aliases(self):
        for source, outer, inner in (
            ("∃Q◇◇P", "somewhere", "diamond"),
            ("∀Q□□P", "everywhere", "box"),
            ("◇∃Q◇P", "diamond", "somewhere"),
            ("□∀Q□P", "box", "everywhere"),
            ("∃Q ◇P", "existsQ", "diamond"),
            ("∀Q □P", "forallQ", "box"),
            ("∃ꟴ◇◇P", "somewhere", "diamond"),
            ("∀ꟴ□□P", "everywhere", "box"),
            ("◇∃ꟴ◇P", "diamond", "somewhere"),
            ("□∀ꟴ□P", "box", "everywhere"),
            ("∃ꟴ ◇P", "existsQ", "diamond"),
            ("∀ꟴ □P", "forallQ", "box"),
            ("someQuorumSomePoint(somewhere(P))", "somewhere", "diamond"),
            ("everyQuorumEveryPoint(everywhere(P))", "everywhere", "box"),
        ):
            with self.subTest(source=source):
                tree = Node(outer, (Node(inner, (Node("pred", value="P"),)),))
                self.assertEqual(parse_formula(source), tree)
                for notation in ("unicode", "ascii"):
                    self.assertEqual(parse_formula(format_formula(tree, notation=notation)), tree)

    def test_alias_names_inside_quoted_values_are_unchanged(self):
        value = "somewhere everywhere someQuorumSomePoint everyQuorumEveryPoint"
        tree = parse_formula(f"P({value!r}) # somewhere and ∃Q◇\n")
        self.assertEqual(tree.args[0].value, value)
        self.assertEqual(parse_formula(str(tree)), tree)

    def test_latest_assignment_and_value_equality_are_distinct(self):
        self.assertAliases("latest v = undef. v == red", "latest v = undef. v = red")
        for source in ["latest v == undef. P(v)", "P === Q", "red = blue = red"]:
            with self.subTest(source=source), self.assertRaises(FormulaError):
                parse_formula(source)

    def test_quoted_values_and_comments_are_not_normalised(self):
        value = "⇀ ∀ □ ∃Q□ ∃ꟴ□ ∀ꟴ◇ => -> <= != # //"
        source = f"P({value!r}) # ⇒ @ ∃⁰¹ -\\\n ∧ Q // ∀ . @\n"
        tree = parse_formula(source)
        self.assertEqual(tree.args[0].args[0].value, value)
        for notation in ("unicode", "ascii"):
            self.assertEqual(parse_formula(format_formula(tree, notation=notation)), tree)

    def test_ascii_output_escapes_unicode_literals_without_changing_values(self):
        tree = parse_formula("∀ v. P('café', '⇀', '😀', '∃ꟴ', v) ⇀ Q(v)")
        rendered = format_formula(tree, notation="ascii")
        self.assertTrue(rendered.isascii())
        self.assertIn(r"'caf\xe9'", rendered)
        self.assertIn(r"'\u21c0'", rendered)
        self.assertIn(r"'\U0001f600'", rendered)
        self.assertIn(r"'\u2203\ua7f4'", rendered)
        self.assertEqual(parse_formula(rendered), tree)

    def test_errors_refer_to_original_unicode_source_offsets(self):
        for source, character in [
            ("∀ value. P(value) ∧\n  @", "@"),
            ("∃⁰¹ . P", "."),
            ("∀Q◇(P ∧ )", ")"),
            ("∀ꟴ◇(P ∧ )", ")"),
            ("∃ꟴ□(P) ∧\n ∀ꟴ◇(P ∧ @)", "@"),
            ("P('∀ ⇀') ∧\n ∃¹ . Q", "."),
        ]:
            with self.subTest(source=source), self.assertRaises(FormulaError) as caught:
                parse_formula(source)
            offset = source.index(character)
            self.assertEqual(caught.exception.offset, offset)
            self.assertEqual(caught.exception.line, source.count("\n", 0, offset) + 1)
            self.assertEqual(caught.exception.column, offset - source.rfind("\n", 0, offset))

    def test_renderer_rejects_unknown_notation(self):
        with self.assertRaisesRegex(ValueError, "notation"):
            format_formula(parse_formula("P"), notation="latex")


if __name__ == "__main__":
    unittest.main()
