from inventory.partitions import require_partition
from revisions.registry import save_revision
from storage import require_text


def register_revision(db, partition, revision):
    require_partition(db, partition)
    require_text(revision, 'revision')
    return save_revision(db, partition, revision)
