"""Shared async HTTP plumbing for the device clients."""

from __future__ import annotations

from typing import Any

import httpx


class DeviceError(RuntimeError):
    """A device did not answer, or answered with an error."""

    def __init__(self, node_id: str, message: str, status: int | None = None) -> None:
        super().__init__(f"{node_id}: {message}")
        self.node_id = node_id
        self.status = status


class DeviceClient:
    def __init__(self, node_id: str, base_url: str, *, timeout_s: float = 3.0,
                 headers: dict[str, str] | None = None,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.node_id = node_id
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout_s
        self._headers = headers or {}
        self._transport = transport

    async def request(self, method: str, path: str, *, json: dict[str, Any] | None = None,
                      params: dict[str, Any] | None = None) -> Any:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout,
                                         headers=self._headers,
                                         transport=self._transport) as client:
                response = await client.request(method, path, json=json, params=params)
        except httpx.HTTPError as exc:
            raise DeviceError(self.node_id, f"{method} {path} failed: {exc}") from exc
        if response.status_code >= 400:
            detail = response.text.strip()[:200]
            raise DeviceError(self.node_id, f"{method} {path} -> {response.status_code} {detail}",
                              status=response.status_code)
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise DeviceError(self.node_id, f"{method} {path}: response is not JSON") from exc
