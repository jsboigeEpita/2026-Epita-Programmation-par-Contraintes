from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import time

from src.core.graph import KEPGraph



@dataclass
class SolverResult:
    """
    Résultat standardisé retourné par tous les solveurs KEP.

    Attributes:
        status          : 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'TIMEOUT' | 'ERROR'
        cycles          : Cycles sélectionnés (listes d'ids de paires).
        chains          : Chaînes altruistes sélectionnées.
        n_transplants   : Nombre total de transplantations réalisées.
        objective_value : Valeur de la fonction objectif (poids total).
        wall_time       : Temps de résolution en secondes.
        solver_name     : Nom du solveur utilisé.
        metadata        : Informations supplémentaires (spécifiques au solveur).
    """
    status: str
    cycles: list[list[int]] = field(default_factory=list)
    chains: list[list[int]] = field(default_factory=list)
    n_transplants: int = 0
    objective_value: float = 0.0
    wall_time: float = 0.0
    solver_name: str = "unknown"
    metadata: dict = field(default_factory=dict)

    def is_feasible(self) -> bool:
        """True si le solveur a trouvé au moins une solution valide."""
        return self.status in ("OPTIMAL", "FEASIBLE")

    def summary(self) -> str:
        """Résumé lisible pour l'affichage console."""
        lines = [
            f"=== {self.solver_name} ===",
            f"  Status         : {self.status}",
            f"  Transplants    : {self.n_transplants}",
            f"  Cycles         : {len(self.cycles)}  → {self.cycles}",
            f"  Chains         : {len(self.chains)}  → {self.chains}",
            f"  Objective      : {self.objective_value:.4f}",
            f"  Wall time      : {self.wall_time:.4f}s",
        ]
        if self.metadata:
            for k, v in self.metadata.items():
                lines.append(f"  {k:20s}: {v}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Sérialisation pour export JSON / DataFrame."""
        return {
            "solver": self.solver_name,
            "status": self.status,
            "n_transplants": self.n_transplants,
            "n_cycles": len(self.cycles),
            "n_chains": len(self.chains),
            "objective_value": round(self.objective_value, 4),
            "wall_time_s": round(self.wall_time, 6),
            "cycles": self.cycles,
            "chains": self.chains,
            **self.metadata,
        }



class KidneyExchangeSolver(ABC):
    """
    Interface commune pour tous les solveurs du Kidney Exchange Problem.

    Sous-classes concrètes :
        - CPSatSolver  (models/cpsat_model.py)
        - PLNESolver   (models/PLNE.py)
        - GreedySolver (models/greedy.py)

    Usage type :
        solver = CPSatSolver(graph, max_cycle_size=3)
        result = solver.solve(time_limit=60.0)
        print(result.summary())
    """

    def __init__(self, graph: KEPGraph, max_cycle_size: int = 3):
        """
        Args:
            graph          : Graphe KEP pré-construit (avec arcs de compatibilité).
            max_cycle_size : Taille maximale des cycles autorisés.
        """
        self.graph = graph
        self.max_cycle_size = max_cycle_size
        self._result: Optional[SolverResult] = None
        self.altruist_enabled: bool = False  # Activer via enable_altruists()

    def enable_altruists(self) -> "KidneyExchangeSolver":
        """Active la prise en compte des chaînes altruistes (NDD). Retourne self."""
        self.altruist_enabled = True
        return self


    @abstractmethod
    def solve(self, time_limit: float = 60.0) -> SolverResult:
        """
        Lance la résolution et retourne un SolverResult.

        Args:
            time_limit : Temps maximum de résolution en secondes.

        Returns:
            SolverResult avec la meilleure solution trouvée.
        """
        ...

    @property
    def name(self) -> str:
        """Nom court du solveur (pour les rapports et graphiques)."""
        return self.__class__.__name__

    @property
    def last_result(self) -> Optional[SolverResult]:
        """Dernier résultat calculé (None si solve() jamais appelé)."""
        return self._result


    def _start_timer(self) -> float:
        """Démarre le chronomètre. Retourne le timestamp de départ."""
        return time.perf_counter()

    def _elapsed(self, start: float) -> float:
        """Retourne le temps écoulé depuis start en secondes."""
        return time.perf_counter() - start

    def _make_result(
        self,
        status: str,
        cycles: list[list[int]],
        chains: list[list[int]],
        objective_value: float,
        wall_time: float,
        **metadata,
    ) -> SolverResult:
        """Construit et mémorise un SolverResult standardisé."""
        n_transplants = (
            sum(len(c) for c in cycles)
            + sum(len(c) - 1 for c in chains)   # le NDD ne reçoit pas de rein
        )
        result = SolverResult(
            status=status,
            cycles=cycles,
            chains=chains,
            n_transplants=n_transplants,
            objective_value=objective_value,
            wall_time=wall_time,
            solver_name=self.name,
            metadata=metadata,
        )
        self._result = result
        return result

    def _no_solution(self, status: str, wall_time: float) -> SolverResult:
        """Résultat vide pour les cas INFEASIBLE / TIMEOUT / ERROR."""
        return self._make_result(
            status=status,
            cycles=[],
            chains=[],
            objective_value=0.0,
            wall_time=wall_time,
        )

    def __repr__(self) -> str:
        return (
            f"{self.name}("
            f"max_cycle={self.max_cycle_size}, "
            f"altruists={self.altruist_enabled}, "
            f"graph={self.graph})"
        )
