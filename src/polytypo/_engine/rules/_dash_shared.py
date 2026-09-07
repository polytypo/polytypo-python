"""Shared dash-token scanning steps (spec/rules/dashes.md 3.2, 3.2a, 3.2b), consumed identically
by `ranges` (order 25) and `dashes` (order 30). Each rule runs its own independent scan over the
(possibly already-once-edited-by-ranges) code-point array using this same token-identification
logic, then branches on whether the token is digit-flanked (ranges' territory) or not (dashes')."""

from __future__ import annotations

from dataclasses import dataclass

from polytypo._engine.sentinels import LINE_MARKER, NONE

DASH = frozenset({0x2D, 0x2010, 0x2013, 0x2014, 0x2212})
DIGIT = frozenset(range(0x30, 0x3A))
SPACE = 0x20
# Includes LINE_MARKER: a member of BREAK for every rule everywhere (modes.md 3.2).
BREAK = frozenset({0x0A, 0x0D, 0x0B, 0x0C, 0x85, 0x2028, 0x2029, LINE_MARKER})
NOBREAK_SPACE = frozenset({0xA0, 0x202F})
SPACE_LIKE = frozenset({SPACE}) | NOBREAK_SPACE
ROMAN = frozenset({0x49, 0x56, 0x58, 0x4C, 0x43, 0x44, 0x4D})  # I V X L C D M
INERT_DASH = frozenset({0xAD, 0x2011, 0x2012, 0x2015, 0xFE58, 0xFE63, 0xFF0D})
JOINER = 0x2060
DASH_OR_INERT = DASH | INERT_DASH


def at(cp: list[int], i: int) -> int:
    if i < 0 or i >= len(cp):
        return NONE
    return cp[i]


@dataclass
class DashToken:
    s: int
    e: int
    k: int
    lsp: int
    rsp: int
    left_idx: int  # index of cp[L*], or -1 if NONE
    right_idx: int  # index of cp[R*], or -1 if NONE
    left_cp: int  # cp[L*], or NONE
    right_cp: int  # cp[R*], or NONE
    crossed_joiner: bool
    # min(s - lsp, joinStart) / max(e + rsp, joinEnd) -- meaningful beyond plain s-lsp/e+rsp
    # only when crossed_joiner is True, which for a non-digit-flanked token always means
    # decline (dashes' territory never sees one; only `ranges` can).
    span_start: int
    span_end: int


def _walk_across_joiners(cp: list[int], i: int, step: int) -> int:
    """From index i, step in `step` direction (+1/-1) across a maximal run of JOINER, and
    return the resulting index (which may be out of bounds)."""
    n = len(cp)
    while 0 <= i < n and cp[i] == JOINER:
        i += step
    return i


def find_token(cp: list[int], i: int) -> tuple[DashToken | None, int]:
    """cp[i] is in DASH. Returns (token_or_None, next_scan_index). next_scan_index is always
    the index just past the run (`e`), regardless of whether the token was accepted or
    declined by the shared guards -- matching dashes.md 3.5's "continue from just past the
    token's run in the input array"."""
    n = len(cp)
    s = i
    e = s
    while e < n and cp[e] in DASH:
        e += 1
    k = e - s

    if k > 3:
        return None, e

    lsp = 1 if s > 0 and cp[s - 1] == SPACE else 0
    rsp = 1 if e < n and at(cp, e) == SPACE else 0

    if lsp != rsp:
        return None, e

    L = s - 1 - lsp
    R = e + rsp
    if L < 0 or n <= R:
        return None, e

    # 3.2a: JOINER neighbours -- walk L and R across any maximal JOINER run, before reading
    # what's beyond them. Order matters here: BREAK/isolation/crossed-joiner all inspect the
    # POST-walk neighbour, exactly as dashes.md 3.2a's findDashTokens does (a joiner-adjacent
    # BREAK or space-like character must be read past the joiner, not at it).
    join_start = L + 1
    join_end = R
    left_star = _walk_across_joiners(cp, L, -1)
    right_star = _walk_across_joiners(cp, R, 1)
    if left_star < 0 or right_star >= n:
        return None, e
    crossed_joiner = (left_star + 1 != join_start) or (right_star != join_end)
    join_start = left_star + 1
    join_end = right_star
    L, R = left_star, right_star

    left_cp = cp[L]
    right_cp = cp[R]

    if crossed_joiner and not (left_cp in DIGIT and right_cp in DIGIT):
        return None, e
    if left_cp in BREAK or right_cp in BREAK:
        return None, e

    # Isolation guard: INERT_DASH, DASH, or space-like neighbor declines.
    if left_cp in DASH_OR_INERT or left_cp in SPACE_LIKE:
        return None, e
    if right_cp in DASH_OR_INERT or right_cp in SPACE_LIKE:
        return None, e

    # Cluster guard: maximal span of DASH | INERT_DASH | DIGIT | JOINER containing this run;
    # if it has >= 2 dash runs, the whole cluster is inert.
    if _cluster_has_multiple_dash_runs(cp, s, e):
        return None, e

    token = DashToken(
        s=s,
        e=e,
        k=k,
        lsp=lsp,
        rsp=rsp,
        left_idx=L,
        right_idx=R,
        left_cp=left_cp,
        right_cp=right_cp,
        crossed_joiner=crossed_joiner,
        span_start=min(s - lsp, join_start),
        span_end=max(e + rsp, join_end),
    )
    return token, e


