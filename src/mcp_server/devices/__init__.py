"""Southbound adapter: HTTP clients for the edge nodes' published JSON APIs.

The firmware itself lives in the hardware repository, linked at ``iot/`` as a git
submodule. Nothing here depends on that code; this package only speaks the HTTP
contract documented in ``iot/firmware/*/README.md``.
"""

from src.mcp_server.devices.camera import CameraClient
from src.mcp_server.devices.fleet import Fleet
from src.mcp_server.devices.gateway import GatewayClient
from src.mcp_server.devices.http import DeviceError

__all__ = ["CameraClient", "DeviceError", "Fleet", "GatewayClient"]
