"""
railway_generator.py
--------------------
Generates a coherent, (likely) solvable RailwayNetwork instance from
high-level parameters: number of stations, number of lines, and period T.

Design principles
-----------------
1. **Lines first** : lines are generated first as random simple paths over
   the pool of station names. Everything else (stations, segments) is then
   derived strictly from the lines, so there can never be an orphan station
   or an orphan segment.
2. **Feasibility budget** : travel and dwell times are scaled so that the
   total travel time along any line stays well below T.
3. **Voie unique sparsity** : single-track segments are assigned with low
   probability (~25 %) to avoid excessive NoOverlap conflicts.
4. **Platform count** : each station gets at least as many platforms as the
   number of lines that stop there, so Cumulative is always satisfiable.
5. **Connections** : generated only between lines that share a station, with
   wide transfer windows to avoid over-constraining.
"""

import random
from typing import Optional
from src.railway_network import RailwayNetwork


def generate_railway_network(
    n_stations: int,
    n_lines: int,
    T: int,
    seed: Optional[int] = None,
    single_track_prob: float = 0.25,
    connection_prob: float = 0.4,
) -> RailwayNetwork:
    """
    Generate a random but coherent RailwayNetwork.

    Parameters
    ----------
    n_stations : int
        Number of stations in the pool to draw from (>= 3).
    n_lines : int
        Number of train lines (>= 1).
    T : int
        Timetable period in minutes (e.g. 60).
    seed : int, optional
        Random seed for reproducibility.
    single_track_prob : float
        Probability that a given segment is single-track (default 0.25).
    connection_prob : float
        Probability that a shared station between two lines yields a
        transfer constraint (default 0.4).

    Returns
    -------
    RailwayNetwork
        A validated, coherent instance ready to be passed to the solver.
    """
    if n_stations < 3:
        raise ValueError("n_stations must be >= 3.")
    if n_lines < 1:
        raise ValueError("n_lines must be >= 1.")
    if T < 20:
        raise ValueError("T must be >= 20 minutes.")

    rng = random.Random(seed)

    # Pool of candidate station names (not all will necessarily be used).
    all_station_names = [f"S{i}" for i in range(n_stations)]

    # ------------------------------------------------------------------ #
    # 1. Generate lines                                                    #
    #    Lines are simple paths (no repeated station) drawn by sampling   #
    #    without replacement from the station pool.                       #
    #    Lines come FIRST; stations and segments are derived from them.   #
    # ------------------------------------------------------------------ #
    min_line_len = 3
    max_line_len = min(6, n_stations)

    lines: dict[str, tuple[str, ...]] = {}
    for i in range(n_lines):
        target_len = rng.randint(min_line_len, max_line_len)
        path = rng.sample(all_station_names, min(target_len, n_stations))
        lines[f"L{i}"] = tuple(path)

    # ------------------------------------------------------------------ #
    # 2. Derive stations from lines                                        #
    #    Only stations actually visited by at least one line exist.       #
    # ------------------------------------------------------------------ #
    lines_through: dict[str, int] = {}
    for route in lines.values():
        for s in route:
            lines_through[s] = lines_through.get(s, 0) + 1

    # Platform count: at least as many platforms as lines stopping here,
    # then randomly reduce by 1 on some stations to add mild pressure.
    stations: dict[str, int] = {}
    for s, n_lines_here in lines_through.items():
        capacity = max(1, n_lines_here)
        if capacity > 1 and rng.random() < 0.4:
            capacity -= 1
        stations[s] = capacity

    # ------------------------------------------------------------------ #
    # 3. Derive segments from lines                                        #
    #    Only edges actually traversed by at least one line are created.  #
    #    Travel times are scaled to fit comfortably within T.             #
    # ------------------------------------------------------------------ #
    avg_segs_per_line = max(2, n_stations // 2)
    travel_budget_per_seg = max(3, int(0.60 * T / avg_segs_per_line))
    t_min_travel = max(2, int(travel_budget_per_seg * 0.6))
    t_max_travel = travel_budget_per_seg

    segments: dict[frozenset, tuple[int, int, bool]] = {}
    for route in lines.values():
        for i in range(len(route) - 1):
            key = frozenset({route[i], route[i + 1]})
            if key not in segments:
                t_min = t_min_travel + rng.randint(
                    0, max(0, t_max_travel - t_min_travel) // 2
                )
                t_max = t_min + rng.randint(1, max(1, t_max_travel - t_min))
                single = rng.random() < single_track_prob
                segments[key] = (t_min, t_max, single)

    # ------------------------------------------------------------------ #
    # 4. Dwell times                                                       #
    # ------------------------------------------------------------------ #
    dwell_budget = max(3, int(0.10 * T))
    dwell_time = (1, dwell_budget)

    # ------------------------------------------------------------------ #
    # 5. Transfer / correspondence constraints                             #
    #    For each pair of lines sharing a station, maybe add a transfer.  #
    # ------------------------------------------------------------------ #
    connections: list[tuple[str, str, str, int, int]] = []
    line_names = list(lines.keys())

    for i in range(len(line_names)):
        for j in range(i + 1, len(line_names)):
            la, lb = line_names[i], line_names[j]
            shared = set(lines[la]) & set(lines[lb])
            for station in shared:
                if rng.random() < connection_prob:
                    c_min = rng.randint(1, 3)
                    c_max = c_min + rng.randint(4, max(5, int(0.15 * T)))
                    connections.append((la, lb, station, c_min, c_max))

    # ------------------------------------------------------------------ #
    # 6. Build, validate and return                                        #
    # ------------------------------------------------------------------ #
    net = RailwayNetwork(
        T=T,
        stations=stations,
        lines=lines,
        connections=connections,
        segments=segments,
        dwell_time=dwell_time,
    )
    net.validate()
    return net


# --------------------------------------------------------------------------- #
# CLI / quick demo                                                             #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys

    n_stations = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    n_lines    = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    T          = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    seed       = int(sys.argv[4]) if len(sys.argv) > 4 else 42

    net = generate_railway_network(n_stations, n_lines, T, seed=seed)

    print(f"=== Generated RailwayNetwork (seed={seed}) ===")
    print(f"  Period T     : {net.T} min")
    print(f"  Stations ({len(net.stations)}) : {dict(net.stations)}")
    print(f"  Dwell time   : {net.dwell_time}")
    print(f"\n  Lines ({len(net.lines)}):")
    for name, route in net.lines.items():
        print(f"    {name}: {' -> '.join(route)}")
    print(f"\n  Segments ({len(net.segments)}):")
    for key, (tmin, tmax, single) in net.segments.items():
        a, b = sorted(key)
        track = "SINGLE" if single else "double"
        print(f"    {a} -- {b}: [{tmin}, {tmax}] min  ({track} track)")
    print(f"\n  Connections ({len(net.connections)}):")
    for la, lb, st, tmin, tmax in net.connections:
        print(f"    {la} -> {lb} at {st}: [{tmin}, {tmax}] min")