def _cluster_has_multiple_dash_runs(cp: list[int], s: int, e: int) -> bool:
    n = len(cp)
    cluster_alphabet = DASH | INERT_DASH | DIGIT | frozenset({JOINER})

    start = s
    while start > 0 and cp[start - 1] in cluster_alphabet:
        start -= 1
    end = e
    while end < n and cp[end] in cluster_alphabet:
        end += 1

    dash_runs = 0
    i = start
    while i < end:
        if cp[i] in DASH_OR_INERT:
            dash_runs += 1
            while i < end and cp[i] in DASH_OR_INERT:
                i += 1
        else:
            i += 1
    return dash_runs >= 2


def effective_neighbor(cp: list[int], i: int, step: int) -> int:
    """Step outward from i across a maximal run of JOINER; return the first non-joiner code
    point, or NONE if the walk leaves the array."""
    j = _walk_across_joiners(cp, i, step)
    return at(cp, j)


def _two_step_lookout_blocks(cp: list[int], from_idx: int, step: int) -> bool:
    """Reading effective neighbors outward from `from_idx` (exclusive) in `step` direction:
    if the first is DASH/INERT-DASH, or the first is space-like and the second (one step
    further out) is DASH/INERT-DASH, this returns True."""
    first_idx = _walk_across_joiners(cp, from_idx + step, step)
    first = at(cp, first_idx)
    if first in DASH_OR_INERT:
        return True
    if first in SPACE_LIKE:
        second_idx = _walk_across_joiners(cp, first_idx + step, step)
        second = at(cp, second_idx)
        if second in DASH_OR_INERT:
            return True
    return False


def spacing_transition_guard_blocks(cp: list[int], token: DashToken) -> bool:
    """T1 (dashes.md 3.2 step 8): a tight token must not become spaced when doing so would
    insert a space between itself and a digit run that has another dash on its far side.
    Only relevant when lsp=rsp=0 and the chosen form is -spaced; caller checks that."""
    n = len(cp)
    L, R = token.left_idx, token.right_idx

    if 0 <= L < n and cp[L] in DIGIT:
        d = L
        while d > 0 and cp[d - 1] in DIGIT:
            d -= 1
        if _two_step_lookout_blocks(cp, d, -1):
            return True

    if 0 <= R < n and cp[R] in DIGIT:
        d = R
        while d < n - 1 and cp[d + 1] in DIGIT:
            d += 1
        if _two_step_lookout_blocks(cp, d, 1):
            return True

    return False


T2_SET = frozenset({0x2C, 0x2E, 0x3B, 0x3A, 0x21, 0x3F, 0x2026})
CLOSE_BRACKET = frozenset({0x29, 0x5D, 0x7D})
OPEN_BRACKET = frozenset({0x28, 0x5B, 0x7B})


def composition_guard_blocks(cp: list[int], token: DashToken) -> bool:
    """T2 (dashes.md 3.2 step 9): for a -spaced replacement, decline if cp[R] is in T2_SET or
    CLOSE_BRACKET, or cp[L] is in OPEN_BRACKET."""
    if token.right_cp in T2_SET or token.right_cp in CLOSE_BRACKET:
        return True
    return token.left_cp in OPEN_BRACKET
