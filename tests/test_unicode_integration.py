"""Notation is presentation: protect the previously audited theory meanings."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from muql import format_formula, load, loads, parse_formula
from muql.cli import _formula_lines

ROOT = Path(__file__).resolve().parents[1]


def node_data(node):
    return [node.op, node.value, [node_data(arg) for arg in node.args]]


def meaning(theory):
    return {
        'name': theory.name, 'points': theory.points, 'values': theory.values,
        'stages': theory.stages, 'time': theory.time, 'quorums': theory.quorums,
        'predicates': theory.predicates,
        'axioms': {name: node_data(node) for name, node in theory.axioms.items()},
        'properties': {name: node_data(node) for name, node in theory.properties.items()},
    }


def ascii_document(theory):
    quoted = lambda value: json.dumps(value, ensure_ascii=True)
    rows = ['```muql', 'theory ' + quoted(theory.name),
            'points ' + ' '.join(map(quoted, theory.points)),
            'values ' + ' '.join(map(quoted, theory.values)),
            f'stages {theory.stages}', f'time {theory.time}',
            'quorums ' + ' '.join('{' + ','.join(map(quoted, q)) + '}' for q in theory.quorums)]
    rows += [f'predicate {name}/{arity}' for name, arity in theory.predicates.items()]
    for kind, formulas in (('axiom', theory.axioms), ('property', theory.properties)):
        rows += [f'{kind} {name}: {format_formula(formula, notation="ascii")}'
                 for name, formula in formulas.items()]
    return '\n'.join([*rows, '```'])


class UnicodeIntegrationTests(unittest.TestCase):
    def test_all_example_meanings_match_reference(self):
        expected = json.loads((ROOT/'tests/data/notation-baseline.json').read_text())['semantic_sha256']
        renames = json.loads((ROOT/'tests/data/rule-label-renames.json').read_text())['renames']
        original_labels = {new: old for old, new in renames.items()}
        actual = {}
        for path in sorted((ROOT/'examples').glob('*.md')):
            theory = load(path)
            data = meaning(theory)
            # Keep the original audited hashes. Only the explicit label migration
            # is normalized; every formula, scope and other label must still match.
            data['axioms'] = {original_labels.get(name, name): node
                              for name, node in data['axioms'].items()}
            actual[path.name] = hashlib.sha256(
                json.dumps(data, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        self.assertEqual(actual, expected)

    def test_bundled_rules_use_the_paper_direction_marks(self):
        examples = json.loads((ROOT/'tests/data/rule-label-renames.json').read_text())['examples']
        for filename, renames in examples.items():
            with self.subTest(example=filename):
                axioms = load(ROOT/'examples'/filename).axioms
                self.assertTrue(set(renames.values()) <= axioms.keys())
                self.assertFalse(set(renames) & axioms.keys())
                self.assertFalse(any(name.endswith(('_back', '_forward', 'Back', 'Forward', 'Relay'))
                                     for name in axioms))

    def test_all_examples_are_also_executable_pure_ascii(self):
        for path in sorted((ROOT/'examples').glob('*.md')):
            with self.subTest(example=path.name):
                unicode_theory = load(path)
                source = ascii_document(unicode_theory)
                self.assertTrue(source.isascii())
                self.assertEqual(meaning(loads(source)), meaning(unicode_theory))

    def run_cli(self, *args, ascii_console=False):
        env = dict(os.environ)
        env['PYTHONIOENCODING'] = 'ascii' if ascii_console else 'utf-8'
        return subprocess.run([sys.executable, '-m', 'muql', *args], cwd=ROOT,
                              env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)

    def test_list_displays_unicode_and_ascii_on_request(self):
        unicode = self.run_cli('list', 'examples/voting.md', '--notation', 'unicode')
        ascii = self.run_cli('list', 'examples/voting.md', '--notation', 'ascii')
        self.assertEqual(unicode.returncode, 0, unicode.stderr)
        self.assertEqual(ascii.returncode, 0, ascii.stderr)
        self.assertIn('⇀', unicode.stdout)
        self.assertIn('∃ꟴ□', unicode.stdout)
        self.assertNotIn('∃Q', unicode.stdout)
        self.assertIn('-\\', ascii.stdout)
        self.assertNotIn('=>', ascii.stdout)
        self.assertTrue(ascii.stdout.isascii())

    def test_limited_console_automatically_gets_ascii(self):
        result = self.run_cli('list', 'examples/voting.md', ascii_console=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('-\\', result.stdout)
        self.assertTrue(result.stdout.isascii())

    def test_cli_replacement_both_arrow_spellings_have_identical_results(self):
        outputs = []
        for formula in ('∃Q□vote ⇀ observe', '∃ꟴ□vote ⇀ observe', r'quorum(vote) -\ observe',
                        r'someQuorumEveryPoint(vote) -\ observe'):
            result = self.run_cli('check', 'examples/voting.md', '--replace',
                                  'Observe!='+formula, '--json', '-')
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(json.loads(result.stdout)['properties'])
        for output in outputs[1:]:
            self.assertEqual(outputs[0], output)

    def test_clashing_implication_is_rejected_in_theories_and_cli(self):
        source = ascii_document(load(ROOT/'examples/voting.md'))
        with self.assertRaisesRegex(ValueError, "'=>' is not supported"):
            loads(source.replace('-\\', '=>'))
        result = self.run_cli('check', 'examples/voting.md', '--replace',
                              'Observe!=quorum(vote) => observe', '--json', '-')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("'=>' is not supported", result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse(result.stdout.strip())

    def test_simpler_paxos_default_cli_checks_corrected_agreement(self):
        result = self.run_cli('check', 'examples/paxos_simpler.md', '--json', '-')
        self.assertEqual(result.returncode, 0, result.stderr)
        properties = json.loads(result.stdout)['properties']
        self.assertEqual({item['name']: item['status'] for item in properties},
                         {'Validity': 'holds', 'Agreement': 'holds', 'Termination': 'holds'})

    def test_display_wrapping_preserves_literals_and_ast(self):
        formula = parse_formula("P('a long quoted value with "+'space '*30+"and \\\'quotes\\\'') -\\ (Q & R)")
        for notation in ('unicode', 'ascii'):
            text = format_formula(formula, notation=notation)
            lines = _formula_lines(text, width=30)
            self.assertEqual(parse_formula('\n'.join(lines)), formula)


if __name__ == '__main__':
    unittest.main()
