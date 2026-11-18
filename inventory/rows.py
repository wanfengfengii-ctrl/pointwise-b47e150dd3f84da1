from storage import InputError, members, require_text

RowKey = tuple[str, str, str]
RowCounts = dict[RowKey, int]


def _normalize(rows, *, signed):
    counts = {}
    for row in members(rows, 'rows'):
        if not isinstance(row, (tuple, list)) or len(row) != 4:
            raise InputError('row must contain station, slot, quality and count')
        station, slot, quality, count = row
        key = (require_text(station, 'station'), require_text(slot, 'slot'),
               require_text(quality, 'quality'))
        if type(count) is not int or (count < 0 and not signed):
            raise InputError('invalid row count')
        counts[key] = counts.get(key, 0) + count
    return {key: count for key, count in counts.items() if count != 0}


def normalize_inventory_rows(rows) -> RowCounts:
    return _normalize(rows, signed=False)


def normalize_delta_rows(rows) -> RowCounts:
    return _normalize(rows, signed=True)


def add_row_changes(counts: RowCounts, changes: RowCounts, direction: int = 1) -> RowCounts:
    result = counts.copy()
    for key, change in changes.items():
        count = result.get(key, 0) + direction * change
        if count:
            result[key] = count
        else:
            result.pop(key, None)
    return result


def ordered_rows(counts: RowCounts):
    return [(*key, counts[key]) for key in sorted(counts)]
