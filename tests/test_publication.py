from audit.store import initialize_offline
from inventory.accept import accept_inventory
from offline.accept import import_package
from offline.recover import recover
from publication.commit import initialize_source, publish
from publication.package import decode_package
from publication.receipts import fetch, get_receipt
from revisions.import_delta import accept_delta
from revisions.register import register_revision
from storage import EvidenceError, NotFoundError, open_database
from tests import LakesideTestCase, X, Y, seed_case, shipment_counts


class PublicationTests(LakesideTestCase):
    def test_valid_publication(self):
        with open_database(self.source_path) as source:
            deltas = seed_case(source, direct=-2)
            receipt = publish(source, 'P', ('C', 'A', 'B'), ['inv-a'], deltas)
            blob = fetch(source, receipt.package_id)
            self.assertEqual(get_receipt(source, receipt.package_id), receipt)
            self.assertEqual((receipt.partition, receipt.revisions, receipt.inventory_ids, receipt.delta_ids),
                             ('P', ('A', 'B', 'C'), ('inv-a',), ('d-ac', 'd-ba', 'd-bc')))
            self.assertEqual(shipment_counts(source), (1, 1))
        evidence = decode_package(blob)
        self.assertEqual([(d.delta_id, d.source, d.target, d.changes) for d in evidence.deltas],
                         [('d-ac', 'A', 'C', {X: -2, Y: 1}), ('d-ba', 'B', 'A', {X: 1}),
                          ('d-bc', 'B', 'C', {X: -1, Y: 1})])
        self.assertEqual([(i.inventory_id, i.revision, i.rows) for i in evidence.inventories],
                         [('inv-a', 'A', {X: 2})])
        night = self.offline()
        initialize_offline(night)
        package_id = import_package(night, blob)
        self.assertEqual([recover(night, package_id, v) for v in ('A', 'B', 'C')],
                         [[(*X, 2)], [(*X, 1)], [(*Y, 1)]])

    def test_exact_scope(self):
        db = self.source()
        deltas = seed_case(db)
        accept_delta(db, 'P', 'unused-conflict', 'A', 'C', [(*X, -1), (*Y, 1)])
        accept_inventory(db, 'P', 'A', 'unused-anchor', [(*X, 5)])
        register_revision(db, 'P', 'unused-revision')
        receipt = publish(db, 'P', ['A', 'B', 'C'], ['inv-a'], deltas)
        selected = decode_package(fetch(db, receipt.package_id))
        self.assertEqual(selected.revisions, ('A', 'B', 'C'))
        self.assertEqual([i.inventory_id for i in selected.inventories], ['inv-a'])
        self.assertEqual([d.delta_id for d in selected.deltas], ['d-ba', 'd-bc'])
        invalid = [(['A', 'B'], ['inv-a'], deltas), (['B', 'C'], ['inv-a'], ['d-bc']),
                   (['A'], ['missing'], []), (['A'], ['inv-a'], ['missing']),
                   (['A', 'A'], ['inv-a'], []), (['A', 'missing'], ['inv-a'], []),
                   ([], [], [])]
        for revisions, inventories, selected_deltas in invalid:
            with self.subTest(revisions=revisions, inventories=inventories, deltas=selected_deltas):
                with self.assertRaises(EvidenceError):
                    publish(db, 'P', revisions, inventories, selected_deltas)
                self.assertEqual(shipment_counts(db), (1, 1))

    def test_named_parallel_evidence(self):
        db = self.source()
        deltas = seed_case(db, direct=-2)
        accept_delta(db, 'P', 'd-parallel', 'B', 'C', [(*Y, 1), (*X, -1)])
        receipt = publish(db, 'P', ['A', 'B', 'C'], ['inv-a'], (*deltas, 'd-parallel'))
        self.assertEqual(receipt.delta_ids, ('d-ac', 'd-ba', 'd-bc', 'd-parallel'))
        evidence = decode_package(fetch(db, receipt.package_id))
        parallel = [(d.delta_id, d.source, d.target, d.changes) for d in evidence.deltas if d.source == 'B' and d.target == 'C']
        self.assertEqual(parallel, [('d-bc', 'B', 'C', {X: -1, Y: 1}),
                                    ('d-parallel', 'B', 'C', {X: -1, Y: 1})])
        self.assertEqual(len(evidence.deltas), 4)

    def test_second_anchor(self):
        db = self.source()
        deltas = seed_case(db, direct=-2)
        accept_inventory(db, 'P', 'C', 'inv-c', [(*Y, 1)])
        receipt = publish(db, 'P', ['A', 'B', 'C'], ['inv-a', 'inv-c'], deltas)
        evidence = decode_package(fetch(db, receipt.package_id))
        self.assertEqual([(i.inventory_id, i.revision, i.rows) for i in evidence.inventories],
                         [('inv-a', 'A', {X: 2}), ('inv-c', 'C', {Y: 1})])

    def test_separate_anchored_components(self):
        db = self.source()
        deltas = seed_case(db)
        register_revision(db, 'P', 'D')
        accept_inventory(db, 'P', 'D', 'empty-d', [])
        receipt = publish(db, 'P', ['A', 'B', 'C', 'D'], ['empty-d', 'inv-a'], deltas)
        night = self.offline()
        initialize_offline(night)
        package_id = import_package(night, fetch(db, receipt.package_id))
        self.assertEqual(recover(night, package_id, 'D'), [])
        self.assertEqual(recover(night, package_id, 'C'), [(*Y, 1)])

    def test_fixed_fetch(self):
        with open_database(self.source_path) as db:
            deltas = seed_case(db)
            original = publish(db, 'P', ['A', 'B', 'C'], ['inv-a'], deltas)
            blob = fetch(db, original.package_id)
            register_revision(db, 'P', 'D')
            accept_delta(db, 'P', 'd-cd', 'C', 'D', [(*Y, 2)])
            corrected = publish(db, 'P', ['A', 'B', 'C', 'D'], ['inv-a'], (*deltas, 'd-cd'))
        with open_database(self.source_path) as db:
            initialize_source(db, ['P'], [('P', 'A')])
            self.assertNotEqual(original.package_id, corrected.package_id)
            self.assertEqual(fetch(db, original.package_id), blob)
            self.assertEqual(get_receipt(db, original.package_id), original)
            self.assertEqual(decode_package(fetch(db, corrected.package_id)).revisions, ('A', 'B', 'C', 'D'))
            with self.assertRaises(NotFoundError):
                fetch(db, 999)
