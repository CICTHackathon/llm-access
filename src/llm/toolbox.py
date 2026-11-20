"""MCP connections for the agents, with least privilege per role.

Each MCP server runs as its own stdio subprocess. An agent receives the tools of the
servers listed for its role and nothing else, so the access judge cannot deploy and
the executor cannot edit policy.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import sys
from collections.abc import Iterable
from typing import Any

# CrewAI's built-in MCP client. It replaces crewai-tools' MCPServerAdapter, whose
# dependencies alone pushed the Vercel function bundle past the 500 MB limit.
from crewai.mcp.client import MCPClient
from crewai.mcp.tool_resolver import MCPToolResolver
from crewai.mcp.transports.stdio import StdioTransport
from crewai.tools.mcp_native_tool import MCPNativeTool

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


def _run_sync(coro: Any) -> Any:
    """Run a coroutine to completion, also from inside a running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class Toolbox:
    """Starts the MCP servers a set of roles needs, and hands each role its tools.

    Tools are discovered once per server at start. Each tool call then opens its own
    stdio connection to that server (how CrewAI's native MCP tools work), so no
    subprocess stays running between calls.
    """

    def __init__(self, servers: Iterable[str], *, env: dict[str, str] | None = None,
                 connect_timeout: int = 60) -> None:
        self._servers = list(servers)
        root = os.getcwd()
        pythonpath = os.pathsep.join(p for p in (root, os.environ.get("PYTHONPATH")) if p)
        self._env = {**os.environ, "PYTHONPATH": pythonpath, **(env or {})}
        self._timeout = connect_timeout
        self._tools: dict[str, list[Any]] = {}

    def _client(self, server: str) -> MCPClient:
        transport = StdioTransport(command=sys.executable,
                                   args=["-m", "src.mcp_server.main", server], env=self._env)
        return MCPClient(transport=transport, connect_timeout=self._timeout)

    def _discover(self, server: str) -> list[Any]:
        async def list_tools() -> list[dict[str, Any]]:
            client = self._client(server)
            await client.connect()
            try:
                return await client.list_tools()
            finally:
                await client.disconnect()

        tools: list[Any] = []
        for spec in _run_sync(list_tools()):
            name = spec["name"]
            schema = spec.get("inputSchema")
            tool = MCPNativeTool(
                client_factory=lambda server=server: self._client(server),
                tool_name=name,
                tool_schema={
                    "description": spec.get("description", ""),
                    "args_schema": MCPToolResolver._json_schema_to_pydantic(name, schema)
                    if schema else None,
                },
                server_name=server,
                original_tool_name=spec.get("original_name", name),
            )
            tool.name = name  # keep the server's own tool name, without a server prefix
            tools.append(tool)
        return tools

    def start(self) -> Toolbox:
        for server in self._servers:
            if server not in self._tools:
                self._tools[server] = self._discover(server)
        return self

    def tools_for(self, role: str) -> list[Any]:
        tools: list[Any] = []
        for server in ROLE_SERVERS[role]:
            if server not in self._tools:
                raise RuntimeError(f"MCP server {server!r} for role {role!r} is not started")
            tools.extend(self._tools[server])
        withheld = ROLE_WITHHELD.get(role, frozenset())
        return [t for t in tools if t.name not in withheld]

    def stop(self) -> None:
        self._tools.clear()

    def __enter__(self) -> Toolbox:
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.stop()
