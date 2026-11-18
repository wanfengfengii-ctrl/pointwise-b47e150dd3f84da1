from offline.catalog import save_received_package
from publication.package import decode_package
from storage import atomic


def import_package(db, blob: bytes):
    decode_package(blob)
    with atomic(db):
        return save_received_package(db, blob)
