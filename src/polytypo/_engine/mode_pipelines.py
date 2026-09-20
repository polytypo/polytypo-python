"""The four mode-specific top-level pipelines, one per public entry point
(`polytypo` and `polytypo.text`/`.html`/`.markdown`/`.yaml`). Mirrors polytypo-js's
text-pipeline.ts/html-pipeline.ts/markdown-pipeline.ts split: each function imports only what its
mode needs, so `polytypo.text` never imports the HTML or Markdown parsers, and `polytypo.html`
never imports tree-sitter-markdown.

Validation order is public, tested behaviour and is identical across all four: `rules` (an
unknown rule id) before `locale` (an unknown locale) before `dialect`/`keys`/parsing -- see
`pipeline.prepare`'s own docstring."""

from __future__ import annotations

from polytypo._engine.codepoints import from_codepoints, to_codepoints
from polytypo._engine.narrow_target import resolve_narrow_target
from polytypo._engine.origin import Change
from polytypo._engine.pipeline import prepare, run_rules, run_rules_recording
from polytypo._engine.registry import RuleContext
from polytypo._engine.span_runner import analyze_over_spans, run_over_spans
from polytypo._engine.yaml_keys import resolve_yaml_keys
from polytypo._modes.spans import normalize_spans


def run_text_pipeline(
    input_text: str,
    *,
    locale: object,
    rules: dict[str, bool] | None,
    narrow_nbsp: str | None = None,
) -> str:
    narrow_target = resolve_narrow_target(narrow_nbsp)
    resolved_locale, locale_data, plan = prepare(locale, rules)
    cp = to_codepoints(input_text)
    ctx: RuleContext = {
        "mode": "text",
        "dialect": None,
        "locale": resolved_locale,
        "narrow_target": narrow_target,
    }
    return from_codepoints(run_rules(cp, plan, locale_data, ctx))


def run_html_pipeline(
    input_text: str,
    *,
    locale: object,
    rules: dict[str, bool] | None,
    narrow_nbsp: str | None = None,
) -> str:
    from polytypo._modes.html import html_spans

    narrow_target = resolve_narrow_target(narrow_nbsp)
    resolved_locale, locale_data, plan = prepare(locale, rules)
    ctx: RuleContext = {
        "mode": "html",
        "dialect": None,
        "locale": resolved_locale,
        "narrow_target": narrow_target,
    }
    spans = normalize_spans(html_spans(input_text))
    return run_over_spans(input_text, spans, plan, locale_data, ctx)


def run_markdown_pipeline(
    input_text: str,
    *,
    locale: object,
    dialect: str | None,
    rules: dict[str, bool] | None,
    narrow_nbsp: str | None = None,
) -> str:
    from polytypo._modes.markdown import markdown_spans, resolve_dialect

    narrow_target = resolve_narrow_target(narrow_nbsp)
    resolved_locale, locale_data, plan = prepare(locale, rules)
    resolve_dialect(dialect)
    ctx: RuleContext = {
        "mode": "markdown",
        "dialect": dialect,
        "locale": resolved_locale,
        "narrow_target": narrow_target,
    }
    spans = normalize_spans(markdown_spans(input_text, dialect))
    return run_over_spans(input_text, spans, plan, locale_data, ctx)


def run_yaml_pipeline(
    input_text: str,
    *,
    locale: object,
    keys: object,
    rules: dict[str, bool] | None,
    narrow_nbsp: str | None = None,
) -> str:
    """`yaml` mode only, and the only mode pipeline with **no parser dependency at all** -- span
    selection is the specified scan of modes.md 3.8, not a library. There is likewise no
    POLYTYPO_MALFORMED_INPUT counterpart here: with no declared grammar to violate, a file that is
    not YAML yields few spans or none and comes back byte for byte (modes.md 3.8.3). The only
    throw this mode adds is `keys`, which is about the call and not the input."""
    from polytypo._modes.yaml import yaml_spans

    narrow_target = resolve_narrow_target(narrow_nbsp)
    resolved_locale, locale_data, plan = prepare(locale, rules)
    resolved_keys = resolve_yaml_keys(keys)
    ctx: RuleContext = {
        "mode": "yaml",
        "dialect": None,
        "locale": resolved_locale,
        "narrow_target": narrow_target,
    }
    spans = normalize_spans(yaml_spans(input_text, resolved_keys))
    return run_over_spans(input_text, spans, plan, locale_data, ctx)


