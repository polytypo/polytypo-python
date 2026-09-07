"""The three non-code-point values a rule can meet in the array it scans (mirrors polytypo-js's
src/engine/sentinels.ts exactly, including the values themselves -- there is no reason for a port
to renumber them, and every reason not to, since a stray literal -1/-2/-3 elsewhere would then
mean different things in different runtimes' debugging output).

- NONE: there is nothing at that index; the array ends here (never actually present *in* the
  array -- it is what `cp[i]` "is" when `i` is out of bounds).
- MARKER: a span boundary whose skipped region has no line terminator. Per modes.md 3.3, opaque
  content everywhere except OPENISH/CLOSEISH, where it is a member of both. Explicitly not NONE
  and not SPACELIKE.
- LINE_MARKER: a span boundary whose skipped region contains a line terminator. A member of BREAK
  for every rule, everywhere.

These are L1 values: rules (L1) read them, mode adapters (L2) write them. Text mode never
produces either marker -- only html/markdown mode adapters do -- so a rule written against these
predicates behaves identically in text mode with zero extra code, which is exactly the point.
"""

from __future__ import annotations

MARKER = -1
LINE_MARKER = -2
NONE = -3


def is_marker(value: int) -> bool:
    return value in (MARKER, LINE_MARKER)
