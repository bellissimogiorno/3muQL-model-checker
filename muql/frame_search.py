"""Exact, bounded enumeration of finite semitopologies up to isomorphism.

Empty opens are implicit. A family is a tuple of nonzero point bitmasks,
contains the whole space, and is closed under unions. Families are yielded in
nondecreasing quorum count, with deterministic representatives and ordering.

The search starts with the indiscrete family and adds one open at a time.
Point permutations preserving every existing open let us consider just one
subset for each selection count from each incidence class. An exact
isomorphism key removes the remaining duplicate children. Every extension of
an isomorphic parent is still represented, so pruning is complete.
"""
from heapq import heappop, heappush
from itertools import permutations
from math import isnan, lgamma
from time import monotonic

from .frame import FrameLimit


class FrameEnumerationLimit(FrameLimit):
    """A complete structural search exceeded an explicit resource budget."""


# Bound the representation itself before attempting an enormous integer shift.
# This is a reported resource limit, never a silently truncated point domain.
_MAX_POINT_BITS = 1_000_000


class _Budget:
    def __init__(self, deadline, max_candidates, max_families):
        self.deadline = deadline
        self.max_candidates = max_candidates
        self.max_families = max_families
        self.candidates = 0

    def check(self):
        if self.deadline is not None and monotonic() >= self.deadline:
            raise FrameEnumerationLimit('quorum-family enumeration timeout')

    def candidate(self):
        self.check()
        self.candidates += 1
        if self.candidates > self.max_candidates:
            raise FrameEnumerationLimit(
                f'quorum-family enumeration exceeds {self.max_candidates} candidate extensions')

    def family(self, count):
        self.check()
        if count > self.max_families:
            raise FrameEnumerationLimit(
                f'quorum-family enumeration exceeds {self.max_families} stored isomorphism classes')


def _ordered(family):
    return tuple(sorted(family, key=lambda mask: (mask.bit_count(), mask)))


def _point_classes(family, full, budget):
    """Point classes with identical membership in every current open."""
    classes = [full]
    for quorum in family:
        budget.check()
        if quorum == full:
            continue
        refined = []
        for members in classes:
            budget.check()
            inside = members & quorum
            outside = members ^ inside
            if inside:
                refined.append(inside)
            if outside:
                refined.append(outside)
        classes = refined
    return tuple(sorted(classes, key=lambda mask: mask & -mask))


def _orbit_subsets(classes, budget):
    """Lazy mixed-radix traversal; no eager powerset or recursive stack."""
    selected = [0] * len(classes)
    remaining = list(classes)
    current = 0
    while True:
        budget.check()
        yield current
        for index in range(len(classes) - 1, -1, -1):
            budget.check()
            if remaining[index]:
                bit = remaining[index] & -remaining[index]
                remaining[index] ^= bit
                selected[index] |= bit
                current |= bit
                break
            current ^= selected[index]
            selected[index] = 0
            remaining[index] = classes[index]
        else:
            return


def _row_orders(groups, budget):
    """Lazy product of permutations, without itertools.product pooling them."""
    # The number of groups is the number of different proper-quorum sizes.
    # Iterative backtracking avoids recursion-depth assumptions for large n.
    if not groups:
        yield ()
        return
    stack = [iter(permutations(groups[0]))]
    chosen = []
    while stack:
        budget.check()
        try:
            order = next(stack[-1])
        except StopIteration:
            stack.pop()
            if chosen:
                chosen.pop()
            continue
        if len(stack) == len(groups):
            yield tuple(index for part in (*chosen, order) for index in part)
        else:
            chosen.append(order)
            stack.append(iter(permutations(groups[len(stack)])))


