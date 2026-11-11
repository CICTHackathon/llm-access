"""The two crews.

* **Access review** (sequential): evidence analyst, then access judge. It runs inside
  the PDP for a request the rules already permitted, and returns an AgentVerdict.
* **Operations** (hierarchical): the orchestrator, as manager, delegates to the
  configurator, the executor and the compliance auditor to carry out an operator's
  intent through plan, verify, deploy, audit.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from src.llm.model import build_llm
from src.llm.toolbox import Toolbox, servers_for
from src.mcp_server.engine.domain.access import AgentVerdict
from src.settings import Settings

CONFIG_DIR = Path(__file__).parent / "config"
ACCESS_ROLES = ("evidence_analyst", "access_judge")
OPERATIONS_ROLES = ("configurator", "executor", "compliance_auditor")


class OperationReport(BaseModel):
    outcome: Literal["completed", "partial", "no_change", "failed"]
    summary: str
    plans_applied: list[str] = Field(default_factory=list)
    plans_failed: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    follow_up: list[str] = Field(default_factory=list)


@lru_cache
def _config(name: str) -> dict[str, Any]:
    return yaml.safe_load((CONFIG_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


class CrewFactory:
    def __init__(self, settings: Settings, toolbox: Toolbox | None) -> None:
        self.settings = settings
        self.toolbox = toolbox
        self.llm = build_llm(settings)

    def agent(self, key: str, **overrides: Any) -> Any:
        from crewai import Agent

        spec = _config("agents")[key]
        tools = self.toolbox.tools_for(key) if self.toolbox else []
        params: dict[str, Any] = {
            "role": spec["role"], "goal": spec["goal"], "backstory": spec["backstory"],
            "tools": tools, "llm": self.llm, "allow_delegation": False,
            "verbose": self.settings.verbose_agents,
        }
        params.update(overrides)
        return Agent(**params)

    def task(self, key: str, *, agent: Any = None, prefix: str = "", **overrides: Any) -> Any:
        from crewai import Task

        spec = _config("tasks")[key]
        params: dict[str, Any] = {"description": prefix + spec["description"],
                                  "expected_output": spec["expected_output"]}
        if agent is not None:
            params["agent"] = agent
        params.update(overrides)
        return Task(**params)


class AccessReviewer:
    """Long-lived: the MCP servers stay up between requests, crews are built per request."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.toolbox = Toolbox(servers_for(ACCESS_ROLES)).start()
        self.factory = CrewFactory(settings, self.toolbox)

    def review(self, inputs: dict[str, Any]) -> AgentVerdict:
        from crewai import Crew, Process

        budget = max(int(self.settings.decision_budget_s), 5)
        analyst = self.factory.agent("evidence_analyst", max_iter=3, max_execution_time=budget)
        judge = self.factory.agent("access_judge", max_iter=4, max_execution_time=budget)
        gather = self.factory.task("gather_evidence", agent=analyst)
        judge_task = self.factory.task("judge_access", agent=judge, context=[gather],
                                       output_pydantic=AgentVerdict)
        crew = Crew(agents=[analyst, judge], tasks=[gather, judge_task],
                    process=Process.sequential, verbose=self.settings.verbose_agents)
        output = crew.kickoff(inputs={k: _text(v) for k, v in inputs.items()})
        if output.pydantic is not None:
            return AgentVerdict.model_validate(output.pydantic.model_dump())
        return AgentVerdict.model_validate_json(output.raw)

    def close(self) -> None:
        self.toolbox.stop()


def run_operations(settings: Settings, intent: str, *, dry_run: bool) -> OperationReport:
    """Carry out an operator intent with the hierarchical operations crew."""
    from crewai import Crew, Process

    env = {"LLM_ACCESS_DEPLOY_MODE": "dry_run" if dry_run else settings.deploy_mode}
    with Toolbox(servers_for(OPERATIONS_ROLES), env=env) as toolbox:
        factory = CrewFactory(settings, toolbox)
        manager = factory.agent("orchestrator", tools=[], allow_delegation=True, max_iter=25)
        workers = {role: factory.agent(role, max_iter=15) for role in OPERATIONS_ROLES}
        roles = _config("agents")

        def delegated(key: str, role: str, **kw: Any) -> Any:
            return factory.task(key, prefix=f"Delegate this to the {roles[role]['role']}.\n\n",
                                **kw)

        plan = delegated("plan_change", "configurator")
        execute = delegated("execute_change", "executor", context=[plan])
        audit = delegated("audit_change", "compliance_auditor", context=[plan, execute],
                          output_pydantic=OperationReport)
        crew = Crew(agents=list(workers.values()), tasks=[plan, execute, audit],
                    process=Process.hierarchical, manager_agent=manager,
                    verbose=settings.verbose_agents)
        output = crew.kickoff(inputs={"intent": intent})
    if output.pydantic is not None:
        return OperationReport.model_validate(output.pydantic.model_dump())
    return OperationReport(outcome="partial", summary=output.raw)


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=1, default=str, ensure_ascii=False)
