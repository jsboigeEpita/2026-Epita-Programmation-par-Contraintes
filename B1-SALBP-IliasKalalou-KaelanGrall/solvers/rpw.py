import time

import networkx as nx

from instances import Instance, Solution


def compute_rpw(instance: Instance) -> dict[int, int]:
    graph = nx.DiGraph()
    graph.add_nodes_from(instance.tasks)
    graph.add_edges_from(instance.precedences)

    rpw: dict[int, int] = {}
    for task in instance.tasks:
        successors = nx.descendants(graph, task)
        rpw[task] = instance.durations[task] + sum(
            instance.durations[s] for s in successors
        )
    return rpw


def solve_salbp1(instance: Instance) -> Solution:
    start = time.perf_counter()

    rpw = compute_rpw(instance)
    order = sorted(instance.tasks, key=lambda i: -rpw[i])

    predecessors: dict[int, set[int]] = {i: set() for i in instance.tasks}
    for a, b in instance.precedences:
        predecessors[b].add(a)

    assignment: dict[int, int] = {}
    loads: list[int] = []

    for task in order:
        min_station = max(
            (assignment[p] for p in predecessors[task] if p in assignment),
            default=-1,
        ) + 1
        placed = False
        for s in range(min_station, len(loads)):
            if loads[s] + instance.durations[task] <= instance.cycle_time:
                assignment[task] = s
                loads[s] += instance.durations[task]
                placed = True
                break
        if not placed:
            assignment[task] = len(loads)
            loads.append(instance.durations[task])

    elapsed = (time.perf_counter() - start) * 1000

    return Solution(
        instance_name=instance.name,
        solver="RPW",
        variant="SALBP-1",
        assignment=assignment,
        n_stations=len(loads),
        cycle_time=instance.cycle_time,
        optimal=False,
        time_ms=elapsed,
    )
