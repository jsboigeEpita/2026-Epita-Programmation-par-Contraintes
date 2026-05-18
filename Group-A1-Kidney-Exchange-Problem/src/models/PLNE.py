"""
PLNESolver — Integer Linear Programming (ILP) solver for the
Kidney Exchange Problem (KEP).

This solver formulates the KEP as an Integer Linear Program and solves it
using PuLP with the CBC backend. It handles both:
  - Cycles: closed exchanges between compatible patient-donor pairs.
  - Chains: open sequences initiated by a Non-Directed (altruistic) Donor (NDD).

The objective is to maximise the total weighted number of transplants,
subject to the constraint that each patient/donor participates in at most
one selected cycle or chain.

ILP formulation:
    Variables:
        x_i in {0, 1}  — 1 if cycle i is selected, 0 otherwise.
        y_j in {0, 1}  — 1 if chain j is selected, 0 otherwise.

    Objective (maximise):
        sum_i  weight(cycle_i) * x_i  +  sum_j  weight(chain_j) * y_j

    Constraints:
        For every non-NDD node v:
            sum_{i: v in cycle_i} x_i + sum_{j: v in chain_j[1:]} y_j <= 1
        For every NDD node n:
            sum_{j: chain_j[0] == n} y_j <= 1
"""

import itertools
from dataclasses import dataclass, field
from typing import Optional
import pulp
import networkx as nx
import time

from src.models.base import KidneyExchangeSolver, SolverResult
from src.core.graph import KEPGraph


