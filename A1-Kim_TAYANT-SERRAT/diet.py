import csv
import os
from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model
from preprocessing import build_dataset

def solve_diet(foods, nutrients):
    """Minimise le coût en respectant les contraintes nutritionnelles."""
    model = cp_model.CpModel()
    # food[-1]=categorie, food[-2]=max_g, food[-3]=min_g
    quantities = [model.NewIntVar(0, food[-2], food[0]) for food in foods]

    # portion minimale de 50 g => evite les 1g
    use = [model.NewBoolVar(f"use_{i}") for i in range(len(foods))]
    for i, food in enumerate(foods):
        model.Add(quantities[i] >= food[-3]).OnlyEnforceIf(use[i])
        model.Add(quantities[i] == 0).OnlyEnforceIf(use[i].Not())

    from collections import defaultdict
    cat_buckets = defaultdict(list)
    for i, food in enumerate(foods):
        cat_buckets[food[-1]].append(i)

    # impose féculent + viande/poisson + légume + dessert
    for cat in ("féculent", "légume", "dessert"):
        if cat_buckets[cat]:
            model.Add(sum(use[i] for i in cat_buckets[cat]) >= 1)
    # Au moins une viande OU un poisson FIXME: a verifier si bro est vegetarien
    vp = cat_buckets["viande"] + cat_buckets["poisson"]
    if vp:
        model.Add(sum(use[i] for i in vp) >= 1)

    # Max 1 viande/poisson au total
    if vp:
        model.Add(sum(use[i] for i in vp) <= 1)

    # Soit viande soit poisson
    if cat_buckets["viande"] and cat_buckets["poisson"]:
        b_viande = model.NewBoolVar("choix_viande")
        for i in cat_buckets["viande"]:
            model.Add(use[i] == 0).OnlyEnforceIf(b_viande.Not())
        for i in cat_buckets["poisson"]:
            model.Add(use[i] == 0).OnlyEnforceIf(b_viande)

    # max 5 aliments au total
    model.Add(sum(use) <= 5)

    # Contraintes nutritionnelles
    for j, (_, lo, hi) in enumerate(nutrients):
        total = sum(foods[i][j + 2] * quantities[i] for i in range(len(foods))) # Créer l'équation feature_n * x1 + feature_n * x2 ... + feature_n * x_n
        model.Add(total >= lo * 100)
        if hi is not None:
            model.Add(total <= hi  * 100)

    # Minimise le prix
    model.Minimize(sum(foods[i][1] * quantities[i] for i in range(len(foods))))

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    return status, solver, quantities

def print_solution(foods, nutrients, status, solver, quantities):
    """Affiche la solution et renvoie les indices des aliments utilisés."""
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
            # qty est en unités de 10 g
            print(f"  {food[0]:40s} : {qty:4d} g")

    print("\nApports atteints :")
    for j, (name, lo, hi) in enumerate(nutrients):
        total = sum(foods[i][j + 2] * solver.Value(quantities[i])
                    for i in range(len(foods))) // 100
        hi_str = f" - {hi}" if hi else ""
        print(f"  {name:8s} : {total:5d}  (cible: {lo}{hi_str})")

    return used


def main():
    FOODS, NUTRIENTS, df_clean = build_dataset("Table Ciqual 2025_FR_2025_11_03.xlsx")

    print("=== Repas 1 ===")
    status, solver, qty = solve_diet(FOODS, NUTRIENTS)
    used = print_solution(FOODS, NUTRIENTS, status, solver, qty)

    # Exclure les aliments déjà utilisés pour le repas suivant
    remaining = [f for i, f in enumerate(FOODS) if i not in used]

    print("\n=== Repas 2 ===")
    status, solver, qty = solve_diet(remaining, NUTRIENTS)
    print_solution(remaining, NUTRIENTS, status, solver, qty)


if __name__ == "__main__":
    main()