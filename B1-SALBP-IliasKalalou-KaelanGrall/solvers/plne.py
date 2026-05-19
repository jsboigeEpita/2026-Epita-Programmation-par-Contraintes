import time

import pulp

from instances import Instance, Solution


def solve_salbp1(instance: Instance, time_limit: float = 30.0) -> Solution | None:
    m_max = len(instance.tasks)
    prob = pulp.LpProblem("SALBP1", pulp.LpMinimize)

    x = {
        (i, s): pulp.LpVariable(f"x_{i}_{s}", cat="Binary")
        for i in instance.tasks
        for s in range(m_max)
    }
    y = {s: pulp.LpVariable(f"y_{s}", cat="Binary") for s in range(m_max)}

    prob += pulp.lpSum(y[s] for s in range(m_max))

    for i in instance.tasks:
        prob += pulp.lpSum(x[i, s] for s in range(m_max)) == 1

    for s in range(m_max):
        prob += (
            pulp.lpSum(instance.durations[i] * x[i, s] for i in instance.tasks)
            <= instance.cycle_time * y[s]
        )

    for i, j in instance.precedences:
        prob += pulp.lpSum(s * x[i, s] for s in range(m_max)) <= pulp.lpSum(
            s * x[j, s] for s in range(m_max)
        )

    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit)
    start = time.perf_counter()
    prob.solve(solver)
    elapsed = (time.perf_counter() - start) * 1000

    if pulp.LpStatus[prob.status] != "Optimal":
        return None

    assignment: dict[int, int] = {}
    for i in instance.tasks:
        for s in range(m_max):
            if pulp.value(x[i, s]) > 0.5:
                assignment[i] = s
                break

    return Solution(
        instance_name=instance.name,
        solver="PLNE",
        variant="SALBP-1",
        assignment=assignment,
        n_stations=int(pulp.value(prob.objective)),
        cycle_time=instance.cycle_time,
        optimal=True,
        time_ms=elapsed,
    )
