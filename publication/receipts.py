from dataclasses import dataclass

from storage import InputError, NotFoundError, decode_json, encode_json


@dataclass(frozen=True)
class Receipt:
    receipt_id: int
    package_id: int
    partition: str
    revisions: tuple[str, ...]
    inventory_ids: tuple[str, ...]
    delta_ids: tuple[str, ...]


def init_receipts(db):
    db.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id INTEGER PRIMARY KEY,
            package_id INTEGER NOT NULL UNIQUE REFERENCES shipments(package_id),
            partition TEXT NOT NULL,
            scope TEXT NOT NULL
        )
    ''')


def record_receipt(db, package_id, evidence):
    revisions = tuple(sorted(evidence.revisions))
    inventory_ids = tuple(sorted(record.inventory_id for record in evidence.inventories))
    delta_ids = tuple(sorted(record.delta_id for record in evidence.deltas))
    scope = encode_json((revisions, inventory_ids, delta_ids))
    cursor = db.execute('INSERT INTO receipts (package_id, partition, scope) VALUES (?, ?, ?)',
                        (package_id, evidence.partition, scope))
    return Receipt(cursor.lastrowid, package_id, evidence.partition, revisions, inventory_ids, delta_ids)


def get_receipt(db, package_id):
    _require_package_id(package_id)
    row = db.execute('''
        SELECT receipt_id, partition, scope FROM receipts WHERE package_id = ?
    ''', (package_id,)).fetchone()
    if row is None:
        raise NotFoundError(f'no receipt for package {package_id}')
    receipt_id, partition, scope = row
    revisions, inventories, deltas = map(tuple, decode_json(scope))
    return Receipt(receipt_id, package_id, partition, revisions, inventories, deltas)


def _require_package_id(package_id):
    if type(package_id) is not int or package_id <= 0:
        raise InputError('package number must be a positive integer')
    if package_id > 2**63 - 1:
        raise NotFoundError('published package number is outside the catalog')


def fetch(db, package_id) -> bytes:
    _require_package_id(package_id)
    row = db.execute('''
        SELECT shipments.blob FROM shipments JOIN receipts USING (package_id)
        WHERE shipments.package_id = ?
    ''', (package_id,)).fetchone()
    if row is None:
        raise NotFoundError(f'unknown published package {package_id}')
    return row[0]
