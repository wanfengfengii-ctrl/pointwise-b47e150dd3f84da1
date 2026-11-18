import json

from audit.store import initialize_offline
from offline.accept import import_package
from offline.catalog import get_received_package
from offline.recover import recover, recover_revision_rows
from publication.commit import publish
from publication.package import decode_package
from publication.receipts import fetch
from storage import EvidenceError, NotFoundError, open_database
from tests import LakesideTestCase, X, Y, foreign_blob, seed_case, wire_blob


class OfflineTests(LakesideTestCase):
    def test_reverse_recovery(self):
        with open_database(self.source_path) as source:
            deltas = seed_case(source)
            receipt = publish(source, 'P', ['A', 'B', 'C'], ['inv-a'], deltas)
            local_blob = fetch(source, receipt.package_id)
        with open_database(self.offline_path) as night:
            initialize_offline(night)
            local_id = import_package(night, local_blob)
            foreign_id = import_package(night, foreign_blob())
        with open_database(self.offline_path) as night:
            for package_id in (local_id, foreign_id):
                with self.subTest(package_id=package_id):
                    try:
                        actual = [recover(night, package_id, rev) for rev in ('A', 'B', 'C')]
                    except EvidenceError as exc:
                        self.fail(f'LAKE_HANDOFF_MISMATCH legal offline handoff: {exc}')
                    self.assertEqual(actual, [[(*X, 2)], [(*X, 1)], [(*Y, 1)]],
                                     'LAKE_HANDOFF_MISMATCH incorrect offline row multiplicities')
        self.assertEqual(recover_revision_rows(decode_package(foreign_blob()), 'C'), [(*Y, 1)])

    def test_equivalent_edges(self):
        fixture = json.loads(foreign_blob())
        fixture['deltas'].reverse()
        edge = next(delta for delta in fixture['deltas'] if delta['id'] == 'foreign-bc')
        edge['source'], edge['target'] = edge['target'], edge['source']
        for row in edge['rows']:
            row[3] = -row[3]
        night = self.offline()
        initialize_offline(night)
        for blob in (foreign_blob(), wire_blob(fixture)):
            package_id = import_package(night, blob)
            self.assertEqual([recover(night, package_id, rev) for rev in ('A', 'B', 'C')],
                             [[(*X, 2)], [(*X, 1)], [(*Y, 1)]])

    def test_bundle_isolation(self):
        original = foreign_blob()
        different = json.loads(original)
        different['inventories'][0]['rows'][0][3] = 5
        other_blob = wire_blob(different)
        with open_database(self.offline_path) as night:
            initialize_offline(night)
            first = import_package(night, original)
            second = import_package(night, other_blob)
            self.assertNotEqual(first, second)
            self.assertEqual(import_package(night, original), first)
        with open_database(self.offline_path) as night:
            initialize_offline(night)
            self.assertEqual(get_received_package(night, first), original)
            self.assertEqual(get_received_package(night, second), other_blob)
            for package_id, count in [(first, 2), (second, 5), (first, 2), (second, 5)]:
                self.assertEqual(recover(night, package_id, 'A'), [(*X, count)])

    def test_unknown_lookup(self):
        night = self.offline()
        initialize_offline(night)
        package_id = import_package(night, foreign_blob())
        for number, revision in [(999, 'A'), (package_id, 'D'), (2**64, 'A')]:
            with self.subTest(number=number, revision=revision), self.assertRaises(NotFoundError):
                recover(night, number, revision)
        self.assertEqual(night.execute('SELECT count(*) FROM received_packages').fetchone(), (1,))

    def test_full_row_order(self):
        fixture = json.loads(foreign_blob())
        fixture['revisions'] = ['A']
        fixture['deltas'] = []
        fixture['inventories'][0]['rows'] = [['z', '06:00', 'G', 1], ['a', '07:00', 'G', 1],
                                               ['a', '06:00', 'H', 2], ['a', '06:00', 'G', 2],
                                               ['a', '06:00', 'G', 1], ['a', '08:00', 'G', 0]]
        night = self.offline()
        initialize_offline(night)
        package_id = import_package(night, wire_blob(fixture))
        self.assertEqual(recover(night, package_id, 'A'), [('a', '06:00', 'G', 3), ('a', '06:00', 'H', 2),
                                                          ('a', '07:00', 'G', 1), ('z', '06:00', 'G', 1)])
