#!/usr/bin/env python3
"""Compare the bundled rule-label migration with a reference source checkout.

python tools/audit_rule_labels.py --reference /path/to/reference-source --output audit.json

Compare scopes, ordered labels, macros and complete formula trees, followed by
the existing CNF/report/progress/export/replay comparison. Only the explicit,
one-to-one label migration, package version and elapsed report times are
normalized. Both engines run in separate processes. Standard library only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from audit_equivalence import collect, fingerprint


ROOT = Path(__file__).resolve().parents[1]
THEORIES = '''
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from muql import load
def node(value):
    return [value.op, value.value, [node(arg) for arg in value.args]]
result = {}
for path in sorted((root / 'examples').rglob('*.md')):
    theory = load(path, for_search=True)
    result[str(path.relative_to(root / 'examples'))] = {
        **{key: getattr(theory, key) for key in
           ('name', 'points', 'values', 'stages', 'time', 'quorums', 'predicates', 'scope_declared')},
        'axioms': {name: node(value) for name, value in theory.axioms.items()},
        'properties': {name: node(value) for name, value in theory.properties.items()},
        'axiom_order': list(theory.axioms), 'property_order': list(theory.properties),
        'macros': {name: [macro.parameters, node(macro.body)]
                   for name, macro in theory._macros.items()},
    }
print(json.dumps(result, ensure_ascii=True))
'''


def theories(package):
    result = subprocess.run([sys.executable, '-B', '-c', THEORIES, str(package)],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reference = args.reference.resolve()
    fixture = json.loads((ROOT / 'tests/data/rule-label-renames.json').read_text())
    labels = fixture['renames']
    assert len(labels) == len(set(labels.values())), 'label map must be one-to-one'
    token = re.compile(r'\b(?:' + '|'.join(map(re.escape, sorted(labels, key=len, reverse=True))) + r')\b')

    def renamed(value):
        if isinstance(value, dict):
            result = {renamed(key): renamed(item) for key, item in value.items()}
            assert len(result) == len(value), 'label normalization collided'
            return result
        if isinstance(value, list):
            return [renamed(item) for item in value]
        if isinstance(value, str):
            return token.sub(lambda match: labels[match[0]], value)
        return value

    before, after = theories(reference), theories(ROOT)
    assert before.keys() == after.keys(), 'example inventory changed'
    declarations = 0
    for filename, mapping in fixture['examples'].items():
        assert mapping.keys() <= before[filename]['axioms'].keys()
        assert set(mapping.values()) <= after[filename]['axioms'].keys()
        declarations += len(mapping)
    assert renamed(before) == after, 'theory meaning or an unlisted label changed'

    old_files = {p.name: p.read_bytes() for p in (reference / 'muql').glob('*.py')}
    new_files = {p.name: p.read_bytes() for p in (ROOT / 'muql').glob('*.py')}
    engine_changes = sorted(name for name in old_files.keys() | new_files.keys()
                            if old_files.get(name) != new_files.get(name))
    assert engine_changes == ['__init__.py'], engine_changes
    old_init = old_files['__init__.py'].decode()
    new_init = new_files['__init__.py'].decode()
    version = re.compile(r"__version__ = '[^']+'")
    assert version.sub('__version__ = VERSION', old_init) == version.sub('__version__ = VERSION', new_init)

    with tempfile.TemporaryDirectory(prefix='muql-rule-labels-') as temporary:
        directory = Path(temporary)
        old = collect(reference, directory / 'reference.json')
        new = collect(ROOT, directory / 'current.json')
    normalized = renamed(old['records'])
    differences = [name for name in sorted(normalized.keys() | new['records'].keys())
                   if normalized.get(name) != new['records'].get(name)]
    result = {
        'reference_version': old['version'], 'version': new['version'],
        'status': 'failed' if differences else 'passed',
        'examples_compared': len(before), 'theory_files_renamed': len(fixture['examples']),
        'distinct_labels_renamed': len(labels), 'declarations_renamed': declarations,
        'full_formula_trees_macros_scopes_and_order': 'identical after explicit label migration',
        'theory_sha256': fingerprint(after), 'engine_change': 'version only',
        'records_compared': len(normalized), 'differences': differences,
        'reference_normalized_sha256': fingerprint(normalized),
        'current_sha256': fingerprint(new['records']),
        'normalized': ['explicit label map', 'package version', 'report stats.seconds'],
        'label_map': labels,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return bool(differences)


if __name__ == '__main__':
    raise SystemExit(main())
