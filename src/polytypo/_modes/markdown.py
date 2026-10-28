"""spec/rules/modes.md 3.7 -- Markdown span extraction, CommonMark + GFM only. `dialect="mdx"`
raises POLYTYPO_INVALID_DIALECT: this runtime has no MDX/JSX parser, which the spec permits (a
narrower conformance claim, not a silent mishandling of a dialect it claims to support).

Uses tree-sitter-markdown, whose block AND inline grammars report byte-accurate source ranges for
every construct 3.7.3 needs to distinguish -- the property modes.md 4 requires ("a runtime whose
parser cannot report source offsets cannot implement html mode conformantly" applies identically
here). A token-tree library such as markdown-it-py was tried first and rejected: it gives no
absolute offsets for inline tokens (only [start_line, end_line] on block tokens), and its `text`
token content is already escape/entity-decoded, both of which break modes.md 4's round-trip
guarantee outright rather than merely complicating it.

Architecture: the block grammar and the inline grammar are two separate parsers. The block tree
identifies each `inline` leaf's byte range (one block's worth of prose, e.g. one paragraph); that
slice is re-parsed with the dedicated inline grammar to find code spans, links, autolinks,
entities, emphasis delimiters, and raw inline HTML tags within it. This mirrors how editors drive
tree-sitter-markdown via language injection; we do the same slice-and-reparse by hand.
"""

from __future__ import annotations

import unicodedata
from bisect import bisect_right
from dataclasses import dataclass, field

import tree_sitter_markdown as _tsm
from tree_sitter import Language, Node, Parser

from polytypo._modes.html import SKIPPED_ELEMENTS as _HTML_SKIPPED_ELEMENTS
from polytypo._modes.html import html_spans
from polytypo._modes.parse_error import wrap_parser_errors
from polytypo._modes.spans import Span, normalize_spans
from polytypo._modes.yaml import split_lines
from polytypo.errors import POLYTYPO_INVALID_DIALECT, PolytypoError

_BLOCK_LANGUAGE = Language(_tsm.language())
_INLINE_LANGUAGE = Language(_tsm.inline_language())


def resolve_dialect(dialect: str | None) -> None:
    """modes.md 3.7.1: `dialect` is required, has no default, and is never detected."""
    if dialect is None:
        raise PolytypoError(
            POLYTYPO_INVALID_DIALECT,
            'Mode "markdown" requires a dialect. This runtime supports "commonmark"; '
            "there is no default.",
        )
    if dialect == "mdx":
        raise PolytypoError(
            POLYTYPO_INVALID_DIALECT,
            'Dialect "mdx" is not supported by this runtime (no MDX/JSX parser available). '
            'Only "commonmark" is supported.',
        )
    if dialect != "commonmark":
        raise PolytypoError(
            POLYTYPO_INVALID_DIALECT,
            f'Unknown dialect {dialect!r}. This runtime supports "commonmark".',
        )


class _ByteOffsets:
    """tree-sitter reports UTF-8 byte offsets; every other layer of this engine indexes Python
    str code points (ARCHITECTURE.md 4.2's array-of-code-points discipline, applied here for the
    reason it exists elsewhere: an index that means one thing in one representation and another
    in a second is exactly the class of bug that discipline exists to rule out). `char_of`
    converts once per span endpoint via a precomputed prefix-sum table."""

    def __init__(self, source: str) -> None:
        starts = [0]
        for ch in source:
            starts.append(starts[-1] + len(ch.encode("utf-8")))
        self._byte_starts = starts

    def char_of(self, byte_offset: int) -> int:
        return bisect_right(self._byte_starts, byte_offset) - 1


# Global (anywhere in an inline tree): a whole subtree that is never processable.
_INLINE_SKIP_TYPES = frozenset(
    {
        "code_span",
        "backslash_escape",
        "entity_reference",
        "numeric_character_reference",
        "uri_autolink",
        "email_autolink",
        "link_destination",
        "link_title",
        "link_label",
        "emphasis_delimiter",
    }
)

