"""Auditor: security compliance of the nodes, door anomalies, and the decision log."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.mcp_server.devices import DeviceError
from src.mcp_server.engine.compliance import check_camera, check_gateway
from src.mcp_server.engine.risk import Evidence, assess_risk
from src.mcp_server.runtime import get_runtime

mcp = FastMCP(
    "smartgate-auditor",
    instructions="Security and compliance checks. Findings are graded critical, error, "
    "warning or info; report critical and error findings first.",
)


async def _safe(coro: Any) -> Any:
    try:
        return await coro
    except DeviceError:
        return None


@mcp.tool()
async def check_compliance(node_id: str | None = None) -> dict[str, Any]:
    """Check one node, or every node, against the security baseline: API token and
    decision key set, PIN enforced where policy requires it, PDP timeout covering the
    decision budget, clock set, doorId matching the inventory."""
    runtime = get_runtime()
    inventory = runtime.sot.inventory
    targets = [node_id] if node_id else list(inventory.nodes)
    findings = []
    for nid in targets:
        node = inventory.nodes.get(nid)
        if node is None:
            raise ValueError(f"unknown node {nid!r}")
        if node.kind == "gateway":
            client = runtime.fleet.gateway(nid)
            status, config = await asyncio.gather(_safe(client.status()), _safe(client.config()))
            findings += check_gateway(nid, inventory=inventory, policies=runtime.sot.policies,
                                      status=status, config=config,
                                      min_pdp_timeout_ms=runtime.min_pdp_timeout_ms)
        else:
            client = runtime.fleet.camera(nid)
            status, config = await asyncio.gather(_safe(client.status()), _safe(client.config()))
            findings += check_camera(nid, status=status, config=config)
    order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    findings.sort(key=lambda f: order[f.severity])
    return {"compliant": not any(f.severity in ("critical", "error") for f in findings),
            "findings": [f.model_dump() for f in findings]}


@mcp.tool()
async def detect_door_anomalies(door_id: str) -> dict[str, Any]:
    """Door-level risk signals right now: unattested motion, bad signatures, remote
    unlocks, tamper, lockouts and clock problems, from live device evidence."""
    runtime = get_runtime()
    door = runtime.sot.inventory.doors.get(door_id)
    if door is None:
        raise ValueError(f"unknown door {door_id!r}")
    gateway = runtime.fleet.gateway(door.gateway)
    camera = runtime.fleet.camera_for_door(door_id)
    gw_status, gw_events = await asyncio.gather(_safe(gateway.status()), _safe(gateway.events()))
    cam_status = cam_events = None
    if camera:
        cam_status, cam_events = await asyncio.gather(_safe(camera.status()),
                                                      _safe(camera.events()))
    evidence = Evidence(gateway_status=gw_status, gateway_events=gw_events,
                        camera_status=cam_status, camera_events=cam_events)
    signals = assess_risk(door_id=door_id, door=door, uid="", evidence=evidence,
                          policy=runtime.sot.policies.risk, now_epoch=int(time.time()))
    return {"door": door_id, "signals": [s.model_dump() for s in signals]}


@mcp.tool()
def get_decision_history(limit: int = 20, door: str | None = None, uid: str | None = None,
                         subject_id: str | None = None) -> list[dict[str, Any]]:
    """Recent PDP decisions, newest first, with effect, code and the stage that decided."""
    rows = get_runtime().decisions.recent(limit=limit, door=door, uid=uid, subject=subject_id)
    return [{
        "decision_id": r["decision_id"], "decided_at": r["decided_at"], "door": r["door"],
        "uid": r["uid"], "subject_id": r.get("subject_id"), "effect": r["effect"],
        "code": r["code"],
        "decided_by": next((s["name"] for s in r["stages"] if not s["passed"]), "all_stages"),
        "agent": (r.get("agent") or {}).get("code"),
    } for r in rows]


@mcp.tool()
def explain_decision(decision_id: str) -> dict[str, Any]:
    """Every stage, matched rule, risk signal and agent verdict behind one decision."""
    record = get_runtime().decisions.get(decision_id)
    if record is None:
        raise ValueError(f"no decision {decision_id!r} in recent history")
    return record


@mcp.tool()
def verify_decision_log_integrity() -> dict[str, Any]:
    """Walk the hash chain of the decision log and report the first broken link, if any."""
    return get_runtime().decisions.verify()
