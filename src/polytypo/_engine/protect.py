"""modes.md 3.9: ``text`` mode's ``protect`` option (spec 1.13.0), the caller's own skipped
regions. A protected run is a skipped region whose position the caller supplied instead of a
parser, so it takes the same mechanism as html/markdown/yaml (Model C): the run becomes ONE
boundary marker in the code-point array, the rules run once, and the run is re-emitted byte for
byte. Mirrors polytypo-js's src/engine/protect.ts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, NamedTuple

from polytypo._engine.codepoints import from_codepoints, to_codepoints
from polytypo._engine.origin import NO_ORIGIN, Change
from polytypo._engine.pipeline import run_rules_recording
from polytypo._engine.registry import RuleContext
from polytypo._engine.sentinels import LINE_MARKER, MARKER, is_marker
from polytypo._engine.span_runner import run_rules_over_spans
from polytypo._modes.spans import filter_boundary_edits, span_ranges_of
from polytypo.errors import (
    POLYTYPO_INVALID_OPTION,
    POLYTYPO_RULE_CONTRACT,
    PolytypoError,
)

# The seven code points of BREAK (spaces.md 3.1): a hole containing one is a line marker.
_LINE_TERMINATORS = frozenset({0x0A, 0x0D, 0x0B, 0x0C, 0x85, 0x2028, 0x2029})


class Hole(NamedTuple):
    """One maximal protected run, ``[start, end)`` in code points of the input."""

    start: int
    end: int


def _invalid(message: str) -> PolytypoError:
    return PolytypoError(POLYTYPO_INVALID_OPTION, message)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def resolve_protect(value: object, length: int) -> list[Hole]:
    """Validates ``protect`` against the input's length in code points and merges touching
    ranges. ``None`` and an empty sequence are the same call (modes.md 3.9.2)."""
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _invalid('"protect" must be a sequence of (start, end) ranges (modes.md 3.9.2).')
    holes: list[Hole] = []
    previous_end = 0
    for item in value:
        if isinstance(item, (str, bytes)) or not isinstance(item, Sequence) or len(item) != 2:
            raise _invalid(f'"protect" entries must be (start, end) pairs; received {item!r}.')
        start, end = item[0], item[1]
        if not _is_int(start) or not _is_int(end):
            raise _invalid(f'"protect" start and end must be integers; received {item!r}.')
        if start < 0 or end <= start:
            raise _invalid(f'"protect" range [{start}, {end}) is empty or negative.')
        if start < previous_end:
            raise _invalid(
                f'"protect" range [{start}, {end}) overlaps or precedes the previous one.'
            )
        if end > length:
            raise _invalid(
                f'"protect" range [{start}, {end}) runs past the end of the input '
                f"({length} code points)."
            )
        if holes and holes[-1].end == start:
            holes[-1] = Hole(holes[-1].start, end)
        else:
            holes.append(Hole(start, end))
        previous_end = end
    return holes


def assert_no_protect(value: object) -> None:
    """modes.md 3.9.2: outside ``text`` a non-empty ``protect`` is refused, not ignored."""
    if value is None:
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 0:
        return
    raise _invalid('"protect" is only available in text mode (modes.md 3.9.2).')


def _layout(cp: list[int], holes: list[Hole]) -> tuple[list[int], list[int]]:
    """``[S0] m S1 m ... [Sk]``, with a marker for every hole, edges included (modes.md 3.9.1)."""
    array: list[int] = []
    origin: list[int] = []
    cursor = 0
    for hole in holes:
        array.extend(cp[cursor : hole.start])
        origin.extend(range(cursor, hole.start))
        is_line = any(c in _LINE_TERMINATORS for c in cp[hole.start : hole.end])
        array.append(LINE_MARKER if is_line else MARKER)
        origin.append(NO_ORIGIN)
        cursor = hole.end
    array.extend(cp[cursor:])
    origin.extend(range(cursor, len(cp)))
    return array, origin


def run_protected_mapped(
    input_text: str,
    holes: list[Hole],
    plan: list[str],
    locale_data: dict[str, Any],
    ctx: RuleContext,
) -> tuple[str, list[Hole]]:
    """The output text and the holes located in it. ``transform`` returns only the text
    (modes.md 3.9.5); the second value exists so tests can build ``protect'``."""
    cp = to_codepoints(input_text)
    array, _ = _layout(cp, holes)
    out = run_rules_over_spans(array, plan, locale_data, ctx)
    result: list[int] = []
    mapped: list[Hole] = []
    seen = 0
    for value in out:
        if is_marker(value):
            hole = holes[seen]
            start = len(result)
            result.extend(cp[hole.start : hole.end])
            mapped.append(Hole(start, len(result)))
            seen += 1
            continue
        result.append(value)
    if seen != len(holes):
        raise PolytypoError(
            POLYTYPO_RULE_CONTRACT, "boundary markers did not survive the pipeline."
        )
    return from_codepoints(result), mapped


def run_protected(
    input_text: str,
    holes: list[Hole],
    plan: list[str],
    locale_data: dict[str, Any],
    ctx: RuleContext,
) -> str:
    return run_protected_mapped(input_text, holes, plan, locale_data, ctx)[0]


def analyze_protected(
    input_text: str,
    holes: list[Hole],
    plan: list[str],
    locale_data: dict[str, Any],
    ctx: RuleContext,
) -> list[Change]:
    cp = to_codepoints(input_text)
    array, origin = _layout(cp, holes)
    return run_rules_recording(
        array,
        plan,
        locale_data,
        ctx,
        origin,
        len(cp),
        lambda current, edits: filter_boundary_edits(current, edits, span_ranges_of(current)),
    )
