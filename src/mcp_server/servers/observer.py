"""Observer: live state of the gateways and recorders, and badge/motion correlation."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.mcp_server.devices import DeviceError
from src.mcp_server.engine.correlation import correlate
from src.mcp_server.runtime import get_runtime

mcp = FastMCP(
    "smartgate-observer",
    instructions="Read-only monitoring of the edge nodes: status, audit events, camera "
    "events and the movement classes obtained by joining them.",
)


@mcp.tool()
async def get_gateway_status(node_id: str) -> dict[str, Any]:
    """FSM state, door position, transaction in flight, counters, PDP link and clock."""
    return await get_runtime().fleet.gateway(node_id).status()


@mcp.tool()
async def get_gateway_events(node_id: str, since: int = 0, limit: int = 48) -> list[dict[str, Any]]:
    """The gateway's audit ring, newest first (state, effect, reason, uid, epoch)."""
    return await get_runtime().fleet.gateway(node_id).events(since=since, limit=limit)


@mcp.tool()
async def get_camera_status(node_id: str) -> dict[str, Any]:
    """Recorder counters, frame rate and clock."""
    return await get_runtime().fleet.camera(node_id).status()


@mcp.tool()
async def get_camera_events(node_id: str) -> list[dict[str, Any]]:
    """Recent motion events with verdict, scores, bounding box and clip path."""
    return await get_runtime().fleet.camera(node_id).events()


@mcp.tool()
async def correlate_door_movements(door_id: str, window_s: int | None = None) -> dict[str, Any]:
    """Join the door's badge events to its camera events into movement classes:
    attested transit, unattested motion (tailgate/propped door), unconsummated grant."""
    runtime = get_runtime()
    window = window_s or runtime.sot.policies.risk.correlation_window_s
    gateway = runtime.fleet.gateway_for_door(door_id)
    camera = runtime.fleet.camera_for_door(door_id)
    if camera is None:
        return {"available": False, "reason": f"{door_id} has no camera"}
    gw_status, gw_events, cam_status, cam_events = await asyncio.gather(
        gateway.status(), gateway.events(), camera.status(), camera.events())
    report = correlate(gw_events, cam_events, window_s=window,
                       gateway_clock_set=bool(gw_status.get("clockSet")),
                       camera_clock_set=bool(cam_status.get("clockSet")))
    return {**report.model_dump(mode="json"), "summary": report.summary()}


@mcp.tool()
async def check_fleet_health() -> list[dict[str, Any]]:
    """Reachability and headline state of every node in the inventory."""
    runtime = get_runtime()

    async def probe(node_id: str, kind: str) -> dict[str, Any]:
        client = (runtime.fleet.gateway(node_id) if kind == "gateway"
                  else runtime.fleet.camera(node_id))
        try:
            status = await client.status()
        except DeviceError as exc:
            return {"node": node_id, "kind": kind, "reachable": False, "error": str(exc)}
        keys = ("state", "door", "clockSet", "uptime", "fps", "ip")
        return {"node": node_id, "kind": kind, "reachable": True,
                **{k: status[k] for k in keys if k in status}}

    nodes = runtime.sot.inventory.nodes
    return list(await asyncio.gather(*(probe(n, v.kind) for n, v in nodes.items())))
