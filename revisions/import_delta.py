from inventory.rows import normalize_delta_rows
from revisions.registry import DeltaRecord, require_declared_revision, save_delta
from storage import atomic, require_text


def accept_delta(db, partition, delta_id, source, target, rows):
    require_text(delta_id, 'delta number')
    changes = normalize_delta_rows(rows)
    with atomic(db):
        require_declared_revision(db, partition, source)
        require_declared_revision(db, partition, target)
        return save_delta(db, DeltaRecord(partition, delta_id, source, target, changes))
