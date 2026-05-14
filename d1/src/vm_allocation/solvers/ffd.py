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

    def solve[ID_T](
        self, modifications: List[VM[ID_T]], context: Context[ID_T]
    ) -> Context[ID_T] | None:

        print("\n===== FFD CLEAN SOLVER =====")

        context = context.copy()
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

        groups.sort(key=lambda g: sum(vm.total_requirement() for vm in g), reverse=True)

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
                if self._can_place_group(server, group):
                    for vm in group:
                        if not server.add_vm(vm):
                            return None
                    placed = True
                    break

            if not placed:
                print("[FAIL] cannot place group")
                return None

        return context

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _merge_with_existing[ID_T](
        self, modifications: List[VM[ID_T]], context: Context[ID_T]
    ) -> List[VM[ID_T]]:
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

    def _build_affinity_groups[ID_T](self, vms: List[VM[ID_T]]) -> List[List[VM[ID_T]]]:
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

    def _place_group[ID_T](self, group: List[VM[ID_T]], servers: list) -> bool:
        """
        Tente de placer tout un groupe sur le même serveur (First Fit).
        Retourne True si le placement a réussi.
        """
        for server in servers:
            if self._can_place_group(server, group):
                for vm in group:
                    if not server.add_vm(vm):
                        return False
                return True

        return False

    def _can_place_group[ID_T](self, server, group: List[VM[ID_T]]) -> bool:
        """
        Vérifie qu'un groupe entier peut être placé sur un serveur.
        """
        cpu_usage = server.cpu_usage
        ram_usage = server.ram_usage
        storage_usage = server.storage_usage
        bw_usage = server.bw_usage

        for vm in group:
            if any(existing_vm.id == vm.id for existing_vm in server.vms):
                return False

            for existing_vm in server.vms:
                if (
                    existing_vm.id in vm.anti_affinity
                    or vm.id in existing_vm.anti_affinity
                ):
                    return False

            for other_vm in group:
                if other_vm.id == vm.id:
                    continue
                if (
                    other_vm.id in vm.anti_affinity
                    or vm.id in other_vm.anti_affinity
                ):
                    return False

            cpu_usage += vm.cpu
            ram_usage += vm.ram
            storage_usage += vm.storage
            bw_usage += vm.bw

        return (
            cpu_usage <= server.cpu_capacity
            and ram_usage <= server.ram_capacity
            and storage_usage <= server.storage_capacity
            and bw_usage <= server.bw_capacity
        )
