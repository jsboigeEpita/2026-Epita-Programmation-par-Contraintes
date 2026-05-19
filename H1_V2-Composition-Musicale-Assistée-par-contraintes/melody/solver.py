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
    # C5. Pas de note identique consecutive : |pitch[t+1] - pitch[t]| >= 1.
    # C6. Interdiction du TRITON (saut de 6 demi-tons).
    #     Le triton (ex: Do -> Fa#) est l'intervalle le plus dissonant
    #     de la musique tonale. Au Moyen Age on l'appelait "diabolus in musica"
    #     (le diable en musique) car il sonne tellement faux qu'il etait
    #     interdit dans la musique liturgique. On le banit donc explicitement.
    for t in range(n_notes - 1):
        diff = model.NewIntVar(-24, 24, f"diff_{t}")
        model.Add(diff == pitch[t + 1] - pitch[t])
        # AddAbsEquality : abs_diff vaut |diff|
        abs_diff = model.NewIntVar(0, 24, f"abs_diff_{t}")
        model.AddAbsEquality(abs_diff, diff)

        # C4 : sauts bornes
        model.Add(abs_diff <= max_interval)
        # C5 : pas deux notes consecutives identiques
        model.Add(abs_diff >= 1)
        # C6 : interdiction du triton
        model.Add(abs_diff != 6)

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


def add_soft_strong_beat_consonance(model, pitch, weight: int,
                                    scale_name: str = "C_major") -> list:
    """
    Soft constraint : "favoriser les notes consonantes sur les temps forts".

    En musique classique, les temps forts (1er et 3e temps d'une mesure 4/4)
    sont les moments OU L'OREILLE attend une note stable. On y favorise donc
    les notes consonantes : la tonique (I), la mediante (III) et la dominante (V),
    qui forment ensemble l'accord parfait de la gamme (Do-Mi-Sol en Do majeur).

    Sur chaque temps fort (positions 0, 2, 4, 6, 8, ...), on paye un cout si
    la note n'est PAS I, III ou V.

    Pourquoi c'est interessant a presenter :
    - Cette contrainte modelise la "pesanteur metrique" : les temps forts
      portent plus de poids harmonique que les temps faibles.
    - On peut tout a fait avoir une note dissonante sur un temps fort dans
      certains styles (jazz), d'ou le choix de soft plutot que hard.

    Note : on assume une metrique 4/4 implicite ou chaque "noire" du solveur
    correspond a un temps de la mesure. Les temps forts sont donc les
    positions paires (0, 2, 4, ...).
    """
    from melody.music_theory import SCALES

    # Pitch classes des degres I, III, V (= la triade)
    pcs = SCALES[scale_name]["pcs"]
    triad_pcs = [pcs[0], pcs[2], pcs[4]]   # I, III, V

    # Liste des hauteurs MIDI dont le pc est dans la triade
    triad_pitches = [p for p in range(0, 128) if p % 12 in triad_pcs]

    costs = []
    for t in range(0, len(pitch), 2):     # positions paires uniquement
        # is_on_triad = 1 si pitch[t] appartient a la triade
        is_on_triad = model.NewBoolVar(f"triad_{t}")
        # On exprime ca avec AddAllowedAssignments sur la variable.
        # Astuce : on cree une variable indicatrice via un BoolVar et
        # une contrainte "if-then" classique.
        model.AddAllowedAssignments(
            [pitch[t]], [(p,) for p in triad_pitches]
        ).OnlyEnforceIf(is_on_triad)
        # Si is_on_triad = 0, le pitch peut etre n'importe quoi (le solveur
        # choisira la valeur qui minimise le cout total)
        # On veut : cost = weight si is_on_triad == 0, sinon 0
        cost = model.NewIntVar(0, weight, f"triad_cost_{t}")
        model.Add(cost == weight * (1 - is_on_triad))
        costs.append(cost)
    return costs


