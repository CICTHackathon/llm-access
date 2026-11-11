"""Verifier: validates a proposed change and, if it passes, issues a deployable plan.

A plan id is the only thing the deployer accepts. Errors block the plan; warnings
are carried on it so the executor and the auditor can see them.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from src.mcp_server.devices import DeviceError
from src.mcp_server.engine import verifier as checks
from src.mcp_server.engine.domain.identity import Directory
from src.mcp_server.engine.domain.policy import PolicySet
from src.mcp_server.engine.edits import (
    CredentialAction,
    EditError,
    PolicyAction,
    apply_credential_edit,
    apply_policy_edit,
)
from src.mcp_server.engine.offline_acl import ACL_CAPACITY, compute_offline_acl
from src.mcp_server.engine.pipeline import DecisionEngine
from src.mcp_server.engine.plans import PlanKind
from src.mcp_server.engine.source_of_truth import parse_when
from src.mcp_server.engine.verifier import (
    Issue,
    Verification,
    lint_policy,
    regression_issues,
    run_scenarios,
)
from src.mcp_server.runtime import get_runtime

mcp = FastMCP(
    "smartgate-verifier",
    instructions="Validate every change before it is deployed. A change that passes "
    "returns a plan_id; hand that id to the deployer. Fix errors and verify again.",
)


def _issue_plan(verification: Verification, *, kind: PlanKind, target: str, summary: str,
                payload: dict[str, Any], base_version: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = verification.model_dump()
    if verification.ok:
        plan = get_runtime().plans.create(
            kind=kind, target=target, summary=summary, payload=payload,
            issues=[i.model_dump() for i in verification.issues], base_version=base_version)
        result.update(plan_id=plan.id, expires_at=plan.expires_at.isoformat())
    else:
        result["plan_id"] = None
    return result


@mcp.tool()
async def verify_gateway_config(node_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Validate gateway settings, e.g. {"pdpTimeoutMs": 25000, "openHoldMs": 4000}.

    Checks firmware ranges, cross-field rules (servo angles), and site invariants
    (PIN required by policy, doorId matches inventory, PDP timeout covers the
    decision budget). Secrets (apiToken, decisionKey, pdpToken) are refused.
    """
    runtime = get_runtime()
    try:
        current = await runtime.fleet.gateway(node_id).config()
    except (DeviceError, KeyError):
        current = None
    verification = verify_gateway_config_impl(node_id, changes, current)
    return _issue_plan(verification, kind="gateway_config", target=node_id,
                       summary=f"set {sorted(verification.normalised)} on {node_id}",
                       payload={"node": node_id, "changes": verification.normalised})


def verify_gateway_config_impl(node_id: str, changes: dict[str, Any],
                               current: dict[str, Any] | None) -> Verification:
    runtime = get_runtime()
    return checks.verify_gateway_config(
        node_id, changes, inventory=runtime.sot.inventory, policies=runtime.sot.policies,
        current=current, min_pdp_timeout_ms=runtime.min_pdp_timeout_ms)


