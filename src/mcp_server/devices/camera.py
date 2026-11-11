"""Client for the esp32cam movement recorder (HTTP API on port 80, unauthenticated)."""

from __future__ import annotations

from typing import Any

import httpx

from src.mcp_server.devices.http import DeviceClient


class CameraClient(DeviceClient):
    def __init__(self, node_id: str, base_url: str, *, timeout_s: float = 3.0,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(node_id, base_url, timeout_s=timeout_s, transport=transport)

    async def status(self) -> dict[str, Any]:
        return await self.request("GET", "/api/status")

    async def events(self) -> list[dict[str, Any]]:
        data = await self.request("GET", "/api/events")
        return list(data) if isinstance(data, list) else []

    async def config(self) -> dict[str, Any]:
        return await self.request("GET", "/api/config")

    async def set_config(self, changes: dict[str, Any]) -> dict[str, Any]:
        # The recorder takes settings as integer query parameters.
        params = {k: int(v) if isinstance(v, bool) else v for k, v in changes.items()}
        return await self.request("POST", "/api/config", params=params)