def _isomorphism_key(family, npoints, full, classes, budget):
    """Exact canonical key, using the cheaper side of the incidence matrix.

Point permutations canonically relabel the opens. Alternatively, permutations
of equally sized opens canonically relabel the incidence columns. In the
second method the multiset of columns determines a point bijection exactly.
The method choice depends only on isomorphism-invariant counts.
"""
    proper = tuple(quorum for quorum in family if quorum != full)
    sizes = tuple(quorum.bit_count() for quorum in proper)
    by_size = {}
    for index, size in enumerate(sizes):
        by_size.setdefault(size, []).append(index)
    groups = tuple(tuple(by_size[size]) for size in sorted(by_size))
    row_cost = sum(lgamma(len(group) + 1) for group in groups)
    if lgamma(npoints + 1) < row_cost:
        best = None
        for permutation in permutations(range(npoints)):
            budget.check()
            transformed = []
            for quorum in family:
                budget.check()
                mapped, bits = 0, quorum
                while bits:
                    bit = bits & -bits
                    mapped |= 1 << permutation[bit.bit_length() - 1]
                    bits ^= bit
                transformed.append(mapped)
            key = _ordered(transformed)
            if best is None or key < best:
                best = key
        return ('points', best)

    columns = []
    for members in classes:
        budget.check()
        representative = members & -members
        column = 0
        for index, quorum in enumerate(proper):
            if quorum & representative:
                column |= 1 << index
        columns.append((column, members.bit_count()))
    best = None
    for order in _row_orders(groups, budget):
        budget.check()
        transformed = []
        for column, count in columns:
            budget.check()
            mapped = 0
            for new_index, old_index in enumerate(order):
                if column & (1 << old_index):
                    mapped |= 1 << new_index
            transformed.append((mapped, count))
        key = tuple(sorted(transformed))
        if best is None or key < best:
            best = key
    return ('rows', sizes, best)


def iter_quorum_families(npoints, max_quorums, *, deadline=None,
                        max_candidates=1_000_000, max_families=100_000):
    """Yield every eligible semitopology once up to point permutation.

    ``npoints`` and ``max_quorums`` are positive integers. ``deadline`` is an
    absolute ``time.monotonic()`` deadline, or None for no time limit. The two
    explicit count budgets limit attempted extensions and stored isomorphism
    classes. Exhaustion raises :class:`FrameEnumerationLimit`; it never causes
    the generator to claim successful completion of a smaller search.

    Each tuple contains nonzero masks sorted by ``(bit_count, mask)``. The
    whole-space-only family is yielded first, before exploring any extensions.
    Empty opens are excluded from ``max_quorums``. If that bound exceeds the
    number of possible nonempty subsets, the mathematical maximum is used.

    Validation occurs when iteration starts, as for ordinary Python generators.
    The point bitmask representation has an explicit one-million-bit ceiling.
    """
    for name, value in (('npoints', npoints), ('max_quorums', max_quorums),
                        ('max_families', max_families)):
        if type(value) is not int or value < 1:
            raise ValueError(f'{name} must be a positive integer')
    if type(max_candidates) is not int or max_candidates < 0:
        raise ValueError('max_candidates must be a nonnegative integer')
    if deadline is not None and isnan(deadline):
        raise ValueError('deadline must not be NaN')
    budget = _Budget(deadline, max_candidates, max_families)
    budget.check()
    if npoints > _MAX_POINT_BITS:
        raise FrameEnumerationLimit(
            f'quorum-family point bitmask exceeds {_MAX_POINT_BITS} bits')
    full = (1 << npoints) - 1
    max_quorums = min(max_quorums, full)
    first = (full,)
    first_classes = (full,)
    seen = {_isomorphism_key(first, npoints, full, first_classes, budget)}
    pending = [(1, first)]
    while pending:
        budget.check()
        _, family = heappop(pending)
        yield family
        # A caller finding a witness can stop without paying for expansion.
        budget.check()
        if len(family) == max_quorums:
            continue
        members = set(family)
        classes = _point_classes(family, full, budget)
        for added in _orbit_subsets(classes, budget):
            if not added or added in members:
                continue
            budget.candidate()
            closure = members | {added}
            # F is union-closed: adding A needs only A and every A union Q.
            # Unions of those new sets introduce nothing further.
            for quorum in family:
                budget.check()
                closure.add(added | quorum)
                if len(closure) > max_quorums:
                    break
            if len(closure) > max_quorums:
                continue
            child = _ordered(closure)
            child_classes = _point_classes(child, full, budget)
            key = _isomorphism_key(child, npoints, full, child_classes, budget)
            if key in seen:
                continue
            budget.family(len(seen) + 1)
            seen.add(key)
            heappush(pending, (len(child), child))
