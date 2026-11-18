from inventory.partitions import require_partition
from inventory.rows import normalize_inventory_rows
from inventory.store import InventoryRecord, save_inventory
from revisions.registry import require_declared_revision
from storage import atomic, require_text


def accept_inventory(db, partition, revision, inventory_id, rows):
    require_text(inventory_id, 'inventory number')
    counts = normalize_inventory_rows(rows)
    with atomic(db):
        require_partition(db, partition)
        require_declared_revision(db, partition, revision)
        return save_inventory(db, InventoryRecord(partition, inventory_id, revision, counts))
