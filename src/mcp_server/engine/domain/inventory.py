"""Physical site: zones, doors and the edge nodes that enforce them."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Site(_Model):
    id: str
    name: str = ""
    timezone: str = "UTC"


class Zone(_Model):
    name: str = ""
    level: int = Field(0, ge=0)
    department: str | None = None


class Door(_Model):
    name: str = ""
    zone: str
    gateway: str
    camera: str | None = None
    require_pin: bool | None = None
    lockdown: bool = False


class Node(_Model):
    kind: Literal["gateway", "camera"]
    url: str
    door: str
    api_token_env: str | None = None
    pdp_token_env: str | None = None
    decision_key_env: str | None = None

    def secret(self, which: Literal["api_token", "pdp_token", "decision_key"]) -> str:
        """Resolve a secret from the environment variable the inventory names for it."""
        env_name = getattr(self, f"{which}_env")
        return os.environ.get(env_name, "") if env_name else ""


class Inventory(_Model):
    site: Site
    zones: dict[str, Zone]
    doors: dict[str, Door]
    nodes: dict[str, Node]

    @model_validator(mode="after")
    def _check_references(self) -> Inventory:
        for door_id, door in self.doors.items():
            if door.zone not in self.zones:
                raise ValueError(f"door {door_id}: unknown zone {door.zone!r}")
            gateway = self.nodes.get(door.gateway)
            if gateway is None or gateway.kind != "gateway":
                raise ValueError(f"door {door_id}: {door.gateway!r} is not a gateway node")
            if door.camera:
                camera = self.nodes.get(door.camera)
                if camera is None or camera.kind != "camera":
                    raise ValueError(f"door {door_id}: {door.camera!r} is not a camera node")
        for node_id, node in self.nodes.items():
            if node.door not in self.doors:
                raise ValueError(f"node {node_id}: unknown door {node.door!r}")
        return self
