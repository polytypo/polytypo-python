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

from bisect import bisect_right
from dataclasses import dataclass, field

import tree_sitter_markdown as _tsm
from tree_sitter import Language, Node, Parser

from polytypo._modes.html import SKIPPED_ELEMENTS as _HTML_SKIPPED_ELEMENTS
from polytypo._modes.html import html_spans
from polytypo._modes.parse_error import wrap_parser_errors
from polytypo._modes.spans import Span
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


@dataclass
class _WalkState:
    source: str
    offsets: _ByteOffsets
    base_byte_offset: int
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


def _walk_children_with_gaps(state: _WalkState, node: Node, slice_text: str) -> None:
    cursor = node.start_byte
    for child in node.children:
        if child.start_byte > cursor:
            _emit(state, cursor, child.start_byte)
        _walk(state, child, slice_text)
        cursor = child.end_byte
    if node.end_byte > cursor:
        _emit(state, cursor, node.end_byte)


def _walk(state: _WalkState, node: Node, slice_text: str) -> None:
    node_type = node.type
    if node_type in _INLINE_SKIP_TYPES:
        return
    if node_type == "html_tag":
        _handle_html_tag(state, node, slice_text)
        return
    if node_type in _LINK_FAMILY_TYPES:
        for child in node.children:
            if child.type in _LABEL_FIELD_TYPES:
                _walk_children_with_gaps(state, child, slice_text)
        return
    _walk_children_with_gaps(state, node, slice_text)


def _inline_spans(
    source: str, offsets: _ByteOffsets, source_bytes: bytes, start_byte: int, end_byte: int
) -> list[Span]:
    parser = Parser(_INLINE_LANGUAGE)
    slice_bytes = source_bytes[start_byte:end_byte]
    tree = parser.parse(slice_bytes)
    state = _WalkState(source=source, offsets=offsets, base_byte_offset=start_byte)
    slice_text = slice_bytes.decode("utf-8")
    _walk_children_with_gaps(state, tree.root_node, slice_text)
    return state.spans


# Block-level constructs that are never processable, in full (modes.md 3.7.3): frontmatter,
# fenced/indented code, reference-link definitions (the whole line, unlike an inline link where
# the *text* is processable), and thematic breaks (no prose content).
_BLOCK_SKIP_TYPES = frozenset(
    {
        "minus_metadata",
        "plus_metadata",
        "indented_code_block",
        "fenced_code_block",
        "link_reference_definition",
        "thematic_break",
    }
)


def _walk_block(
    spans: list[Span], source: str, offsets: _ByteOffsets, source_bytes: bytes, node: Node
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
        spans.extend(_inline_spans(source, offsets, source_bytes, node.start_byte, node.end_byte))
        return
    if node_type == "pipe_table_cell":
        # GFM: table pipes and the delimiter row are structural (modes.md 3.7.3); cell content
        # is ordinary prose and may itself contain inline constructs.
        spans.extend(_inline_spans(source, offsets, source_bytes, node.start_byte, node.end_byte))
        return
    if node_type == "pipe_table_delimiter_row":
        return
    for child in node.children:
        _walk_block(spans, source, offsets, source_bytes, child)


def markdown_spans(source: str, dialect: str | None) -> list[Span]:
    """Locate the processable spans of a Markdown document. `resolve_dialect` must be called by
    the caller before this (it raises before any parsing is attempted for an unsupported
    dialect); this function assumes `dialect == "commonmark"`."""
    source_bytes = source.encode("utf-8")
    offsets = _ByteOffsets(source)

    def run() -> Node:
        parser = Parser(_BLOCK_LANGUAGE)
        return parser.parse(source_bytes).root_node

    root = wrap_parser_errors("CommonMark", run)
    spans: list[Span] = []
    _walk_block(spans, source, offsets, source_bytes, root)
    return spans
