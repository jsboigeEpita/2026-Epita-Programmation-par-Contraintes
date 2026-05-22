"""
instances.py
============
Génération d'instances synthétiques d'ordonnancement de blocs opératoires.

L'approche retenue suit les caractéristiques typiques de la littérature
hospitalière (Cardoen et al. 2010, Guerriero & Guido 2016) :

- mélange d'interventions électives et urgentes (≈ 20 % d'urgences) ;
- distribution log-normale des durées par spécialité ;
- spécialisation partielle des salles (deux à trois spécialités possibles
  par salle) ;
- chirurgiens monospécialistes ou bispécialistes ;
- pool d'équipements mobiles (microscope, robot, échographe) en nombre
  limité, partagés entre les salles.
"""

from __future__ import annotations

import random
from typing import List

from .models import Instance, Priority, Room, Surgeon, Surgery


SPECIALTIES = ["cardio", "ortho", "neuro", "general", "uro"]
EQUIPMENT_TYPES = ["microscope", "robot", "echo"]

# durée moyenne et écart-type en minutes par spécialité
_DURATION_PROFILE = {
    "cardio": (180, 45),
    "ortho": (120, 30),
    "neuro": (240, 60),
    "general": (75, 20),
    "uro": (90, 25),
}

# équipement le plus susceptible d'être requis pour chaque spécialité
_EQUIPMENT_HINT = {
    "cardio": ["echo"],
    "ortho": [],
    "neuro": ["microscope"],
    "general": [],
    "uro": ["robot"],
}


