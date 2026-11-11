"""The PDP end to end, with a fake agent reviewer, and the HTTP API the gateway calls."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.llm.decision import DecisionService
from src.mcp_server.engine.domain.access import AgentVerdict
from src.mcp_server.engine.security import pin_digest, verify_decision
from tests.conftest import DECISION_KEY

TXN = "a0a1a2a3a4a5a6a7"


class FakeReviewer:
    def __init__(self, verdict: AgentVerdict | None = None, error: Exception | None = None):
        self.verdict, self.error, self.inputs = verdict, error, None

    def review(self, inputs: dict[str, Any]) -> AgentVerdict:
        self.inputs = inputs
        if self.error:
            raise self.error
        return self.verdict


def body(uid: str = "0xa1b2c3d4", pin: str = "1234", txn: str = TXN) -> dict[str, Any]:
    return {"txn": txn, "door": "door-1", "uid": uid, "pinDigest": pin_digest(txn, pin),
            "pinSalt": "txn", "uptime": 10, "epoch": 0, "rssi": -60, "node": "gateway-esp32"}


@pytest.fixture
def business_hours(monkeypatch, runtime):
    from tests.conftest import local

    fixed = local("2026-11-10T09:00")
    monkeypatch.setattr(runtime.sot, "local_time",
                        lambda at=None: fixed if at is None else at)
    return fixed


async def test_signed_permit_after_agent_confirms(runtime, business_hours) -> None:
    reviewer = FakeReviewer(AgentVerdict(effect="permit", confidence=0.95, code="consistent",
                                         cited_policies=["G-TAILGATE"]))
    service = DecisionService(runtime, reviewer)
    reply = await service.decide_raw(body(), bearer="pdp-secret")
    assert reply["effect"] == "permit" and reply["reason"] == "R-STAFF-DEPT"
    assert verify_decision(DECISION_KEY, TXN, "permit", reply["sig"])
    assert "G-TAILGATE" in reviewer.inputs["guidance"]
    assert list(reply)[:2] == ["txn", "effect"]


async def test_agent_can_turn_a_permit_into_a_deny(runtime, business_hours) -> None:
    reviewer = FakeReviewer(AgentVerdict(effect="deny", confidence=0.8, code="tailgate_risk"))
    reply = await DecisionService(runtime, reviewer).decide_raw(body(), bearer="pdp-secret")
    assert (reply["effect"], reply["reason"]) == ("deny", "tailgate_risk")
    record = runtime.decisions.get(reply["decision_id"])
    assert record["stages"][-1]["name"] == "agent_review"


async def test_agent_failure_fails_secure(runtime, business_hours) -> None:
    reviewer = FakeReviewer(error=RuntimeError("model down"))
    reply = await DecisionService(runtime, reviewer).decide_raw(body(), bearer="pdp-secret")
    assert (reply["effect"], reply["reason"]) == ("deny", "agent_unavailable")


async def test_agents_never_see_engine_denials(runtime, business_hours) -> None:
    reviewer = FakeReviewer(AgentVerdict(effect="permit", confidence=1, code="consistent"))
    reply = await DecisionService(runtime, reviewer).decide_raw(body(pin="0000"),
                                                                bearer="pdp-secret")
    assert (reply["effect"], reply["reason"]) == ("deny", "pin_mismatch")
    assert reviewer.inputs is None


async def test_wrong_bearer_and_replay_are_signed_denials(runtime, business_hours) -> None:
    service = DecisionService(runtime, FakeReviewer(
        AgentVerdict(effect="permit", confidence=1, code="consistent")))
    reply = await service.decide_raw(body(), bearer="wrong")
    assert reply["reason"] == "pep_unauthorized"
    assert verify_decision(DECISION_KEY, TXN, "deny", reply["sig"])
    replay = await service.decide_raw(body(), bearer="pdp-secret")
    assert replay["reason"] == "replayed_txn"


async def test_malformed_request_still_gets_a_deny(runtime) -> None:
    reply = await DecisionService(runtime).decide_raw({"txn": "nothex", "door": "door-1"}, None)
    assert (reply["effect"], reply["reason"]) == ("deny", "bad_request")


async def test_decision_log_chain_detects_tampering(runtime, business_hours) -> None:
    service = DecisionService(runtime, FakeReviewer(
        AgentVerdict(effect="permit", confidence=1, code="consistent")))
    for i in range(3):
        await service.decide_raw(body(txn=f"{i:016x}"), bearer="pdp-secret")
    assert runtime.decisions.verify() == {**runtime.decisions.verify(), "ok": True, "records": 3}
    path = runtime.decisions.path
    lines = path.read_text().splitlines()
    lines[1] = lines[1].replace('"effect":"permit"', '"effect":"deny"', 1)
    path.write_text("\n".join(lines) + "\n")
    report = runtime.decisions.verify()
    assert report["ok"] is False and report["broken_at_line"] == 2


def test_http_endpoint_with_agents_off(runtime, monkeypatch) -> None:
    monkeypatch.setattr(runtime.settings, "agent_review", "off")
    from src.main import app

    with TestClient(app) as client:
        assert client.get("/health").json()["agent_review"] == "off"
        reply = client.post("/pdp/decide", json=body(uid="0xe5f60718", pin="1111"),
                            headers={"Authorization": "Bearer pdp-secret"}).json()
        assert (reply["effect"], reply["reason"]) == ("deny", "subject_inactive")
        assert client.get(f"/pdp/decisions/{reply['decision_id']}").status_code == 200
        assert client.get("/pdp/integrity").json()["ok"] is True
