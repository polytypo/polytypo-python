"""spec/rules/nbsp.md -- order 70 (last), default on. Ten independent sub-rules (N1-N10),
first-claim-wins by sub-rule order, each computed against the ORIGINAL code-point array (not a
partially-edited one) and merged afterward -- matching the spec's "keyed by the index" framing."""

from __future__ import annotations

from typing import Any

from polytypo._engine.edits import Edit
from polytypo._engine.registry import RuleContext
from polytypo._engine.sentinels import LINE_MARKER, NONE
from polytypo._engine.unicode import is_letter, is_upper, simple_uppercase
from polytypo.errors import POLYTYPO_MALFORMED_LOCALE_DATA, PolytypoError

RULE_ID = "nbsp"

SP = 0x20
NBSP = 0xA0
NNBSP = 0x202F
NOBREAK = frozenset({NBSP, NNBSP})
OTHER_SPACE = frozenset(
    {
        0x2000,
        0x2001,
        0x2002,
        0x2003,
        0x2004,
        0x2005,
        0x2006,
        0x2007,
        0x2008,
        0x2009,
        0x200A,
        0x205F,
        0x3000,
    }
)
# Includes LINE_MARKER: a member of BREAK for every rule everywhere (modes.md 3.2). nbsp's own
# OPENISH/CLOSEISH (brackets + locale quote glyphs, see _openish_closeish) do NOT get MARKER --
# unlike quotes/apostrophe, matching the reference implementation exactly.
BREAK = frozenset({0x0A, 0x0D, 0x0B, 0x0C, 0x85, 0x2028, 0x2029, LINE_MARKER})
SPACELIKE = frozenset({SP, 0x09}) | NOBREAK | OTHER_SPACE | BREAK
DIGIT = frozenset(range(0x30, 0x3A))
DOT = 0x2E
SENTENCE_DASH = frozenset({0x2013, 0x2014})
DASHISH = frozenset({0x2D, 0x2011, 0x2013, 0x2014})


def _at(cp: list[int], i: int) -> int:
    if i < 0 or i >= len(cp):
        return NONE
    return cp[i]


def _is_alnum(v: int) -> bool:
    return v != NONE and (is_letter(v) or v in DIGIT)


def _openish_closeish(locale_data: dict[str, Any]) -> tuple[frozenset[int], frozenset[int]]:
    quotes = locale_data["quotes"]
    openish = {0x28, 0x5B, 0x7B}
    closeish = {0x29, 0x5D, 0x7D}
    for pair in (quotes["primary"], quotes["secondary"]):
        openish.add(ord(pair["open"]))
        closeish.add(ord(pair["close"]))
    return frozenset(openish), frozenset(closeish)


def scan(cp: list[int], locale_data: dict[str, Any], ctx: RuleContext) -> list[Edit]:
    nbsp_data = locale_data["nbsp"]
    before_punct = {ord(c) for c in nbsp_data["beforePunctuation"]}
    narrow_before_punct = {ord(c) for c in nbsp_data["narrowBeforePunctuation"]}
    if before_punct & narrow_before_punct:
        raise PolytypoError(
            POLYTYPO_MALFORMED_LOCALE_DATA,
            "nbsp.beforePunctuation and nbsp.narrowBeforePunctuation must be disjoint",
        )
    openish, closeish = _openish_closeish(locale_data)

    sub_rule_edits = [
        _n1_before_punctuation(cp, before_punct, narrow_before_punct, openish, closeish),
        _n2_narrow_before_punctuation(cp, before_punct, narrow_before_punct, openish, closeish),
        _n3_after_short_words(cp, nbsp_data["afterShortWords"], openish),
        _n4_abbreviations(cp, nbsp_data["abbreviations"]),
        _n5_before_units(cp, nbsp_data["beforeUnits"]),
        _n6_after_symbols(cp, nbsp_data["afterSymbols"]),
        _n7_initial_binding(cp, nbsp_data["initialBinding"], openish),
        _n8_quotes_inner_space(cp, locale_data["quotes"]),
        _n9_before_number(cp, nbsp_data["beforeNumber"], openish),
        _n10_before_word(cp, nbsp_data["beforeWord"], openish, nbsp_data["initialBinding"]),
    ]

    claimed: set[int] = set()
    result: list[Edit] = []
    for edits in sub_rule_edits:
        for edit in edits:
            if edit.start in claimed:
                continue
            claimed.add(edit.start)
            result.append(edit)
    result.sort(key=lambda e: e.start)
    return result


