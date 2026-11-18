from dataclasses import dataclass

from inventory.rows import RowCounts, normalize_inventory_rows, ordered_rows
from storage import InputError, NotFoundError, decode_json, encode_json, require_text


@dataclass(frozen=True)
class InventoryRecord:
    partition: str
    inventory_id: str
    revision: str
    rows: RowCounts


def init_inventory_store(db):
    db.execute('''
        CREATE TABLE IF NOT EXISTS inventories (
            inventory_id TEXT PRIMARY KEY NOT NULL,
            partition TEXT NOT NULL,
            revision TEXT NOT NULL,
            rows TEXT NOT NULL,
            FOREIGN KEY (partition, revision) REFERENCES revisions(partition, revision)
        )
    ''')


def get_inventory(db, partition, inventory_id):
    require_text(partition, 'partition')
    require_text(inventory_id, 'inventory number')
    row = db.execute('''
        SELECT revision, rows FROM inventories WHERE inventory_id = ? AND partition = ?
    ''', (inventory_id, partition)).fetchone()
    if row is None:
        raise NotFoundError(f'inventory {inventory_id!r} in partition {partition!r}')
    revision, rows = row
    return InventoryRecord(partition, inventory_id, revision, normalize_inventory_rows(decode_json(rows)))


def save_inventory(db, record: InventoryRecord):
    """Save a validated inventory and preserve the original on a conflicting retry."""
    content = (record.partition, record.revision, encode_json(ordered_rows(record.rows)))
    inserted = db.execute('''
        INSERT INTO inventories (inventory_id, partition, revision, rows) VALUES (?, ?, ?, ?)
        ON CONFLICT (inventory_id) DO NOTHING
    ''', (record.inventory_id, *content))
    if inserted.rowcount == 0:
        previous = db.execute('''
            SELECT partition, revision, rows FROM inventories WHERE inventory_id = ?
        ''', (record.inventory_id,)).fetchone()
        if previous != content:
            raise InputError(f'inventory number {record.inventory_id!r} already has different content')
    return record.inventory_id
