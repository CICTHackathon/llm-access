"""Deployer: applies verified plans to devices and documents, and rolls them back.

It accepts nothing but a plan id. Every apply re-checks the plan (status, expiry,
checksum, base version), records the previous device state as a revision, and reads
the device back afterwards to confirm the change actually took.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from src.mcp_server.devices import DeviceError
from src.mcp_server.engine.edits import apply_credential_edit, apply_policy_edit
from src.mcp_server.engine.plans import Plan, PlanError, PlanStatus
from src.mcp_server.engine.verifier import GATEWAY_FIELDS
from src.mcp_server.runtime import Runtime, get_runtime
from src.mcp_server.servers.verifier import verify_gateway_config_impl

mcp = FastMCP(
    "smartgate-deployer",
    instructions="Apply plans issued by the verifier, by plan_id only. Report the result "
    "exactly as returned; a failed apply is not retried with a different change.",
)

_DOCUMENT_OF = {"policy_update": "policies", "credential_update": "identities",
                "acl_sync": "identities"}


@mcp.tool()
def list_plans(status: PlanStatus | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Recent plans, newest first, optionally filtered by status."""
    return [{"id": p.id, "kind": p.kind, "target": p.target, "summary": p.summary,
             "status": p.status, "expires_at": p.expires_at.isoformat()}
            for p in get_runtime().plans.list(status=status, limit=limit)]


@mcp.tool()
async def apply_plan(plan_id: str) -> dict[str, Any]:
    """Apply a verified plan. In dry_run deploy mode, report what would change instead."""
    runtime = get_runtime()
    try:
        plan = runtime.plans.get(plan_id)
        document = _DOCUMENT_OF.get(plan.kind)
        current = runtime.sot.version(document) if document else None
        plan = runtime.plans.claim(plan_id, current_version=current)
    except PlanError as exc:
        return {"applied": False, "plan_id": plan_id, "error": str(exc)}

    if runtime.settings.deploy_mode == "dry_run":
        return {"applied": False, "dry_run": True, "plan": plan.public_view()}

    try:
        result = await _APPLY[plan.kind](runtime, plan)
    except (DeviceError, PlanError, ValueError) as exc:
        runtime.plans.finish(plan, "failed", {"error": str(exc)})
        return {"applied": False, "plan_id": plan_id, "error": str(exc)}
    status: PlanStatus = "applied" if result.get("confirmed", True) else "failed"
    runtime.plans.finish(plan, status, result)
    return {"applied": status == "applied", "plan_id": plan_id, **result}


@mcp.tool()
async def rollback_gateway(node_id: str) -> dict[str, Any]:
    """Restore the gateway settings saved before the last applied config plan.
    The restored record is re-verified first, so a rollback cannot break an invariant."""
    runtime = get_runtime()
    revision = _latest_revision(runtime, node_id)
    if revision is None:
        return {"rolled_back": False, "error": f"no saved revision for {node_id}"}
    restore = {k: v for k, v in revision["config"].items() if k in GATEWAY_FIELDS}
    gateway = runtime.fleet.gateway(node_id)
    verification = verify_gateway_config_impl(node_id, restore, await gateway.config())
    if not verification.ok:
        return {"rolled_back": False, "issues": verification.model_dump()["issues"]}
    if runtime.settings.deploy_mode == "dry_run":
        return {"rolled_back": False, "dry_run": True, "would_restore": verification.normalised}
    await gateway.set_config(verification.normalised)
    return {"rolled_back": True, "revision": revision["saved_at"],
            "restored": verification.normalised}


@mcp.tool()
async def override_door(gateway_id: str, action: Literal["lock", "unlock"],
                        reason: str) -> dict[str, Any]:
    """Operator override of a door latch. Disabled unless LLM_ACCESS_ALLOW_ACTUATION=true;
    the gateway audits it as a remote action with no credential behind it."""
    runtime = get_runtime()
    if not runtime.settings.allow_actuation:
        return {"done": False, "error": "actuation is disabled (LLM_ACCESS_ALLOW_ACTUATION)"}
    if runtime.settings.deploy_mode == "dry_run":
        return {"done": False, "dry_run": True, "would": f"{action} {gateway_id}"}
    gateway = runtime.fleet.gateway(gateway_id)
    who = f"agent:{reason}"[:23]
    await (gateway.unlock(who) if action == "unlock" else gateway.lock(who))
    return {"done": True, "action": action, "gateway": gateway_id, "audited_as": who}


