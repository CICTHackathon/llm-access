"""Configuration reasoning: verify -> plan -> deploy, and the offline cache."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from src.mcp_server.engine.offline_acl import compute_offline_acl
from src.mcp_server.servers import deployer, verifier
from tests.conftest import local


def codes(result: dict) -> set[str]:
    return {i["code"] for i in result["issues"]}


async def test_gateway_config_limits_and_invariants(runtime) -> None:
    result = await verifier.verify_gateway_config(
        "gw-1", {"openAngle": 90, "pinAttempts": 50, "requirePin": False,
                 "decisionKey": "x", "colour": "red"})
    assert result["plan_id"] is None
    assert {"angles_equal", "out_of_range", "pin_required_by_policy", "secret_in_plan",
            "unknown_key"} <= codes(result)


async def test_pdp_timeout_must_cover_the_decision_budget(runtime) -> None:
    result = await verifier.verify_gateway_config("gw-1", {"pdpTimeoutMs": 5000})
    assert "pdp_timeout_below_budget" in codes(result)
    ok = await verifier.verify_gateway_config("gw-1", {"pdpTimeoutMs": 25000})
    assert ok["ok"] and ok["plan_id"]


async def test_verified_plan_is_applied_and_read_back(runtime, gateway) -> None:
    plan = await verifier.verify_gateway_config("gw-1", {"pdpTimeoutMs": 25000,
                                                         "openHoldMs": 4000})
    result = await deployer.apply_plan(plan["plan_id"])
    assert result["applied"] is True
    assert gateway.config["pdpTimeoutMs"] == 25000
    assert result["changed"]["pdpTimeoutMs"] == {"from": 4000, "to": 25000}
    again = await deployer.apply_plan(plan["plan_id"])
    assert again["applied"] is False and "applied, not verified" in again["error"]


async def test_rollback_restores_the_previous_config(runtime, gateway) -> None:
    plan = await verifier.verify_gateway_config("gw-1", {"pdpTimeoutMs": 25000})
    await deployer.apply_plan(plan["plan_id"])
    gateway.config["pdpTimeoutMs"] = 25000
    # the saved revision has 4000, which is below the budget, so rollback is refused
    refused = await deployer.rollback_gateway("gw-1")
    assert refused["rolled_back"] is False
    assert any(i["code"] == "pdp_timeout_below_budget" for i in refused["issues"])


async def test_deployer_refuses_tampered_and_expired_plans(runtime) -> None:
    plan_id = (await verifier.verify_gateway_config("gw-1", {"openHoldMs": 4000}))["plan_id"]
    path = runtime.plans._path(plan_id)
    data = json.loads(path.read_text())
    data["payload"]["changes"]["openHoldMs"] = 60000
    path.write_text(json.dumps(data))
    assert "modified after verification" in (await deployer.apply_plan(plan_id))["error"]

    plan_id = (await verifier.verify_gateway_config("gw-1", {"openHoldMs": 4000}))["plan_id"]
    data = json.loads(runtime.plans._path(plan_id).read_text())
    data["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    runtime.plans._path(plan_id).write_text(json.dumps(data))
    assert "expired" in (await deployer.apply_plan(plan_id))["error"]


async def test_dry_run_touches_nothing(runtime, gateway, monkeypatch) -> None:
    monkeypatch.setattr(runtime.settings, "deploy_mode", "dry_run")
    plan_id = (await verifier.verify_gateway_config("gw-1", {"openHoldMs": 4000}))["plan_id"]
    result = await deployer.apply_plan(plan_id)
    assert result["dry_run"] is True
    assert gateway.config["openHoldMs"] == 5000


def test_policy_change_that_breaks_a_scenario_is_rejected(runtime) -> None:
    result = verifier.verify_policy_change("remove", rule_id="D-INTERN-SERVER-ROOM")
    assert result["plan_id"] is None
    assert "scenario_regression" in codes(result)


def test_unconditional_permit_is_rejected(runtime) -> None:
    rule = {"id": "R-OPEN", "effect": "permit", "target": {"zones": ["lobby"]}}
    assert "unconditional_permit" in codes(verifier.verify_policy_change("add", rule=rule))


async def test_policy_plan_goes_stale_when_the_policy_changes(runtime) -> None:
    rule = {"id": "R-LOBBY", "effect": "permit", "target": {"zones": ["lobby"]},
            "condition": {"roles_any": ["employee"]}}
    first = verifier.verify_policy_change("add", rule=rule)
    other = {**rule, "id": "R-LOBBY-2"}
    second = verifier.verify_policy_change("add", rule=other)
    assert (await deployer.apply_plan(second["plan_id"]))["applied"] is True
    stale = await deployer.apply_plan(first["plan_id"])
    assert stale["applied"] is False and "since changed" in stale["error"]
    assert runtime.sot.policies.rule("R-LOBBY-2") is not None


def test_offline_cache_follows_rules_and_schedules(runtime) -> None:
    morning = compute_offline_acl(runtime.sot, "door-1", local("2026-11-10T10:00"))
    by_subject = {e.subject: e for e in morning.entries}
    assert set(by_subject) == {"alice", "bao"}       # chi's rule is not offline_cache
    assert by_subject["alice"].ttl == 3600
    late = compute_offline_acl(runtime.sot, "door-1", local("2026-11-10T21:30"))
    assert {e.subject: e.ttl for e in late.entries}["alice"] == 1800  # window ends at 22:00
    excluded = {x["subject"]: x["reason"] for x in morning.excluded}
    assert excluded["chi"] == "rule_not_offline"


async def test_acl_sync_never_returns_digests(runtime, gateway, monkeypatch) -> None:
    real = compute_offline_acl
    monkeypatch.setattr(verifier, "compute_offline_acl",
                        lambda sot, door: real(sot, door, local("2026-11-10T10:00")))
    result = verifier.verify_offline_acl("door-1")
    assert "pin" not in json.dumps(result["entries"])
    applied = await deployer.apply_plan(result["plan_id"])
    assert applied["applied"] is True
    assert set(gateway.acl) == {"0xa1b2c3d4", "0xb2c3d4e5"}
    assert len(gateway.acl["0xa1b2c3d4"]["pin"]) == 64


@pytest.mark.parametrize("uid", ["0xa1b2c3d4"])
def test_credential_assign_requires_revoking_first(runtime, uid) -> None:
    result = verifier.verify_credential_change("assign", uid, "bao")
    assert result["plan_id"] is None and "bad_edit" in codes(result)
