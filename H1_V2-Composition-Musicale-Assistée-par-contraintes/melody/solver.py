"""
solver.py
----------
Le coeur du projet : modeliser et resoudre la generation de melodies
en CP-SAT (OR-Tools).

Structure :
  - build_model()   : construit le modele CP-SAT (variables + contraintes)
  - add_soft_*()    : ajoute des soft constraints (preferences) au modele
  - solve()         : lance le solveur et retourne une melodie (ou None)
  - PROFILES        : 3 profils stylistiques pre-regles

Tout le savoir musical vit dans music_theory.py. Ici, on ne fait que de
la programmation par contraintes.
"""

from ortools.sat.python import cp_model
from melody.music_theory import (
    scale_pitches,
    tonic_pitch_classes,
    dominant_or_leading_tone_pcs,
)


# ===========================================================================
# 1. MODELE DE BASE : variables + hard constraints
# ===========================================================================

def build_model(
    n_notes: int = 16,
    scale_name: str = "C_major",
    max_interval: int = 7,
):
    """
    Construit un modele CP-SAT pour generer une melodie monodique.

    Parametres
    ----------
    n_notes : int
        Nombre de notes a generer (longueur de la melodie).
    scale_name : str
        Nom de la gamme (cf. music_theory.SCALES).
    max_interval : int
        Saut melodique maximum autorise, en demi-tons.
        7 = une quinte juste, valeur classique en musique tonale.

    Retourne
    --------
    (model, pitch) : le modele CP-SAT et la liste des variables pitch[t].
    """
    model = cp_model.CpModel()

    # --- VARIABLES ----------------------------------------------------------
    # Une variable entiere par position dans la melodie.
    # Son domaine = toutes les hauteurs MIDI appartenant a la gamme.
    #
    # ASTUCE : on aurait pu prendre des variables sur [0, 127] et poser une
    # contrainte "pitch % 12 in scale". Mais reduire le domaine en amont est
    # bien plus efficace : le solveur explore moins d'etats.
    domain = scale_pitches(scale_name)
    pitch = [
        model.NewIntVarFromDomain(cp_model.Domain.FromValues(domain), f"pitch_{t}")
        for t in range(n_notes)
    ]

    # --- CONTRAINTES "HARD" -------------------------------------------------
    # (= obligatoirement satisfaites, sinon pas de solution)

    # C1. La premiere note est la tonique.
    #     Cela ancre la melodie dans sa tonalite des le debut.
    tonic_pcs = tonic_pitch_classes(scale_name)
    _force_pitch_class(model, pitch[0], tonic_pcs)

    # C2. La derniere note est aussi la tonique.
    #     Cela donne une impression de "phrase finie".
    _force_pitch_class(model, pitch[-1], tonic_pcs)

    # C3. L'avant-derniere note est dominante (V) ou sensible (VII).
    #     -> cadence parfaite (V->I) ou cadence en sensible (VII->I).
    cadence_pcs = dominant_or_leading_tone_pcs(scale_name)
    _force_pitch_class(model, pitch[-2], cadence_pcs)

    # C4. Sauts melodiques bornes : |pitch[t+1] - pitch[t]| <= max_interval.
    #     Empeche les melodies "en zigzag" injouables.
    for t in range(n_notes - 1):
        diff = model.NewIntVar(-24, 24, f"diff_{t}")
        model.Add(diff == pitch[t + 1] - pitch[t])
        # AddAbsEquality : abs_diff vaut |diff|
        abs_diff = model.NewIntVar(0, 24, f"abs_diff_{t}")
        model.AddAbsEquality(abs_diff, diff)
        model.Add(abs_diff <= max_interval)
        # On interdit aussi de rester strictement sur la meme note.
        # Sans ca, le solveur pourrait repeter une note 16 fois (valide
        # mais inecoutable). On laissera la possibilite via une soft
        # constraint plus loin si on veut autoriser les repetitions.
        model.Add(abs_diff >= 1)

    return model, pitch