# ----------------------------------------------------------------- appliers ---

async def _apply_gateway_config(runtime: Runtime, plan: Plan) -> dict[str, Any]:
    node_id, changes = plan.payload["node"], plan.payload["changes"]
    gateway = runtime.fleet.gateway(node_id)
    before = await gateway.config()
    _save_revision(runtime, node_id, before, plan.id)
    await gateway.set_config(changes)
    after = await gateway.config()
    mismatched = {k: {"wanted": v, "got": after.get(k)} for k, v in changes.items()
                  if after.get(k) != v}
    return {"confirmed": not mismatched, "mismatched": mismatched,
            "changed": {k: {"from": before.get(k), "to": after.get(k)} for k in changes}}


async def _apply_camera_config(runtime: Runtime, plan: Plan) -> dict[str, Any]:
    node_id, changes = plan.payload["node"], plan.payload["changes"]
    camera = runtime.fleet.camera(node_id)
    before = await camera.config()
    _save_revision(runtime, node_id, before, plan.id)
    await camera.set_config(changes)
    after = await camera.config()
    mismatched = {k: {"wanted": v, "got": after.get(k)} for k, v in changes.items()
                  if int(after.get(k, -1)) != int(v)}
    return {"confirmed": not mismatched, "mismatched": mismatched}


async def _apply_acl_sync(runtime: Runtime, plan: Plan) -> dict[str, Any]:
    gateway = runtime.fleet.gateway(plan.target)
    desired = {e["uid"]: e for e in plan.payload["entries"]}
    present = {e["uid"] for e in (await gateway.acl()).get("entries", [])}
    removed = sorted(present - set(desired))
    for uid in removed:
        await gateway.acl_remove(uid)
    for entry in desired.values():  # aclAdd upserts by uid
        await gateway.acl_upsert(entry["uid"], entry["pin"], int(entry["ttl"]))
    after = {e["uid"] for e in (await gateway.acl()).get("entries", [])}
    return {"confirmed": after == set(desired), "removed": removed,
            "upserted": sorted(desired), "on_device": sorted(after)}


async def _apply_policy_update(runtime: Runtime, plan: Plan) -> dict[str, Any]:
    p = plan.payload
    doc = apply_policy_edit(runtime.sot.dump("policies"), p["action"], p.get("rule"),
                            p.get("rule_id"))
    version = runtime.sot.write("policies", doc)
    return {"confirmed": True, "policies_version": version, "policy_set_version": doc["version"]}


async def _apply_credential_update(runtime: Runtime, plan: Plan) -> dict[str, Any]:
    p = plan.payload
    doc = apply_credential_edit(runtime.sot.dump("identities"), p["action"], p["uid"],
                                p.get("subject_id"))
    version = runtime.sot.write("identities", doc)
    return {"confirmed": True, "identities_version": version}


_APPLY = {
    "gateway_config": _apply_gateway_config,
    "camera_config": _apply_camera_config,
    "acl_sync": _apply_acl_sync,
    "policy_update": _apply_policy_update,
    "credential_update": _apply_credential_update,
}


def _save_revision(runtime: Runtime, node_id: str, config: dict[str, Any], plan_id: str) -> None:
    directory = runtime.settings.revisions_dir / node_id
    directory.mkdir(parents=True, exist_ok=True)
    saved_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    record = {"node": node_id, "plan_id": plan_id, "saved_at": saved_at, "config": config}
    (directory / f"{saved_at}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")


def _latest_revision(runtime: Runtime, node_id: str) -> dict[str, Any] | None:
    directory = runtime.settings.revisions_dir / node_id
    files = sorted(directory.glob("*.json")) if directory.exists() else []
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None
