"""Computes the cached authorisation set a gateway may use while the PDP is unreachable.

The gateway's cache knows a card, a PIN digest and a time-to-live, nothing more: no
schedule, no deny rule, no risk. So an entry is only issued to a subject who is
permitted *now* by a rule marked ``offline_cache``, who no deny rule applies to, and
only for as long as that permission would keep holding by itself.
"""

from __future__ import annotations

from datetime import datetime, time

from pydantic import BaseModel, Field

from src.mcp_server.engine.conditions import EvalContext
from src.mcp_server.engine.domain.access import Effect
from src.mcp_server.engine.rules import authorize
from src.mcp_server.engine.security import acl_pin_digest
from src.mcp_server.engine.source_of_truth import SourceOfTruth

ACL_CAPACITY = 16  # ACL_ENTRIES in gateway-esp32/app_config.h
MIN_TTL_S = 60


class AclEntry(BaseModel):
    uid: str
    subject: str
    rule: str
    ttl: int
    pin_digest: str = Field(repr=False, exclude=True)

    def device_payload(self) -> dict[str, str]:
        return {"uid": self.uid, "pin": self.pin_digest, "ttl": str(self.ttl)}


class AclPlan(BaseModel):
    door: str
    computed_at: datetime
    entries: list[AclEntry]
    excluded: list[dict[str, str]]


def _seconds_until_end_of(day_end: datetime, at: datetime) -> int:
    return int((day_end - at).total_seconds())


def compute_offline_acl(sot: SourceOfTruth, door_id: str, at: datetime | None = None) -> AclPlan:
    inventory, directory, policies = sot.inventory, sot.directory, sot.policies
    local = sot.local_time(at)
    door = inventory.doors[door_id]
    zone = inventory.zones[door.zone]
    end_of_day = datetime.combine(local.date(), time(23, 59, 59), tzinfo=local.tzinfo)

    entries: list[AclEntry] = []
    excluded: list[dict[str, str]] = []
    for cred in directory.credentials:
        subject = directory.subject(cred.subject)

        def skip(reason: str, uid: str = cred.uid, sid: str = cred.subject) -> None:
            excluded.append({"uid": uid, "subject": sid, "reason": reason})

        if subject is None or subject.status != "active" or cred.status != "active":
            skip("inactive")
            continue
        if not cred.pin:
            skip("no_pin")  # a card-only cache entry would make offline mode one-factor
            continue
        if (cred.expires and cred.expires < local.date()) or (
            subject.valid_until and subject.valid_until < local.date()
        ):
            skip("expired")
            continue

        ctx = EvalContext(subject=subject, door_id=door_id, door=door, zone_id=door.zone,
                          zone=zone, at=local, schedules=policies.schedules)
        auth = authorize(policies, ctx)
        if auth.effect is not Effect.PERMIT:
            if not auth.near_misses or auth.matched:
                skip(auth.code)
            continue
        offline_rules = [policies.rule(m.rule_id) for m in auth.matched]
        offline_rules = [r for r in offline_rules if r and r.offline_cache]
        if not offline_rules:
            skip("rule_not_offline")
            continue

        # The longest any matching offline rule keeps holding without re-evaluation.
        horizon = 0
        for rule in offline_rules:
            if rule.condition.schedule:
                horizon = max(horizon,
                              policies.schedules[rule.condition.schedule].seconds_remaining(local))
            else:
                horizon = policies.defaults.offline_cache_ttl_s
        ttl = min(policies.defaults.offline_cache_ttl_s, horizon)
        for limit in (cred.expires, subject.valid_until):
            if limit and limit == local.date():
                ttl = min(ttl, _seconds_until_end_of(end_of_day, local))
        if ttl < MIN_TTL_S:
            skip("window_closing")
            continue
        entries.append(AclEntry(uid=cred.uid, subject=subject.id, rule=offline_rules[0].id,
                                ttl=ttl, pin_digest=acl_pin_digest(cred.uid, cred.pin)))

    entries.sort(key=lambda e: (e.subject, e.uid))
    return AclPlan(door=door_id, computed_at=local, entries=entries, excluded=excluded)
