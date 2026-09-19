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

# ranges.md 3.2a CLOSED-SYMBOL (spec 1.3.0): the symbols conventionally written closed up to a
# number. A literal code-point set, never a Unicode category test -- a category makes the verdict
# depend on which Unicode version a runtime was built against, and the five runtimes must agree.
# The currency part is the U+20A0-U+20CF block by its own bounds, not the subset assigned in some
# Unicode version: the assigned subset drifts between releases, block bounds do not.
CLOSED_SYMBOL = (
    frozenset({0x24})
    | frozenset(range(0xA2, 0xA6))
    | frozenset(range(0x20A0, 0x20D0))
    | frozenset({0x25, 0x2030, 0x2031, 0xB0})
)


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

    # dashes.md 3.2a: re-entry across a joiner is only ever a bound range `ranges` produced on
    # an earlier pass. Spec 1.3.0 reads that condition after the closed-up-symbol walk, so
    # `$15<J>-<J>$20` re-enters the same way `1914<J>-<J>1918` does.
    if crossed_joiner and range_flanks(cp, L, R) is None:
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


@dataclass(frozen=True)
class RangeFlanks:
    """ranges.md 3.2a: a token's flanks after the closed-up-symbol walk, with the digit runs the
    guards and the replacement then read. `left`/`right` are L'/R'; `outer_left`/`outer_right`
    are the matched outer symbols' indices, or -1."""

    left: int
    right: int
    a: int
    b: int
    outer_left: int
    outer_right: int


def range_flanks(cp: list[int], left: int, right: int) -> RangeFlanks | None:
    """ranges.md 3.2 and 3.2a -- is this token a range candidate, and where are its digit runs?
    None means it is not one, which is the signal that the token belongs to `dashes`.

    Both sides are decided from the ORIGINAL left/right, simultaneously; a side consumes a
    closed-up symbol only when the opposite member repeats the same code point. An unmatched
    symbol leaves the flank a non-DIGIT, so `$15-\u20ac20` and `15-$20` are not candidates and do
    not change hands."""
    n = len(cp)
    inner_right = (
        cp[right]
        if at(cp, right) in CLOSED_SYMBOL and right + 1 < n and cp[right + 1] in DIGIT
        else None
    )
    inner_left = (
        cp[left] if at(cp, left) in CLOSED_SYMBOL and left > 0 and cp[left - 1] in DIGIT else None
    )

    left_index = left if inner_left is None else left - 1
    right_index = right if inner_right is None else right + 1
    if at(cp, left_index) not in DIGIT or at(cp, right_index) not in DIGIT:
        return None

    a = left_index
    while a > 0 and cp[a - 1] in DIGIT:
        a -= 1
    b = right_index
    while b + 1 < n and cp[b + 1] in DIGIT:
        b += 1

    outer_left = -1
    if inner_right is not None:
        outer_left = _walk_across_joiners(cp, a - 1, -1)
        if at(cp, outer_left) != inner_right:
            return None
    outer_right = -1
    if inner_left is not None:
        outer_right = _walk_across_joiners(cp, b + 1, 1)
        if at(cp, outer_right) != inner_left:
            return None

    return RangeFlanks(left_index, right_index, a, b, outer_left, outer_right)


def _skip_closed_up_symbol(cp: list[int], from_idx: int, step: int) -> int:
    """T1's reach is transparent to one CLOSED-SYMBOL on either end of a digit run (spec 1.3.0):
    the run it protects may be a range member carrying an outer symbol."""
    i = _walk_across_joiners(cp, from_idx, step)
    if at(cp, i) not in CLOSED_SYMBOL:
        return from_idx
    return i + step


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


def _two_step_lookout_blocks(cp: list[int], start_idx: int, step: int) -> bool:
    """Reading effective neighbors outward from `start_idx` (inclusive) in `step` direction:
    if the first is DASH/INERT-DASH, or the first is space-like and the second (one step
    further out) is DASH/INERT-DASH, this returns True."""
    first_idx = _walk_across_joiners(cp, start_idx, step)
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

    # Spec 1.3.0, position p1: step over a CLOSED-SYMBOL sitting between the token and the run.
    if at(cp, L) in CLOSED_SYMBOL and L > 0 and cp[L - 1] in DIGIT:
        L -= 1
    if at(cp, R) in CLOSED_SYMBOL and n > R + 1 and cp[R + 1] in DIGIT:
        R += 1

    if 0 <= L < n and cp[L] in DIGIT:
        d = L
        while d > 0 and cp[d - 1] in DIGIT:
            d -= 1
        # Position p2: and over one at the far end of the run.
        if _two_step_lookout_blocks(cp, _skip_closed_up_symbol(cp, d - 1, -1), -1):
            return True

    if 0 <= R < n and cp[R] in DIGIT:
        d = R
        while d < n - 1 and cp[d + 1] in DIGIT:
            d += 1
        if _two_step_lookout_blocks(cp, _skip_closed_up_symbol(cp, d + 1, 1), 1):
            return True

    return False


T2_SET = frozenset({0x2C, 0x2E, 0x3B, 0x3A, 0x21, 0x3F, 0x2026})
CLOSE_BRACKET = frozenset({0x29, 0x5D, 0x7D})
OPEN_BRACKET = frozenset({0x28, 0x5B, 0x7B})


def composition_guard_blocks(
    cp: list[int], token: DashToken, flanks: RangeFlanks | None = None
) -> bool:
    """T2 (dashes.md 3.2 step 9): for a -spaced replacement, decline if cp[R] is in T2_SET or
    CLOSE_BRACKET, or cp[L] is in OPEN_BRACKET. `ranges` passes its walked flanks, because
    ranges.md 3.2a makes cp[L']/cp[R'] what every shared guard sees once a closed-up symbol has
    been consumed."""
    left_cp = token.left_cp if flanks is None else at(cp, flanks.left)
    right_cp = token.right_cp if flanks is None else at(cp, flanks.right)
    if right_cp in T2_SET or right_cp in CLOSE_BRACKET:
        return True
    return left_cp in OPEN_BRACKET
