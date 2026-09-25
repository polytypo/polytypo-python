"""``polytypo.markdown`` -- Markdown-only entry point. Its module graph includes tree-sitter and
`html.parser` (the latter via `_modes.markdown` importing `_modes.html` for normative embedded
-HTML handling, modes.md 3.7) -- both are legitimately reachable here (mirrors polytypo-js's
`polytypo/markdown` subpath export and its module-graph-isolation rationale). It imports
`_engine.mode_pipelines.run_markdown_pipeline` directly and never touches the aggregate
`polytypo` module.

`mode` is absent from this entry's `transform` -- this module only ever runs `markdown` mode.
`dialect` keeps the aggregate entry's contract: required, no default. This runtime supports only
``"commonmark"``; ``dialect="mdx"`` raises ``POLYTYPO_INVALID_DIALECT`` (no MDX/JSX parser)."""

from __future__ import annotations

from polytypo._engine.mode_pipelines import analyze_markdown_pipeline, run_markdown_pipeline
from polytypo._engine.origin import Change
from polytypo.errors import PolytypoError

__all__ = ["Change", "PolytypoError", "analyze", "transform"]


def transform(
    input: str,
    *,
    locale: str,
    dialect: str,
    rules: dict[str, bool] | None = None,
    narrow_nbsp: str | None = None,
    frontmatter_keys: object = None,
) -> str:
    return run_markdown_pipeline(
        input,
        locale=locale,
        dialect=dialect,
        rules=rules,
        narrow_nbsp=narrow_nbsp,
        frontmatter_keys=frontmatter_keys,
    )


def analyze(
    input: str,
    *,
    locale: str,
    dialect: str,
    rules: dict[str, bool] | None = None,
    narrow_nbsp: str | None = None,
    frontmatter_keys: object = None,
) -> list[Change]:
    """The same pipeline as this entry's `transform`, reporting instead of applying
    (spec/rules/analyze.md). Offsets are code-point offsets into the **document**, not into a
    span (analyze.md section 2)."""
    return analyze_markdown_pipeline(
        input,
        locale=locale,
        dialect=dialect,
        rules=rules,
        narrow_nbsp=narrow_nbsp,
        frontmatter_keys=frontmatter_keys,
    )
