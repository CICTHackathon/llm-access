"""Simulator: what-if access requests and the policy regression suite (no devices touched)."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from src.mcp_server.engine.source_of_truth import parse_when
from src.mcp_server.engine.verifier import run_scenarios
from src.mcp_server.runtime import get_runtime

mcp = FastMCP(
    "smartgate-simulator",
    instructions="Dry-run access requests through the deterministic pipeline, assuming the "
    "correct PIN. Use it to explain an outcome or to test a policy before changing it.",
)


@mcp.tool()
def simulate_access(uid: str, door_id: str, at: str | None = None) -> dict[str, Any]:
    """Evaluate a card at a door at a local time (ISO-8601, default now) and return every
    stage, the matched rules and, for a deny, the near misses that explain it."""
    result = get_runtime().engine.simulate(uid, door_id, at=parse_when(at))
    auth = result.authorization
    return {
        "effect": result.effect.value,
        "code": result.code,
        "at": result.at.isoformat(),
        "subject": result.subject.id if result.subject else None,
        "stages": [s.model_dump() for s in result.stages],
        "matched_rules": [m.model_dump() for m in auth.matched] if auth else [],
        "near_misses": [m.model_dump() for m in auth.near_misses] if auth else [],
    }


@mcp.tool()
def run_policy_scenarios() -> dict[str, Any]:
    """Run every scenario in scenarios.yaml against the live policy and report failures."""
    runtime = get_runtime()

    def simulate(uid: str, door: str, at: Any) -> tuple[str, str]:
        result = runtime.engine.simulate(uid, door, at=parse_when(at))
        return result.effect.value, result.code

    outcomes = run_scenarios(runtime.sot.scenarios, simulate)
    failed = sum(not o.passed for o in outcomes)
    return {"passed": len(outcomes) - failed, "failed": failed,
            "outcomes": [o.as_dict() for o in outcomes]}
