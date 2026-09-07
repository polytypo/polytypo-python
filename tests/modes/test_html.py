"""spec/rules/modes.md 3.6 -- HTML span extraction. Protects the round-trip guarantee (section 4)
and the skip-list (section 3.6) directly, at the span-extraction layer, not only end to end
through `polytypo.html.transform` (mirrors the spirit of polytypo-js's tests/modes/html.test.ts,
at reduced scope)."""

from __future__ import annotations

import polytypo.html
from polytypo._modes.html import html_spans
from polytypo._modes.spans import normalize_spans

ROUND_TRIP_SAMPLES = [
    'Tom &amp; Jerry\'s "book" &#x2014; a &nbsp;test & bare<b>bold &copy; text</b>',
    "<p>rock 'n' roll</p>",
    '"<p class="x">«[t](u)',
    "<CODE>a *b* c</CODE>after",
    "<pre><em>x</em></pre>tail",
    "line1\n<pre>code</pre>\nline3",
    "<svg><text>hi</text></svg>after",
    "<br>after<br/>more<hr>done",
    "unterminated <b>bold",
    "<!-- comment --> text <!DOCTYPE html> more",
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
        spans = normalize_spans(html_spans(source))
        assert _reassemble(source, spans) == source


def test_code_element_subtree_is_skipped_whole() -> None:
    out = polytypo.html.transform('<code>a *b* "c"</code>', locale="en-US")
    assert out == '<code>a *b* "c"</code>'


def test_unknown_custom_element_is_processable() -> None:
    # modes.md 3.6: the skip list is closed -- unknown elements are far more likely wrappers.
    out = polytypo.html.transform('<my-callout>Say "hi"</my-callout>', locale="en-US")
    assert out == "<my-callout>Say “hi”</my-callout>"


def test_character_reference_spelling_is_preserved() -> None:
    out = polytypo.html.transform('Tom &amp; Jerry\'s "book"', locale="en-US")
    assert "&amp;" in out
    assert out == "Tom &amp; Jerry’s “book”"


def test_svg_subtree_is_skipped() -> None:
    out = polytypo.html.transform('<svg><text>"a"</text></svg>', locale="en-US")
    assert out == '<svg><text>"a"</text></svg>'


def test_attribute_quoting_is_preserved() -> None:
    out = polytypo.html.transform('<p class=foo>"hi"</p>', locale="en-US")
    assert out.startswith("<p class=foo>")
