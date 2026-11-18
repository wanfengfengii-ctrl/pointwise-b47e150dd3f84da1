from collections import defaultdict, deque

from inventory.rows import add_row_changes
from offline.catalog import get_received_package
from offline.render import render_rows
from publication.package import PackageEvidence, decode_package
from storage import EvidenceError, NotFoundError, require_text


def recover_revision_rows(evidence: PackageEvidence, revision):
    """Find the inventory for the requested revision and replay its later deltas."""
    require_text(revision, "revision")
    if revision not in evidence.revisions:
        raise NotFoundError(f"revision {revision!r} not declared in this package")

    anchors = {record.revision: record.rows for record in evidence.inventories}
    incoming = defaultdict(list)
    for delta in evidence.deltas:
        incoming[delta.target].append(delta)

    pending = deque([revision])
    toward_request = {revision: None}
    while pending:
        current = pending.popleft()
        if current in anchors:
            counts = anchors[current].copy()
            while current != revision:
                delta = toward_request[current]
                counts = add_row_changes(counts, delta.changes)
                current = delta.target
                if any(count < 0 for count in counts.values()):
                    raise EvidenceError(f"negative row count at revision {current!r}")
            return render_rows(counts)
        for delta in incoming[current]:
            if delta.source not in toward_request:
                toward_request[delta.source] = delta
                pending.append(delta.source)
    raise EvidenceError(f"revision {revision!r} has no inventory in this package")


def recover(db, package_id, revision):
    blob = get_received_package(db, package_id)
    return recover_revision_rows(decode_package(blob), revision)
