import json
import sqlite3
from contextlib import contextmanager
from decimal import Decimal


class InputError(ValueError):
    """The submitted business input is invalid."""


class EvidenceError(InputError):
    """The selected evidence does not establish a handoff."""


class PackageError(InputError):
    """The submitted bytes violate the V1 exchange format."""


class NotFoundError(LookupError):
    """The requested business identity does not exist in this scope."""


class StorageError(RuntimeError):
    """The publication transaction could not be committed."""


@contextmanager
def open_database(path):
    db = sqlite3.connect(path, isolation_level=None)
    try:
        db.execute('PRAGMA foreign_keys = ON')
        yield db
    finally:
        db.close()


@contextmanager
def atomic(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


def require_text(value, label):
    if not isinstance(value, str) or not value:
        raise InputError(f'{label} must be nonempty text')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise InputError(f'{label} must be valid UTF-8 text') from exc
    return value


def members(values, label):
    if isinstance(values, (str, bytes)):
        raise InputError(f'{label} must be a collection')
    try:
        return iter(values)
    except TypeError as exc:
        raise InputError(f'{label} must be a collection') from exc


def unique_names(values, label):
    names = tuple(require_text(value, label) for value in members(values, label))
    if len(names) != len(set(names)):
        raise InputError(f'duplicate {label}')
    return tuple(sorted(names))


def encode_json(value):
    """Encode the application's JSON values, including unbounded integer counts."""
    if type(value) is int:
        return str(Decimal(value))
    if isinstance(value, dict):
        fields = (f'{encode_json(key)}:{encode_json(value[key])}' for key in sorted(value))
        return '{' + ','.join(fields) + '}'
    if isinstance(value, (list, tuple)):
        return '[' + ','.join(encode_json(item) for item in value) + ']'
    return json.dumps(value, ensure_ascii=True, allow_nan=False)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key {key!r}')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f'invalid JSON constant {value}')


def decode_json(text):
    return json.loads(text, parse_int=lambda literal: int(Decimal(literal)),
                      parse_constant=_reject_constant, object_pairs_hook=_unique_object)
