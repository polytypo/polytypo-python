"""nbsp.md 3.1a: resolve the ``narrow_nbsp`` option to the code point the rule writes.

Done once, at the call boundary, so no rule ever sees the option's string. Checked immediately
after ``mode`` and before ``rules`` -- the two checks that read nothing but the call itself come
first (ARCHITECTURE.md section 7). It runs whether or not ``nbsp`` is enabled, so a misspelled
value still raises rather than being silently ignored."""

from __future__ import annotations

from polytypo.errors import POLYTYPO_INVALID_OPTION, PolytypoError

#: U+202F, the narrow no-break space -- nbsp.md 3.1a's default NARROW-TARGET.
NARROW_NO_BREAK_SPACE = 0x202F
#: U+00A0, what ``narrow_nbsp="nbsp"`` substitutes for it.
NO_BREAK_SPACE = 0x00A0


def resolve_narrow_target(value: str | None) -> int:
    if value is None or value == "narrow":
        return NARROW_NO_BREAK_SPACE
    if value == "nbsp":
        return NO_BREAK_SPACE
    raise PolytypoError(
        POLYTYPO_INVALID_OPTION,
        f'Unknown narrow_nbsp {value!r}. Expected "narrow" or "nbsp".',
    )