# ---------------------------------------------------------------- N1 / N2


def _before_punctuation_common(
    cp: list[int],
    target_set: set[int],
    other_set: set[int],
    openish: frozenset[int],
    closeish: frozenset[int],
    already_correct: int,
    convert_from: frozenset[int],
    insert_target: int,
) -> list[Edit]:
    n = len(cp)
    edits: list[Edit] = []
    for i in range(n):
        if cp[i] not in target_set:
            continue
        # Run guard.
        prev = _at(cp, i - 1)
        if prev in target_set or prev in other_set:
            continue
        # Right-context guard. nbsp.md's own CLOSEISH (brackets + locale close glyphs), NOT
        # quotes.md's broader CLOSEISH -- the two documents define the class name differently.
        after = _at(cp, i + 1)
        if (
            after != NONE
            and after not in SPACELIKE
            and after not in closeish
            and after != 0x2026
            and after not in target_set
            and after not in other_set
        ):
            continue
        # Quote-glyph guard.
        if (prev in SPACELIKE and _at(cp, i - 2) in openish) or prev in openish:
            continue
        left = prev
        if left == already_correct:
            continue  # already correct
        if left == SP or left in convert_from:
            edits.append(Edit(i - 1, i, [insert_target], RULE_ID))
        elif left in OTHER_SPACE or left == NONE or left in BREAK or left == 0x09:
            continue
        else:
            edits.append(Edit(i, i, [insert_target], RULE_ID))
    return edits


def _n1_before_punctuation(
    cp: list[int],
    before_punct: set[int],
    narrow_before_punct: set[int],
    openish: frozenset[int],
    closeish: frozenset[int],
) -> list[Edit]:
    return _before_punctuation_common(
        cp, before_punct, narrow_before_punct, openish, closeish, NBSP, frozenset({SP, NNBSP}), NBSP
    )


def _n2_narrow_before_punctuation(
    cp: list[int],
    before_punct: set[int],
    narrow_before_punct: set[int],
    openish: frozenset[int],
    closeish: frozenset[int],
) -> list[Edit]:
    return _before_punctuation_common(
        cp,
        narrow_before_punct,
        before_punct,
        openish,
        closeish,
        NNBSP,
        frozenset({SP, NBSP}),
        NNBSP,
    )


# ---------------------------------------------------------------- N3


def _n3_after_short_words(cp: list[int], words: list[str], openish: frozenset[int]) -> list[Edit]:
    patterns = [[ord(c) for c in w] for w in words]
    n = len(cp)
    edits: list[Edit] = []
    a = 0
    while a < n:
        best: list[int] | None = None
        for pat in patterns:
            if _matches_first_char_lenient(cp, a, pat) and (best is None or len(pat) > len(best)):
                best = pat
        if best is None:
            a += 1
            continue
        k = len(best)
        left = _at(cp, a - 1)
        if not (left == NONE or left in SPACELIKE or left in openish or left in SENTENCE_DASH):
            a += 1
            continue
        right = _at(cp, a + k)
        if right == NONE or right not in (SP, NBSP):
            a += 1
            continue
        following = _at(cp, a + k + 1)
        if following == NONE or not (_is_alnum(following) or following in openish):
            a += 1
            continue
        if right == NBSP:
            pass  # already correct, claims nothing further but position is "seen"
        else:
            edits.append(Edit(a + k, a + k + 1, [NBSP], RULE_ID))
        a += k
    return edits


def _matches_first_char_lenient(cp: list[int], a: int, pattern: list[int]) -> bool:
    n = len(cp)
    for j, w in enumerate(pattern):
        idx = a + j
        if idx >= n:
            return False
        c = cp[idx]
        if j == 0:
            if c != w and c != simple_uppercase(w):
                return False
        else:
            if c != w:
                return False
    return True


# ---------------------------------------------------------------- N4


def _n4_abbreviations(cp: list[int], abbreviations: list[str]) -> list[Edit]:
    patterns = [[ord(c) for c in s] for s in abbreviations]
    n = len(cp)
    edits: list[Edit] = []
    a = 0
    while a < n:
        best: list[int] | None = None
        for pat in patterns:
            if _matches_space_lenient(cp, a, pat) and (best is None or len(pat) > len(best)):
                best = pat
        if best is None:
            a += 1
            continue
        k = len(best)
        if _is_alnum(_at(cp, a - 1)) or _is_alnum(_at(cp, a + k)):
            a += 1
            continue
        for j, w in enumerate(best):
            if w == SP and cp[a + j] != NBSP:
                edits.append(Edit(a + j, a + j + 1, [NBSP], RULE_ID))
        a += k
    return edits


