from __future__ import annotations


class VM:
    def __init__(self, vm_id, cpu, ram, storage, bw):
        self.id = vm_id

        self.cpu = cpu
        self.ram = ram
        self.storage = storage
        self.bw = bw
        self.affinity = set()
        self.anti_affinity = set()

    def requirements(self) -> dict[str, int]:
        return {
            "cpu": self.cpu,
            "ram": self.ram,
            "storage": self.storage,
            "bw": self.bw,
        }

    def total_requirement(self) -> int:
        return sum(self.requirements().values())

    def add_affinity(self, vm: VM) -> None:
        self.affinity.add(vm.id)
        vm.affinity.add(self.id)

    def add_anti_affinity(self, vm: VM) -> None:
        self.anti_affinity.add(vm.id)
        vm.anti_affinity.add(self.id)

    def copy(self) -> VM:
        c = VM(self.id, self.cpu, self.ram, self.storage, self.bw)
        c.affinity = c.affinity.union(self.affinity)
        c.anti_affinity = c.anti_affinity.union(self.anti_affinity)

        return c
