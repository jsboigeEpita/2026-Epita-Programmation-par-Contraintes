"""Provides the Context class."""

from __future__ import annotations

from typing import List
from uuid import UUID

from .server import Server


class Context:
    """Datacenter context, containing populated servers with various capacities.

    Attributes
    ----------
    servers : List[Server] | None, optional
        List of servers to populate the context with at setup, by default None.
    """

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
