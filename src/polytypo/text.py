"""``polytypo.text`` -- text-only entry point. Its module graph excludes `html.parser`-based
span extraction and tree-sitter entirely: it imports `_engine.mode_pipelines.run_text_pipeline`
directly and never touches `_modes.html` or `_modes.markdown` (mirrors polytypo-js's
`polytypo/text` subpath export and its module-graph-isolation rationale).

`mode` and `dialect` are absent from this entry's `transform` -- this module only ever runs
`text` mode, and `dialect` has no effect there even in the aggregate entry point."""

from __future__ import annotations

from collections.abc import Sequence

from polytypo._engine.mode_pipelines import analyze_text_pipeline, run_text_pipeline
from polytypo._engine.origin import Change
from polytypo.errors import PolytypoError

__all__ = ["Change", "PolytypoError", "analyze", "transform"]


def transform(
    input: str,
    *,
    locale: str,
    rules: dict[str, bool] | None = None,
    narrow_nbsp: str | None = None,
    protect: Sequence[Sequence[int]] | None = None,
) -> str:
    """`protect` is a sequence of `(start, end)` code-point ranges of `input`, half-open,
    ascending and non-overlapping, that are never edited (modes.md 3.9). `None` and `[]` are the
    same call. Any malformed value raises POLYTYPO_INVALID_OPTION."""
    return run_text_pipeline(
        input, locale=locale, rules=rules, narrow_nbsp=narrow_nbsp, protect=protect
    )


def analyze(
    input: str,
    *,
    locale: str,
    rules: dict[str, bool] | None = None,
    narrow_nbsp: str | None = None,
    protect: Sequence[Sequence[int]] | None = None,
) -> list[Change]:
    """The same pipeline as this entry's `transform`, reporting instead of applying
    (spec/rules/analyze.md). Offsets are code-point offsets into `input`."""
    return analyze_text_pipeline(
        input, locale=locale, rules=rules, narrow_nbsp=narrow_nbsp, protect=protect
    )
