from dataclasses import dataclass

from inventory.rows import RowCounts, normalize_delta_rows, ordered_rows
from storage import InputError, NotFoundError, decode_json, encode_json, require_text


@dataclass(frozen=True)
class DeltaRecord:
    partition: str
    delta_id: str
    source: str
    target: str
    changes: RowCounts


def init_revision_registry(db):
    db.execute('''
        CREATE TABLE IF NOT EXISTS revisions (
            partition TEXT NOT NULL REFERENCES partitions(partition),
            revision TEXT NOT NULL,
            PRIMARY KEY (partition, revision)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS deltas (
            delta_id TEXT PRIMARY KEY NOT NULL,
            partition TEXT NOT NULL REFERENCES partitions(partition),
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            changes TEXT NOT NULL
        )
    ''')


def get_declared_revision(db, partition, revision):
    require_text(partition, 'partition')
    require_text(revision, 'revision')
    row = db.execute('''
        SELECT revision FROM revisions WHERE partition = ? AND revision = ?
    ''', (partition, revision)).fetchone()
    if row is None:
        raise NotFoundError(f'revision {revision!r} in partition {partition!r}')
    return row[0]


def require_declared_revision(db, partition, revision):
    try:
        return get_declared_revision(db, partition, revision)
    except NotFoundError as exc:
        raise InputError(str(exc)) from exc


def save_revision(db, partition, revision):
    db.execute('INSERT INTO revisions VALUES (?, ?) ON CONFLICT DO NOTHING', (partition, revision))
    return revision


def get_delta(db, partition, delta_id):
    require_text(partition, 'partition')
    require_text(delta_id, 'delta number')
    row = db.execute('''
        SELECT source, target, changes FROM deltas WHERE delta_id = ? AND partition = ?
    ''', (delta_id, partition)).fetchone()
    if row is None:
        raise NotFoundError(f'delta {delta_id!r} in partition {partition!r}')
    source, target, changes = row
    return DeltaRecord(partition, delta_id, source, target, normalize_delta_rows(decode_json(changes)))


def save_delta(db, record: DeltaRecord):
    """Store the original direction and normalized changes of a validated delta."""
    content = (record.partition, record.source, record.target, encode_json(ordered_rows(record.changes)))
    inserted = db.execute('''
        INSERT INTO deltas (delta_id, partition, source, target, changes) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (delta_id) DO NOTHING
    ''', (record.delta_id, *content))
    if inserted.rowcount == 0:
        previous = db.execute('''
            SELECT partition, source, target, changes FROM deltas WHERE delta_id = ?
        ''', (record.delta_id,)).fetchone()
        if previous != content:
            raise InputError(f'delta number {record.delta_id!r} already has different content')
    return record.delta_id
