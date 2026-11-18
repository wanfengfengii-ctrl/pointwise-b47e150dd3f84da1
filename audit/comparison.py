from collections.abc import Mapping

from storage import InputError, require_text


def validate_ledger_counts(ledger):
    if ledger is None:
        return None
    if not isinstance(ledger, Mapping):
        raise InputError('ledger must map quality codes to nonnegative integers')
    counts = {}
    for code, count in ledger.items():
        require_text(code, 'ledger quality code')
        if type(count) is not int or count < 0:
            raise InputError('ledger count must be a nonnegative integer')
        counts[code] = count
    return counts


def compare_ledger_counts(actual, ledger):
    if ledger is None:
        return None
    return {code: actual.get(code, 0) - ledger.get(code, 0)
            for code in sorted(actual.keys() | ledger.keys())}
