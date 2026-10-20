"""Paper-style rule labels survive editing, selection, export and replay."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from muql import check, format_theory, loads, parse_formula, replay
from muql.theory import TheoryError, validate_theory
from muql.web import handle_json


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = '''```muql
theory "Symbolic labels"
predicate P/0
axiom PaxWrite?: T(P) # backward rule
axiom PaxWrite!: TF(P) // forward rule
axiom PaxDecide-not-L!: t
property Goal?: P
property Goal!: !P
```'''
SCOPED = TEMPLATE.replace('predicate P/0', '''points a
values unit
stages 1
quorums {a}
predicate P/0''')
BOUNDS = {"max_points": 1, "max_values": 1, "max_stages": 1, "max_quorums": 1}


def web(source, **options):
    return json.loads(handle_json(json.dumps({
        "action": "run", "source": source, "solver": "builtin", **options,
    })))


class RuleLabelTests(unittest.TestCase):
    def test_direction_marks_distinguish_rules_and_keep_formula_negation(self):
        theory = loads(SCOPED)
        self.assertEqual(list(theory.axioms), ['PaxWrite?', 'PaxWrite!', 'PaxDecide-not-L!'])
        self.assertEqual(theory.properties['Goal!'], parse_formula('!P'))
        self.assertEqual({r.name: r.status for r in check(theory).properties},
                         {'Goal?': 'holds', 'Goal!': 'counterexample'})
        # There is no whitespace requirement around the declaration's colon.
        compact = loads(SCOPED.replace('property Goal!: !P', 'property Goal!:!P'))
        self.assertEqual(compact.properties, theory.properties)

    def test_public_theory_validation_and_both_export_notations_agree(self):
        theory = loads(SCOPED)
        theory = replace(theory, axioms={**theory.axioms, '_Rule!?-2': parse_formula('t')})
        validate_theory(theory)
        for notation in ('unicode', 'ascii'):
            with self.subTest(notation=notation):
                exported = format_theory(theory, notation=notation)
                restored = loads(exported)
                self.assertIn('axiom _Rule!?-2:', exported)
                self.assertEqual(restored.axioms, theory.axioms)
                self.assertEqual(restored.properties, theory.properties)

    def test_exact_label_drop_and_replacement_preserve_the_original(self):
        theory = loads(SCOPED)
        edited = theory.without('PaxWrite!').replace('PaxWrite?', '!P')
        self.assertEqual(list(edited.axioms), ['PaxWrite?', 'PaxDecide-not-L!'])
        self.assertEqual(edited.axioms['PaxWrite?'], parse_formula('!P'))
        self.assertEqual(theory.axioms['PaxWrite?'], parse_formula('T(P)'))
        self.assertIn('PaxWrite!', theory.axioms)
        for action in (lambda: theory.without('PaxWrite'), lambda: theory.replace('PaxWrite', 't')):
            with self.assertRaisesRegex(TheoryError, 'unknown axiom'):
                action()

    def test_duplicate_labels_still_share_one_namespace(self):
        for declaration in ('axiom PaxWrite?: t', 'property PaxWrite?: t'):
            with self.subTest(declaration=declaration):
                with self.assertRaisesRegex(TheoryError, r"duplicate axiom or property name 'PaxWrite\?'"):
                    loads(SCOPED.rsplit('```', 1)[0] + declaration + '\n```')
        theory = loads(SCOPED)
        with self.assertRaisesRegex(TheoryError, 'labels must be distinct'):
            validate_theory(replace(theory, properties={'PaxWrite?': parse_formula('t')}))

    def test_rule_punctuation_does_not_extend_formula_identifiers(self):
        for declaration in ('predicate P!/0', 'predicate P?/0', 'let Rule!(): t',
                            'let Rule?(): t', 'let Rule(x?): t', 'property Goal: forall x?. P'):
            with self.subTest(declaration=declaration):
                with self.assertRaises(TheoryError):
                    loads(SCOPED.rsplit('```', 1)[0] + declaration + '\n```')

    def test_invalid_labels_are_rejected_by_loader_and_public_api(self):
        theory = loads(SCOPED)
        for name in ('', '!Rule', '?Rule', '1Rule', 'Two words', 'Rule=Other', 'Rule/path'):
            with self.subTest(name=name):
                with self.assertRaises(TheoryError):
                    loads(SCOPED.rsplit('```', 1)[0] + f'axiom {name}: t\n```')
                with self.assertRaisesRegex(TheoryError, 'invalid axioms name'):
                    validate_theory(replace(theory, axioms={name: parse_formula('t')}))

    def test_formula_error_coordinates_include_the_whole_symbolic_label(self):
        line = 'axiom PaxDecide-not-L?!: P => P'
        source = SCOPED.rsplit('```', 1)[0] + line + '\n```'
        with self.assertRaises(TheoryError) as caught:
            loads(source, source='rules.md')
        self.assertEqual(caught.exception.source, 'rules.md')
        self.assertEqual(caught.exception.line, source.splitlines().index(line) + 1)
        self.assertEqual(caught.exception.column, line.index('=>') + 1)

    def test_web_inspection_selection_and_retained_exports_preserve_labels(self):
        inspected = web(SCOPED, action='inspect')
        self.assertTrue(inspected['ok'], inspected)
        self.assertEqual([a['name'] for a in inspected['metadata']['axioms']],
                         list(loads(SCOPED).axioms))
        for mode, source in (('check', SCOPED), ('search', TEMPLATE)):
            with self.subTest(mode=mode):
                result = web(source, mode=mode, properties=['Goal?'], drop=['PaxWrite?'], limits=BOUNDS)
                self.assertTrue(result['ok'], result)
                self.assertEqual(result['report']['properties'][0]['name'], 'Goal?')
                self.assertEqual(result['report']['properties'][0]['status'], 'counterexample')
                retained = next(d for d in result['downloads'] if d['name'] == 'theory')
                theory = loads(retained['content'], for_search=mode == 'search')
                self.assertNotIn('PaxWrite?', theory.axioms)
                self.assertIn('PaxWrite!', theory.axioms)
                self.assertEqual(theory.scope_declared, mode == 'check')

    def test_web_witness_names_are_portable_distinct_and_replayable(self):
        result = web(TEMPLATE, mode='search', drop=['PaxWrite?'], limits=BOUNDS)
        self.assertTrue(result['ok'], result)
        downloads = {item['name']: item for item in result['downloads']}
        filenames = [item['filename'] for item in downloads.values()]
        self.assertEqual(len(filenames), len(set(filenames)))
        self.assertTrue(all(not any(c in filename for c in '<>:"/\\|?*') for filename in filenames))
        for name in ('Goal?', 'Goal!'):
            concrete = loads(downloads[f'witness-{name}-theory']['content'])
            witness = json.loads(downloads[f'witness-{name}-countermodel']['content'])
            self.assertEqual(witness['property'], name)
            self.assertEqual(set(witness['axiom_values']), {'PaxWrite!', 'PaxDecide-not-L!'})
            self.assertTrue(replay(concrete, witness))

    def test_cli_list_drop_replacement_and_selected_property(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.md'
            path.write_text(SCOPED, encoding='utf-8')
            listed = self.cli('list', path)
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn('PaxWrite?', listed.stdout)
            self.assertIn('PaxWrite!', listed.stdout)
            for edits, expected in (([], 'holds'), (['--drop', 'PaxWrite?'], 'counterexample'),
                                    (['--replace', 'PaxWrite?=!P'], 'counterexample'),
                                    (['--drop', 'PaxWrite?', '--replace', 'PaxWrite!=!P'], 'counterexample')):
                result = self.cli('check', path, *edits, '--property', 'Goal?', '--json', '-')
                self.assertEqual(result.returncode, int(expected == 'counterexample'), result.stderr)
                self.assertEqual([(p['name'], p['status']) for p in json.loads(result.stdout)['properties']],
                                 [('Goal?', expected)])

    def test_cli_search_exports_both_colliding_filenames_and_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'input.md'
            path.write_text(TEMPLATE, encoding='utf-8')
            witnesses = root / 'witnesses'
            result = self.cli('search', path, '--drop', 'PaxWrite?', '--solver', 'builtin',
                              '--max-points', '1', '--max-values', '1', '--max-stages', '1',
                              '--max-quorums', '1', '--countermodels', witnesses, '--json', '-')
            self.assertEqual(result.returncode, 1, result.stderr)
            files = sorted(witnesses.glob('*.json'))
            self.assertEqual([p.name for p in files], ['01-Goal_.json', '02-Goal_.json'])
            self.assertEqual({json.loads(p.read_text())['property'] for p in files}, {'Goal?', 'Goal!'})
            for witness in files:
                concrete = witness.with_suffix('.md')
                replayed = self.cli('replay', concrete, witness)
                self.assertEqual(replayed.returncode, 0, replayed.stderr)

    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'muql', *map(str, args)], cwd=ROOT,
                              capture_output=True, text=True, encoding='utf-8', timeout=30)


if __name__ == '__main__':
    unittest.main()