def _force_pitch_class(model, pitch_var, allowed_pcs: list[int]) -> None:
    """
    Force une variable pitch a appartenir a un sous-ensemble de pitch classes.
    Helper interne, utilise pour les contraintes de debut/fin/cadence.

    On utilise AddAllowedAssignments : c'est la facon idiomatique en CP-SAT
    de poser "x dans une liste de valeurs". Le solveur exploite directement
    cette table pour propager.
    """
    # On regarde le domaine actuel de pitch_var et on garde uniquement
    # les valeurs dont le pitch class est autorise.
    # En pratique, comme on a deja restreint pitch_var a la gamme,
    # ces valeurs existent.
    allowed_values = []
    # On enumere les hauteurs MIDI possibles dans une plage large
    for p in range(0, 128):
        if p % 12 in allowed_pcs:
            allowed_values.append((p,))
    model.AddAllowedAssignments([pitch_var], allowed_values)


# ===========================================================================
# 2. SOFT CONSTRAINTS : preferences stylistiques
# ===========================================================================
#
# Une soft constraint est une preference, pas une obligation.
# Principe : pour chaque "ecart" par rapport a la preference, on cree une
# variable de cout, et on demande au solveur de minimiser la somme des couts.
#
# C'est tres exactement le "Weighted CSP" du notebook CSP-7.

def add_soft_smoothness(model, pitch, weight: int) -> list:
    """
    Soft constraint : "preferer les mouvements conjoints" (= petits intervalles).

    Pour chaque saut > 2 demi-tons, on paye un cout proportionnel a la taille
    du saut. Avec un weight eleve, la melodie tend a se deplacer par notes
    voisines (style "comptine"). Avec un weight faible, elle s'autorise les
    grands sauts (style "aventureux").

    Retourne la liste des variables de cout creees (a sommer dans Minimize).
    """
    costs = []
    for t in range(len(pitch) - 1):
        # On reconstruit la valeur absolue de l'intervalle.
        diff = model.NewIntVar(-24, 24, f"smooth_diff_{t}")
        model.Add(diff == pitch[t + 1] - pitch[t])
        abs_diff = model.NewIntVar(0, 24, f"smooth_abs_{t}")
        model.AddAbsEquality(abs_diff, diff)

        # cost = max(0, abs_diff - 2) * weight
        # -> 0 si le saut est <= 2 demi-tons (mouvement conjoint)
        # -> proportionnel au-dela
        excess = model.NewIntVar(0, 24, f"smooth_excess_{t}")
        model.AddMaxEquality(excess, [abs_diff - 2, model.NewConstant(0)])

        cost = model.NewIntVar(0, 24 * weight, f"smooth_cost_{t}")
        model.Add(cost == excess * weight)
        costs.append(cost)
    return costs


def add_soft_range(model, pitch, weight: int, min_range: int = 12) -> list:
    """
    Soft constraint : "couvrir au moins une octave".

    On veut que la melodie occupe un certain ambitus (ecart entre la note
    la plus aigue et la plus grave). Sinon elle reste coincee sur 3-4 notes
    et sonne pauvre.

    On paye un cout si max(pitch) - min(pitch) < min_range.
    """
    max_pitch = model.NewIntVar(0, 127, "max_pitch")
    min_pitch = model.NewIntVar(0, 127, "min_pitch")
    model.AddMaxEquality(max_pitch, pitch)
    model.AddMinEquality(min_pitch, pitch)

    actual_range = model.NewIntVar(0, 127, "range")
    model.Add(actual_range == max_pitch - min_pitch)

    # cost = max(0, min_range - actual_range) * weight
    deficit = model.NewIntVar(0, 127, "range_deficit")
    model.AddMaxEquality(deficit, [min_range - actual_range, model.NewConstant(0)])

    cost = model.NewIntVar(0, 127 * weight, "range_cost")
    model.Add(cost == deficit * weight)
    return [cost]


def add_soft_no_oscillation(model, pitch, weight: int) -> list:
    """
    Soft constraint : "eviter les oscillations triviales".

    On penalise les motifs A-B-A (la note t+2 == note t).
    Sinon le solveur, qui veut minimiser tous les couts, trouve souvent
    qu'osciller entre 2 notes voisines coute zero a tous les autres couts :
    saut de 2 demi-tons (pas penalise par smoothness),
    changement de direction systematique (pas penalise par direction).

    Resultat : C D C D C D... -> valide, mais musicalement mort.
    On force le solveur a varier en penalisant les retours immediats.
    """
    costs = []
    for t in range(len(pitch) - 2):
        # is_same = 1 si pitch[t+2] == pitch[t], sinon 0
        is_same = model.NewBoolVar(f"osc_{t}")
        model.Add(pitch[t + 2] == pitch[t]).OnlyEnforceIf(is_same)
        model.Add(pitch[t + 2] != pitch[t]).OnlyEnforceIf(is_same.Not())

        cost = model.NewIntVar(0, weight, f"osc_cost_{t}")
        model.Add(cost == weight * is_same)
        costs.append(cost)
    return costs


