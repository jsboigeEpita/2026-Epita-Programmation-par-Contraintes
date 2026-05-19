"""
railway_solver.py
-----------------
CP-SAT solver for the Railway Timetabling Problem.

Periodic encoding
-----------------
All "difference mod T" constraints are encoded as a single linear equation:

    x_j - x_i - d == -b * T      b in {0, 1},  d in [d_min, d_max]

where b is a BoolVar representing the wrap-around case (x_j < x_i).
This is a single linear constraint — NOT two OnlyEnforceIf implications —
which avoids spurious infeasibility from the implication encoding.
"""

from typing import Dict, Optional, Tuple
from ortools.sat.python import cp_model

from src.railway_network import RailwayNetwork

EventKey = Tuple[str, str, str]   # (line, station, "arr" | "dep")


def _create_event_vars(
    model: cp_model.CpModel,
    network: RailwayNetwork,
) -> Tuple[Dict[Tuple[str, str], cp_model.IntVar],
           Dict[Tuple[str, str], cp_model.IntVar]]:
    arr_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}
    dep_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}

    for line, route in network.lines.items():
        for station in route:
            arr_vars[(line, station)] = model.NewIntVar(
                0, network.T - 1, f"arr_{line}_{station}"
            )
            dep_vars[(line, station)] = model.NewIntVar(
                0, network.T - 1, f"dep_{line}_{station}"
            )

    return arr_vars, dep_vars


def _build_timetable_constraints(
    model: cp_model.CpModel,
    network: RailwayNetwork,
    arr_vars: Dict[Tuple[str, str], cp_model.IntVar],
    dep_vars: Dict[Tuple[str, str], cp_model.IntVar],
) -> None:
    dwell_min, dwell_max = network.dwell_time

    for line, route in network.lines.items():
        for idx, station in enumerate(route):
            arr = arr_vars[(line, station)]
            dep = dep_vars[(line, station)]

            if idx == 0:
                model.Add(arr == dep)
            else:
                model.Add(dep - arr >= dwell_min)
                model.Add(dep - arr <= dwell_max)

    for line, route in network.lines.items():
        for idx in range(len(route) - 1):
            s_from = route[idx]
            s_to = route[idx + 1]
            t_min, t_max, _ = network.get_segment(s_from, s_to)

            _add_periodic_diff(
                model,
                arr_vars[(line, s_to)],
                dep_vars[(line, s_from)],
                t_min, t_max, network.T,
                name=f"travel_{line}_{s_from}_{s_to}",
            )

    for conn in network.connections:
        line_a, line_b, station, t_min, t_max = conn

        _add_periodic_diff(
            model,
            dep_vars[(line_b, station)],
            arr_vars[(line_a, station)],
            t_min, t_max, network.T,
            name=f"transfer_{line_a}_{line_b}_{station}",
        )

    seg_users: Dict[frozenset, list] = {}
    for seg_key, (_, _, single_track) in network.segments.items():
        if single_track:
            seg_users[seg_key] = []

    for line, route in network.lines.items():
        for idx in range(len(route) - 1):
            s_from = route[idx]
            s_to = route[idx + 1]
            key = frozenset({s_from, s_to})
            if key in seg_users:
                t_min, t_max, _ = network.get_segment(s_from, s_to)
                seg_users[key].append((line, dep_vars[(line, s_from)], t_min, t_max))

    for seg_key, users in seg_users.items():
        if len(users) < 2:
            continue

        seg_name = "_".join(sorted(seg_key))
        interval_list = []

        for line, dep_var, t_min, t_max in users:
            duration = model.NewIntVar(t_min, t_max, f"dur_{line}_{seg_name}")

            start1 = model.NewIntVar(0, network.T - 1, f"st1_{line}_{seg_name}")
            end1 = model.NewIntVar(0, 2 * network.T - 1, f"en1_{line}_{seg_name}")
            model.Add(start1 == dep_var)
            iv1 = model.NewIntervalVar(start1, duration, end1,
                                       f"iv1_{line}_{seg_name}")
            interval_list.append(iv1)

            start2 = model.NewIntVar(network.T, 2 * network.T - 1, f"st2_{line}_{seg_name}")
            end2 = model.NewIntVar(network.T, 2 * network.T - 1, f"en2_{line}_{seg_name}")
            model.Add(start2 == dep_var + network.T)
            iv2 = model.NewIntervalVar(start2, duration, end2,
                                       f"iv2_{line}_{seg_name}")
            interval_list.append(iv2)

        model.AddNoOverlap(interval_list)

    for station, n_platforms in network.stations.items():
        station_intervals = []
        station_demands = []

        for line, route in network.lines.items():
            if station not in route:
                continue

            arr = arr_vars[(line, station)]
            dep = dep_vars[(line, station)]

            dur = model.NewIntVar(0, dwell_max, f"stay_dur_{line}_{station}")
            start = model.NewIntVar(0, network.T - 1, f"stay_start_{line}_{station}")
            end = model.NewIntVar(0, network.T - 1 + dwell_max,
                                    f"stay_end_{line}_{station}")

            model.Add(dur == dep - arr)
            model.Add(start == arr)
            model.Add(end == dep)

            iv = model.NewIntervalVar(start, dur, end,
                                      f"iv_stay_{line}_{station}")
            station_intervals.append(iv)
            station_demands.append(1)

        if len(station_intervals) > 1:
            model.AddCumulative(station_intervals, station_demands, n_platforms)


