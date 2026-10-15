"""Typesetting must preserve the reader's executable and copied formulas."""

from html.parser import HTMLParser
import json
import re
import unittest

from muql.syntax import parse_formula
from tools.build_guide import ROOT, build, formula_html, intro_html


class Fragment(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.tags = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


class GuideTypesettingTests(unittest.TestCase):
    def test_every_quorum_operator_preserves_exact_text(self):
        for operator in ("∃Q", "∀Q", "∃Q◇", "∀Q□", "∃Q□", "∀Q◇", "∃Q⋄", "∀Q⋄"):
            with self.subTest(operator=operator):
                source = f"{operator}(p(v))"
                parsed = Fragment(formula_html(source))
                self.assertEqual("".join(parsed.text), source)
                self.assertEqual(parsed.tags, [
                    ("span", {"class": "quorum-quantifier"}),
                    ("sup", {"class": "quorum-mark"}),
                ])
        self.assertEqual(formula_html("∀v. ∃¹w. p(v, w)"), "∀v. ∃¹w. p(v, w)")

    def test_native_superscript_quorum_q_is_preserved_without_double_raising(self):
        for operator in ("∃ꟴ", "∀ꟴ", "∃ꟴ◇", "∀ꟴ□", "∃ꟴ□", "∀ꟴ◇", "∃ꟴ⋄", "∀ꟴ⋄"):
            with self.subTest(operator=operator):
                source = f"{operator}(p(v))"
                parsed = Fragment(formula_html(source))
                self.assertEqual("".join(parsed.text), source)
                self.assertEqual(parsed.tags, [("span", {"class": "quorum-quantifier"})])

    def test_quoted_literals_comments_and_incomplete_quotes_stay_literal(self):
        cases = (
            ('p("∃Q") ∧ ∀Q p(\'∀Q\')', 1),
            (r'p("escaped\"∃Q") ∧ ∃Q◇ p()', 1),
            ("p('unfinished ∀Q", 0),
            ('"unfinished ∃Q' + "\\", 0),
            ("∃Q p() # ∀Q comment\n∀Q p()", 2),
            ("// ∃Q comment\r\n∀Q p()", 1),
            ('p("# ∃Q // ∀Q")', 0),
            ('p("∃ꟴ□", \'∀ꟴ◇\') ∧ ∃ꟴ□ p() # ∀ꟴ comment', 0),
        )
        for source, count in cases:
            with self.subTest(source=source):
                parsed = Fragment(formula_html(source))
                self.assertEqual("".join(parsed.text), source)
                self.assertEqual(sum(tag == "sup" for tag, _ in parsed.tags), count)

    def test_untrusted_formula_text_never_becomes_html(self):
        source = '<img src=x onerror="∃Q"> & <script>∀Q</script> \' &quot;'
        parsed = Fragment(formula_html(source))
        self.assertEqual("".join(parsed.text), source)
        self.assertTrue(all(tag in {"span", "sup"} for tag, _ in parsed.tags))
        self.assertEqual(sum(tag == "sup" for tag, _ in parsed.tags), 1)

    def test_intro_inline_formulas_share_typesetting_without_rendering_html(self):
        rendered = intro_html('# Title\n\nRead `∃Q□(p())` and `<img src=x>`.\n\n```muql\n')
        parsed = Fragment(rendered)
        self.assertEqual("".join(parsed.text), "Read ∃Q□(p()) and <img src=x>.")
        self.assertEqual(sum(tag == "sup" for tag, _ in parsed.tags), 1)
        self.assertNotIn("img", [tag for tag, _ in parsed.tags])

    def test_generated_guide_preserves_formula_data_and_is_self_contained(self):
        document, count = build()
        self.assertEqual(count, 13)
        self.assertEqual(build(), (document, count))
        metadata_match = re.search(r'<script id="guide-data" type="application/json">(.*?)</script>', document, re.S)
        self.assertIsNotNone(metadata_match)
        data = json.loads(metadata_match[1])
        formulas = re.findall(r'<div class="formula" data-formula="(\d+)">(.*?)</div>', document, re.S)
        self.assertEqual(len(formulas), len(data["formulas"]))
        for index, markup in formulas:
            forms = data["formulas"][int(index)]
            self.assertEqual("".join(Fragment(markup).text), forms["unicode"])
            self.assertEqual(parse_formula(forms["unicode"]), parse_formula(forms["ascii"]))
        self.assertIn('<sup class="quorum-mark">Q</sup>', document)
        self.assertIn('url("data:font/woff;base64,', document)
        self.assertNotIn('url("quorum-superscript.woff")', document)
        self.assertIn('--math: "MuQL Quorum",', document)
        script = (ROOT / "web" / "notation.js").read_text(encoding="utf-8")
        self.assertIn(script.replace("export function formulaHTML(", "function formulaHTML(", 1), document)
        self.assertNotIn("@@NOTATION_", document)
        self.assertNotIn('<script src=', document)
        self.assertIn('formula.innerHTML = formulaHTML(', document)


if __name__ == "__main__":
    unittest.main()
