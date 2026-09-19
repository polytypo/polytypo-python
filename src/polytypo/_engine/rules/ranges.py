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
        # ranges.md 3.2, 3.2a -- a candidate iff both flanks are DIGIT once a matched closed-up
        # symbol has been walked over. Anything else is dashes' concern.
        flanks = shared.range_flanks(cp, token.left_idx, token.right_idx)
        if flanks is None:
            continue

        edit = _try_range(cp, token, flanks, form)
        if edit is not None:
            edits.append(edit)
    return edits


def _try_range(
    cp: list[int], token: shared.DashToken, flanks: shared.RangeFlanks, form: str
) -> Edit | None:
    """G1-G5 over the flanks and digit runs ranges.md 3.2a's walk produced. `before`/`after` read
    past a matched outer closed-up symbol, so G1-G3 judge the text in front of the whole member
    rather than the symbol itself -- which is what declines `US$15-$20` on G1."""
    L, R, a, b = flanks.left, flanks.right, flanks.a, flanks.b

    lrun = "".join(chr(c) for c in cp[a : L + 1])
    rrun = "".join(chr(c) for c in cp[R : b + 1])

    before_from = a if flanks.outer_left < 0 else flanks.outer_left
    after_from = b if flanks.outer_right < 0 else flanks.outer_right
    before = shared.effective_neighbor(cp, before_from - 1, -1)
    after = shared.effective_neighbor(cp, after_from + 1, 1)

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
        if shared.composition_guard_blocks(cp, token, flanks):
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
