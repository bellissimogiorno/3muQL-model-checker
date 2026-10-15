"""Measure fixed workloads, including SAT calls and independent axiom replays.

Run against this checkout, or use --package /path/to/another/release to compare.
Timings are evidence, not performance assertions in the test suite.
"""
import argparse
import json
from pathlib import Path
from statistics import median
import sys
import time
from unittest.mock import patch
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parents[1])
args = parser.parse_args()
package = args.package.resolve()
if not (package / 'muql' / '__init__.py').is_file() or not (package / 'demo.py').is_file():
    parser.error('--package must name a source release containing muql/ and demo.py')
sys.path.insert(0, str(package))
import demo
from muql import check, loads
import muql.checker as checker

synthetic = loads('''```muql
points a b c d
values red blue
stages 3
quorums {a,b,c} {a,b,d} {a,c,d} {b,c,d}
predicate P/1
predicate Q/1
axiom Related: forall v. P(v) ≡ Q(v)
property A: forall v. P(v)
property B: exists v. Q(v)
property C: everywhere(P(red))
property D: somewhere(P(blue))
property E: quorum(Q(red))
property F: contra(Q(blue))
property G: T(P(red))
property H: T(Q(blue))
property I: past(P(red))
property J: once(Q(blue))
property K: tomorrow(P(red))
property L: sometime(Q(blue))
```''')
cases = [(case.key, case.theory, case.properties) for case in demo.fixed_scenarios() if case.key in {'semitopology', 'fixedpoints', 'bracha_without_relay', 'spax_without_write_affine'}]
cases.append(('multiple_conjectures', synthetic, None))
rows=[]
for label, theory, properties in cases:
    elapsed=[]
    for _ in range(7):
        with patch('muql.checker.solve', wraps=checker.solve) as solve:
            with patch('muql.checker._replay_axioms', wraps=checker._replay_axioms) as replay:
                start=time.perf_counter(); result=check(theory, properties); elapsed.append(time.perf_counter()-start)
        calls=solve.call_count; replays=replay.call_count
    rows.append(dict(case=label, seconds=median(elapsed), solver_calls=calls, axiom_replays=replays, decisions=result.stats['decisions'], statuses=[p.status for p in result.properties]))
print(json.dumps(rows, indent=2))
