from audit.comparison import compare_ledger_counts, validate_ledger_counts
from audit.counts import count_by_quality_code
from audit.export import render_audit
from audit.store import save_audit
from offline.recover import recover
from storage import atomic


def audit(db, package_id, revision, ledger=None):
    expected = validate_ledger_counts(ledger)
    rows = recover(db, package_id, revision)
    actual = count_by_quality_code(rows)
    differences = compare_ledger_counts(actual, expected)
    with atomic(db):
        record = save_audit(db, package_id, revision, actual, differences)
        return render_audit(record)
