"""Provides the Solver interface."""

from abc import ABC, abstractmethod
from typing import List

from vm_allocation.models import VM, Context


class Solver(ABC):
    """Interface providing the template for VM allocation problem solvers."""

    @abstractmethod
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
        ...
