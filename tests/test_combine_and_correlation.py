"""The agent can only tighten a decision; movements are classified like the console."""

from __future__ import annotations

import pytest

from src.mcp_server.engine.combine import combine_review
from src.mcp_server.engine.correlation import correlate
from src.mcp_server.engine.domain.access import AgentVerdict, Effect


def verdict(effect: str, confidence: float = 0.9, code: str = "consistent") -> AgentVerdict:
    return AgentVerdict(effect=effect, confidence=confidence, code=code)


@pytest.mark.parametrize(("engine", "review", "error", "mode", "expected"), [
    (Effect.PERMIT, None, None, "deny", (Effect.PERMIT, "R-1")),
    (Effect.PERMIT, verdict("permit"), None, "deny", (Effect.PERMIT, "R-1")),
    (Effect.PERMIT, verdict("permit", 0.4), None, "deny", (Effect.DENY, "agent_low_confidence")),
    (Effect.PERMIT, verdict("deny", code="tailgate_risk"), None, "deny",
     (Effect.DENY, "tailgate_risk")),
    (Effect.PERMIT, None, "timeout", "deny", (Effect.DENY, "agent_unavailable")),
    (Effect.PERMIT, None, "timeout", "rules", (Effect.PERMIT, "R-1")),
    (Effect.DENY, verdict("permit"), None, "rules", (Effect.DENY, "R-1")),
])
def test_combination_table(engine, review, error, mode, expected) -> None:
    result = combine_review(engine, "R-1", verdict=review, error=error, failure_mode=mode,
                            min_confidence=0.7)
    assert (result.effect, result.code) == expected


def test_movement_classes() -> None:
    t = 1_800_000_000
    gateway = [
        {"id": 1, "epoch": t, "effect": "permit"},          # walked through
        {"id": 2, "epoch": t + 100, "effect": "permit"},    # nobody came
        {"id": 3, "epoch": t + 200, "effect": "deny"},
        {"id": 4, "epoch": t + 300, "effect": "none"},      # not a credential event
    ]
    camera = [
        {"id": 10, "epoch": t + 5, "verdict": "classified"},
        {"id": 11, "epoch": t + 400, "verdict": "motion"},             # tailgate
        {"id": 12, "epoch": t + 500, "verdict": "rejected-geometry"},  # not a person
    ]
    report = correlate(gateway, camera, window_s=15)
    assert report.summary() == {"attested_transit": 1, "unattested_motion": 1,
                                "unconsummated_grant": 1, "denial": 1}


def test_correlation_refuses_without_clocks() -> None:
    report = correlate([], [], gateway_clock_set=True, camera_clock_set=False)
    assert not report.available
    assert "camera" in report.reason
