"""spec/rules/ellipsis.md -- order 20, default on.
Locale data: ellipsis.abbreviatedAfterTerminal."""

from __future__ import annotations

from typing import Any

from polytypo._engine.edits import Edit
from polytypo._engine.registry import RuleContext
from polytypo._engine.sentinels import NONE

RULE_ID = "ellipsis"

DOT = 0x2E
ELL = 0x2026
DOTLIKE = frozenset({DOT, ELL})
TERMINAL = frozenset({0x21, 0x3F})


def _at(cp: list[int], i: int) -> int:
    if i < 0 or i >= len(cp):
        return NONE
    return cp[i]


def scan(cp: list[int], locale_data: dict[str, Any], ctx: RuleContext) -> list[Edit]:
    abbreviated_after_terminal: bool = locale_data["ellipsis"]["abbreviatedAfterTerminal"]
    edits: list[Edit] = []
    n = len(cp)
    i = 0
    while i < n:
        if cp[i] not in DOTLIKE:
            i += 1
            continue
        s = i
        e = s
        d = 0
        q = 0
        while e < n and cp[e] in DOTLIKE:
            if cp[e] == DOT:
                d += 1
            else:
                q += 1
            e += 1
        k = e - s

        left = _at(cp, s - 1)

        if k == 1 and d == 1:
            pass  # ordinary full stop, no edit
        elif k == 1 and q == 1:
            _maybe_abbreviate(edits, s, left, abbreviated_after_terminal)
        elif k == 2 and q == 0:
            if abbreviated_after_terminal:
                pass  # unconditionally inert
            elif left in TERMINAL:
                edits.append(Edit(s, e, [ELL], RULE_ID))
            # else: leave alone (../, 1..5, a..b)
        else:
            # k>=2,q>=1 (mixed/repeated) or k>=3,q==0 (three-or-more dots): normalize to one
            # ellipsis, then it may still need the abbreviated-after-terminal treatment. (The
            # k==2,q==0 case is unreachable here -- the elif above already claims it.)
            if not _maybe_abbreviate(edits, s, left, abbreviated_after_terminal, run_end=e):
                edits.append(Edit(s, e, [ELL], RULE_ID))
        i = e
    return edits


def _maybe_abbreviate(
    edits: list[Edit],
    s: int,
    left: int,
    abbreviated_after_terminal: bool,
    run_end: int | None = None,
) -> bool:
    """Applies to a run that is (or normalizes to) a single U+2026 at position s. If
    run_end is given, the run currently spans [s, run_end) and must be normalized to
    a single ellipsis as part of the same edit (never two chained edits). Returns True if
    an edit was appended."""
    end = run_end if run_end is not None else s + 1
    if abbreviated_after_terminal and left in TERMINAL:
        edits.append(Edit(s, end, [DOT, DOT], RULE_ID))
        return True
    if run_end is not None:
        edits.append(Edit(s, end, [ELL], RULE_ID))
        return True
    return False