def _add_periodic_min_delay(
    model: cp_model.CpModel,
    x_var: cp_model.IntVar,
    base_time: int,
    min_delay: int,
    T: int,
    name: str,
) -> cp_model.IntVar:
    delay = model.NewIntVar(min_delay, T - 1, f"delay_{name}")
    wrap = model.NewBoolVar(f"wrap_{name}")
    model.Add(x_var - base_time == delay - T * wrap)
    return delay


def _add_periodic_diff(
    model: cp_model.CpModel,
    x_j: cp_model.IntVar,
    x_i: cp_model.IntVar,
    d_min: int,
    d_max: int,
    T: int,
    name: str,
) -> cp_model.IntVar:
    """
    Enforce (x_j - x_i) mod T in [d_min, d_max].
    """
    d = model.NewIntVar(d_min, d_max, f"d_{name}")
    b = model.NewBoolVar(f"b_{name}")
    model.Add(x_j - x_i - d == -T * b)
    return d


def solve(
    network: RailwayNetwork,
    time_limit_seconds: float = 60.0,
) -> Optional[Dict[EventKey, int]]:
    network.validate()

    model = cp_model.CpModel()
    arr_vars, dep_vars = _create_event_vars(model, network)
    _build_timetable_constraints(model, network, arr_vars, dep_vars)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.log_search_progress = True

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"No solution found. Solver status: {solver.StatusName(status)}")
        return None

    solution: Dict[EventKey, int] = {}
    for line, route in network.lines.items():
        for station in route:
            solution[(line, station, "arr")] = solver.Value(arr_vars[(line, station)])
            solution[(line, station, "dep")] = solver.Value(dep_vars[(line, station)])

    return solution


def solve_recovery(
    network: RailwayNetwork,
    base_solution: Dict[EventKey, int],
    delays: Dict[EventKey, int],
    time_limit_seconds: float = 60.0,
) -> Optional[Dict[EventKey, int]]:
    """
    Build and solve a recovery timetable with event delays.

    Parameters
    ----------
    network : RailwayNetwork
        A validated network instance.
    base_solution : dict
        A previously found timetable mapping EventKey to minute [0, T).
    delays : dict
        Mapping of EventKey to minimum delay in minutes.
    time_limit_seconds : float
        Wall-clock time limit for CP-SAT.

    Returns
    -------
    dict mapping EventKey -> int (minute within [0, T)) if feasible, else None.
    """
    network.validate()

    model = cp_model.CpModel()
    arr_vars, dep_vars = _create_event_vars(model, network)
    _build_timetable_constraints(model, network, arr_vars, dep_vars)

    delay_vars = []
    for event_key, min_delay in delays.items():
        if min_delay <= 0:
            continue

        if event_key not in base_solution:
            raise ValueError(f"Unknown perturbation event {event_key}")

        line, station, kind = event_key
        if kind == "arr":
            x_var = arr_vars[(line, station)]
        elif kind == "dep":
            x_var = dep_vars[(line, station)]
        else:
            raise ValueError(f"Invalid event kind {kind!r}, expected 'arr' or 'dep'.")

        if min_delay >= network.T:
            raise ValueError(
                f"Delay {min_delay} is too large for period {network.T}. "
                "Use a smaller delay or increase T."
            )

        delay_vars.append(
            _add_periodic_min_delay(
                model,
                x_var,
                base_solution[event_key],
                min_delay,
                network.T,
                name=f"recovery_{line}_{station}_{kind}",
            )
        )

    if delay_vars:
        model.Minimize(sum(delay_vars))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.log_search_progress = True

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"No recovery solution found. Solver status: {solver.StatusName(status)}")
        return None

    solution: Dict[EventKey, int] = {}
    for line, route in network.lines.items():
        for station in route:
            solution[(line, station, "arr")] = solver.Value(arr_vars[(line, station)])
            solution[(line, station, "dep")] = solver.Value(dep_vars[(line, station)])

    return solution


# --------------------------------------------------------------------------- #
# Smoke test                                                                   #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    from src.railway_network import RailwayNetwork
    from collections import defaultdict

    net = RailwayNetwork(
        T=60,
        stations={"A": 2, "B": 1, "C": 3},
        lines={
            "L1": ("A", "B", "C"),
            "L2": ("C", "B", "A"),
        },
        segments={
            frozenset({"A", "B"}): (15, 20, True),
            frozenset({"B", "C"}): (10, 15, False),
        },
        connections=[("L1", "L2", "B", 2, 8)],
        dwell_time=(1, 3),
    )

    result = solve(net, time_limit_seconds=30.0)

    if result:
        print("\nTimetable solution:")
        by_line: dict = defaultdict(dict)
        for (line, station, ev), t in result.items():
            by_line[line][(station, ev)] = t
        for line, route in net.lines.items():
            print(f"  {line}: {' -> '.join(net.lines[line])}")
            for station in net.lines[line]:
                arr = by_line[line].get((station, "arr"), "?")
                dep = by_line[line].get((station, "dep"), "?")
                print(f"    {station:6s}  arr={arr:>3}  dep={dep:>3}")
    else:
        print("No feasible timetable found.")