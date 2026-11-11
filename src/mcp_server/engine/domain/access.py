"""Access requests from the gateway, and the decision record the PDP produces for them."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.mcp_server.engine.domain.identity import normalise_uid

# The gateway reads `reason` into a 24-byte buffer with a naive scanner that stops at
# a comma, quote or brace, so the code it is sent must be short and plain.
_REASON_UNSAFE = re.compile(r"[^A-Za-z0-9_.:-]")
REASON_MAX = 23


def gateway_reason(code: str) -> str:
    return _REASON_UNSAFE.sub("_", code)[:REASON_MAX] or "none"


class Effect(StrEnum):
    PERMIT = "permit"
    DENY = "deny"


class AccessRequest(BaseModel):
    """The AccessRequest the gateway firmware POSTs to its ``pdpUrl``."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    txn: str = Field(pattern=r"^[0-9a-f]{16}$")
    door: str = Field(min_length=1, max_length=23)
    uid: str = Field(min_length=4, max_length=14)
    pin_digest: str = Field("", alias="pinDigest", pattern=r"^([0-9a-f]{64})?$")
    pin_salt: str = Field("txn", alias="pinSalt")
    uptime: int = 0
    epoch: int = 0
    rssi: int = 0
    node: str = ""

    @property
    def card_uid(self) -> str:
        return normalise_uid(self.uid)


StageName = Literal["validate", "identify", "authenticate", "authorize", "risk", "agent_review"]


class Stage(BaseModel):
    """One step of the decision pipeline, in the order it ran."""

    name: StageName
    passed: bool
    code: str
    detail: str = ""


class RuleMatch(BaseModel):
    rule_id: str
    effect: Effect
    description: str = ""


class RuleFailure(BaseModel):
    """Why a permit rule that targeted the door did not apply."""

    rule_id: str
    code: str
    detail: str


class Authorization(BaseModel):
    effect: Effect
    code: str
    matched: list[RuleMatch] = Field(default_factory=list)
    near_misses: list[RuleFailure] = Field(default_factory=list)


Severity = Literal["info", "warn", "critical"]


class RiskSignal(BaseModel):
    code: str
    severity: Severity
    detail: str
    data: dict[str, Any] = Field(default_factory=dict)


class AgentVerdict(BaseModel):
    """Structured output of the access-judge agent."""

    effect: Effect
    confidence: float = Field(ge=0.0, le=1.0)
    code: str = Field(description="Short snake_case reason, e.g. 'tailgate_risk' or 'consistent'.")
    reasons: list[str] = Field(default_factory=list)
    cited_policies: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    """Full, auditable record of one access decision."""

    decision_id: str
    txn: str
    door: str
    uid: str
    subject_id: str | None = None
    effect: Effect
    code: str
    stages: list[Stage]
    matched_rules: list[str] = Field(default_factory=list)
    risk: list[RiskSignal] = Field(default_factory=list)
    agent: AgentVerdict | None = None
    decided_at: datetime
    latency_ms: int = 0

    @property
    def reason(self) -> str:
        return gateway_reason(self.code)
