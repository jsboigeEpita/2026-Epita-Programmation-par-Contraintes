from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import networkx as nx

@dataclass
class Donor:
    id: int
    blood_type: str
    hla_antigens: list[str]


@dataclass
class Patient:
    id: int
    blood_type: str
    pra: float                  # Panel Reactive Antibodies [0, 1]
    hla_antibodies: list[str]
    time_on_dialysis: int       # en mois


@dataclass
class Pair:
    """
    Une paire patient-donneur incompatible.
    Pour un donneur altruiste (NDD), patient vaut None.
    """
    id: int
    patient: Optional[Patient]
    donor: Donor
    is_altruistic: bool = False  # NDD : donneur sans patient associé


class KEPGraph:
    """
    Graphe orienté représentant le Kidney Exchange Problem.

    Nœuds  : paires patient-donneur.
    Arcs   : compatibilité du donneur de i vers le patient de j,
             avec un poids reflétant la qualité de la compatibilité.
    """

    def __init__(self, max_cycle_size: int = 3, max_chain_length: int = 3):
        self.pairs: list[Pair] = []
        self._pair_index: dict[int, Pair] = {}   # CORRECTION : accès O(1) par id
        self.graph = nx.DiGraph()
        self.max_cycle_size = max_cycle_size
        self.max_chain_length = max_chain_length


    def add_pair(self, pair: Pair) -> None:
        """Ajoute une paire (ou NDD) au graphe."""
        self.pairs.append(pair)
        self._pair_index[pair.id] = pair          # CORRECTION : mise à jour de l'index
        self.graph.add_node(pair.id, pair=pair)

    def build_compatibility_arcs(self, compatibility_checker) -> None:
        """
        Construit les arcs selon les règles de compatibilité.
        """
        for i in self.pairs:
            for j in self.pairs:
                if i.id == j.id:
                    continue
                if j.is_altruistic:
                    continue
                if i.is_altruistic:
                    weight = compatibility_checker.check(i.donor, j.patient)
                    if weight > 0:
                        self.graph.add_edge(i.id, j.id, weight=weight)
                else:
                    weight = compatibility_checker.check(i.donor, j.patient)
                    if weight > 0:
                        self.graph.add_edge(i.id, j.id, weight=weight)



    def get_valid_cycles(self) -> list[list[int]]:
        """
        Énumère tous les cycles simples de taille 2 ≤ k ≤ max_cycle_size
        ne passant que par des nœuds non-altruistes.
        """
        # Sous-graphe sans les NDD
        non_ndd = [p.id for p in self.pairs if not p.is_altruistic]
        subgraph = self.graph.subgraph(non_ndd)

        cycles = []
        for cycle in nx.simple_cycles(subgraph, length_bound=self.max_cycle_size):
            if 2 <= len(cycle) <= self.max_cycle_size:
                cycles.append(cycle)
        return cycles

    def get_valid_chains(self) -> list[list[int]]:
        """
        Énumère les chaînes altruistes de longueur 1 à max_chain_length.

        Returns:
            Liste de chaînes, chaque chaîne = [ndd_id, pair1_id, pair2_id, ...]
        """
        if self.max_chain_length == 0:
            return []

        ndd_nodes = [p.id for p in self.pairs if p.is_altruistic]
        chains: list[list[int]] = []

        for ndd_id in ndd_nodes:
            self._dfs_chains(
                current=ndd_id,
                path=[ndd_id],
                visited={ndd_id},
                chains=chains,
            )
        return chains

    def _dfs_chains(
        self,
        current: int,
        path: list[int],
        visited: set[int],
        chains: list[list[int]],
    ) -> None:

        if len(path) >= 2:
            chains.append(list(path))

        if len(path) - 1 >= self.max_chain_length:
            return

        for neighbor in self.graph.successors(current):
            if neighbor not in visited and not self._pair_index[neighbor].is_altruistic:
                visited.add(neighbor)
                path.append(neighbor)
                self._dfs_chains(neighbor, path, visited, chains)
                path.pop()
                visited.discard(neighbor)



    def get_pair(self, pair_id: int) -> Pair:
        """Retourne la paire associée à un identifiant."""
        return self._pair_index[pair_id]

    def arc_weight(self, i: int, j: int) -> float:
        """Retourne le poids de l'arc (i, j), 0 si inexistant."""
        return self.graph[i][j].get("weight", 0.0) if self.graph.has_edge(i, j) else 0.0

    def cycle_weight(self, cycle: list[int]) -> float:
        """Retourne le poids total d'un cycle."""
        return sum(
            self.arc_weight(cycle[k], cycle[(k + 1) % len(cycle)])
            for k in range(len(cycle))
        )

    def chain_weight(self, chain: list[int]) -> float:
        """Retourne le poids total d'une chaîne."""
        return sum(
            self.arc_weight(chain[k], chain[k + 1])
            for k in range(len(chain) - 1)
        )

    def __repr__(self) -> str:
        n_ndd = sum(1 for p in self.pairs if p.is_altruistic)
        return (
            f"KEPGraph(pairs={len(self.pairs) - n_ndd}, "
            f"ndds={n_ndd}, "
            f"arcs={self.graph.number_of_edges()}, "
            f"max_cycle={self.max_cycle_size})"
        )
