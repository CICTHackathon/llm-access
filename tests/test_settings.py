"""Settings load .env into the process environment without overriding what is already set."""

from __future__ import annotations

import os

from src.settings import get_settings


def test_dotenv_exports_secrets_but_respects_existing_env(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text(
        "LLM_ACCESS_PORT=9090\nGW9_DECISION_KEY=from-dotenv\nGW9_API_TOKEN=from-dotenv\n",
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GW9_DECISION_KEY", raising=False)
    monkeypatch.setenv("GW9_API_TOKEN", "from-shell")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.port == 9090
        assert os.environ["GW9_DECISION_KEY"] == "from-dotenv"
        assert os.environ["GW9_API_TOKEN"] == "from-shell"
    finally:
        os.environ.pop("GW9_DECISION_KEY", None)
        get_settings.cache_clear()
