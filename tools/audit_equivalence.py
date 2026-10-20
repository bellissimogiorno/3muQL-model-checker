#!/usr/bin/env python3
"""Compare this checkout with a reference source tree in separate processes.

python tools/audit_equivalence.py --reference /path/to/reference --output audit.json

Checks exact CNF fingerprints, reports, progress, witness exports/replay, error
handling and browser-bridge payloads on deterministic workloads. Only elapsed
report times are removed. This is a regression comparison, not an independent
semantic oracle; run the semantic oracle and ordinary test suites as well.
No downloads, installed packages, or changes to either source tree are needed.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RECURRENCES = (
    'mu X. P | yesterday(X)', 'nu X. P & tomorrow(X)',
    'mu X. !X', 'nu X. !X', 'mu X. (X <=> P)', 'nu X. (X <= P)',
    'mu X. (mu Y. X | !Y)', 'nu X. (nu Y. X & !Y)',
    'mu X. (mu Y. P | Y) | !X', 'nu X. (nu Y. P & Y) & !X',
    'mu X. exists v. R(v) | !X', 'nu X. forall v. R(v) & tomorrow(X)',
    'mu X. !diamond(P & X)', 'nu X. existsQ(X) | P',
    'mu X. forallQ(X) & P', 'mu X. TB(X) | P', 'nu X. FB(X) & P',
    'mu X. (X -> P)', 'nu X. (P -\\ X)', 'mu X. (X xor P)',
    'mu X. past(X) | P', 'nu X. forever(X) & P',
    'mu X. quorum(X) | P', 'nu X. contra(X) & P',
)


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def untimed(report):
    result = deepcopy(report)
    result.get('stats', {}).pop('seconds', None)
    return result


def snapshot(package):
    """Import only the requested engine; do not mix versions in sys.modules."""
    sys.path.insert(0, str(package))
    import demo
    import muql
    from muql import check, format_theory, loads, replay, search, witness_theory
    from muql.compile import Compiler
    from muql.frame import Frame
    from muql.syntax import parse_formula
    from muql.web import handle_json

    records = {}

    def record_run(label, theory, properties=None, *, bounds=None, **limits):
        events = []
        if bounds is None:
            report = check(theory, properties, progress=events.append, **limits)
        else:
            report = search(theory, properties, progress=events.append,
                            solver='builtin', **bounds, **limits)
        exports = []
        for item in report.properties:
            if item.countermodel is not None:
                concrete = witness_theory(theory, item.countermodel)
                exports.append({'theory': format_theory(concrete),
                                'ascii': format_theory(concrete, notation='ascii'),
                                'table': item.countermodel.format(),
                                'replay': replay(concrete, item.countermodel)})
        records[label] = {'report': untimed(report.to_dict()), 'progress': events, 'exports': exports}

    for case in demo.scenarios():
        record_run('demo/' + case.key, case.theory, case.properties,
                   bounds=case.search_bounds)

    # Compare the actual Boolean translation, including variable/cell order.
    # Two temporal contexts, or four spatial contexts including p outside O.
    for spatial in (False, True):
        for time in ('finite', 'stutter'):
            theory = loads('''```muql
theory Audit
points a
values red blue
stages 2
quorums {a}
predicate P/0
predicate R/1
```''')
            theory = replace(theory, time=time)
            if spatial:
                theory = replace(theory, points=('a', 'z'), quorums=(('a',), ('a', 'z')), stages=1)
            frame = Frame.from_theory(theory)
            compiler = Compiler(theory, frame)
            for index, text in enumerate(RECURRENCES):
                # Nested arbitrary recurrences are expensive on four contexts;
                # they are compared exhaustively on the temporal frames above.
                if spatial and index in (6, 7, 8, 9):
                    continue
                node = parse_formula(text)
                pairs = [compiler.eval(node, context) for context in frame.contexts]
                image = {'variables': compiler.circuit.nvars, 'clauses': compiler.circuit.clauses,
                         'cells': [[list(key[:3]) + [list(key[3])], pair]
                                   for key, pair in compiler.cells.items()], 'outputs': pairs}
                records[f'cnf/{spatial}/{time}/{index:02d}'] = fingerprint(image)

    theory = loads('''```muql
theory Boundaries
points a b
values red blue
stages 2
quorums {a} {a,b}
predicate P/0
predicate R/1
axiom Correct: TF(P)
property Always: P | !P
property Goal: T(P)
```''')
    for key, options in (
        ('nodes', {'max_nodes': 1}), ('decisions', {'max_decisions': 0}),
        ('zero', {'timeout': 0}), ('total-zero', {'total_timeout': 0}),
    ):
        record_run('cutoff/' + key, theory, **options)
    record_run('cutoff/frames', theory, bounds={
        'max_points': 2, 'max_values': 2, 'max_stages': 2, 'max_frames': 1})
    record_run('axioms-only', theory, properties=[])
    record_run('inconsistent', replace(theory, axioms={'Impossible': parse_formula('f')}))
    general = replace(theory, properties={'Goal': parse_formula('mu X. !box(X)')})
    record_run('cutoff/recurrence', general, max_mu_contexts=1)

    # Serialized flags and summaries do not make a witness valid. Check both
    # descriptive tampering (accepted) and structural/semantic tampering.
    model = check(theory).properties[1].countermodel.to_dict()
    for key in ('replayed', 'axiom_values'):
        changed = deepcopy(model)
        changed[key] = False if key == 'replayed' else {'Invented': ['t']}
        records['replay/ignored/' + key] = replay(theory, changed)
    for label, mutate in (
        ('missing', lambda data: data['valuation'].pop()),
        ('duplicate', lambda data: data['valuation'].append(data['valuation'][0])),
        ('float-time', lambda data: data['failure'].update(time=0.0)),
        ('boolean-time', lambda data: data['valuation'][0].update(time=False)),
        ('wrong-failure', lambda data: data['failure'].update(value='b')),
        ('unknown-property', lambda data: data.update(property='Missing')),
        ('bad-scope', lambda data: data['scope'].update(stages=999)),
    ):
        changed = deepcopy(model)
        mutate(changed)
        try:
            replay(theory, changed)
        except ValueError as error:
            records['replay/rejected/' + label] = str(error)
        else:
            raise AssertionError('invalid replay accepted: ' + label)

    source = format_theory(theory)
    for action, mode in (('inspect', 'check'), ('run', 'check'), ('run', 'search')):
        events = []
        request = {'action': action, 'mode': mode, 'source': source,
                   'limits': {'max_points': 2, 'max_values': 2, 'max_stages': 1}}
        result = json.loads(handle_json(json.dumps(request), events.append))
        assert result['ok'], result
        if 'report' in result:
            result['report'] = untimed(result['report'])
        for item in result.get('downloads', []):
            if item['name'] == 'report':
                item['content'] = untimed(json.loads(item['content']))
        records['bridge/' + action + '/' + mode] = {'result': result, 'progress': events}
    return {'version': muql.__version__, 'records': records}


def collect(package, destination):
    subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
                    '--snapshot', str(package), '--output', str(destination)], check=True)
    return json.loads(destination.read_text(encoding='utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.snapshot is not None:
        result = snapshot(args.snapshot.resolve())
    else:
        if args.reference is None or not (args.reference / 'muql').is_dir():
            parser.error('--reference must contain the reference muql package')
        with tempfile.TemporaryDirectory(prefix='muql-equivalence-') as directory:
            directory = Path(directory)
            before = collect(args.reference.resolve(), directory / 'reference.json')
            after = collect(ROOT, directory / 'current.json')
        changed = [key for key in sorted(before['records'].keys() | after['records'].keys())
                   if before['records'].get(key) != after['records'].get(key)]
        result = {'reference_version': before['version'], 'version': after['version'],
                  'records_compared': len(before['records']), 'differences': changed,
                  'reference_sha256': fingerprint(before['records']),
                  'current_sha256': fingerprint(after['records']),
                  'ignored': ['package version', 'report stats.seconds'],
                  'coverage': '30 demos; 88 cumulative CNF fingerprints; budgets; replay; bridge; progress; exports'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    if args.snapshot is None:
        print(json.dumps(result, indent=2))
        return 1 if result['differences'] else 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
