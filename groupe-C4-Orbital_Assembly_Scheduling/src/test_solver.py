from __future__ import annotations

from .baseline_greedy import solve_greedy
from .domain import OrbitalInstance
from .instance_generator import generate_instance
from .solver_cp_sat import SolveResult, solve_cpsat
from .validation import validate_schedule


def _assert_valid(label: str, instance: OrbitalInstance, result: SolveResult) -> None:
    if not result.feasible:
        raise AssertionError(f"{label} did not find a feasible solution: {result.status}")

    check = validate_schedule(instance, result.schedule)
    if not check["feasible"]:
        raise AssertionError(f"{label} produced an invalid schedule: {check['violations']}")


def main() -> None:
    instance = generate_instance(n_modules=4, horizon=420, seed=11)

    cp_result = solve_cpsat(instance, time_limit_s=5.0, workers=1, seed=11)
    greedy_result = solve_greedy(instance)

    _assert_valid("CP-SAT", instance, cp_result)
    _assert_valid("greedy", instance, greedy_result)

    print("Smoke test passed.")
    print(f"CP-SAT: makespan={cp_result.makespan}, fuel={cp_result.total_fuel}, status={cp_result.status}")
    print(f"Greedy: makespan={greedy_result.makespan}, fuel={greedy_result.total_fuel}, status={greedy_result.status}")


if __name__ == "__main__":
    main()
