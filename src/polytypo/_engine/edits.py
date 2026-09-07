"""The Edit contract (mirrors polytypo-js's src/engine/edits.ts). Rules produce edits; the
pipeline applies them -- this separation is the one piece of v1 internal structure explicitly
authorized ahead of need (docs/ARCHITECTURE.md section 7.1's reserved, not-yet-implemented
``analyze()`` API)."""

from __future__ import annotations

from dataclasses import dataclass

from polytypo._engine.codepoints import is_valid_codepoint
from polytypo.errors import POLYTYPO_RULE_CONTRACT, PolytypoError


@dataclass(frozen=True, slots=True)
class Edit:
    """Half-open ``[start, end)`` over the code-point array being transformed."""

    start: int
    end: int
    replacement: list[int]
    rule_id: str


def validate_edits(edits: list[Edit], length: int, rule_id: str | None = None) -> None:
    """Raises POLYTYPO_RULE_CONTRACT unless every edit is in-bounds, ascending, non-overlapping,
    tagged with the expected rule id (when one is given), and every replacement code point is
    valid. Mirrors edits.ts's ``validateEdits`` contract exactly."""
    previous_end = 0
    for i, edit in enumerate(edits):
        where = f"edit[{i}] (rule {edit.rule_id!r})"
        if not isinstance(edit.start, int) or not isinstance(edit.end, int):
            raise PolytypoError(POLYTYPO_RULE_CONTRACT, f"{where}: start/end must be integers")
        if edit.start < 0 or edit.end > length or edit.end < edit.start:
            raise PolytypoError(
                POLYTYPO_RULE_CONTRACT,
                f"{where}: bounds [{edit.start}, {edit.end}) are invalid for length {length}",
            )
        if edit.start < previous_end:
            raise PolytypoError(
                POLYTYPO_RULE_CONTRACT,
                f"{where}: overlaps or precedes the previous edit (start={edit.start} < "
                f"previous_end={previous_end}) -- edits must be strictly ascending and "
                "non-overlapping",
            )
        if rule_id is not None and edit.rule_id != rule_id:
            raise PolytypoError(
                POLYTYPO_RULE_CONTRACT,
                f"{where}: ruleId mismatch, expected {rule_id!r}",
            )
        for cp in edit.replacement:
            if not is_valid_codepoint(cp):
                raise PolytypoError(POLYTYPO_RULE_CONTRACT, f"{where}: invalid code point {cp!r}")
        previous_end = edit.end


def apply_edits(cp: list[int], edits: list[Edit], rule_id: str | None = None) -> list[int]:
    """Validates, then does a single left-to-right splice. Never mutates ``cp``."""
    validate_edits(edits, len(cp), rule_id)
    out: list[int] = []
    cursor = 0
    for edit in edits:
        out.extend(cp[cursor : edit.start])
        out.extend(edit.replacement)
        cursor = edit.end
    out.extend(cp[cursor:])
    return out
