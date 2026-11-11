"""Pre-deployment validation of device configuration and policy changes.

The firmware silently clamps out-of-range values; the verifier refuses them instead,
so a verified plan states exactly what the device will end up running. On top of the
device's own limits it enforces the site's security invariants.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from src.mcp_server.engine.domain.inventory import Inventory
from src.mcp_server.engine.domain.policy import PolicySet

Severity = Literal["error", "warning"]


class Issue(BaseModel):
    severity: Severity
    code: str
    message: str


class Verification(BaseModel):
    ok: bool
    issues: list[Issue] = Field(default_factory=list)
    normalised: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def of(cls, issues: list[Issue], normalised: dict[str, Any] | None = None) -> Verification:
        return cls(ok=not any(i.severity == "error" for i in issues), issues=issues,
                   normalised=normalised or {})


@dataclass(frozen=True)
class _Field:
    kind: Literal["int", "bool", "str"]
    lo: int = 0
    hi: int = 0
    max_len: int = 0


# gateway-esp32: configApplyOne() / RuntimeConfig in app_config.h
GATEWAY_FIELDS: dict[str, _Field] = {
    "closedAngle": _Field("int", 0, 180),
    "openAngle": _Field("int", 0, 180),
    "openHoldMs": _Field("int", 500, 60000),
    "pinTimeoutMs": _Field("int", 2000, 60000),
    "pdpTimeoutMs": _Field("int", 500, 30000),
    "pinAttempts": _Field("int", 1, 10),
    "requirePin": _Field("bool"),
    "degradedAllow": _Field("bool"),
    "buzzerEnabled": _Field("bool"),
    "doorId": _Field("str", max_len=23),
    "pdpUrl": _Field("str", max_len=95),
}
# Provisioned out of band (`llm-access provision`), never through an agent's plan.
GATEWAY_SECRETS = frozenset({"apiToken", "decisionKey", "pdpToken"})

# esp32cam: configPostHandler() in web.cpp
CAMERA_FIELDS: dict[str, _Field] = {
    "frameSize": _Field("int", 0, 15),
    "jpegQuality": _Field("int", 10, 63),
    "hMirror": _Field("bool"),
    "vFlip": _Field("bool"),
    "cellDelta": _Field("int", 1, 200),
    "motionPercent": _Field("int", 1, 100),
    "sampleIdle": _Field("int", 1, 60),
    "sampleActive": _Field("int", 1, 60),
    "minFrames": _Field("int", 1, 60),
    "clearFrames": _Field("int", 1, 200),
    "classifierPercent": _Field("int", 0, 100),
    "mlProbability": _Field("int", 0, 100),
    "mlUse": _Field("bool"),
    "saveEvents": _Field("bool"),
    "lampOnEvent": _Field("bool"),
    "lampBrightness": _Field("int", 0, 255),
}

_TRUE = {"1", "true", "yes", "on", "t", "y"}
_FALSE = {"0", "false", "no", "off", "f", "n"}


def _coerce(key: str, value: Any, spec: _Field, issues: list[Issue]) -> Any:
    if spec.kind == "bool":
        text = str(value).strip().lower()
        if isinstance(value, bool):
            return value
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        issues.append(Issue(severity="error", code="not_boolean",
                            message=f"{key}={value!r} is not a boolean"))
        return None
    if spec.kind == "int":
        try:
            number = int(str(value).strip())
        except ValueError:
            issues.append(Issue(severity="error", code="not_integer",
                                message=f"{key}={value!r} is not an integer"))
            return None
        if not spec.lo <= number <= spec.hi:
            issues.append(Issue(severity="error", code="out_of_range",
                                message=f"{key}={number} outside {spec.lo}..{spec.hi}"))
            return None
        return number
    text = str(value)
    if len(text) > spec.max_len:
        issues.append(Issue(severity="error", code="too_long",
                            message=f"{key} longer than {spec.max_len} characters"))
        return None
    return text


def _normalise(changes: dict[str, Any], fields: dict[str, _Field],
               issues: list[Issue]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in changes.items():
        if key in GATEWAY_SECRETS:
            issues.append(Issue(severity="error", code="secret_in_plan",
                                message=f"{key} is a secret; provision it out of band"))
            continue
        spec = fields.get(key)
        if spec is None:
            issues.append(Issue(severity="error", code="unknown_key",
                                message=f"{key!r} is not a setting of this node"))
            continue
        coerced = _coerce(key, value, spec, issues)
        if coerced is not None:
            out[key] = coerced
    if not changes:
        issues.append(Issue(severity="error", code="empty_change", message="nothing to change"))
    return out


def verify_gateway_config(
    node_id: str,
    changes: dict[str, Any],
    *,
    inventory: Inventory,
    policies: PolicySet,
    current: dict[str, Any] | None,
    min_pdp_timeout_ms: int,
) -> Verification:
    issues: list[Issue] = []
    node = inventory.nodes.get(node_id)
    if node is None or node.kind != "gateway":
        return Verification.of([Issue(severity="error", code="unknown_node",
                                      message=f"{node_id!r} is not a gateway")])
    normalised = _normalise(changes, GATEWAY_FIELDS, issues)
    door = inventory.doors[node.door]

    # Judge the record as it will be after the change, as the firmware does.
    merged = {**(current or {}), **normalised}
    if current is None:
        issues.append(Issue(severity="warning", code="current_unknown",
                            message="current config unavailable; cross-field checks partial"))

    if "openAngle" in merged and merged.get("openAngle") == merged.get("closedAngle"):
        issues.append(Issue(severity="error", code="angles_equal",
                            message="openAngle and closedAngle must differ"))

    require_pin = policies.defaults.require_pin if door.require_pin is None else door.require_pin
    if require_pin and normalised.get("requirePin") is False:
        issues.append(Issue(severity="error", code="pin_required_by_policy",
                            message=f"{node.door} requires a PIN; requirePin cannot be false"))

    if "doorId" in normalised and normalised["doorId"] != node.door:
        issues.append(Issue(severity="error", code="door_id_mismatch",
                            message=f"doorId must be {node.door!r} (inventory)"))

    url = normalised.get("pdpUrl")
    if url is not None and url and not url.startswith(("http://", "https://")):
        issues.append(Issue(severity="error", code="bad_url", message="pdpUrl must be http(s)"))

    # A change may not introduce this violation; one already on the device is reported
    # but does not block an unrelated change.
    timeout = merged.get("pdpTimeoutMs")
    if isinstance(timeout, int) and timeout < min_pdp_timeout_ms:
        issues.append(Issue(
            severity="error" if "pdpTimeoutMs" in normalised else "warning",
            code="pdp_timeout_below_budget",
            message=f"pdpTimeoutMs {timeout} is below the PDP decision budget "
                    f"({min_pdp_timeout_ms} ms); requests would fall to the cached set"))

    if normalised.get("openHoldMs", 0) > 15000:
        issues.append(Issue(severity="warning", code="long_hold",
                            message="latch held open longer than 15 s widens the tailgate window"))
    if normalised.get("pinAttempts", 0) > 5:
        issues.append(Issue(severity="warning", code="many_attempts",
                            message="more than 5 PIN attempts makes guessing cheaper"))
    if door.lockdown and normalised.get("degradedAllow") is True:
        issues.append(Issue(severity="error", code="lockdown_offline_grant",
                            message="a door in lockdown cannot grant from the offline cache"))

    return Verification.of(issues, normalised)


def verify_camera_config(node_id: str, changes: dict[str, Any], *,
                         inventory: Inventory) -> Verification:
    node = inventory.nodes.get(node_id)
    if node is None or node.kind != "camera":
        return Verification.of([Issue(severity="error", code="unknown_node",
                                      message=f"{node_id!r} is not a camera")])
    issues: list[Issue] = []
    normalised = _normalise(changes, CAMERA_FIELDS, issues)
    if normalised.get("saveEvents") is False:
        issues.append(Issue(severity="warning", code="evidence_disabled",
                            message="the recorder will stop keeping clips used as evidence"))
    if normalised.get("minFrames", 0) > 10:
        issues.append(Issue(severity="warning", code="slow_trigger",
                            message="minFrames above 10 may miss a fast tailgate"))
    return Verification.of(issues, normalised)


@dataclass(frozen=True)
class ScenarioOutcome:
    name: str
    expect: str
    got: str
    code: str
    expect_code: str | None

    @property
    def passed(self) -> bool:
        return self.got == self.expect and (self.expect_code in (None, self.code))

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "expect": self.expect, "got": self.got, "code": self.code,
                "expect_code": self.expect_code, "passed": self.passed}


def lint_policy(candidate: dict[str, Any], *, inventory: Inventory,
                roles_in_use: set[str]) -> tuple[PolicySet | None, list[Issue]]:
    """Schema and semantic checks on a candidate policy document."""
    try:
        policy = PolicySet.model_validate(candidate)
    except ValidationError as exc:
        return None, [Issue(severity="error", code="schema",
                            message=e["msg"] + f" at {'.'.join(map(str, e['loc']))}")
                      for e in exc.errors()]
    issues: list[Issue] = []
    for rule in policy.rules:
        unknown_zones = set(rule.target.zones) - set(inventory.zones)
        unknown_doors = set(rule.target.doors) - set(inventory.doors)
        if unknown_zones or unknown_doors:
            unknown = sorted(unknown_zones | unknown_doors)
            issues.append(Issue(severity="error", code="unknown_target",
                                message=f"{rule.id}: unknown {unknown}"))
        if rule.effect == "permit" and rule.condition.is_empty():
            issues.append(Issue(severity="error", code="unconditional_permit",
                                message=f"{rule.id} permits everyone who reaches the door"))
        if rule.effect == "permit" and rule.target.any and not rule.condition.roles_any:
            issues.append(Issue(severity="error", code="broad_permit",
                                message=f"{rule.id} targets every door without a role clause"))
        unknown_roles = set(rule.condition.roles_any) - roles_in_use
        if unknown_roles:
            issues.append(Issue(severity="warning", code="unused_role",
                                message=f"{rule.id}: no subject holds {sorted(unknown_roles)}"))
    return policy, issues


def regression_issues(outcomes: list[ScenarioOutcome]) -> list[Issue]:
    return [
        Issue(severity="error", code="scenario_regression",
              message=f"'{o.name}': expected {o.expect}"
                      f"{'/' + o.expect_code if o.expect_code else ''}, got {o.got}/{o.code}")
        for o in outcomes if not o.passed
    ]


def run_scenarios(scenarios: list[dict[str, Any]],
                  simulate: Callable[[str, str, Any], tuple[str, str]]) -> list[ScenarioOutcome]:
    """Run scenarios with ``simulate(uid, door, at) -> (effect, code)``."""
    outcomes = []
    for sc in scenarios:
        effect, code = simulate(sc["uid"], sc["door"], sc.get("at"))
        outcomes.append(ScenarioOutcome(name=sc["name"], expect=sc["expect"], got=effect,
                                        code=code, expect_code=sc.get("code")))
    return outcomes