def add_soft_arch_contour(model, pitch, weight: int) -> list:
    """
    Soft constraint : "favoriser un contour melodique en arche".

    Une melodie "naturelle" a souvent un contour en arche : elle monte
    progressivement vers un sommet (la "note culminante", typiquement
    aux 2/3 de la melodie), puis redescend vers la tonique finale.
    C'est un principe esthetique classique (regle des "trois quarts").

    On modelise ca simplement : on veut que la note la plus aigue de la
    melodie soit dans la 2e moitie de la melodie, pas trop tot ni trop tard.

    Cible : la note culminante doit etre entre la position n/3 et 2n/3.
    Cout : on paye 'weight' par position d'ecart au centre cible.

    C'est une preference forte chez Mozart et plus generalement dans la
    musique classique. Sans contrainte, le solveur tend a placer le pic
    n'importe ou.
    """
    n = len(pitch)
    target_lo = n // 3
    target_hi = (2 * n) // 3

    # Trouver l'argmax de pitch (position du max)
    # En CP-SAT, pour exprimer "argmax", on cree des booleens et on contraint :
    # argmax_t = 1 si pitch[t] == max(pitch)
    max_val = model.NewIntVar(0, 127, "arch_max")
    model.AddMaxEquality(max_val, pitch)

    # Pour chaque position, est-elle l'argmax ?
    is_peak = []
    for t in range(n):
        b = model.NewBoolVar(f"peak_{t}")
        model.Add(pitch[t] == max_val).OnlyEnforceIf(b)
        model.Add(pitch[t] != max_val).OnlyEnforceIf(b.Not())
        is_peak.append(b)

    # Exactement un pic (en cas d'egalite, on prend le premier)
    # On simplifie : on cherche juste la presence du pic dans la zone cible.
    # Cout = weight si AUCUN pic n'est dans [target_lo, target_hi]
    in_zone_bools = is_peak[target_lo:target_hi + 1]
    if not in_zone_bools:
        return []

    peak_in_zone = model.NewBoolVar("peak_in_zone")
    model.AddBoolOr(in_zone_bools).OnlyEnforceIf(peak_in_zone)
    # Si peak_in_zone = 0, alors AUCUN des bools de la zone n'est vrai
    for b in in_zone_bools:
        model.AddImplication(peak_in_zone.Not(), b.Not())

    cost = model.NewIntVar(0, weight, "arch_cost")
    model.Add(cost == weight * (1 - peak_in_zone))
    return [cost]


# ===========================================================================
# 3. PROFILS STYLISTIQUES
# ===========================================================================
#
# Chaque profil est juste un dictionnaire de poids passes aux soft constraints.
# C'est la beaute du framework : changer un parametre change le style.

