"""Security compliance of live nodes against the inventory and the decision pipeline."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from src.mcp_server.engine.domain.inventory import Inventory
from src.mcp_server.engine.domain.policy import PolicySet

Severity = Literal["critical", "error", "warning", "info"]


class Finding(BaseModel):
    node: str
    severity: Severity
    code: str
    message: str


def check_gateway(
    node_id: str,
    *,
    inventory: Inventory,
    policies: PolicySet,
    status: dict[str, Any] | None,
    config: dict[str, Any] | None,
    min_pdp_timeout_ms: int,
) -> list[Finding]:
    node = inventory.nodes[node_id]
    door = inventory.doors[node.door]
    out: list[Finding] = []

    def add(severity: Severity, code: str, message: str) -> None:
        out.append(Finding(node=node_id, severity=severity, code=code, message=message))

    for which in ("api_token", "pdp_token", "decision_key"):
        env_name = getattr(node, f"{which}_env")
        if env_name and not node.secret(which):
            add("warning", "missing_secret_env", f"environment variable {env_name} is not set")

    if status is None or config is None:
        add("error", "unreachable", "node did not answer status/config")
        return out

    if config.get("apiToken") != "set":
        add("critical", "bench_mode_api", "API token cleared: anyone on the LAN can unlock")
    if config.get("decisionKey") != "set":
        add("critical", "unsigned_decisions", "decisionKey unset: decisions are not verified")
    if config.get("pdpToken") != "set":
        add("warning", "pdp_token_unset", "gateway does not authenticate itself to the PDP")
    if not config.get("pdpUrl"):
        add("error", "pdp_not_configured", "pdpUrl empty: the node never asks the PDP")
    if config.get("doorId") != node.door:
        add("error", "door_id_mismatch",
            f"doorId {config.get('doorId')!r} but inventory says {node.door!r}")

    require_pin = policies.defaults.require_pin if door.require_pin is None else door.require_pin
    if require_pin and config.get("requirePin") is False:
        add("critical", "pin_disabled", "requirePin is false but policy requires a PIN")

    timeout = config.get("pdpTimeoutMs")
    if isinstance(timeout, int) and timeout < min_pdp_timeout_ms:
        add("error", "pdp_timeout_below_budget",
            f"pdpTimeoutMs {timeout} < decision budget {min_pdp_timeout_ms} ms")
    if door.lockdown and config.get("degradedAllow"):
        add("error", "lockdown_offline_grant", "door in lockdown still grants from the cache")

    if not status.get("clockSet"):
        add("error", "clock_unset",
            "no NTP time: audit cannot be correlated, ACL TTLs never expire")
    if status.get("lcd") is False:
        add("info", "lcd_missing", "display not detected")
    last_code = (status.get("pdp") or {}).get("lastCode", 0)
    if last_code not in (0, 200):
        add("warning", "pdp_errors", f"last PDP call returned {last_code}")
    return out


def check_camera(node_id: str, *, status: dict[str, Any] | None,
                 config: dict[str, Any] | None) -> list[Finding]:
    out: list[Finding] = []
    if status is None:
        return [Finding(node=node_id, severity="error", code="unreachable",
                        message="recorder did not answer")]
    if not status.get("clockSet"):
        out.append(Finding(node=node_id, severity="error", code="clock_unset",
                           message="no NTP time: clips cannot attest badge events"))
    if config and not config.get("saveEvents", 1):
        out.append(Finding(node=node_id, severity="warning", code="evidence_disabled",
                           message="saveEvents is off"))
    out.append(Finding(node=node_id, severity="info", code="unauthenticated_api",
                       message="recorder HTTP API has no authentication; keep it on its VLAN"))
    return out