def _matches_space_lenient(cp: list[int], a: int, pattern: list[int]) -> bool:
    n = len(cp)
    for j, w in enumerate(pattern):
        idx = a + j
        if idx >= n:
            return False
        c = cp[idx]
        if w == SP:
            if c != SP and c not in NOBREAK:
                return False
        else:
            if c != w:
                return False
    return True


# ---------------------------------------------------------------- N5


def _n5_before_units(cp: list[int], units: list[str]) -> list[Edit]:
    patterns = [[ord(c) for c in u] for u in units]
    n = len(cp)
    edits: list[Edit] = []
    a = 0
    while a < n:
        best: list[int] | None = None
        for pat in patterns:
            if _matches_exact(cp, a, pat) and (best is None or len(pat) > len(best)):
                best = pat
        if best is None:
            a += 1
            continue
        k = len(best)
        right = _at(cp, a + k)
        if _is_alnum(right):
            a += 1
            continue
        left = _at(cp, a - 1)
        if left not in (SP, NBSP):
            a += 1
            continue
        if _at(cp, a - 2) not in DIGIT:
            a += 1
            continue
        b = a - 2
        while b > 0 and cp[b - 1] in DIGIT:
            b -= 1
        if _at(cp, b - 1) != NONE and is_letter(_at(cp, b - 1)):
            a += 1
            continue
        if left != NBSP:
            edits.append(Edit(a - 1, a, [NBSP], RULE_ID))
        a += k
    return edits


def _matches_exact(cp: list[int], a: int, pattern: list[int]) -> bool:
    n = len(cp)
    if a + len(pattern) > n:
        return False
    return cp[a : a + len(pattern)] == pattern


# ---------------------------------------------------------------- N6


def _n6_after_symbols(cp: list[int], symbols: list[str]) -> list[Edit]:
    patterns = [[ord(c) for c in s] for s in symbols]
    n = len(cp)
    edits: list[Edit] = []
    a = 0
    while a < n:
        best: list[int] | None = None
        for pat in patterns:
            if _matches_exact(cp, a, pat) and (best is None or len(pat) > len(best)):
                best = pat
        if best is None:
            a += 1
            continue
        k = len(best)
        if _is_alnum(_at(cp, a - 1)):
            a += 1
            continue
        right = _at(cp, a + k)
        if right not in (SP, NBSP):
            a += 1
            continue
        if _at(cp, a + k + 1) not in DIGIT:
            a += 1
            continue
        if right != NBSP:
            edits.append(Edit(a + k, a + k + 1, [NBSP], RULE_ID))
        a += k
    return edits


# ---------------------------------------------------------------- N7


def _is_initial(cp: list[int], p: int, openish: frozenset[int]) -> bool:
    v = _at(cp, p)
    if v == NONE or not is_upper(v):
        return False
    if _at(cp, p + 1) != DOT:
        return False
    left = _at(cp, p - 1)
    return left == NONE or left in SPACELIKE or left in openish


def _n7_initial_binding(cp: list[int], mode: str, openish: frozenset[int]) -> list[Edit]:
    if mode == "none":
        return []
    n = len(cp)
    edits: list[Edit] = []
    for q in range(n):
        if cp[q] not in (SP, NBSP):
            continue
        # C1: initial on the left.
        if cp[q] in (SP, NBSP) and _at(cp, q - 1) == DOT:
            p = q - 2
            if _is_initial(cp, p, openish):
                right = _at(cp, q + 1)
                # C1-a guard: lower-case abbreviation tail.
                if right != NONE and is_upper(right) and not _c1a_blocks(cp, p):
                    between_initials = _is_initial(cp, q + 1, openish)
                    eligible = between_initials or (
                        mode == "single" or (mode == "chain" and _chain_confirmed(cp, p, openish))
                    )
                    if eligible:
                        if cp[q] != NBSP:
                            edits.append(Edit(q, q + 1, [NBSP], RULE_ID))
                        continue
        # C2: two initials on the right.
        left = _at(cp, q - 1)
        c2 = (
            left != NONE
            and is_letter(left)
            and _is_initial(cp, q + 1, openish)
            and _at(cp, q + 3) in (SP, NBSP)
            and _is_initial(cp, q + 4, openish)
        )
        if c2 and cp[q] != NBSP:
            edits.append(Edit(q, q + 1, [NBSP], RULE_ID))
    return edits


