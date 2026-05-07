"""Provides the Context class."""

from __future__ import annotations

from typing import List
from uuid import UUID

import matplotlib.pyplot as plt
import matplotlib.patches as patches

from .server import Server


class Context:
    """Datacenter context, containing populated servers with various capacities.

    Attributes
    ----------
    servers : List[Server] | None, optional
        List of servers to populate the context with at setup, by default None.
    """

    _VM_PALETTE = [
        "#4C72B0",
        "#DD8452",
        "#55A868",
        "#C44E52",
        "#8172B3",
        "#937860",
        "#DA8BC3",
        "#8C8C8C",
        "#CCB974",
        "#64B5CD",
    ]

    def __init__(self, servers: List[Server] | None = None):
        self.servers: dict[UUID, Server] = {}
        if servers is not None:
            for server in servers:
                self.add_server(server)

    def add_server(self, server: Server | None = None, **kwargs) -> UUID:
        """Adds a server to the context by object or kwargs construction.

        Parameters
        ----------
        server : Server | None, optional
            The server to add, by default None.

        Returns
        -------
        UUID
            The generated id of the server if it was created by kwargs.
        """
        new_server = server or Server(UUID(), **kwargs)
        self.servers[new_server.id] = new_server
        return new_server.id

    def remove_server(self, server_id: UUID):
        """Removes a server from the context by id.

        Parameters
        ----------
        server_id : UUID
            The id of the server to remove.
        """
        self.servers.pop(server_id)

    def get_server(self, server_id: UUID) -> Server:
        """Gets a specific server object from the context.

        Parameters
        ----------
        server_id : UUID
            The id of the server to get.

        Returns
        -------
        Server
            The fetched server.

        Raises
        ------
        KeyError
            The server id didn't exist.
        """
        return self.servers[server_id]

    def get_servers(self) -> List[Server]:
        """Gets a list of all servers.

        Returns
        -------
        List[Server]
            The list of all the servers.
        """
        return list(server for server in self.servers.values())

    def copy(self) -> Context:
        """Creates a new context instance from this context.

        Returns
        -------
        Context
            The copied context.
        """
        return Context([server.copy() for server in self.get_servers()])

    def plot(
        self,
        title: str = "Datacenter - Resource allocation",
        figsize: tuple | None = None,
        max_cols: int = 3,
    ) -> plt.Figure | None:
        """Matplotlib visualization.

        Parameters
        ----------
        title : str, optional
            Title of the figure.
        figsize : tuple | None, optional
            Matplotlib figure's figsize.
        max_cols : int, optional
            Maximum number of columns in grid layout.

        Returns
        -------
        matplotlib.figure.Figure
        """
        n = len(self.servers)
        if n == 0:
            return None

        # Colors
        all_vm_ids: list = []
        for s in self.servers.values():
            for vm in s.vms:
                if vm.id not in all_vm_ids:
                    all_vm_ids.append(vm.id)
        vm_colors = {
            vid: self._VM_PALETTE[i % len(self._VM_PALETTE)]
            for i, vid in enumerate(all_vm_ids)
        }

        # Grid layout
        cols = min(n, max_cols)
        rows = (n + cols - 1) // cols

        if figsize is None:
            figsize = (cols * 6, rows * 4 + 1)

        fig, axes_grid = plt.subplots(rows, cols, figsize=figsize, squeeze=False)
        fig.suptitle(title, fontweight="bold")

        # Server plotting

        for idx, server in zip(range(rows * cols), self.servers.values()):
            row, col = divmod(idx, cols)
            ax = axes_grid[row][col]

            server.draw(ax, vm_colors)

        # Legend

        if all_vm_ids:
            handles = [
                patches.Patch(
                    color=vm_colors[vid],
                    label=f"VM {vid}",
                )
                for vid in all_vm_ids
            ]
            fig.legend(
                handles=handles,
                loc="lower center",
                ncol=min(len(handles), 5),
                title="VMs",
            )

        fig.tight_layout(pad=2)

        return fig

    def __str__(self) -> str:
        total_vms = sum(len(s.vms) for s in self.servers.values())
        n_srv = len(self.servers)

        header = (
            f"===== Context - {n_srv} server{'s' if n_srv != 1 else ''}"
            f", {total_vms} VM{'s' if total_vms != 1 else ''} total ====="
        )
        lines = [header, ""]
        for srv in self.servers.values():
            lines.append(str(srv))
            lines.append("")
        lines.append(len(header) * "=")
        return "\n".join(lines)
