"""Identity: the subject directory and card registry (the PIP). PINs are never returned."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from src.mcp_server.runtime import get_runtime

mcp = FastMCP(
    "smartgate-identity",
    instructions="Who the subjects are, which cards they hold, and card enrolment at a "
    "gateway. Changing a credential goes through the verifier, not through this server.",
)


@mcp.tool()
def list_subjects(role: str | None = None, department: str | None = None) -> list[dict[str, Any]]:
    """Subjects, optionally filtered by role and/or department."""
    subjects = get_runtime().sot.directory.subjects
    return [s.public_view() for s in subjects
            if (role is None or role in s.roles)
            and (department is None or s.department == department)]


@mcp.tool()
def get_subject(subject_id: str) -> dict[str, Any]:
    """One subject with their credentials (status, expiry, whether a PIN is on file)."""
    directory = get_runtime().sot.directory
    subject = directory.subject(subject_id)
    if subject is None:
        raise ValueError(f"unknown subject {subject_id!r}")
    view = subject.public_view()
    sponsor_id = subject.attributes.get("sponsor")
    if sponsor_id:
        sponsor = directory.subject(str(sponsor_id))
        view["sponsor_status"] = sponsor.status if sponsor else "missing"
    view["credentials"] = [c.public_view() for c in directory.credentials_of(subject_id)]
    return view


@mcp.tool()
def resolve_card(uid: str) -> dict[str, Any]:
    """Which subject a card UID (e.g. 0xa1b2c3d4) belongs to, and the card's state."""
    directory = get_runtime().sot.directory
    cred = directory.credential(uid)
    if cred is None:
        return {"uid": uid, "known": False}
    subject = directory.subject(cred.subject)
    return {"known": True, **cred.public_view(),
            "subject_detail": subject.public_view() if subject else None}


@mcp.tool()
async def arm_card_enrolment(gateway_id: str, seconds: int = 20) -> dict[str, Any]:
    """Make the gateway report the next card presented instead of starting a transaction."""
    seconds = max(5, min(seconds, 120))
    await get_runtime().fleet.gateway(gateway_id).arm_enrolment(seconds * 1000)
    return {"armed": True, "gateway": gateway_id, "seconds": seconds}


@mcp.tool()
async def collect_card_enrolment(gateway_id: str) -> dict[str, Any]:
    """Collect the UID read by an armed gateway, and whether it is already registered."""
    result = await get_runtime().fleet.gateway(gateway_id).take_enrolment()
    uid = result.get("uid") or ""
    if not uid:
        return {"uid": None, "armed": bool(result.get("armed"))}
    cred = get_runtime().sot.directory.credential(uid)
    return {"uid": uid, "registered": cred is not None,
            "credential": cred.public_view() if cred else None}
