from storage import InputError, NotFoundError


def init_offline_catalog(db):
    db.execute('''
        CREATE TABLE IF NOT EXISTS received_packages (
            package_id INTEGER PRIMARY KEY,
            blob BLOB NOT NULL UNIQUE
        )
    ''')


def save_received_package(db, blob):
    cursor = db.execute('INSERT INTO received_packages (blob) VALUES (?) ON CONFLICT DO NOTHING', (blob,))
    if cursor.rowcount:
        return cursor.lastrowid
    (package_id,) = db.execute('SELECT package_id FROM received_packages WHERE blob = ?', (blob,)).fetchone()
    return package_id


def get_received_package(db, package_id) -> bytes:
    if type(package_id) is not int or package_id <= 0:
        raise InputError('offline package number must be a positive integer')
    if package_id > 2**63 - 1:
        raise NotFoundError('offline package number is outside the catalog')
    row = db.execute('SELECT blob FROM received_packages WHERE package_id = ?', (package_id,)).fetchone()
    if row is None:
        raise NotFoundError(f'unknown offline package {package_id}')
    return row[0]
