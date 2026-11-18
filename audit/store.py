from dataclasses import dataclass

from offline.catalog import init_offline_catalog
from storage import InputError, NotFoundError, atomic, decode_json, encode_json


@dataclass(frozen=True)
class AuditRecord:
    audit_id: int
    package_id: int
    revision: str
    actual: dict[str, int]
    differences: dict[str, int] | None


def init_audit_store(db):
    db.execute('''
        CREATE TABLE IF NOT EXISTS audits (
            audit_id INTEGER PRIMARY KEY,
            package_id INTEGER NOT NULL REFERENCES received_packages(package_id),
            revision TEXT NOT NULL,
            actual TEXT NOT NULL,
            differences TEXT NOT NULL
        )
    ''')


def initialize_offline(db):
    with atomic(db):
        init_offline_catalog(db)
        init_audit_store(db)


def save_audit(db, package_id, revision, actual, differences):
    cursor = db.execute('''
        INSERT INTO audits (package_id, revision, actual, differences) VALUES (?, ?, ?, ?)
    ''', (package_id, revision, encode_json(actual), encode_json(differences)))
    return AuditRecord(cursor.lastrowid, package_id, revision, actual, differences)


def get_audit(db, audit_id):
    if type(audit_id) is not int or audit_id <= 0:
        raise InputError('audit number must be a positive integer')
    if audit_id > 2**63 - 1:
        raise NotFoundError('audit number is outside the catalog')
    row = db.execute('''
        SELECT package_id, revision, actual, differences FROM audits WHERE audit_id = ?
    ''', (audit_id,)).fetchone()
    if row is None:
        raise NotFoundError(f'unknown audit {audit_id}')
    package_id, revision, actual, differences = row
    return AuditRecord(audit_id, package_id, revision, decode_json(actual), decode_json(differences))
