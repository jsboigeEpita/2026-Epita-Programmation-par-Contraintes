"""
heuristics.py
=============
Baselines pour comparer la qualité du modèle CP-SAT :

- ``solve_priority_rule`` : règle de dispatching gloutonne (urgence/deadline/durée).
- ``solve_simulated_annealing`` : recuit simulé sur la permutation des
  chirurgies, en réutilisant le décodeur glouton de la règle de priorité.
- ``schedule_objective`` : fonction d'objectif partagée (alignée sur CP-SAT)
  pour pouvoir comparer les trois solveurs sur la même métrique.
"""

from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Optional, Tuple

from .cp_solver import ALPHA_MAKESPAN, BETA_WAIT, GAMMA_PREF
from .models import Assignment, Instance, Priority, ScheduleResult


def _compatible_rooms(instance: Instance, sid: int) -> List[int]:
    s = instance.surgeries[sid]
    return [r.rid for r in instance.rooms if s.specialty in r.specialties]


def _compatible_surgeons(instance: Instance, sid: int) -> List[int]:
    s = instance.surgeries[sid]
    return [sg.surg_id for sg in instance.surgeons if s.specialty in sg.specialties]


def _decode_permutation(
    instance: Instance, order: List[int]
) -> Optional[List[Assignment]]:
    """
    Décodeur glouton : pour chaque chirurgie dans l'ordre donné, on choisit
    le couple (salle, chirurgien) qui permet de démarrer au plus tôt.

    Renvoie ``None`` si une chirurgie ne peut être placée (violation d'une
    deadline ou d'un shift).
    """
    rooms_by_id = {r.rid: r for r in instance.rooms}
    surgeons_by_id = {sg.surg_id: sg for sg in instance.surgeons}

    # disponibilité par ressource (instant de prochaine dispo)
    room_free: Dict[int, int] = {r.rid: 0 for r in instance.rooms}
    surg_free: Dict[int, int] = {sg.surg_id: sg.shift[0] for sg in instance.surgeons}

    # pour les équipements partagés : liste des intervalles déjà occupés
    eq_occupancy: Dict[str, List[Tuple[int, int]]] = {
        eq: [] for eq in instance.equipment_pool
    }

    def equipment_earliest(eq_type: str, dur: int, t_min: int, capacity: int) -> int:
        """Premier instant ≥ t_min permettant d'insérer un intervalle [t, t+dur]
        sans dépasser ``capacity`` du pool. Méthode par balayage."""
        if capacity <= 0:
            return math.inf
        events = []
        for a, b in eq_occupancy[eq_type]:
            events.append((a, +1))
            events.append((b, -1))
        events.sort()
        # on cherche un slot où la charge reste < capacity pendant dur minutes
        # en partant de t_min. Approche : tester t = t_min puis chaque évènement.
        candidates = [t_min] + [t for t, _ in events if t >= t_min]
        for t in sorted(set(candidates)):
            load = sum(1 for a, b in eq_occupancy[eq_type] if a <= t < b)
            if load >= capacity:
                continue
            # vérifier que sur [t, t+dur] on ne dépasse pas
            ok = True
            for a, b in eq_occupancy[eq_type]:
                if a >= t + dur or b <= t:
                    continue
                # chevauchement : il faut compter les chevauchements simultanés
                # en début de fenêtre — déjà ≥ capacity bloquerait
                # on recalcule la charge max sur la fenêtre
                pass
            # calcul correct du max load sur [t, t+dur]
            max_load = 0
            grid = sorted({t, t + dur} | {a for a, _ in eq_occupancy[eq_type]}
                          | {b for _, b in eq_occupancy[eq_type]})
            for g in grid:
                if g < t or g >= t + dur:
                    continue
                load_g = sum(1 for a, b in eq_occupancy[eq_type] if a <= g < b)
                if load_g + 1 > capacity:
                    max_load = capacity + 1
                    break
                max_load = max(max_load, load_g + 1)
            if max_load <= capacity:
                ok = True
            else:
                ok = False
            if ok:
                return t
        return math.inf

    # exclusivité d'une salle pour une spécialité « autre » que celle traitée :
    # pour chaque spécialité σ, si une seule salle la prend en charge alors
    # toute salle compatible avec σ paie un coût d'opportunité à être utilisée
    # par une autre spécialité (on bloque la seule ressource cardio en cas
    # d'usage par de l'ortho, par exemple).
    specs_by_room: Dict[str, List[int]] = {}
    for r in instance.rooms:
        for sp in r.specialties:
            specs_by_room.setdefault(sp, []).append(r.rid)

    def room_opportunity_cost(rid: int, current_spec: str) -> int:
        room = rooms_by_id[rid]
        cost = 0
        for sp in room.specialties:
            if sp == current_spec:
                continue
            if len(specs_by_room.get(sp, [])) == 1:
                cost += 1
        return cost

    # idem pour les chirurgiens (préférer les chirurgiens « passe-partout » à
    # spécialité égale pour les autres chirurgiens monospécialistes).
    specs_by_surgeon: Dict[str, List[int]] = {}
    for sg in instance.surgeons:
        for sp in sg.specialties:
            specs_by_surgeon.setdefault(sp, []).append(sg.surg_id)

    def surgeon_opportunity_cost(sg_id: int, current_spec: str) -> int:
        sg = surgeons_by_id[sg_id]
        cost = 0
        for sp in sg.specialties:
            if sp == current_spec:
                continue
            if len(specs_by_surgeon.get(sp, [])) == 1:
                cost += 1
        return cost

    # pénalité en minutes par unité de coût d'opportunité — assez forte pour
    # peser face à un écart de start raisonnable, mais pas écrasante.
    OPP_WEIGHT = 60

    assignments: List[Assignment] = []

    for sid in order:
        s = instance.surgeries[sid]
        best: Optional[Tuple[int, int, int]] = None  # (start, room, surgeon)
        best_tiebreak: Tuple[int, int, int] = (10**9, 10**9, 10**9)

        # préférer le chirurgien favori en cas d'égalité
        candidates_surg = _compatible_surgeons(instance, sid)
        if s.preferred_surgeon in candidates_surg:
            # place le préféré en tête : ne change pas le start mais cassera
            # les égalités en sa faveur
            candidates_surg = ([s.preferred_surgeon]
                               + [x for x in candidates_surg if x != s.preferred_surgeon])

        for rid in _compatible_rooms(instance, sid):
            room = rooms_by_id[rid]
            for sg_id in candidates_surg:
                sg = surgeons_by_id[sg_id]
                t = max(s.release, room_free[rid], surg_free[sg_id], sg.shift[0])
                # respect équipements
                for eq in s.equipment:
                    cap = instance.equipment_pool.get(eq, 0)
                    t = max(t, equipment_earliest(eq, s.duration, t, cap))
                if t == math.inf:
                    continue
                # respect shift et deadline
                if t + s.duration > sg.shift[1]:
                    continue
                if s.deadline is not None and t > s.deadline:
                    continue
                if t + s.duration > instance.horizon:
                    continue
                # score = start + W * coût d'opportunité (libérer les
                # ressources « exclusives » pour les spécialités qui en dépendent)
                score = (
                    t
                    + OPP_WEIGHT * room_opportunity_cost(rid, s.specialty)
                    + OPP_WEIGHT * surgeon_opportunity_cost(sg_id, s.specialty)
                )
                tiebreak = (score, t, len(rooms_by_id[rid].specialties))
                if best is None or tiebreak < best_tiebreak:
                    best = (t, rid, sg_id)
                    best_tiebreak = tiebreak
        if best is None:
            return None
        t_star, room_pick, surg_pick = best
        assignments.append(
            Assignment(
                sid=sid,
                start=t_star,
                end=t_star + s.duration,
                room=room_pick,
                surgeon=surg_pick,
            )
        )
        clean = rooms_by_id[room_pick].clean_time
        room_free[room_pick] = t_star + s.duration + clean
        surg_free[surg_pick] = t_star + s.duration
        for eq in s.equipment:
            eq_occupancy[eq].append((t_star, t_star + s.duration))

    return assignments


