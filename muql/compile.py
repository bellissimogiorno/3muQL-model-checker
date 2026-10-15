"""Bit-vector compilation of three-valued formulas into propositional CNF.

A pair (valid, true) represents the two thresholds x >= b and x == t.
This encoding is order preserving and the forbidden pair (False, True)
is excluded for every atomic cell. No two-valued substitution is performed.
"""
from itertools import product
from math import isnan
from time import monotonic
from .syntax import Node
from .sat import Circuit


class ResourceLimit(RuntimeError):
    """An exact compilation exceeded its declared resource budget."""


def free_fix(node, variable):
    if node.op == 'var':
        return node.value == variable
    if node.op in ('mu', 'nu') and node.value == variable:
        return False
    return any(free_fix(a, variable) for a in node.args)


def positive(node, variable, polarity=1):
    """Conservative monotonicity certificate, never an optimistic guess."""
    if not free_fix(node, variable):
        return True
    if node.op == 'var':
        return polarity == 1
    if node.op in ('not', 'F', 'FB'):
        return positive(node.args[0], variable, -polarity)
    if node.op in ('and', 'or', 'T', 'TB', 'box', 'diamond', 'existsQ', 'forallQ',
                   'quorum', 'contra', 'somewhere', 'everywhere', 'yesterday',
                   'tomorrow', 'once', 'past', 'historically', 'sometime', 'forever',
                   'infinitely', 'ultimately', 'forall', 'exists', 'mu', 'nu'):
        return all(positive(a, variable, polarity) for a in node.args)
    if node.op in ('weak', 'strong'):
        return positive(node.args[0], variable, -polarity) and positive(node.args[1], variable, polarity)
    return False


