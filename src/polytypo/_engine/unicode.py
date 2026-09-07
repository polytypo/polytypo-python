"""Hand-rolled-equivalent Unicode predicates for the rule engine.

The JS reference implementation hand-rolls these as static binary-searched code-point-range
tables (src/engine/unicode.ts), because Go's RE2 has no `\\p{L}`-style Unicode property escapes
(docs/ARCHITECTURE.md section 4.1) and JS's own regex engine, while it does support them, is
avoided everywhere for cross-runtime consistency. Python has neither constraint: `unicodedata` is
a direct, deterministic Unicode Character Database lookup -- not a regex engine, and not
locale-dependent in the ARCHITECTURE.md section 4.4 sense (it never consults `locale.setlocale()`
or any OS/environment setting; it reflects only the interpreter's compiled-in UCD version). Using
it directly is *more* correct than porting JS's frozen-at-one-UCD-version table, not a shortcut.

UCD version note (matches spec/rules/apostrophe.md 7 and nbsp.md 7's documented gap): this
interpreter's `unicodedata` is version 16.0.0; the JS reference implementation's is 17.0. The spec
does not yet pin a UCD version, so two runtimes can disagree on newly assigned code points -- an
acknowledged, spec-level gap, not a defect in this port.
"""

from __future__ import annotations

import unicodedata

_LETTER_CATEGORIES = frozenset({"Lu", "Ll", "Lt", "Lm", "Lo", "Mn", "Mc", "Me"})
_UPPER_CATEGORIES = frozenset({"Lu", "Lt"})


def is_letter(cp: int) -> bool:
    """True for a code point in Lu, Ll, Lt, Lm, Lo, Mn, Mc or Me."""
    if cp < 0 or cp > 0x10FFFF:
        return False
    return unicodedata.category(chr(cp)) in _LETTER_CATEGORIES


def is_upper(cp: int) -> bool:
    """True for a code point in Lu or Lt -- spec 3.1 UPPER, read by nbsp's N7."""
    if cp < 0 or cp > 0x10FFFF:
        return False
    return unicodedata.category(chr(cp)) in _UPPER_CATEGORIES


def simple_uppercase(cp: int) -> int:
    """Unicode *simple* (one-code-point-to-one-code-point) uppercase mapping, needed by
    hyphen.md 3.3 and nbsp.md 3.5 for matching a pattern's first character case-insensitively --
    applied to the *pattern*, never to the input, and never via a whole-string `.upper()` call
    (ARCHITECTURE.md section 4.4 forbids locale-dependent case conversion; this is not that, but
    the discipline of a single explicit code point in, one code point out is still enforced here).

    `str.upper()` on a single Python `str` character is Unicode's *full* case mapping, which for a
    handful of code points (U+00DF small sharp s -> "SS", ligatures like U+FB00 -> "FF") expands
    to more than one character -- exactly the set JS's SIMPLE_UPPERCASE table excludes by
    construction ("entries whose full uppercase mapping expands to more than one code point ...
    are absent, which is exactly what the simple mapping says: they map to themselves"). Guarding
    on the expanded length reproduces that same exclusion without a separate static table.
    """
    if cp < 0 or cp > 0x10FFFF:
        return cp
    upper = chr(cp).upper()
    if len(upper) != 1:
        return cp
    return ord(upper)
