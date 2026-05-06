import random
from collections import deque, defaultdict
from ortools.linear_solver import pywraplp
from preprocessing import build_dataset

VEGETARIAN_PENALTY = 100000

OPTIMAL    = pywraplp.Solver.OPTIMAL
FEASIBLE   = pywraplp.Solver.FEASIBLE
INFEASIBLE = pywraplp.Solver.INFEASIBLE


def solve_diet_pnle(foods, nutrients, budget_cts=None, vegetarian=False):
    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:
        raise RuntimeError("Backend CBC indisponible")

    # food[-1]=categorie, food[-2]=max_g, food[-3]=min_g
    quantities = [solver.IntVar(0, food[-2], food[0]) for food in foods]

    use = [solver.BoolVar(f"use_{i}") for i in range(len(foods))]

    # semi-continu via big-M : qty=0 si use=0, qty entre min_g et max_g sinon
    for i, food in enumerate(foods):
        solver.Add(quantities[i] >= food[-3] * use[i])
        solver.Add(quantities[i] <= food[-2] * use[i])

    cat_buckets = defaultdict(list)
    for i, food in enumerate(foods):
        cat_buckets[food[-1]].append(i)

    for cat in ("féculent", "légume", "dessert"):
        if cat_buckets[cat]:
            solver.Add(sum(use[i] for i in cat_buckets[cat]) >= 1)

    vp = cat_buckets["viande"] + cat_buckets["poisson"]
    if vp and not vegetarian:
        solver.Add(sum(use[i] for i in vp) >= 1)
    if vp:
        solver.Add(sum(use[i] for i in vp) <= 1)

    solver.Add(sum(use) <= 5)

    for j, (_, lo, hi) in enumerate(nutrients):
        total = sum(foods[i][j + 2] * quantities[i] for i in range(len(foods)))
        solver.Add(total >= lo * 100)
        if hi is not None:
            solver.Add(total <= hi * 100)

    # Budget global : somme des coûts du repas <= budget alloué
    if budget_cts is not None:
        solver.Add(sum(foods[i][1] * quantities[i] for i in range(len(foods))) <= budget_cts)

    # minimiser cout + penalite viande/poisson si vegetarien
    cost = sum(foods[i][1] * quantities[i] for i in range(len(foods)))
    if vegetarian:
        penalty = VEGETARIAN_PENALTY * sum(
            use[i] for i, food in enumerate(foods) if food[-1] in ("viande", "poisson")
        )
        solver.Minimize(cost + penalty)
    else:
        solver.Minimize(cost)

    status = solver.Solve()
    return status, solver, quantities


def print_solution_pnle(foods, nutrients, status, solver, quantities):
    if status not in (OPTIMAL, FEASIBLE):
        print("Pas de solution réalisable.")
        return []

    if status == FEASIBLE:
        print("Solution trouvée mais optimalité non prouvée.")

    print(f"Coût total : {solver.Objective().Value() / 10000:.2f} €\n")

    print("Quantités :")
    used = []
    for i, food in enumerate(foods):
        qty = int(quantities[i].solution_value())
        if qty > 0:
            used.append(i)
            print(f"  {food[0]:40s} : {qty:4d} g")

    print("\nApports atteints :")
    for j, (name, lo, hi) in enumerate(nutrients):
        total = sum(foods[i][j + 2] * int(quantities[i].solution_value())
                    for i in range(len(foods))) // 100
        hi_str = f" - {hi}" if hi else ""
        print(f"  {name:8s} : {total:5d}  (cible: {lo}{hi_str})")

    return used


def _build_pool(
    foods: list,
    history: deque,
    proba_exclusion: float = 0.80,
    cost_noise: float = 0.60,
) -> list:

    recent   = list(history)
    hard_out = set().union(*recent[-2:]) if len(recent) >= 2 else (recent[-1] if recent else set())
    soft_out = set().union(*recent[:-2]) if len(recent) > 2  else set()

    pool = []
    for food in foods:
        name = food[0]
        if name in hard_out:
            continue
        if name in soft_out and random.random() < proba_exclusion:
            continue
        factor = 1.0 + random.uniform(-cost_noise, cost_noise)
        perturbed = (food[0], max(1, int(food[1] * factor)), *food[2:])
        pool.append(perturbed)
    return pool


def build_weekly_menu_pnle(
    foods: list,
    nutrients: list,
    days: int = 7,
    meals_per_day: int = 2,
    seed: int = None,
    budget_eur: float = None,
    vegetarian: bool = False,
    excluded_foods: list = None,
) -> list:

    if seed is not None:
        random.seed(seed)

    # Exclusion hard des aliments blacklistés
    if excluded_foods:
        blacklist = set(excluded_foods)
        foods = [f for f in foods if f[0] not in blacklist]

    per_meal_budget_cts = (
        int(budget_eur * 10000 / (days * meals_per_day))
        if budget_eur is not None else None
    )

    history = deque(maxlen=6)   # 6 repas = 3 jours de mémoire
    weekly  = []

    for day in range(1, days + 1):
        day_meals = []
        for meal_idx in range(1, meals_per_day + 1):

            pool = _build_pool(foods, history)
            status, solver, quantities = solve_diet_pnle(
                pool, nutrients,
                budget_cts=per_meal_budget_cts,
                vegetarian=vegetarian,
            )

            # fallback
            if status not in (OPTIMAL, FEASIBLE):
                hard_excluded = history[-1] if history else set()
                pool = [f for f in foods if f[0] not in hard_excluded]
                status, solver, quantities = solve_diet_pnle(
                    pool, nutrients,
                    budget_cts=per_meal_budget_cts,
                    vegetarian=vegetarian,
                )

            used_names, meal_foods = set(), []
            if status in (OPTIMAL, FEASIBLE):
                for i, food in enumerate(pool):
                    qty = int(quantities[i].solution_value())
                    if qty > 0:
                        used_names.add(food[0])
                        meal_foods.append((food[0], qty))
                cost = sum(
                    pool[j][1] * int(quantities[j].solution_value()) / 10000
                    for j in range(len(pool))
                )
            else:
                cost = 0.0

            history.append(used_names)
            day_meals.append({
                "foods":  meal_foods,
                "cost":   cost,
                "status": "optimal"    if status == OPTIMAL
                          else "feasible"   if status == FEASIBLE
                          else "infeasible",
            })

        weekly.append(day_meals)

    return weekly


def main():
    FOODS, NUTRIENTS, _ = build_dataset("Table Ciqual 2025_FR_2025_11_03.xlsx")

    weekly = build_weekly_menu_pnle(
        FOODS, NUTRIENTS,
        days=7, meals_per_day=2, seed=42,
        budget_eur=30,
        vegetarian=False,
        excluded_foods=["Pomme de terre dauphine, surgelée, cuite"]
    )
    from diet import print_weekly_menu
    print_weekly_menu(weekly)


if __name__ == "__main__":
    main()
