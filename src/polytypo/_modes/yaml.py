"""spec/rules/modes.md 3.8. ``yaml`` differs from the other two document modes twice over.

It uses **no parser** (3.8.1): two of the five ecosystems' YAML libraries cannot report the source
offsets the round-trip guarantee needs, so the scan below is specified rather than delegated and
is written the same way in every runtime.

And the caller names the keys (3.8.2). YAML is a data format with islands of prose in it -- the
inverse of HTML and Markdown -- and nothing in its syntax separates ``description:`` from
``run:``. A keyless draft of this file rewrote ``if !`` as ``if!`` inside a workflow's shell
script; there is no content test that would not, because shell and template expressions are
written in words.

It also **skips by default** -- the inverse of 3.6's closed skip list. A construct this scan does
not recognise with certainty yields no spans, so the worst outcome of a gap in it is prose left
untypeset, never a changed byte."""

from __future__ import annotations

from dataclasses import dataclass

from polytypo._modes.spans import Span

TAB = "\t"
LF = "\n"
CR = "\r"
SPACE = " "


@dataclass(frozen=True, slots=True)
class Line:
    start: int
    #: Index of the line terminator, or of the end of the source -- never inside a span.
    end: int


def split_lines(source: str) -> list[Line]:
    """3.8.4: a line ends at U+000A, and **a U+000D immediately before it is not part of the
    line** -- it is a terminator like the U+000A itself, so it lies outside every span and comes
    back untouched. Without that clause a CRLF file behaves differently from the same bytes with
    LF: the block header reads as ``|\\r`` and is unrecognised, and a plain scalar carries the
    carriage return inside its span. Five runtimes split lines with five different standard-library
    calls, so the treatment has to be stated rather than inherited.

    Shared with `_modes.markdown` rather than private to this module: 3.7.4's per-line bail on a
    lone U+000D is defined in 3.8.4's line terms, so it has to ask 3.8.4's splitter rather than
    keep a second copy of this clause -- which is the drift 3.8.1 exists to prevent."""
    lines: list[Line] = []
    start = 0

    def end_of(i: int) -> int:
        return i - 1 if i > start and source[i - 1] == CR else i

    for i, ch in enumerate(source):
        if ch == LF:
            lines.append(Line(start, end_of(i)))
            start = i + 1
    if start < len(source):
        lines.append(Line(start, end_of(len(source))))
    return lines


def _first_non_space(source: str, line: Line) -> int:
    i = line.start
    while i < line.end and source[i] == SPACE:
        i += 1
    return i


def _is_blank(source: str, line: Line) -> bool:
    return _first_non_space(source, line) == line.end


def _has_tab(source: str, line: Line) -> bool:
    return TAB in source[line.start : line.end]


def _is_document_marker(source: str, from_: int, end: int) -> bool:
    """3.8.4 step 3. ``---`` and ``...`` at the head of a line, bare or introducing a node: the
    trailing-content form is declined too, so ``--- key: value`` never yields a key of
    ``--- key``."""
    if end - from_ < 3:
        return False
    c = source[from_]
    if c not in ("-", "."):
        return False
    if source[from_ + 1] != c or source[from_ + 2] != c:
        return False
    return from_ + 3 == end or source[from_ + 3] == SPACE


def _is_indicator_colon(source: str, j: int, end: int) -> bool:
    """A colon that ends the line or is followed by U+0020 -- the only colon YAML reads as an
    indicator."""
    if source[j] != ":":
        return False
    return j + 1 == end or source[j + 1] == SPACE


def _is_sequence_dash(source: str, j: int, end: int) -> bool:
    if source[j] != "-":
        return False
    return j + 1 == end or source[j + 1] == SPACE


def _value_run_end(source: str, lines: list[Line], li: int, indent: int) -> int:
    """The value run of 3.8.4 step 7: every following line that is blank or indented more than
    the key line. **Those lines are never scanned again** -- without that, a multi-line quoted
    scalar, a multi-line flow collection and a folded plain scalar all leak their continuation
    lines back into the scan as if they were mappings, and a span can end up holding a scalar's
    own closing delimiter."""
    k = li + 1
    while k < len(lines):
        nxt = lines[k]
        if not _is_blank(source, nxt) and _first_non_space(source, nxt) - nxt.start <= indent:
            break
        k += 1
    return k


def yaml_spans(source: str, keys: frozenset[str]) -> list[Span]:
    lines = split_lines(source)
    spans: list[Span] = []
    li = 0
    while li < len(lines):
        li = _scan_line(source, lines, li, keys, spans)
    return spans