# Containers whose only processable child is the label field; every other child (brackets, "!",
# link_destination/title/label) is skipped whole without its own type-by-type check.
_LINK_FAMILY_TYPES = frozenset(
    {"image", "inline_link", "shortcut_link", "collapsed_reference_link", "full_reference_link"}
)
_LABEL_FIELD_TYPES = frozenset({"link_text", "image_description"})


@dataclass(frozen=True, slots=True)
class _Labels:
    """The labels a document defines, normalised as CommonMark 4.7 matches them (modes.md 3.7.3,
    spec 1.17.2): ``references`` for `[label]: destination`, ``footnotes`` for `[^label]:`."""

    references: frozenset[str] = frozenset()
    footnotes: frozenset[str] = frozenset()


_NO_LABELS = _Labels()


def _normalize_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def _footnote_label_at(text: str) -> str | None:
    """The label of a footnote definition opening `text` -- ``[^label]:`` with no whitespace or
    bracket in the label -- or None."""
    if not text.startswith("[^"):
        return None
    close = text.find("]", 2)
    if close < 3 or text[close + 1 : close + 2] != ":":
        return None
    label = text[2:close]
    if any(ch.isspace() or ch == "[" for ch in label):
        return None
    return label


def _collect_labels(root: Node, source_bytes: bytes) -> _Labels:
    references: set[str] = set()
    footnotes: set[str] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "link_reference_definition":
            label = next((c for c in node.children if c.type == "link_label"), None)
            if label is not None:
                text = source_bytes[label.start_byte + 1 : label.end_byte - 1].decode("utf-8")
                if text.startswith("^"):
                    footnotes.add(_normalize_label(text[1:]))
                else:
                    references.add(_normalize_label(text))
            continue
        if node.type == "paragraph":
            text = source_bytes[node.start_byte : node.end_byte].decode("utf-8")
            footnote = _footnote_label_at(text)
            if footnote is not None:
                footnotes.add(_normalize_label(footnote))
        stack.extend(node.children)
    return _Labels(frozenset(references), frozenset(footnotes))


@dataclass
class _WalkState:
    source: str
    offsets: _ByteOffsets
    base_byte_offset: int
    labels: _Labels
    slice_bytes: bytes
    #: The slice is a whole paragraph, so a footnote definition label can start it.
    is_block_start: bool = False
    spans: list[Span] = field(default_factory=list)
    html_stack: list[str] = field(default_factory=list)


def _emit(state: _WalkState, start_byte: int, end_byte: int) -> None:
    if state.html_stack or end_byte <= start_byte:
        return
    a = state.offsets.char_of(state.base_byte_offset + start_byte)
    b = state.offsets.char_of(state.base_byte_offset + end_byte)
    state.spans.append(Span(a, b))


def _read_tag(raw: str) -> tuple[str, bool, bool] | None:
    """Parses "<name ...>", "</name>" or "<name .../>" into (name, closing, self_closing).
    Comments/declarations/processing instructions ("<!--", "<!", "<?") have no element name."""
    if not raw.startswith("<"):
        return None
    i = 1
    closing = i < len(raw) and raw[i] == "/"
    if closing:
        i += 1
    if i >= len(raw) or raw[i] in "!?":
        return None
    if not ("a" <= raw[i].lower() <= "z"):
        return None
    name_start = i
    while i < len(raw) and raw[i] not in ">/ \t\n\r":
        i += 1
    name = raw[name_start:i].lower()
    self_closing = raw.rstrip().endswith("/>")
    return name, closing, self_closing


def _handle_html_tag(state: _WalkState, node: Node, slice_text: str) -> None:
    """modes.md 3.7.3: inline raw HTML arrives as isolated tags with Markdown between them, so
    the html skip list's subtree rule is a stack of open skipped elements, pushed on a start tag
    and popped on its matching end tag -- not a tree walk, since there isn't one here."""
    raw = slice_text[node.start_byte : node.end_byte]
    parsed = _read_tag(raw)
    if parsed is None:
        return
    name, closing, self_closing = parsed
    if closing:
        if state.html_stack and state.html_stack[-1] == name:
            state.html_stack.pop()
        return
    if not self_closing and name in _HTML_SKIPPED_ELEMENTS:
        state.html_stack.append(name)


