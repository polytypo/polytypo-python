"""Rule order and defaults, derived from vendor/polytypo-spec/rules/order.json at import time --
never hand-duplicated (ARCHITECTURE.md section 4.5: order.json is the single source of truth,
never registration order, never dict-iteration order)."""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from importlib import resources
from typing import Any, TypedDict

from polytypo._engine.edits import Edit


class RuleContext(TypedDict):
    mode: str
    dialect: str | None
    locale: str


RuleFn = Callable[[list[int], dict[str, Any], RuleContext], list[Edit]]

_ORDER_PACKAGE = "polytypo._data.rules"


@lru_cache(maxsize=1)
def _order_data() -> dict[str, Any]:
    text = resources.files(_ORDER_PACKAGE).joinpath("order.json").read_text("utf-8")
    result: dict[str, Any] = json.loads(text)
    return result


@lru_cache(maxsize=1)
def rule_order() -> list[str]:
    """Rule ids in ascending pipeline order."""
    rules = sorted(_order_data()["rules"], key=lambda r: r["order"])
    return [r["id"] for r in rules]


@lru_cache(maxsize=1)
def rule_defaults() -> dict[str, bool]:
    """Rule id -> default enabled/disabled (only `ranges` defaults to False). order.json's
    `default` field is the string "on"/"off", not a JSON boolean -- `bool(x)` on either string
    would be True, so this must compare against "on" explicitly."""
    return {r["id"]: r["default"] == "on" for r in _order_data()["rules"]}


_RULES: dict[str, RuleFn] = {}


def register(rule_id: str, fn: RuleFn) -> None:
    _RULES[rule_id] = fn


def get_rule(rule_id: str) -> RuleFn:
    return _RULES[rule_id]


def known_rule_ids() -> frozenset[str]:
    return frozenset(rule_defaults().keys())