def analyze_text_pipeline(
    input_text: str,
    *,
    locale: object,
    rules: dict[str, bool] | None,
    narrow_nbsp: str | None = None,
) -> list[Change]:
    """analyze.md section 1: the same pipeline as `run_text_pipeline`, reporting instead of
    applying."""
    narrow_target = resolve_narrow_target(narrow_nbsp)
    resolved_locale, locale_data, plan = prepare(locale, rules)
    cp = to_codepoints(input_text)
    ctx: RuleContext = {
        "mode": "text",
        "dialect": None,
        "locale": resolved_locale,
        "narrow_target": narrow_target,
    }
    return run_rules_recording(cp, plan, locale_data, ctx, list(range(len(cp))), len(cp))


def analyze_html_pipeline(
    input_text: str,
    *,
    locale: object,
    rules: dict[str, bool] | None,
    narrow_nbsp: str | None = None,
) -> list[Change]:
    """analyze.md section 1, `html` mode: offsets are into the document, not into a span
    (analyze.md section 6)."""
    from polytypo._modes.html import html_spans

    narrow_target = resolve_narrow_target(narrow_nbsp)
    resolved_locale, locale_data, plan = prepare(locale, rules)
    ctx: RuleContext = {
        "mode": "html",
        "dialect": None,
        "locale": resolved_locale,
        "narrow_target": narrow_target,
    }
    spans = normalize_spans(html_spans(input_text))
    return analyze_over_spans(input_text, spans, plan, locale_data, ctx)


def analyze_markdown_pipeline(
    input_text: str,
    *,
    locale: object,
    dialect: str | None,
    rules: dict[str, bool] | None,
    narrow_nbsp: str | None = None,
) -> list[Change]:
    """analyze.md section 1, `markdown` mode. Dialect validation happens here exactly as it does
    for `run_markdown_pipeline`, so an absent or unsupported dialect raises
    POLYTYPO_INVALID_DIALECT from `analyze` too (analyze.md section 4, A1)."""
    from polytypo._modes.markdown import markdown_spans, resolve_dialect

    narrow_target = resolve_narrow_target(narrow_nbsp)
    resolved_locale, locale_data, plan = prepare(locale, rules)
    resolve_dialect(dialect)
    ctx: RuleContext = {
        "mode": "markdown",
        "dialect": dialect,
        "locale": resolved_locale,
        "narrow_target": narrow_target,
    }
    spans = normalize_spans(markdown_spans(input_text, dialect))
    return analyze_over_spans(input_text, spans, plan, locale_data, ctx)


def analyze_yaml_pipeline(
    input_text: str,
    *,
    locale: object,
    keys: object,
    rules: dict[str, bool] | None,
    narrow_nbsp: str | None = None,
) -> list[Change]:
    """analyze.md section 1, `yaml` mode: offsets are into the document, not into a span
    (analyze.md section 6)."""
    from polytypo._modes.yaml import yaml_spans

    narrow_target = resolve_narrow_target(narrow_nbsp)
    resolved_locale, locale_data, plan = prepare(locale, rules)
    resolved_keys = resolve_yaml_keys(keys)
    ctx: RuleContext = {
        "mode": "yaml",
        "dialect": None,
        "locale": resolved_locale,
        "narrow_target": narrow_target,
    }
    spans = normalize_spans(yaml_spans(input_text, resolved_keys))
    return analyze_over_spans(input_text, spans, plan, locale_data, ctx)
