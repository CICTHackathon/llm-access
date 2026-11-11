"""ABAC policy model: schedules, rules (target + condition + effect) and NL guidance."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAYS: tuple[Weekday, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Schedule(_Model):
    """A weekly window. ``start > end`` means the window crosses midnight."""

    days: list[Weekday]
    start: time
    end: time

    def _opens_on(self, day: datetime) -> bool:
        return WEEKDAYS[day.weekday()] in self.days

    def contains(self, at: datetime) -> bool:
        now = at.time()
        if self.start <= self.end:
            return self._opens_on(at) and self.start <= now < self.end
        # Overnight: the evening part belongs to today, the morning part to yesterday.
        if now >= self.start:
            return self._opens_on(at)
        if now < self.end:
            return self._opens_on(at - timedelta(days=1))
        return False

    def seconds_remaining(self, at: datetime) -> int:
        """Seconds until the window that contains ``at`` closes (0 if it is closed)."""
        if not self.contains(at):
            return 0
        close = at.replace(hour=self.end.hour, minute=self.end.minute, second=0, microsecond=0)
        if close <= at:
            close += timedelta(days=1)
        return int((close - at).total_seconds())


class Target(_Model):
    any: bool = False
    zones: list[str] = Field(default_factory=list)
    doors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _not_empty(self) -> Target:
        if not (self.any or self.zones or self.doors):
            raise ValueError("target must name zones, doors, or set any: true")
        return self

    def applies_to(self, door_id: str, zone_id: str) -> bool:
        return self.any or door_id in self.doors or zone_id in self.zones


class Condition(_Model):
    """Every field that is set must hold. An empty condition always holds."""

    roles_any: list[str] = Field(default_factory=list)
    departments_any: list[str] = Field(default_factory=list)
    same_department_as_zone: bool = False
    min_clearance: int | None = Field(default=None, ge=0)
    clearance_at_least_zone: bool = False
    schedule: str | None = None
    subject_attributes: dict[str, Any] = Field(default_factory=dict)

    def is_empty(self) -> bool:
        return self == Condition()


class Rule(_Model):
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,23}$")
    description: str = ""
    effect: Literal["permit", "deny"]
    target: Target
    condition: Condition = Field(default_factory=Condition)
    offline_cache: bool = False

    @model_validator(mode="after")
    def _offline_only_for_permits(self) -> Rule:
        if self.offline_cache and self.effect != "permit":
            raise ValueError(f"rule {self.id}: offline_cache only applies to permit rules")
        return self


class Guidance(_Model):
    id: str
    text: str


class RiskPolicy(_Model):
    max_recent_denials: int = Field(3, ge=1)
    recent_denials_window_s: int = Field(600, gt=0)
    anomaly_window_s: int = Field(900, gt=0)
    correlation_window_s: int = Field(15, ge=1, le=120)
    max_clock_skew_s: int = Field(120, gt=0)


class PolicyDefaults(_Model):
    require_pin: bool = True
    offline_cache_ttl_s: int = Field(3600, gt=0)


class PolicySet(_Model):
    version: int = 1
    defaults: PolicyDefaults = Field(default_factory=PolicyDefaults)
    risk: RiskPolicy = Field(default_factory=RiskPolicy)
    schedules: dict[str, Schedule] = Field(default_factory=dict)
    rules: list[Rule] = Field(default_factory=list)
    guidance: list[Guidance] = Field(default_factory=list)

    @field_validator("rules")
    @classmethod
    def _unique_ids(cls, rules: list[Rule]) -> list[Rule]:
        ids = [r.id for r in rules]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate rule id")
        return rules

    @model_validator(mode="after")
    def _known_schedules(self) -> PolicySet:
        for rule in self.rules:
            name = rule.condition.schedule
            if name and name not in self.schedules:
                raise ValueError(f"rule {rule.id}: unknown schedule {name!r}")
        return self

    def rule(self, rule_id: str) -> Rule | None:
        return next((r for r in self.rules if r.id == rule_id), None)
