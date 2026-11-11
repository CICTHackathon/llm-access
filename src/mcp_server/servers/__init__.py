"""The seven role-scoped MCP servers. Each agent is connected only to the ones it needs.

| Server     | Role                                   | Mutates                       |
|------------|----------------------------------------|-------------------------------|
| librarian  | Source of truth: site, doors, policy   | nothing                       |
| identity   | Subjects, cards, card enrolment        | nothing (enrolment is a read) |
| verifier   | Pre-deployment validation, plan issue  | plan store                    |
| deployer   | Applies verified plans, rollback       | devices, policy, identities   |
| observer   | Live status and events of the nodes    | nothing                       |
| auditor    | Compliance, anomalies, decision log    | nothing                       |
| simulator  | What-if access requests, regressions   | nothing                       |
"""

SERVERS: dict[str, str] = {
    "librarian": "src.mcp_server.servers.librarian",
    "identity": "src.mcp_server.servers.identity",
    "verifier": "src.mcp_server.servers.verifier",
    "deployer": "src.mcp_server.servers.deployer",
    "observer": "src.mcp_server.servers.observer",
    "auditor": "src.mcp_server.servers.auditor",
    "simulator": "src.mcp_server.servers.simulator",
}
