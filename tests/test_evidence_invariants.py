import json

from audit.store import initialize_offline
from inventory.accept import accept_inventory
from offline.accept import import_package
from offline.catalog import get_received_package
from offline.recover import recover, recover_revision_rows
from publication.commit import publish
from publication.package import decode_package
from publication.receipts import fetch
from storage import EvidenceError, PackageError
from tests import LakesideTestCase, X, Y, foreign_blob, seed_case, shipment_counts, wire_blob


class EvidenceInvariantTests(LakesideTestCase):
    def test_well_formed_but_contradictory_foreign_piece_rejected(self):
        # A V1 piece with valid fields and references but whose direct route
        # contradicts the two-step route must be refused at the offline door,
        # leaving no catalog row and no success receipt.
        document = json.loads(foreign_blob())
        document['deltas'].append(
            {'id': 'foreign-ac', 'source': 'A', 'target': 'C',
             'rows': [['ridge', '06:00', 'G', -1], ['ridge', '07:00', 'H', 1]]})
        night = self.offline()
        initialize_offline(night)
        with self.assertRaises(EvidenceError, msg='LAKE_HANDOFF_MISMATCH contradictory foreign piece'):
            import_package(night, wire_blob(document))
        self.assertEqual(night.execute('SELECT count(*) FROM received_packages').fetchone(), (0,))
        # The legal piece from the same workstation still imports and reads.
        legal_id = import_package(night, foreign_blob())
        self.assertEqual([recover(night, legal_id, rev) for rev in ('A', 'B', 'C')],
                         [[(*X, 2)], [(*X, 1)], [(*Y, 1)]])

    def test_foreign_piece_with_unanchored_revision_rejected(self):
        document = json.loads(foreign_blob())
        document['revisions'] = ['A', 'B', 'C', 'D']
        document['deltas'].append({'id': 'foreign-dd', 'source': 'D', 'target': 'D', 'rows': []})
        night = self.offline()
        initialize_offline(night)
        with self.assertRaises(EvidenceError):
            import_package(night, wire_blob(document))
        self.assertEqual(night.execute('SELECT count(*) FROM received_packages').fetchone(), (0,))

    def test_foreign_piece_with_negative_account_rejected(self):
        document = json.loads(foreign_blob())
        document['inventories'][0]['rows'][0][3] = 0
        # B would then hold -1 X after undoing B->A.
        night = self.offline()
        initialize_offline(night)
        with self.assertRaises((EvidenceError, PackageError)):
            import_package(night, wire_blob(document))
        self.assertEqual(night.execute('SELECT count(*) FROM received_packages').fetchone(), (0,))

    def test_format_failure_still_package_error(self):
        night = self.offline()
        initialize_offline(night)
        with self.assertRaises(PackageError):
            import_package(night, b'{')
        self.assertEqual(night.execute('SELECT count(*) FROM received_packages').fetchone(), (0,))

    def test_shuffled_wire_order_recovers_same_ordered_rows(self):
        document = json.loads(foreign_blob())
        document['revisions'] = list(reversed(document['revisions']))
        document['deltas'].reverse()
        document['inventories'][0]['rows'].reverse()
        shuffled = wire_blob(document)
        night = self.offline()
        initialize_offline(night)
        package_id = import_package(night, shuffled)
        self.assertEqual(get_received_package(night, package_id), shuffled)
        self.assertEqual([recover(night, package_id, rev) for rev in ('C', 'B', 'A')],
                         [[(*Y, 1)], [(*X, 1)], [(*X, 2)]])
        self.assertEqual(recover_revision_rows(decode_package(shuffled), 'B'), [(*X, 1)])

    def test_reversed_equivalent_delta_is_the_same_account(self):
        document = json.loads(foreign_blob())
        edge = next(delta for delta in document['deltas'] if delta['id'] == 'foreign-ba')
        edge['source'], edge['target'] = edge['target'], edge['source']
        for row in edge['rows']:
            row[3] = -row[3]
        night = self.offline()
        initialize_offline(night)
        package_id = import_package(night, wire_blob(document))
        self.assertEqual([recover(night, package_id, rev) for rev in ('A', 'B', 'C')],
                         [[(*X, 2)], [(*X, 1)], [(*Y, 1)]])

    def test_identical_second_anchor_remains_legal(self):
        db = self.source()
        deltas = seed_case(db)
        accept_inventory(db, 'P', 'A', 'inv-a-copy', [(*X, 2)])
        receipt = publish(db, 'P', ['A', 'B', 'C'], ['inv-a', 'inv-a-copy'], deltas)
        night = self.offline()
        initialize_offline(night)
        package_id = import_package(night, fetch(db, receipt.package_id))
        self.assertEqual(recover(night, package_id, 'B'), [(*X, 1)])
        self.assertEqual(shipment_counts(db), (1, 1))
