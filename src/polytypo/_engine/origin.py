"""analyze.md section 2: every reported offset is a code-point offset into the input the caller
passed, in every mode. The rules, however, run over an array that is not the input -- in `text`
mode edits from earlier rules have already shifted it, and in `html`/`markdown` mode it is the
marker-joined concatenation of the processable spans (modes.md 3.5). This module carries the one
structure that bridges the two: an origin map, parallel to the current code-point array, holding
the input offset each code point came from, or NO_ORIGIN for one the pipeline itself produced.
Mirrors polytypo-js's src/engine/origin.ts."""

from __future__ import annotations

from dataclasses import dataclass

from polytypo._engine.codepoints import from_codepoints
from polytypo._engine.edits import Edit

NO_ORIGIN = -1


@dataclass(frozen=True, slots=True)
class Change:
    """One entry of ``analyze``'s result, in input coordinates (analyze.md section 2)."""

    rule_id: str
    start: int
    end: int
    before: str
    after: str


def origin_at(origin: list[int], index: int, input_length: int) -> int:
    """The input offset an edit boundary at ``index`` addresses. Synthetic code points have no
    origin of their own, so the scan runs forward to the first that has one -- an insertion
    between two earlier insertions still lands where the next real character is. Falling off the
    end means the boundary is at the end of the input."""
    for i in range(index, len(origin)):
        if origin[i] != NO_ORIGIN:
            return origin[i]
    return input_length


def apply_edits_to_origin(origin: list[int], edits: list[Edit]) -> list[int]:
    """The origin map for the array ``apply_edits`` is about to produce. A replacement of equal
    length keeps its origins position by position, which is what makes a conversion
    (U+0020 -> U+00A0) still point at the character it converted; anything longer is synthetic
    beyond the positions it covers."""
    if not edits:
        return list(origin)
    out: list[int] = []
    cursor = 0
    for edit in edits:
        out.extend(origin[cursor : edit.start])
        for k in range(len(edit.replacement)):
            source = edit.start + k
            out.append(origin[source] if source < edit.end else NO_ORIGIN)
        cursor = edit.end
    out.extend(origin[cursor:])
    return out


def record_changes(
    cp: list[int], edits: list[Edit], origin: list[int], input_length: int, rule_id: str
) -> list[Change]:
    """One rule's edits, in the coordinates that rule saw, rendered as Changes in input
    coordinates. ``before`` is the text this rule replaced and ``after`` what it replaced it with
    (analyze.md section 2), so on a text two rules have both touched, ``before`` is what the
    second rule saw rather than what the caller typed -- section 5 says so and shows the French
    case where it matters."""
    return [
        Change(
            rule_id=rule_id,
            start=origin_at(origin, edit.start, input_length),
            end=origin_at(origin, edit.end, input_length),
            before=from_codepoints(cp[edit.start : edit.end]),
            after=from_codepoints(edit.replacement),
        )
        for edit in edits
    ]
