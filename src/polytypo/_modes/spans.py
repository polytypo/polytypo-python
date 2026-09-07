"""spec/rules/modes.md 3.2-3.5 -- the span model shared by every mode adapter that is not
``text``. Mirrors polytypo-js's src/modes/spans.ts exactly: markers are written here (mode
layer), classified in engine/sentinels.py and in each rule's own class definitions (L1)."""

from __future__ import annotations

from dataclasses import dataclass

from polytypo._engine.codepoints import to_codepoints
from polytypo._engine.edits import Edit
from polytypo._engine.sentinels import LINE_MARKER, MARKER, is_marker
from polytypo.errors import POLYTYPO_RULE_CONTRACT, PolytypoError

LINE_TERMINATORS = frozenset({0x0A, 0x0D, 0x0B, 0x0C, 0x85, 0x2028, 0x2029})


@dataclass(frozen=True, slots=True)
class Span:
    """A processable span, identified by its offsets in the **original source** -- Python str
    indices, which are already code-point indices (no UTF-16 surrogate-pair concern JS has)."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class SpanRange:
    """A span's extent in the concatenated code-point array: s0/s1 of modes.md 3.4."""

    first: int
    last: int


def _gap_is_line_boundary(source: str, from_: int, to: int) -> bool:
    return any(ord(source[i]) in LINE_TERMINATORS for i in range(from_, to))


def normalize_spans(spans: list[Span]) -> list[Span]:
    """Sort, drop empties, and coalesce spans separated by nothing in the source (modes.md 7.5).
    Overlapping spans are an extractor bug and are rejected rather than silently merged."""
    sorted_spans = sorted((s for s in spans if s.end > s.start), key=lambda s: s.start)
    out: list[Span] = []
    for span in sorted_spans:
        if not out:
            out.append(span)
            continue
        last = out[-1]
        if span.start < last.end:
            raise PolytypoError(
                POLYTYPO_RULE_CONTRACT,
                f"mode extractor produced overlapping spans ({last.start}, {last.end}) and "
                f"({span.start}, {span.end})",
            )
        if span.start == last.end:
            out[-1] = Span(last.start, span.end)
            continue
        out.append(span)
    return out


def concatenate_spans(source: str, spans: list[Span]) -> list[int]:
    """S1 (marker) S2 ... Sm (modes.md 3.5 step 2)."""
    cp: list[int] = []
    previous: Span | None = None
    for span in spans:
        if previous is not None:
            is_line = _gap_is_line_boundary(source, previous.end, span.start)
            cp.append(LINE_MARKER if is_line else MARKER)
        cp.extend(to_codepoints(source[span.start : span.end]))
        previous = span
    return cp


def span_ranges_of(cp: list[int]) -> list[SpanRange]:
    """The span extents of the array as it stands. Recomputed after every rule, because applying
    edits shifts every index after the first one -- the markers themselves always survive, since
    no edit may contain one."""
    ranges: list[SpanRange] = []
    first = 0
    for i, value in enumerate(cp):
        if is_marker(value):
            ranges.append(SpanRange(first, i - 1))
            first = i + 1
    ranges.append(SpanRange(first, len(cp) - 1))
    return ranges


def _span_containing(ranges: list[SpanRange], p: int) -> SpanRange | None:
    for r in ranges:
        if r.first <= p <= r.last + 1:
            return r
    return None


def filter_boundary_edits(cp: list[int], edits: list[Edit], ranges: list[SpanRange]) -> list[Edit]:
    """modes.md 3.4, two safety nets, both pure functions of (p, q, r, s0, s1):

    1. No edit may contain a marker -- one that does is a bug, discarded rather than
       redistributed.
    2. The edge-growth rule: an edit is discarded if it would place code points at an extremity
       of its span that were not there before (p = s0 and r > d, or q = s1 and r > d, with
       d = q - p + 1 the replaced length and r the replacement length).

    Deletion at an edge is NOT restricted here -- r > d is always false for a deletion, so this
    filter never sees one; that case is spaces.md 3.2 step 4's own edge-as-NONE clause instead.
    """
    out: list[Edit] = []
    for edit in edits:
        if any(is_marker(cp[i]) for i in range(edit.start, edit.end)):
            continue

        p = edit.start
        q = edit.end - 1
        d = edit.end - edit.start
        r = len(edit.replacement)
        span = _span_containing(ranges, p)
        if span is not None and r > d and (p == span.first or q == span.last):
            continue

        out.append(edit)
    return out


def split_on_marker(cp: list[int], expected: int) -> list[list[int]]:
    """Redistribute the transformed array back to one piece per span (modes.md 3.5 step 4)."""
    pieces: list[list[int]] = [[]]
    for value in cp:
        if is_marker(value):
            pieces.append([])
            continue
        pieces[-1].append(value)
    if len(pieces) != expected:
        raise PolytypoError(
            POLYTYPO_RULE_CONTRACT,
            f"boundary markers did not survive the pipeline: expected {expected} spans, "
            f"found {len(pieces)}",
        )
    return pieces
