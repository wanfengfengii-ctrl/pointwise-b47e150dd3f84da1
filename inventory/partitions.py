from storage import InputError, require_text, unique_names


def init_partitions(db, partition_ids=()):
    ids = unique_names(partition_ids, 'partition')
    db.execute('CREATE TABLE IF NOT EXISTS partitions (partition TEXT PRIMARY KEY NOT NULL)')
    db.executemany('INSERT INTO partitions VALUES (?) ON CONFLICT DO NOTHING',
                   ((partition,) for partition in ids))


def require_partition(db, partition):
    require_text(partition, 'partition')
    row = db.execute('SELECT partition FROM partitions WHERE partition = ?', (partition,)).fetchone()
    if row is None:
        raise InputError(f'unknown partition {partition!r}')
    return row[0]
