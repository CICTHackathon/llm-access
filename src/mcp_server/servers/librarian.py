"""Librarian: read-only source of truth for the site, its doors and the policy set."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from src.mcp_server.runtime import get_runtime

mcp = FastMCP(
    "smartgate-librarian",
    instructions="Source of truth for zones, doors, edge nodes and access policy. "
    "Consult it before reasoning about any door or rule; never assume values.",
)


@mcp.tool()
def get_site_overview() -> dict[str, Any]:
    """Site, zones (with security level and owning department) and doors with their nodes."""
    sot = get_runtime().sot
    inv = sot.inventory
    return {
        "site": inv.site.model_dump(),
        "zones": {k: v.model_dump() for k, v in inv.zones.items()},
        "doors": {k: v.model_dump() for k, v in inv.doors.items()},
        "nodes": {k: {"kind": v.kind, "door": v.door, "url": v.url}
                  for k, v in inv.nodes.items()},
        "versions": {doc: sot.version(doc) for doc in ("inventory", "identities", "policies")},
    }


@mcp.tool()
def get_door(door_id: str) -> dict[str, Any]:
    """One door: its zone, nodes, PIN requirement, lockdown flag and the rules targeting it."""
    sot = get_runtime().sot
    door = sot.inventory.doors.get(door_id)
    if door is None:
        raise ValueError(f"unknown door {door_id!r}; known: {sorted(sot.inventory.doors)}")
    policies = sot.policies
    rules = [r.model_dump(mode="json") for r in policies.rules
             if r.target.applies_to(door_id, door.zone)]
    require_pin = policies.defaults.require_pin if door.require_pin is None else door.require_pin
    return {"door_id": door_id, **door.model_dump(), "effective_require_pin": require_pin,
            "zone_detail": sot.inventory.zones[door.zone].model_dump(), "rules": rules}


@mcp.tool()
def get_policies() -> dict[str, Any]:
    """The full policy set: defaults, risk thresholds, schedules, rules and guidance."""
    sot = get_runtime().sot
    return {"version": sot.version("policies"), **sot.policies.model_dump(mode="json")}


@mcp.tool()
def get_guidance() -> list[dict[str, str]]:
    """Natural-language policy statements the access judge must apply on top of the rules."""
    return [g.model_dump() for g in get_runtime().sot.policies.guidance]


@mcp.tool()
def search_policies(query: str) -> list[dict[str, Any]]:
    """Rules and guidance whose id, description or text contains ``query`` (case-insensitive)."""
    q = query.lower()
    policies = get_runtime().sot.policies
    hits: list[dict[str, Any]] = [
        {"kind": "rule", **r.model_dump(mode="json")} for r in policies.rules
        if q in r.id.lower() or q in r.description.lower()
    ]
    hits += [{"kind": "guidance", **g.model_dump()} for g in policies.guidance
             if q in g.id.lower() or q in g.text.lower()]
    return hits


@mcp.resource("librarian://inventory")
def inventory_resource() -> str:
    return get_runtime().sot.path("inventory").read_text(encoding="utf-8")


@mcp.resource("librarian://policies")
def policies_resource() -> str:
    return get_runtime().sot.path("policies").read_text(encoding="utf-8")