def schedule_objective(
    assignments: List[Assignment],
    instance: Instance,
    alpha: int = ALPHA_MAKESPAN,
    beta: int = BETA_WAIT,
    gamma: int = GAMMA_PREF,
) -> Tuple[float, int, int]:
    """Calcule (objectif, makespan, attente pondérée) d'un planning donné."""
    if not assignments:
        return float("inf"), 0, 0
    makespan = max(a.end for a in assignments)
    wait = sum(
        int(instance.surgeries[a.sid].priority) * (a.start - instance.surgeries[a.sid].release)
        for a in assignments
    )
    pref_pen = 0
    for a in assignments:
        s = instance.surgeries[a.sid]
        if s.preferred_surgeon is None:
            continue
        if s.preferred_surgeon != a.surgeon:
            pref_pen += 1
    obj = alpha * makespan + beta * wait + gamma * pref_pen
    return float(obj), makespan, wait


# ─────────────────────────────────────────────────────────────────────────────
# Règle de priorité
# ─────────────────────────────────────────────────────────────────────────────

def solve_priority_rule(
    instance: Instance,
    n_restarts: int = 12,
    seed: int = 0,
) -> ScheduleResult:
    """
    Heuristique multi-règles avec restarts aléatoires.

    Plusieurs règles classiques (EDD, EDD-SPT, EDD-LPT, FCFS) sont tentées,
    suivies de quelques perturbations aléatoires de l'ordre EDD. La meilleure
    solution faisable trouvée est renvoyée.
    """
    t0 = time.perf_counter()
    rng = random.Random(seed)

    def edd_spt(s):
        prio = -int(s.priority)
        dl = s.deadline if s.deadline is not None else s.release + 10**6
        return (prio, dl, s.duration, s.sid)

    def edd_lpt(s):
        prio = -int(s.priority)
        dl = s.deadline if s.deadline is not None else s.release + 10**6
        return (prio, dl, -s.duration, s.sid)

    def fcfs(s):
        prio = -int(s.priority)
        return (prio, s.release, s.duration, s.sid)

    orders: List[List[int]] = []
    for key in (edd_spt, edd_lpt, fcfs):
        orders.append([s.sid for s in sorted(instance.surgeries, key=key)])

    # restarts : on permute légèrement les électifs autour de l'ordre EDD-SPT
    base = orders[0]
    for _ in range(n_restarts):
        cand = base[:]
        n = len(cand)
        for _swap in range(rng.randint(1, max(1, n // 3))):
            i, j = rng.sample(range(n), 2)
            cand[i], cand[j] = cand[j], cand[i]
        orders.append(cand)

    best: Optional[List[Assignment]] = None
    best_obj = float("inf")
    for order in orders:
        a = _decode_permutation(instance, order)
        if a is None:
            continue
        obj, _, _ = schedule_objective(a, instance)
        if obj < best_obj:
            best_obj = obj
            best = a

    elapsed = (time.perf_counter() - t0) * 1000
    if best is None:
        return ScheduleResult(
            status="INFEASIBLE",
            assignments=[],
            makespan=0,
            total_wait=0,
            objective=float("inf"),
            solver="priority",
            solve_ms=elapsed,
        )
    obj, ms, wait = schedule_objective(best, instance)
    return ScheduleResult(
        status="FEASIBLE",
        assignments=best,
        makespan=ms,
        total_wait=wait,
        objective=obj,
        solver="priority",
        solve_ms=elapsed,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Recuit simulé
# ─────────────────────────────────────────────────────────────────────────────

def _random_neighbor(order: List[int], rng: random.Random) -> List[int]:
    new = order[:]
    n = len(new)
    if rng.random() < 0.5:
        # swap
        i, j = rng.sample(range(n), 2)
        new[i], new[j] = new[j], new[i]
    else:
        # relocation
        i = rng.randrange(n)
        j = rng.randrange(n)
        x = new.pop(i)
        new.insert(j, x)
    return new


def solve_simulated_annealing(
    instance: Instance,
    n_iter: int = 5000,
    T0: float = 200.0,
    Tend: float = 0.5,
    seed: int = 0,
) -> ScheduleResult:
    """
    Recuit simulé sur la permutation des chirurgies.

    Le décodage est celui de la règle de priorité. La permutation initiale est
    celle de la règle de priorité statique, qui sert également de meilleure
    solution initiale.
    """
    t0 = time.perf_counter()
    rng = random.Random(seed)

    # init : règle de priorité ; en cas d'échec on tente des permutations
    # aléatoires jusqu'à en obtenir une faisable (budget 200 essais).
    init = solve_priority_rule(instance, seed=seed)
    if init.status == "INFEASIBLE":
        ids = [s.sid for s in instance.surgeries]
        decoded = None
        for _ in range(200):
            cand = ids[:]
            rng.shuffle(cand)
            decoded = _decode_permutation(instance, cand)
            if decoded is not None:
                break
        if decoded is None:
            return ScheduleResult(
                status="INFEASIBLE",
                assignments=[],
                makespan=0,
                total_wait=0,
                objective=float("inf"),
                solver="sa",
                solve_ms=(time.perf_counter() - t0) * 1000,
            )
        best_assign = decoded
        best_obj = schedule_objective(decoded, instance)[0]
        order = [a.sid for a in sorted(decoded, key=lambda a: (a.start, a.sid))]
    else:
        order = [a.sid for a in sorted(init.assignments, key=lambda a: (a.start, a.sid))]
        best_assign = init.assignments
        best_obj = init.objective
    cur_order = order
    cur_obj = best_obj

    alpha_cool = (Tend / T0) ** (1.0 / max(1, n_iter))
    T = T0

    for _ in range(n_iter):
        cand = _random_neighbor(cur_order, rng)
        decoded = _decode_permutation(instance, cand)
        if decoded is None:
            T *= alpha_cool
            continue
        cand_obj, _, _ = schedule_objective(decoded, instance)
        delta = cand_obj - cur_obj
        if delta < 0 or rng.random() < math.exp(-delta / max(T, 1e-9)):
            cur_order = cand
            cur_obj = cand_obj
            if cand_obj < best_obj:
                best_obj = cand_obj
                best_assign = decoded
        T *= alpha_cool

    elapsed = (time.perf_counter() - t0) * 1000
    obj, ms, wait = schedule_objective(best_assign, instance)
    return ScheduleResult(
        status="FEASIBLE",
        assignments=best_assign,
        makespan=ms,
        total_wait=wait,
        objective=obj,
        solver="sa",
        solve_ms=elapsed,
    )


__all__ = [
    "solve_priority_rule",
    "solve_simulated_annealing",
    "schedule_objective",
]
