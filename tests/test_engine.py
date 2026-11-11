"""Rule evaluation, the stage pipeline and risk signals."""

from __future__ import annotations

from datetime import time

import pytest

from src.mcp_server.engine.domain.access import AccessRequest, Effect
from src.mcp_server.engine.domain.policy import Schedule
from src.mcp_server.engine.pipeline import DecisionEngine
from src.mcp_server.engine.risk import Evidence
from src.mcp_server.engine.security import pin_digest
from src.mcp_server.engine.source_of_truth import SourceOfTruth, parse_when
from src.mcp_server.engine.verifier import run_scenarios
from tests.conftest import local

TXN = "00112233aabbccdd"


@pytest.fixture
def sot(config_dir) -> SourceOfTruth:
    return SourceOfTruth(config_dir)


@pytest.fixture
def engine(sot) -> DecisionEngine:
    return DecisionEngine(sot)


def request(uid: str = "0xa1b2c3d4", door: str = "door-1", pin: str | None = "1234",
            txn: str = TXN, epoch: int = 0) -> AccessRequest:
    return AccessRequest(txn=txn, door=door, uid=uid, epoch=epoch,
                         pinDigest=pin_digest(txn, pin) if pin else "")


def test_regression_scenarios_hold(sot, engine) -> None:
    def simulate(uid, door, at):
        result = engine.simulate(uid, door, at=parse_when(at))
        return result.effect.value, result.code

    failed = [o.as_dict() for o in run_scenarios(sot.scenarios, simulate) if not o.passed]
    assert failed == []


def test_overnight_schedule() -> None:
    night = Schedule(days=["mon"], start=time(22), end=time(6))
    assert night.contains(local("2026-11-09T23:00"))      # Monday evening
    assert night.contains(local("2026-11-10T05:59"))      # Tuesday morning, Monday's window
    assert not night.contains(local("2026-11-11T05:00"))  # Wednesday morning: Tuesday closed
    assert night.seconds_remaining(local("2026-11-09T23:00")) == 7 * 3600


def test_near_miss_explains_a_schedule_denial(engine) -> None:
    result = engine.simulate("0xa1b2c3d4", "door-1", at=local("2026-11-10T23:30"))
    assert result.effect is Effect.DENY
    assert result.code == "outside_schedule"
    assert result.authorization.near_misses[0].rule_id == "R-STAFF-DEPT"


def test_deny_rule_overrides_permits(engine, sot) -> None:
    sot.directory.subject("dung").roles.append("admin")
    sot.directory.subject("dung").clearance = 3
    result = engine.simulate("0xd4e5f607", "door-2", at=local("2026-11-10T10:00"))
    assert result.code == "D-INTERN-SERVER-ROOM"


def test_full_request_permits_with_correct_pin(engine) -> None:
    result = engine.decide(request(), Evidence(), now=local("2026-11-10T09:00"))
    assert result.effect is Effect.PERMIT
    assert [s.name for s in result.stages] == [
        "validate", "identify", "authenticate", "authorize", "risk"]


@pytest.mark.parametrize(("kwargs", "code"), [
    ({"pin": "9999"}, "pin_mismatch"),
    ({"pin": None}, "pin_required"),
    ({"uid": "0x01020304"}, "unknown_card"),
    ({"door": "door-9"}, "unknown_door"),
])
def test_pipeline_denials(engine, kwargs, code) -> None:
    result = engine.decide(request(**kwargs), Evidence(), now=local("2026-11-10T09:00"))
    assert (result.effect, result.code) == (Effect.DENY, code)


def test_replayed_and_stale_requests(engine) -> None:
    now = local("2026-11-10T09:00")
    assert engine.decide(request(), Evidence(), now=now, txn_seen=True).code == "replayed_txn"
    stale = request(epoch=int(now.timestamp()) - 3600)
    assert engine.decide(stale, Evidence(), now=now).code == "stale_request"
    assert engine.decide(request(), Evidence(), now=now,
                         pep_authenticated=False).code == "pep_unauthorized"


def test_lockdown_is_a_hard_deny(engine, sot) -> None:
    sot.inventory.doors["door-1"].lockdown = True
    result = engine.decide(request(), Evidence(), now=local("2026-11-10T09:00"))
    assert (result.effect, result.code) == (Effect.DENY, "door_lockdown")


def test_denial_velocity_is_a_hard_deny(engine) -> None:
    now = local("2026-11-10T09:00")
    epoch = int(now.timestamp())
    recent = [{"uid": "0xa1b2c3d4", "effect": "deny", "epoch": epoch - 60, "code": "pin_mismatch"}
              for _ in range(3)]
    result = engine.decide(request(), Evidence(recent_decisions=recent), now=now)
    assert result.code == "denial_velocity"


def test_unattested_motion_is_a_warning_for_the_agents(engine) -> None:
    now = local("2026-11-10T09:00")
    epoch = int(now.timestamp())
    evidence = Evidence(
        gateway_status={"clockSet": True, "signedDecisions": True},
        gateway_events=[],
        camera_status={"clockSet": True},
        camera_events=[{"id": 7, "epoch": epoch - 120, "verdict": "classified"}],
    )
    result = engine.decide(request(), evidence, now=now)
    assert result.effect is Effect.PERMIT
    assert [s.code for s in result.risk if s.severity == "warn"] == ["unattested_motion"]
    assert result.stages[-1].code == "elevated"
