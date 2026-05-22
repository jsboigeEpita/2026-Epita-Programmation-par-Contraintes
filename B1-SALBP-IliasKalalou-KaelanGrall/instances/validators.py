import networkx as nx

from . import Instance


class InstanceValidationError(ValueError):
    pass


def validate_precedences(
    n_tasks: int,
    precedences: list[tuple[int, int]],
) -> tuple[list[tuple[int, int]], list[str]]:
    cleaned: list[tuple[int, int]] = []
    warnings: list[str] = []
    seen: set[tuple[int, int]] = set()

    for a, b in precedences:
        if not (0 <= a < n_tasks and 0 <= b < n_tasks):
            warnings.append(f"Precedence hors plage ignoree : ({a}, {b})")
            continue
        if a == b:
            warnings.append(f"Precedence auto-referente ignoree : ({a}, {b})")
            continue
        if (a, b) in seen:
            warnings.append(f"Precedence dupliquee ignoree : ({a}, {b})")
            continue
        seen.add((a, b))
        cleaned.append((a, b))

    graph = nx.DiGraph()
    graph.add_nodes_from(range(n_tasks))
    graph.add_edges_from(cleaned)
    try:
        cycle = nx.find_cycle(graph, orientation="original")
        edges = " -> ".join(f"{u}" for u, _, _ in cycle) + f" -> {cycle[0][0]}"
        raise InstanceValidationError(f"Cycle detecte dans les precedences : {edges}")
    except nx.NetworkXNoCycle:
        pass

    return cleaned, warnings


def validate_instance(instance: Instance) -> list[str]:
    warnings: list[str] = []
    if instance.cycle_time <= 0:
        raise InstanceValidationError(f"Cycle time doit etre positif (recu {instance.cycle_time}).")

    max_dur = max(instance.durations.values()) if instance.durations else 0
    if max_dur > instance.cycle_time:
        raise InstanceValidationError(
            f"Une tache dure {max_dur}, superieur au cycle time {instance.cycle_time} : "
            "instance infaisable."
        )

    missing = [t for t in instance.tasks if t not in instance.durations]
    if missing:
        raise InstanceValidationError(f"Durees manquantes pour : {missing}")

    return warnings
