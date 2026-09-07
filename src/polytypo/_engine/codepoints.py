"""String <-> code-point array conversion (docs/ARCHITECTURE.md section 4.2: rules index an
explicit code-point array, never a native string). Python 3 strings are already sequences of
Unicode code points (no UTF-16 surrogate-pair encoding to undo, unlike the JS reference
implementation) -- this module exists for cross-runtime consistency and because every rule below
is written against "index i of the code-point array", not "index i of the string", so the
discipline is worth keeping explicit even where Python makes it nearly free."""

from __future__ import annotations


def to_codepoints(s: str) -> list[int]:
    return [ord(c) for c in s]


def from_codepoints(cp: list[int]) -> str:
    return "".join(chr(c) for c in cp)


def is_valid_codepoint(value: int) -> bool:
    return isinstance(value, int) and 0 <= value <= 0x10FFFF
