"""``polytypo.html`` -- HTML-only entry point. Its module graph includes `html.parser` (stdlib)
but excludes tree-sitter entirely: it imports `_engine.mode_pipelines.run_html_pipeline`
directly and never touches `_modes.markdown` (mirrors polytypo-js's `polytypo/html` subpath
export and its module-graph-isolation rationale).

`mode` and `dialect` are absent from this entry's `transform` -- this module only ever runs
`html` mode, and `dialect` has no effect there even in the aggregate entry point."""

from __future__ import annotations

from polytypo._engine.mode_pipelines import run_html_pipeline
from polytypo.errors import PolytypoError

__all__ = ["PolytypoError", "transform"]


def transform(input: str, *, locale: str, rules: dict[str, bool] | None = None) -> str:
    return run_html_pipeline(input, locale=locale, rules=rules)
