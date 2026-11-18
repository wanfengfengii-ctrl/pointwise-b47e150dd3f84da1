from inventory.partitions import require_partition
from inventory.store import get_inventory
from publication.package import PackageEvidence, validate_scope
from revisions.select import select_deltas, select_revisions
from storage import EvidenceError, InputError, NotFoundError, unique_names


def select_publication_evidence(db, partition, revision_ids, inventory_ids, delta_ids):
    """Resolve one selection inside the caller's stable publication transaction."""
    try:
        require_partition(db, partition)
        revisions = select_revisions(db, partition, revision_ids)
        inventories = tuple(get_inventory(db, partition, inventory_id)
                            for inventory_id in unique_names(inventory_ids, 'inventory number'))
        deltas = select_deltas(db, partition, delta_ids)
        evidence = PackageEvidence(partition, revisions, inventories, deltas)
        validate_scope(evidence)
        return evidence
    except (InputError, NotFoundError) as exc:
        raise EvidenceError(f'invalid publication selection: {exc}') from exc
