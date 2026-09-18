"""``polytypo.html`` -- HTML-only entry point. Its module graph includes `html.parser` (stdlib)
but excludes tree-sitter entirely: it imports `_engine.mode_pipelines.run_html_pipeline`
directly and never touches `_modes.markdown` (mirrors polytypo-js's `polytypo/html` subpath
export and its module-graph-isolation rationale).

`mode` and `dialect` are absent from this entry's `transform` -- this module only ever runs
`html` mode, and `dialect` has no effect there even in the aggregate entry point."""

from __future__ import annotations

from polytypo._engine.mode_pipelines import analyze_html_pipeline, run_html_pipeline
from polytypo._engine.origin import Change
from polytypo.errors import PolytypoError

__all__ = ["Change", "PolytypoError", "analyze", "transform"]


def transform(input: str, *, locale: str, rules: dict[str, bool] | None = None) -> str:
    return run_html_pipeline(input, locale=locale, rules=rules)


def analyze(input: str, *, locale: str, rules: dict[str, bool] | None = None) -> list[Change]:
    """The same pipeline as this entry's `transform`, reporting instead of applying
    (spec/rules/analyze.md). Offsets are code-point offsets into the **document**, not into a
    span (analyze.md section 2)."""
    return analyze_html_pipeline(input, locale=locale, rules=rules)
