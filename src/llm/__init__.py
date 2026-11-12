"""Agent layer: CrewAI crews that reason over the MCP servers.

    llm/
    ├── config/      agents.yaml and tasks.yaml (roles, goals, prompts)
    ├── model.py     the LLM every agent uses
    ├── toolbox.py   MCP connections, least privilege per agent role
    ├── crews.py     access-review crew and operations crew
    └── decision.py  the PDP: engine stages, agent review, combine, sign, log
"""
