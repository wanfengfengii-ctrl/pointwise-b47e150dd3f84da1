from inventory.rows import RowCounts, ordered_rows
from publication.package import PackageEvidence
from storage import EvidenceError


def solve_accounts(evidence: PackageEvidence) -> dict[str, RowCounts]:
    """Assign the unique nonnegative row account of every declared revision.

    The selected inventories are fixed accounts and each delta states an
    equation: account(source) + changes == account(target). All revisions
    have to belong to a component anchored by a formal inventory, every
    equation has to hold, and every resulting row multiplicity has to be a
    nonnegative integer. Ordering of evidence and equivalent reversed
    representations produce the same accounts.
    """
    adjacency: dict[str, list] = {revision: [] for revision in evidence.revisions}
    for delta in evidence.deltas:
        adjacency[delta.source].append(delta)
        adjacency[delta.target].append(delta)

    anchors: dict[str, RowCounts] = {}
    for inventory in evidence.inventories:
        rows = dict(inventory.rows)
        if inventory.revision in anchors and anchors[inventory.revision] != rows:
            raise EvidenceError(
                f"inventories disagree on revision {inventory.revision!r}")
        anchors[inventory.revision] = rows

    accounts: dict[str, RowCounts] = {}
    for start in evidence.revisions:
        if start in accounts:
            continue
        component = [start]
        component_deltas = []
        delta_ids: set[int] = set()
        pending = [start]
        seen = {start}
        while pending:
            current = pending.pop()
            for delta in adjacency[current]:
                if id(delta) not in delta_ids:
                    delta_ids.add(id(delta))
                    component_deltas.append(delta)
                neighbor = delta.target if delta.source == current else delta.source
                if neighbor not in seen:
                    seen.add(neighbor)
                    component.append(neighbor)
                    pending.append(neighbor)

        anchored = next((revision for revision in component if revision in anchors), None)
        if anchored is None:
            names = ", ".join(sorted(component))
            raise EvidenceError(f"revisions without an inventory: {names}")

        component_accounts: dict[str, RowCounts] = {anchored: dict(anchors[anchored])}
        pending = [anchored]
        while pending:
            current = pending.pop()
            for delta in adjacency[current]:
                if delta.source == current:
                    neighbor, sign = delta.target, 1
                else:
                    neighbor, sign = delta.source, -1
                if neighbor in component_accounts:
                    continue
                derived: RowCounts = {}
                for key in set(component_accounts[current]) | set(delta.changes):
                    value = component_accounts[current].get(key, 0) + sign * delta.changes.get(key, 0)
                    if value:
                        derived[key] = value
                component_accounts[neighbor] = derived
                pending.append(neighbor)

        # The spanning tree gives candidate accounts; verify every equation,
        # including cycle-closing edges that describe an alternative route.
        for delta in component_deltas:
            expected: RowCounts = {}
            for key in set(component_accounts[delta.source]) | set(delta.changes):
                value = component_accounts[delta.source].get(key, 0) + delta.changes.get(key, 0)
                if value:
                    expected[key] = value
            if expected != component_accounts[delta.target]:
                raise EvidenceError(
                    f"delta {delta.delta_id!r} contradicts the other evidence "
                    f"between {delta.source!r} and {delta.target!r}")

        for revision in component:
            if any(count < 0 for count in component_accounts[revision].values()):
                raise EvidenceError(f"negative row count at revision {revision!r}")
            if revision in anchors and component_accounts[revision] != anchors[revision]:
                raise EvidenceError(
                    f"inventories and deltas disagree on revision {revision!r}")
        accounts.update(component_accounts)

    return accounts


def reconcile_evidence(evidence: PackageEvidence) -> None:
    """Establish one common nonnegative account for every selected revision."""
    solve_accounts(evidence)


def recover_account(evidence: PackageEvidence, revision: str) -> list:
    """Read back the full rows of one revision with their exact multiplicity."""
    return ordered_rows(solve_accounts(evidence)[revision])
