"""Entry point for the MCP servers.

    python -m src.mcp_server.main librarian                  # stdio (what CrewAI spawns)
    python -m src.mcp_server.main observer --transport streamable-http --port 8101
"""

from __future__ import annotations

import argparse
import importlib

from mcp.server.fastmcp import FastMCP

from src.mcp_server.servers import SERVERS


def load_server(name: str) -> FastMCP:
    if name not in SERVERS:
        raise SystemExit(f"unknown server {name!r}; choose from {', '.join(SERVERS)}")
    return importlib.import_module(SERVERS[name]).mcp


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run one Smart Gateway MCP server.")
    parser.add_argument("server", choices=sorted(SERVERS))
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"],
                        default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args(argv)

    server = load_server(args.server)
    if args.transport != "stdio":
        server.settings.host = args.host
        server.settings.port = args.port
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
