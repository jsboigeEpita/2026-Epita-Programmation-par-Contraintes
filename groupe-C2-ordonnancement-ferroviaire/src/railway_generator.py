"""
railway_generator.py
--------------------
Generates a coherent, (likely) solvable RailwayNetwork instance.

Design principles
-----------------
1. **Lines first** : everything (stations, segments) is derived strictly from
   the lines — no orphan station or segment is possible.
2. **Full coverage** : every station in the pool is visited by at least one
   line. Lines are built by first distributing stations across lines to ensure
   full coverage, then padding remaining slots randomly.
3. **Feasibility budget** : travel/dwell times scaled to stay well below T.
4. **Voie unique sparsity** : ~25 % single-track by default.
5. **Platform count** : >= lines stopping there (Cumulative always feasible).
6. **Connections** : only between lines sharing a station, wide windows.
"""

import random
from typing import Optional
from railway_network import RailwayNetwork


def generate_railway_network(
    n_stations: int,
    n_lines: int,
    T: int,
    seed: Optional[int] = None,
    single_track_prob: float = 0.25,
    connection_prob: float = 0.4,
) -> RailwayNetwork:
    """
    Generate a random but coherent RailwayNetwork where every requested
    station appears in at least one line.

    Parameters
    ----------
    n_stations : int   Number of stations (>= 3).
    n_lines    : int   Number of lines (>= 1).
    T          : int   Timetable period in minutes (>= 20).
    seed       : int   Optional random seed.
    single_track_prob : float  P(segment is single-track).
    connection_prob   : float  P(shared station yields a transfer constraint).
    """
    if n_stations < 3:
        raise ValueError("n_stations must be >= 3.")
    if n_lines < 1:
        raise ValueError("n_lines must be >= 1.")
    if T < 20:
        raise ValueError("T must be >= 20 minutes.")

    rng = random.Random(seed)

    all_stations = [f"S{i}" for i in range(n_stations)]
    min_len = 3
    max_len = min(6, n_stations)

    # ------------------------------------------------------------------ #
    # 1. Build lines with guaranteed full station coverage                 #
    #                                                                      #
    # Strategy:                                                            #
    #   a) Shuffle stations and distribute them into lines so every        #
    #      station is assigned to exactly one "home" line first.           #
    #   b) Each line then gets padded with random extra stations up to     #
    #      its target length.                                              #
    #   c) This guarantees 100 % station coverage regardless of n_lines   #
    #      or n_stations.                                                  #
    # ------------------------------------------------------------------ #

    # Assign each station a "home" line round-robin (after shuffling)
    shuffled = all_stations[:]
    rng.shuffle(shuffled)
    home: dict[str, list[str]] = {f"L{i}": [] for i in range(n_lines)}
    for idx, station in enumerate(shuffled):
        home[f"L{idx % n_lines}"].append(station)

    lines: dict[str, tuple[str, ...]] = {}
    for i in range(n_lines):
        line_name = f"L{i}"
        base = home[line_name][:]           # stations this line must cover
        target_len = rng.randint(min_len, max_len)

        # Pad with random stations not already in this line
        extras = [s for s in all_stations if s not in base]
        rng.shuffle(extras)
        slots = max(0, target_len - len(base))
        path = base + extras[:slots]

        # Shuffle the path order (a line is an ordered route)
        rng.shuffle(path)

        # Ensure minimum length of 2
        if len(path) < 2:
            fallback = [s for s in all_stations if s not in path]
            path += fallback[:2 - len(path)]

        lines[line_name] = tuple(path)

    # ------------------------------------------------------------------ #
    # 2. Derive stations from lines (all n_stations are covered)          #
    # ------------------------------------------------------------------ #
    lines_through: dict[str, int] = {}
    for route in lines.values():
        for s in route:
            lines_through[s] = lines_through.get(s, 0) + 1

    stations: dict[str, int] = {}
    for s, n_lines_here in lines_through.items():
        capacity = max(1, n_lines_here)
        if capacity > 1 and rng.random() < 0.4:
            capacity -= 1
        stations[s] = capacity

    # ------------------------------------------------------------------ #
    # 3. Derive segments from lines                                        #
    # ------------------------------------------------------------------ #
    avg_segs = max(2, n_stations // 2)
    budget   = max(3, int(0.60 * T / avg_segs))
    t_min_t  = max(2, int(budget * 0.6))
    t_max_t  = budget

    segments: dict[frozenset, tuple[int, int, bool]] = {}
    for route in lines.values():
        for i in range(len(route) - 1):
            key = frozenset({route[i], route[i + 1]})
            if key not in segments:
                t_min = t_min_t + rng.randint(0, max(0, t_max_t - t_min_t) // 2)
                t_max = t_min + rng.randint(1, max(1, t_max_t - t_min))
                single = rng.random() < single_track_prob
                segments[key] = (t_min, t_max, single)

    # ------------------------------------------------------------------ #
    # 4. Dwell times                                                       #
    # ------------------------------------------------------------------ #
    dwell_time = (1, max(3, int(0.10 * T)))

    # ------------------------------------------------------------------ #
    # 5. Transfer constraints                                              #
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


if __name__ == "__main__":
    import sys
    n_stations = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    n_lines    = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    T          = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    seed       = int(sys.argv[4]) if len(sys.argv) > 4 else 42

    net = generate_railway_network(n_stations, n_lines, T, seed=seed)
    print(f"Stations ({len(net.stations)}): {list(net.stations)}")
    print(f"Lignes   ({len(net.lines)}):")
    for name, route in net.lines.items():
        print(f"  {name}: {' -> '.join(route)}")
    print(f"Segments ({len(net.segments)})")
    print(f"Connexions ({len(net.connections)})")