def _walk_children_with_gaps(
    state: _WalkState, node: Node, slice_text: str, literal_delimiters: bool = False
) -> None:
    cursor = node.start_byte
    for child in node.children:
        if child.start_byte > cursor:
            _emit(state, cursor, child.start_byte)
        if literal_delimiters and child.type == "emphasis_delimiter":
            _emit(state, child.start_byte, child.end_byte)
        else:
            _walk(state, child, slice_text)
        cursor = child.end_byte
    if node.end_byte > cursor:
        _emit(state, cursor, node.end_byte)


_RESOURCE_OR_LABEL = frozenset({"link_label", "link_destination", "("})


def _is_reference_label(state: _WalkState, node: Node) -> bool:
    """modes.md 3.7.3 (spec 1.17.2): the text of a shortcut or collapsed reference is the label it
    is matched by, and so is a footnote call's or definition's label. A bracketed run no
    definition answers to, and a full reference, are prose. The parser forms a shortcut or
    collapsed run from any brackets, so the definitions are consulted here; an image has no
    separate node for the two, and is told apart by having no label or resource child."""
    if node.type in ("inline_link", "full_reference_link"):
        return False
    if any(child.type in _RESOURCE_OR_LABEL for child in node.children):
        return False
    label = next((child for child in node.children if child.type in _LABEL_FIELD_TYPES), None)
    if label is None:
        return False
    text = state.slice_bytes[label.start_byte : label.end_byte].decode("utf-8")
    if text.startswith("^"):
        if state.is_block_start and node.start_byte == 0:
            following = state.slice_bytes[node.end_byte : node.end_byte + 1]
            if following == b":" and _footnote_label_at("[" + text + "]:") is not None:
                return True
        return _normalize_label(text[1:]) in state.labels.footnotes
    return _normalize_label(text) in state.labels.references


def _is_punctuation(ch: str) -> bool:
    return unicodedata.category(ch)[0] in "PS"


def _is_flanking(state: _WalkState, delimiter: Node, closing: bool) -> bool:
    """CommonMark 6.2's left- (opening) or right-flanking (closing) test for the delimiter run
    `delimiter`. The start and end of the slice count as whitespace."""
    data = state.slice_bytes
    before = data[max(0, delimiter.start_byte - 4) : delimiter.start_byte]
    after = data[delimiter.end_byte : delimiter.end_byte + 4]
    prev = before.decode("utf-8", errors="ignore")[-1:] or " "
    nxt = after.decode("utf-8", errors="ignore")[:1] or " "
    inner, outer = (prev, nxt) if closing else (nxt, prev)
    if inner.isspace():
        return False
    return not _is_punctuation(inner) or outer.isspace() or _is_punctuation(outer)


def _is_valid_strikethrough(state: _WalkState, node: Node) -> bool:
    """tree-sitter-markdown pairs `~` runs without CommonMark's flanking test (measured:
    `~25 et «~25` closes on a tilde that follows a guillemet and precedes a digit, which no GFM
    parser pairs). Such a pair is literal text, the same as the unpaired tildes the other parsers
    leave, and is walked as text so the delimiter-neighbour rule (modes.md 3.4) sees the same
    document they do."""
    delimiters = [child for child in node.children if child.type == "emphasis_delimiter"]
    if len(delimiters) < 2:
        return True
    return _is_flanking(state, delimiters[0], closing=False) and _is_flanking(
        state, delimiters[-1], closing=True
    )


def _walk(state: _WalkState, node: Node, slice_text: str) -> None:
    node_type = node.type
    if node_type == "strikethrough" and not _is_valid_strikethrough(state, node):
        _walk_children_with_gaps(state, node, slice_text, literal_delimiters=True)
        return
    if node_type in _INLINE_SKIP_TYPES:
        return
    if node_type == "html_tag":
        _handle_html_tag(state, node, slice_text)
        return
    if node_type in _LINK_FAMILY_TYPES:
        if _is_reference_label(state, node):
            return
        for child in node.children:
            if child.type in _LABEL_FIELD_TYPES:
                _walk_children_with_gaps(state, child, slice_text)
        return
    _walk_children_with_gaps(state, node, slice_text)


