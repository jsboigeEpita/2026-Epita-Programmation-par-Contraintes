import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from instances import Instance
from solvers import cpsat


@dataclass(frozen=True)
class ParetoPoint:
    n_stations: int
    cycle_time: int
    assignment: dict[int, int]
    optimal: bool
    time_ms: float


@dataclass
class ParetoFront:
    instance_name: str
    points: list[ParetoPoint] = field(default_factory=list)
    total_time_ms: float = 0.0

    @property
    def m_min(self) -> int:
        return min(p.n_stations for p in self.points)

    @property
    def m_max(self) -> int:
        return max(p.n_stations for p in self.points)

    @property
    def cycle_min(self) -> int:
        return min(p.cycle_time for p in self.points)


def compute_pareto_front(
    instance: Instance,
    extra_stations: int = 4,
    time_limit_per_point: float = 10.0,
) -> ParetoFront:
    start = time.perf_counter()
    front = ParetoFront(instance_name=instance.name)

    base = cpsat.solve_salbp1(instance, time_limit=time_limit_per_point)
    if base is None:
        front.total_time_ms = (time.perf_counter() - start) * 1000
        return front

    m_min = base.n_stations
    front.points.append(
        ParetoPoint(
            n_stations=m_min,
            cycle_time=base.cycle_time,
            assignment=dict(base.assignment),
            optimal=base.optimal,
            time_ms=base.time_ms,
        )
    )

    for delta in range(1, extra_stations + 1):
        m = m_min + delta
        sol = cpsat.solve_salbp2(
            instance, n_stations=m, time_limit=time_limit_per_point
        )
        if sol is None:
            continue
        if sol.cycle_time > front.points[-1].cycle_time:
            continue
        front.points.append(
            ParetoPoint(
                n_stations=m,
                cycle_time=sol.cycle_time,
                assignment=dict(sol.assignment),
                optimal=sol.optimal,
                time_ms=sol.time_ms,
            )
        )

    front.total_time_ms = (time.perf_counter() - start) * 1000
    return front


def weighted_sum(
    instance: Instance,
    alpha: float = 1.0,
    beta: float = 0.1,
    time_limit: float = 30.0,
) -> tuple[int, int, dict[int, int], bool, float] | None:
    m_max = len(instance.tasks)
    model = cp_model.CpModel()

    station = {i: model.new_int_var(0, m_max - 1, f"s_{i}") for i in instance.tasks}
    n_stations = model.new_int_var(1, m_max, "n_stations")
    max_load = model.new_int_var(
        max(instance.durations.values()),
        sum(instance.durations.values()),
        "max_load",
    )

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
        model.add(
            sum(instance.durations[i] * assign[i, s] for i in instance.tasks)
            <= max_load
        )

    scale = 100
    alpha_i = int(round(alpha * scale))
    beta_i = int(round(beta * scale))
    model.minimize(alpha_i * n_stations + beta_i * max_load)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    start = time.perf_counter()
    status = solver.solve(model)
    elapsed = (time.perf_counter() - start) * 1000

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    assignment = {i: solver.value(station[i]) for i in instance.tasks}
    return (
        solver.value(n_stations),
        solver.value(max_load),
        assignment,
        status == cp_model.OPTIMAL,
        elapsed,
    )
