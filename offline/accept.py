from offline.catalog import save_received_package
from publication.package import decode_package
from publication.reconcile import reconcile_evidence
from storage import atomic


def import_package(db, blob: bytes):
    # Format and field validation raise PackageError; well-formed foreign
    # pieces must also satisfy the same full-evidence business invariants as
    # locally published shipments (EvidenceError). Either failure rolls back
    # and leaves no catalog entry or success receipt.
    evidence = decode_package(blob)
    reconcile_evidence(evidence)
    with atomic(db):
        return save_received_package(db, blob)
