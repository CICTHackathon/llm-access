"""ABAC rule evaluation with the deny-overrides combining algorithm and default deny."""

from __future__ import annotations

from src.mcp_server.engine.conditions import EvalContext, check_condition
from src.mcp_server.engine.domain.access import Authorization, Effect, RuleFailure, RuleMatch
from src.mcp_server.engine.domain.policy import PolicySet, Rule


def applicable_rules(policies: PolicySet, ctx: EvalContext) -> list[Rule]:
    """Rules whose target covers the door and whose condition holds."""
    return [
        rule
        for rule in policies.rules
        if rule.target.applies_to(ctx.door_id, ctx.zone_id)
        and check_condition(rule.condition, ctx) is None
    ]


def authorize(policies: PolicySet, ctx: EvalContext) -> Authorization:
    denies: list[RuleMatch] = []
    permits: list[RuleMatch] = []
    near_misses: list[RuleFailure] = []

    for rule in policies.rules:
        if not rule.target.applies_to(ctx.door_id, ctx.zone_id):
            continue
        failure = check_condition(rule.condition, ctx)
        if failure is None:
            match = RuleMatch(rule_id=rule.id, effect=Effect(rule.effect),
                              description=rule.description)
            (denies if rule.effect == "deny" else permits).append(match)
        elif rule.effect == "permit":
            near_misses.append(
                RuleFailure(rule_id=rule.id, code=failure.code, detail=failure.detail)
            )

    if denies:
        return Authorization(effect=Effect.DENY, code=denies[0].rule_id, matched=denies,
                             near_misses=near_misses)
    if permits:
        return Authorization(effect=Effect.PERMIT, code=permits[0].rule_id, matched=permits)
    code = near_misses[0].code if near_misses else "no_rule_for_door"
    return Authorization(effect=Effect.DENY, code=code, near_misses=near_misses)
