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
    Enforce  (x_j - x_i) mod T  in  [d_min, d_max].

    Encoded as the single linear constraint:
        x_j - x_i - d == -b * T
    with d in [d_min, d_max] and b in {0, 1}.

    b == 0  =>  x_j - x_i == d          (no wrap-around)
    b == 1  =>  x_j - x_i + T == d      (wrap-around: x_j < x_i)

    Returns d (the auxiliary difference variable).
    """
    d = model.NewIntVar(d_min, d_max, f"d_{name}")
    b = model.NewBoolVar(f"b_{name}")
    # x_j - x_i - d = -b * T
    model.Add(x_j - x_i - d == -T * b)
    return d


def solve(
    network: RailwayNetwork,
    time_limit_seconds: float = 60.0,
) -> Optional[Dict[EventKey, int]]:
    """
    Build and solve the railway timetabling model.

    Parameters
    ----------
    network : RailwayNetwork
        A validated network instance.
    time_limit_seconds : float
        Wall-clock time limit given to CP-SAT.

    Returns
    -------
    dict mapping EventKey -> int (minute within [0, T))
        if a feasible solution is found, else None.
    """
    network.validate()

    model = cp_model.CpModel()
    T = network.T

    # ------------------------------------------------------------------ #
    # 1. Decision variables                                                #
    #    arr_vars[(line, station)] : arrival   time in [0, T)             #
    #    dep_vars[(line, station)] : departure time in [0, T)             #
    # ------------------------------------------------------------------ #

    arr_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}
    dep_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}

    for line, route in network.lines.items():
        for station in route:
            arr_vars[(line, station)] = model.NewIntVar(
                0, T - 1, f"arr_{line}_{station}"
            )
            dep_vars[(line, station)] = model.NewIntVar(
                0, T - 1, f"dep_{line}_{station}"
            )

    # ------------------------------------------------------------------ #
    # 2. Dwell-time constraints                                            #
    #    dep - arr  in  [dwell_min, dwell_max]  (plain, no wrap-around)  #
    #    First stop: arr == dep (no incoming journey)                     #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # 3. Travel-time constraints                                           #
    #    (arr[s_{i+1}] - dep[s_i]) mod T  in  [t_min, t_max]             #
    # ------------------------------------------------------------------ #

    for line, route in network.lines.items():
        for idx in range(len(route) - 1):
            s_from = route[idx]
            s_to   = route[idx + 1]
            t_min, t_max, _ = network.get_segment(s_from, s_to)

            _add_periodic_diff(
                model,
                arr_vars[(line, s_to)],
                dep_vars[(line, s_from)],
                t_min, t_max, T,
                name=f"travel_{line}_{s_from}_{s_to}",
            )

    # ------------------------------------------------------------------ #
    # 4. Transfer / correspondence constraints                             #
    #    (dep[line_b, sta] - arr[line_a, sta]) mod T  in  [t_min, t_max] #
    # ------------------------------------------------------------------ #

    for conn in network.connections:
        line_a, line_b, station, t_min, t_max = conn

        _add_periodic_diff(
            model,
            dep_vars[(line_b, station)],
            arr_vars[(line_a, station)],
            t_min, t_max, T,
            name=f"transfer_{line_a}_{line_b}_{station}",
        )

    # ------------------------------------------------------------------ #
    # 5. Single-track constraints (NoOverlap)                             #
    #    Two trains on a single-track segment cannot occupy it at the     #
    #    same time.                                                        #
    #                                                                      #
    #    We work in [0, 2T): each train's occupation gets two IntervalVar #
    #    copies (original and shifted by T) to capture wrap-around        #
    #    conflicts between trains that straddle the period boundary.       #
    # ------------------------------------------------------------------ #

    seg_users: Dict[frozenset, list] = {}
    for seg_key, (_, _, single_track) in network.segments.items():
        if single_track:
            seg_users[seg_key] = []

    for line, route in network.lines.items():
        for idx in range(len(route) - 1):
            s_from = route[idx]
            s_to   = route[idx + 1]
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

            # Original copy: start == dep_var, in [0, T)
            start1 = model.NewIntVar(0, T - 1, f"st1_{line}_{seg_name}")
            end1   = model.NewIntVar(0, 2 * T - 1, f"en1_{line}_{seg_name}")
            model.Add(start1 == dep_var)
            iv1 = model.NewIntervalVar(start1, duration, end1,
                                       f"iv1_{line}_{seg_name}")
            interval_list.append(iv1)

            # Shifted copy: start == dep_var + T, in [T, 2T)
            start2 = model.NewIntVar(T, 2 * T - 1, f"st2_{line}_{seg_name}")
            end2   = model.NewIntVar(T, 2 * T - 1, f"en2_{line}_{seg_name}")
            model.Add(start2 == dep_var + T)
            iv2 = model.NewIntervalVar(start2, duration, end2,
                                       f"iv2_{line}_{seg_name}")
            interval_list.append(iv2)

        model.AddNoOverlap(interval_list)

    # ------------------------------------------------------------------ #
    # 6. Multi-platform constraints (Cumulative)                           #
    #    Simultaneous train occupancy at a station <= n_platforms.         #
    #    Stay interval = [arr, dep], no wrap-around (dep >= arr always).  #
    # ------------------------------------------------------------------ #

    for station, n_platforms in network.stations.items():
        station_intervals = []
        station_demands   = []

        for line, route in network.lines.items():
            if station not in route:
                continue

            arr = arr_vars[(line, station)]
            dep = dep_vars[(line, station)]

            dur   = model.NewIntVar(0, dwell_max, f"stay_dur_{line}_{station}")
            start = model.NewIntVar(0, T - 1, f"stay_start_{line}_{station}")
            end   = model.NewIntVar(0, T - 1 + dwell_max,
                                    f"stay_end_{line}_{station}")

            model.Add(dur   == dep - arr)
            model.Add(start == arr)
            model.Add(end   == dep)

            iv = model.NewIntervalVar(start, dur, end,
                                      f"iv_stay_{line}_{station}")
            station_intervals.append(iv)
            station_demands.append(1)

        if len(station_intervals) > 1:
            model.AddCumulative(station_intervals, station_demands, n_platforms)

    # ------------------------------------------------------------------ #
    # 7. Solve                                                             #
    # ------------------------------------------------------------------ #

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.log_search_progress = True

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"No solution found. Solver status: {solver.StatusName(status)}")
        return None

    # ------------------------------------------------------------------ #
    # 8. Extract solution                                                  #
    # ------------------------------------------------------------------ #

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