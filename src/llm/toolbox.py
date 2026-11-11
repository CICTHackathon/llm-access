"""MCP connections for the agents, with least privilege per role.

Each MCP server runs as its own stdio subprocess. An agent receives the tools of the
servers listed for its role and nothing else, so the access judge cannot deploy and
the executor cannot edit policy.
"""

from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Iterable
from typing import Any

ROLE_SERVERS: dict[str, tuple[str, ...]] = {
    "evidence_analyst": ("observer", "auditor"),
    "access_judge": ("librarian", "identity", "auditor"),
    "orchestrator": (),
    "configurator": ("librarian", "identity", "verifier", "simulator"),
    "executor": ("deployer", "observer"),
    "compliance_auditor": ("auditor", "observer", "simulator"),
}


# Tools withheld from a role even though its servers expose them.
ROLE_WITHHELD: dict[str, frozenset[str]] = {
    "access_judge": frozenset({"arm_card_enrolment", "collect_card_enrolment"}),
    "evidence_analyst": frozenset({"check_compliance"}),
}


def servers_for(roles: Iterable[str]) -> list[str]:
    return sorted({server for role in roles for server in ROLE_SERVERS[role]})


class Toolbox:
    """Starts the MCP servers a set of roles needs, and hands each role its tools."""

    def __init__(self, servers: Iterable[str], *, env: dict[str, str] | None = None,
                 connect_timeout: int = 60) -> None:
        self._servers = list(servers)
        self._env = {**os.environ, **(env or {})}
        self._timeout = connect_timeout
        self._adapters: dict[str, Any] = {}

    def start(self) -> Toolbox:
        from crewai_tools import MCPServerAdapter
        from mcp import StdioServerParameters

        for name in self._servers:
            if name in self._adapters:
                continue
            params = StdioServerParameters(
                command=sys.executable, args=["-m", "src.mcp_server.main", name],
                env=self._env, cwd=os.getcwd())
            self._adapters[name] = MCPServerAdapter(params, connect_timeout=self._timeout)
        return self

    def tools_for(self, role: str) -> list[Any]:
        tools: list[Any] = []
        for server in ROLE_SERVERS[role]:
            if server not in self._adapters:
                raise RuntimeError(f"MCP server {server!r} for role {role!r} is not started")
            tools.extend(self._adapters[server].tools)
        withheld = ROLE_WITHHELD.get(role, frozenset())
        return [t for t in tools if t.name not in withheld]

    def stop(self) -> None:
        for adapter in self._adapters.values():
            with contextlib.suppress(Exception):  # shutting down; nothing useful to raise
                adapter.stop()
        self._adapters.clear()

    def __enter__(self) -> Toolbox:
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.stop()
