import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from inventory.accept import accept_inventory
from publication.commit import initialize_source
from revisions.import_delta import accept_delta
from revisions.register import register_revision
from storage import open_database

X = ('ridge', '06:00', 'G')
Y = ('ridge', '07:00', 'H')
BASE_DELTAS = ('d-ba', 'd-bc')


def seed_case(db, direct=None):
    initialize_source(db, ['P'], [('P', 'A')])
    accept_inventory(db, 'P', 'A', 'inv-a', [(*X, 1), (*X, 1)])
    for revision in ('B', 'C'):
        register_revision(db, 'P', revision)
    accept_delta(db, 'P', 'd-ba', 'B', 'A', [(*X, 1)])
    accept_delta(db, 'P', 'd-bc', 'B', 'C', [(*X, -1), (*Y, 1)])
    if direct is not None:
        accept_delta(db, 'P', 'd-ac', 'A', 'C', [(*X, direct), (*Y, 1)])
        return (*BASE_DELTAS, 'd-ac')
    return BASE_DELTAS


def foreign_blob():
    return (Path(__file__).resolve().parents[1] / 'examples' / 'foreign-v1.json').read_bytes()


def wire_blob(document):
    return json.dumps(document, ensure_ascii=False).encode('utf-8')


def shipment_counts(db):
    return (db.execute('SELECT count(*) FROM shipments').fetchone()[0],
            db.execute('SELECT count(*) FROM receipts').fetchone()[0])


class LakesideTestCase(TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.source_path = self.directory / 'source.sqlite'
        self.offline_path = self.directory / 'offline.sqlite'

    def source(self):
        return self.enterContext(open_database(self.source_path))

    def offline(self):
        return self.enterContext(open_database(self.offline_path))
