"""spec/rules/spaces.md -- order 10, default on, no locale data."""

from __future__ import annotations

from typing import Any

from polytypo._engine.edits import Edit
from polytypo._engine.registry import RuleContext
from polytypo._engine.sentinels import LINE_MARKER, NONE, is_marker
from polytypo._engine.unicode import is_letter

RULE_ID = "spaces"

SPACE = 0x20
# Includes LINE_MARKER: a member of BREAK for every rule everywhere (modes.md 3.2).
BREAK = frozenset({0x0A, 0x0D, 0x0B, 0x0C, 0x85, 0x2028, 0x2029, LINE_MARKER})
STRIP_BEFORE = frozenset({0x2C, 0x2E, 0x3B, 0x3A, 0x21, 0x3F})
DOTLIKE = frozenset({0x2E, 0x2026})
OPEN_BRACKET = frozenset({0x28, 0x5B, 0x7B})
CLOSE_BRACKET = frozenset({0x29, 0x5D, 0x7D})
_BRACKET_PAIR = {0x28: 0x29, 0x5B: 0x5D, 0x7B: 0x7D}
EMOTICON_EYE = frozenset({0x3A, 0x3B})
EMOTICON_NOSE = frozenset({0x2D, 0x5E})
EMOTICON_MOUTH = frozenset(
    {0x28, 0x29, 0x5B, 0x5D, 0x44, 0x64, 0x50, 0x70, 0x4F, 0x6F, 0x2F, 0x5C, 0x7C, 0x2A}
)


def _at(cp: list[int], i: int) -> int:
    if i < 0 or i >= len(cp):
        return NONE
    return cp[i]


def _is_break_or_none(value: int) -> bool:
    return value == NONE or value in BREAK


def _is_ascii_digit(value: int) -> bool:
    return 0x30 <= value <= 0x39


def _emoticon_eye_side_fires(cp: list[int], e: int) -> bool:
    """cp[e] is EMOTICON_EYE (the run's `right`). Walk forward through an optional nose to a
    mouth; if what follows the mouth is a LETTER or ASCII digit, the guard does not fire."""
    i = e + 1
    if _at(cp, i) in EMOTICON_NOSE:
        i += 1
    if _at(cp, i) not in EMOTICON_MOUTH:
        return False
    after = _at(cp, i + 1)
    return after == NONE or not (is_letter(after) or _is_ascii_digit(after))


def _emoticon_mouth_side_fires(cp: list[int], s: int) -> bool:
    """cp[s-1] is EMOTICON_MOUTH (the run's `left`). Walk backward through an optional nose to
    an eye."""
    j = s - 2
    if _at(cp, j) in EMOTICON_NOSE:
        j -= 1
    return _at(cp, j) in EMOTICON_EYE


def scan(cp: list[int], locale_data: dict[str, Any], ctx: RuleContext) -> list[Edit]:
    edits: list[Edit] = []
    n = len(cp)
    i = 0
    while i < n:
        if cp[i] != SPACE:
            i += 1
            continue
        s = i
        e = s
        while e < n and cp[e] == SPACE:
            e += 1
        k = e - s

        left = _at(cp, s - 1)
        right = _at(cp, e)

        # Boundary guard (3.2 step 4): a span boundary marker counts as NONE here, the one
        # place in the spec a marker is not opaque content -- spaces.md 3.2 step 4.
        left_is_none = left == NONE or is_marker(left) or left in BREAK
        right_is_none = right == NONE or is_marker(right) or right in BREAK
        if left_is_none or right_is_none:
            i = e
            continue

        # 3.2 step 5: decide the replacement length in one step.
        empty_bracket_guard = left in OPEN_BRACKET and _BRACKET_PAIR[left] == right
        if empty_bracket_guard:
            replacement_len = 1
        elif (
            (left in OPEN_BRACKET and not _emoticon_mouth_side_fires(cp, s))
            or right in CLOSE_BRACKET
            or (
                right in STRIP_BEFORE
                and _lone_dot_condition_holds(cp, e, right)
                and not (right in EMOTICON_EYE and _emoticon_eye_side_fires(cp, e))
            )
        ):
            replacement_len = 0
        else:
            replacement_len = 1

        if replacement_len != k:
            replacement = [SPACE] if replacement_len == 1 else []
            edits.append(Edit(s, e, replacement, RULE_ID))
        i = e
    return edits


def _lone_dot_condition_holds(cp: list[int], e: int, right: int) -> bool:
    """3.4: if right is U+002E, replacement length may be 0 only if the maximal DOTLIKE run
    starting at e has length exactly 1. Any other STRIP-BEFORE member is unaffected."""
    if right != 0x2E:
        return True
    j = e
    n = len(cp)
    run_len = 0
    while j < n and cp[j] in DOTLIKE:
        run_len += 1
        j += 1
    return run_len == 1
