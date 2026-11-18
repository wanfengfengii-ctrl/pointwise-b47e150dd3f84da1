from inventory.rows import add_row_changes
from publication.package import PackageEvidence
from storage import EvidenceError


def reconcile_evidence(evidence: PackageEvidence) -> None:
    """Establish the accounts of the selected revisions before shipment."""
    parent_deltas = {}
    for delta in evidence.deltas:
        parent_deltas.setdefault(delta.target, delta)

    accounts = {}
    for inventory in evidence.inventories:
        accounts.setdefault(inventory.revision, inventory.rows)

    pending = list(parent_deltas.values())
    while pending:
        deferred = []
        for delta in pending:
            source_known = delta.source in accounts
            target_known = delta.target in accounts
            if source_known and target_known:
                continue
            if source_known:
                revision = delta.target
                rows = add_row_changes(accounts[delta.source], delta.changes)
            elif target_known:
                revision = delta.source
                rows = add_row_changes(accounts[delta.target], delta.changes, -1)
            else:
                deferred.append(delta)
                continue
            if any(count < 0 for count in rows.values()):
                raise EvidenceError(f"negative row count at revision {revision!r}")
            accounts[revision] = rows
        if len(deferred) == len(pending):
            break
        pending = deferred

    missing = sorted(set(evidence.revisions) - accounts.keys())
    if missing:
        names = ", ".join(missing)
        raise EvidenceError(f"revisions without an inventory: {names}")
