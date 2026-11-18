from collections import defaultdict


def count_by_quality_code(rows):
    counts = defaultdict(int)
    for _, _, quality, count in rows:
        counts[quality] += count
    return dict(sorted(counts.items()))
