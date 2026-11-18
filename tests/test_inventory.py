from inventory.accept import accept_inventory
from inventory.store import get_inventory
from publication.commit import initialize_source
from revisions.register import register_revision
from revisions.registry import get_declared_revision
from storage import InputError, NotFoundError, open_database
from tests import LakesideTestCase, X


class InventoryTests(LakesideTestCase):
    def test_inventory_repeat(self):
        with open_database(self.source_path) as db:
            initialize_source(db, ['P'], [('P', 'A')])
            self.assertEqual(accept_inventory(db, 'P', 'A', 'formal', [(*X, 1), (*X, 1)]), 'formal')
            register_revision(db, 'P', 'B')
        with open_database(self.source_path) as db:
            initialize_source(db, ['P'], [('P', 'A')])
            self.assertEqual(get_declared_revision(db, 'P', 'B'), 'B')
            self.assertEqual(accept_inventory(db, 'P', 'A', 'formal', [(*X, 2)]), 'formal')
            self.assertEqual(get_inventory(db, 'P', 'formal').rows, {X: 2})
            self.assertEqual(db.execute('SELECT count(*) FROM inventories').fetchone(), (1,))

    def test_full_row_identity(self):
        db = self.source()
        initialize_source(db, ['P'], [('P', 'A')])
        other = ('ridge', '06:00', 'H')
        accept_inventory(db, 'P', 'A', 'same-slot', [(*X, 1), (*other, 1), (*X, 1)])
        accept_inventory(db, 'P', 'A', 'empty', [(*X, 0)])
        with open_database(self.source_path) as reopened:
            self.assertEqual(get_inventory(reopened, 'P', 'same-slot').rows, {X: 2, other: 1})
            self.assertEqual(get_inventory(reopened, 'P', 'empty').rows, {})

    def test_changed_resubmission(self):
        db = self.source()
        initialize_source(db, ['P', 'Q'], [('P', 'A'), ('P', 'B'), ('Q', 'A')])
        accept_inventory(db, 'P', 'A', 'formal', [(*X, 2)])
        for partition, revision, rows in [('P', 'A', [(*X, 3)]), ('P', 'B', [(*X, 2)]),
                                          ('Q', 'A', [(*X, 2)])]:
            with self.subTest(partition=partition, revision=revision, rows=rows):
                with self.assertRaises(InputError):
                    accept_inventory(db, partition, revision, 'formal', rows)
        with open_database(self.source_path) as reopened:
            original = get_inventory(reopened, 'P', 'formal')
            self.assertEqual((original.partition, original.revision, original.rows), ('P', 'A', {X: 2}))
            self.assertEqual(reopened.execute('SELECT count(*) FROM inventories').fetchone(), (1,))

    def test_invalid_rows_and_anchor(self):
        db = self.source()
        initialize_source(db, ['P'], [('P', 'A')])
        for rows in [[X], [(*X, -1), (*X, 3)], [(*X, True)], [(*X, 1.0)], [(*X, None)],
                     [('ridge', '', 'G', 1)], [('ridge', '06:00', None, 1)]]:
            with self.subTest(rows=rows), self.assertRaises(InputError):
                accept_inventory(db, 'P', 'A', 'bad', rows)
        with self.assertRaises(InputError):
            accept_inventory(db, 'P', 'missing', 'bad', [])
        with self.assertRaises(NotFoundError):
            get_inventory(db, 'P', 'bad')
        self.assertEqual(db.execute('SELECT count(*) FROM inventories').fetchone(), (0,))
