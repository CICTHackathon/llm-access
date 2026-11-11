"""Builds device clients from the inventory, resolving each node's secrets from the env."""

from __future__ import annotations

import httpx

from src.mcp_server.devices.camera import CameraClient
from src.mcp_server.devices.gateway import GatewayClient
from src.mcp_server.engine.source_of_truth import SourceOfTruth


class Fleet:
    def __init__(self, sot: SourceOfTruth, *, timeout_s: float = 3.0,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.sot = sot
        self.timeout_s = timeout_s
        self.transport = transport

    def gateway(self, node_id: str) -> GatewayClient:
        node = self.sot.inventory.nodes.get(node_id)
        if node is None or node.kind != "gateway":
            raise KeyError(f"{node_id!r} is not a gateway in the inventory")
        return GatewayClient(node_id, node.url, api_token=node.secret("api_token"),
                             timeout_s=self.timeout_s, transport=self.transport)

    def camera(self, node_id: str) -> CameraClient:
        node = self.sot.inventory.nodes.get(node_id)
        if node is None or node.kind != "camera":
            raise KeyError(f"{node_id!r} is not a camera in the inventory")
        return CameraClient(node_id, node.url, timeout_s=self.timeout_s,
                            transport=self.transport)

    def gateway_for_door(self, door_id: str) -> GatewayClient:
        return self.gateway(self.sot.inventory.doors[door_id].gateway)

    def camera_for_door(self, door_id: str) -> CameraClient | None:
        camera = self.sot.inventory.doors[door_id].camera
        return self.camera(camera) if camera else None
