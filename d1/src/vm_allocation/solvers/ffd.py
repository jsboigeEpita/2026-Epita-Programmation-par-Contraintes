from typing import List
from vm_allocation.models import Context, VM, Solver


class FFDSolver(Solver):
    """
    First Fit Decreasing solver.

    On trie les VMs par taille décroissante, puis on place chaque VM
    sur le premier serveur qui peut l'accueillir.

    Pour les contraintes d'affinité, on regroupe d'abord les VMs qui
    doivent être ensemble, et on les place en bloc.
    """

    def solve(self, modifications: List[VM], context: Context) -> Context | None:

        print("\n===== FFD CLEAN SOLVER =====")

        servers = context.get_servers()

        # 1. REMOVE old versions of modified VMs
        modified_ids = {vm.id for vm in modifications}

        for server in servers:
            server.vms = [vm for vm in server.vms if vm.id not in modified_ids]

            # reset usage propre (IMPORTANT)
            server.cpu_usage = sum(vm.cpu for vm in server.vms)
            server.ram_usage = sum(vm.ram for vm in server.vms)
            server.storage_usage = sum(vm.storage for vm in server.vms)
            server.bw_usage = sum(vm.bw for vm in server.vms)

        # 2. rebuild full VM list CLEAN
        all_vms = []
        for server in servers:
            all_vms.extend(server.vms)

        all_vms.extend(modifications)

        print(f"[DEBUG] total VMs = {len(all_vms)}")

        # 3. rebuild groups (affinity safe)
        groups = self._build_affinity_groups(all_vms)

        groups.sort(
            key=lambda g: sum(vm.total_requirement() for vm in g),
            reverse=True
        )

        # 4. clear servers BEFORE placement (VERY IMPORTANT)
        for server in servers:
            server.vms.clear()
            server.cpu_usage = 0
            server.ram_usage = 0
            server.storage_usage = 0
            server.bw_usage = 0

        # 5. place groups
        for group in groups:

            placed = False

            for server in servers:

                if all(server.can_host(vm) for vm in group):
                    for vm in group:
                        server.add_vm(vm)
                    placed = True
                    break

            if not placed:
                print("[FAIL] cannot place group")
                return None

        return context



    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _merge_with_existing(self, modifications: List[VM], context: Context) -> List[VM]:
        """
        Fusionne les VMs modifiées avec celles déjà présentes dans le contexte,
        en remplaçant les anciennes versions par les nouvelles.
        """
        modified_ids = {vm.id for vm in modifications}

        existing_vms = [
            vm
            for server in context.get_servers()
            for vm in server.vms
            if vm.id not in modified_ids
        ]

        return existing_vms + modifications

    def _build_affinity_groups(self, vms: List[VM]) -> List[List[VM]]:
        """
        Regroupe les VMs liées par affinité via un union-find simple.
        Chaque groupe devra être placé sur le même serveur.
        """
        vm_by_id = {vm.id: vm for vm in vms}
        parent = {vm.id: vm.id for vm in vms}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]  # path compression
                x = parent[x]
            return x

        def union(x, y):
            parent[find(x)] = find(y)

        for vm in vms:
            for affinity_id in vm.affinity:
                if affinity_id in vm_by_id:
                    union(vm.id, affinity_id)

        # Regrouper par racine
        groups: dict = {}
        for vm in vms:
            root = find(vm.id)
            groups.setdefault(root, []).append(vm)

        return list(groups.values())

    def _place_group(self, group: List[VM], servers: list) -> bool:
        """
        Tente de placer tout un groupe sur le même serveur (First Fit).
        Retourne True si le placement a réussi.
        """
        for server in servers:
            if all(server.can_host(vm) for vm in group):
                for vm in group:
                    server.add_vm(vm)
                return True

        return False