def _c1a_blocks(cp: list[int], p: int) -> bool:
    left1 = _at(cp, p - 1)
    if left1 not in SPACELIKE:
        return False
    if _at(cp, p - 2) != DOT:
        return False
    letter = _at(cp, p - 3)
    return letter != NONE and is_letter(letter) and not is_upper(letter)


def _chain_confirmed(cp: list[int], p: int, openish: frozenset[int]) -> bool:
    left = _at(cp, p - 1)
    if left not in (SP, NBSP):
        return False
    if _at(cp, p - 2) != DOT:
        return False
    return _is_initial(cp, p - 3, openish)


# ---------------------------------------------------------------- N8


def _n8_quotes_inner_space(cp: list[int], quotes_data: dict[str, Any]) -> list[Edit]:
    edits: list[Edit] = []
    n = len(cp)
    for pair_key in ("primary", "secondary"):
        pair = quotes_data[pair_key]
        inner = pair["innerSpace"]
        if inner == "none":
            continue
        target = NBSP if inner == "nbsp" else NNBSP
        open_glyph = ord(pair["open"])
        close_glyph = ord(pair["close"])
        if open_glyph == close_glyph:
            continue

        for o in range(n):
            if cp[o] != open_glyph:
                continue
            nxt = _at(cp, o + 1)
            if nxt == target:
                continue
            elif nxt == SP or nxt in NOBREAK:
                edits.append(Edit(o + 1, o + 2, [target], RULE_ID))
            elif nxt == NONE or nxt in BREAK:
                continue
            else:
                edits.append(Edit(o + 1, o + 1, [target], RULE_ID))

        for c in range(n):
            if cp[c] != close_glyph:
                continue
            prev = _at(cp, c - 1)
            if prev == target:
                continue
            elif prev == SP or prev in NOBREAK:
                edits.append(Edit(c - 1, c, [target], RULE_ID))
            elif prev == NONE or prev in BREAK:
                continue
            else:
                edits.append(Edit(c, c, [target], RULE_ID))
    return edits


# ---------------------------------------------------------------- N9


def _n9_before_number(cp: list[int], entries: list[str], openish: frozenset[int]) -> list[Edit]:
    patterns = [[ord(c) for c in s] for s in entries]
    n = len(cp)
    edits: list[Edit] = []
    a = 0
    while a < n:
        best: list[int] | None = None
        for pat in patterns:
            if _matches_exact(cp, a, pat) and (best is None or len(pat) > len(best)):
                best = pat
        if best is None:
            a += 1
            continue
        k = len(best)
        left = _at(cp, a - 1)
        if not (left == NONE or left in SPACELIKE or left in openish or left in SENTENCE_DASH):
            a += 1
            continue
        sep = _at(cp, a + k)
        if sep not in (SP, NBSP):
            a += 1
            continue
        if _at(cp, a + k + 1) in SPACELIKE:
            a += 1
            continue
        if _at(cp, a + k + 1) not in DIGIT:
            a += 1
            continue
        if sep != NBSP:
            edits.append(Edit(a + k, a + k + 1, [NBSP], RULE_ID))
        a += k
    return edits


# ---------------------------------------------------------------- N10


def _n10_before_word(
    cp: list[int], entries: list[str], openish: frozenset[int], initial_binding: str
) -> list[Edit]:
    patterns = [[ord(c) for c in s] for s in entries]
    n = len(cp)
    edits: list[Edit] = []
    a = 0
    while a < n:
        best: list[int] | None = None
        for pat in patterns:
            if _matches_exact(cp, a, pat) and (best is None or len(pat) > len(best)):
                best = pat
        if best is None:
            a += 1
            continue
        k = len(best)
        left = _at(cp, a - 1)
        if not (left == NONE or left in SPACELIKE or left in openish or left in SENTENCE_DASH):
            a += 1
            continue
        sep = _at(cp, a + k)
        if sep not in (SP, NBSP):
            a += 1
            continue
        if _at(cp, a + k + 1) in SPACELIKE:
            a += 1
            continue
        # G-D: initial-collision guard.
        if initial_binding != "none" and k == 2 and is_upper(best[0]) and best[1] == DOT:
            a += 1
            continue
        following = _at(cp, a + k + 1)
        if following == NONE or not is_letter(following):
            a += 1
            continue
        # G-B: line-boundary guard.
        if sep in BREAK:
            a += 1
            continue
        if sep != NBSP:
            edits.append(Edit(a + k, a + k + 1, [NBSP], RULE_ID))
        a += k
    return edits
