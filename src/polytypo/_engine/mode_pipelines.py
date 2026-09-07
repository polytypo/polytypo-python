"""The three mode-specific top-level pipelines, one per public entry point
(`polytypo`/`polytypo.text`/`polytypo.html`/`polytypo.markdown`). Mirrors polytypo-js's
text-pipeline.ts/html-pipeline.ts/markdown-pipeline.ts split: each function imports only what its
mode needs, so `polytypo.text` never imports the HTML or Markdown parsers, and `polytypo.html`
never imports tree-sitter-markdown.

Validation order is public, tested behaviour and is identical across all three: `rules` (an
unknown rule id) before `locale` (an unknown locale) before `dialect`/parsing -- see
`pipeline.prepare`'s own docstring."""

from __future__ import annotations

from polytypo._engine.codepoints import from_codepoints, to_codepoints
from polytypo._engine.pipeline import prepare, run_rules
from polytypo._engine.registry import RuleContext
from polytypo._engine.span_runner import run_over_spans
from polytypo._modes.spans import normalize_spans


def run_text_pipeline(input_text: str, *, locale: object, rules: dict[str, bool] | None) -> str:
    resolved_locale, locale_data, plan = prepare(locale, rules)
    cp = to_codepoints(input_text)
    ctx: RuleContext = {"mode": "text", "dialect": None, "locale": resolved_locale}
    return from_codepoints(run_rules(cp, plan, locale_data, ctx))


def run_html_pipeline(input_text: str, *, locale: object, rules: dict[str, bool] | None) -> str:
    from polytypo._modes.html import html_spans

    resolved_locale, locale_data, plan = prepare(locale, rules)
    ctx: RuleContext = {"mode": "html", "dialect": None, "locale": resolved_locale}
    spans = normalize_spans(html_spans(input_text))
    return run_over_spans(input_text, spans, plan, locale_data, ctx)


def run_markdown_pipeline(
    input_text: str, *, locale: object, dialect: str | None, rules: dict[str, bool] | None
) -> str:
    from polytypo._modes.markdown import markdown_spans, resolve_dialect

    resolved_locale, locale_data, plan = prepare(locale, rules)
    resolve_dialect(dialect)
    ctx: RuleContext = {"mode": "markdown", "dialect": dialect, "locale": resolved_locale}
    spans = normalize_spans(markdown_spans(input_text, dialect))
    return run_over_spans(input_text, spans, plan, locale_data, ctx)
