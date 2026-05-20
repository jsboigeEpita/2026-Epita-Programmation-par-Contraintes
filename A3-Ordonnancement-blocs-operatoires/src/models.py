"""
models.py
=========
Structures de données partagées par tous les modules du projet A3.

Le bloc opératoire est modélisé comme un ensemble de chirurgies à planifier
sur un horizon journalier (en minutes), à exécuter sur un parc de salles
d'opération et un effectif de chirurgiens compétents.

Classes
-------
Priority
    Niveau d'urgence d'une intervention (URGENT, ELECTIVE).
Surgery
    Une intervention à planifier (durée, spécialité, chirurgiens habilités,
    équipements requis, deadline éventuelle, chirurgien préféré).
Surgeon
    Profil d'un chirurgien (spécialités maîtrisées, fenêtre de disponibilité).
Room
    Salle d'opération (équipements fixes, temps de nettoyage entre interventions).
EquipmentPool
    Pool d'équipements mobiles partagés (microscope, robot, etc.).
Instance
    Instance complète du problème.
Assignment
    Décision de planification pour une chirurgie (start, salle, chirurgien).
ScheduleResult
    Résultat d'une procédure d'optimisation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple


class Priority(IntEnum):
    """Niveau d'urgence. La valeur sert directement de poids dans l'objectif."""

    ELECTIVE = 1
    URGENT = 5


@dataclass
class Surgery:
    """
    Une intervention chirurgicale à planifier.

    Parameters
    ----------
    sid : int
        Identifiant unique (0-indexé).
    name : str
        Libellé lisible (ex. ``"appendicectomie-3"``).
    duration : int
        Durée en minutes (préparation + acte + réveil immédiat).
    specialty : str
        Spécialité requise (``"cardio"``, ``"ortho"``…). Filtre les chirurgiens.
    equipment : list of str
        Types d'équipement mobile nécessaires en parallèle de l'opération.
    priority : Priority
        Niveau d'urgence. Influe sur le poids du temps d'attente dans l'objectif.
    deadline : Optional[int]
        Pour les urgences : instant limite (minutes depuis 0) avant lequel
        l'intervention doit avoir démarré. ``None`` sinon.
    preferred_surgeon : Optional[int]
        Identifiant du chirurgien souhaité (soft constraint). ``None`` si
        aucune préférence.
    release : int
        Instant minimal de démarrage (patient prêt). Par défaut 0.
    """

    sid: int
    name: str
    duration: int
    specialty: str
    equipment: List[str] = field(default_factory=list)
    priority: Priority = Priority.ELECTIVE
    deadline: Optional[int] = None
    preferred_surgeon: Optional[int] = None
    release: int = 0


@dataclass
class Surgeon:
    """
    Profil d'un chirurgien.

    Parameters
    ----------
    surg_id : int
        Identifiant.
    name : str
        Libellé lisible.
    specialties : list of str
        Spécialités maîtrisées. Une chirurgie *i* ne peut être affectée à un
        chirurgien que si ``i.specialty`` figure dans cette liste.
    shift : tuple[int, int]
        Fenêtre de présence ``(start, end)`` en minutes depuis l'origine.
    """

    surg_id: int
    name: str
    specialties: List[str]
    shift: Tuple[int, int]


@dataclass
class Room:
    """
    Salle d'opération.

    Parameters
    ----------
    rid : int
        Identifiant.
    name : str
        Libellé (ex. ``"OR-1"``).
    specialties : list of str
        Spécialités possibles dans cette salle (équipement fixe). Une
        chirurgie ne peut s'y dérouler que si sa spécialité y figure.
    clean_time : int
        Temps de nettoyage / décontamination ajouté après chaque intervention
        (minutes).
    """

    rid: int
    name: str
    specialties: List[str]
    clean_time: int = 15


@dataclass
class Instance:
    """
    Instance complète du problème d'ordonnancement.

    Parameters
    ----------
    surgeries : list of Surgery
    surgeons : list of Surgeon
    rooms : list of Room
    equipment_pool : dict[str, int]
        Pour chaque type d'équipement mobile, le nombre d'unités disponibles.
    horizon : int
        Borne supérieure sur la durée totale (minutes). Le solveur peut viser
        un makespan inférieur ; ``horizon`` sert d'horizon pour les variables.
    """

    surgeries: List[Surgery]
    surgeons: List[Surgeon]
    rooms: List[Room]
    equipment_pool: Dict[str, int]
    horizon: int


@dataclass
class Assignment:
    """Décision de planification pour une chirurgie."""

    sid: int
    start: int
    end: int
    room: int
    surgeon: int


@dataclass
class ScheduleResult:
    """
    Résultat d'une procédure d'optimisation.

    Parameters
    ----------
    status : str
        ``"OPTIMAL"``, ``"FEASIBLE"``, ``"INFEASIBLE"`` ou ``"UNKNOWN"``.
    assignments : list of Assignment
        Une décision par chirurgie planifiée. Vide si infeasible.
    makespan : int
        Instant de fin du dernier acte (minutes).
    total_wait : int
        Somme pondérée (start − release) × priorité.
    objective : float
        Valeur de l'objectif tel que défini par le solveur appelé.
    solver : str
        Identifiant : ``"cp_sat"``, ``"priority"``, ``"sa"``.
    solve_ms : float
        Temps de résolution en millisecondes.
    """

    status: str
    assignments: List[Assignment]
    makespan: int
    total_wait: int
    objective: float
    solver: str
    solve_ms: float


__all__ = [
    "Priority",
    "Surgery",
    "Surgeon",
    "Room",
    "Instance",
    "Assignment",
    "ScheduleResult",
]
