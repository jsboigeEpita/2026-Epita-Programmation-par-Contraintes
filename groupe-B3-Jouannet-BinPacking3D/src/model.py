from dataclasses import dataclass
from typing import List
from ortools.sat.python import cp_model


@dataclass
class Item:
    w: int          # largeur
    d: int          # profondeur
    h: int          # hauteur
    weight: float = 0.0
    fragile: bool = False

    @property
    def volume(self):
        return self.w * self.d * self.h


@dataclass
class Container:
    W: int          # largeur max
    D: int          # profondeur max
    H: int          # hauteur max
    max_weight: float = float('inf')

    @property
    def volume(self):
        return self.W * self.D * self.H


def solve(items: List[Item], container: Container, time_limit: int = 60) -> dict:
    """
    Résout le 3D Bin Packing avec CP-SAT (OR-Tools).

    Modélisation :
    - bin_var[i]     : quel conteneur reçoit l'objet i  (IntVar 0..n-1)
    - x[i],y[i],z[i]: position de l'objet i dans son conteneur

    Non-chevauchement : pour chaque paire (i,j) dans le même conteneur,
    au moins une des 6 séparations axiales doit tenir (disjonction sur 6 bool).

    Fragilité : un objet fragile est placé en haut du conteneur
    (z[i] = H - h[i]), ce qui garantit qu'aucun objet ne peut être au-dessus.

    Poids : pour chaque conteneur b, la somme des poids des objets assignés
    ne dépasse pas max_weight.

    Objectif : minimiser le nombre de conteneurs utilisés.
    Cassage de symétrie : les indices de conteneurs sont croissants.
    """
    n = len(items)
    if n == 0:
        return {'status': 'OPTIMAL', 'num_bins': 0, 'assignment': [], 'positions': []}

    model = cp_model.CpModel()
    max_bins = n

    # ── Variables principales ─────────────────────────────────────────────────

    bin_var = [model.NewIntVar(0, max_bins - 1, f'bin_{i}') for i in range(n)]

    x = [model.NewIntVar(0, container.W - items[i].w, f'x_{i}') for i in range(n)]
    y = [model.NewIntVar(0, container.D - items[i].d, f'y_{i}') for i in range(n)]
    z = [model.NewIntVar(0, container.H - items[i].h, f'z_{i}') for i in range(n)]

    # ── Cassage de symétrie ───────────────────────────────────────────────────
    model.Add(bin_var[0] == 0)
    for i in range(1, n):
        model.Add(bin_var[i] <= bin_var[i - 1] + 1)

    # ── Fragilité ─────────────────────────────────────────────────────────────
    # Un objet fragile est forcé tout en haut → rien ne peut être posé dessus.
    for i in range(n):
        if items[i].fragile:
            model.Add(z[i] == container.H - items[i].h)

    # ── Non-chevauchement ─────────────────────────────────────────────────────
    # Pour chaque paire (i,j) : si même conteneur → séparés sur au moins 1 axe.
    for i in range(n):
        for j in range(i + 1, n):
            wi, di, hi = items[i].w, items[i].d, items[i].h
            wj, dj, hj = items[j].w, items[j].d, items[j].h

            # same ↔ (bin_var[i] == bin_var[j])
            same = model.NewBoolVar(f'same_{i}_{j}')
            diff = model.NewIntVar(-(max_bins - 1), max_bins - 1, f'diff_{i}_{j}')
            abs_diff = model.NewIntVar(0, max_bins - 1, f'adiff_{i}_{j}')
            model.Add(diff == bin_var[i] - bin_var[j])
            model.AddAbsEquality(abs_diff, diff)
            model.Add(abs_diff == 0).OnlyEnforceIf(same)
            model.Add(abs_diff >= 1).OnlyEnforceIf(same.Not())

            sep = [model.NewBoolVar(f'sep_{i}_{j}_{k}') for k in range(6)]
            model.Add(x[i] + wi <= x[j]).OnlyEnforceIf([same, sep[0]])
            model.Add(x[j] + wj <= x[i]).OnlyEnforceIf([same, sep[1]])
            model.Add(y[i] + di <= y[j]).OnlyEnforceIf([same, sep[2]])
            model.Add(y[j] + dj <= y[i]).OnlyEnforceIf([same, sep[3]])
            model.Add(z[i] + hi <= z[j]).OnlyEnforceIf([same, sep[4]])
            model.Add(z[j] + hj <= z[i]).OnlyEnforceIf([same, sep[5]])
            model.AddBoolOr(sep).OnlyEnforceIf(same)

    # ── Poids par conteneur ────────────────────────────────────────────────────
    # in_bin[i][b] = 1 si l'objet i est dans le conteneur b.
    if container.max_weight < float('inf'):
        scale = 1000
        max_w_int = int(container.max_weight * scale)
        weights_int = [int(items[i].weight * scale) for i in range(n)]

        for b in range(max_bins):
            in_b = [model.NewBoolVar(f'ib_{i}_{b}') for i in range(n)]
            for i in range(n):
                # in_b[i] = 1  ↔  bin_var[i] == b
                model.Add(bin_var[i] == b).OnlyEnforceIf(in_b[i])
                diff_b = model.NewIntVar(-(max_bins - 1), max_bins - 1, f'dib_{i}_{b}')
                abs_b = model.NewIntVar(0, max_bins - 1, f'aib_{i}_{b}')
                model.Add(diff_b == bin_var[i] - b)
                model.AddAbsEquality(abs_b, diff_b)
                model.Add(abs_b >= 1).OnlyEnforceIf(in_b[i].Not())
            model.Add(
                sum(weights_int[i] * in_b[i] for i in range(n)) <= max_w_int
            )

    # ── Objectif ──────────────────────────────────────────────────────────────
    max_bin_used = model.NewIntVar(0, max_bins - 1, 'max_bin_used')
    model.AddMaxEquality(max_bin_used, bin_var)
    model.Minimize(max_bin_used + 1)

    # ── Résolution ────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = False
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            'status': solver.StatusName(status),
            'num_bins': int(solver.Value(max_bin_used)) + 1,
            'assignment': [int(solver.Value(bin_var[i])) for i in range(n)],
            'positions': [
                (int(solver.Value(x[i])), int(solver.Value(y[i])), int(solver.Value(z[i])))
                for i in range(n)
            ],
            'solve_time': solver.WallTime(),
        }

    return {
        'status': solver.StatusName(status),
        'num_bins': None,
        'solve_time': solver.WallTime(),
    }
