"""Process-wide services shared by every MCP server and by the PDP API."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from src.mcp_server.devices import Fleet
from src.mcp_server.engine.audit_log import DecisionLog
from src.mcp_server.engine.pipeline import DecisionEngine
from src.mcp_server.engine.plans import PlanStore
from src.mcp_server.engine.source_of_truth import SourceOfTruth
from src.settings import Settings, get_settings


@dataclass
class Runtime:
    settings: Settings
    sot: SourceOfTruth
    fleet: Fleet
    plans: PlanStore
    decisions: DecisionLog
    engine: DecisionEngine

    @classmethod
    def build(cls, settings: Settings) -> Runtime:
        sot = SourceOfTruth(settings.config_dir, backup_dir=settings.revisions_dir)
        return cls(
            settings=settings,
            sot=sot,
            fleet=Fleet(sot, timeout_s=settings.device_timeout_s),
            plans=PlanStore(settings.plans_dir, ttl_s=settings.plan_ttl_s),
            decisions=DecisionLog(settings.decision_log_path),
            engine=DecisionEngine(sot),
        )

    @property
    def min_pdp_timeout_ms(self) -> int:
        """The shortest gateway ``pdpTimeoutMs`` that leaves the PDP its whole budget."""
        if self.settings.agent_review == "off":
            return 2000
        return int(self.settings.decision_budget_s * 1000) + 1500


@lru_cache
def get_runtime() -> Runtime:
    return Runtime.build(get_settings())
