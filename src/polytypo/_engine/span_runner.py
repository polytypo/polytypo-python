"""modes.md 3.5. The pipeline runs **once**, over the marker-separated concatenation of every
processable span -- not per span (would pair quotation marks in isolation), and not over a naive
concatenation (would manufacture adjacencies the document does not have). Mirrors polytypo-js's
src/engine/span-runner.ts."""

from __future__ import annotations

from typing import Any

from polytypo._engine.codepoints import from_codepoints
from polytypo._engine.edits import apply_edits
from polytypo._engine.registry import RuleContext, get_rule
from polytypo._modes.spans import (
    Span,
    concatenate_spans,
    filter_boundary_edits,
    normalize_spans,
    span_ranges_of,
    split_on_marker,
)


def _run_rules_over_spans(
    cp: list[int], plan: list[str], locale_data: dict[str, Any], ctx: RuleContext
) -> list[int]:
    """The same sequence as `run_rules`, with the two boundary filters of modes.md 3.4
    interposed. Span extents are recomputed after every rule, because applying an edit shifts
    every index after it; the markers themselves always survive, since no edit may contain one."""
    current = cp
    for rule_id in plan:
        rule_fn = get_rule(rule_id)
        edits = rule_fn(current, locale_data, ctx)
        filtered = filter_boundary_edits(current, edits, span_ranges_of(current))
        if filtered:
            current = apply_edits(current, filtered, rule_id)
    return current


def run_over_spans(
    source: str,
    spans: list[Span],
    plan: list[str],
    locale_data: dict[str, Any],
    ctx: RuleContext,
) -> str:
    """The output is the input with a set of disjoint substring replacements applied and nothing
    else (modes.md 4). A span whose content the rules did not change contributes no replacement,
    so a document needing no changes comes back byte-identical; the parser located the spans and
    was then discarded, and the document is never serialised."""
    normalized = normalize_spans(spans)
    if not normalized:
        return source

    concatenated = concatenate_spans(source, normalized)
    transformed = _run_rules_over_spans(concatenated, plan, locale_data, ctx)
    pieces = split_on_marker(transformed, len(normalized))

    out: list[str] = []
    cursor = 0
    for span, piece in zip(normalized, pieces, strict=True):
        replacement = from_codepoints(piece)
        original = source[span.start : span.end]
        out.append(source[cursor : span.start])
        out.append(original if replacement == original else replacement)
        cursor = span.end
    out.append(source[cursor:])
    return "".join(out)
