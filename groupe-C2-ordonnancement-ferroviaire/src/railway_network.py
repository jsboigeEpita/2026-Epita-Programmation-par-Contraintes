"""
railway_network.py
------------------
Data class representing a railway network instance.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class RailwayNetwork:
    """
    Represents a railway network instance.

    Attributes
    ----------
    T : int
        The period of the timetable in minutes (e.g. 60 for a hourly timetable).

    stations : dict[str, int]
        Maps each station name to its number of available platforms (quais).
        Example: {"Paris": 4, "Lyon": 2, "Marseille": 3}

    lines : dict[str, tuple[str, ...]]
        Maps each line name to an ordered tuple of station names representing
        the route of that line (from first to last stop).
        Example: {"L1": ("Paris", "Lyon", "Marseille")}

    connections : list[tuple[str, str, str, int, int]]
        Each element is a 5-tuple:
            (line_a, line_b, station, t_min, t_max)
        representing a required passenger transfer between line_a and line_b
        at the given station, with a transfer time in [t_min, t_max] minutes.
        The pair (line_a, line_b) is ordered: the passenger arrives on line_a
        and departs on line_b.
        Example: [("L1", "L2", "Lyon", 3, 8)]

    segments : dict[frozenset, tuple[int, int, bool]]
        Maps each undirected pair of stations (as a frozenset) to a 3-tuple:
            (t_min, t_max, single_track)
        where t_min and t_max are the minimum and maximum travel times in
        minutes, and single_track is True if the segment has only one track
        (trains in opposite directions cannot be on it simultaneously).
        Example: {frozenset({"Paris", "Lyon"}): (90, 100, True)}

    dwell_time : tuple[int, int]
        A single pair (t_min, t_max) that applies to every train at every
        intermediate station (i.e. not the terminus stops of a line).
        Example: (1, 5)
    """

    T: int
    stations: Dict[str, int]
    lines: Dict[str, Tuple[str, ...]]
    connections: List[Tuple[str, str, str, int, int]]
    segments: Dict[frozenset, Tuple[int, int, bool]]
    dwell_time: Tuple[int, int]

    # ------------------------------------------------------------------ #
    # Convenience helpers used by the solver                               #
    # ------------------------------------------------------------------ #

    def get_segment(self, station_a: str, station_b: str) -> Tuple[int, int, bool]:
        """
        Return the segment data (t_min, t_max, single_track) for the
        undirected pair (station_a, station_b).

        Raises KeyError if the segment does not exist.
        """
        key = frozenset({station_a, station_b})
        return self.segments[key]

    def is_single_track(self, station_a: str, station_b: str) -> bool:
        """Return True if the segment between the two stations is single-track."""
        return self.get_segment(station_a, station_b)[2]

    def intermediate_stations(self, line: str) -> Tuple[str, ...]:
        """Return the stations of a line that are neither the first nor the last."""
        route = self.lines[line]
        return route[1:-1]

    def validate(self) -> None:
        """
        Perform basic consistency checks on the network description.
        Raises ValueError with an explanatory message on the first problem found.
        """
        if self.T <= 0:
            raise ValueError(f"Period T must be positive, got {self.T}.")

        dmin, dmax = self.dwell_time
        if dmin < 0 or dmax < dmin:
            raise ValueError(
                f"Invalid dwell_time {self.dwell_time}: need 0 <= t_min <= t_max."
            )

        for line, route in self.lines.items():
            if len(route) < 2:
                raise ValueError(
                    f"Line '{line}' has fewer than 2 stations: {route}."
                )
            for station in route:
                if station not in self.stations:
                    raise ValueError(
                        f"Station '{station}' used in line '{line}' "
                        f"is not declared in stations."
                    )
            for i in range(len(route) - 1):
                key = frozenset({route[i], route[i + 1]})
                if key not in self.segments:
                    raise ValueError(
                        f"Segment {route[i]!r} -- {route[i+1]!r} used in "
                        f"line '{line}' is not declared in segments."
                    )

        for conn in self.connections:
            line_a, line_b, station, t_min, t_max = conn
            if line_a not in self.lines:
                raise ValueError(f"Connection references unknown line '{line_a}'.")
            if line_b not in self.lines:
                raise ValueError(f"Connection references unknown line '{line_b}'.")
            if station not in self.stations:
                raise ValueError(
                    f"Connection references unknown station '{station}'."
                )
            if station not in self.lines[line_a]:
                raise ValueError(
                    f"Station '{station}' is not on line '{line_a}' "
                    f"(required by connection)."
                )
            if station not in self.lines[line_b]:
                raise ValueError(
                    f"Station '{station}' is not on line '{line_b}' "
                    f"(required by connection)."
                )
            if t_min < 0 or t_max < t_min:
                raise ValueError(
                    f"Invalid connection times [{t_min}, {t_max}] for "
                    f"({line_a}, {line_b}, {station})."
                )

        for key, (t_min, t_max, _) in self.segments.items():
            if t_min < 0 or t_max < t_min:
                raise ValueError(
                    f"Invalid segment times [{t_min}, {t_max}] for segment {key}."
                )


# --------------------------------------------------------------------------- #
# Quick usage example (not part of the solver)                                #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    net = RailwayNetwork(
        T=60,
        stations={
            "A": 2,
            "B": 1,
            "C": 3,
        },
        lines={
            "L1": ("A", "B", "C"),
            "L2": ("C", "B", "A"),
        },
        segments={
            frozenset({"A", "B"}): (15, 20, True),   # voie unique
            frozenset({"B", "C"}): (10, 15, False),  # double voie
        },
        connections=[
            ("L1", "L2", "B", 2, 8),
        ],
        dwell_time=(1, 3),
    )

    net.validate()
    print("Network is valid.")
    print(f"Segment A-B: {net.get_segment('A', 'B')}")
    print(f"Single track A-B: {net.is_single_track('A', 'B')}")
    print(f"Intermediate stations of L1: {net.intermediate_stations('L1')}")
