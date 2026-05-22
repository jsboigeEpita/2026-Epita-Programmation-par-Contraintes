"""Démo en ligne de commande : génère une instance, résout avec CP-SAT, imprime le planning."""

from src import (
    generate_instance,
    solve_cp_sat,
    solve_priority_rule,
    solve_simulated_annealing,
    format_schedule,
)


def main() -> None:
    instance = generate_instance(
        n_surgeries=14, n_rooms=3, n_surgeons=4, seed=42
    )

    print(f"Instance: {len(instance.surgeries)} chirurgies, "
          f"{len(instance.rooms)} salles, {len(instance.surgeons)} chirurgiens, "
          f"horizon={instance.horizon} min")
    print()

    for name, solver in [
        ("Priority-rule (greedy)", solve_priority_rule),
        ("Simulated annealing", lambda inst: solve_simulated_annealing(inst, n_iter=4000, seed=1)),
        ("CP-SAT", lambda inst: solve_cp_sat(inst, time_limit_s=10.0)),
    ]:
        result = solver(instance)
        print(f"=== {name} ===")
        print(f"  status   : {result.status}")
        print(f"  makespan : {result.makespan} min")
        print(f"  attente  : {result.total_wait} min")
        print(f"  objectif : {result.objective:.1f}")
        print(f"  temps    : {result.solve_ms:.0f} ms")
        print()

    print("Planning détaillé (CP-SAT) :")
    result = solve_cp_sat(instance, time_limit_s=10.0)
    print(format_schedule(result, instance))


if __name__ == "__main__":
    main()
