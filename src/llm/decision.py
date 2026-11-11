"""The Policy Decision Point: one access request in, one signed decision out.

    authenticate PEP -> engine stages (local evidence) -> device evidence -> engine again
      -> agent review (time-boxed) -> combine -> sign -> decision log

Two properties hold whatever happens inside:

* **Fail secure.** Any error answers a signed *deny* with HTTP 200. A non-200 would
  push the gateway into its degraded path, where the offline cache decides instead.
* **Agents only tighten.** The review runs only on a request the engine permitted, and
  :func:`combine_review` lets it turn that permit into a deny, never the reverse.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from datetime import datetime
from typing import Any, Protocol

from pydantic import ValidationError

from src.mcp_server.devices import DeviceError
from src.mcp_server.engine.combine import combine_review
from src.mcp_server.engine.domain.access import (
    AccessRequest,
    AgentVerdict,
    Decision,
    Effect,
    gateway_reason,
)
from src.mcp_server.engine.pipeline import Preliminary
from src.mcp_server.engine.risk import Evidence
from src.mcp_server.engine.security import constant_time_equals, sign_decision
from src.mcp_server.runtime import Runtime

log = logging.getLogger(__name__)


class Reviewer(Protocol):
    def review(self, inputs: dict[str, Any]) -> AgentVerdict: ...


class DecisionService:
    def __init__(self, runtime: Runtime, reviewer: Reviewer | None = None, *,
                 collect_device_evidence: bool = True) -> None:
        self.runtime = runtime
        self.reviewer = reviewer
        self.collect_device_evidence = collect_device_evidence

    # ------------------------------------------------------------------ API ---

    async def decide_raw(self, body: dict[str, Any], bearer: str | None) -> dict[str, Any]:
        """Entry point for the gateway: never raises, always answers a gateway document."""
        try:
            request = AccessRequest.model_validate(body)
        except ValidationError as exc:
            log.warning("malformed access request: %s", exc.errors()[:2])
            return self._response(str(body.get("txn", "")), str(body.get("door", "")),
                                  Effect.DENY, "bad_request", decision_id=None)
        try:
            decision = await self.decide(request, bearer=bearer)
        except Exception:  # noqa: BLE001 - the gateway must get an answer
            log.exception("decision failed for txn %s", request.txn)
            return self._response(request.txn, request.door, Effect.DENY, "pdp_error",
                                  decision_id=None)
        return self._response(decision.txn, decision.door, decision.effect, decision.reason,
                              decision_id=decision.decision_id)

    async def decide(self, request: AccessRequest, *, bearer: str | None = None,
                     now: datetime | None = None) -> Decision:
        started = time.monotonic()
        runtime = self.runtime
        engine = runtime.engine
        settings = runtime.settings

        recent = runtime.decisions.recent(limit=50, uid=request.card_uid)
        evidence = Evidence(recent_decisions=recent)
        kwargs = {"now": now, "txn_seen": runtime.decisions.seen_txn(request.txn),
                  "pep_authenticated": self._pep_authenticated(request.door, bearer)}

        # Cheap pass first: most denials need no device round trip at all.
        prelim = engine.decide(request, evidence, **kwargs)
        if prelim.effect is Effect.PERMIT and self.collect_device_evidence:
            evidence = await self._device_evidence(request.door, recent)
            prelim = engine.decide(request, evidence, **kwargs)

        verdict, error = None, None
        if self._should_review(prelim):
            remaining = settings.decision_budget_s - (time.monotonic() - started)
            verdict, error = await self._review(prelim, evidence, remaining)

        combined = combine_review(prelim.effect, prelim.code, verdict=verdict, error=error,
                                  failure_mode=settings.agent_failure_mode,
                                  min_confidence=settings.agent_min_confidence)
        stages = prelim.stages + ([combined.stage] if combined.stage else [])
        decision = Decision(
            decision_id=f"dec-{secrets.token_hex(6)}", txn=request.txn, door=request.door,
            uid=request.card_uid, subject_id=prelim.subject.id if prelim.subject else None,
            effect=combined.effect, code=combined.code, stages=stages,
            matched_rules=[m.rule_id for m in (prelim.authorization.matched
                                               if prelim.authorization else [])],
            risk=prelim.risk, agent=verdict, decided_at=prelim.at,
            latency_ms=int((time.monotonic() - started) * 1000))
        runtime.decisions.append(decision)
        log.info("%s %s door=%s uid=%s code=%s %dms", decision.decision_id,
                 decision.effect.value, decision.door, decision.uid, decision.code,
                 decision.latency_ms)
        return decision

    # ------------------------------------------------------------ internals ---

    def _pep_authenticated(self, door_id: str, bearer: str | None) -> bool:
        door = self.runtime.sot.inventory.doors.get(door_id)
        if door is None:
            return True  # the validate stage reports the unknown door
        expected = self.runtime.sot.inventory.nodes[door.gateway].secret("pdp_token")
        if not expected:
            return True  # bench: no token configured for this gateway
        return bool(bearer) and constant_time_equals(bearer, expected)

    def _should_review(self, prelim: Preliminary) -> bool:
        mode = self.runtime.settings.agent_review
        if mode == "off" or prelim.subject is None:
            return False
        return mode == "always" or prelim.effect is Effect.PERMIT

    async def _device_evidence(self, door_id: str, recent: list[dict[str, Any]]) -> Evidence:
        runtime = self.runtime
        timeout = min(runtime.settings.device_timeout_s, runtime.settings.decision_budget_s / 4)
        gateway = runtime.fleet.gateway_for_door(door_id)
        camera = runtime.fleet.camera_for_door(door_id)
        errors: list[str] = []

        async def fetch(name: str, coro: Any) -> Any:
            try:
                return await asyncio.wait_for(coro, timeout)
            except (DeviceError, TimeoutError) as exc:
                errors.append(f"{name}: {exc or 'timeout'}")
                return None

        calls = [fetch("gateway status", gateway.status()),
                 fetch("gateway events", gateway.events())]
        if camera:
            calls += [fetch("camera status", camera.status()),
                      fetch("camera events", camera.events())]
        results = await asyncio.gather(*calls)
        gw_status, gw_events = results[0], results[1]
        cam_status, cam_events = (results[2], results[3]) if camera else (None, None)
        return Evidence(gateway_status=gw_status, gateway_events=gw_events,
                        camera_status=cam_status, camera_events=cam_events,
                        recent_decisions=recent, errors=errors)

    async def _review(self, prelim: Preliminary, evidence: Evidence,
                      remaining_s: float) -> tuple[AgentVerdict | None, str | None]:
        if self.reviewer is None:
            return None, "no reviewer available"
        if remaining_s < 2:
            return None, "decision budget exhausted before review"
        try:
            verdict = await asyncio.wait_for(
                asyncio.to_thread(self.reviewer.review, self._review_inputs(prelim, evidence)),
                remaining_s)
            return verdict, None
        except TimeoutError:
            return None, f"review exceeded {remaining_s:.1f}s"
        except Exception as exc:  # noqa: BLE001 - any reviewer failure is handled by policy
            log.exception("agent review failed")
            return None, type(exc).__name__

    def _review_inputs(self, prelim: Preliminary, evidence: Evidence) -> dict[str, Any]:
        policies = self.runtime.sot.policies
        subject = prelim.subject
        return {
            "door": prelim.door_id,
            "uid": prelim.uid,
            "at": prelim.at.isoformat(timespec="minutes"),
            "subject": subject.id if subject else "unknown",
            "subject_detail": subject.public_view() if subject else {},
            "stages": "\n".join(f"- {s.name}: {'pass' if s.passed else 'DENY'} {s.code} "
                                f"({s.detail})" for s in prelim.stages),
            "risk": "\n".join(f"- [{s.severity}] {s.code}: {s.detail}" for s in prelim.risk)
                    or "- none",
            "evidence_gaps": "; ".join(evidence.errors) or "none",
            "matched_rules": [m.model_dump() for m in (prelim.authorization.matched
                                                       if prelim.authorization else [])],
            "guidance": "\n".join(f"- {g.id}: {g.text}" for g in policies.guidance),
        }

    def _response(self, txn: str, door_id: str, effect: Effect, reason: str,
                  *, decision_id: str | None) -> dict[str, Any]:
        """The decision document the firmware parses: flat fields, txn and effect first."""
        body: dict[str, Any] = {"txn": txn, "effect": effect.value,
                                "reason": gateway_reason(reason)}
        door = self.runtime.sot.inventory.doors.get(door_id)
        key = self.runtime.sot.inventory.nodes[door.gateway].secret("decision_key") if door else ""
        if key and txn:
            body["sig"] = sign_decision(key, txn, effect.value)
        if decision_id:
            body["decision_id"] = decision_id
        return body
