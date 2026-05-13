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
        new_context = context.copy()

        # Retirer les VMs modifiées de leur serveur actuel
        for vm in modifications:
            for server in new_context.get_servers():
                server.remove_vm_by_id(vm.id)
        #print('modification', modifications)
        # Construire les groupes d'affinité
        #all_vms = self._merge_with_existing(modifications, new_context)
        groups = self._build_affinity_groups(modifications)

        # Trier chaque groupe par taille décroissante (la plus grosse VM du groupe en tête)
        groups.sort(key=lambda g: max(vm.total_requirement() for vm in g), reverse=True)

        servers = new_context.get_servers()

        for group in groups:
            # Trouver le premier serveur qui peut accueillir tout le groupe
            placed = self._place_group(group, servers)
            if not placed:
                return None  # Impossible de placer ce groupe

        return new_context

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