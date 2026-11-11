"""Change plans: the only way a configuration change reaches a device or a policy file.

The verifier creates a plan when a change passes validation. The deployer applies a
plan only if it is still ``verified``, not expired, its payload is unchanged, and the
document it was verified against has not changed since. An agent can therefore never
deploy something the verifier did not see.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

PlanKind = Literal["gateway_config", "camera_config", "acl_sync", "policy_update",
                   "credential_update"]
PlanStatus = Literal["verified", "applied", "failed", "rolled_back", "superseded"]


def _checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class Plan(BaseModel):
    id: str
    kind: PlanKind
    target: str
    summary: str
    payload: dict[str, Any]
    checksum: str
    base_version: str | None = None
    status: PlanStatus = "verified"
    issues: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    expires_at: datetime
    applied_at: datetime | None = None
    result: dict[str, Any] = Field(default_factory=dict)

    def public_view(self) -> dict[str, Any]:
        """The plan without its payload's secrets (ACL digests stay on disk)."""
        data = self.model_dump(mode="json")
        if self.kind == "acl_sync":
            data["payload"] = {
                "door": self.payload.get("door"),
                "entries": [{k: v for k, v in e.items() if k != "pin"}
                            for e in self.payload.get("entries", [])],
            }
        return data


class PlanError(RuntimeError):
    pass


class PlanStore:
    def __init__(self, directory: Path, ttl_s: int = 900) -> None:
        self.directory = Path(directory)
        self.ttl = timedelta(seconds=ttl_s)
        self._lock = threading.Lock()

    def create(self, *, kind: PlanKind, target: str, summary: str, payload: dict[str, Any],
               issues: list[dict[str, Any]], base_version: str | None = None) -> Plan:
        now = datetime.now(UTC)
        plan = Plan(id=f"pln-{now:%Y%m%d%H%M%S}-{secrets.token_hex(3)}", kind=kind,
                    target=target, summary=summary, payload=payload,
                    checksum=_checksum(payload), base_version=base_version, issues=issues,
                    created_at=now, expires_at=now + self.ttl)
        self._save(plan)
        return plan

    def get(self, plan_id: str) -> Plan:
        path = self._path(plan_id)
        if not path.exists():
            raise PlanError(f"no plan {plan_id!r}")
        return Plan.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self, status: PlanStatus | None = None, limit: int = 20) -> list[Plan]:
        if not self.directory.exists():
            return []
        plans = [Plan.model_validate_json(p.read_text(encoding="utf-8"))
                 for p in self.directory.glob("pln-*.json")]
        plans = [p for p in plans if status is None or p.status == status]
        return sorted(plans, key=lambda p: p.created_at, reverse=True)[:limit]

    def claim(self, plan_id: str, *, current_version: str | None) -> Plan:
        """Check a plan is still deployable. Raises :class:`PlanError` if it is not."""
        plan = self.get(plan_id)
        if plan.status != "verified":
            raise PlanError(f"plan {plan_id} is {plan.status}, not verified")
        if datetime.now(UTC) > plan.expires_at:
            raise PlanError(f"plan {plan_id} expired at {plan.expires_at:%H:%M:%S}Z; "
                            "verify the change again")
        if _checksum(plan.payload) != plan.checksum:
            raise PlanError(f"plan {plan_id} payload was modified after verification")
        if plan.base_version and current_version and plan.base_version != current_version:
            raise PlanError(f"plan {plan_id} was verified against a version that has since "
                            "changed; verify the change again")
        return plan

    def finish(self, plan: Plan, status: PlanStatus, result: dict[str, Any]) -> Plan:
        plan.status = status
        plan.result = result
        plan.applied_at = datetime.now(UTC)
        self._save(plan)
        return plan

    def _path(self, plan_id: str) -> Path:
        if (not isinstance(plan_id, str) or not plan_id.startswith("pln-")
                or "/" in plan_id or "\\" in plan_id):
            raise PlanError(f"malformed plan id {plan_id!r}")
        return self.directory / f"{plan_id}.json"

    def _save(self, plan: Plan) -> None:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._path(plan.id).write_text(plan.model_dump_json(indent=2), encoding="utf-8")
