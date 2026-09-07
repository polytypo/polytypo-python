"""polytypo -- locale-correct quotes, dashes, ellipses and no-break spaces.

The aggregate entry point. Its module graph includes every mode's dependencies (`html.parser`
and tree-sitter): it is the only pipeline module that imports all three mode-specific ones.
`polytypo.text`, `polytypo.html` and `polytypo.markdown` each call their own mode-specific
pipeline directly and never import this module (mirrors polytypo-js's `polytypo`/`polytypo/text`
/`polytypo/html`/`polytypo/markdown` split)."""

from __future__ import annotations

from polytypo._engine.mode_pipelines import (
    run_html_pipeline,
    run_markdown_pipeline,
    run_text_pipeline,
)
from polytypo.errors import POLYTYPO_INVALID_MODE, PolytypoError

__all__ = ["PolytypoError", "transform"]

__version__ = "0.0.0"


def _resolve_mode(mode: str | None) -> str:
    if mode is None or mode == "text":
        return "text"
    if mode in ("html", "markdown"):
        return mode
    raise PolytypoError(
        POLYTYPO_INVALID_MODE, f'Unknown mode "{mode}". Expected "text", "html" or "markdown".'
    )


def transform(
    input: str,
    *,
    locale: str,
    mode: str | None = None,
    dialect: str | None = None,
    rules: dict[str, bool] | None = None,
) -> str:
    resolved_mode = _resolve_mode(mode)
    if resolved_mode == "text":
        return run_text_pipeline(input, locale=locale, rules=rules)
    if resolved_mode == "html":
        return run_html_pipeline(input, locale=locale, rules=rules)
    return run_markdown_pipeline(input, locale=locale, dialect=dialect, rules=rules)
