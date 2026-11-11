"""Shared fixtures: an isolated copy of the config, a runtime over it, and a fake gateway."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest

from src.mcp_server import runtime as runtime_module
from src.mcp_server.runtime import Runtime
from src.settings import Settings, get_settings

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DECISION_KEY = "bench-key"


def local(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=TZ)


class FakeGateway:
    """Enough of the gateway-esp32 HTTP API to exercise the clients and the deployer."""

    def __init__(self) -> None:
        self.config: dict[str, Any] = {
            "closedAngle": 90, "openAngle": 20, "openHoldMs": 5000, "pinTimeoutMs": 15000,
            "pdpTimeoutMs": 4000, "pinAttempts": 3, "requirePin": True, "degradedAllow": True,
            "buzzerEnabled": True, "pdpUrl": "", "doorId": "door-1", "pdpToken": "",
            "decisionKey": "set", "apiToken": "set",
        }
        self.status: dict[str, Any] = {"state": "idle", "door": "locked", "clockSet": True,
                                       "signedDecisions": True, "pdp": {"lastCode": 0}}
        self.events: list[dict[str, Any]] = []
        self.acl: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, str]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        self.calls.append((method, path))
        body = json.loads(request.content) if request.content else {}
        if path == "/api/status":
            return httpx.Response(200, json=self.status)
        if path == "/api/events":
            return httpx.Response(200, json={"last": len(self.events), "events": self.events})
        if path == "/api/config" and method == "GET":
            return httpx.Response(200, json=self.config)
        if path == "/api/config" and method == "POST":
            for key, value in body.items():
                current = self.config.get(key)
                if isinstance(current, bool):
                    self.config[key] = str(value)[:1] in "1tTyY"
                elif isinstance(current, int):
                    self.config[key] = int(value)
                else:
                    self.config[key] = value
            return httpx.Response(200, json={"ok": True})
        if path == "/api/acl" and method == "GET":
            entries = [{"uid": u, "pin": True, "ttl": int(e["ttl"])} for u, e in self.acl.items()]
            return httpx.Response(200, json={"entries": entries, "capacity": 16})
        if path == "/api/acl" and method == "POST":
            if "remove" in body:
                self.acl.pop(body["remove"], None)
            else:
                self.acl[body["uid"]] = body
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"error": "not found"})


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    shutil.copytree(ROOT / "config", target)
    return target


@pytest.fixture
def settings(config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("GW1_DECISION_KEY", DECISION_KEY)
    monkeypatch.setenv("GW1_PDP_TOKEN", "pdp-secret")
    monkeypatch.setenv("GW1_API_TOKEN", "api-secret")
    for name in ("GW2_DECISION_KEY", "GW2_PDP_TOKEN", "GW2_API_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_ACCESS_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("LLM_ACCESS_STATE_DIR", str(tmp_path / "var"))
    monkeypatch.setenv("LLM_ACCESS_AGENT_REVIEW", "on_permit")
    monkeypatch.setenv("LLM_ACCESS_DEPLOY_MODE", "live")
    get_settings.cache_clear()
    runtime_module.get_runtime.cache_clear()
    yield get_settings()
    get_settings.cache_clear()
    runtime_module.get_runtime.cache_clear()


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def runtime(settings: Settings, gateway: FakeGateway) -> Runtime:
    """The process-wide runtime (as the MCP servers see it), wired to the fake gateway."""
    rt = runtime_module.get_runtime()
    rt.fleet.transport = httpx.MockTransport(gateway.handler)
    return rt
