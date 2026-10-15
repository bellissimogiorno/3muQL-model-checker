"""Finite semitopologies and explicit temporal frames."""
from dataclasses import dataclass
from itertools import combinations, product
from functools import cached_property
from time import monotonic


class FrameLimit(RuntimeError):
    """Constructing or inspecting an exact frame exceeded a resource budget."""


@dataclass(frozen=True)
class Frame:
    points: tuple[str, ...]
    quorums: tuple[frozenset[int], ...]
    stages: int
    time: str = 'finite'

    def __post_init__(self):
        # The low-level constructor accepts an explicit family; from_theory
        # constructs its semitopological union closure. Both require a valid
        # finite relational frame, including when used directly from Python.
        # Take immutable snapshots before caching contexts or intersection
        # results: frozen dataclasses alone do not freeze caller-owned lists.
        object.__setattr__(self, 'points', tuple(self.points))
        object.__setattr__(self, 'quorums', tuple(frozenset(q) for q in self.quorums))
        if not self.points or len(set(self.points)) != len(self.points):
            raise ValueError('frame points must be nonempty and distinct')
        if type(self.stages) is not int or self.stages < 1:
            raise ValueError('frame stages must be a positive integer')
        if self.time not in {'finite', 'stutter'}:
            raise ValueError('frame time must be finite or stutter')
        if not self.quorums or any(not q for q in self.quorums):
            raise ValueError('frame quorums must be nonempty')
        if any(type(p) is not int or p < 0 or p >= len(self.points)
               for q in self.quorums for p in q):
            raise ValueError('frame quorum contains an invalid point index')

    @classmethod
    def from_theory(cls, theory, max_quorums=4096, *, deadline=None):
        if type(max_quorums) is not int or max_quorums < 1:
            raise ValueError('max_quorums must be a positive integer')
        def checkpoint():
            if deadline is not None and monotonic() > deadline:
                raise FrameLimit('frame construction timeout')
        checkpoint()
        if not theory.points or not theory.values or theory.stages < 1:
            raise ValueError('points, values and stages must be nonempty')
        if len(theory.points) != len(set(theory.points)):
            raise ValueError('duplicate points')
        index = {p: i for i, p in enumerate(theory.points)}
        opens = {frozenset(), frozenset(range(len(theory.points)))}
        for q in theory.quorums:
            if any(p not in index for p in q):
                raise ValueError('quorum contains an undeclared point')
            opens.add(frozenset(index[p] for p in q))
        if len(opens) - 1 > max_quorums:
            raise FrameLimit(f'input exceeds {max_quorums} quorums')
        # Every generated open is a union of original generators. Adjoining
        # one generator at a time reaches every such union; combining all
        # generated opens with one another only repeats that work. Empty and
        # whole-space generators cannot produce a new open.
        generators = tuple(opens - {frozenset(), frozenset(range(len(theory.points)))})
        pending = list(generators)
        operations = 0
        while pending:
            q = pending.pop()
            for r in generators:
                operations += 1
                if operations % 256 == 0:
                    checkpoint()
                union = q | r
                if union not in opens:
                    opens.add(union)
                    pending.append(union)
                    if len(opens) - 1 > max_quorums:
                        raise FrameLimit(f'union closure exceeds {max_quorums} quorums')
        checkpoint()
        qs = tuple(sorted(opens - {frozenset()}, key=lambda x: (len(x), tuple(sorted(x)))))
        return cls(tuple(theory.points), qs, theory.stages, getattr(theory, 'time', 'finite'))

    @cached_property
    def contexts(self):
        return tuple(product(range(self.stages), range(len(self.points)), range(len(self.quorums))))

    def future(self, stage):
        if self.time == 'stutter' and stage == self.stages - 1:
            return (stage,)
        return tuple(range(stage + 1, self.stages))

    @cached_property
    def _twined_cache(self):
        return {}

    def twined(self, n, *, checkpoint=None):
        if type(n) is not int or n < 1:
            raise ValueError('twined requires a positive integer')
        if checkpoint is not None:
            checkpoint()
        if n in self._twined_cache:
            return self._twined_cache[n]
        requested = n
        # n > |Q| adds no distinct intersections (repeated quorums are allowed).
        n = min(n, len(self.quorums))
        # A shared point witnesses every intersection without an exponential
        # enumeration. At n=|Q| there is just the one intersection to inspect.
        common = set.intersection(*(set(q) for q in self.quorums))
        if n == 1 or common:
            result = True
        elif n == len(self.quorums):
            result = False
        else:
            result = True
            for index, qs in enumerate(combinations(self.quorums, n)):
                if checkpoint is not None and index % 128 == 0:
                    checkpoint()
                if not set.intersection(*(set(q) for q in qs)):
                    result = False
                    break
        self._twined_cache[requested] = result
        return result

    def describe(self):
        return {'points': list(self.points), 'values_note': 'values specified by theory',
                'quorums': [[self.points[p] for p in sorted(q)] for q in self.quorums],
                'stages': self.stages, 'time': self.time}
