"""modes.md 3.5. The pipeline runs **once**, over the marker-separated concatenation of every
processable span -- not per span (would pair quotation marks in isolation), and not over a naive
concatenation (would manufacture adjacencies the document does not have). Mirrors polytypo-js's
src/engine/span-runner.ts."""

from __future__ import annotations

from typing import Any

from polytypo._engine.codepoints import from_codepoints
from polytypo._engine.edits import apply_edits
from polytypo._engine.origin import Change
from polytypo._engine.pipeline import run_rules_recording
from polytypo._engine.registry import RuleContext, get_rule
from polytypo._modes.spans import (
    Span,
    concatenate_spans,
    filter_boundary_edits,
    normalize_spans,
    origin_of_spans,
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


def _replacements_of_unit(
    source: str,
    spans: list[Span],
    plan: list[str],
    locale_data: dict[str, Any],
    ctx: RuleContext,
) -> list[tuple[Span, str]]:
    """One text unit (modes.md 3.1): the marker-separated concatenation, the pipeline, and the
    pieces it produced, paired with the spans they replace."""
    normalized = normalize_spans(spans)
    if not normalized:
        return []
    concatenated = concatenate_spans(source, normalized)
    transformed = _run_rules_over_spans(concatenated, plan, locale_data, ctx)
    pieces = split_on_marker(transformed, len(normalized))
    return [(span, from_codepoints(piece)) for span, piece in zip(normalized, pieces, strict=True)]


def _emit(source: str, replacements: list[tuple[Span, str]]) -> str:
    """modes.md 4: the source with disjoint replacements applied at recorded offsets, and nothing
    else changed."""
    out: list[str] = []
    cursor = 0
    for span, replacement in replacements:
        original = source[span.start : span.end]
        out.append(source[cursor : span.start])
        out.append(original if replacement == original else replacement)
        cursor = span.end
    out.append(source[cursor:])
    return "".join(out)


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
    return _emit(source, _replacements_of_unit(source, spans, plan, locale_data, ctx))


def run_over_units(
    source: str,
    units: list[list[Span]],
    plan: list[str],
    locale_data: dict[str, Any],
    ctx: RuleContext,
) -> str:
    """modes.md 3.1 and 3.5 step 3 (spec 1.7.0). A document has one text unit, except in
    ``markdown`` with ``frontmatter_keys``, where the frontmatter block's spans form a unit of
    their own. The pipeline runs once per unit and the two edit sets are disjoint, because no span
    of one unit lies inside the other -- which is what the body's span walk skipping the block
    guarantees. Only step 5 is shared: the source is emitted once, in document order."""
    replacements: list[tuple[Span, str]] = []
    for spans in units:
        replacements.extend(_replacements_of_unit(source, spans, plan, locale_data, ctx))
    replacements.sort(key=lambda pair: pair[0].start)
    return _emit(source, replacements)


def analyze_over_units(
    source: str,
    units: list[list[Span]],
    plan: list[str],
    locale_data: dict[str, Any],
    ctx: RuleContext,
) -> list[Change]:
    """`analyze_over_spans` per text unit (modes.md 3.1), reported in document order."""
    changes: list[Change] = []
    for spans in units:
        changes.extend(analyze_over_spans(source, spans, plan, locale_data, ctx))
    changes.sort(key=lambda change: change.start)
    return changes


def analyze_over_spans(
    source: str,
    spans: list[Span],
    plan: list[str],
    locale_data: dict[str, Any],
    ctx: RuleContext,
) -> list[Change]:
    """`run_over_spans`, reporting instead of applying (analyze.md section 1). The span table
    supplies the origin map, so every change comes back in DOCUMENT coordinates -- analyze.md
    section 6 names a runtime that reports span-local offsets here as the mistake that passes
    every text-mode test."""
    normalized = normalize_spans(spans)
    if not normalized:
        return []
    return run_rules_recording(
        concatenate_spans(source, normalized),
        plan,
        locale_data,
        ctx,
        origin_of_spans(source, normalized),
        len(source),
        lambda current, edits: filter_boundary_edits(current, edits, span_ranges_of(current)),
    )