def _inline_spans(
    source: str,
    offsets: _ByteOffsets,
    source_bytes: bytes,
    start_byte: int,
    end_byte: int,
    labels: _Labels,
    is_block_start: bool,
) -> list[Span]:
    parser = Parser(_INLINE_LANGUAGE)
    slice_bytes = source_bytes[start_byte:end_byte]
    tree = parser.parse(slice_bytes)
    state = _WalkState(
        source=source,
        offsets=offsets,
        base_byte_offset=start_byte,
        labels=labels,
        slice_bytes=slice_bytes,
        is_block_start=is_block_start,
    )
    slice_text = slice_bytes.decode("utf-8")
    _walk_children_with_gaps(state, tree.root_node, slice_text)
    return state.spans


# Block-level constructs that are never processable, in full (modes.md 3.7.3): fenced/indented
# code, reference-link definitions (the whole line, unlike an inline link where the *text* is
# processable), and thematic breaks (no prose content).
#
# Frontmatter is deliberately NOT here. Spec 1.8.0 makes 3.7.3a's scan the block's only
# authority and masks the block out of the parser's input, so a document reaching this walk has
# no `minus_metadata`/`plus_metadata` node -- `markdown_spans` reparses any that still does.
# Both node types are childless leaves (measured), so listing them changed no span either way;
# they are dropped because two authorities on one construct is what 1.8.0 removed, and the
# reparse, not this list, is what makes an opener indented by one to three spaces come back as
# the prose 3.7.3a step 1 says it is.
_BLOCK_SKIP_TYPES = frozenset(
    {
        "indented_code_block",
        "fenced_code_block",
        "link_reference_definition",
        "thematic_break",
    }
)


def _walk_block(
    spans: list[Span],
    source: str,
    offsets: _ByteOffsets,
    source_bytes: bytes,
    node: Node,
    labels: _Labels,
) -> None:
    node_type = node.type
    if node_type in _BLOCK_SKIP_TYPES:
        return
    if node_type == "html_block":
        # modes.md 3.7.3: "handed to the html extractor rather than skipped whole" -- the prose
        # inside `<div>...</div>` is typeset, the markup is not.
        text = source_bytes[node.start_byte : node.end_byte].decode("utf-8")
        char_offset = offsets.char_of(node.start_byte)
        for span in html_spans(text):
            spans.append(Span(char_offset + span.start, char_offset + span.end))
        return
    if node_type == "inline":
        spans.extend(
            _inline_spans(
                source, offsets, source_bytes, node.start_byte, node.end_byte, labels, True
            )
        )
        return
    if node_type == "pipe_table_cell":
        # GFM: table pipes and the delimiter row are structural (modes.md 3.7.3); cell content
        # is ordinary prose and may itself contain inline constructs.
        spans.extend(
            _inline_spans(
                source, offsets, source_bytes, node.start_byte, node.end_byte, labels, False
            )
        )
        return
    if node_type == "pipe_table_delimiter_row":
        return
    for child in node.children:
        _walk_block(spans, source, offsets, source_bytes, child, labels)


YAML_DELIMITER = "---"
TOML_DELIMITER = "+++"
BYTE_ORDER_MARK = "\ufeff"
CARRIAGE_RETURN = "\r"
_DELIMITER_WHITESPACE = frozenset({" ", "\t"})
_MASK = " "


@dataclass(frozen=True, slots=True)
class Frontmatter:
    """The extent of a frontmatter block, in code-point offsets into the document."""

    delimiter: str
    #: The opening delimiter's first code point: 0, or 1 past a leading U+FEFF (3.7.3a step 1).
    start: int
    #: First code point after the opening delimiter line's terminator (3.7.4).
    content_start: int
    #: The code point that begins the closing delimiter line (3.7.4).
    content_end: int
    #: End of the closing delimiter line's terminator -- the first code point of the body.
    end: int


