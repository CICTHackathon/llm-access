"""Client for the gateway-esp32 enforcement node (HTTP API on port 80)."""

from __future__ import annotations

from typing import Any

import httpx

from src.mcp_server.devices.http import DeviceClient


def _wire(value: Any) -> str:
    # The firmware's flat-field reader takes strings; booleans by first letter.
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class GatewayClient(DeviceClient):
    def __init__(self, node_id: str, base_url: str, *, api_token: str = "",
                 timeout_s: float = 3.0,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        headers = {"X-Api-Token": api_token} if api_token else {}
        super().__init__(node_id, base_url, timeout_s=timeout_s, headers=headers,
                         transport=transport)

    async def status(self) -> dict[str, Any]:
        return await self.request("GET", "/api/status")

    async def events(self, since: int = 0, limit: int = 48) -> list[dict[str, Any]]:
        data = await self.request("GET", "/api/events", params={"since": since, "limit": limit})
        return list(data.get("events", []))

    async def config(self) -> dict[str, Any]:
        return await self.request("GET", "/api/config")

    async def set_config(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Write several settings in one transaction (the firmware judges them together)."""
        return await self.request("POST", "/api/config",
                                  json={k: _wire(v) for k, v in changes.items()})

    async def acl(self) -> dict[str, Any]:
        return await self.request("GET", "/api/acl")

    async def acl_upsert(self, uid: str, pin_digest: str, ttl: int) -> dict[str, Any]:
        return await self.request("POST", "/api/acl",
                                  json={"uid": uid, "pin": pin_digest, "ttl": str(ttl)})

    async def acl_remove(self, uid: str) -> dict[str, Any]:
        return await self.request("POST", "/api/acl", json={"remove": uid})

    async def arm_enrolment(self, ms: int = 20000) -> dict[str, Any]:
        return await self.request("POST", "/api/enrol", params={"ms": ms})

    async def take_enrolment(self) -> dict[str, Any]:
        return await self.request("GET", "/api/enrol")

    async def unlock(self, who: str) -> dict[str, Any]:
        return await self.request("POST", "/api/unlock", json={"who": who[:23]})

    async def lock(self, who: str) -> dict[str, Any]:
        return await self.request("POST", "/api/lock", json={"who": who[:23]})
