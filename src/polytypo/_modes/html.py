"""spec/rules/modes.md 3.6 -- HTML span extraction via stdlib `html.parser.HTMLParser`
(SAX-style; no external dependency, per this project's minimal-footprint choice for this port).

The parser is used only to locate spans and is then discarded (modes.md 4: "the document is
never serialised"). We never touch attributes, tag syntax, or entity spelling -- `handle_data`
only fires for actual text-node content (with `convert_charrefs=False`, entity/character
references are reported as separate `handle_entityref`/`handle_charref` callbacks with their own
position, so a text span never includes one; we simply do not emit a span for them, which leaves
their exact source spelling in the untouched gap between two data spans -- the only way `&nbsp;`
survives as `&nbsp;` rather than becoming a literal U+00A0 and back).
"""

from __future__ import annotations

from html.parser import HTMLParser

from polytypo._modes.parse_error import wrap_parser_errors
from polytypo._modes.spans import Span

# modes.md 3.6, exhaustive and CLOSED: extending it is a spec change, not an implementation
# decision. `svg`/`math` are here because in MathML a quotation mark, a hyphen and a prime are
# operators and identifiers -- substituting a curly glyph changes what the expression means.
# Everything else is processable, including unknown and custom elements.
SKIPPED_ELEMENTS = frozenset(
    {"code", "pre", "kbd", "samp", "var", "script", "style", "textarea", "svg", "math"}
)

# HTML5 void elements: never pushed onto the element stack, since most authors never close them
# and html.parser calls handle_endtag only for an explicit closing tag or a self-closing `/>`
# (handled via the default handle_startendtag -> handle_starttag + handle_endtag combinator).
# None of them are skip-listed, so this never affects skip tracking, only stack hygiene.
VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


def _line_start_offsets(source: str) -> list[int]:
    """HTMLParser.getpos() counts lines by counting `\\n` alone (see _markupbase.updatepos), so
    line starts must be computed the same way, not via str.splitlines() (which also splits on
    \\v, \\f, U+2028, etc. and would desync)."""
    offsets = [0]
    for line in source.split("\n")[:-1]:
        offsets.append(offsets[-1] + len(line) + 1)
    return offsets


class _SpanCollector(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self._source = source
        self._line_starts = _line_start_offsets(source)
        self.spans: list[Span] = []
        self._stack: list[str] = []
        self._skip_depth = 0

    def _offset(self) -> int:
        line, col = self.getpos()
        return self._line_starts[line - 1] + col

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in VOID_ELEMENTS:
            return
        self._stack.append(tag)
        if tag in SKIPPED_ELEMENTS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag not in self._stack:
            return
        idx = len(self._stack) - 1 - self._stack[::-1].index(tag)
        popped = self._stack[idx:]
        del self._stack[idx:]
        self._skip_depth -= sum(1 for name in popped if name in SKIPPED_ELEMENTS)

    def handle_data(self, data: str) -> None:
        if self._skip_depth != 0 or not data:
            return
        start = self._offset()
        self.spans.append(Span(start, start + len(data)))


def html_spans(source: str) -> list[Span]:
    """Locate the processable spans of an HTML document."""
    collector = _SpanCollector(source)

    def run() -> _SpanCollector:
        collector.feed(source)
        collector.close()
        return collector

    wrap_parser_errors("HTML", run)
    return collector.spans
