from typing import List
from .context import Context
from .vm import VM
from abc import ABC, abstractmethod


class Solver(ABC):
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