@mcp.tool()
def verify_camera_config(node_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Validate recorder settings, e.g. {"cellDelta": 30, "minFrames": 3}."""
    verification = verify_camera_config_impl(node_id, changes)
    return _issue_plan(verification, kind="camera_config", target=node_id,
                       summary=f"set {sorted(verification.normalised)} on {node_id}",
                       payload={"node": node_id, "changes": verification.normalised})


def verify_camera_config_impl(node_id: str, changes: dict[str, Any]) -> Verification:
    return checks.verify_camera_config(node_id, changes, inventory=get_runtime().sot.inventory)


@mcp.tool()
def verify_offline_acl(door_id: str) -> dict[str, Any]:
    """Compute the cached authorisation set the door's gateway may use while the PDP is
    unreachable, and issue a plan to sync it. Only subjects permitted right now by an
    offline_cache rule are included, each with a TTL that ends when that rule would stop
    holding. Digests are kept in the plan file and never returned."""
    runtime = get_runtime()
    sot = runtime.sot
    if door_id not in sot.inventory.doors:
        raise ValueError(f"unknown door {door_id!r}")
    acl = compute_offline_acl(sot, door_id)
    issues: list[Issue] = []
    if len(acl.entries) > ACL_CAPACITY:
        issues.append(Issue(severity="error", code="acl_capacity",
                            message=f"{len(acl.entries)} entries exceed the gateway's "
                                    f"{ACL_CAPACITY} slots; narrow the offline rules"))
    if sot.inventory.doors[door_id].lockdown and acl.entries:
        issues.append(Issue(severity="error", code="lockdown",
                            message="a door in lockdown must not hold an offline cache"))
    if not acl.entries:
        issues.append(Issue(severity="warning", code="empty_cache",
                            message="nobody qualifies right now; the gateway will deny "
                                    "everything while the PDP is unreachable"))
    verification = Verification.of(issues)
    result = _issue_plan(
        verification, kind="acl_sync", target=sot.inventory.doors[door_id].gateway,
        summary=f"sync {len(acl.entries)} offline entries for {door_id}",
        payload={"door": door_id, "entries": [{**e.model_dump(), **e.device_payload()}
                                              for e in acl.entries]},
        base_version=sot.version("identities"))
    result["entries"] = [e.model_dump() for e in acl.entries]
    result["excluded"] = acl.excluded
    return result


@mcp.tool()
def verify_policy_change(action: PolicyAction, rule: dict[str, Any] | None = None,
                         rule_id: str | None = None) -> dict[str, Any]:
    """Validate adding, replacing or removing a rule.

    ``rule`` uses the policies.yaml shape: {"id", "description", "effect",
    "target": {"zones"|"doors"|"any"}, "condition": {...}, "offline_cache"}. The
    candidate policy is linted and every regression scenario is re-run against it; a
    change that flips an expected outcome is rejected.
    """
    runtime = get_runtime()
    sot = runtime.sot
    try:
        candidate_doc = apply_policy_edit(sot.dump("policies"), action, rule, rule_id)
    except EditError as exc:
        return Verification.of([Issue(severity="error", code="bad_edit", message=str(exc))]
                               ).model_dump() | {"plan_id": None}
    roles = {r for s in sot.directory.subjects for r in s.roles}
    candidate, issues = lint_policy(candidate_doc, inventory=sot.inventory, roles_in_use=roles)
    outcomes = []
    if candidate is not None:
        outcomes = _scenarios_against(policies=candidate)
        issues += regression_issues(outcomes)
    verification = Verification.of(issues)
    result = _issue_plan(
        verification, kind="policy_update", target="policies",
        summary=f"{action} rule {rule_id or (rule or {}).get('id')}",
        payload={"action": action, "rule": rule, "rule_id": rule_id},
        base_version=sot.version("policies"))
    result["scenarios"] = [o.as_dict() for o in outcomes]
    return result


@mcp.tool()
def verify_credential_change(action: CredentialAction, uid: str,
                             subject_id: str | None = None) -> dict[str, Any]:
    """Validate assigning a card to a subject or revoking a card. PINs are set out of band."""
    sot = get_runtime().sot
    try:
        candidate_doc = apply_credential_edit(sot.dump("identities"), action, uid, subject_id)
        candidate = Directory.model_validate(candidate_doc)
    except (EditError, ValueError) as exc:
        return Verification.of([Issue(severity="error", code="bad_edit", message=str(exc))]
                               ).model_dump() | {"plan_id": None}
    issues: list[Issue] = []
    cred = candidate.credential(uid)
    if action == "assign" and cred and not cred.pin:
        issues.append(Issue(severity="warning", code="no_pin",
                            message="card has no PIN; PIN doors deny it until one is set"))
    outcomes = _scenarios_against(directory=candidate)
    issues += regression_issues(outcomes)
    verification = Verification.of(issues)
    return _issue_plan(verification, kind="credential_update", target="identities",
                       summary=f"{action} {uid}" + (f" -> {subject_id}" if subject_id else ""),
                       payload={"action": action, "uid": uid, "subject_id": subject_id},
                       base_version=sot.version("identities"))


@mcp.tool()
def get_plan(plan_id: str) -> dict[str, Any]:
    """A plan's status, payload (without secrets), issues and result."""
    return get_runtime().plans.get(plan_id).public_view()


def _scenarios_against(*, policies: PolicySet | None = None,
                       directory: Directory | None = None) -> list:
    sot = get_runtime().sot
    overrides = {k: v for k, v in (("policies", policies), ("directory", directory)) if v}
    engine = DecisionEngine(sot.overlay(**overrides))

    def simulate(uid: str, door: str, at: Any) -> tuple[str, str]:
        result = engine.simulate(uid, door, at=parse_when(at))
        return result.effect.value, result.code

    return run_scenarios(sot.scenarios, simulate)
