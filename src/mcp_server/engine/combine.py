"""Combines the deterministic outcome with the agent review into the final effect.

The combination is deny-overrides with the engine as the ceiling:

| Engine | Agent review                         | Final  | Code                     |
|--------|--------------------------------------|--------|--------------------------|
| deny   | anything (advisory only)             | deny   | engine code              |
| permit | not requested                        | permit | matched rule             |
| permit | permit, confidence >= threshold      | permit | matched rule             |
| permit | permit, confidence <  threshold      | deny   | agent_low_confidence     |
| permit | deny                                 | deny   | agent's code             |
| permit | failed / timed out, mode ``deny``    | deny   | agent_unavailable        |
| permit | failed / timed out, mode ``rules``   | permit | matched rule             |

An agent can therefore make a decision stricter, never looser.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.mcp_server.engine.domain.access import AgentVerdict, Effect, Stage


@dataclass(frozen=True)
class Combined:
    effect: Effect
    code: str
    stage: Stage | None


def combine_review(
    effect: Effect,
    code: str,
    *,
    verdict: AgentVerdict | None,
    error: str | None,
    failure_mode: str,
    min_confidence: float,
) -> Combined:
    if verdict is None and error is None:
        return Combined(effect, code, None)

    if effect is Effect.DENY:
        detail = f"advisory only: {verdict.code}" if verdict else f"advisory failed: {error}"
        return Combined(effect, code, Stage(name="agent_review", passed=True, code="advisory",
                                            detail=detail))

    if verdict is None:
        if failure_mode == "rules":
            return Combined(effect, code, Stage(name="agent_review", passed=True,
                                                code="fallback_rules",
                                                detail=f"review failed ({error}); rules stand"))
        return Combined(Effect.DENY, "agent_unavailable",
                        Stage(name="agent_review", passed=False, code="agent_unavailable",
                              detail=f"review failed ({error}); failing secure"))

    if verdict.effect is Effect.DENY:
        return Combined(Effect.DENY, verdict.code,
                        Stage(name="agent_review", passed=False, code=verdict.code,
                              detail="; ".join(verdict.reasons) or "agent denied"))

    if verdict.confidence < min_confidence:
        return Combined(Effect.DENY, "agent_low_confidence",
                        Stage(name="agent_review", passed=False, code="agent_low_confidence",
                              detail=f"confidence {verdict.confidence:.2f} < {min_confidence:.2f}"))

    return Combined(effect, code, Stage(name="agent_review", passed=True, code=verdict.code,
                                        detail="; ".join(verdict.reasons) or "consistent"))
