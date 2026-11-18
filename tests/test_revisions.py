from publication.commit import initialize_source
from revisions.import_delta import accept_delta
from revisions.register import register_revision
from revisions.registry import get_declared_revision, get_delta
from revisions.select import select_deltas
from storage import InputError, NotFoundError, open_database
from tests import LakesideTestCase, X, Y


class RevisionTests(LakesideTestCase):
    def test_delta_scope(self):
        with open_database(self.source_path) as db:
            initialize_source(db, ['P', 'Q'], [('P', 'A'), ('Q', 'outside')])
            register_revision(db, 'P', 'B')
            accept_delta(db, 'P', 'local', 'A', 'B', [(*X, -1)])
            with self.assertRaises(InputError):
                accept_delta(db, 'P', 'foreign', 'A', 'outside', [(*Y, 1)])
        with open_database(self.source_path) as db:
            (local,) = select_deltas(db, 'P', ['local'])
            self.assertEqual((local.delta_id, local.source, local.target, local.changes),
                             ('local', 'A', 'B', {X: -1}))
            with self.assertRaises(NotFoundError):
                get_delta(db, 'P', 'foreign')
            self.assertEqual(db.execute('SELECT count(*) FROM deltas').fetchone(), (1,))

    def test_registered_delta_and_stable_original(self):
        db = self.source()
        initialize_source(db, ['P'], [('P', 'A')])
        self.assertEqual(register_revision(db, 'P', 'B'), 'B')
        self.assertEqual(register_revision(db, 'P', 'B'), 'B')
        rows = [(*X, -5), (*X, 2), (*Y, -1), (*Y, 1)]
        self.assertEqual(accept_delta(db, 'P', 'first', 'B', 'A', rows), 'first')
        self.assertEqual(accept_delta(db, 'P', 'first', 'B', 'A', [(*X, -3)]), 'first')
        accept_delta(db, 'P', 'parallel', 'B', 'A', [(*X, -3)])
        with self.assertRaises(InputError):
            accept_delta(db, 'P', 'first', 'A', 'B', [(*X, 3)])
        with open_database(self.source_path) as reopened:
            self.assertEqual(get_declared_revision(reopened, 'P', 'B'), 'B')
            selected = select_deltas(reopened, 'P', ['parallel', 'first'])
            self.assertEqual([(d.delta_id, d.source, d.target, d.changes) for d in selected],
                             [('first', 'B', 'A', {X: -3}), ('parallel', 'B', 'A', {X: -3})])

    def test_unknown_partition_and_endpoints(self):
        db = self.source()
        initialize_source(db, ['P'], [('P', 'A')])
        with self.assertRaises(InputError):
            register_revision(db, 'missing', 'A')
        self.assertEqual(get_declared_revision(db, 'P', 'A'), 'A')
        for source, target in [('A', 'B'), ('B', 'A')]:
            with self.subTest(source=source, target=target), self.assertRaises(InputError):
                accept_delta(db, 'P', 'unknown', source, target, [])
        self.assertEqual(db.execute('SELECT count(*) FROM deltas').fetchone(), (0,))