def add_soft_direction_changes(model, pitch, weight: int) -> list:
    """
    Soft constraint : "favoriser les changements de direction".

    Une melodie qui monte sans cesse (ou descend sans cesse) est ennuyeuse.
    On encourage les changements de sens.

    On compte les "pics" et "creux" : un pic en t signifie pitch[t-1] < pitch[t] > pitch[t+1].
    Plus il y a de pics/creux, mieux c'est, donc on paye un cout quand
    deux intervalles consecutifs ont le meme signe.
    """
    costs = []
    for t in range(1, len(pitch) - 1):
        # interval avant et apres la note t
        a = model.NewIntVar(-24, 24, f"dir_a_{t}")
        b = model.NewIntVar(-24, 24, f"dir_b_{t}")
        model.Add(a == pitch[t] - pitch[t - 1])
        model.Add(b == pitch[t + 1] - pitch[t])

        # On veut detecter si a et b sont de meme signe.
        # Astuce : a et b ont meme signe <=> a*b > 0.
        # CP-SAT n'aime pas la multiplication libre, mais on peut decomposer :
        # On cree deux booleens "monte_a", "monte_b" et on compare.
        up_a = model.NewBoolVar(f"up_a_{t}")
        up_b = model.NewBoolVar(f"up_b_{t}")
        model.Add(a > 0).OnlyEnforceIf(up_a)
        model.Add(a <= 0).OnlyEnforceIf(up_a.Not())
        model.Add(b > 0).OnlyEnforceIf(up_b)
        model.Add(b <= 0).OnlyEnforceIf(up_b.Not())

        # same_direction = (up_a == up_b)
        same_direction = model.NewBoolVar(f"same_dir_{t}")
        model.Add(up_a == up_b).OnlyEnforceIf(same_direction)
        model.Add(up_a != up_b).OnlyEnforceIf(same_direction.Not())

        # On paye 'weight' a chaque continuation de direction
        cost = model.NewIntVar(0, weight, f"dir_cost_{t}")
        model.Add(cost == weight * same_direction)
        costs.append(cost)
    return costs


# ===========================================================================
# 3. PROFILS STYLISTIQUES
# ===========================================================================
#
# Chaque profil est juste un dictionnaire de poids passes aux soft constraints.
# C'est la beaute du framework : changer un parametre change le style.

PROFILES = {
    # Mouvement conjoint tres favorise -> melodies "fluides"
    "fluide": {
        "smoothness":     5,
        "range":          1,
        "direction":      1,
        "no_oscillation": 3,
    },
    # Sauts autorises, ambitus large -> melodies "aventureuses"
    "aventureux": {
        "smoothness":     1,
        "range":          5,
        "direction":      3,
        "no_oscillation": 2,
    },
    # Mouvements monotones tolerable, range moyen -> melodies "minimalistes"
    "minimaliste": {
        "smoothness":     3,
        "range":          0,
        "direction":      0,
        "no_oscillation": 1,
    },
}


# ===========================================================================
# 4. SOLVE : assembler le tout et lancer le solveur
# ===========================================================================

