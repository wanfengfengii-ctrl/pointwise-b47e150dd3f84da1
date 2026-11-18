from audit.store import AuditRecord, get_audit


def render_audit(record: AuditRecord):
    result = {'audit_id': record.audit_id, 'package_id': record.package_id,
              'revision': record.revision, 'actual': dict(sorted(record.actual.items()))}
    if record.differences is not None:
        result['differences'] = dict(sorted(record.differences.items()))
    return result


def fetch_audit(db, audit_id):
    return render_audit(get_audit(db, audit_id))
