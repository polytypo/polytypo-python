"""spec/rules/quote-punctuation.md -- order 45, default OFF, locale data:
quotes.punctuationPlacement and quotes.primary.close. A comma or full stop that follows a closing
primary quotation mark moves to before it, in a locale whose placement is "inside"; every other
locale is a no-op."""

from __future__ import annotations

from typing import Any

from polytypo._engine.edits import Edit
from polytypo._engine.registry import RuleContext
from polytypo._engine.rules.quotes import SPACELIKE
from polytypo._engine.sentinels import NONE
from polytypo._engine.unicode import is_letter

RULE_ID = "quote-punctuation"

COMMA = 0x2C
FULL_STOP = 0x2E


def _at(cp: list[int], i: int) -> int:
    if i < 0 or i >= len(cp):
        return NONE
    return cp[i]


def scan(cp: list[int], locale_data: dict[str, Any], ctx: RuleContext) -> list[Edit]:
    quotes = locale_data["quotes"]
    if quotes["punctuationPlacement"] != "inside":
        return []

    close = ord(quotes["primary"]["close"][0])
    edits: list[Edit] = []
    n = len(cp)
    i = 0
    # Spec 3.2: C1-C4 in one left-to-right scan; after an edit continue from i + 2.
    while i + 1 < n:
        following = cp[i + 1]
        after = _at(cp, i + 2)
        if (
            cp[i] == close
            and following in (COMMA, FULL_STOP)
            and i >= 1
            and is_letter(cp[i - 1])
            and (after == NONE or after in SPACELIKE)
        ):
            edits.append(Edit(i, i + 2, [following, close], RULE_ID))
            i += 2
            continue
        i += 1
    return edits
