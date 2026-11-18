from inventory.accept import accept_inventory
from publication.commit import initialize_source, publish
from publication.receipts import fetch, get_receipt
from revisions.import_delta import accept_delta
from revisions.register import register_revision
from storage import EvidenceError, NotFoundError
from tests import LakesideTestCase, X, Y, seed_case, shipment_counts


class PublicationConflictTests(LakesideTestCase):
    def test_conflicting_paths(self):
        db = self.source()
        deltas = seed_case(db, direct=-1)
        with self.assertRaises(EvidenceError, msg='LAKE_HANDOFF_MISMATCH conflicting routes must reject'):
            publish(db, 'P', ['A', 'B', 'C'], ['inv-a'], deltas)
        self.assertEqual(shipment_counts(db), (0, 0), 'LAKE_HANDOFF_MISMATCH unexpected shipment or receipt')
        with self.assertRaises(NotFoundError):
            fetch(db, 1)
        with self.assertRaises(NotFoundError):
            get_receipt(db, 1)

    def test_second_anchor_conflict(self):
        db = self.source()
        deltas = seed_case(db)
        accept_inventory(db, 'P', 'C', 'bad-c', [(*X, 1), (*Y, 1)])
        with self.assertRaises(EvidenceError):
            publish(db, 'P', ['A', 'B', 'C'], ['inv-a', 'bad-c'], deltas)
        self.assertEqual(shipment_counts(db), (0, 0))

    def test_unanchored(self):
        db = self.source()
        deltas = seed_case(db)
        for revision in ('D', 'E'):
            register_revision(db, 'P', revision)
        accept_delta(db, 'P', 'unanchored', 'D', 'E', [])
        with self.assertRaises(EvidenceError):
            publish(db, 'P', ['A', 'B', 'C', 'D', 'E'], ['inv-a'], (*deltas, 'unanchored'))
        self.assertEqual(shipment_counts(db), (0, 0))

    def test_negative_intermediate(self):
        db = self.source()
        initialize_source(db, ['P'], [('P', 'A'), ('P', 'B'), ('P', 'C')])
        accept_inventory(db, 'P', 'A', 'inv-a', [(*X, 1)])
        accept_delta(db, 'P', 'd-ba', 'B', 'A', [(*X, 2)])
        accept_delta(db, 'P', 'd-bc', 'B', 'C', [(*X, 1), (*Y, 1)])
        with self.assertRaises(EvidenceError):
            publish(db, 'P', ['A', 'B', 'C'], ['inv-a'], ['d-ba', 'd-bc'])
        self.assertEqual(shipment_counts(db), (0, 0))
