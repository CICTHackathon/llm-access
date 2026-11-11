"""Contextual risk signals for one request, computed from evidence gathered at decision time.

``critical`` signals deny outright. ``warn`` and ``info`` signals are handed to the
access-judge agent, which weighs them against the natural-language guidance.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.mcp_server.engine.correlation import correlate
from src.mcp_server.engine.domain.access import RiskSignal
from src.mcp_server.engine.domain.inventory import Door
from src.mcp_server.engine.domain.policy import RiskPolicy

CLOCK_SET_AFTER = 1_700_000_000  # same predicate as the firmware's clockSet()


class Evidence(BaseModel):
    """What the PDP could learn about the door and the card when the request arrived.

    ``None`` means the source was not consulted or did not answer; an empty list means
    it answered with nothing.
    """

    gateway_status: dict[str, Any] | None = None
    gateway_events: list[dict[str, Any]] | None = None
    camera_status: dict[str, Any] | None = None
    camera_events: list[dict[str, Any]] | None = None
    recent_decisions: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def _within(event: dict[str, Any], now_epoch: int, window_s: int) -> bool:
    epoch = int(event.get("epoch") or 0)
    return epoch > CLOCK_SET_AFTER and 0 <= now_epoch - epoch <= window_s


def assess_risk(
    *,
    door_id: str,
    door: Door,
    uid: str,
    evidence: Evidence,
    policy: RiskPolicy,
    now_epoch: int,
) -> list[RiskSignal]:
    signals: list[RiskSignal] = []

    def add(code: str, severity: str, detail: str, **data: Any) -> None:
        signals.append(RiskSignal(code=code, severity=severity, detail=detail, data=data))

    if door.lockdown:
        add("door_lockdown", "critical", f"{door_id} is in lockdown in the source of truth")

    denials = [
        d for d in evidence.recent_decisions
        if d.get("uid") == uid and d.get("effect") == "deny"
        and 0 <= now_epoch - int(d.get("epoch", 0)) <= policy.recent_denials_window_s
    ]
    if len(denials) >= policy.max_recent_denials:
        add("denial_velocity", "critical",
            f"{len(denials)} denials for this card in the last "
            f"{policy.recent_denials_window_s}s", codes=[d.get("code") for d in denials])
    elif denials:
        add("recent_denials", "warn", f"{len(denials)} recent denial(s) for this card",
            codes=[d.get("code") for d in denials])

    gw_status = evidence.gateway_status or {}
    if evidence.gateway_status is not None:
        if not gw_status.get("clockSet", True):
            add("gateway_clock_unset", "warn",
                "gateway has no wall-clock time; audit events cannot be correlated")
        if gw_status.get("signedDecisions") is False:
            add("unsigned_decisions", "warn",
                "gateway accepts unsigned decisions (decisionKey not set)")

    window = policy.anomaly_window_s
    events = [e for e in (evidence.gateway_events or []) if _within(e, now_epoch, window)]
    bad_sigs = [e for e in events if e.get("reason") == "bad_signature"]
    if bad_sigs:
        add("bad_signature", "warn",
            f"{len(bad_sigs)} decision(s) with a bad signature rejected in the last {window}s")
    remote = [e for e in events if e.get("reason") == "remote" and e.get("effect") == "permit"]
    if remote:
        add("remote_unlock", "warn",
            f"{len(remote)} operator remote unlock(s) in the last {window}s",
            who=[e.get("note") for e in remote])
    if any(e.get("reason") == "tamper" for e in events):
        add("tamper", "warn", f"reader tamper reported in the last {window}s")
    if any(e.get("state") == "lockout" for e in events):
        add("pin_lockout", "info", f"PIN attempt lockout at this door in the last {window}s")

    if evidence.gateway_events is not None and evidence.camera_events is not None:
        report = correlate(
            [e for e in evidence.gateway_events if _within(e, now_epoch, window)],
            [e for e in evidence.camera_events if _within(e, now_epoch, window)],
            window_s=policy.correlation_window_s,
            gateway_clock_set=bool(gw_status.get("clockSet", True)),
            camera_clock_set=bool((evidence.camera_status or {}).get("clockSet", True)),
        )
        if not report.available:
            add("correlation_unavailable", "info", report.reason)
        else:
            unattested = report.count("unattested_motion")
            if unattested:
                add("unattested_motion", "warn",
                    f"{unattested} camera event(s) with no credential in the last {window}s "
                    "(possible tailgate or propped door)", count=unattested)
            unused = report.count("unconsummated_grant")
            if unused:
                add("unconsummated_grant", "info",
                    f"{unused} grant(s) with no recorded movement in the last {window}s",
                    count=unused)
    elif door.camera:
        add("camera_evidence_missing", "info",
            "the door has a camera but its events were not available")

    for error in evidence.errors:
        add("evidence_unavailable", "info", error)

    return signals
