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


_HTML_WHITESPACE = frozenset("\t\n\f\r ")
_LINE_BREAKS = frozenset("\n\f\r")


def _is_line_break_whitespace(data: str) -> bool:
    return all(ch in _HTML_WHITESPACE for ch in data) and any(ch in _LINE_BREAKS for ch in data)


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
        self._pieces: list[Span] = []
        self._run_start: int | None = None

    def _offset(self) -> int:
        line, col = self.getpos()
        return self._line_starts[line - 1] + col

    def _flush(self, end: int) -> None:
        """Close the text run that ends at source offset `end`. modes.md 3.6: a run between two
        pieces of markup is judged on its raw source, so a character reference inside it is never
        whitespace and a run holding a line break plus only whitespace is not a span."""
        pieces, run_start = self._pieces, self._run_start
        self._pieces, self._run_start = [], None
        if run_start is None or not pieces:
            return
        if _is_line_break_whitespace(self._source[run_start:end]):
            return
        self.spans.extend(pieces)

    def _begin_run(self) -> bool:
        if self._skip_depth != 0:
            return False
        if self._run_start is None:
            self._run_start = self._offset()
        return True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._flush(self._offset())
        if tag in VOID_ELEMENTS:
            return
        self._stack.append(tag)
        if tag in SKIPPED_ELEMENTS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        self._flush(self._offset())
        if tag not in self._stack:
            return
        idx = len(self._stack) - 1 - self._stack[::-1].index(tag)
        popped = self._stack[idx:]
        del self._stack[idx:]
        self._skip_depth -= sum(1 for name in popped if name in SKIPPED_ELEMENTS)

    def handle_comment(self, data: str) -> None:
        self._flush(self._offset())

    def handle_decl(self, decl: str) -> None:
        self._flush(self._offset())

    def handle_pi(self, data: str) -> None:
        self._flush(self._offset())

    def unknown_decl(self, data: str) -> None:
        self._flush(self._offset())

    def handle_charref(self, name: str) -> None:
        self._begin_run()

    def handle_entityref(self, name: str) -> None:
        self._begin_run()

    def handle_data(self, data: str) -> None:
        if not data or not self._begin_run():
            return
        start = self._offset()
        self._pieces.append(Span(start, start + len(data)))


def html_spans(source: str) -> list[Span]:
    """Locate the processable spans of an HTML document."""
    collector = _SpanCollector(source)

    def run() -> _SpanCollector:
        collector.feed(source)
        collector.close()
        collector._flush(len(source))
        return collector

    wrap_parser_errors("HTML", run)
    return collector.spans
