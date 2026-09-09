"""The two decline-only predicates `quotes` reads (quotes.md 3.2, "Listed elision veto" and
"Universal medial-`n` elision veto"). Both have the same outcome: the marks survive pass 2
unmatched and `apostrophe` converts each by its own case ladder, giving `rock 'n' roll` ->
`rock ’n’ roll`. Only `quotes` consumes this module -- spec 0.5.0 had `apostrophe` consume it
too, through a preserve set withdrawn in 1.1.0 (apostrophe.md 3.4). Mirrors polytypo-js's
src/rules/quote-ambiguity.ts."""

from __future__ import annotations

from typing import Any

from polytypo._engine.sentinels import NONE
from polytypo._engine.unicode import is_letter

NARROW = frozenset({0x27, 0x2018, 0x2019, 0x201A, 0x201B, 0x2039, 0x203A})  # both vetoes' trigger
# class -- ANY NARROW mark, curly or straight. For the universal medial-n veto this is an
# IDEMPOTENCY obligation, not a preference: its marks are converted to U+2019 by `apostrophe`, so
# a straight-ASCII-only predicate would not recognise its own output and pass 2 would pair
# `rock ’n’ roll` as an ordinary NARROW quotation on the next run -- measured as `rock «n» roll`
# in ru and `rock ”n” roll` in fi.
LOWER_N = 0x6E  # quotes.md 3.2 -- the one code point the universal veto's span may enclose,
UPPER_N = 0x4E  # in either case
DIGIT = frozenset(range(0x30, 0x3A))
INLINE_SPACE = frozenset({0x20, 0x09, 0xA0, 0x202F, 0x2007, 0x2009, 0x200A})


def _at(cp: list[int], i: int) -> int:
    if i < 0 or i >= len(cp):
        return NONE
    return cp[i]


def _is_word_boundary(v: int) -> bool:
    return v == NONE or not (is_letter(v) or v in DIGIT)


def _word_ending_at(cp: list[int], last_idx: int) -> tuple[int, int] | None:
    """If cp[last_idx] is a LETTER, returns (start_idx, end_idx_inclusive) of the maximal
    LETTER run ending there, provided its outer (left) boundary is legal. Else None."""
    if last_idx < 0 or last_idx >= len(cp) or not is_letter(cp[last_idx]):
        return None
    start = last_idx
    while start > 0 and is_letter(cp[start - 1]):
        start -= 1
    outer = _at(cp, start - 1)
    if not _is_word_boundary(outer):
        return None
    return start, last_idx


def _word_starting_at(cp: list[int], first_idx: int) -> tuple[int, int] | None:
    if first_idx < 0 or first_idx >= len(cp) or not is_letter(cp[first_idx]):
        return None
    end = first_idx
    n = len(cp)
    while end < n - 1 and is_letter(cp[end + 1]):
        end += 1
    outer = _at(cp, end + 1)
    if not _is_word_boundary(outer):
        return None
    return first_idx, end


def _word_matches(cp: list[int], start: int, end: int, pattern: str) -> bool:
    """Exact match except the first code point, which folds ASCII A-Z to a-z on both sides."""
    if end - start + 1 != len(pattern):
        return False
    for offset, pch in enumerate(pattern):
        cp_val = cp[start + offset]
        pat_val = ord(pch)
        if offset == 0:
            cp_folded = cp_val + 32 if 0x41 <= cp_val <= 0x5A else cp_val
            pat_folded = pat_val + 32 if 0x41 <= pat_val <= 0x5A else pat_val
            if cp_folded != pat_folded:
                return False
        else:
            if cp_val != pat_val:
                return False
    return True


def compute_ambiguous_indices(cp: list[int], locale_data: dict[str, Any]) -> set[int]:
    """Every index that must have both quote capabilities forced false in `quotes`' own pass 1 --
    the union of the listed-idiom matches and the universal medial-n matches.

    The union is computed rather than assumed: an idiom's `elided` field is not required to be
    the single `n` the universal veto matches.
    """
    n = len(cp)
    idiom_indices: set[int] = set()
    idioms = locale_data.get("quotes", {}).get("elisionIdioms", [])

    for i in range(n):
        if cp[i] not in NARROW:
            continue
        for idiom in idioms:
            left, elided, right = idiom["left"], idiom["elided"], idiom["right"]
            k = len(elided)
            span_start = i + 1
            span_end = span_start + k
            if span_end >= n:
                continue
            span = cp[span_start:span_end]
            # A marker never matches a literal (modes.md 3.3): guard before chr(), since a
            # marker is a negative sentinel, not a valid code point.
            if any(c < 0 for c in span) or [chr(c) for c in span] != list(elided):
                continue
            j = span_end
            if cp[j] not in NARROW:
                continue
            if _at(cp, i - 1) not in INLINE_SPACE:
                continue
            left_word = _word_ending_at(cp, i - 2)
            if left_word is None or not _word_matches(cp, left_word[0], left_word[1], left):
                continue
            if j + 1 >= n or cp[j + 1] not in INLINE_SPACE:
                continue
            right_word = _word_starting_at(cp, j + 2)
            if right_word is None or not _word_matches(cp, right_word[0], right_word[1], right):
                continue
            idiom_indices.add(i)
            idiom_indices.add(j)

    medial_n_indices: set[int] = set()
    for i in range(n):
        if cp[i] not in NARROW:
            continue
        if _at(cp, i + 1) not in (LOWER_N, UPPER_N):
            continue
        j = i + 2
        if _at(cp, j) not in NARROW:
            continue
        if _at(cp, i - 1) not in INLINE_SPACE:
            continue
        if _at(cp, j + 1) not in INLINE_SPACE:
            continue
        medial_n_indices.add(i)
        medial_n_indices.add(j)

    return idiom_indices | medial_n_indices
