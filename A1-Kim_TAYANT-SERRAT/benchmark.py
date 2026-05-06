import time
import random
from preprocessing import build_dataset
from diet import solve_diet
from diet_pnle import solve_diet_pnle, OPTIMAL as P_OPT, FEASIBLE as P_FEAS
from ortools.sat.python import cp_model


def run_cpsat(pool, nutrients, budget_cts):
    t0 = time.perf_counter()
    status, solver, qty = solve_diet(pool, nutrients, budget_cts=budget_cts)
    dt = time.perf_counter() - t0
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    cost = solver.ObjectiveValue() / 10000 if ok else None
    return dt, ok, cost


def run_pnle(pool, nutrients, budget_cts):
    t0 = time.perf_counter()
    status, solver, qty = solve_diet_pnle(pool, nutrients, budget_cts=budget_cts)
    dt = time.perf_counter() - t0
    ok = status in (P_OPT, P_FEAS)
    cost = solver.Objective().Value() / 10000 if ok else None
    n_vars = solver.NumVariables()
    n_cons = solver.NumConstraints()
    return dt, ok, cost, n_vars, n_cons


def bench(foods, nutrients, pool_size, n_runs, budget_eur):
    budget_cts = int(budget_eur * 10000)
    rows = []
    for run in range(n_runs):
        random.seed(run)
        pool = random.sample(foods, min(pool_size, len(foods)))

        t_cp, ok_cp, cost_cp = run_cpsat(pool, nutrients, budget_cts)
        t_p, ok_p, cost_p, nv, nc = run_pnle(pool, nutrients, budget_cts)

        rows.append({
            "pool": pool_size, "run": run,
            "cp_ms": t_cp * 1000, "cp_ok": ok_cp, "cp_cost": cost_cp,
            "p_ms":  t_p  * 1000, "p_ok":  ok_p,  "p_cost":  cost_p,
            "p_nvars": nv, "p_nconstraints": nc,
        })
    return rows


def print_table(rows):
    print(f"\n{'pool':>5} {'run':>3} | {'CP-SAT (ms)':>12} {'coût':>7} | {'PLNE (ms)':>10} {'coût':>7} | vars  cons")
    print("-" * 80)
    for r in rows:
        print(
            f"{r['pool']:>5} {r['run']:>3} | "
            f"{r['cp_ms']:>10.1f}   {(r['cp_cost'] or 0):>5.2f} € | "
            f"{r['p_ms']:>8.1f}   {(r['p_cost'] or 0):>5.2f} € | "
            f"{r['p_nvars']:>4}  {r['p_nconstraints']:>4}"
        )

    # Moyennes par taille de pool
    by_pool = {}
    for r in rows:
        by_pool.setdefault(r["pool"], []).append(r)
    print("\nMoyennes :")
    for pool, rs in by_pool.items():
        avg_cp = sum(r["cp_ms"] for r in rs) / len(rs)
        avg_p  = sum(r["p_ms"]  for r in rs) / len(rs)
        ratio = avg_cp / avg_p if avg_p > 0 else 0
        winner = "PLNE" if avg_p < avg_cp else "CP-SAT"
        print(f"  pool={pool:>4} : CP-SAT {avg_cp:>7.1f} ms   PLNE {avg_p:>7.1f} ms   {winner} gagne (x{max(ratio, 1/ratio):.1f})")


def main():
    print("Chargement Ciqual...")
    foods, nutrients, _ = build_dataset("Table Ciqual 2025_FR_2025_11_03.xlsx")
    print(f"{len(foods)} aliments disponibles\n")

    all_rows = []
    for size in (100, 300, 800):
        all_rows += bench(foods, nutrients, pool_size=size, n_runs=3, budget_eur=5.0)

    print_table(all_rows)


if __name__ == "__main__":
    main()
