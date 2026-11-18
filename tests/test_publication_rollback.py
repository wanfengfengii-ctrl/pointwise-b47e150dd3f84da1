from publication.commit import publish
from publication.receipts import fetch, get_receipt
from storage import NotFoundError, StorageError, open_database
from tests import LakesideTestCase, seed_case, shipment_counts


class PublicationRollbackTests(LakesideTestCase):
    def test_rollback_after_package_insert(self):
        with open_database(self.source_path) as db:
            deltas = seed_case(db)
            first = publish(db, 'P', ['A'], ['inv-a'], [])
            old_blob = fetch(db, first.package_id)
            db.execute('''
                CREATE TRIGGER stop_receipt BEFORE INSERT ON receipts
                WHEN EXISTS (SELECT 1 FROM shipments WHERE package_id = NEW.package_id)
                BEGIN SELECT RAISE(ABORT, 'receipt interrupted after package insert'); END
            ''')
            with self.assertRaisesRegex(StorageError, 'receipt interrupted after package insert'):
                publish(db, 'P', ['A', 'B', 'C'], ['inv-a'], deltas)
            self.assertFalse(db.in_transaction)
            self.assertEqual(shipment_counts(db), (1, 1))
        with open_database(self.source_path) as db:
            self.assertEqual(shipment_counts(db), (1, 1))
            self.assertEqual(fetch(db, first.package_id), old_blob)
            self.assertEqual(get_receipt(db, first.package_id), first)
            with self.assertRaises(NotFoundError):
                fetch(db, first.package_id + 1)
            with self.assertRaises(NotFoundError):
                get_receipt(db, first.package_id + 1)
            db.execute('DROP TRIGGER stop_receipt')
            second = publish(db, 'P', ['A', 'B', 'C'], ['inv-a'], deltas)
            self.assertNotEqual(fetch(db, second.package_id), old_blob)
            self.assertEqual(shipment_counts(db), (2, 2))
