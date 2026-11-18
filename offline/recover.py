from offline.catalog import get_received_package
from publication.package import decode_package
from publication.reconcile import recover_account
from storage import EvidenceError, NotFoundError, require_text


def recover_revision_rows(evidence, revision):
    """Recover the full rows of one revision from the package's evidence.

    Deltas are equations between revisions, so evidence is traversed in both
    directions: a formal inventory can anchor a revision through forward or
    reverse delta chains. Reversed or reordered representations of the same
    evidence yield the same rows.
    """
    require_text(revision, "revision")
    if revision not in evidence.revisions:
        raise NotFoundError(f"revision {revision!r} not declared in this package")
    try:
        return recover_account(evidence, revision)
    except EvidenceError:
        raise
    except KeyError as exc:  # defensive: solve_accounts covers every revision
        raise EvidenceError(f"revision {revision!r} has no inventory in this package") from exc


def recover(db, package_id, revision):
    blob = get_received_package(db, package_id)
    return recover_revision_rows(decode_package(blob), revision)