def _line_at(source: str, start: int) -> tuple[int, int]:
    """3.7.3a step 5: **the Markdown document's line model, deliberately not 3.8.4's.** A line
    ends at U+000A, at a U+000D not followed by U+000A, or at the end of input, and the
    terminator is never part of the line. So a file whose last line is `---` followed by U+000D
    closes its block, and a document written with lone U+000D endings has one at all -- both of
    which a literal reading of 3.8.4's LF-only model loses, handing the metadata to the rules.

    The content *inside* the block keeps 3.8.4's model, because that half is YAML. The two are
    different on purpose and a port that harmonises them has silently changed one of them.

    Returns the line's end and the start of the next one, which are the same index at the end of
    the input."""
    n = len(source)
    i = start
    while i < n:
        if source[i] == "\n":
            return i, i + 1
        if source[i] == "\r":
            return i, i + (2 if i + 1 < n and source[i + 1] == "\n" else 1)
        i += 1
    return n, n


def _is_delimiter_line(source: str, start: int, end: int, delimiter: str) -> bool:
    """3.7.3a steps 2 and 3: the line's first code point begins the delimiter and the rest of the
    line is U+0020 and U+0009 only. Indentation disqualifies it (the comparison starts at the
    line's own first code point), and a fourth delimiter character is not whitespace, so `----`
    is neither an opener nor a closer."""
    if end - start < len(delimiter) or source[start : start + len(delimiter)] != delimiter:
        return False
    return all(source[i] in _DELIMITER_WHITESPACE for i in range(start + len(delimiter), end))


def locate_frontmatter(source: str) -> Frontmatter | None:
    """modes.md 3.7.3a, spec 1.8.0. **The block's extent is decided by this scan, not by a
    parser's frontmatter support.** Until 1.8.0 each runtime reached the construct through its
    own parser extension -- four extensions, two answers on a delimiter line carrying one
    trailing space, and the two runtimes that read it as prose handed `date: "2026-09-26"` to
    the rules. The scan is now what a fixture pins and what a disagreement is measured against,
    which is why this runtime's tree-sitter opinion is overruled rather than trusted
    (`markdown_spans`).

    It runs on every `markdown` call, so it stops at the first line when that line is not a
    delimiter -- which is every document that has no frontmatter -- and at the closing line when
    it is."""
    start = len(BYTE_ORDER_MARK) if source.startswith(BYTE_ORDER_MARK) else 0
    opener_end, content_start = _line_at(source, start)
    for candidate in (YAML_DELIMITER, TOML_DELIMITER):
        if _is_delimiter_line(source, start, opener_end, candidate):
            delimiter = candidate
            break
    else:
        return None
    line_start = content_start
    while line_start < len(source):
        line_end, next_start = _line_at(source, line_start)
        if _is_delimiter_line(source, line_start, line_end, delimiter):
            return Frontmatter(delimiter, start, content_start, line_start, next_start)
        line_start = next_start
    return None


def mask_frontmatter(source: str, block: Frontmatter) -> str:
    """3.7.3a: **the parser is handed the block masked out** -- the block replaced by U+0020,
    line terminators kept as they are, so nothing inside it can form or close a construct in the
    body.

    Suppressing spans inside the block's range instead is not enough, and the runtime that did
    that is measured in 3.7.3a: a fenced-code line inside a metadata value pairs with the body's
    own fence, and the body's code block and its prose swap places. No span-level check can see
    it, because the damage is in what the parser concluded.

    **One U+0020 per index unit**, which for this runtime is per code point, because every offset
    here is a Python str index and tree-sitter's byte offsets are converted through
    `_ByteOffsets` rather than used raw. A byte-indexed runtime must emit one space per byte
    instead, or masking an astral character shortens its input by three and shifts every body
    offset after it.

    The **leading U+FEFF of step 1 is masked with the block**, although the scan stepped over it
    rather than counting it in: a first line of U+FEFF followed by spaces is not blank and no
    parser is required to strip the mark, so a runtime masking the block alone emits a span for
    it. tree-sitter-markdown happens not to -- measured, both ways give the same spans here --
    which is exactly why the rule is the spec's and not this runtime's observation."""
    return (
        "".join(ch if ch in ("\n", "\r") else _MASK for ch in source[: block.end])
        + source[block.end :]
    )