class PLNESolver(KidneyExchangeSolver):
    """
    ILP-based solver for the Kidney Exchange Problem (KEP).

    Inherits from KidneyExchangeSolver and implements the solve() method
    using a cycle-and-chain ILP formulation. Cycles and chains are fully
    enumerated before solving; the ILP then selects the optimal subset.

    Attributes:
        cycles (list[list[int]]): All valid cycles pre-enumerated from
            the compatibility graph (length <= max_cycle_size).
        chains (list[list[int]]): All valid chains pre-enumerated from
            NDD nodes (total nodes <= max_chain_length + 1, NDD first).
        max_chain_length (int): Maximum number of transplants (edges) in
            a chain, i.e. maximum chain node count minus the NDD.
    """

    def __init__(
        self,
        kep_graph: KEPGraph,
        max_cycle_size: int = 3,
        max_chain_length: int = 3,
    ):
        """
        Initialise the solver and pre-enumerate all cycles and chains.

        Args:
            kep_graph (KEPGraph): The compatibility graph representing
                patient-donor pairs and their directed weighted edges.
            max_cycle_size (int): Maximum number of nodes (pairs) allowed
                in a single cycle. Defaults to 3.
            max_chain_length (int): Maximum number of transplants (edges)
                allowed in a single chain, i.e. maximum number of
                non-NDD nodes in the chain. Defaults to 3.
        """
        super().__init__(kep_graph, max_cycle_size)

        # Cycles are enumerated by the parent class / graph utility.
        self.cycles = self.graph.get_valid_cycles()

        self.max_chain_length = max_chain_length
        # Chains are enumerated here using iterative DFS from each NDD.
        self.chains = self._enumerate_chains()

    # ------------------------------------------------------------------
    # Chain enumeration
    # ------------------------------------------------------------------

    def _enumerate_chains(self) -> list[list[int]]:
        """
        Enumerate all simple chains starting from Non-Directed Donors (NDDs).

        A chain is a simple path in the compatibility graph that begins at
        an altruistic (NDD) node. The NDD is included as the first element
        of the path but does not itself receive a kidney — it only donates.

        Only paths of length >= 2 nodes (i.e. at least one transplant edge)
        are recorded. Paths grow up to max_chain_length + 1 nodes total
        (NDD + max_chain_length recipients).

        An iterative DFS (stack-based) is used to avoid recursion limits on
        large graphs.

        Returns:
            list[list[int]]: A list of chains, each represented as an
                ordered list of node IDs. The first element is always an
                NDD; subsequent elements are patient-donor pairs.
        """
        chains = []
        ndd_ids = [p.id for p in self.graph.pairs if p.is_altruistic]

        for ndd in ndd_ids:
            # Each stack entry is a partial path starting from this NDD.
            stack = [[ndd]]
            while stack:
                path = stack.pop()
                last = path[-1]

                # Record the path as a valid chain once it contains at
                # least the NDD and one recipient (>= 2 nodes).
                if len(path) >= 2:
                    chains.append(path[:])

                # Extend the path if we have not yet reached the length limit.
                # max_chain_length counts transplant edges, so the maximum
                # number of nodes is max_chain_length + 1 (including the NDD).
                if len(path) <= self.max_chain_length:
                    for _, neighbour in self.graph.graph.out_edges(last):
                        # Avoid revisiting nodes already in the current path.
                        if neighbour not in path:
                            stack.append(path + [neighbour])

        return chains

    # ------------------------------------------------------------------
    # Weight / transplant count helpers
    # ------------------------------------------------------------------

    def _cycle_weights(self, cycle: list[int]) -> float:
        """
        Compute the total weight of all edges in a cycle.

        Edges are traversed in order:
            cycle[0] -> cycle[1] -> ... -> cycle[n-1] -> cycle[0].
        Missing edges contribute 0 to the total.

        Args:
            cycle (list[int]): Ordered list of node IDs forming the cycle.

        Returns:
            float: Sum of edge weights around the cycle.
        """
        total = 0.0
        n = len(cycle)
        for i in range(n):
            u = cycle[i]
            v = cycle[(i + 1) % n]  # Wrap around to close the cycle.
            data = self.graph.graph.get_edge_data(u, v)
            total += data["weight"] if data else 0.0
        return total

    def _chain_weights(self, chain: list[int]) -> float:
        """
        Compute the total weight of all edges in a chain.

        Edges are traversed in order:
            chain[0] -> chain[1] -> ... -> chain[-1].
        There is no closing edge (chains are open paths).
        Missing edges contribute 0 to the total.

        Args:
            chain (list[int]): Ordered list of node IDs forming the chain,
                with the NDD at index 0.

        Returns:
            float: Sum of edge weights along the chain.
        """
        total = 0.0
        for i in range(len(chain) - 1):
            u, v = chain[i], chain[i + 1]
            data = self.graph.graph.get_edge_data(u, v)
            total += data["weight"] if data else 0.0
        return total

    def _cycle_transplants(self, cycle: list[int]) -> int:
        """
        Return the number of transplants performed in a cycle.

        In a cycle every node both donates and receives, so the number of
        transplants equals the number of nodes (= number of directed edges).

        Args:
            cycle (list[int]): Ordered list of node IDs forming the cycle.

        Returns:
            int: Number of transplants (= number of nodes in the cycle).
        """
        return len(cycle)

    def _chain_transplants(self, chain: list[int]) -> int:
        """
        Return the number of transplants performed in a chain.

        In a chain the NDD donates but does not receive, so the number of
        transplants equals the number of directed edges = len(chain) - 1.

        Args:
            chain (list[int]): Ordered list of node IDs forming the chain,
                with the NDD at index 0.

        Returns:
            int: Number of transplants (= number of edges in the chain).
        """
        return len(chain) - 1

    # ------------------------------------------------------------------
    # Main solve method
    # ------------------------------------------------------------------

    def solve(self, time_limit: float = 60.0) -> SolverResult:
        """
        Solve the KEP instance using Integer Linear Programming.

        Builds and solves the ILP described in the module docstring.
        The CBC solver (via PuLP) is used with a configurable time limit.

        Solving steps:
            1. Create binary decision variables for each cycle (x_i) and
               chain (y_j).
            2. Define the maximisation objective (total weighted transplants).
            3. Add coverage constraints — each non-NDD node appears in at
               most one selected cycle or chain.
            4. Add NDD constraints — each NDD initiates at most one chain.
            5. Solve with CBC and extract the selected cycles/chains.

        Args:
            time_limit (float): Maximum wall-clock time (in seconds) allowed
                for the ILP solver. Defaults to 60 seconds.

        Returns:
            SolverResult: A result object containing:
                - status         : "OPTIMAL", "FEASIBLE", "INFEASIBLE",
                                   or "TIMEOUT".
                - selected_cycles: list of selected cycles (each a list of
                                   node IDs).
                - selected_chains: list of selected chains (each a list of
                                   node IDs, NDD first).
                - objective_value: total number of transplants achieved.
                - solve_time     : elapsed wall-clock time in seconds.
        """
        t0 = time.time()

        # ------------------------------------------------------------------
        # 1. Problem definition
        # ------------------------------------------------------------------
        prob = pulp.LpProblem("KEP_PLNE", pulp.LpMaximize)

        # Binary variable x_i: 1 if cycle i is included in the solution.
        x = {
            i: pulp.LpVariable(f"x_c{i}", cat="Binary")
            for i in range(len(self.cycles))
        }

        # Binary variable y_j: 1 if chain j is included in the solution.
        y = {
            j: pulp.LpVariable(f"y_ch{j}", cat="Binary")
            for j in range(len(self.chains))
        }

        # ------------------------------------------------------------------
        # 2. Objective: maximise total weighted transplants
        # ------------------------------------------------------------------
        prob += (
            pulp.lpSum(
                self._cycle_weights(self.cycles[i]) * x[i]
                for i in range(len(self.cycles))
            )
            + pulp.lpSum(
                self._chain_weights(self.chains[j]) * y[j]
                for j in range(len(self.chains))
            )
        )

        # ------------------------------------------------------------------
        # 3. Coverage constraints for non-NDD nodes
        #    Each patient-donor pair may participate in at most one cycle
        #    or chain (ch[1:] excludes the NDD at position 0 from the check).
        # ------------------------------------------------------------------
        non_ndd_ids = [p.id for p in self.graph.pairs if not p.is_altruistic]

        for node in non_ndd_ids:
            # Cycles that contain this node.
            cycle_vars = [x[i] for i, c in enumerate(self.cycles) if node in c]

            # Chains that contain this node as a recipient (not as the NDD,
            # hence ch[1:] skips the first element).
            chain_vars = [y[j] for j, ch in enumerate(self.chains) if node in ch[1:]]

            if cycle_vars or chain_vars:
                prob += (
                    pulp.lpSum(cycle_vars + chain_vars) <= 1,
                    f"cover_{node}",
                )

        # ------------------------------------------------------------------
        # 4. NDD constraints
        #    Each altruistic donor may initiate at most one chain.
        # ------------------------------------------------------------------
        ndd_ids = [p.id for p in self.graph.pairs if p.is_altruistic]
        for ndd in ndd_ids:
            chain_vars = [y[j] for j, ch in enumerate(self.chains) if ch[0] == ndd]
            if chain_vars:
                prob += pulp.lpSum(chain_vars) <= 1, f"ndd_{ndd}"

        # ------------------------------------------------------------------
        # 5. Solve with CBC
        # ------------------------------------------------------------------
        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=int(time_limit))
        prob.solve(solver)

        solve_time = time.time() - t0

        # ------------------------------------------------------------------
        # 6. Extract solution
        # ------------------------------------------------------------------
        selected_cycles = [
            self.cycles[i]
            for i in range(len(self.cycles))
            if pulp.value(x[i]) is not None and pulp.value(x[i]) > 0.5
        ]

        selected_chains = [
            self.chains[j]
            for j in range(len(self.chains))
            if pulp.value(y[j]) is not None and pulp.value(y[j]) > 0.5
        ]

        total_transplants = sum(
            self._cycle_transplants(c) for c in selected_cycles
        ) + sum(
            self._chain_transplants(ch) for ch in selected_chains
        )

        # Map PuLP status strings to the project's canonical status codes.
        pulp_status = pulp.LpStatus[prob.status]
        if pulp_status == "Optimal":
            status_str = "OPTIMAL"
        elif pulp_status == "Infeasible":
            status_str = "INFEASIBLE"
        elif pulp_status == "Not Solved":
            # CBC hit the time limit without proving optimality.
            status_str = "TIMEOUT"
        else:
            status_str = "FEASIBLE"

        return self._make_result(
            status_str,
            selected_cycles,
            selected_chains,
            float(total_transplants),
            solve_time,
        )