from dataclasses import dataclass

from inventory.rows import normalize_delta_rows, normalize_inventory_rows, ordered_rows
from inventory.store import InventoryRecord
from revisions.registry import DeltaRecord
from storage import InputError, PackageError, decode_json, encode_json, require_text, unique_names


@dataclass(frozen=True)
class PackageEvidence:
    partition: str
    revisions: tuple[str, ...]
    inventories: tuple[InventoryRecord, ...]
    deltas: tuple[DeltaRecord, ...]


def validate_scope(evidence: PackageEvidence):
    revisions = set(evidence.revisions)
    if not revisions:
        raise InputError('a handoff needs at least one declared revision')
    unique_names((record.inventory_id for record in evidence.inventories), 'inventory number')
    unique_names((record.delta_id for record in evidence.deltas), 'delta number')
    for record in evidence.inventories:
        if record.partition != evidence.partition or record.revision not in revisions:
            raise InputError(f'inventory {record.inventory_id!r} is outside the handoff scope')
    for record in evidence.deltas:
        if record.partition != evidence.partition or not {record.source, record.target} <= revisions:
            raise InputError(f'delta {record.delta_id!r} is outside the handoff scope')


def encode_package(evidence: PackageEvidence) -> bytes:
    inventories = sorted(evidence.inventories, key=lambda record: record.inventory_id)
    deltas = sorted(evidence.deltas, key=lambda record: record.delta_id)
    document = {
        'version': 1,
        'partition': evidence.partition,
        'revisions': sorted(evidence.revisions),
        'inventories': [
            {'id': record.inventory_id, 'revision': record.revision, 'rows': ordered_rows(record.rows)}
            for record in inventories
        ],
        'deltas': [
            {'id': record.delta_id, 'source': record.source, 'target': record.target,
             'rows': ordered_rows(record.changes)}
            for record in deltas
        ],
    }
    return encode_json(document).encode('utf-8')


def _object(value, *fields):
    if not isinstance(value, dict) or value.keys() != set(fields):
        raise InputError(f'expected object fields {", ".join(fields)}')
    return value


def _array(value, label):
    if not isinstance(value, list):
        raise InputError(f'{label} must be a JSON array')
    return value


def _inventory(partition, value):
    record = _object(value, 'id', 'revision', 'rows')
    return InventoryRecord(partition, require_text(record['id'], 'inventory number'),
                           require_text(record['revision'], 'revision'),
                           normalize_inventory_rows(_array(record['rows'], 'inventory rows')))


def _delta(partition, value):
    record = _object(value, 'id', 'source', 'target', 'rows')
    return DeltaRecord(partition, require_text(record['id'], 'delta number'),
                       require_text(record['source'], 'source revision'),
                       require_text(record['target'], 'target revision'),
                       normalize_delta_rows(_array(record['rows'], 'delta rows')))


def decode_package(blob: bytes) -> PackageEvidence:
    if not isinstance(blob, bytes):
        raise PackageError('package must be UTF-8 bytes')
    try:
        document = _object(decode_json(blob.decode('utf-8')), 'version', 'partition', 'revisions',
                           'inventories', 'deltas')
        if type(document['version']) is not int or document['version'] != 1:
            raise InputError('unsupported package version')
        partition = require_text(document['partition'], 'partition')
        revisions = unique_names(_array(document['revisions'], 'revisions'), 'revision')
        inventories = tuple(_inventory(partition, value)
                            for value in _array(document['inventories'], 'inventories'))
        deltas = tuple(_delta(partition, value) for value in _array(document['deltas'], 'deltas'))
        evidence = PackageEvidence(partition, revisions, inventories, deltas)
        validate_scope(evidence)
        return evidence
    except (ValueError, RecursionError) as exc:
        raise PackageError(f'invalid V1 package: {exc}') from exc
