"""Independent exhaustive checks of semitopology enumeration.

The reference enumerates *all labeled families* and tests every pairwise
union. Its isomorphism oracle tries every point permutation. It uses neither
the production augmentation nor incidence-class/canonicalization helpers.
"""
from itertools import permutations
import unittest
from unittest.mock import patch

from muql.frame_search import FrameEnumerationLimit, iter_quorum_families


def brute_families(npoints, max_quorums):
    full = (1 << npoints) - 1
    for selected in range(1 << (full - 1)):
        if selected.bit_count() + 1 > max_quorums:
            continue
        family = {full}
        family.update(mask for mask in range(1, full) if selected & (1 << (mask - 1)))
        if all((left | right) in family for left in family for right in family):
            yield tuple(sorted(family))


def point_permutation_key(family, npoints):
    alternatives = []
    for permutation in permutations(range(npoints)):
        relabeled = []
        for quorum in family:
            members = [point for point in range(npoints) if quorum & (1 << point)]
            relabeled.append(sum(1 << permutation[point] for point in members))
        alternatives.append(tuple(sorted(relabeled)))
    return min(alternatives)


class QuorumFamilyEnumerationTests(unittest.TestCase):
    def assert_complete(self, npoints, max_quorums):
        expected = {point_permutation_key(family, npoints)
                    for family in brute_families(npoints, max_quorums)}
        output = list(iter_quorum_families(npoints, max_quorums))
        actual = [point_permutation_key(family, npoints) for family in output]
        self.assertEqual(set(actual), expected)
        self.assertEqual(len(actual), len(set(actual)), 'isomorphic duplicate output')
        for family in output:
            self.assertLessEqual(len(family), max_quorums)
            self.assertIn((1 << npoints) - 1, family)
            self.assertNotIn(0, family)
            self.assertTrue(all((left | right) in family for left in family for right in family))
        return output

    def test_every_small_point_and_quorum_bound_is_complete(self):
        for npoints in (1, 2, 3):
            for max_quorums in range(1, (1 << npoints) + 2):
                with self.subTest(npoints=npoints, max_quorums=max_quorums):
                    self.assert_complete(npoints, max_quorums)

    def test_all_four_point_families_against_full_labeled_powerset(self):
        output = self.assert_complete(4, 15)
        self.assertEqual(len(output), 165)

    def test_four_point_restricted_bounds_do_not_lose_augmentation_paths(self):
        for maximum in (2, 4, 6):
            with self.subTest(maximum=maximum):
                self.assert_complete(4, maximum)

    def test_output_is_deterministic_small_first_and_masks_are_sorted(self):
        first = list(iter_quorum_families(4, 8))
        self.assertEqual(first, list(iter_quorum_families(4, 8)))
        self.assertEqual(first[0], (15,))
        self.assertEqual(list(map(len, first)), sorted(map(len, first)))
        for family in first:
            self.assertEqual(family, tuple(sorted(family, key=lambda mask: (mask.bit_count(), mask))))

    def test_large_point_domain_with_two_opens_uses_incidence_symmetry(self):
        # Up to point permutation, a two-open family is determined exactly by
        # the size of its proper open. There are n-1 of those, plus {full}.
        # Only n-1 extensions are needed, not all 2**n labeled subsets.
        npoints = 20
        families = list(iter_quorum_families(npoints, 2, max_candidates=npoints - 1))
        self.assertEqual(len(families), npoints)
        self.assertEqual([family[0].bit_count() for family in families[1:]], list(range(1, npoints)))
        self.assertEqual(list(iter_quorum_families(1000, 1)), [((1 << 1000) - 1,)])

    def test_first_family_is_yielded_before_any_extensions_are_generated(self):
        with patch('muql.frame_search._orbit_subsets', side_effect=AssertionError('expanded too early')):
            iterator = iter_quorum_families(5, 8)
            self.assertEqual(next(iterator), (31,))
            with self.assertRaisesRegex(AssertionError, 'expanded too early'):
                next(iterator)

    def test_candidate_and_stored_family_limits_are_explicit(self):
        for limits, message in (({'max_candidates': 0}, 'candidate extensions'),
                                ({'max_families': 1}, 'stored isomorphism classes')):
            with self.subTest(limits=limits):
                iterator = iter_quorum_families(3, 4, **limits)
                self.assertEqual(next(iterator), (7,))
                with self.assertRaisesRegex(FrameEnumerationLimit, message):
                    list(iterator)

    def test_expired_deadline_and_expiry_during_search_are_explicit(self):
        with patch('muql.frame_search.monotonic', return_value=2):
            with self.assertRaisesRegex(FrameEnumerationLimit, 'timeout'):
                next(iter_quorum_families(3, 4, deadline=1))
        ticks = 0
        def clock():
            nonlocal ticks
            ticks += 1
            return 0 if ticks < 100 else 2
        with patch('muql.frame_search.monotonic', side_effect=clock):
            iterator = iter_quorum_families(4, 8, deadline=1)
            self.assertEqual(next(iterator), (15,))
            with self.assertRaisesRegex(FrameEnumerationLimit, 'timeout'):
                list(iterator)
        self.assertGreaterEqual(ticks, 100)

    def test_impossible_representation_request_fails_before_allocating_it(self):
        with self.assertRaisesRegex(FrameEnumerationLimit, 'point bitmask'):
            next(iter_quorum_families(10**12, 1))

    def test_invalid_limits_are_rejected(self):
        for arguments, keywords in (((0, 1), {}), ((True, 1), {}), ((2, 0), {}),
                                    ((2, 1.5), {}), ((2, 3), {'max_candidates': -1}),
                                    ((2, 3), {'max_families': 0}),
                                    ((2, 3), {'deadline': float('nan')})):
            with self.subTest(arguments=arguments, keywords=keywords), self.assertRaises(ValueError):
                next(iter_quorum_families(*arguments, **keywords))


if __name__ == '__main__':
    unittest.main()
