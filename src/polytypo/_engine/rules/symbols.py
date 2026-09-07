"""spec/rules/symbols.md -- order 60, default on, no locale data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polytypo._engine.edits import Edit
from polytypo._engine.registry import RuleContext
from polytypo._engine.sentinels import NONE
from polytypo._engine.unicode import is_letter

RULE_ID = "symbols"

SPACE = 0x20
NOBREAK_SPACE = frozenset({0xA0, 0x202F})
SPACE_LIKE = frozenset({SPACE}) | NOBREAK_SPACE
MUL_LETTER = frozenset({0x78, 0x58, 0x445, 0x425})  # x X х Х
DIGITS = frozenset(range(0x30, 0x3A))

_TRADEMARK_ROWS: list[tuple[list[int], int, bool]] = [
    # (literal code points, replacement, is_cr_row)
    ([0x28, 0x74, 0x6D, 0x29], 0x2122, False),  # (tm)
    ([0x28, 0x54, 0x4D, 0x29], 0x2122, False),  # (TM)
    ([0x28, 0x54, 0x6D, 0x29], 0x2122, False),  # (Tm)
    ([0x28, 0x74, 0x4D, 0x29], 0x2122, False),  # (tM)
    ([0x28, 0x63, 0x29], 0xA9, True),  # (c)
    ([0x28, 0x43, 0x29], 0xA9, True),  # (C)
    ([0x28, 0x72, 0x29], 0xAE, True),  # (r)
    ([0x28, 0x52, 0x29], 0xAE, True),  # (R)
]

_CONVERTED_SYMBOLS = frozenset({0xA9, 0xAE, 0x2122})


def _at(cp: list[int], i: int) -> int:
    if i < 0 or i >= len(cp):
        return NONE
    return cp[i]


def _is_digit(v: int) -> bool:
    return v in DIGITS


def _is_alnum(v: int) -> bool:
    return v != NONE and (_is_digit(v) or is_letter(v))


def scan(cp: list[int], locale_data: dict[str, Any], ctx: RuleContext) -> list[Edit]:
    edits: list[Edit] = []
    n = len(cp)
    i = 0
    while i < n:
        if cp[i] == 0x28:
            consumed = _try_trademark(cp, i, edits)
            if consumed:
                i += consumed
                continue
        if _is_digit(cp[i]) and (i == 0 or not _is_digit(cp[i - 1])):
            consumed = _try_multiplication_chain(cp, i, edits)
            if consumed:
                i = consumed
                continue
        if (
            cp[i] == 0x2B
            and _at(cp, i + 1) == 0x2F
            and _at(cp, i + 2) == 0x2D
            and _try_plus_minus(cp, i, edits)
        ):
            i += 3
            continue
        i += 1
    return edits


def _try_trademark(cp: list[int], i: int, edits: list[Edit]) -> int:
    n = len(cp)
    for literal, replacement, is_cr_row in _TRADEMARK_ROWS:
        length = len(literal)
        if i + length > n:
            continue
        if cp[i : i + length] != literal:
            continue
        before = _at(cp, i - 1)
        after = _at(cp, i + length)
        if is_cr_row and (
            _is_alnum(before) or before in (0x29, 0x5D) or before in _CONVERTED_SYMBOLS
        ):
            return 0
        if after != NONE and _is_alnum(after):
            return 0
        if before == 0x28:
            return 0
        edits.append(Edit(i, i + length, [replacement], RULE_ID))
        return length
    return 0


@dataclass
class _MulLink:
    letter_idx: int
    left_space: int | None
    right_space: int | None
    digit_end: int


def _try_multiplication_chain(cp: list[int], a: int, edits: list[Edit]) -> int:
    n = len(cp)
    b = a
    while b < n and _is_digit(cp[b]):
        b += 1
    # b is now one past the first digit run. Try to read links.
    links: list[_MulLink] = []
    pos = b
    while True:
        j = pos
        left_space = None
        if j < n and cp[j] in SPACE_LIKE:
            left_space = cp[j]
            j += 1
        if j >= n or cp[j] not in MUL_LETTER:
            break
        letter_idx = j
        j += 1
        right_space = None
        if j < n and cp[j] in SPACE_LIKE:
            right_space = cp[j]
            j += 1
        digit_start = j
        while j < n and _is_digit(cp[j]):
            j += 1
        if j == digit_start:
            break  # no digit run after the letter -- link incomplete
        links.append(_MulLink(letter_idx, left_space, right_space, j))
        pos = j

    if not links:
        return 0

    b_end = links[-1].digit_end  # end of the whole chain, exclusive

    # Guard M1: spacing symmetric per link, and uniform across links.
    sp: int | None = None
    for link in links:
        has_left = link.left_space is not None
        has_right = link.right_space is not None
        if has_left != has_right:
            return 0
        this_sp = 1 if has_left else 0
        if sp is None:
            sp = this_sp
        elif sp != this_sp:
            return 0
    assert sp is not None

    # Guard M2: chain must not start after a LETTER.
    before = _at(cp, a - 1)
    if before != NONE and is_letter(before):
        return 0
    # Guard M3: chain must not end before a LETTER.
    after = _at(cp, b_end)
    if after != NONE and is_letter(after):
        return 0
    # Guard M4: hex literal veto -- sp==0, first link's letter is lowercase x, and the first
    # (pre-first-link) digit run is the single code point "0".
    if sp == 0:
        first = links[0]
        if cp[first.letter_idx] == 0x78 and (b - a) == 1 and cp[a] == 0x30:
            return 0

    for link in links:
        j = link.letter_idx
        if sp == 0:
            edits.append(Edit(j, j + 1, [0xD7], RULE_ID))
        else:
            left_sp = cp[j - 1]
            right_sp = cp[j + 1]
            replacement = [left_sp, 0xD7, right_sp]
            if cp[j - 1 : j + 2] == replacement:
                continue
            edits.append(Edit(j - 1, j + 2, replacement, RULE_ID))
    return b_end


def _try_plus_minus(cp: list[int], i: int, edits: list[Edit]) -> bool:
    before = _at(cp, i - 1)
    if before == 0x5B:
        return False
    j = i + 3
    if _at(cp, j) == SPACE:
        j += 1
    if not _is_digit(_at(cp, j)):
        return False
    edits.append(Edit(i, i + 3, [0xB1], RULE_ID))
    return True
