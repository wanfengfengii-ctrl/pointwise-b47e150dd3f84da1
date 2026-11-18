from revisions.registry import get_declared_revision, get_delta
from storage import unique_names


def select_revisions(db, partition, revision_ids):
    return tuple(get_declared_revision(db, partition, revision)
                 for revision in unique_names(revision_ids, 'revision'))


def select_deltas(db, partition, delta_ids):
    return tuple(get_delta(db, partition, delta_id)
                 for delta_id in unique_names(delta_ids, 'delta number'))