PROFILES = {
    # Mouvement conjoint tres favorise -> melodies "fluides"
    # Avec consonance forte et arche typique -> tres "classique/comptine"
    "fluide": {
        "smoothness":     5,
        "range":          1,
        "direction":      1,
        "no_oscillation": 3,
        "strong_beat":    4,   # tres consonant sur les temps forts
        "arch":           3,   # contour en arche prononce
    },
    # Sauts autorises, ambitus large -> melodies "aventureuses"
    # Moins de respect des conventions classiques
    "aventureux": {
        "smoothness":     1,
        "range":          5,
        "direction":      3,
        "no_oscillation": 2,
        "strong_beat":    1,   # peu de contrainte sur la consonance
        "arch":           1,   # contour libre
    },
    # Stable, peu d'ambitus -> melodies "minimalistes"
    "minimaliste": {
        "smoothness":     3,
        "range":          0,
        "direction":      0,
        "no_oscillation": 1,
        "strong_beat":    2,   # consonance moderee
        "arch":           0,   # pas de contour particulier
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
    if weights.get("strong_beat", 0) > 0:
        all_costs += add_soft_strong_beat_consonance(
            model, pitch, weights["strong_beat"], scale_name=scale_name
        )
    if weights.get("arch", 0) > 0:
        all_costs += add_soft_arch_contour(model, pitch, weights["arch"])

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
    if weights.get("strong_beat", 0) > 0:
        all_costs += add_soft_strong_beat_consonance(
            model, pitch, weights["strong_beat"], scale_name=scale_name
        )
    if weights.get("arch", 0) > 0:
        all_costs += add_soft_arch_contour(model, pitch, weights["arch"])

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


# ===========================================================================
# 5. MODE VARIATION : completer une melodie partielle
# ===========================================================================
#
# Au lieu de generer une melodie from-scratch, on fournit un "theme" partiel
# (certaines notes fixees, d'autres a None) et le solveur complete les trous
# en respectant toutes les contraintes du modele.
#
# C'est un PROBLEME INVERSE classique en CP : on impose des valeurs sur
# certaines variables, et on laisse le solveur explorer pour les autres.
#
# Cas d'usage :
#   - Composer une variation sur un theme connu
#   - Completer une melodie ou il manque des notes
#   - Forcer une "note pivot" au milieu pour donner une direction

def solve_with_fixed_notes(
    fixed_notes: list[int | None],
    scale_name: str = "C_major",
    profile: str = "fluide",
    time_limit: float = 10.0,
    random_seed: int = 0,
) -> list[int] | None:
    """
    Resout en imposant certaines notes pre-determinees.

    Parametres
    ----------
    fixed_notes : list[int | None]
        Liste de la longueur de la melodie. Chaque element vaut :
          - un entier MIDI (60, 62, ...) -> cette note est FIXEE
          - None -> cette note est LIBRE, le solveur la choisit
        Exemple : [60, None, None, 60, 65, None, None, 60]
        -> melodie de 8 notes, on impose les notes 0, 3, 4, 7

    scale_name, profile, time_limit, random_seed : voir solve()

    Retourne
    --------
    list[int] | None : la melodie complete (avec les fixes + les libres)

    Exemple d'utilisation
    ---------------------
    >>> # Imposer le debut de "Au clair de la lune" et laisser le solveur
    >>> # completer une suite coherente
    >>> theme = [60, 60, 60, 62, 64, None, 62, None, 60, None, 64, None,
    ...          62, None, None, 60]
    >>> melody = solve_with_fixed_notes(theme)
    """
    n_notes = len(fixed_notes)

    # 1. On construit le modele complet (memes hard constraints que d'habitude)
    model, pitch = build_model(n_notes=n_notes, scale_name=scale_name)

    # 2. On AJOUTE les contraintes d'egalite pour les notes fixees
    # C'est ca le "mode variation" : on impose pitch[t] == valeur sur
    # les positions specifiees.
    for t, fixed_value in enumerate(fixed_notes):
        if fixed_value is not None:
            model.Add(pitch[t] == fixed_value)

    # 3. Soft constraints (memes que solve)
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
    if weights.get("strong_beat", 0) > 0:
        all_costs += add_soft_strong_beat_consonance(
            model, pitch, weights["strong_beat"], scale_name=scale_name
        )
    if weights.get("arch", 0) > 0:
        all_costs += add_soft_arch_contour(model, pitch, weights["arch"])

    if all_costs:
        model.Minimize(sum(all_costs))

    # 4. Resolution
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.random_seed = random_seed
    solver.parameters.randomize_search = True

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Si pas de solution : les notes fixees sont peut-etre incompatibles
        # avec les hard constraints (ex: deux notes fixees a un triton d'ecart,
        # ou la premiere note fixee qui n'est pas la tonique).
        return None
    return [solver.Value(p) for p in pitch]


def generate_variations(theme: list[int], n_variations: int = 4,
                        keep_positions: list[int] | None = None,
                        **kwargs) -> list[list[int]]:
    """
    Genere n variations d'un theme en gardant certaines notes pivots.

    Parametres
    ----------
    theme : list[int]
        La melodie originale (theme de base).
    n_variations : int
        Nombre de variations a generer.
    keep_positions : list[int] | None
        Indices des notes du theme a conserver dans toutes les variations.
        Par defaut : on garde la premiere, la derniere et les positions
        multiples de 4 (= les "notes pivots" sur les temps forts).

    Retourne
    --------
    list[list[int]] : les variations generees (sans le theme original).
    """
    n = len(theme)
    if keep_positions is None:
        # Par defaut : on garde le debut, la fin, l'avant-derniere (cadence)
        # et quelques positions "pivots" (toutes les 4 notes).
        # On veut laisser environ 50-70% des notes LIBRES pour avoir
        # de la diversite dans les variations.
        keep_positions = [0, n - 1, n - 2] + list(range(0, n, 4))
        keep_positions = sorted(set(keep_positions))

    # Construire le pattern "note fixee / note libre"
    fixed_notes = [
        theme[t] if t in keep_positions else None
        for t in range(n)
    ]

    # Pour avoir DES variations differentes (pas toujours la meme solution
    # optimale), on utilise la meme astuce blocklist que solve_many() :
    # apres chaque variation trouvee, on lui interdit de reapparaitre.
    variations = []
    blocklist = [theme]  # on interdit aussi le theme original

    for seed in range(200):
        if len(variations) >= n_variations:
            break
        var = _variation_with_blocklist(
            fixed_notes=fixed_notes,
            blocklist=blocklist,
            random_seed=seed,
            **kwargs,
        )
        if var is not None and var not in variations and var != theme:
            variations.append(var)
            blocklist.append(var)
    return variations


def _variation_with_blocklist(
    fixed_notes: list[int | None],
    blocklist: list[list[int]],
    scale_name: str = "C_major",
    profile: str = "fluide",
    time_limit: float = 5.0,
    random_seed: int = 0,
) -> list[int] | None:
    """
    Comme solve_with_fixed_notes(), mais en interdisant aussi les
    melodies de blocklist. Utilise en interne par generate_variations().
    """
    n_notes = len(fixed_notes)
    model, pitch = build_model(n_notes=n_notes, scale_name=scale_name)

    # Imposer les notes fixees
    for t, fixed_value in enumerate(fixed_notes):
        if fixed_value is not None:
            model.Add(pitch[t] == fixed_value)

    # Soft constraints
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
    if weights.get("strong_beat", 0) > 0:
        all_costs += add_soft_strong_beat_consonance(
            model, pitch, weights["strong_beat"], scale_name=scale_name
        )
    if weights.get("arch", 0) > 0:
        all_costs += add_soft_arch_contour(model, pitch, weights["arch"])

    # Interdire toutes les melodies de blocklist
    for prev in blocklist:
        diff_bools = []
        for t in range(n_notes):
            b = model.NewBoolVar(f"var_diff_{len(blocklist)}_{t}")
            model.Add(pitch[t] != prev[t]).OnlyEnforceIf(b)
            model.Add(pitch[t] == prev[t]).OnlyEnforceIf(b.Not())
            diff_bools.append(b)
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