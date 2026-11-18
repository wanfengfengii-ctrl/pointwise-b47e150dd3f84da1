from audit.export import fetch_audit
from audit.reconcile import audit
from audit.store import initialize_offline
from inventory.accept import accept_inventory
from offline.accept import import_package
from offline.recover import recover
from publication.commit import initialize_source, publish
from publication.receipts import fetch
from revisions.import_delta import accept_delta
from revisions.register import register_revision
from storage import InputError, NotFoundError, open_database
from tests import LakesideTestCase, X, foreign_blob, seed_case


class AuditTests(LakesideTestCase):
    def test_fixed_audit(self):
        with open_database(self.source_path) as source:
            deltas = seed_case(source)
            receipt = publish(source, 'P', ['A', 'B', 'C'], ['inv-a'], deltas)
            original = fetch(source, receipt.package_id)
        with open_database(self.offline_path) as night:
            initialize_offline(night)
            package_id = import_package(night, original)
            old = audit(night, package_id, 'A', {'G': 1})
            self.assertEqual(old, {'audit_id': old['audit_id'], 'package_id': package_id,
                                   'revision': 'A', 'actual': {'G': 2}, 'differences': {'G': 1}})
        with open_database(self.source_path) as source:
            register_revision(source, 'P', 'D')
            accept_delta(source, 'P', 'd-ad', 'A', 'D', [(*X, 3)])
            corrected = publish(source, 'P', ['A', 'D'], ['inv-a'], ['d-ad'])
            replacement = fetch(source, corrected.package_id)
            self.assertEqual(fetch(source, receipt.package_id), original)
        with open_database(self.offline_path) as night:
            initialize_offline(night)
            new_id = import_package(night, replacement)
            self.assertEqual(audit(night, new_id, 'D')['actual'], {'G': 5})
            self.assertEqual(fetch_audit(night, old['audit_id']), old)
            self.assertEqual(recover(night, package_id, 'A'), [(*X, 2)])

    def test_ledger_union_and_omission(self):
        night = self.offline()
        initialize_offline(night)
        package_id = import_package(night, foreign_blob())
        result = audit(night, package_id, 'A', {'Z': 4, 'G': 2, 'A': 1})
        self.assertEqual(result['actual'], {'G': 2})
        self.assertEqual(list(result['differences'].items()), [('A', -1), ('G', 0), ('Z', -4)])
        self.assertEqual(sum(result['actual'].values()), sum(row[3] for row in recover(night, package_id, 'A')))
        self.assertEqual(audit(night, package_id, 'A', {})['differences'], {'G': 2})
        omitted = audit(night, package_id, 'A')
        self.assertNotIn('differences', omitted)
        self.assertNotIn('differences', fetch_audit(night, omitted['audit_id']))

    def test_invalid_input(self):
        night = self.offline()
        initialize_offline(night)
        package_id = import_package(night, foreign_blob())
        original = audit(night, package_id, 'A')
        for ledger in ({'G': -1}, {'G': True}, {'G': 1.5}, {'G': None}, {'': 1}, [('G', 1)]):
            with self.subTest(ledger=ledger), self.assertRaises(InputError):
                audit(night, package_id, 'A', ledger)
        with self.assertRaises(NotFoundError):
            audit(night, package_id, 'unknown')
        with self.assertRaises(NotFoundError):
            audit(night, 999, 'A')
        with self.assertRaises(NotFoundError):
            fetch_audit(night, 999)
        self.assertEqual(night.execute('SELECT count(*) FROM audits').fetchone(), (1,))
        self.assertEqual(fetch_audit(night, original['audit_id']), original)

    def test_exact_large_integer_round_trip(self):
        huge = 10**4400 + 37
        with open_database(self.source_path) as source:
            initialize_source(source, ['P'], [('P', 'A'), ('P', 'B')])
            accept_inventory(source, 'P', 'A', 'huge', [(*X, huge)])
            accept_delta(source, 'P', 'advance', 'A', 'B', [(*X, huge)])
            receipt = publish(source, 'P', ['A', 'B'], ['huge'], ['advance'])
            blob = fetch(source, receipt.package_id)
        with open_database(self.offline_path) as night:
            initialize_offline(night)
            package_id = import_package(night, blob)
            self.assertEqual(recover(night, package_id, 'B')[0][3], 2 * huge)
            result = audit(night, package_id, 'B', {'G': 2 * huge + 5})
            self.assertEqual(result['differences']['G'], -5)
        with open_database(self.offline_path) as night:
            self.assertEqual(fetch_audit(night, result['audit_id'])['actual']['G'], 2 * huge)
