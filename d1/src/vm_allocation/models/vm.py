"""Provides the VM class."""

from __future__ import annotations

from uuid import UUID


class VM:
    """Model representing a VM with requirements.

    Attributes
    ----------
    vm_id : UUID
        The id of the VM, supposed to be unique per VM.
    cpu : int
        The CPU requirement.
    ram : int
        The RAM requirement.
    storage : int
        The storage requirement.
    bw : int
        The bandwidth requirement.
    affinity : set[VM]
        The set of VM ids this VM needs to share a server with.
    anti_affinity : set[VM]
        The set of VM ids this VM needs to have distinct server with.
    """

    def __init__(self, vm_id: UUID, cpu: int, ram: int, storage: int, bw: int):
        self.id = vm_id

        self.cpu = cpu
        self.ram = ram
        self.storage = storage
        self.bw = bw
        self.affinity: set[UUID] = set()
        self.anti_affinity: set[UUID] = set()

    def requirements(self) -> dict[str, int]:
        """VM requirements represented as a dictionary.

        Returns
        -------
        dict[str, int]
            A dictionary with keys cpu, ram, storage and bw.
        """
        return {
            "cpu": self.cpu,
            "ram": self.ram,
            "storage": self.storage,
            "bw": self.bw,
        }

    def total_requirement(self) -> int:
        """The sum of all the VM's requirements.

        Returns
        -------
        int
            The sum.
        """
        return sum(self.requirements().values())

    def add_affinity(self, vm: VM) -> None:
        """Adds a VM as affinity.

        Please bear in mind that this attribute, although transitive, will not
        propagate. A solver or any program should recurse through the affinities
        to find the total group of affiliated VMs.

        Parameters
        ----------
        vm : VM
            The VM to add affinity with.
        """
        self.affinity.add(vm.id)
        vm.affinity.add(self.id)

    def add_anti_affinity(self, vm: VM) -> None:
        """Adds a VM as anti-affinity.

        Parameters
        ----------
        vm : VM
            The VM to add anti-affinity with.
        """
        self.anti_affinity.add(vm.id)
        vm.anti_affinity.add(self.id)

    def copy(self) -> VM:
        """ "Creates a new VM instance from this VM.

        Returns
        -------
        VM
            The copied VM.
        """
        c = VM(self.id, self.cpu, self.ram, self.storage, self.bw)
        c.affinity = c.affinity.union(self.affinity)
        c.anti_affinity = c.anti_affinity.union(self.anti_affinity)

        return c
