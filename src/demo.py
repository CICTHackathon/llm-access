"""Demo seed: two weeks of access decisions, decided by the real pipeline at past times.

Each request is built as the gateway would send it (card UID, nonce-salted PIN digest,
PEP bearer token) and goes through every deterministic stage, so the records are genuine
engine output on a valid hash chain. Only the agent-review step is replaced by
:class:`DemoReviewer`, which answers without an LLM and says so in its reasons.

Seeding writes only into an empty decision log; it never mixes with real traffic.
"""

from __future__ import annotations

import logging
import random
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.llm.decision import DecisionService
from src.mcp_server.engine.domain.access import AccessRequest, AgentVerdict, Effect
from src.mcp_server.engine.pipeline import Preliminary
from src.mcp_server.engine.security import pin_digest
from src.mcp_server.runtime import Runtime

log = logging.getLogger("llm_access.demo")

SEED = 20261122


@dataclass(frozen=True)
class Attempt:
    uid: str
    door: str
    pin: str


# Who taps where, from config/identities.yaml. Weights are relative frequencies.
_TRAFFIC: list[tuple[int, Attempt]] = [
    (30, Attempt("0xa1b2c3d4", "door-1", "1234")),   # alice, engineering lab
    (8, Attempt("0xb2c3d4e5", "door-1", "4321")),    # bao (admin)
    (8, Attempt("0xb2c3d4e5", "door-2", "4321")),    # bao, server room
    (10, Attempt("0xc3d4e5f6", "door-1", "5678")),   # chi (contractor)
    (5, Attempt("0xa1b2c3d4", "door-2", "1234")),    # alice at the server room
    (5, Attempt("0xd4e5f607", "door-2", "8765")),    # dung (intern) at the server room
    (4, Attempt("0xd4e5f607", "door-1", "8765")),    # dung, engineering lab
    (3, Attempt("0xe5f60718", "door-1", "1111")),    # em (suspended)
    (3, Attempt("0xf6071829", "door-1", "1234")),    # alice's revoked card
    (4, Attempt("0xa1b2c3d4", "door-1", "0000")),    # wrong PIN
    (2, Attempt("0xdeadbeef", "door-1", "1234")),    # unknown card
    (2, Attempt("0x0badcafe", "door-2", "9999")),    # unknown card
]


class DemoReviewer:
    """Stands in for the access-review crew: mostly confirms, sometimes tightens."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def review(self, inputs: dict[str, Any]) -> AgentVerdict:  # noqa: ARG002 - same shape as the crew
        roll = self.rng.random()
        if roll < 0.08:
            return AgentVerdict(
                effect=Effect.DENY, confidence=round(self.rng.uniform(0.78, 0.93), 2),
                code="tailgate_risk",
                reasons=["Demo seed: motion with no matching credential before the request."],
                cited_policies=["G-TAILGATE"])
        if roll < 0.11:
            return AgentVerdict(
                effect=Effect.DENY, confidence=round(self.rng.uniform(0.72, 0.88), 2),
                code="probing_pattern",
                reasons=["Demo seed: several denied attempts on this card earlier in the hour."],
                cited_policies=["G-PROBING"])
        return AgentVerdict(
            effect=Effect.PERMIT, confidence=round(self.rng.uniform(0.82, 0.98), 2),
            code="consistent",
            reasons=["Demo seed: no guidance statement applies; door evidence is consistent."])


class _SeedService(DecisionService):
    """Reviews every permit with a known subject, whatever LLM_ACCESS_AGENT_REVIEW says."""

    def _should_review(self, prelim: Preliminary) -> bool:
        return prelim.subject is not None and prelim.effect is Effect.PERMIT


def _schedule(rng: random.Random, now: datetime, days: int) -> list[datetime]:
    """Request times over the last `days` days in site time: busy weekdays, quiet nights."""
    times: list[datetime] = []
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for back in range(days - 1, -1, -1):
        day = midnight - timedelta(days=back)
        weekend = day.weekday() >= 5
        for _ in range(rng.randint(3, 7) if weekend else rng.randint(14, 24)):
            hour = rng.randint(7, 18) if rng.random() < 0.88 else rng.choice([5, 6, 19, 20, 21, 22])
            at = day + timedelta(hours=hour, seconds=rng.randint(0, 3599))
            if at < now:
                times.append(at)
    return sorted(times)


async def seed_demo_decisions(runtime: Runtime, *, days: int = 14, seed: int = SEED) -> int:
    """Fills an empty decision log; returns how many decisions were written (0 if not empty)."""
    if runtime.decisions.recent(limit=1) or runtime.decisions.verify()["records"]:
        log.info("decision log is not empty; demo seed skipped")
        return 0

    rng = random.Random(seed)
    service = _SeedService(runtime, DemoReviewer(rng), collect_device_evidence=False)
    weights = [w for w, _ in _TRAFFIC]
    attempts = [a for _, a in _TRAFFIC]
    inventory = runtime.sot.inventory

    count = 0
    for at in _schedule(rng, runtime.sot.local_time(), days):
        attempt = rng.choices(attempts, weights)[0]
        door = inventory.doors.get(attempt.door)
        if door is None:
            continue
        txn = secrets.token_hex(8)
        request = AccessRequest(txn=txn, door=attempt.door, uid=attempt.uid,
                                pinDigest=pin_digest(txn, attempt.pin), node=door.gateway)
        bearer = inventory.nodes[door.gateway].secret("pdp_token") or None
        await service.decide(request, bearer=bearer, now=at)
        count += 1
    log.info("seeded %d demo decisions over %d days", count, days)
    return count
