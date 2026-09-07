"""Resolves the locale, builds the rule plan, and runs each enabled rule in
spec/rules/order.json order over a code-point array, applying its edits before the next rule
sees it. No module-level mutable state beyond the immutable, load-once-at-import spec data in
registry.py/locale.py (ARCHITECTURE.md section 7). `_engine.mode_pipelines` is what turns this
into the three public per-mode entry points."""

from __future__ import annotations

from typing import Any

# Import side effect: registers every rule id with the registry (mirrors polytypo-js's
# registry.ts, which statically imports every rule module for the same reason: importing the
# engine must be enough, without a separate caller-side step).
import polytypo._engine.rules  # noqa: F401,E402
from polytypo._engine.edits import apply_edits
from polytypo._engine.locale import get_locale_data, resolve
from polytypo._engine.registry import (
    RuleContext,
    get_rule,
    known_rule_ids,
    rule_defaults,
    rule_order,
)
from polytypo.errors import POLYTYPO_UNKNOWN_RULE, PolytypoError


def resolve_rule_plan(rules_option: dict[str, bool] | None) -> list[str]:
    """Defaults + opt-out overrides. `rules` is opt-out only (ARCHITECTURE.md section 7) -- it
    may only disable a default-on rule or enable a default-off one (`ranges`); an unknown key
    raises POLYTYPO_UNKNOWN_RULE."""
    defaults = rule_defaults()
    enabled = dict(defaults)
    if rules_option:
        for rule_id, flag in rules_option.items():
            if rule_id not in known_rule_ids():
                raise PolytypoError(POLYTYPO_UNKNOWN_RULE, f"unknown rule id: {rule_id!r}")
            enabled[rule_id] = bool(flag)
    return [rule_id for rule_id in rule_order() if enabled[rule_id]]


def prepare(
    locale: object, rules_option: dict[str, bool] | None
) -> tuple[str, dict[str, Any], list[str]]:
    """Builds the rule plan, then resolves the locale and loads its data -- the setup step shared
    by `run_pipeline` (text mode) and the span-runner (html/markdown modes). Order matters and is
    public, tested behaviour (mirrors polytypo-js's rule-runner/locale validation order exactly):
    an unknown-rule error must win over an unknown-locale error when both are present."""
    plan = resolve_rule_plan(rules_option)
    resolved_locale = resolve(locale)
    locale_data: dict[str, Any] = get_locale_data(resolved_locale)
    return resolved_locale, locale_data, plan


def run_rules(
    cp: list[int], plan: list[str], locale_data: dict[str, Any], ctx: RuleContext
) -> list[int]:
    """Runs each enabled rule in order.json order over `cp`, applying its edits before the next
    rule sees the array. Shared by text mode (this module) and the span-runner (modes.md 3.5),
    which interposes the two boundary filters of modes.md 3.4 between rule and apply."""
    current = cp
    for rule_id in plan:
        rule_fn = get_rule(rule_id)
        edits = rule_fn(current, locale_data, ctx)
        if edits:
            current = apply_edits(current, edits, rule_id)
    return current
