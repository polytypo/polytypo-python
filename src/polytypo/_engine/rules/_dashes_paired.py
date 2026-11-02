"""spec/rules/dashes.md 3.4a -- `dash.parenthetical = "em-paired"` (spec 1.18.0).

The pair is written with a space outside it and none inside (`Llegó —por fin— a casa`), which no
per-token rule can express: which stroke opens and which closes is a property of the sentence, not
of the token. A sentence is converted only when it holds exactly two counted strokes and both are
eligible; anything else is left as typed."""

from __future__ import annotations

from dataclasses import dataclass

from polytypo._engine.edits import Edit
from polytypo._engine.rules import _dash_shared as shared
from polytypo._engine.sentinels import is_marker
from polytypo._engine.unicode import is_letter

_RULE_ID = "dashes"
_EM_DASH = 0x2014
_EN_DASH = 0x2013
_HYPHEN_SHAPED = frozenset({0x2D, 0x2010, 0x2212})
_TERMINALS = frozenset({0x2E, 0x3F, 0x21, 0x2026})


@dataclass(frozen=True)
class _Run:
    s: int
    e: int
    lsp: int
    rsp: int
    left: int
    right: int
    eligible: bool


def _ends_segment(cp: list[int], i: int) -> bool:
    """A terminal ends a segment only before a space (U+0020 or a no-break space, which `nbsp`
    puts there later), a line break, a marker or the end of input."""
    if cp[i] not in _TERMINALS:
        return False
    if i + 1 >= len(cp):
        return True
    nxt = cp[i + 1]
    return (
        nxt == shared.SPACE or nxt in shared.NOBREAK_SPACE or nxt in shared.BREAK or is_marker(nxt)
    )


def _classify(cp: list[int], s: int, e: int) -> _Run | None:
    n = len(cp)
    k = e - s
    if k > 3:
        return None

    lsp = 1 if s > 0 and cp[s - 1] == shared.SPACE else 0
    rsp = 1 if e < n and cp[e] == shared.SPACE else 0
    first = cp[s]
    # A hyphen inside a word is a compound, not a stroke.
    if k == 1 and first in _HYPHEN_SHAPED and lsp == 0 and rsp == 0:
        return None
    # The hyphen of `+/-`, which `symbols` (order 80) turns into `±`: counting it would let that
    # later rule change the number of strokes in the segment.
    if k == 1 and first == 0x2D and s >= 2 and cp[s - 1] == 0x2F and cp[s - 2] == 0x2B:
        return None

    def counted(eligible: bool, left: int, right: int) -> _Run:
        return _Run(s, e, lsp, rsp, left, right, eligible)

    left = s - 1 - lsp
    right = e + rsp
    if left < 0 or right >= n:
        return counted(False, left, right)

    join_start = left + 1
    join_end = right
    while left >= 0 and cp[left] == shared.JOINER:
        left -= 1
    while right < n and cp[right] == shared.JOINER:
        right += 1
    if left < 0 or right >= n:
        return counted(False, left, right)
    crossed_joiner = left + 1 != join_start or right != join_end

    if shared.range_flanks(cp, left, right) is not None:
        return None
    if crossed_joiner:
        return counted(False, left, right)

    left_cp = cp[left]
    right_cp = cp[right]
    if left_cp in shared.BREAK or right_cp in shared.BREAK:
        return counted(False, left, right)
    if left_cp in shared.DASH_OR_INERT or right_cp in shared.DASH_OR_INERT:
        return counted(False, left, right)
    if left_cp in shared.SPACE_LIKE or right_cp in shared.SPACE_LIKE:
        return counted(False, left, right)
    if shared.cluster_has_multiple_dash_runs(cp, s, e):
        return counted(False, left, right)

    # A stroke spaced on one side only is eligible solely as the one em dash that is already half
    # of the target form; `-mente`, `pre-`, `--force` and `- item` are not dashes.
    if lsp != rsp and not (k == 1 and first == _EM_DASH):
        return counted(False, left, right)
    # P4: a tight stroke between two Roman numerals is a range already in its correct form.
    if lsp == 0 and rsp == 0 and shared.is_roman_flanked(cp, left, right):
        return counted(False, left, right)
    # P5: an authored lone en dash is declined in every locale.
    if k == 1 and first == _EN_DASH:
        return counted(False, left, right)
    return counted(True, left, right)


def _wants_space(c: int) -> bool:
    return is_letter(c) or c in shared.DIGIT


def scan_paired(cp: list[int]) -> list[Edit]:
    n = len(cp)
    edits: list[Edit] = []
    segment: list[_Run] = []
    i = 0
    while i < n:
        if cp[i] in shared.DASH:
            s = i
            e = s
            while e < n and cp[e] in shared.DASH:
                e += 1
            i = e
            run = _classify(cp, s, e)
            if run is not None:
                segment.append(run)
            continue
        if _ends_segment(cp, i):
            _flush(cp, segment, edits)
            segment = []
        i += 1
    _flush(cp, segment, edits)
    return edits


def _flush(cp: list[int], segment: list[_Run], edits: list[Edit]) -> None:
    if len(segment) == 2:
        _emit_pair(cp, segment[0], segment[1], edits)


def _emit_pair(cp: list[int], a: _Run, b: _Run, edits: list[Edit]) -> None:
    if not a.eligible or not b.eligible:
        return
    if a.lsp == 0 and a.rsp == 1:  # the first stroke is shaped like a closer
        return
    if b.lsp == 1 and b.rsp == 0:  # the second stroke is shaped like an opener
        return
    for j in range(a.e, b.s):
        if cp[j] in shared.BREAK:
            return

    insert_before = a.lsp == 0 and _wants_space(cp[a.left])
    insert_after = b.rsp == 0 and _wants_space(cp[b.right])
    if insert_before and shared.spacing_transition_blocked_left(cp, a.left):
        return
    if insert_after and shared.spacing_transition_blocked_right(cp, b.right):
        return

    opener = [shared.SPACE, _EM_DASH] if a.lsp == 1 or insert_before else [_EM_DASH]
    closer = [_EM_DASH, shared.SPACE] if b.rsp == 1 or insert_after else [_EM_DASH]

    for run, replacement in ((a, opener), (b, closer)):
        start = run.s - run.lsp
        end = run.e + run.rsp
        if cp[start:end] == replacement:
            continue
        edits.append(Edit(start, end, replacement, _RULE_ID))
