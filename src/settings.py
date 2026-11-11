"""Runtime settings, read from the environment (prefix ``LLM_ACCESS_``) and ``.env``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

AgentReview = Literal["off", "on_permit", "always"]
FailureMode = Literal["deny", "rules"]
DeployMode = Literal["live", "dry_run"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLM_ACCESS_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Where the source of truth lives and where runtime state is written.
    config_dir: Path = Path("config")
    state_dir: Path = Path("var")

    # LLM used by every agent (CrewAI "<provider>/<model>" string).
    llm_model: str = "anthropic/claude-opus-5-5"
    llm_base_url: str | None = None
    llm_api_key: str | None = None

    # Decision pipeline.
    agent_review: AgentReview = "on_permit"
    agent_failure_mode: FailureMode = "deny"
    agent_min_confidence: float = Field(0.7, ge=0.0, le=1.0)
    decision_budget_s: float = Field(20.0, gt=0.0, le=28.0)

    # Devices and operations.
    device_timeout_s: float = Field(3.0, gt=0.0)
    allow_actuation: bool = False
    deploy_mode: DeployMode = "live"
    plan_ttl_s: int = Field(900, gt=0)

    # HTTP API.
    host: str = "0.0.0.0"
    port: int = 8080
    verbose_agents: bool = False

    @property
    def plans_dir(self) -> Path:
        return self.state_dir / "plans"

    @property
    def revisions_dir(self) -> Path:
        return self.state_dir / "revisions"

    @property
    def decision_log_path(self) -> Path:
        return self.state_dir / "decisions.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
