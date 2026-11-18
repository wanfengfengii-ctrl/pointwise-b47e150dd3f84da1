import sqlite3

from inventory.partitions import init_partitions
from inventory.store import init_inventory_store
from publication.package import encode_package
from publication.receipts import init_receipts, record_receipt
from publication.reconcile import reconcile_evidence
from publication.scope import select_publication_evidence
from revisions.register import register_revision
from revisions.registry import init_revision_registry
from storage import StorageError, atomic


def init_shipment_store(db):
    db.execute('''
        CREATE TABLE IF NOT EXISTS shipments (package_id INTEGER PRIMARY KEY, blob BLOB NOT NULL)
    ''')
    init_receipts(db)


def initialize_source(db, partitions=(), initial_revisions=()):
    with atomic(db):
        init_partitions(db, partitions)
        init_revision_registry(db)
        init_inventory_store(db)
        init_shipment_store(db)
        for partition, revision in initial_revisions:
            register_revision(db, partition, revision)


def commit_shipment(db, evidence):
    """Write qualified evidence and its receipt in the caller's transaction."""
    if not db.in_transaction:
        raise RuntimeError('shipment write requires an active transaction')
    blob = encode_package(evidence)
    cursor = db.execute('INSERT INTO shipments (blob) VALUES (?)', (blob,))
    return record_receipt(db, cursor.lastrowid, evidence)


def publish(db, partition, revision_ids, inventory_ids, delta_ids):
    try:
        with atomic(db):
            evidence = select_publication_evidence(db, partition, revision_ids, inventory_ids, delta_ids)
            reconcile_evidence(evidence)
            return commit_shipment(db, evidence)
    except sqlite3.Error as exc:
        raise StorageError(f'publication transaction failed: {exc}') from exc
