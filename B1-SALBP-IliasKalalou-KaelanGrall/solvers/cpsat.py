import time

from ortools.sat.python import cp_model

from instances import Instance, Solution


def solve_salbp1(instance: Instance, time_limit: float = 30.0) -> Solution | None:
    m_max = len(instance.tasks)
    model = cp_model.CpModel()

    station = {i: model.new_int_var(0, m_max - 1, f"s_{i}") for i in instance.tasks}
    n_stations = model.new_int_var(1, m_max, "n_stations")

    for i, j in instance.precedences:
        model.add(station[i] <= station[j])

    for i in instance.tasks:
        model.add(station[i] < n_stations)

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

    for s in range(m_max):
        model.add(
            sum(instance.durations[i] * assign[i, s] for i in instance.tasks)
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
    return Solution(
        instance_name=instance.name,
        solver="CP-SAT",
        variant="SALBP-1",
        assignment=assignment,
        n_stations=solver.value(n_stations),
        cycle_time=instance.cycle_time,
        optimal=status == cp_model.OPTIMAL,
        time_ms=elapsed,
    )


def solve_salbp2(instance: Instance, n_stations: int, time_limit: float = 30.0) -> Solution | None:
    model = cp_model.CpModel()

    station = {i: model.new_int_var(0, n_stations - 1, f"s_{i}") for i in instance.tasks}
    cycle_var = model.new_int_var(
        max(instance.durations.values()),
        sum(instance.durations.values()),
        "cycle",
    )

    for i, j in instance.precedences:
        model.add(station[i] <= station[j])

    assign = {
        (i, s): model.new_bool_var(f"a_{i}_{s}")
        for i in instance.tasks
        for s in range(n_stations)
    }
    for i in instance.tasks:
        model.add_exactly_one(assign[i, s] for s in range(n_stations))
        for s in range(n_stations):
            model.add(station[i] == s).only_enforce_if(assign[i, s])
            model.add(station[i] != s).only_enforce_if(assign[i, s].Not())

    for s in range(n_stations):
        model.add(
            sum(instance.durations[i] * assign[i, s] for i in instance.tasks)
            <= cycle_var
        )

    model.minimize(cycle_var)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    start = time.perf_counter()
    status = solver.solve(model)
    elapsed = (time.perf_counter() - start) * 1000

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    assignment = {i: solver.value(station[i]) for i in instance.tasks}
    return Solution(
        instance_name=instance.name,
        solver="CP-SAT",
        variant="SALBP-2",
        assignment=assignment,
        n_stations=n_stations,
        cycle_time=solver.value(cycle_var),
        optimal=status == cp_model.OPTIMAL,
        time_ms=elapsed,
    )
