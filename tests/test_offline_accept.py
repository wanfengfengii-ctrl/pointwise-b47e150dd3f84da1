import json

from audit.store import initialize_offline
from offline.accept import import_package
from offline.catalog import get_received_package
from offline.recover import recover
from storage import PackageError
from tests import LakesideTestCase, Y, foreign_blob, wire_blob


class OfflineAcceptTests(LakesideTestCase):
    def test_bad_package(self):
        night = self.offline()
        initialize_offline(night)
        original = foreign_blob()
        first = import_package(night, original)
        wrong_version = original.replace(b'"version": 1', b'"version": true')
        duplicate_field = original.replace(b'"version": 1', b'"version": 1, "version": 1')
        for bad in (b'{', b'\xff', wrong_version, duplicate_field, original.decode('utf-8')):
            with self.subTest(bad=bad), self.assertRaises(PackageError):
                import_package(night, bad)
        self.assertEqual(night.execute('SELECT count(*) FROM received_packages').fetchone(), (1,))
        self.assertEqual(get_received_package(night, first), original)
        self.assertEqual(recover(night, first, 'C'), [(*Y, 1)])

    def test_incomplete_evidence(self):
        night = self.offline()
        initialize_offline(night)
        original = foreign_blob()
        first = import_package(night, original)
        incomplete = json.loads(original)
        del incomplete['deltas'][0]['target']
        outside = json.loads(original)
        outside['deltas'][0]['target'] = 'D'
        duplicate = json.loads(original)
        duplicate['deltas'][1]['id'] = duplicate['deltas'][0]['id']
        negative = json.loads(original)
        negative['inventories'][0]['rows'][0][3] = -1
        for document in (incomplete, outside, duplicate, negative):
            with self.subTest(document=document), self.assertRaises(PackageError):
                import_package(night, wire_blob(document))
        self.assertEqual(night.execute('SELECT count(*) FROM received_packages').fetchone(), (1,))
        self.assertEqual(get_received_package(night, first), original)
        self.assertEqual(recover(night, first, 'C'), [(*Y, 1)])
