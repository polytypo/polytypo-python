"""``polytypo.text`` -- text-only entry point. Its module graph excludes `html.parser`-based
span extraction and tree-sitter entirely: it imports `_engine.mode_pipelines.run_text_pipeline`
directly and never touches `_modes.html` or `_modes.markdown` (mirrors polytypo-js's
`polytypo/text` subpath export and its module-graph-isolation rationale).

`mode` and `dialect` are absent from this entry's `transform` -- this module only ever runs
`text` mode, and `dialect` has no effect there even in the aggregate entry point."""

from __future__ import annotations

from polytypo._engine.mode_pipelines import run_text_pipeline
from polytypo.errors import PolytypoError

__all__ = ["PolytypoError", "transform"]


def transform(input: str, *, locale: str, rules: dict[str, bool] | None = None) -> str:
    return run_text_pipeline(input, locale=locale, rules=rules)
