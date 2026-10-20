#!/usr/bin/env python3
"""Time compilation alone on fixed workloads; no solver or runtime download.

Run separately against each source tree with --package. Alternate their order
and use several fresh processes when comparing versions. Medians are local
measurements, not performance assertions. Fingerprints detect CNF changes.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--repeats', type=int, default=9)
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    package = args.package.resolve()
    if not (package / 'muql/__init__.py').is_file():
        parser.error('--package must contain muql/')
    sys.path.insert(0, str(package))
    from muql import load, loads, parse_formula
    from muql.compile import Compiler
    from muql.frame import Frame

    base = loads('''```muql
theory Compilation
points a
values red blue
stages 16
quorums {a}
predicate P/0
predicate Q/0
predicate R/1
property Past: mu X. (P & forall v. R(v)) | yesterday(X)
property Future: nu X. (Q | exists v. R(v)) & tomorrow(X)
```''')
    nested = replace(base, stages=1, properties={
        'Dependent': parse_formula('mu X. (mu Y. (mu Z. X | Y | !Z) & !Y)'),
        'Independent': parse_formula('mu X. (mu Y. (mu Z. R(red) | !Z) & !Y) | !X'),
    })
    cases = [(name, load(package / 'examples' / (name + '.md')))
             for name in ('fixedpoints', 'paxos', 'paxos_simpler')]
    cases.extend([('16-stage temporal', base), ('nested recurrences', nested)])
    results = []
    for label, theory in cases:
        frame = Frame.from_theory(theory)
        times = []
        expected = None
        for _ in range(args.repeats):
            compiler = Compiler(theory, frame)
            start = perf_counter()
            for formula in (*theory.axioms.values(), *theory.properties.values()):
                for context in frame.contexts:
                    compiler.eval(formula, context)
            compiler.budget(force=True)
            times.append(perf_counter() - start)
            image = json.dumps([compiler.circuit.nvars, compiler.circuit.clauses], separators=(',', ':'))
            digest = hashlib.sha256(image.encode('ascii')).hexdigest()
            if expected is not None and digest != expected:
                raise AssertionError('nondeterministic compilation: ' + label)
            expected = digest
        results.append({'case': label, 'repetitions': args.repeats,
                        'seconds': times, 'median_seconds': median(times),
                        'variables': compiler.circuit.nvars,
                        'clauses': len(compiler.circuit.clauses), 'cnf_sha256': expected})
    print(json.dumps(results, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
