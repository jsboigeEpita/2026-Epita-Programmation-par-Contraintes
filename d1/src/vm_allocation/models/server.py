from __future__ import annotations


class Server:
    def __init__(self, server_id, cpu, ram, storage, bw):

        self.id = server_id
        self.cpu_capacity = cpu
        self.ram_capacity = ram
        self.storage_capacity = storage
        self.bw_capacity = bw

        self.cpu_usage = 0
        self.ram_usage = 0
        self.storage_usage = 0
        self.bw_usage = 0

        self.vms = []

    def remove_vm_by_id(self, vm_id):
        for vm in self.vms:
            if vm.id == vm_id:
                self.cpu_usage -= vm.cpu
                self.ram_usage -= vm.ram
                self.storage_usage -= vm.storage
                self.bw_usage -= vm.bw

                self.vms.remove(vm)

                return True

        return False

    def add_vm(self, vm):

        if not self.can_host(vm):
            return False
        self.vms.append(vm)

        self.cpu_usage += vm.cpu
        self.ram_usage += vm.ram
        self.storage_usage += vm.storage
        self.bw_usage += vm.bw

        return True

    def can_host(self, vm):

        if (
            self.cpu_usage + vm.cpu > self.cpu_capacity
            or self.ram_usage + vm.ram > self.ram_capacity
            or self.storage_usage + vm.storage > self.storage_capacity
            or self.bw_usage + vm.bw > self.bw_capacity
        ):
            return False

        for other_vm in self.vms:
            if other_vm.id in vm.anti_affinity:
                return False

        return True

    def copy(self) -> Server:
        c = Server(
            self.id,
            self.cpu_capacity,
            self.ram_capacity,
            self.storage_capacity,
            self.bw_capacity,
        )
        for vm in self.vms:
            c.add_vm(vm.copy())

        return c
