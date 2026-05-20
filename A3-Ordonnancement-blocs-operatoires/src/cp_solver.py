"""
cp_solver.py
============
Modèle CP-SAT (Google OR-Tools) pour l'ordonnancement de blocs opératoires.

Formulation
-----------
Pour chaque chirurgie *i* on introduit :

- ``start_i`` ∈ [release_i, horizon]   (entier)
- ``end_i = start_i + duration_i``
- ``interval_i = IntervalVar(start_i, duration_i, end_i)``
- ``room_i`` ∈ rooms compatibles avec la spécialité
- ``surg_i`` ∈ chirurgiens compatibles
- optional intervals ``room_present_{i,r}`` et ``surg_present_{i,s}``
  utilisés pour les contraintes ``NoOverlap`` et ``Cumulative``.

Contraintes dures :

1. **NoOverlap par salle** sur des intervalles élargis (durée + nettoyage),
   via ``AddNoOverlap`` sur les intervalles optionnels présents.
2. **Cumulative capacité 1 par chirurgien** sur les intervalles optionnels
   présents — implémente *un chirurgien sert une seule intervention à la fois*
   tout en supportant la sélection multi-chirurgien.
3. **Cumulative par équipement** : la somme des demandes simultanées d'un
   type donné ne dépasse pas le nombre d'unités du pool.
4. **Deadline urgences** : ``start_i ≤ deadline_i`` si urgence.
5. **Shift chirurgiens** : intervalle inclus dans la fenêtre de présence.

Objectif (soft) :

    minimize  α·makespan + β·Σ_i w_i · (start_i − release_i)
              + γ·Σ_i pref_penalty_i

où *w_i* = priorité (URGENT > ELECTIVE) et *pref_penalty_i* = 1 si le
chirurgien préféré n'est pas affecté.
"""

from __future__ import annotations

import time
from typing import Dict, List, Tuple

from ortools.sat.python import cp_model

from .models import Assignment, Instance, Priority, ScheduleResult


# Poids par défaut de l'objectif (exposés pour le notebook).
ALPHA_MAKESPAN = 1
BETA_WAIT = 1
GAMMA_PREF = 30


