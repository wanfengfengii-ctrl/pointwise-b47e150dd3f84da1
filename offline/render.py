from inventory.rows import RowCounts, ordered_rows


def render_rows(counts: RowCounts) -> list[tuple[str, str, str, int]]:
    return ordered_rows(counts)
