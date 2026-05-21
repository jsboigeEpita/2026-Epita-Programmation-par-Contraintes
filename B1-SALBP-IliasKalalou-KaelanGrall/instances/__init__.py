from dataclasses import dataclass


@dataclass(frozen=True)
class Instance:
    name: str
    tasks: list[int]
    durations: dict[int, int]
    precedences: list[tuple[int, int]]
    cycle_time: int


@dataclass
class Solution:
    instance_name: str
    solver: str
    variant: str
    assignment: dict[int, int]
    n_stations: int
    cycle_time: int
    optimal: bool
    time_ms: float

    @property
    def stations(self) -> dict[int, list[int]]:
        result: dict[int, list[int]] = {}
        for task, station in self.assignment.items():
            result.setdefault(station, []).append(task)
        return result

    def station_load(self, station: int, durations: dict[int, int]) -> int:
        return sum(durations[t] for t in self.stations.get(station, []))
