from __future__ import annotations

from typing import List

import pulp

from vm_allocation.models import Context, Server, Solver, VM


RESOURCES = (
    ("cpu", "cpu_capacity"),
    ("ram", "ram_capacity"),
    ("storage", "storage_capacity"),
    ("bw", "bw_capacity"),
)

AssignmentVars = dict[tuple[int, int], pulp.LpVariable]
ServerUsageVars = dict[int, pulp.LpVariable]


class PLNESolver(Solver):
    """Solve VM allocation as an integer linear program with PuLP/CBC."""

    def __init__(
        self,
        migration_weight: float = 0,
        fragmentation_weight: float = 0,
    ):
        self.migration_weight = migration_weight
        self.fragmentation_weight = fragmentation_weight

    def solve(self, modifications: List[VM], context: Context) -> Context | None:
        """Build and solve the ILP model, then return the resulting context.

        The model re-allocates every VM from the current context plus every VM
        from ``modifications``. If a modified VM has the same id as an existing
        one, the modified definition replaces the old one.
        """
        servers = context.get_servers()
        vms = self._target_vms(modifications, context)
        if not servers and vms:
            return None

        problem = pulp.LpProblem("VM_Allocation_PLNE", pulp.LpMinimize)

        x = self._create_assignment_variables(vms, servers)
        y = self._create_server_usage_variables(servers)

        self._add_presence_constraints(problem, x, vms, servers)
        self._add_server_usage_constraints(problem, x, y, vms, servers)
        self._add_capacity_constraints(problem, x, y, vms, servers)
        self._add_affinity_constraints(problem, x, vms, servers)
        self._add_anti_affinity_constraints(problem, x, vms, servers)

        problem += self._objective_expression(x, y, vms, servers, context)

        status = problem.solve(self._make_pulp_solver())
        if status != pulp.LpStatusOptimal:
            return None

        return self._build_solution_context(x, vms, servers)

    def _create_assignment_variables(
        self, vms: list[VM], servers: list[Server]
    ) -> AssignmentVars:
        """Create x[i, j], equal to 1 when VM i is assigned to server j."""
        return {
            (i, j): pulp.LpVariable(f"x_{i}_{j}", cat="Binary")
            for i in range(len(vms))
            for j in range(len(servers))
        }

    def _create_server_usage_variables(self, servers: list[Server]) -> ServerUsageVars:
        """Create y[j], equal to 1 when server j hosts at least one VM."""
        return {
            j: pulp.LpVariable(f"y_{j}", cat="Binary")
            for j in range(len(servers))
        }

    def _target_vms(self, modifications: List[VM], context: Context) -> list[VM]:
        """Return the VMs that must exist in the final allocation.

        Existing VMs are copied from the current context. VMs from
        ``modifications`` are then copied on top of them: a new id adds a VM,
        while an existing id replaces the previous VM definition.
        """
        vms_by_id = {}
        ordered_ids = []

        for server in context.get_servers():
            for vm in server.vms:
                if vm.id not in vms_by_id:
                    ordered_ids.append(vm.id)
                vms_by_id[vm.id] = vm.copy()

        for vm in modifications:
            if vm.id not in vms_by_id:
                ordered_ids.append(vm.id)
            vms_by_id[vm.id] = vm.copy()

        return [vms_by_id[vm_id] for vm_id in ordered_ids]

    def _add_presence_constraints(
        self,
        problem: pulp.LpProblem,
        x: AssignmentVars,
        vms: list[VM],
        servers: list[Server],
    ) -> None:
        """Force every VM to be assigned to exactly one server."""
        number_of_servers = len(servers)

        for vm_index in range(len(vms)):
            possible_assignments = []

            for server_index in range(number_of_servers):
                assignment = x[(vm_index, server_index)]
                possible_assignments.append(assignment)

            vm_assignment_count = pulp.lpSum(possible_assignments)
            constraint_name = f"presence_vm_{vm_index}"

            problem += (vm_assignment_count == 1, constraint_name)

    def _add_server_usage_constraints(
        self,
        problem: pulp.LpProblem,
        x: AssignmentVars,
        y: ServerUsageVars,
        vms: list[VM],
        servers: list[Server],
    ) -> None:
        """Mark a server as used when at least one VM is assigned to it.

        If x[i, j] is 1, then y[j] must also be 1. Since the objective
        minimizes the sum of y[j], unused servers naturally stay at 0.
        """
        number_of_vms = len(vms)
        number_of_servers = len(servers)

        for vm_index in range(number_of_vms):
            for server_index in range(number_of_servers):
                vm_assigned_to_server = x[(vm_index, server_index)]
                server_is_used = y[server_index]
                constraint_name = (
                    f"server_usage_vm_{vm_index}_server_{server_index}"
                )

                problem += (
                    vm_assigned_to_server <= server_is_used,
                    constraint_name,
                )

    def _add_capacity_constraints(
        self,
        problem: pulp.LpProblem,
        x: AssignmentVars,
        y: ServerUsageVars,
        vms: list[VM],
        servers: list[Server],
    ) -> None:
        """Ensure each server stays within CPU, RAM, storage, and bandwidth limits."""
        for server_index, server in enumerate(servers):
            for vm_attr, server_attr in RESOURCES:
                total_resource_usage = self._server_usage_expression(
                    x,
                    vms,
                    server_index,
                    vm_attr,
                )
                server_capacity = getattr(server, server_attr)
                server_is_used = y[server_index]
                available_capacity = server_capacity * server_is_used
                constraint_name = f"capacity_{vm_attr}_server_{server_index}"

                problem += (
                    total_resource_usage <= available_capacity,
                    constraint_name,
                )

    def _add_affinity_constraints(
        self,
        problem: pulp.LpProblem,
        x: AssignmentVars,
        vms: list[VM],
        servers: list[Server],
    ) -> None:
        """Force affinity pairs to be placed on the same server."""
        affinity_pairs = self._vm_relation_pairs(vms, "affinity")
        number_of_servers = len(servers)

        for left_vm_index, right_vm_index in affinity_pairs:
            for server_index in range(number_of_servers):
                left_vm_assignment = x[(left_vm_index, server_index)]
                right_vm_assignment = x[(right_vm_index, server_index)]
                constraint_name = (
                    f"affinity_vm_{left_vm_index}_vm_{right_vm_index}"
                    f"_server_{server_index}"
                )

                problem += (
                    left_vm_assignment == right_vm_assignment,
                    constraint_name,
                )

    def _add_anti_affinity_constraints(
        self,
        problem: pulp.LpProblem,
        x: AssignmentVars,
        vms: list[VM],
        servers: list[Server],
    ) -> None:
        """Force anti-affinity pairs to be placed on different servers."""
        anti_affinity_pairs = self._vm_relation_pairs(vms, "anti_affinity")
        number_of_servers = len(servers)

        for left_vm_index, right_vm_index in anti_affinity_pairs:
            for server_index in range(number_of_servers):
                left_vm_assignment = x[(left_vm_index, server_index)]
                right_vm_assignment = x[(right_vm_index, server_index)]
                assignment_count_on_server = (
                    left_vm_assignment + right_vm_assignment
                )
                constraint_name = (
                    f"anti_affinity_vm_{left_vm_index}_vm_{right_vm_index}"
                    f"_server_{server_index}"
                )

                problem += (
                    assignment_count_on_server <= 1,
                    constraint_name,
                )

    def _vm_relation_pairs(
        self, vms: list[VM], relation_attr: str
    ) -> set[tuple[int, int]]:
        """Return unique VM index pairs for an affinity-like relation."""
        vm_index = {vm.id: i for i, vm in enumerate(vms)}
        pairs = set()

        for vm in vms:
            for other_vm_id in getattr(vm, relation_attr):
                if other_vm_id not in vm_index:
                    continue
                pairs.add(tuple(sorted((vm_index[vm.id], vm_index[other_vm_id]))))

        return pairs

    def _objective_expression(
        self,
        x: AssignmentVars,
        y: ServerUsageVars,
        vms: list[VM],
        servers: list[Server],
        context: Context,
    ):
        """Build the objective: used servers plus optional soft penalties."""
        terms = [pulp.lpSum(y[j] for j in range(len(servers)))]

        if self.migration_weight:
            terms.append(
                self.migration_weight
                * self._migration_expression(x, vms, servers, context)
            )

        if self.fragmentation_weight:
            terms.append(
                self.fragmentation_weight
                * self._fragmentation_expression(x, y, vms, servers)
            )

        return pulp.lpSum(terms)

    def _migration_expression(
        self, x: AssignmentVars, vms: list[VM], servers: list[Server], context: Context
    ):
        """Count assignments that move an existing VM away from its current server."""
        current_assignment = self._current_assignment(context)
        server_index = {server.id: j for j, server in enumerate(servers)}
        terms = []

        for i, vm in enumerate(vms):
            current_server_id = current_assignment.get(vm.id)
            if current_server_id not in server_index:
                continue

            current_server_index = server_index[current_server_id]
            terms.extend(
                x[(i, j)] for j in range(len(servers)) if j != current_server_index
            )

        return pulp.lpSum(terms)

    def _fragmentation_expression(
        self,
        x: AssignmentVars,
        y: ServerUsageVars,
        vms: list[VM],
        servers: list[Server],
    ):
        """Measure normalized free resources left on active servers."""
        terms = []
        for j, server in enumerate(servers):
            for vm_attr, server_attr in RESOURCES:
                capacity = getattr(server, server_attr)
                if capacity <= 0:
                    continue

                used = self._server_usage_expression(x, vms, j, vm_attr)
                terms.append((capacity * y[j] - used) / capacity)

        return pulp.lpSum(terms)

    def _server_usage_expression(
        self, x: AssignmentVars, vms: list[VM], server_index: int, vm_attr: str
    ):
        """Return the total usage of one VM resource on one server."""
        return pulp.lpSum(
            getattr(vm, vm_attr) * x[(i, server_index)] for i, vm in enumerate(vms)
        )

    def _make_pulp_solver(self):
        """Create the PuLP CBC solver used for the ILP."""
        return pulp.PULP_CBC_CMD(msg=False)

    def _current_assignment(self, context: Context) -> dict:
        """Map each currently hosted VM id to its current server id."""
        assignment = {}
        for server in context.get_servers():
            for vm in server.vms:
                assignment[vm.id] = server.id
        return assignment

    def _build_solution_context(
        self, x: AssignmentVars, vms: list[VM], servers: list[Server]
    ) -> Context:
        """Convert solved x[i, j] values back into a concrete Context."""
        solution_servers = [
            Server(
                server.id,
                server.cpu_capacity,
                server.ram_capacity,
                server.storage_capacity,
                server.bw_capacity,
            )
            for server in servers
        ]

        for i, vm in enumerate(vms):
            for j, server in enumerate(solution_servers):
                if pulp.value(x[(i, j)]) > 0.5:
                    server.add_vm(vm.copy())
                    break

        return Context(solution_servers)
