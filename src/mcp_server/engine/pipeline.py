"""The deterministic part of the access decision, as a short-circuiting stage pipeline.

    validate -> identify -> authenticate -> authorize -> risk

Each stage either passes or denies; the first denial ends the pipeline. A request
that clears every stage is a *preliminary* permit, which the agent review can
still turn into a deny, and never the other way round.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from src.mcp_server.engine.conditions import EvalContext
from src.mcp_server.engine.domain.access import (
    AccessRequest,
    Authorization,
    Effect,
    RiskSignal,
    Stage,
)
from src.mcp_server.engine.domain.identity import Credential, Subject, normalise_uid
from src.mcp_server.engine.risk import CLOCK_SET_AFTER, Evidence, assess_risk
from src.mcp_server.engine.rules import authorize
from src.mcp_server.engine.security import constant_time_equals, pin_digest
from src.mcp_server.engine.source_of_truth import SourceOfTruth


@dataclass
class Preliminary:
    """Outcome of the deterministic stages, with everything the agents need to review it."""

    effect: Effect
    code: str
    door_id: str
    uid: str
    at: datetime
    stages: list[Stage] = field(default_factory=list)
    subject: Subject | None = None
    credential: Credential | None = None
    authorization: Authorization | None = None
    risk: list[RiskSignal] = field(default_factory=list)

    def deny(self, stage: Stage) -> Preliminary:
        self.stages.append(stage)
        self.effect, self.code = Effect.DENY, stage.code
        return self

    def pass_(self, stage: Stage) -> None:
        self.stages.append(stage)


class DecisionEngine:
    def __init__(self, sot: SourceOfTruth) -> None:
        self.sot = sot

    def decide(
        self,
        request: AccessRequest,
        evidence: Evidence,
        *,
        now: datetime | None = None,
        txn_seen: bool = False,
        pep_authenticated: bool = True,
    ) -> Preliminary:
        """Run every stage for a request the gateway actually sent."""
        at = self.sot.local_time(now)
        result = Preliminary(effect=Effect.DENY, code="pending", door_id=request.door,
                             uid=request.card_uid, at=at)

        if not pep_authenticated:
            return result.deny(Stage(name="validate", passed=False, code="pep_unauthorized",
                                     detail="bearer token does not match the door's gateway"))
        if not self._validate(request, result, at, txn_seen=txn_seen):
            return result
        return self._evaluate(result, evidence, pin=("digest", request.pin_digest, request.txn))

    def simulate(
        self,
        uid: str,
        door_id: str,
        *,
        at: datetime | None = None,
        evidence: Evidence | None = None,
    ) -> Preliminary:
        """Evaluate as if the right PIN had been entered. Used by the simulator and verifier."""
        local = self.sot.local_time(at)
        result = Preliminary(effect=Effect.DENY, code="pending", door_id=door_id,
                             uid=normalise_uid(uid), at=local)
        if door_id not in self.sot.inventory.doors:
            return result.deny(Stage(name="validate", passed=False, code="unknown_door",
                                     detail=f"{door_id!r} is not in the inventory"))
        result.pass_(Stage(name="validate", passed=True, code="simulated"))
        return self._evaluate(result, evidence or Evidence(), pin=("assume",))

    # ---------------------------------------------------------------- stages ---

    def _validate(self, request: AccessRequest, result: Preliminary, at: datetime,
                  *, txn_seen: bool) -> bool:
        inventory = self.sot.inventory
        if request.door not in inventory.doors:
            result.deny(Stage(name="validate", passed=False, code="unknown_door",
                              detail=f"{request.door!r} is not in the inventory"))
            return False
        if txn_seen:
            result.deny(Stage(name="validate", passed=False, code="replayed_txn",
                              detail=f"transaction {request.txn} was already decided"))
            return False
        skew_limit = self.sot.policies.risk.max_clock_skew_s
        if request.epoch > CLOCK_SET_AFTER:
            skew = abs(int(at.timestamp()) - request.epoch)
            if skew > skew_limit:
                result.deny(Stage(name="validate", passed=False, code="stale_request",
                                  detail=f"request clock differs by {skew}s (> {skew_limit}s)"))
                return False
        result.pass_(Stage(name="validate", passed=True, code="ok",
                           detail="known door, fresh transaction"))
        return True

    def _evaluate(self, result: Preliminary, evidence: Evidence, *, pin: tuple) -> Preliminary:
        inventory, directory, policies = self.sot.inventory, self.sot.directory, self.sot.policies
        door = inventory.doors[result.door_id]
        today: date = result.at.date()

        # identify -------------------------------------------------------------
        credential = directory.credential(result.uid)
        if credential is None:
            return result.deny(Stage(name="identify", passed=False, code="unknown_card",
                                     detail=f"no credential with uid {result.uid}"))
        result.credential = credential
        if credential.status != "active":
            return result.deny(Stage(name="identify", passed=False,
                                     code=f"card_{credential.status}",
                                     detail=f"credential is {credential.status}"))
        if credential.expires and credential.expires < today:
            return result.deny(Stage(name="identify", passed=False, code="card_expired",
                                     detail=f"credential expired on {credential.expires}"))
        subject = directory.subject(credential.subject)
        if subject is None or subject.status != "active":
            status = subject.status if subject else "missing"
            return result.deny(Stage(name="identify", passed=False, code="subject_inactive",
                                     detail=f"subject {credential.subject} is {status}"))
        if subject.valid_until and subject.valid_until < today:
            return result.deny(Stage(name="identify", passed=False, code="subject_expired",
                                     detail=f"subject validity ended on {subject.valid_until}"))
        result.subject = subject
        result.pass_(Stage(name="identify", passed=True, code="ok",
                           detail=f"{subject.id} ({', '.join(subject.roles)})"))

        # authenticate ---------------------------------------------------------
        require_pin = (policies.defaults.require_pin if door.require_pin is None
                       else door.require_pin)
        if pin[0] == "assume":
            result.pass_(Stage(name="authenticate", passed=True, code="assumed",
                               detail="simulation: PIN taken as correct"))
        else:
            _, digest, txn = pin
            if not digest:
                if require_pin:
                    return result.deny(Stage(name="authenticate", passed=False,
                                             code="pin_required",
                                             detail="door requires a PIN and none was sent"))
                result.pass_(Stage(name="authenticate", passed=True, code="card_only",
                                   detail="door does not require a PIN"))
            elif not credential.pin:
                return result.deny(Stage(name="authenticate", passed=False,
                                         code="no_pin_enrolled",
                                         detail="credential has no PIN on file"))
            elif not constant_time_equals(pin_digest(txn, credential.pin), digest):
                return result.deny(Stage(name="authenticate", passed=False, code="pin_mismatch",
                                         detail="PIN digest does not match"))
            else:
                result.pass_(Stage(name="authenticate", passed=True, code="ok",
                                   detail="PIN verified against the transaction nonce"))

        # authorize ------------------------------------------------------------
        ctx = EvalContext(subject=subject, door_id=result.door_id, door=door, zone_id=door.zone,
                          zone=inventory.zones[door.zone], at=result.at,
                          schedules=policies.schedules)
        authorization = authorize(policies, ctx)
        result.authorization = authorization
        if authorization.effect is Effect.DENY:
            detail = (
                f"deny rule {authorization.code} applies" if authorization.matched
                else "; ".join(f"{m.rule_id}: {m.detail}" for m in authorization.near_misses)
                or "no rule targets this door"
            )
            return result.deny(Stage(name="authorize", passed=False, code=authorization.code,
                                     detail=detail))
        result.pass_(Stage(name="authorize", passed=True, code=authorization.code,
                           detail="permitted by " + ", ".join(m.rule_id
                                                              for m in authorization.matched)))

        # risk -----------------------------------------------------------------
        result.risk = assess_risk(door_id=result.door_id, door=door, uid=result.uid,
                                  evidence=evidence, policy=policies.risk,
                                  now_epoch=int(result.at.timestamp()))
        critical = [s for s in result.risk if s.severity == "critical"]
        if critical:
            return result.deny(Stage(name="risk", passed=False, code=critical[0].code,
                                     detail=critical[0].detail))
        warnings = [s.code for s in result.risk if s.severity == "warn"]
        result.pass_(Stage(name="risk", passed=True, code="elevated" if warnings else "ok",
                           detail=", ".join(warnings) or "no warning signals"))

        result.effect, result.code = Effect.PERMIT, authorization.code
        return result
