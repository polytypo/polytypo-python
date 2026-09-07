"""spec/rules/hyphen.md -- order 35, default on.
Locale data: hyphen.{prefixes,suffixes,compounds}."""

from __future__ import annotations

from typing import Any

from polytypo._engine.edits import Edit
from polytypo._engine.registry import RuleContext
from polytypo._engine.sentinels import NONE
from polytypo._engine.unicode import is_letter, simple_uppercase
from polytypo.errors import POLYTYPO_MALFORMED_LOCALE_DATA, PolytypoError

RULE_ID = "hyphen"

HY = 0x2D
NBHY = 0x2011
HYPHENISH = frozenset({HY, NBHY})
DIGIT = frozenset(range(0x30, 0x3A))


def _at(cp: list[int], i: int) -> int:
    if i < 0 or i >= len(cp):
        return NONE
    return cp[i]


def _is_wordish(v: int) -> bool:
    return v != NONE and (is_letter(v) or v in DIGIT or v in HYPHENISH)


def _matches_at(cp: list[int], a: int, pattern: list[int]) -> bool:
    n = len(cp)
    for j, w in enumerate(pattern):
        idx = a + j
        if idx >= n:
            return False
        c = cp[idx]
        if w == HY:
            if c not in HYPHENISH:
                return False
        elif j == 0 and is_letter(w):
            if c != w and c != simple_uppercase(w):
                return False
        else:
            if c != w:
                return False
    return True


def _validate_entry(entry: list[int]) -> None:
    if HY not in entry:
        raise PolytypoError(
            POLYTYPO_MALFORMED_LOCALE_DATA,
            f"hyphen list entry {entry!r} contains no U+002D to convert",
        )


def scan(cp: list[int], locale_data: dict[str, Any], ctx: RuleContext) -> list[Edit]:
    hyphen_data = locale_data["hyphen"]
    compounds = [[ord(c) for c in w] for w in hyphen_data["compounds"]]
    prefixes = [[ord(c) for c in w] for w in hyphen_data["prefixes"]]
    suffixes = [[ord(c) for c in w] for w in hyphen_data["suffixes"]]
    for group in (compounds, prefixes, suffixes):
        for entry in group:
            _validate_entry(entry)

    if not compounds and not prefixes and not suffixes:
        return []

    edits: list[Edit] = []
    n = len(cp)
    a = 0
    while a < n:
        candidate = _select_candidate(cp, a, compounds, prefixes, suffixes)
        if candidate is None:
            a += 1
            continue
        kind, pattern = candidate
        k = len(pattern)
        if kind == "compound" and _compound_guards_pass(cp, a, k):
            _emit_compound(cp, a, pattern, edits)
            a += k
            continue
        if kind == "prefix" and _prefix_guards_pass(cp, a, k):
            _emit_single(cp, a + k - 1, edits)
            a += k
            continue
        if kind == "suffix" and _suffix_guards_pass(cp, a, k):
            _emit_single(cp, a, edits)
            a += k
            continue
        a += 1
    return edits


def _select_candidate(
    cp: list[int],
    a: int,
    compounds: list[list[int]],
    prefixes: list[list[int]],
    suffixes: list[list[int]],
) -> tuple[str, list[int]] | None:
    """The longest entry matching at `a` across all three lists, ties broken
    compounds > prefixes > suffixes."""
    best: tuple[str, list[int]] | None = None
    for kind, group in (("compound", compounds), ("prefix", prefixes), ("suffix", suffixes)):
        for entry in group:
            if _matches_at(cp, a, entry) and (best is None or len(entry) > len(best[1])):
                best = (kind, entry)
    return best


def _compound_guards_pass(cp: list[int], a: int, k: int) -> bool:
    return not (_is_wordish(_at(cp, a - 1)) or _is_wordish(_at(cp, a + k)))


def _prefix_guards_pass(cp: list[int], a: int, k: int) -> bool:
    if _is_wordish(_at(cp, a - 1)):
        return False
    right = _at(cp, a + k)
    return right != NONE and is_letter(right)


def _suffix_guards_pass(cp: list[int], a: int, k: int) -> bool:
    left = _at(cp, a - 1)
    if left == NONE or not is_letter(left):
        return False
    return not _is_wordish(_at(cp, a + k))


def _emit_compound(cp: list[int], a: int, pattern: list[int], edits: list[Edit]) -> None:
    for j, w in enumerate(pattern):
        if w == HY and cp[a + j] != NBHY:
            edits.append(Edit(a + j, a + j + 1, [NBHY], RULE_ID))


def _emit_single(cp: list[int], idx: int, edits: list[Edit]) -> None:
    if cp[idx] != NBHY:
        edits.append(Edit(idx, idx + 1, [NBHY], RULE_ID))
