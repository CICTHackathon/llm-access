"""MCP layer: seven role-scoped servers over a deterministic engine and a device adapter.

    mcp_server/
    ├── engine/    deterministic reasoning: rules, risk, verification, plans, audit log
    ├── devices/   southbound HTTP adapter to the edge nodes (firmware lives in iot/)
    ├── servers/   the MCP servers the agents connect to
    ├── runtime.py shared services for one process
    └── main.py    `python -m src.mcp_server.main <server>`
"""
