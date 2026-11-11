"""Joins badge events to camera events by epoch, as the operator console's Timeline does.

| Class | Credential | Motion | Interpretation                              |
|-------|------------|--------|---------------------------------------------|
| 1     | permit     | yes    | Attested transit                            |
| 2     | none       | yes    | Unattested motion: tailgate, propped door   |
| 3     | permit     | no     | Unconsummated grant: unused or probing      |

Camera events the cascade rejected as not-a-person (``rejected-*``) are left out of
the join, so they cannot raise a Class 2 on their own.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MOTION_VERDICTS = frozenset({"motion", "classified"})
MovementClass = Literal["attested_transit", "unattested_motion", "unconsummated_grant", "denial"]


class Movement(BaseModel):
    epoch: int
    movement: MovementClass
    credential_event: dict[str, Any] | None = None
    motion_event: dict[str, Any] | None = None


class CorrelationReport(BaseModel):
    available: bool
    reason: str = ""
    window_s: int
    movements: list[Movement] = Field(default_factory=list)
    unstamped: int = 0

    def count(self, movement: MovementClass) -> int:
        return sum(1 for m in self.movements if m.movement == movement)

    def summary(self) -> dict[str, int]:
        return {
            "attested_transit": self.count("attested_transit"),
            "unattested_motion": self.count("unattested_motion"),
            "unconsummated_grant": self.count("unconsummated_grant"),
            "denial": self.count("denial"),
        }


def correlate(
    gateway_events: list[dict[str, Any]],
    camera_events: list[dict[str, Any]],
    *,
    window_s: int = 15,
    gateway_clock_set: bool = True,
    camera_clock_set: bool = True,
) -> CorrelationReport:
    if not (gateway_clock_set and camera_clock_set):
        unset = [name for name, ok in (("gateway", gateway_clock_set),
                                       ("camera", camera_clock_set)) if not ok]
        return CorrelationReport(available=False, window_s=window_s,
                                 reason=f"clock unset on {' and '.join(unset)}")

    credential_all = [e for e in gateway_events if e.get("effect") in ("permit", "deny")]
    credentials = sorted((e for e in credential_all if e.get("epoch")), key=lambda e: e["epoch"])
    motion_all = [e for e in camera_events if e.get("verdict") in MOTION_VERDICTS]
    motions = sorted((e for e in motion_all if e.get("epoch")), key=lambda e: e["epoch"])
    unstamped = (len(credential_all) - len(credentials)) + (len(motion_all) - len(motions))

    used: set[Any] = set()
    movements: list[Movement] = []
    for cred in credentials:
        match = next(
            (m for m in motions
             if m.get("id") not in used and abs(m["epoch"] - cred["epoch"]) <= window_s),
            None,
        )
        if match is not None:
            used.add(match.get("id"))
        if cred["effect"] == "permit":
            kind: MovementClass = "attested_transit" if match else "unconsummated_grant"
        else:
            kind = "denial"
        movements.append(Movement(epoch=cred["epoch"], movement=kind,
                                  credential_event=cred, motion_event=match))

    for motion in motions:
        if motion.get("id") not in used:
            movements.append(Movement(epoch=motion["epoch"], movement="unattested_motion",
                                      motion_event=motion))

    movements.sort(key=lambda m: m.epoch, reverse=True)
    return CorrelationReport(available=True, window_s=window_s, movements=movements,
                             unstamped=unstamped)
