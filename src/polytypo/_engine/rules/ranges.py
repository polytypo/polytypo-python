"""spec/rules/ranges.md -- order 25, default OFF, locale data: dash.range."""

from __future__ import annotations

from typing import Any

from polytypo._engine.edits import Edit
from polytypo._engine.registry import RuleContext
from polytypo._engine.rules import _dash_shared as shared
from polytypo._engine.sentinels import NONE
from polytypo._engine.unicode import is_letter

RULE_ID = "ranges"

JOINER = 0x2060

_REPLACEMENT_GLYPH = {
    "em-tight": 0x2014,
    "em-spaced": 0x2014,
    "en-tight": 0x2013,
    "en-spaced": 0x2013,
}


def scan(cp: list[int], locale_data: dict[str, Any], ctx: RuleContext) -> list[Edit]:
    form = locale_data["dash"]["range"]
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
        if token.left_cp not in shared.DIGIT or token.right_cp not in shared.DIGIT:
            continue  # not a range candidate; dashes' concern

        edit = _try_range(cp, token, form)
        if edit is not None:
            edits.append(edit)
    return edits


def _try_range(cp: list[int], token: shared.DashToken, form: str) -> Edit | None:
    L, R = token.left_idx, token.right_idx

    a = L
    while a > 0 and cp[a - 1] in shared.DIGIT:
        a -= 1
    b = R
    while b < len(cp) - 1 and cp[b + 1] in shared.DIGIT:
        b += 1

    lrun = "".join(chr(c) for c in cp[a : L + 1])
    rrun = "".join(chr(c) for c in cp[R : b + 1])

    before = shared.effective_neighbor(cp, a - 1, -1)
    after = shared.effective_neighbor(cp, b + 1, 1)

    # G1: no letter adjacency.
    if before != NONE and is_letter(before):
        return None
    # G2: no chain.
    if before in shared.DASH_OR_INERT or after in shared.DASH_OR_INERT:
        return None
    # G3: not part of a decimal or path.
    if before in (0x2E, 0x2C, 0x2F) or after == 0x2F:
        return None
    # G4: run lengths.
    if len(lrun) == len(rrun) or len(lrun) == 1 and len(rrun) == 2 and rrun[0] != "0":
        pass
    else:
        return None
    # G5: non-decreasing.
    if int(lrun) > int(rrun):
        return None

    if form == "none":
        return None

    glyph = _REPLACEMENT_GLYPH[form]
    spaced = form in ("em-spaced", "en-spaced")

    if spaced:
        if token.lsp == 0 and token.rsp == 0 and shared.spacing_transition_guard_blocks(cp, token):
            return None
        if shared.composition_guard_blocks(cp, token):
            return None

    span_start, span_end = token.span_start, token.span_end

    # 3.3.1: never make an edit whose entire content is invisible. Try the unbound
    # replacement first; only add the joiner pair if the dash itself is genuinely changing.
    unbound = [0x20, glyph, 0x20] if spaced else [glyph]
    only_binding_would_change = not spaced and cp[span_start:span_end] == unbound
    bind = not spaced and not only_binding_would_change
    replacement = [JOINER, glyph, JOINER] if bind else unbound
    if cp[span_start:span_end] == replacement:
        return None

    return Edit(span_start, span_end, replacement, RULE_ID)
