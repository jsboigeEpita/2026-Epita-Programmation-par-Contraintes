from uuid import UUID
from typing import List, Any

from ortools.sat.python import cp_model

from vm_allocation.models import VM, Context, Solver, Server


class CPSATSolver(Solver):
    def __init__(self, hot_swaps_factor: float, fragmentation_factor: float):
        self.hot_swaps_factor = hot_swaps_factor
        self.fragmentation_factor = fragmentation_factor

    def solve(self, modifications: List[VM], context: Context) -> Context | None:
        """Returns the solution to a vm allocation problem.

        Parameters
        ----------
        modifications : List[VM]
            The list of added or modified VMs configurations.
        context : Context
            The context with the servers, their allocated VMs.

        Returns
        -------
        Context | None
            A new context to accommodate for the changes, None if impossible.
        """

        vms: dict[UUID, VM] = {vm.id: vm for vm in modifications}
        servers: dict[UUID, Server] = {}
        servers_id_sets: dict[UUID, set[UUID]] = {}
        for server in context.get_servers():
            servers[server.id] = server
            id_set = set()
            for vm in server.vms:
                id_set.add(vm.id)
                if vm.id not in vms:
                    vms[vm.id] = vm
            servers_id_sets[server.id] = id_set

        model = cp_model.CpModel()

        # VM allocation
        x: dict[tuple[UUID, UUID], cp_model.IntVar] = {
            (vm_id, server_id): model.new_bool_var(f"x_{vm_id}_{server_id}")
            for vm_id in vms
            for server_id in servers
        }

        # Server activity
        y: dict[UUID, cp_model.IntVar] = {
            server_id: model.new_bool_var(f"y_{server_id}") for server_id in servers
        }
        for vm_id in vms:
            for server_id in servers:
                model.add(y[server_id] >= x[(vm_id, server_id)])

        # Unity
        for vm_id in vms:
            model.add(sum(x[(vm_id, server_id)] for server_id in servers) == 1)

        # Capacity
        for server_id, server in servers.items():
            # CPU, RAM, Storage, Bandwidth
            model.add(
                sum(vm.cpu * x[(vm_id, server_id)] for vm_id, vm in vms.items())
                <= server.cpu_capacity
            )
            model.add(
                sum(vm.ram * x[(vm_id, server_id)] for vm_id, vm in vms.items())
                <= server.ram_capacity
            )
            model.add(
                sum(vm.storage * x[(vm_id, server_id)] for vm_id, vm in vms.items())
                <= server.storage_capacity
            )
            model.add(
                sum(vm.bw * x[(vm_id, server_id)] for vm_id, vm in vms.items())
                <= server.bw_capacity
            )

        # Affinity / Anti-affinity
        for vm_id, vm in vms.items():
            for server_id in servers:
                for other_vm in vm.affinity:
                    model.add(x[(vm_id, server_id)] == x[(other_vm.id, server_id)])
                for other_vm in vm.anti_affinity:
                    model.add(x[(vm_id, server_id)] != x[(other_vm.id, server_id)])

        # Dynamic consolidation
        d_list: list[cp_model.IntVar] = []
        for server_id, vm_ids in servers_id_sets.items():
            for vm_id in vm_ids:
                d = model.new_bool_var(f"d_{vm_id}_{server_id}")
                d_list.append(d)
                model.add(d >= (1 - x[(vm_id, server_id)]))

        # Fragmentation
        f_list: list[cp_model.IntVar] = []
        for server_id in servers:
            f = model.new_bool_var(f"f_{server_id}")
            model.add(
                server.cpu_capacity
                - sum(vm.cpu * x[(vm_id, server_id)] for vm_id, vm in vms.items())
                <= f * server.cpu_capacity
            )
            model.add(
                server.ram_capacity
                - sum(vm.ram * x[(vm_id, server_id)] for vm_id, vm in vms.items())
                <= f * server.ram_capacity
            )
            model.add(
                server.storage_capacity
                - sum(vm.storage * x[(vm_id, server_id)] for vm_id, vm in vms.items())
                <= f * server.storage_capacity
            )
            model.add(
                server.bw_capacity
                - sum(vm.bw * x[(vm_id, server_id)] for vm_id, vm in vms.items())
                <= f * server.bw_capacity
            )

        # Objective
        model.minimize(
            sum(y[server_id] for server_id in servers)
            + self.hot_swaps_factor * sum(d for d in d_list)
            + self.fragmentation_factor * sum(f for f in f_list)
        )

        # Solving
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        # Impossible case
        if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
            return None

        # Context creation
        server_list = []
        for server_id, server in servers.items():
            new_server = Server(
                server_id,
                server.cpu_capacity,
                server.ram_capacity,
                server.storage_capacity,
                server.bw_capacity,
            )
            for vm_id, vm in vms.items():
                if solver.Value(x[(vm_id, server_id)]) == 1:
                    new_server.add_vm(vm.copy())
            server_list.append(new_server)

        return Context(server_list)
