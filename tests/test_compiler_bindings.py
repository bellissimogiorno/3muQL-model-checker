"""Binding-sensitive compilation must survive repeated and nested evaluation.

These cases exercise reuse of one compiler, rather than testing its cache
layout. Expected fixed points come from full-context lattice enumeration.
"""
from itertools import product
import unittest

from muql.compile import Compiler
from muql.evaluate import Evaluator
from muql.frame import Frame
from muql.sat import solve
from muql.syntax import parse_formula

from test_compile import global_oracle, theory_for


def decoded(pair, assignment):
    return sum(assignment[abs(literal)] == (literal > 0) for literal in pair)


class CompilerBindingTests(unittest.TestCase):
    def test_active_outer_bindings_are_never_reused_as_closed_results(self):
        frame = Frame(('p',), (frozenset({0}),), 1)
        theory = theory_for(frame)
        context = frame.contexts[0]
        compiler = Compiler(theory, frame)
        formulas = [parse_formula(text).args[0] for text in (
            'mu X. X', 'mu X. (mu Y. X | !Y)', 'mu X. (nu Y. X & !Y)',
        )] + [parse_formula('mu X. !X')]
        # Revisit prior bindings after other values; the independent inner
        # binder named X must hide the supplied outer interpretation of X.
        for value in (0, 2, 1, 0, 1, 2):
            bindings = {'X': {context: (compiler.f, compiler.b, compiler.t)[value]}}
            pairs = [compiler.eval(node, context, fix=bindings) for node in formulas]
            result = solve(compiler.circuit.nvars, compiler.circuit.clauses)
            self.assertEqual(result.status, 'sat')
            self.assertEqual([decoded(pair, result.assignment) for pair in pairs],
                             [value, max(1, value), min(1, value), 1])

    def test_value_bindings_remain_distinct_inside_the_same_recurrence(self):
        frame = Frame(('p',), (frozenset({0}),), 1)
        theory = theory_for(frame)
        compiler = Compiler(theory, frame)
        context = frame.contexts[0]
        node = parse_formula('mu X. R(v) | X')
        pairs = [compiler.eval(node, context, env={'v': value})
                 for value in ('red', 'blue', 'red')]
        clauses = [*compiler.circuit.clauses]
        for (_, _, _, terms), (low, high) in compiler.cells.items():
            value = 0 if terms == ('red',) else 2
            clauses.extend([[low if value >= 1 else -low], [high if value == 2 else -high]])
        result = solve(compiler.circuit.nvars, clauses)
        self.assertEqual(result.status, 'sat')
        self.assertEqual([decoded(pair, result.assignment) for pair in pairs], [0, 2, 0])

    def test_nested_recurrences_match_full_context_definition(self):
        texts = (
            'mu X. P | yesterday(X)',
            'nu X. P & tomorrow(X)',
            'mu X. (mu Y. P | Y) | !X',
            'nu X. (nu Y. P & Y) & !X',
            'mu X. (mu Y. X | !Y)',
            'nu X. (nu Y. X & !Y)',
        )
        for time in ('finite', 'stutter'):
            frame = Frame(('p',), (frozenset({0}),), 2, time)
            theory = theory_for(frame)
            compiler = Compiler(theory, frame)
            formulas = [parse_formula(text) for text in texts]
            outputs = [(node, context, compiler.eval(node, context))
                       for node in formulas for context in frame.contexts]
            # Every assignment to P at both stages. R and Q are unused here.
            for values in product(range(3), repeat=2):
                valuation = {('P', stage, 0, ()): value for stage, value in enumerate(values)}
                evaluator = Evaluator(theory, frame, valuation)
                clauses = [*compiler.circuit.clauses]
                for key, (low, high) in compiler.cells.items():
                    value = valuation[key]
                    clauses.extend([[low if value >= 1 else -low], [high if value == 2 else -high]])
                expected = [global_oracle(node, context, frame, valuation)
                            for node, context, _ in outputs]
                result = solve(compiler.circuit.nvars, clauses)
                self.assertEqual(result.status, 'sat')
                for (node, context, pair), value in zip(outputs, expected):
                    with self.subTest(time=time, values=values, node=str(node), context=context):
                        self.assertEqual(decoded(pair, result.assignment), value)
                        self.assertEqual(evaluator.eval(node, context), value)
                # Prove the compiled outputs are forced, rather than accepting
                # a single lucky SAT assignment that happens to match.
                mismatch = [(-literal if value >= threshold else literal)
                            for (_, _, pair), value in zip(outputs, expected)
                            for threshold, literal in enumerate(pair, 1)]
                self.assertEqual(solve(compiler.circuit.nvars, [*clauses, mismatch]).status, 'unsat')


if __name__ == '__main__':
    unittest.main()
