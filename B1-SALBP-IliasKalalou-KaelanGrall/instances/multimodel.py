from dataclasses import dataclass

from . import Instance


@dataclass(frozen=True)
class MultiModelInstance:
    name: str
    models: list[str]
    tasks: list[int]
    durations: dict[str, dict[int, int]]
    precedences: dict[str, list[tuple[int, int]]]
    cycle_time: int
    demand: dict[str, float]

    def average_durations(self) -> dict[int, int]:
        total = sum(self.demand.values()) or 1.0
        avg: dict[int, float] = {t: 0.0 for t in self.tasks}
        for model in self.models:
            weight = self.demand.get(model, 0.0) / total
            for t in self.tasks:
                avg[t] += weight * self.durations[model].get(t, 0)
        return {t: int(round(v)) for t, v in avg.items()}

    def max_durations(self) -> dict[int, int]:
        result: dict[int, int] = {t: 0 for t in self.tasks}
        for model in self.models:
            for t in self.tasks:
                result[t] = max(result[t], self.durations[model].get(t, 0))
        return result

    def union_precedences(self) -> list[tuple[int, int]]:
        seen: set[tuple[int, int]] = set()
        for model in self.models:
            for a, b in self.precedences.get(model, []):
                seen.add((a, b))
        return sorted(seen)


def two_model_toy() -> MultiModelInstance:
    tasks = list(range(11))
    return MultiModelInstance(
        name="multimodel-toy",
        models=["A", "B"],
        tasks=tasks,
        durations={
            "A": {0: 6, 1: 5, 2: 4, 3: 5, 4: 3, 5: 6, 6: 4, 7: 7, 8: 5, 9: 6, 10: 7},
            "B": {0: 7, 1: 4, 2: 5, 3: 6, 4: 2, 5: 7, 6: 5, 7: 6, 8: 6, 9: 5, 10: 8},
        },
        precedences={
            "A": [
                (0, 1), (0, 2), (1, 3), (2, 3), (2, 4),
                (3, 5), (4, 5), (4, 6), (5, 7), (6, 7),
                (7, 8), (7, 9), (8, 10), (9, 10),
            ],
            "B": [
                (0, 1), (0, 2), (1, 3), (2, 3), (2, 4),
                (3, 5), (4, 5), (4, 6), (5, 7), (6, 7),
                (7, 8), (7, 9), (8, 10), (9, 10),
            ],
        },
        cycle_time=14,
        demand={"A": 0.6, "B": 0.4},
    )


def to_aggregated_instance(mm: MultiModelInstance, mode: str = "max") -> Instance:
    if mode == "average":
        durations = mm.average_durations()
    else:
        durations = mm.max_durations()
    return Instance(
        name=f"{mm.name}-{mode}",
        tasks=mm.tasks,
        durations=durations,
        precedences=mm.union_precedences(),
        cycle_time=mm.cycle_time,
    )
