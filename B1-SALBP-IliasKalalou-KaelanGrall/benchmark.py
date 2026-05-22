from dataclasses import dataclass

from instances import Instance, Solution
from solvers import cpsat, plne, rpw


@dataclass
class BenchmarkRow:
    instance: str
    n_tasks: int
    cycle_time: int
    known_optimum: int | None
    cpsat: Solution | None
    plne: Solution | None
    rpw: Solution | None

    def to_dict(self) -> dict:
        def stations(s: Solution | None) -> int | str:
            return s.n_stations if s is not None else "-"

        def time_ms(s: Solution | None) -> str:
            return f"{s.time_ms:.0f}" if s is not None else "-"

        def gap(s: Solution | None) -> str:
            if s is None or self.known_optimum is None:
                return "-"
            return f"{100 * (s.n_stations - self.known_optimum) / self.known_optimum:.1f}%"

        return {
            "Instance": self.instance,
            "Tâches": self.n_tasks,
            "Cycle": self.cycle_time,
            "Optimum connu": self.known_optimum if self.known_optimum is not None else "-",
            "CP-SAT stations": stations(self.cpsat),
            "CP-SAT temps (ms)": time_ms(self.cpsat),
            "CP-SAT gap": gap(self.cpsat),
            "PLNE stations": stations(self.plne),
            "PLNE temps (ms)": time_ms(self.plne),
            "RPW stations": stations(self.rpw),
            "RPW temps (ms)": time_ms(self.rpw),
            "RPW gap": gap(self.rpw),
        }


def run_benchmark(
    instances: list[tuple[Instance, int | None]],
    time_limit_cpsat: float = 10.0,
    time_limit_plne: float = 10.0,
    run_plne: bool = True,
) -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    for inst, known_opt in instances:
        sol_cpsat = cpsat.solve_salbp1(inst, time_limit=time_limit_cpsat)
        sol_plne = plne.solve_salbp1(inst, time_limit=time_limit_plne) if run_plne else None
        sol_rpw = rpw.solve_salbp1(inst)
        rows.append(
            BenchmarkRow(
                instance=inst.name,
                n_tasks=len(inst.tasks),
                cycle_time=inst.cycle_time,
                known_optimum=known_opt,
                cpsat=sol_cpsat,
                plne=sol_plne,
                rpw=sol_rpw,
            )
        )
    return rows
