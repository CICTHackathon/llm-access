"""Evaluation of a rule's condition against one subject, at one door, at one time."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.mcp_server.engine.domain.identity import Subject
from src.mcp_server.engine.domain.inventory import Door, Zone
from src.mcp_server.engine.domain.policy import Condition, Schedule


@dataclass(frozen=True)
class EvalContext:
    subject: Subject
    door_id: str
    door: Door
    zone_id: str
    zone: Zone
    at: datetime
    schedules: dict[str, Schedule] = field(default_factory=dict)


@dataclass(frozen=True)
class Failure:
    code: str
    detail: str


def check_condition(cond: Condition, ctx: EvalContext) -> Failure | None:
    """Return the first clause that does not hold, or ``None`` when all of them do.

    Clauses about *who* the subject is are checked before *when* they arrive, so a
    near miss reports ``outside_schedule`` only for someone who would otherwise
    have been admitted. The access judge relies on that distinction.
    """
    subject, zone = ctx.subject, ctx.zone

    if cond.roles_any and not set(cond.roles_any) & set(subject.roles):
        return Failure("role_not_allowed", f"needs one of roles {cond.roles_any}")

    if cond.departments_any and subject.department not in cond.departments_any:
        return Failure("department_not_allowed", f"needs department in {cond.departments_any}")

    if cond.same_department_as_zone and (
        zone.department is None or subject.department != zone.department
    ):
        return Failure(
            "department_mismatch",
            f"zone {ctx.zone_id} belongs to {zone.department!r}, subject to "
            f"{subject.department!r}",
        )

    if cond.clearance_at_least_zone and subject.clearance < zone.level:
        return Failure(
            "insufficient_clearance",
            f"clearance {subject.clearance} below zone level {zone.level}",
        )

    if cond.min_clearance is not None and subject.clearance < cond.min_clearance:
        return Failure(
            "insufficient_clearance",
            f"clearance {subject.clearance} below required {cond.min_clearance}",
        )

    for key, expected in cond.subject_attributes.items():
        if subject.attributes.get(key) != expected:
            return Failure("attribute_mismatch", f"attribute {key!r} must be {expected!r}")

    if cond.schedule:
        schedule = ctx.schedules.get(cond.schedule)
        if schedule is None:
            return Failure("unknown_schedule", f"schedule {cond.schedule!r} is not defined")
        if not schedule.contains(ctx.at):
            return Failure(
                "outside_schedule",
                f"{ctx.at:%a %H:%M} is outside {cond.schedule} "
                f"({','.join(schedule.days)} {schedule.start:%H:%M}-{schedule.end:%H:%M})",
            )

    return None