def generate_instance(
    n_surgeries: int = 12,
    n_rooms: int = 3,
    n_surgeons: int = 4,
    urgent_ratio: float = 0.2,
    horizon_minutes: int = 12 * 60,
    seed: int = 0,
) -> Instance:
    """
    Génère une instance synthétique reproductible.

    Parameters
    ----------
    n_surgeries : int
        Nombre d'interventions à planifier.
    n_rooms : int
        Nombre de salles d'opération.
    n_surgeons : int
        Nombre de chirurgiens.
    urgent_ratio : float
        Proportion d'urgences (avec deadline). Le reste est électif.
    horizon_minutes : int
        Horizon supérieur (minutes). Une journée standard = 12 h = 720 min.
    seed : int
        Graine du RNG pour la reproductibilité.

    Returns
    -------
    Instance
    """
    rng = random.Random(seed)

    n_spec_active = min(len(SPECIALTIES), max(2, n_rooms + 1))
    active_specs = SPECIALTIES[:n_spec_active]

    # ── Salles ─────────────────────────────────────────────────────────────
    rooms: List[Room] = []
    for rid in range(n_rooms):
        # chaque salle prend en charge 2 à 3 spécialités voisines
        first = rid % n_spec_active
        n_specs = rng.choice([2, 3])
        specs = [active_specs[(first + k) % n_spec_active] for k in range(n_specs)]
        rooms.append(
            Room(
                rid=rid,
                name=f"OR-{rid + 1}",
                specialties=sorted(set(specs)),
                clean_time=rng.choice([10, 15, 20]),
            )
        )

    # ── Chirurgiens ────────────────────────────────────────────────────────
    surgeons: List[Surgeon] = []
    for sid in range(n_surgeons):
        # mono ou bispécialiste
        first = sid % n_spec_active
        n_specs = rng.choice([1, 2])
        specs = [active_specs[(first + k) % n_spec_active] for k in range(n_specs)]
        shift_start = rng.choice([0, 0, 30])
        shift_end = horizon_minutes - rng.choice([0, 30, 60])
        surgeons.append(
            Surgeon(
                surg_id=sid,
                name=f"Dr-{sid + 1}",
                specialties=sorted(set(specs)),
                shift=(shift_start, shift_end),
            )
        )

    # garantir au moins un chirurgien par spécialité présente dans une salle
    rooms_specs = {s for r in rooms for s in r.specialties}
    for sp in rooms_specs:
        if not any(sp in sg.specialties for sg in surgeons):
            target = surgeons[rng.randrange(len(surgeons))]
            target.specialties = sorted(set(target.specialties) | {sp})

    # capacité chirurgien par spécialité (minutes disponibles)
    capacity_by_spec: dict[str, int] = {sp: 0 for sp in rooms_specs}
    for sg in surgeons:
        for sp in sg.specialties:
            if sp in capacity_by_spec:
                capacity_by_spec[sp] += sg.shift[1] - sg.shift[0]
    # capacité salle par spécialité
    room_capacity_by_spec: dict[str, int] = {sp: 0 for sp in rooms_specs}
    for r in rooms:
        for sp in r.specialties:
            room_capacity_by_spec[sp] += horizon_minutes
    # plafond effectif : on garde 50 % de la plus petite des deux capacités
    # (laisse de la marge pour les pertes liées à l'équipement partagé et aux
    # temps de nettoyage non pris en compte ici)
    spec_budget = {
        sp: int(0.5 * min(capacity_by_spec[sp], room_capacity_by_spec[sp]))
        for sp in rooms_specs
    }
    used_by_spec = {sp: 0 for sp in rooms_specs}

    # ── Chirurgies ─────────────────────────────────────────────────────────
    surgeries: List[Surgery] = []
    feasible_specs = sorted(rooms_specs)
    urgent_count_by_spec: dict[str, int] = {sp: 0 for sp in feasible_specs}
    # plafond d'urgences par spécialité : 2 si plusieurs chirurgiens, 1 sinon
    urgent_cap_by_spec = {
        sp: 2 if sum(1 for sg in surgeons if sp in sg.specialties) >= 2 else 1
        for sp in feasible_specs
    }
    for i in range(n_surgeries):
        # tirer la spécialité parmi celles encore en budget ;
        # fallback : la spécialité au plus grand budget restant
        eligible = [sp for sp in feasible_specs if used_by_spec[sp] < spec_budget[sp]]
        if not eligible:
            eligible = [max(feasible_specs, key=lambda sp: spec_budget[sp] - used_by_spec[sp])]
        spec = rng.choice(eligible)
        mu, sigma = _DURATION_PROFILE[spec]
        duration = max(30, int(rng.gauss(mu, sigma)))
        # plafonner la durée pour ne pas exploser le budget restant
        remaining = max(30, spec_budget[spec] - used_by_spec[spec])
        duration = min(duration, max(30, remaining))
        # discrétisation 5 min
        duration = (duration // 5) * 5
        used_by_spec[spec] += duration

        equipment = list(_EQUIPMENT_HINT.get(spec, []))
        if rng.random() < 0.15:
            equipment.append(rng.choice(EQUIPMENT_TYPES))
        equipment = sorted(set(equipment))

        # une chirurgie longue n'est pas marquée urgente : peu réaliste et
        # gênant pour la faisabilité.
        is_urgent = (
            rng.random() < urgent_ratio
            and urgent_count_by_spec[spec] < urgent_cap_by_spec[spec]
            and duration <= 150
        )
        if is_urgent:
            priority = Priority.URGENT
            # deadline généreuse : au moins 2·durée pour laisser la place à
            # une intervention en cours, dans la fenêtre [2 h, 4 h].
            deadline = max(2 * duration + 30, rng.choice([2 * 60, 3 * 60, 4 * 60]))
            release = 0
            urgent_count_by_spec[spec] += 1
        else:
            priority = Priority.ELECTIVE
            deadline = None
            release = rng.choice([0, 0, 0, 30, 60])

        # préférence pour un chirurgien compétent
        candidates = [sg.surg_id for sg in surgeons if spec in sg.specialties]
        preferred = rng.choice(candidates) if candidates and rng.random() < 0.5 else None

        surgeries.append(
            Surgery(
                sid=i,
                name=f"{spec}-{i + 1}",
                duration=duration,
                specialty=spec,
                equipment=equipment,
                priority=priority,
                deadline=deadline,
                preferred_surgeon=preferred,
                release=release,
            )
        )

    # ── Pool d'équipements ─────────────────────────────────────────────────
    equipment_pool = {eq: 1 for eq in EQUIPMENT_TYPES}
    # au moins une unité, mais on monte à 2 si la charge est forte
    for eq in EQUIPMENT_TYPES:
        demand = sum(1 for s in surgeries if eq in s.equipment)
        if demand > max(2, n_surgeries // 4):
            equipment_pool[eq] = 2

    return Instance(
        surgeries=surgeries,
        surgeons=surgeons,
        rooms=rooms,
        equipment_pool=equipment_pool,
        horizon=horizon_minutes,
    )


def format_instance(instance: Instance) -> str:
    """Résumé textuel d'une instance, utile en notebook."""
    lines = [
        f"Instance : {len(instance.surgeries)} chirurgies, "
        f"{len(instance.rooms)} salles, {len(instance.surgeons)} chirurgiens",
        f"Horizon  : {instance.horizon} min",
        f"Pool     : {instance.equipment_pool}",
        "",
        "Salles :",
    ]
    for r in instance.rooms:
        lines.append(
            f"  {r.name:6s}  specs={r.specialties}  clean={r.clean_time} min"
        )
    lines.append("Chirurgiens :")
    for sg in instance.surgeons:
        lines.append(
            f"  {sg.name:6s}  specs={sg.specialties}  shift={sg.shift}"
        )
    lines.append("Chirurgies :")
    for s in instance.surgeries:
        tag = "URG" if s.priority == Priority.URGENT else "   "
        dl = f"dl={s.deadline}" if s.deadline is not None else ""
        pref = f"pref=Dr-{s.preferred_surgeon + 1}" if s.preferred_surgeon is not None else ""
        eq = f"eq={s.equipment}" if s.equipment else ""
        extras = " ".join(x for x in [dl, pref, eq] if x)
        lines.append(
            f"  [{tag}] {s.name:14s} dur={s.duration:3d} rel={s.release:3d}  {extras}"
        )
    return "\n".join(lines)


__all__ = ["generate_instance", "format_instance", "SPECIALTIES", "EQUIPMENT_TYPES"]
