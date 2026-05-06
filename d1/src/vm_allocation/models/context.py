from __future__ import annotations

from typing import List
from uuid import UUID

from vm_allocation.models import Server


class Context:
    def __init__(self, servers: List[Server] | None = None):
        self.servers: dict[UUID, Server] = {}
        if servers is not None:
            for server in servers:
                self.add_server(server)

    def add_server(self, server: Server | None = None, **kwargs) -> UUID:
        new_server = server or Server(UUID(), **kwargs)
        self.servers[new_server.id] = new_server
        return new_server.id

    def remove_server(self, server_id: UUID):
        self.servers.pop(server_id)

    def get_server(self, server_id: UUID) -> Server:
        return self.servers[server_id]

    def get_servers(self) -> List[Server]:
        return list(server for server in self.servers.values())

    def copy(self) -> Context:
        return Context([server.copy() for server in self.get_servers()])
