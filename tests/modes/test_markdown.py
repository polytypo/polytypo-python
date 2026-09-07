"""spec/rules/modes.md 3.7 -- Markdown span extraction. Protects the round-trip guarantee, the
CommonMark+GFM skip list, and the dialect contract at the span-extraction layer (mirrors the
spirit of polytypo-js's tests/modes/markdown.test.ts, at reduced scope -- this runtime supports
only the "commonmark" dialect)."""

from __future__ import annotations

import pytest

import polytypo.markdown
from polytypo._modes.markdown import markdown_spans, resolve_dialect
from polytypo._modes.spans import normalize_spans
from polytypo.errors import PolytypoError

ROUND_TRIP_SAMPLES = [
    'Text *em* `code` \\* escape &amp; entity <https://x.com> [txt](url "ti") ~~strike~~ '
    "<code>a *b* c</code>\n",
    "---\ntitle: Test\n---\n\n# Heading one *em*\n\nBody.\n",
    "café «bonjour» *em*\n",
    'This is a long\nparagraph that wraps\nacross three lines with "quotes".\n',
    '<div class="x">\n  Body "text" inside.\n</div>\n\nAlso <b>"kept"</b> outside "here".\n',
    '![alt text](img.png "title")\n\n[shortcut]\n\n[collapsed][]\n\n[full][ref]\n',
    "\"He said *'hi'* loudly\"\n",
]


def _reassemble(source: str, spans) -> str:
    out = []
    cursor = 0
    for span in spans:
        out.append(source[cursor : span.start])
        out.append(source[span.start : span.end])
        cursor = span.end
    out.append(source[cursor:])
    return "".join(out)


def test_round_trip_guarantee_byte_identical() -> None:
    for source in ROUND_TRIP_SAMPLES:
        spans = normalize_spans(markdown_spans(source, "commonmark"))
        assert _reassemble(source, spans) == source


def test_dialect_is_required() -> None:
    with pytest.raises(PolytypoError) as excinfo:
        resolve_dialect(None)
    assert excinfo.value.code == "POLYTYPO_INVALID_DIALECT"


def test_mdx_dialect_is_not_supported() -> None:
    with pytest.raises(PolytypoError) as excinfo:
        resolve_dialect("mdx")
    assert excinfo.value.code == "POLYTYPO_INVALID_DIALECT"


def test_unknown_dialect_raises() -> None:
    with pytest.raises(PolytypoError) as excinfo:
        resolve_dialect("bogus")
    assert excinfo.value.code == "POLYTYPO_INVALID_DIALECT"


def test_fenced_code_block_is_skipped() -> None:
    out = polytypo.markdown.transform(
        '```js\nconst s = "raw";\n```\n', locale="en-US", dialect="commonmark"
    )
    assert out == '```js\nconst s = "raw";\n```\n'


def test_inline_code_span_is_skipped() -> None:
    out = polytypo.markdown.transform('Use `"raw"` here.\n', locale="en-US", dialect="commonmark")
    assert out == 'Use `"raw"` here.\n'


def test_link_text_is_processable_but_destination_is_not() -> None:
    out = polytypo.markdown.transform(
        '[te...xt](http://a...b "ti...tle")\n', locale="en-US", dialect="commonmark"
    )
    assert out == '[te…xt](http://a...b "ti...tle")\n'


def test_frontmatter_is_skipped() -> None:
    out = polytypo.markdown.transform(
        '---\ntitle: "Une note"\n---\n\nBody has "quotes" here.\n',
        locale="en-US",
        dialect="commonmark",
    )
    assert out == '---\ntitle: "Une note"\n---\n\nBody has “quotes” here.\n'


def test_html_block_content_is_typeset_but_markup_is_not() -> None:
    out = polytypo.markdown.transform(
        '<div class="x">\n  Body "text" inside.\n</div>\n', locale="en-US", dialect="commonmark"
    )
    assert out == '<div class="x">\n  Body “text” inside.\n</div>\n'
