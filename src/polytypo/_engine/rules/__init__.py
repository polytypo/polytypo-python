"""Importing this module registers every rule with the registry. Order of import here doesn't
matter -- pipeline order comes from registry.rule_order(), never import/registration order."""

from __future__ import annotations

from polytypo._engine.registry import register
from polytypo._engine.rules import (
    apostrophe,
    dashes,
    ellipsis,
    hyphen,
    nbsp,
    quotes,
    ranges,
    spaces,
    symbols,
)

register(spaces.RULE_ID, spaces.scan)
register(ellipsis.RULE_ID, ellipsis.scan)
register(ranges.RULE_ID, ranges.scan)
register(dashes.RULE_ID, dashes.scan)
register(hyphen.RULE_ID, hyphen.scan)
register(quotes.RULE_ID, quotes.scan)
register(apostrophe.RULE_ID, apostrophe.scan)
register(symbols.RULE_ID, symbols.scan)
register(nbsp.RULE_ID, nbsp.scan)