def solve(
    n_notes: int = 16,
    scale_name: str = "C_major",
    profile: str = "fluide",
    time_limit: float = 10.0,
    random_seed: int = 0,
) -> list[int] | None:
    """
    Resout le probleme et retourne la melodie generee (liste de hauteurs MIDI).

    Parametres
    ----------
    n_notes : int        - longueur de la melodie
    scale_name : str     - gamme (cf. SCALES)
    profile : str        - 'fluide' | 'aventureux' | 'minimaliste'
    time_limit : float   - duree max de calcul en secondes
    random_seed : int    - graine pour varier les solutions

    Retourne
    --------
    list[int] | None : la liste des hauteurs MIDI, ou None si infeasible.
    """
    # 1. Modele de base avec hard constraints
    model, pitch = build_model(n_notes=n_notes, scale_name=scale_name)

    # 2. Soft constraints selon le profil
    weights = PROFILES[profile]
    all_costs = []
    if weights["smoothness"] > 0:
        all_costs += add_soft_smoothness(model, pitch, weights["smoothness"])
    if weights["range"] > 0:
        all_costs += add_soft_range(model, pitch, weights["range"])
    if weights["direction"] > 0:
        all_costs += add_soft_direction_changes(model, pitch, weights["direction"])
    if weights["no_oscillation"] > 0:
        all_costs += add_soft_no_oscillation(model, pitch, weights["no_oscillation"])

    # 3. Fonction objectif : minimiser la somme des couts
    if all_costs:
        model.Minimize(sum(all_costs))

    # 4. Lancer le solveur
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    # La graine aleatoire change la "personnalite" du solveur :
    # deux graines differentes donnent souvent deux melodies differentes
    # de qualite (presque) equivalente. Tres utile pour la demo.
    solver.parameters.random_seed = random_seed
    # On randomise aussi l'ordre d'exploration, sinon le solveur tend a
    # produire toujours la meme solution.
    solver.parameters.randomize_search = True

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    # 5. Extraire la solution
    return [solver.Value(p) for p in pitch]


# Petit utilitaire pour generer n melodies differentes (pour la demo)
def solve_many(n: int, **kwargs) -> list[list[int]]:
    """
    Genere n melodies en interdisant explicitement les melodies deja trouvees.

    Astuce : CP-SAT donne souvent la meme melodie quand on relance, car
    plusieurs sont optimales et il trouve la meme en premier. On le force
    a chercher ailleurs en lui interdisant les solutions deja produites.
    """
    melodies = []
    # On reconstruit le modele a chaque iteration en y ajoutant les
    # contraintes de "differentiation". Plus simple que de jouer avec
    # les callbacks d'enumeration.
    for seed in range(n):
        m = _solve_with_blocklist(blocklist=melodies, random_seed=seed, **kwargs)
        if m is None:
            break   # plus de solutions possibles
        melodies.append(m)
    return melodies


def _solve_with_blocklist(blocklist: list[list[int]], **kwargs) -> list[int] | None:
    """
    Comme solve(), mais en interdisant les melodies de blocklist.

    Pour interdire la melodie M = [m_0, ..., m_{n-1}], on ajoute la contrainte
    "au moins une des notes doit differer", ce qui s'ecrit :
       pitch[0] != m_0 OU pitch[1] != m_1 OU ... OU pitch[n-1] != m_{n-1}
    """
    n_notes = kwargs.get("n_notes", 16)
    scale_name = kwargs.get("scale_name", "C_major")
    profile = kwargs.get("profile", "fluide")
    time_limit = kwargs.get("time_limit", 10.0)
    random_seed = kwargs.get("random_seed", 0)

    model, pitch = build_model(n_notes=n_notes, scale_name=scale_name)

    weights = PROFILES[profile]
    all_costs = []
    if weights["smoothness"] > 0:
        all_costs += add_soft_smoothness(model, pitch, weights["smoothness"])
    if weights["range"] > 0:
        all_costs += add_soft_range(model, pitch, weights["range"])
    if weights["direction"] > 0:
        all_costs += add_soft_direction_changes(model, pitch, weights["direction"])
    if weights["no_oscillation"] > 0:
        all_costs += add_soft_no_oscillation(model, pitch, weights["no_oscillation"])

    # Pour chaque melodie deja generee, on ajoute "au moins une note differe"
    for prev_melody in blocklist:
        # Liste des booleens "pitch[t] != prev[t]"
        diff_bools = []
        for t in range(n_notes):
            b = model.NewBoolVar(f"diff_{len(blocklist)}_{t}")
            model.Add(pitch[t] != prev_melody[t]).OnlyEnforceIf(b)
            model.Add(pitch[t] == prev_melody[t]).OnlyEnforceIf(b.Not())
            diff_bools.append(b)
        # Au moins un des booleens doit etre vrai = au moins une note differe
        model.AddBoolOr(diff_bools)

    if all_costs:
        model.Minimize(sum(all_costs))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.random_seed = random_seed
    solver.parameters.randomize_search = True

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [solver.Value(p) for p in pitch]