def solve_cp_sat(
    instance: Instance,
    time_limit_s: float = 10.0,
    alpha: int = ALPHA_MAKESPAN,
    beta: int = BETA_WAIT,
    gamma: int = GAMMA_PREF,
    log_search: bool = False,
) -> ScheduleResult:
    """
    Résout une instance par CP-SAT.

    Parameters
    ----------
    instance : Instance
    time_limit_s : float
        Borne de temps CPU (secondes).
    alpha, beta, gamma : int
        Poids des trois termes de l'objectif (entiers, CP-SAT n'aime pas les
        flottants dans la fonction objectif).
    log_search : bool
        Active la trace de CP-SAT (utile en debug, très verbeux).

    Returns
    -------
    ScheduleResult
    """
    t0 = time.perf_counter()

    model = cp_model.CpModel()
    H = instance.horizon

    # Pré-calculs : compatibilités salle/chirurgien par chirurgie
    rooms_by_id = {r.rid: r for r in instance.rooms}
    surgeons_by_id = {sg.surg_id: sg for sg in instance.surgeons}

    compat_rooms: Dict[int, List[int]] = {}
    compat_surgeons: Dict[int, List[int]] = {}
    for s in instance.surgeries:
        compat_rooms[s.sid] = [r.rid for r in instance.rooms if s.specialty in r.specialties]
        compat_surgeons[s.sid] = [
            sg.surg_id for sg in instance.surgeons if s.specialty in sg.specialties
        ]
        if not compat_rooms[s.sid]:
            raise ValueError(f"Chirurgie {s.name} : aucune salle compatible.")
        if not compat_surgeons[s.sid]:
            raise ValueError(f"Chirurgie {s.name} : aucun chirurgien compatible.")

    # ── Variables principales ──────────────────────────────────────────────
    start, end, interval = {}, {}, {}
    for s in instance.surgeries:
        latest_start = H - s.duration
        if s.deadline is not None:
            latest_start = min(latest_start, s.deadline)
        start[s.sid] = model.NewIntVar(s.release, max(s.release, latest_start), f"start_{s.sid}")
        end[s.sid] = model.NewIntVar(s.release + s.duration, H, f"end_{s.sid}")
        interval[s.sid] = model.NewIntervalVar(
            start[s.sid], s.duration, end[s.sid], f"itv_{s.sid}"
        )

    # ── Assignation salle (par intervalles optionnels élargis du clean) ────
    room_assigned: Dict[Tuple[int, int], cp_model.IntVar] = {}
    room_intervals_by_room: Dict[int, list] = {r.rid: [] for r in instance.rooms}

    for s in instance.surgeries:
        bools_for_s = []
        for rid in compat_rooms[s.sid]:
            room = rooms_by_id[rid]
            present = model.NewBoolVar(f"room_{s.sid}_{rid}")
            room_assigned[(s.sid, rid)] = present
            bools_for_s.append(present)
            # intervalle élargi (durée + nettoyage) pour NoOverlap
            extended_end = model.NewIntVar(
                s.release + s.duration, H + room.clean_time, f"endR_{s.sid}_{rid}"
            )
            model.Add(extended_end == end[s.sid] + room.clean_time).OnlyEnforceIf(present)
            opt_itv = model.NewOptionalIntervalVar(
                start[s.sid],
                s.duration + room.clean_time,
                extended_end,
                present,
                f"itvR_{s.sid}_{rid}",
            )
            room_intervals_by_room[rid].append(opt_itv)
        model.AddExactlyOne(bools_for_s)

    # ── Assignation chirurgien (capacité 1 via Cumulative) ─────────────────
    surg_assigned: Dict[Tuple[int, int], cp_model.IntVar] = {}
    surg_intervals_by_surgeon: Dict[int, list] = {sg.surg_id: [] for sg in instance.surgeons}

    for s in instance.surgeries:
        bools_for_s = []
        for sid in compat_surgeons[s.sid]:
            sg = surgeons_by_id[sid]
            present = model.NewBoolVar(f"surg_{s.sid}_{sid}")
            surg_assigned[(s.sid, sid)] = present
            bools_for_s.append(present)
            opt_itv = model.NewOptionalIntervalVar(
                start[s.sid], s.duration, end[s.sid], present, f"itvS_{s.sid}_{sid}"
            )
            surg_intervals_by_surgeon[sid].append(opt_itv)
            # fenêtre de présence
            model.Add(start[s.sid] >= sg.shift[0]).OnlyEnforceIf(present)
            model.Add(end[s.sid] <= sg.shift[1]).OnlyEnforceIf(present)
        model.AddExactlyOne(bools_for_s)

    # ── Contraintes de ressource ───────────────────────────────────────────
    for rid, itvs in room_intervals_by_room.items():
        if itvs:
            model.AddNoOverlap(itvs)

    for sid, itvs in surg_intervals_by_surgeon.items():
        if itvs:
            model.AddCumulative(itvs, [1] * len(itvs), 1)

    # ── Équipements partagés (Cumulative) ──────────────────────────────────
    for eq_type, capacity in instance.equipment_pool.items():
        eq_intervals = []
        eq_demands = []
        for s in instance.surgeries:
            if eq_type in s.equipment:
                eq_intervals.append(interval[s.sid])
                eq_demands.append(1)
        if eq_intervals:
            model.AddCumulative(eq_intervals, eq_demands, capacity)

    # ── Makespan ───────────────────────────────────────────────────────────
    makespan = model.NewIntVar(0, H, "makespan")
    model.AddMaxEquality(makespan, [end[s.sid] for s in instance.surgeries])

    # ── Pénalité de préférence chirurgien ─────────────────────────────────
    pref_penalties = []
    for s in instance.surgeries:
        if s.preferred_surgeon is None:
            continue
        if (s.sid, s.preferred_surgeon) not in surg_assigned:
            # chirurgien préféré incompatible : pénalité fixe = 1
            pref_penalties.append(model.NewConstant(1))
            continue
        pen = model.NewBoolVar(f"pref_pen_{s.sid}")
        # pen = 1 - surg_assigned[i, preferred]
        model.Add(pen + surg_assigned[(s.sid, s.preferred_surgeon)] == 1)
        pref_penalties.append(pen)

    # ── Temps d'attente pondéré par priorité ──────────────────────────────
    wait_terms = []
    for s in instance.surgeries:
        wait = model.NewIntVar(0, H, f"wait_{s.sid}")
        model.Add(wait == start[s.sid] - s.release)
        wait_terms.append(int(s.priority) * wait)

    obj_terms = [alpha * makespan]
    if wait_terms:
        obj_terms.append(beta * sum(wait_terms))
    if pref_penalties:
        obj_terms.append(gamma * sum(pref_penalties))
    model.Minimize(sum(obj_terms))

    # ── Résolution ─────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = log_search

    status = solver.Solve(model)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    status_name = solver.StatusName(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ScheduleResult(
            status=status_name,
            assignments=[],
            makespan=0,
            total_wait=0,
            objective=float("inf"),
            solver="cp_sat",
            solve_ms=elapsed_ms,
        )

    assignments: List[Assignment] = []
    for s in instance.surgeries:
        room_pick = next(
            rid for rid in compat_rooms[s.sid] if solver.Value(room_assigned[(s.sid, rid)])
        )
        surg_pick = next(
            sid for sid in compat_surgeons[s.sid] if solver.Value(surg_assigned[(s.sid, sid)])
        )
        assignments.append(
            Assignment(
                sid=s.sid,
                start=int(solver.Value(start[s.sid])),
                end=int(solver.Value(end[s.sid])),
                room=room_pick,
                surgeon=surg_pick,
            )
        )

    ms_val = int(solver.Value(makespan))
    wait_val = sum(int(s.priority) * (a.start - instance.surgeries[a.sid].release)
                   for a in assignments)

    return ScheduleResult(
        status=status_name,
        assignments=assignments,
        makespan=ms_val,
        total_wait=wait_val,
        objective=float(solver.ObjectiveValue()),
        solver="cp_sat",
        solve_ms=elapsed_ms,
    )


__all__ = ["solve_cp_sat", "ALPHA_MAKESPAN", "BETA_WAIT", "GAMMA_PREF"]
