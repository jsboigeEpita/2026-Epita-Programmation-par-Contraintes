import time
from dataclasses import dataclass

from ortools.sat.python import cp_model

from instances.multimodel import MultiModelInstance


@dataclass
class MultiModelSolution:
    instance_name: str
    n_stations: int
    cycle_time: int
    assignment: dict[int, int]
    optimal: bool
    time_ms: float
    cycle_per_model: dict[str, int]

    @property
    def stations(self) -> dict[int, list[int]]:
        result: dict[int, list[int]] = {}
        for task, station in self.assignment.items():
            result.setdefault(station, []).append(task)
        return result


def solve_mmalbp(instance: MultiModelInstance, time_limit: float = 30.0) -> MultiModelSolution | None:
    m_max = len(instance.tasks)
    model = cp_model.CpModel()

    station = {i: model.new_int_var(0, m_max - 1, f"s_{i}") for i in instance.tasks}
    n_stations = model.new_int_var(1, m_max, "n_stations")

    assign = {
        (i, s): model.new_bool_var(f"a_{i}_{s}")
        for i in instance.tasks
        for s in range(m_max)
    }
    for i in instance.tasks:
        model.add_exactly_one(assign[i, s] for s in range(m_max))
        for s in range(m_max):
            model.add(station[i] == s).only_enforce_if(assign[i, s])
            model.add(station[i] != s).only_enforce_if(assign[i, s].Not())

    for i in instance.tasks:
        model.add(station[i] < n_stations)

    for prec_list in instance.precedences.values():
        for i, j in prec_list:
            model.add(station[i] <= station[j])

    for m_name in instance.models:
        durations_m = instance.durations[m_name]
        for s in range(m_max):
            model.add(
                sum(durations_m.get(i, 0) * assign[i, s] for i in instance.tasks)
                <= instance.cycle_time
            )

    model.minimize(n_stations)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    start = time.perf_counter()
    status = solver.solve(model)
    elapsed = (time.perf_counter() - start) * 1000

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    assignment = {i: solver.value(station[i]) for i in instance.tasks}
    n_stat = solver.value(n_stations)

    cycle_per_model: dict[str, int] = {}
    for m_name in instance.models:
        durations_m = instance.durations[m_name]
        max_load = 0
        for s in range(n_stat):
            load = sum(durations_m.get(i, 0) for i, st in assignment.items() if st == s)
            max_load = max(max_load, load)
        cycle_per_model[m_name] = max_load

    return MultiModelSolution(
        instance_name=instance.name,
        n_stations=n_stat,
        cycle_time=instance.cycle_time,
        assignment=assignment,
        optimal=status == cp_model.OPTIMAL,
        time_ms=elapsed,
        cycle_per_model=cycle_per_model,
    )