def _declined_content_lines(content: str) -> list[tuple[int, int]]:
    """3.7.4, spec 1.8.0: **a line of the block's content carrying a U+000D not followed by
    U+000A yields no spans**, exactly as 3.8.4 step 1 already declines a line containing U+0009.

    Per line rather than per block: a stray U+000D inside one quoted value is something people
    produce by accident and costs that value, not the block. A lone-U+000D document is one
    3.8.4 line, so it still loses everything -- which is the price of not widening 3.8.4, a
    change that would reach `yaml` mode for every caller."""
    lines = split_lines(content)
    declined: list[tuple[int, int]] = []
    for position, line in enumerate(lines):
        # Up to the NEXT line's start, not to `line.end`: 3.8.4's splitter reads a U+000D at the
        # very end of its input as a terminator even with no U+000A after it, and for a block's
        # content that trailing U+000D is precisely the character this bail is about -- it is what
        # makes a whole lone-U+000D block look like one clean line.
        until = lines[position + 1].start if position + 1 < len(lines) else len(content)
        index = content.find(CARRIAGE_RETURN, line.start, until)
        while index >= 0:
            if index + 1 >= len(content) or content[index + 1] != "\n":
                declined.append((line.start, until))
                break
            index = content.find(CARRIAGE_RETURN, index + 1, until)
    return declined


def frontmatter_spans(source: str, dialect: str | None, keys: frozenset[str]) -> list[Span]:
    """modes.md 3.7.4, spec 1.7.0. The frontmatter block's own spans, which form a **second text
    unit**: the pipeline runs over them separately from the body's, so an unbalanced mark in a
    metadata field can never pair with one in the first paragraph, and the option cannot change a
    byte outside the block.

    The block is located by 3.7.3a's scan (spec 1.8.0), which is also what the body's parser
    input is masked by, so no source position can belong to both units. Locating it needs no
    parse: before 1.8.0 this function ran the block grammar a second time purely to find the
    node (polytypo/polytypo#59).

    Spans inside it come from the scan of modes.md 3.8 -- frontmatter *is* YAML, and implementing
    that grammar twice is how two implementations of one spec drift -- with ``keys`` as step 8's
    key predicate. A TOML block yields nothing, with the option or without it: its quoting is a
    second grammar this scan does not claim (modes.md 7.13).

    **A content line carrying a U+000D not followed by U+000A yields no spans either** (spec
    1.8.0). That is where the two line models meet and fail to compose:
    3.7.3a step 5 finds the block in a lone-U+000D document and 3.8.4's LF-only scan then reads
    the whole block as one line. Measured, the result is not merely inert -- marks pair across
    two mapping lines, an unlisted line inside the listed key's scalar takes `fr`'s spacing, and
    the U+000D lands inside a span, which 3.8.4 forbids in the same breath."""
    from polytypo._modes.yaml import yaml_spans

    if not keys:
        return []
    block = locate_frontmatter(source)
    if block is None or block.delimiter != YAML_DELIMITER:
        return []
    base = block.content_start
    content = source[block.content_start : block.content_end]
    declined = _declined_content_lines(content)
    return [
        Span(span.start + base, span.end + base)
        for span in yaml_spans(content, keys)
        if not any(span.start < end and start < span.end for start, end in declined)
    ]


def _has_metadata_node(root: Node) -> bool:
    return any(child.type in ("minus_metadata", "plus_metadata") for child in root.children)


def _parse(source_bytes: bytes) -> Node:
    def run() -> Node:
        parser = Parser(_BLOCK_LANGUAGE)
        return parser.parse(source_bytes).root_node

    return wrap_parser_errors("CommonMark", run)


def _walked_spans(source: str) -> list[Span]:
    source_bytes = source.encode("utf-8")
    spans: list[Span] = []
    root = _parse(source_bytes)
    labels = _collect_labels(root, source_bytes)
    _walk_block(spans, source, _ByteOffsets(source), source_bytes, root, labels)
    return spans


