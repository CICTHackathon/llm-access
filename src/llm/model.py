"""The LLM shared by every agent."""

from __future__ import annotations

from typing import Any

from src.settings import Settings


def build_llm(settings: Settings) -> Any:
    from crewai import LLM

    kwargs: dict[str, Any] = {"model": settings.llm_model}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    if settings.llm_api_key:
        kwargs["api_key"] = settings.llm_api_key
    # Current Claude models reject sampling parameters, so temperature is only pinned
    # for other providers, where 0 keeps the agents' reasoning repeatable.
    if not settings.llm_model.startswith("anthropic/"):
        kwargs["temperature"] = 0
    return LLM(**kwargs)
