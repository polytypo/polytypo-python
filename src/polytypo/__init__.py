"""polytypo -- locale-correct quotes, dashes, ellipses and no-break spaces.

The aggregate entry point. Its module graph includes every mode's dependencies (`html.parser`
and tree-sitter): it is the only pipeline module that imports all four mode-specific ones.
`polytypo.text`, `polytypo.html`, `polytypo.markdown` and `polytypo.yaml` each call their own
mode-specific pipeline directly and never import this module (mirrors polytypo-js's
`polytypo`/`polytypo/text`/`polytypo/html`/`polytypo/markdown`/`polytypo/yaml` split). `yaml`
needs no parser at all (modes.md 3.8.1), so it is the lightest of the four."""

from __future__ import annotations

from polytypo._engine.mode_pipelines import (
    analyze_html_pipeline,
    analyze_markdown_pipeline,
    analyze_text_pipeline,
    analyze_yaml_pipeline,
    run_html_pipeline,
    run_markdown_pipeline,
    run_text_pipeline,
    run_yaml_pipeline,
)
from polytypo._engine.origin import Change
from polytypo.errors import POLYTYPO_INVALID_MODE, PolytypoError

__all__ = ["Change", "PolytypoError", "analyze", "transform"]

__version__ = "0.0.0"


def _resolve_mode(mode: str | None) -> str:
    if mode is None or mode == "text":
        return "text"
    if mode in ("html", "markdown", "yaml"):
        return mode
    raise PolytypoError(
        POLYTYPO_INVALID_MODE,
        f'Unknown mode "{mode}". Expected "text", "html", "markdown" or "yaml".',
    )


def transform(
    input: str,
    *,
    locale: str,
    mode: str | None = None,
    dialect: str | None = None,
    keys: object = None,
    rules: dict[str, bool] | None = None,
    narrow_nbsp: str | None = None,
) -> str:
    """`narrow_nbsp="nbsp"` makes the engine emit U+00A0 everywhere it would emit U+202F
    (nbsp.md 3.1a). It moves the rule's target rather than post-processing the output, so the
    result stays a fixed point. Validation order is mode -> narrow_nbsp -> rules -> locale ->
    dialect -> keys, and the check runs whether or not `nbsp` is enabled.

    `keys` is required when `mode="yaml"` and ignored otherwise (modes.md 3.8.2): YAML is a data
    format with islands of prose in it, so the caller names the mapping keys whose values are
    prose and the library never guesses. An empty sequence is legal and processes nothing."""
    resolved_mode = _resolve_mode(mode)
    if resolved_mode == "text":
        return run_text_pipeline(input, locale=locale, rules=rules, narrow_nbsp=narrow_nbsp)
    if resolved_mode == "html":
        return run_html_pipeline(input, locale=locale, rules=rules, narrow_nbsp=narrow_nbsp)
    if resolved_mode == "yaml":
        return run_yaml_pipeline(
            input, locale=locale, keys=keys, rules=rules, narrow_nbsp=narrow_nbsp
        )
    return run_markdown_pipeline(
        input, locale=locale, dialect=dialect, rules=rules, narrow_nbsp=narrow_nbsp
    )


def analyze(
    input: str,
    *,
    locale: str,
    mode: str | None = None,
    dialect: str | None = None,
    keys: object = None,
    rules: dict[str, bool] | None = None,
    narrow_nbsp: str | None = None,
) -> list[Change]:
    """The same pipeline as `transform`, reporting what it would do instead of doing it
    (spec/rules/analyze.md). Offsets are code-point offsets into `input` in every mode.

    What it guarantees: the list is empty exactly when `transform` would return the input
    unchanged, every `rule_id` was enabled for the call, and every offset is inside the input.
    What it does not: the list is a report, not a patch -- two rules may touch the same original
    range, so replaying it is not guaranteed to reproduce `transform`'s output. Call `transform`
    for the text (analyze.md sections 4 and 5)."""
    resolved_mode = _resolve_mode(mode)
    if resolved_mode == "text":
        return analyze_text_pipeline(input, locale=locale, rules=rules, narrow_nbsp=narrow_nbsp)
    if resolved_mode == "html":
        return analyze_html_pipeline(input, locale=locale, rules=rules, narrow_nbsp=narrow_nbsp)
    if resolved_mode == "yaml":
        return analyze_yaml_pipeline(
            input, locale=locale, keys=keys, rules=rules, narrow_nbsp=narrow_nbsp
        )
    return analyze_markdown_pipeline(
        input, locale=locale, dialect=dialect, rules=rules, narrow_nbsp=narrow_nbsp
    )
