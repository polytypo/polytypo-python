"""spec/rules/dashes.md -- order 30, default on, locale data: dash.parenthetical."""

from __future__ import annotations

from typing import Any

from polytypo._engine.edits import Edit
from polytypo._engine.registry import RuleContext
from polytypo._engine.rules import _dash_shared as shared
from polytypo._engine.sentinels import NONE
from polytypo._engine.unicode import is_letter

RULE_ID = "dashes"

_REPLACEMENT_GLYPH = {
    "em-tight": 0x2014,
    "em-spaced": 0x2014,
    "en-tight": 0x2013,
    "en-spaced": 0x2013,
}


def scan(cp: list[int], locale_data: dict[str, Any], ctx: RuleContext) -> list[Edit]:
    form = locale_data["dash"]["parenthetical"]
    edits: list[Edit] = []
    n = len(cp)
    i = 0
    while i < n:
        if cp[i] not in shared.DASH:
            i += 1
            continue
        token, next_i = shared.find_token(cp, i)
        i = next_i
        if token is None:
            continue
        if token.left_cp in shared.DIGIT and token.right_cp in shared.DIGIT:
            continue  # digit-flanked: ranges' territory exclusively, never dashes'.

        edit = _try_parenthetical(cp, token, form)
        if edit is not None:
            edits.append(edit)
    return edits


def _try_parenthetical(cp: list[int], token: shared.DashToken, form: str) -> Edit | None:
    s, k = token.s, token.k
    lsp, rsp = token.lsp, token.rsp

    # P5: a pure, single, authored en-dash is never touched, in any locale, unconditionally.
    if k == 1 and cp[s] == 0x2013:
        return None

    # P1: a bare hyphen-shaped stroke must be spaced (else it's a compound-word hyphen).
    if k == 1 and cp[s] in (0x2D, 0x2010, 0x2212) and lsp == 0:
        return None

    # P4: Roman-numeral veto (tight token only).
    if lsp == 0 and rsp == 0 and _roman_veto_fires(cp, token):
        return None

    # P2/P3: everything else (any DASH glyph, k in {1,2,3}) promotes to the locale's form.
    if form == "none":
        return None

    glyph = _REPLACEMENT_GLYPH[form]
    spaced = form in ("em-spaced", "en-spaced")

    if spaced:
        if lsp == 0 and rsp == 0 and shared.spacing_transition_guard_blocks(cp, token):
            return None
        if shared.composition_guard_blocks(cp, token):
            return None
        replacement = [0x20, glyph, 0x20]
    else:
        replacement = [glyph]

    span_start, span_end = token.span_start, token.span_end
    if cp[span_start:span_end] == replacement:
        return None

    return Edit(span_start, span_end, replacement, RULE_ID)


def _roman_veto_fires(cp: list[int], token: shared.DashToken) -> bool:
    """P4: a tight dash between two maximal ROMAN runs, each outer-bounded by a non-LETTER,
    is preserved as a genuine Russian-style range and never converted."""
    L, R = token.left_idx, token.right_idx
    n = len(cp)

    if not (0 <= L < n and cp[L] in shared.ROMAN):
        return False
    if not (0 <= R < n and cp[R] in shared.ROMAN):
        return False

    left_run_start = L
    while left_run_start > 0 and cp[left_run_start - 1] in shared.ROMAN:
        left_run_start -= 1
    outer_left = shared.at(cp, left_run_start - 1)
    if outer_left != NONE and is_letter(outer_left):
        return False

    right_run_end = R
    while right_run_end < n - 1 and cp[right_run_end + 1] in shared.ROMAN:
        right_run_end += 1
    outer_right = shared.at(cp, right_run_end + 1)
    return outer_right == NONE or not is_letter(outer_right)
