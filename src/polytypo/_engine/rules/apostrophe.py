"""spec/rules/apostrophe.md -- order 50, default on. Locale data: quotes.elisionIdioms
(indirectly, via the shared ambiguity predicate's preserve set)."""

from __future__ import annotations

from typing import Any

from polytypo._engine.edits import Edit
from polytypo._engine.registry import RuleContext
from polytypo._engine.rules import _quote_ambiguity
from polytypo._engine.sentinels import LINE_MARKER, MARKER, NONE
from polytypo._engine.unicode import is_letter

RULE_ID = "apostrophe"

SQ = 0x27
DIGIT = frozenset(range(0x30, 0x3A))
# Includes LINE_MARKER: a member of BREAK for every rule everywhere (modes.md 3.2).
BREAK = frozenset({0x0A, 0x0D, 0x0B, 0x0C, 0x85, 0x2028, 0x2029, LINE_MARKER})
SPACELIKE = frozenset({0x20, 0x09, 0xA0, 0x202F, 0x2007, 0x2009, 0x200A}) | BREAK
# MARKER is a member of both OPENISH and CLOSEISH (modes.md 3.3).
OPENISH = frozenset(
    {
        MARKER,
        0x28,
        0x5B,
        0x7B,
        0xAB,
        0x2018,
        0x201A,
        0x201B,
        0x201C,
        0x201E,
        0x201F,
        0x2039,
        0x2D,
        0x2011,
        0x2013,
        0x2014,
    }
)
CLOSEISH = frozenset(
    {
        MARKER,
        0x29,
        0x5D,
        0x7D,
        0xBB,
        0x2019,
        0x201D,
        0x203A,
        0x2C,
        0x2E,
        0x3B,
        0x3A,
        0x21,
        0x3F,
        0x2026,
        0x2D,
        0x2011,
        0x2013,
        0x2014,
    }
)


def _at(cp: list[int], i: int) -> int:
    if i < 0 or i >= len(cp):
        return NONE
    return cp[i]


def _is_alnum(v: int) -> bool:
    return v != NONE and (is_letter(v) or v in DIGIT)


def scan(cp: list[int], locale_data: dict[str, Any], ctx: RuleContext) -> list[Edit]:
    _veto, preserve = _quote_ambiguity.compute_ambiguous_indices(cp, locale_data)

    edits: list[Edit] = []
    for i, g in enumerate(cp):
        if g != SQ or i in preserve:
            continue
        left = _at(cp, i - 1)
        right = _at(cp, i + 1)

        if left in DIGIT and (right == NONE or not is_letter(right)):
            continue  # case 1: prime guard
        if _is_alnum(left) and _is_alnum(right):
            edits.append(Edit(i, i + 1, [0x2019], RULE_ID))  # case 2: medial
            continue
        if (
            left != NONE
            and is_letter(left)
            and (right == NONE or right in SPACELIKE or right in CLOSEISH)
        ):
            edits.append(Edit(i, i + 1, [0x2019], RULE_ID))  # case 3: trailing
            continue
        if (left == NONE or left in SPACELIKE or left in OPENISH) and _is_alnum(right):
            edits.append(Edit(i, i + 1, [0x2019], RULE_ID))  # case 4: leading
            continue
        # case 5: otherwise, leave alone
    return edits
