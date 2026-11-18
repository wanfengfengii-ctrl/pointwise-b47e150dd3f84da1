import json
from pathlib import Path
from tempfile import TemporaryDirectory

from audit.export import fetch_audit
from audit.reconcile import audit
from audit.store import initialize_offline
from inventory.accept import accept_inventory
from offline.accept import import_package
from offline.recover import recover
from publication.commit import initialize_source, publish
from publication.receipts import fetch
from revisions.import_delta import accept_delta
from revisions.register import register_revision
from storage import open_database


def report(case_id, inputs, expected, actual, downstream_expected, downstream_actual, code_paths, oracle):
    if actual != expected or downstream_actual != downstream_expected:
        raise AssertionError((case_id, expected, actual, downstream_expected, downstream_actual))
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id, 'input': inputs, 'expected': expected, 'actual': actual,
        'downstream_expected': downstream_expected, 'downstream_actual': downstream_actual,
        'code_paths': code_paths, 'oracle': oracle,
    }, ensure_ascii=False, sort_keys=True))


def main():
    x = ('ridge', '06:00', 'G')
    y = ('ridge', '07:00', 'H')
    foreign = (Path(__file__).resolve().parent / 'examples' / 'foreign-v1.json').read_bytes()
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source_path = root / 'source.sqlite'
        offline_path = root / 'offline.sqlite'
        with open_database(source_path) as source:
            initialize_source(source, ['P'], [('P', 'A')])
            accept_inventory(source, 'P', 'A', 'opening', [(*x, 1), (*x, 1)])
            for revision in ('B', 'C'):
                register_revision(source, 'P', revision)
            accept_delta(source, 'P', 'back', 'B', 'A', [(*x, 1)])
            accept_delta(source, 'P', 'next', 'B', 'C', [(*x, -1), (*y, 1)])
            accept_delta(source, 'P', 'direct', 'A', 'C', [(*x, -2), (*y, 1)])
            receipt = publish(source, 'P', ['A', 'B', 'C'], ['opening'], ['back', 'next', 'direct'])
            blob = fetch(source, receipt.package_id)
        with open_database(offline_path) as night:
            initialize_offline(night)
            local_id = import_package(night, blob)
            foreign_id = import_package(night, foreign)
            local_rows = recover(night, local_id, 'C')
            foreign_rows = {revision: recover(night, foreign_id, revision) for revision in ('A', 'B', 'C')}
            result = audit(night, local_id, 'A', {'G': 1})
        with open_database(offline_path) as night:
            initialize_offline(night)
            fixed = fetch_audit(night, result['audit_id'])
            fixed_c = recover(night, foreign_id, 'C')
        report('valid_publication', {'A': [(*x, 2)], 'B→A': [(*x, 1)],
                                    'B→C': [(*x, -1), (*y, 1)], 'A→C': [(*x, -2), (*y, 1)]},
               ['back', 'direct', 'next'], list(receipt.delta_ids), [(*y, 1)], local_rows,
               ['publication/commit.py', 'publication/reconcile.py', 'offline/recover.py'],
               'A−X gives B=X. B−X+Y and A−2X+Y both give C=Y.')
        report('reverse_recovery', {'file': 'examples/foreign-v1.json', 'revisions': ['A', 'B', 'C']},
               {'A': [(*x, 2)], 'B': [(*x, 1)], 'C': [(*y, 1)]}, foreign_rows, [(*y, 1)], fixed_c,
               ['offline/accept.py', 'offline/recover.py', 'offline/catalog.py'],
               'The independent fixture anchors A at 2X. Undo B→A, then apply B→C.')
        expected_audit = {'package_id': local_id, 'revision': 'A', 'actual': {'G': 2}, 'differences': {'G': 1}}
        report('fixed_audit', {'revision': 'A', 'ledger': {'G': 1}}, expected_audit,
               {key: value for key, value in result.items() if key != 'audit_id'},
               {**expected_audit, 'audit_id': result['audit_id']}, fixed,
               ['audit/reconcile.py', 'audit/comparison.py', 'audit/export.py'],
               'Two occurrences of X have code G. Two actual minus one on the ledger gives one.')


if __name__ == '__main__':
    main()
