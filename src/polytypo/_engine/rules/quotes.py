"""spec/rules/quotes.md -- order 40, default on. Five passes plus emit; see the module docstring
in _quote_ambiguity.py for the predicate shared with `apostrophe`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polytypo._engine.edits import Edit
from polytypo._engine.registry import RuleContext
from polytypo._engine.rules import _quote_ambiguity
from polytypo._engine.sentinels import LINE_MARKER, MARKER, NONE
from polytypo._engine.unicode import is_letter

RULE_ID = "quotes"

WIDE = frozenset({0x22, 0xAB, 0xBB, 0x201C, 0x201D, 0x201E, 0x201F, 0x301D, 0x301E, 0x301F})
NARROW = frozenset({0x27, 0x2018, 0x2019, 0x201A, 0x201B, 0x2039, 0x203A})
QUOTEMARK = WIDE | NARROW
DIGIT = frozenset(range(0x30, 0x3A))
BREAK = frozenset({0x0A, 0x0D, 0x0B, 0x0C, 0x85, 0x2028, 0x2029, LINE_MARKER})
INLINE_SPACE = frozenset({0x20, 0x09, 0xA0, 0x202F, 0x2007, 0x2009, 0x200A})
SPACELIKE = INLINE_SPACE | BREAK
# MARKER is a member of both OPENISH and CLOSEISH (modes.md 3.3) -- not "simplified" away,
# since it's what makes a candidate's verdict independent of which quote glyph its neighbour is
# across a span boundary.
OPENISH = frozenset({MARKER, 0x28, 0x5B, 0x7B}) | QUOTEMARK
CLOSEISH = (
    frozenset(
        {MARKER, 0x29, 0x5D, 0x7D, 0x2C, 0x2E, 0x3B, 0x3A, 0x21, 0x3F, 0x2026, 0x2013, 0x2014}
    )
    | QUOTEMARK
)
DASHISH = frozenset({0x2D, 0x2011, 0x2013, 0x2014})
DELETE_LANDING = QUOTEMARK  # ALNUM handled separately via is_letter/DIGIT check


def _at(cp: list[int], i: int) -> int:
    if i < 0 or i >= len(cp):
        return NONE
    return cp[i]


def _is_alnum(v: int) -> bool:
    return v != NONE and (is_letter(v) or v in DIGIT)


def _is_delete_landing(v: int) -> bool:
    return _is_alnum(v) or v in QUOTEMARK


@dataclass
class Candidate:
    index: int
    width: str  # "WIDE" or "NARROW"
    can_open: bool
    can_close: bool


def _locale_skip_sets(locale_data: dict[str, Any]) -> tuple[set[int], set[int]]:
    space_right: set[int] = set()
    space_left: set[int] = set()
    for pair in (locale_data["quotes"]["primary"], locale_data["quotes"]["secondary"]):
        if pair["innerSpace"] != "none" and pair["open"] != pair["close"]:
            space_right.add(ord(pair["open"]))
            space_left.add(ord(pair["close"]))
    return space_right, space_left


def _skip_left(cp: list[int], i: int) -> int:
    j = i - 1
    while j >= 0 and cp[j] in INLINE_SPACE:
        j -= 1
    return _at(cp, j)


def _skip_right(cp: list[int], i: int) -> int:
    n = len(cp)
    j = i + 1
    while j < n and cp[j] in INLINE_SPACE:
        j += 1
    return _at(cp, j)


def _compute_candidates(cp: list[int], locale_data: dict[str, Any]) -> list[Candidate]:
    space_right, space_left = _locale_skip_sets(locale_data)
    veto_indices = _quote_ambiguity.compute_ambiguous_indices(cp, locale_data)

    candidates: list[Candidate] = []
    for i, g in enumerate(cp):
        if g not in QUOTEMARK:
            continue
        llit = _at(cp, i - 1)
        rlit = _at(cp, i + 1)
        lskip = _skip_left(cp, i)
        rskip = _skip_right(cp, i)

        open_left = lskip if g in space_left else llit
        close_right = rskip if g in space_right else rlit

        open_left_ok = (
            open_left == NONE
            or open_left in SPACELIKE
            or open_left in OPENISH
            or open_left in DASHISH
        )
        can_open = open_left_ok and (
            rskip != NONE
            and rskip not in SPACELIKE
            and (rskip not in CLOSEISH or rskip in QUOTEMARK or rskip == MARKER)
        )
        can_close = (lskip != NONE and lskip not in SPACELIKE) and (
            close_right == NONE
            or close_right in SPACELIKE
            or close_right in CLOSEISH
            or close_right in DASHISH
        )

        if g in NARROW and _is_alnum(llit) and _is_alnum(rlit):
            can_open = False
            can_close = False

        if i in veto_indices:
            can_open = False
            can_close = False

        # V1: same-V1-identity adjacency veto.
        def v1id(v: int) -> int:
            return 0x2019 if v == 0x27 else v

        gap_insertable = g in space_right or g in space_left
        left_vetoed = v1id(llit) == v1id(g) or (
            llit in INLINE_SPACE and v1id(lskip) == v1id(g) and gap_insertable
        )
        right_vetoed = v1id(rlit) == v1id(g) or (
            rlit in INLINE_SPACE and v1id(rskip) == v1id(g) and gap_insertable
        )
        if left_vetoed or right_vetoed:
            can_open = False
            can_close = False

        if can_open or can_close:
            width = "WIDE" if g in WIDE else "NARROW"
            candidates.append(Candidate(i, width, can_open, can_close))
    return candidates


def _vacuous(cp: list[int], a: int, b: int) -> bool:
    return all(cp[k] in INLINE_SPACE for k in range(a + 1, b))


def _pair_candidates(cp: list[int], candidates: list[Candidate]) -> list[tuple[int, int]]:
    stacks: dict[str, list[Candidate]] = {"WIDE": [], "NARROW": []}
    pairs: list[tuple[int, int]] = []
    for c in candidates:
        stack = stacks[c.width]
        if c.can_close and stack and not _vacuous(cp, stack[-1].index, c.index):
            o = stack.pop()
            pairs.append((o.index, c.index))
        elif c.can_open:
            stack.append(c)
    return pairs


def _assign_depths(pairs: list[tuple[int, int]]) -> dict[tuple[int, int], int]:
    depths: dict[tuple[int, int], int] = {}
    for p in pairs:
        depth = 1 + sum(1 for q in pairs if q[0] < p[0] and p[1] < q[1])
        depths[p] = depth
    return depths


def _pair_for_depth(depth: int, locale_data: dict[str, Any]) -> dict[str, Any]:
    quotes = locale_data["quotes"]
    result: dict[str, Any] = quotes["primary"] if depth % 2 == 1 else quotes["secondary"]
    return result


def _render(
    cp: list[int], pairs: list[tuple[int, int]], locale_data: dict[str, Any]
) -> tuple[list[int], dict[int, int]]:
    depths = _assign_depths(pairs)
    glyph_at: dict[int, int] = {}
    delete_spans: list[tuple[int, int]] = []

    for p in pairs:
        open_idx, close_idx = p
        spec = _pair_for_depth(depths[p], locale_data)
        glyph_at[open_idx] = ord(spec["open"])
        glyph_at[close_idx] = ord(spec["close"])
        if spec["innerSpace"] == "none":
            n = len(cp)
            run_start = open_idx + 1
            run_end = run_start
            while run_end < n and cp[run_end] in INLINE_SPACE:
                run_end += 1
            open_run = (run_start, run_end) if run_end > run_start else None
            open_landing = _at(cp, run_end)

            run_end2 = close_idx
            run_start2 = run_end2
            while run_start2 > 0 and cp[run_start2 - 1] in INLINE_SPACE:
                run_start2 -= 1
            close_run = (run_start2, run_end2) if run_end2 > run_start2 else None
            close_landing = _at(cp, run_start2 - 1)

            if open_run is not None and close_run is not None and open_run == close_run:
                open_run = None
                close_run = None
            if open_run is not None and _is_delete_landing(open_landing):
                delete_spans.append(open_run)
            if close_run is not None and _is_delete_landing(close_landing):
                delete_spans.append(close_run)

    delete_set: set[int] = set()
    for s, e in delete_spans:
        delete_set.update(range(s, e))

    out: list[int] = []
    index_map: dict[int, int] = {}
    for i, c in enumerate(cp):
        if i in delete_set:
            continue
        index_map[i] = len(out)
        out.append(glyph_at.get(i, c))
    return out, index_map


def _certify(
    cp: list[int], initial_pairs: list[tuple[int, int]], locale_data: dict[str, Any]
) -> list[tuple[int, int]]:
    a = initial_pairs
    while True:
        if not a:
            return a
        rendered, index_map = _render(cp, a, locale_data)
        b_candidates = _compute_candidates(rendered, locale_data)
        b_pairs = set(_pair_candidates(rendered, b_candidates))
        mapped_a = {(index_map[p[0]], index_map[p[1]]) for p in a}
        if mapped_a == b_pairs:
            return a
        a_prime = [p for p in a if (index_map[p[0]], index_map[p[1]]) in b_pairs]
        if len(a_prime) == len(a):
            worst = max(a, key=lambda p: p[0])
            a = [p for p in a if p != worst]
        else:
            a = a_prime


def scan(cp: list[int], locale_data: dict[str, Any], ctx: RuleContext) -> list[Edit]:
    candidates = _compute_candidates(cp, locale_data)
    pairs = _pair_candidates(cp, candidates)
    accepted = _certify(cp, pairs, locale_data)
    if not accepted:
        return []

    depths = _assign_depths(accepted)
    edits: list[Edit] = []
    for p in accepted:
        open_idx, close_idx = p
        spec = _pair_for_depth(depths[p], locale_data)
        open_glyph = ord(spec["open"])
        close_glyph = ord(spec["close"])
        if cp[open_idx] != open_glyph:
            edits.append(Edit(open_idx, open_idx + 1, [open_glyph], RULE_ID))
        if cp[close_idx] != close_glyph:
            edits.append(Edit(close_idx, close_idx + 1, [close_glyph], RULE_ID))

        if spec["innerSpace"] == "none":
            n = len(cp)
            run_start = open_idx + 1
            run_end = run_start
            while run_end < n and cp[run_end] in INLINE_SPACE:
                run_end += 1
            open_run = (run_start, run_end) if run_end > run_start else None
            open_landing = _at(cp, run_end)

            run_end2 = close_idx
            run_start2 = run_end2
            while run_start2 > 0 and cp[run_start2 - 1] in INLINE_SPACE:
                run_start2 -= 1
            close_run = (run_start2, run_end2) if run_end2 > run_start2 else None
            close_landing = _at(cp, run_start2 - 1)

            if open_run is not None and close_run is not None and open_run == close_run:
                open_run = None
                close_run = None
            if open_run is not None and _is_delete_landing(open_landing):
                edits.append(Edit(open_run[0], open_run[1], [], RULE_ID))
            if close_run is not None and _is_delete_landing(close_landing):
                edits.append(Edit(close_run[0], close_run[1], [], RULE_ID))

    edits.sort(key=lambda e: e.start)
    return edits
