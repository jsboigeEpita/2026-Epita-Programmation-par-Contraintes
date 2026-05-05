import random
from collections import deque
from ortools.sat.python import cp_model
from preprocessing import build_dataset

VEGETARIAN_PENALTY = 100000 # added penalty in case no optimal solution

def solve_diet(foods, nutrients, budget_cts=None, vegetarian=False):
    model = cp_model.CpModel()
    # food[-1]=categorie, food[-2]=max_g, food[-3]=min_g
    quantities = [model.NewIntVar(0, food[-2], food[0]) for food in foods]

    use = [model.NewBoolVar(f"use_{i}") for i in range(len(foods))]
    for i, food in enumerate(foods):
        model.Add(quantities[i] >= food[-3]).OnlyEnforceIf(use[i])
        model.Add(quantities[i] == 0).OnlyEnforceIf(use[i].Not())

    from collections import defaultdict
    cat_buckets = defaultdict(list)
    for i, food in enumerate(foods):
        cat_buckets[food[-1]].append(i)

    for cat in ("féculent", "légume", "dessert"):
        if cat_buckets[cat]:
            model.Add(sum(use[i] for i in cat_buckets[cat]) >= 1)

    vp = cat_buckets["viande"] + cat_buckets["poisson"]
    if vp and not vegetarian:
        model.Add(sum(use[i] for i in vp) >= 1)
    if vp:
        model.Add(sum(use[i] for i in vp) <= 1)

    if cat_buckets["viande"] and cat_buckets["poisson"]:
        b_viande = model.NewBoolVar("choix_viande")
        for i in cat_buckets["viande"]:
            model.Add(use[i] == 0).OnlyEnforceIf(b_viande.Not())
        for i in cat_buckets["poisson"]:
            model.Add(use[i] == 0).OnlyEnforceIf(b_viande)

    model.Add(sum(use) <= 5)

    for j, (_, lo, hi) in enumerate(nutrients):
        total = sum(foods[i][j + 2] * quantities[i] for i in range(len(foods)))
        model.Add(total >= lo * 100)
        if hi is not None:
            model.Add(total <= hi * 100)

    # Budget global : somme des coûts du repas <= budget alloué
    if budget_cts is not None:
        model.Add(sum(foods[i][1] * quantities[i] for i in range(len(foods))) <= budget_cts)

    # minimiser cout + penalite viande/poisson si vegetarien
    cost = sum(foods[i][1] * quantities[i] for i in range(len(foods)))
    if vegetarian:
        penalty = VEGETARIAN_PENALTY * sum(
            use[i] for i, food in enumerate(foods) if food[-1] in ("viande", "poisson")
        )
        model.Minimize(cost + penalty)
    else:
        model.Minimize(cost)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    return status, solver, quantities

def print_solution(foods, nutrients, status, solver, quantities):
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("Pas de solution réalisable.")
        return []

    if status == cp_model.FEASIBLE:
        print("Solution trouvée mais optimalité non prouvée.")

    print(f"Coût total : {solver.ObjectiveValue() / 10000:.2f} €\n")

    print("Quantités :")
    used = []
    for i, food in enumerate(foods):
        qty = solver.Value(quantities[i])
        if qty > 0:
            used.append(i)
            print(f"  {food[0]:40s} : {qty:4d} g")

    print("\nApports atteints :")
    for j, (name, lo, hi) in enumerate(nutrients):
        total = sum(foods[i][j + 2] * solver.Value(quantities[i])
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


def build_weekly_menu(
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
            status, solver, quantities = solve_diet(
                pool, nutrients,
                budget_cts=per_meal_budget_cts,
                vegetarian=vegetarian,
            )

            # fallback
            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                hard_excluded = history[-1] if history else set()
                pool = [f for f in foods if f[0] not in hard_excluded]
                status, solver, quantities = solve_diet(
                    pool, nutrients,
                    budget_cts=per_meal_budget_cts,
                    vegetarian=vegetarian,
                )

            used_names, meal_foods = set(), []
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                for i, food in enumerate(pool):
                    qty = solver.Value(quantities[i])
                    if qty > 0:
                        used_names.add(food[0])
                        meal_foods.append((food[0], qty))
                cost = sum(
                    pool[j][1] * solver.Value(quantities[j]) / 10000
                    for j in range(len(pool))
                )
            else:
                cost = 0.0

            history.append(used_names)
            day_meals.append({
                "foods":  meal_foods,
                "cost":   cost,
                "status": "optimal"    if status == cp_model.OPTIMAL
                          else "feasible"   if status == cp_model.FEASIBLE
                          else "infeasible",
            })

        weekly.append(day_meals)

    return weekly


def print_weekly_menu(weekly: list) -> None:
    total_cost = 0.0
    for day_idx, day_meals in enumerate(weekly, 1):
        print(f"\n{'='*55}")
        print(f"  JOUR {day_idx}")
        print(f"{'='*55}")
        for meal_idx, meal in enumerate(day_meals, 1):
            label = ["Déjeuner", "Dîner"][meal_idx - 1]
            print(f"\n  {label}  [{meal['status']}]  -  {meal['cost']:.2f} €")
            for nom, qty in meal["foods"]:
                print(f"    {nom:45s} : {qty:4d} g")
            total_cost += meal["cost"]
    print(f"\n{'='*55}")
    print(f"  Coût total semaine : {total_cost:.2f} €")
    print(f"{'='*55}\n")


def main():
    FOODS, NUTRIENTS, _ = build_dataset("Table Ciqual 2025_FR_2025_11_03.xlsx")

    weekly = build_weekly_menu(
        FOODS, NUTRIENTS,
        days=7, meals_per_day=2, seed=42,
        budget_eur=30, # ex: 30€ pour la semaine
        vegetarian=False,
        excluded_foods=["Pomme de terre dauphine, surgelée, cuite"]
    )
    print_weekly_menu(weekly)


if __name__ == "__main__":
    main()