def _scan_line(
    source: str, lines: list[Line], li: int, keys: frozenset[str], spans: list[Span]
) -> int:
    """One step of 3.8.4. Returns the index of the next line to scan."""
    line = lines[li]
    skip_line = li + 1

    # step 1 -- blank, or a tab anywhere, which makes indentation undecidable.
    start = _first_non_space(source, line)
    if start == line.end or _has_tab(source, line):
        return skip_line
    indent = start - line.start

    # steps 2 and 3 -- comment, directive, document marker.
    if source[start] in ("#", "%"):
        return skip_line
    if _is_document_marker(source, start, line.end):
        return skip_line

    # step 4 -- block sequence entries are consumed, not skipped; `- - key: v` nests.
    i = start
    while i < line.end and _is_sequence_dash(source, i, line.end):
        i += 2
        while i < line.end and source[i] == SPACE:
            i += 1
    if i >= line.end:
        return skip_line

    # step 5 -- find the key. A colon NOT followed by U+0020 or the line end is an ordinary key
    # character, so `a:b: v` has the key `a:b`; stating that is what keeps five scanners agreeing.
    key_start = i
    colon = -1
    for j in range(i, line.end):
        if source[j] in ('"', "'", "{", "[", "&", "*", "!", "#"):
            return skip_line
        if _is_indicator_colon(source, j, line.end):
            colon = j
            break
    if colon < 0:
        return skip_line
    key_end = colon
    while key_end > key_start and source[key_end - 1] == SPACE:
        key_end -= 1
    if key_end <= key_start:
        return skip_line

    # step 6 -- an empty value means a nested node, whose lines ARE scanned on their own.
    v = colon + 1
    while v < line.end and source[v] == SPACE:
        v += 1
    if v >= line.end:
        return skip_line

    # step 7 -- the line carries an inline value, so its continuation lines belong to that value.
    nxt = _value_run_end(source, lines, li, indent)

    # step 8 -- the key must be listed. Checked before the value's form, so an unlisted key costs
    # nothing to decline: this is what makes `run:`, `if:` and `image:` unreachable.
    if source[key_start:key_end] not in keys:
        return nxt

    # step 9 -- the scalar form.
    value = source[v]
    if value in ("#", "&", "*", "!", "{", "["):
        return nxt
    if value in ("|", ">"):
        _block_scalar(source, lines, li, nxt, indent, v, spans)
        return nxt
    if value in ('"', "'"):
        if nxt == li + 1:
            _quoted_scalar(source, line, v, spans)
        return nxt
    if nxt == li + 1:
        _plain_scalar(source, line, v, spans)
    return nxt


def _block_scalar(
    source: str,
    lines: list[Line],
    li: int,
    run_end: int,
    indent: int,
    v: int,
    spans: list[Span],
) -> None:
    """3.8.5. One span per non-blank content line, starting after the block's own indentation. The
    header, the indentation and every line terminator lie outside every span -- including the run
    of line terminators at the end that the chomping indicator governs, which is why ``|``, ``|-``,
    ``|+``, ``>``, ``>-`` and ``>+`` are handled identically here."""
    line = lines[li]

    # The header: at most one chomping indicator and at most one indentation indicator, in either
    # order, then optional spaces and an optional comment. Anything else is unrecognised.
    h = v + 1
    explicit_indent = 0
    chomping = False
    while h < line.end:
        c = source[h]
        if c in ("-", "+") and not chomping:
            chomping = True
            h += 1
            continue
        if "1" <= c <= "9" and explicit_indent == 0:
            explicit_indent = ord(c) - ord("0")
            h += 1
            continue
        break
    while h < line.end and source[h] == SPACE:
        h += 1
    if h < line.end and source[h] != "#":
        return

    # One definition of the run, and three conditions that make the whole block yield no spans.
    content: list[Line] = []
    content_indent = -1
    for k in range(li + 1, run_end):
        nxt = lines[k]
        if _is_blank(source, nxt):
            continue  # blank lines belong to the block and yield no span
        if _has_tab(source, nxt):
            return
        next_indent = _first_non_space(source, nxt) - nxt.start
        if content_indent < 0:
            content_indent = indent + explicit_indent if explicit_indent > 0 else next_indent
        # An explicit indicator that disagrees with the block as written, or a later line dedented
        # inside it, is ambiguous rather than guessable -- bail rather than choose.
        if next_indent < content_indent:
            return
        content.append(nxt)
    if content_indent <= 0:
        return

    for c_line in content:
        from_ = c_line.start + content_indent
        if c_line.end > from_:
            spans.append(Span(from_, c_line.end))


def _quoted_scalar(source: str, line: Line, v: int, spans: list[Span]) -> None:
    """3.8.6. The span is the content between the quotes. Both bails exist so that source
    characters and content characters are the same thing, which the offset model of 3.1 requires --
    the same constraint that makes an HTML character reference an opaque unit in 3.6. No colon test
    applies here: quoting neutralises the colon, and applying the plain-scalar test would decline
    ``title: "Chapter 1: the beginning"``."""
    quote = source[v]
    close = -1
    j = v + 1
    while j < line.end:
        c = source[j]
        if quote == '"' and c == "\\":
            return
        if quote == "'" and c == "'" and j + 1 < line.end and source[j + 1] == "'":
            return
        if c == quote:
            close = j
            break
        j += 1
    if close < 0:
        return

    after = close + 1
    while after < line.end and source[after] == SPACE:
        after += 1
    if after < line.end and source[after] != "#":
        return

    if close > v + 1:
        spans.append(Span(v + 1, close))


def _plain_scalar(source: str, line: Line, v: int, spans: list[Span]) -> None:
    """3.8.6. In a plain scalar ``:`` and ``#`` are still live: U+0020 beside either of them is
    what turns a scalar into a mapping indicator or a comment, and ``dashes`` emits U+0020 in every
    ``-spaced`` locale. Lifting both out as opaque units puts the dash token at a span extremity,
    where the edge-growth rule of 3.4 discards the replacement that emits one."""
    # The scalar ends before a trailing comment, so a colon inside that comment is not the
    # scalar's and must not decline it.
    end = line.end
    for j in range(v, line.end):
        if source[j] == "#" and j > v and source[j - 1] == SPACE:
            end = j - 1
            break
    while end > v and source[end - 1] == SPACE:
        end -= 1
    if end <= v:
        return

    # Compact nesting is not a value: `key: - item` opens a sequence, and `key: a .:` is a mapping
    # whose key is `a .` -- a plain scalar can never contain a colon in that position.
    if _is_sequence_dash(source, v, line.end):
        return
    for j in range(v, end):
        if _is_indicator_colon(source, j, line.end):
            return

    segment = v
    for j in range(v, end + 1):
        if j == end or source[j] in (":", "#"):
            if j > segment:
                spans.append(Span(segment, j))
            segment = j + 1