_URL_PREFIXES = ("www.", "http://", "https://")
_URL_TERMINATORS = frozenset(" \t\n\r<")
_URL_TAIL_GUARD = frozenset(" \t")


def _starts_url(source: str, i: int, end: int) -> bool:
    """ASCII case-insensitive, with no test on the character before `i` (modes.md 3.7.3)."""
    for prefix in _URL_PREFIXES:
        stop = i + len(prefix)
        if stop > end:
            continue
        if all(
            (ord(c) | 0x20 if "A" <= c <= "Z" else ord(c)) == ord(want)
            for c, want in zip(source[i:stop], prefix, strict=True)
        ):
            return True
    return False


def _trim_url_tails(source: str, spans: list[Span]) -> list[Span]:
    """modes.md 3.7.3 (spec 1.17.2): the tail of a bare web address, found by scanning the source
    of each maximal span rather than asking the parser, which this one does not do for GFM
    autolink literals at all. The piece that follows an address ending at U+0020 or U+0009 is
    marked, so an edit at its first code point cannot swallow the terminator."""
    out: list[Span] = []
    for span in spans:
        from_ = span.start
        i = span.start
        guard = span.url_tail
        while i < span.end:
            if not _starts_url(source, i, span.end):
                i += 1
                continue
            e = i
            while e < span.end and source[e] not in _URL_TERMINATORS:
                e += 1
            if i > from_:
                out.append(Span(from_, i, guard))
            guard = e < span.end and source[e] in _URL_TAIL_GUARD
            from_ = e
            i = e
        if from_ < span.end:
            out.append(Span(from_, span.end, guard))
    return out


def markdown_spans(source: str, dialect: str | None) -> list[Span]:
    """Locate the processable spans of a Markdown document. `resolve_dialect` must be called by
    the caller before this (it raises before any parsing is attempted for an unsupported
    dialect); this function assumes `dialect == "commonmark"`.

    3.7.3a (spec 1.8.0) decides the frontmatter block twice over: `locate_frontmatter` owns its
    extent, and the parser is handed that extent masked out rather than trusted to find it. A
    masked document has no frontmatter node at all, which is why tree-sitter's own
    `minus_metadata`/`plus_metadata` no longer appears in `_BLOCK_SKIP_TYPES` -- one authority on
    the block, not two.

    Where tree-sitter claims a block the scan rejects -- an opener indented by one to three
    spaces is the one shape left -- its opinion is removed the only way a parser with no options
    allows: one leading U+000A, so offset 0 is not a delimiter and no extension can claim
    anything. That is the only document this runtime parses twice, and by 3.7.3a's reading it has
    no frontmatter to parse.

    The block's own offsets are then dropped from the result. That is 3.7.3a's second
    requirement rather than a workaround for this parser -- "no span may lie inside the block,
    whatever the parser did with the masked text". The mask keeps the parse undeformed; the drop
    keeps the spans right where the mask is not enough, and here it is not: tree-sitter reads a
    final line of spaces with no terminator as a paragraph, so `---\\ntitle: a\\n---` comes back
    with a span over its own closing delimiter. goldmark does not, and Go removed its equivalent
    -- which is why the spec states the outcome and leaves the mechanism to each runtime."""
    block = locate_frontmatter(source)
    parser_input = source if block is None else mask_frontmatter(source, block)
    source_bytes = parser_input.encode("utf-8")
    root = _parse(source_bytes)
    if _has_metadata_node(root):
        spans = [Span(s.start - 1, s.end - 1) for s in _walked_spans("\n" + parser_input)]
    else:
        spans = []
        labels = _collect_labels(root, source_bytes)
        _walk_block(spans, parser_input, _ByteOffsets(parser_input), source_bytes, root, labels)
    spans = _trim_url_tails(parser_input, normalize_spans(spans))
    if block is None:
        return spans
    return [
        Span(max(span.start, block.end), span.end, span.url_tail)
        for span in spans
        if span.end > block.end
    ]
