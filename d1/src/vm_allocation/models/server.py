"""Provides the Server class."""

from __future__ import annotations

from typing import List
from uuid import UUID

from vm_allocation.models import VM


class Server:
    """Model representing a server with a capacity and running VMs.

    Attributes
    ----------
    server_id : UUID
        The id of the server, supposed to be unique per server.
    cpu : int
        CPU capacity of the server.
    ram : int
        RAM capacity of the server.
    storage : int
        Storage capacity of the server.
    bw : int
        Bandwidth capacity of the server.
    cpu_usage : int
        Current usage of the CPU.
    ram_usage : int
        Current usage of the RAM.
    storage_usage : int
        Current usage of the storage.
    bw_usage : int
        Current usage of the bandwidth.
    vms : List[VM]
        Active VMs running on the server.
    """

    def __init__(self, server_id: UUID, cpu: int, ram: int, storage: int, bw: int):

        self.id = server_id
        self.cpu_capacity = cpu
        self.ram_capacity = ram
        self.storage_capacity = storage
        self.bw_capacity = bw

        self.cpu_usage = 0
        self.ram_usage = 0
        self.storage_usage = 0
        self.bw_usage = 0

        self.vms: List[VM] = []

    def remove_vm_by_id(self, vm_id: UUID) -> bool:
        """Removes a running VM by id.

        Parameters
        ----------
        vm_id : UUID
            The id of the VM to remove.

        Returns
        -------
        bool
            True if removal successful, False otherwise.
        """
        for vm in self.vms:
            if vm.id == vm_id:
                self.cpu_usage -= vm.cpu
                self.ram_usage -= vm.ram
                self.storage_usage -= vm.storage
                self.bw_usage -= vm.bw

                self.vms.remove(vm)

                return True

        return False

    def add_vm(self, vm: VM) -> bool:
        """Adds a running VM.

        Parameters
        ----------
        vm : VM
            The VM to add.

        Returns
        -------
        bool
            True if addition successful, False otherwise (in case of lack of
            capacity for example).
        """

        if not self.can_host(vm):
            return False
        self.vms.append(vm)

        self.cpu_usage += vm.cpu
        self.ram_usage += vm.ram
        self.storage_usage += vm.storage
        self.bw_usage += vm.bw

        return True

    def can_host(self, vm: VM) -> bool:
        """Whether the server can host the given VM.

        Parameters
        ----------
        vm : VM
            The VM to check for.

        Returns
        -------
        bool
            True if possible, False otherwise.
        """

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
        """ "Creates a new server instance from this server.

        Returns
        -------
        Server
            The copied server.
        """
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