class Compiler:
    def __init__(self, theory, frame, *, timeout=30.0, max_nodes=500000,
                 max_mu_contexts=8):
        if isnan(timeout) or timeout < 0:
            raise ValueError('compilation timeout must be nonnegative and not NaN')
        if any(type(limit) is not int or limit < 1 for limit in (max_nodes, max_mu_contexts)):
            raise ValueError('compilation node/context limits must be positive integers')
        self.theory, self.frame = theory, frame
        self.circuit = Circuit()
        self.cells = {}
        self.cache = {}
        self.mu_cache = {}
        self.deadline = monotonic() + timeout
        self.max_nodes = max_nodes
        self.max_mu_contexts = max_mu_contexts
        self.f = (-1, -1)
        self.b = (1, -1)
        self.t = (1, 1)
        self.steps = 0

    def budget(self, force=False):
        self.steps += 1
        if force or self.steps == 1 or self.steps % 256 == 0:
            if monotonic() > self.deadline:
                raise ResourceLimit('formula compilation timeout')
            if self.circuit.nvars > self.max_nodes:
                raise ResourceLimit(f'formula circuit exceeds {self.max_nodes} variables')

    def both(self, pairs):
        pairs = tuple(pairs)
        return tuple(self.circuit.and_(*(p[i] for p in pairs)) for i in range(2))

    def either(self, pairs):
        pairs = tuple(pairs)
        return tuple(self.circuit.or_(*(p[i] for p in pairs)) for i in range(2))

    @staticmethod
    def neg(pair):
        return (-pair[1], -pair[0])

    @staticmethod
    def crisp(literal):
        return (literal, literal)

    def leq(self, left, right):
        return self.circuit.and_(*(self.circuit.implies(a, b) for a, b in zip(left, right)))

    def cell(self, name, time, point, terms):
        key = (name, time, point, terms)
        if key not in self.cells:
            low = self.circuit.new_var()
            high = self.circuit.new_var()
            self.circuit.add_clause(-high, low)
            self.cells[key] = low, high
        return self.cells[key]

    def term(self, node, env):
        if node.op == 'literal':
            return node.value
        return env.get(node.value, node.value)

    def eval(self, node, ctx, env=None, fix=None):
        self.budget()
        env = {} if env is None else env
        fix = {} if fix is None else fix
        # Only cache formulas independent of the current recurrence interpretation.
        cacheable = not any(free_fix(node, v) for v in fix)
        key = (node, ctx, tuple(sorted(env.items())))
        if cacheable and key in self.cache:
            return self.cache[key]
        answer = self._eval(node, ctx, env, fix)
        if cacheable:
            self.cache[key] = answer
        return answer

    def _eval(self, n, ctx, env, fix):
        op, args = n.op, n.args
        t, p, q = ctx
        c = self.circuit
        ev = lambda a, context=ctx, bindings=env: self.eval(a, context, bindings, fix)
        if op == 'const':
            return {'f': self.f, 'b': self.b, 't': self.t}[n.value]
        if op == 'var':
            return fix[n.value][ctx]
        if op == 'pred':
            return self.cell(n.value, t, p, tuple(self.term(a, env) for a in args))
        if op in ('eq', 'neq'):
            yes = self.term(args[0], env) == self.term(args[1], env)
            return self.t if yes == (op == 'eq') else self.f
        if op == 'twined':
            return self.t if self.frame.twined(int(n.value), checkpoint=lambda: self.budget(force=True)) else self.f
        if op == 'not':
            return self.neg(ev(args[0]))
        if op in ('T', 'F', 'B', 'TB', 'TF', 'FB'):
            lo, hi = ev(args[0])
            bit = {'T': lambda: hi, 'F': lambda: -lo, 'B': lambda: c.and_(lo, -hi),
                   'TB': lambda: lo, 'TF': lambda: c.or_(-lo, hi), 'FB': lambda: -hi}[op]()
            return self.crisp(bit)
        if op in ('and', 'or', 'weak', 'strong', 'equiv', 'order', 'xor'):
            a, b = ev(args[0]), ev(args[1])
            if op == 'and': return self.both((a, b))
            if op == 'or': return self.either((a, b))
            if op == 'weak': return self.either((self.neg(a), b))
            if op == 'strong': return self.either((self.neg(a), self.crisp(b[1])))
            if op == 'equiv': return self.crisp(c.and_(c.iff(a[0], b[0]), c.iff(a[1], b[1])))
            if op == 'order': return self.crisp(self.leq(a, b))
            return self.either((self.both((a, self.neg(b))), self.both((self.neg(a), b))))
        if op in ('forall', 'exists', 'affine', 'unique'):
            vals = [ev(args[0], bindings={**env, n.value: value}) for value in self.theory.values]
            if op == 'forall': return self.both(vals)
            if op == 'exists': return self.either(vals)
            # The join of all distinct pairwise meets is the second-largest
            # truth value. Its negation is affinity. This lattice fold builds
            # a linear circuit instead of one gate per pair of witnesses.
            largest = second = self.f
            for index, value in enumerate(vals):
                second = self.either((second, self.both((largest, value))))
                # Affinity needs no final maximum; uniqueness also needs the
                # existential witness. Omit unused gates in small domains.
                if op == 'unique' or index + 1 < len(vals):
                    largest = self.either((largest, value))
            affine = self.neg(second)
            return affine if op == 'affine' else self.both((largest, affine))
        if op in ('existsQ', 'forallQ', 'diamond', 'box', 'quorum', 'contra', 'somewhere', 'everywhere'):
            if op in ('existsQ', 'forallQ'):
                vals = (ev(args[0], (t, p, r)) for r in range(len(self.frame.quorums)))
                return self.either(vals) if op == 'existsQ' else self.both(vals)
            if op in ('diamond', 'box'):
                vals = (ev(args[0], (t, x, q)) for x in sorted(self.frame.quorums[q]))
                return self.either(vals) if op == 'diamond' else self.both(vals)
            inner = self.both if op in ('quorum', 'everywhere') else self.either
            outer = self.either if op in ('quorum', 'somewhere') else self.both
            return outer(inner(ev(args[0], (t, x, r)) for x in sorted(quorum))
                         for r, quorum in enumerate(self.frame.quorums))
        if op in ('yesterday', 'tomorrow'):
            nt = t - 1 if op == 'yesterday' else t + 1
            if nt == self.frame.stages and self.frame.time == 'stutter': nt = t
            if nt < 0 or nt >= self.frame.stages: return self.f
            return ev(args[0], (nt, p, q))
        if op in ('once', 'past', 'historically', 'sometime', 'forever'):
            times = range(t + (op == 'past')) if op in ('once','past','historically') else self.frame.future(t)
            vals = (ev(args[0], (nt, p, q)) for nt in times)
            return self.both(vals) if op in ('historically', 'forever') else self.either(vals)
        if op == 'infinitely':
            return ev(Node('forever', (Node('sometime', args),)))
        if op == 'ultimately':
            return ev(Node('sometime', (Node('everywhere', (Node('forever', args),)),)))
        if op == 'latest':
            target, body = args
            wanted = self.term(target, env)
            answer = c.false
            none_later = c.true
            for nt in reversed(range(t)):
                at = (nt, p, q)
                witness = ev(body, at, {**env, n.value: wanted})[1]
                any_true = c.or_(*(ev(body, at, {**env, n.value: value})[1] for value in self.theory.values))
                answer = c.or_(answer, c.and_(none_later, witness))
                none_later = c.and_(none_later, -any_true)
            return self.crisp(answer)
        if op in ('mu', 'nu'):
            return self.fixed(n, ctx, env, fix)
        raise ValueError(f'unsupported AST operation {op!r}')

    def dependencies(self, node, ctx, variable):
        """Conservative context dependency graph for one bound variable."""
        if not free_fix(node, variable): return set()
        if node.op == 'var': return {ctx}
        t, p, q = ctx
        op = node.op
        if op in ('mu', 'nu'):
            # Nested recurrences can transport an outer variable transitively.
            return set(self.frame.contexts)
        if op in ('box', 'diamond'):
            contexts = [(t, x, q) for x in self.frame.quorums[q]]
        elif op in ('existsQ', 'forallQ'):
            contexts = [(t, p, r) for r in range(len(self.frame.quorums))]
        elif op in ('quorum', 'contra', 'somewhere', 'everywhere'):
            contexts = [(t, x, r) for r, qq in enumerate(self.frame.quorums) for x in qq]
        elif op == 'yesterday': contexts = [(t-1,p,q)] if t else []
        elif op == 'tomorrow':
            nt = min(t+1,self.frame.stages-1) if self.frame.time == 'stutter' else t+1
            contexts = [(nt,p,q)] if nt < self.frame.stages else []
        elif op in ('once','past','historically','latest'):
            contexts = [(nt,p,q) for nt in range(t + (op == 'past'))]
        elif op in ('sometime','forever','infinitely'):
            contexts = [(nt,p,q) for nt in self.frame.future(t)]
        elif op == 'ultimately':
            contexts = [(nt,x,r) for nt in self.frame.future(t)
                        for r,qq in enumerate(self.frame.quorums) for x in qq]
        else: contexts = [ctx]
        return set().union(*(self.dependencies(a, at, variable) for a in node.args for at in contexts))

    def fixed(self, node, ctx, env, outer_fix):
        variable, body = node.value, node.args[0]
        if not free_fix(body, variable): return self.eval(body, ctx, env, outer_fix)
        # Exact closed form for the paper's nonmonotone leader test.
        if node.op == 'mu' and body.op == 'not' and body.args[0].op == 'diamond':
            inner = body.args[0].args[0]
            if inner.op == 'and':
                a, b = inner.args
                if a.op == 'var' and a.value == variable: a, b = b, a
                if b.op == 'var' and b.value == variable and not free_fix(a, variable):
                    t, p, q = ctx
                    others = [(x, self.eval(a,(t,x,q),env,outer_fix)) for x in self.frame.quorums[q]]
                    if p not in self.frame.quorums[q]:
                        return self.neg(self.either(v for _,v in others))
                    no_other_t = -self.circuit.or_(*(v[1] for x,v in others if x != p))
                    no_any_b = -self.circuit.or_(*(v[0] for _,v in others))
                    return (no_other_t, no_any_b)
        closure = {ctx}
        todo = [ctx]
        while todo:
            at = todo.pop()
            for dep in self.dependencies(body, at, variable) - closure:
                closure.add(dep)
                todo.append(dep)
        contexts = tuple(sorted(closure))
        key = (node, contexts, tuple(sorted(env.items())))
        can_cache = not any(free_fix(node, v) for v in outer_fix)
        if can_cache and key in self.mu_cache: return self.mu_cache[key][ctx]
        if positive(body, variable):
            current = {at: self.f if node.op == 'mu' else self.t for at in contexts}
            # Product lattice 3^K has height 2K+1. Iterating from bottom/top
            # exactly 2K times suffices for a monotone map.
            for _ in range(2 * len(contexts)):
                bindings = {**outer_fix, variable: current}
                new = {at: self.eval(body,at,env,bindings) for at in contexts}
                if new == current: break
                current = new
        else:
            if len(contexts) > self.max_mu_contexts:
                raise ResourceLimit(f'nonmonotone {node.op} needs {len(contexts)} recurrence contexts; '
                                    f'exact enumeration limit is {self.max_mu_contexts}')
            contributions = {at: [] for at in contexts}
            for values in product((self.f,self.b,self.t), repeat=len(contexts)):
                self.budget()
                mapping = dict(zip(contexts,values))
                binding = {**outer_fix,variable:mapping}
                images = {at: self.eval(body,at,env,binding) for at in contexts}
                good = self.circuit.and_(*(self.leq(images[at],mapping[at]) if node.op == 'mu'
                                          else self.leq(mapping[at],images[at]) for at in contexts))
                for at in contexts:
                    if node.op == 'mu':
                        contributions[at].append(tuple(self.circuit.or_(-good,x) for x in mapping[at]))
                    else:
                        contributions[at].append(tuple(self.circuit.and_(good,x) for x in mapping[at]))
            current = {at:(self.both(vals) if node.op == 'mu' else self.either(vals))
                       for at,vals in contributions.items()}
        if can_cache: self.mu_cache[key] = current
        return current[ctx]
