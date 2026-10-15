"""End-to-end obligations that prevent vacuity or corrupted evidence."""
import copy
import unittest
from muql import loads, check, replay


def theory(body):
    return loads('```muql\ntheory "test"\npoints alice\nvalues red blue\nstages 1\nquorums {alice}\npredicate P/0\n'+body+'\n```')


class CheckerTests(unittest.TestCase):
    def test_broken_is_valid_but_not_true(self):
        r=check(theory('axiom Broken: B(P)\nproperty Valid: P\nproperty True: T(P)'))
        self.assertEqual(r.status,'checked')
        self.assertEqual([p.status for p in r.properties],['holds','counterexample'])
        self.assertTrue(r.properties[1].countermodel.replayed)

    def test_inconsistent_axioms_do_not_prove_properties(self):
        r=check(theory('axiom Impossible: f\nproperty Anything: P'))
        self.assertEqual(r.status,'inconsistent')
        self.assertEqual(r.properties,[])
        self.assertIsNone(r.consistency_model)

    def test_countermodel_must_be_false_not_merely_not_true(self):
        r=check(theory('axiom NonFalse: TB(P)\nproperty ExcludedMiddle: P | !P'))
        self.assertEqual(r.properties[0].status,'holds')

    def test_saved_witness_replays_and_detects_tampering(self):
        th=theory('axiom Broken: B(P)\nproperty True: T(P)')
        data=check(th).properties[0].countermodel.to_dict()
        self.assertTrue(replay(th,data))
        forged=copy.deepcopy(data)
        forged['valuation'][0]['value']='t'
        with self.assertRaises(ValueError): replay(th,forged)
        for field in ('valuation','failure','scope'):
            broken=copy.deepcopy(data); del broken[field]
            with self.assertRaises(ValueError): replay(th,broken)

    def test_duplicate_missing_and_extra_witness_cells_rejected(self):
        th=theory('property True: T(P)')
        data=check(th).properties[0].countermodel.to_dict()
        for rows in ([],data['valuation']*2,data['valuation']+[{'predicate':'unknown','time':0,'point':'alice','args':[],'value':'f'}]):
            changed={**data,'valuation':rows}
            with self.assertRaises(ValueError): replay(th,changed)

    def test_node_limit_and_timeout_never_become_pass(self):
        th=theory('property True: P')
        r=check(th,max_nodes=1)
        self.assertEqual(r.status,'unknown')
        self.assertTrue(all(p.status=='unknown' for p in r.properties))
        r=check(th,timeout=1e-20)
        self.assertEqual(r.status,'unknown')

    def test_unused_predicates_are_exported_completely(self):
        th=theory('property False: f')
        witness=check(th).properties[0].countermodel
        self.assertEqual(len(witness.valuation),1)
        self.assertTrue(replay(th,witness))

    def test_bad_property_and_limits_are_rejected(self):
        th=theory('property True: t')
        with self.assertRaises(ValueError): check(th,properties=['missing'])
        with self.assertRaises(ValueError): check(th,timeout=-1)

    def test_empty_property_selection_checks_consistency(self):
        th=theory('axiom Good: t')
        r=check(th)
        self.assertEqual(r.status,'checked')
        self.assertEqual(r.properties,[])
        self.assertIsNotNone(r.consistency_model)


if __name__=='__main__': unittest.main()
