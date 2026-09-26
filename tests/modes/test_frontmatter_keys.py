"""modes.md 3.7.4 -- ``markdown`` mode's optional ``frontmatter_keys`` (spec 1.7.0) -- and
3.7.3a, which decides where the block it names begins and ends (spec 1.8.0).

The conformance fixtures cover what the option converts, and 3.7.3a's twelve locator cases cover
where the block is -- but every one of those sets no option, so none of them reaches the scan
this runtime now locates the block with. This file covers that, the two things a fixture cannot
express (3.7.4: the option throw, the ignored-elsewhere rule, the validation order), the claim
the section asks a port to test directly -- the option cannot change a byte outside the block,
because that block is a text unit of its own -- and the cost 3.7.3a removes: locating the block
no longer needs a parse of its own (polytypo/polytypo#59).
"""

from __future__ import annotations

from typing import Any

import pytest
import tree_sitter_markdown as tsm
from tree_sitter import Language, Parser

import polytypo
from polytypo._modes import markdown as markdown_mode
from polytypo._modes.markdown import (
    frontmatter_spans,
    locate_frontmatter,
    markdown_spans,
    mask_frontmatter,
)
from polytypo.errors import PolytypoError

DOC = '---\ntitle: He said "hello" once\nslug: "a - b"\n---\n\nBody "quotes" - here.\n'


def md(source: str, **options: Any) -> str:
    kwargs: dict[str, Any] = {"locale": "en-US", "mode": "markdown", "dialect": "commonmark"}
    kwargs.update(options)
    return polytypo.transform(source, **kwargs)


def code_of(source: str, **options: Any) -> str:
    try:
        polytypo.transform(source, **options)
    except PolytypoError as error:
        return error.code
    return "NO THROW"


class TestWhatItProcesses:
    def test_processes_a_listed_key_and_nothing_else_in_the_block(self) -> None:
        assert md(DOC, frontmatter_keys=["title"]) == (
            '---\ntitle: He said “hello” once\nslug: "a - b"\n---\n\nBody “quotes”—here.\n'
        )

    def test_absent_means_the_pre_1_7_0_skip(self) -> None:
        assert md(DOC) == (
            '---\ntitle: He said "hello" once\nslug: "a - b"\n---\n\nBody “quotes”—here.\n'
        )

    def test_empty_list_is_legal_and_yields_no_spans(self) -> None:
        assert md(DOC, frontmatter_keys=[]) == md(DOC)
        assert frontmatter_spans(DOC, "commonmark", frozenset()) == []

    def test_matches_a_bare_name_at_any_depth(self) -> None:
        nested = '---\nseo:\n  title: a "b"\ntitle: c "d"\nother:\n  slug: e "f"\n---\n\nx\n'
        assert md(nested, frontmatter_keys=["title"]) == (
            '---\nseo:\n  title: a “b”\ntitle: c “d”\nother:\n  slug: e "f"\n---\n\nx\n'
        )

    def test_leaves_a_toml_block_alone(self) -> None:
        toml = '+++\ntitle = "a - b"\n+++\n\nBody - here.\n'
        assert md(toml, frontmatter_keys=["title"]) == '+++\ntitle = "a - b"\n+++\n\nBody—here.\n'
        assert frontmatter_spans(toml, "commonmark", frozenset({"title"})) == []

    @pytest.mark.parametrize(
        "doc",
        ['---\ntitle: a "b"\n\nBody\n', '\n---\ntitle: a "b"\n---\n\nBody\n'],
        ids=["unterminated", "not-at-the-start"],
    )
    def test_adds_no_spans_where_there_is_no_block(self, doc: str) -> None:
        assert md(doc, frontmatter_keys=["title"]) == md(doc)
        assert frontmatter_spans(doc, "commonmark", frozenset({"title"})) == []

    def test_delimiters_and_line_terminators_stay_outside_every_span(self) -> None:
        crlf = '---\r\ntitle: a "b"\r\n---\r\n\r\nBody\r\n'
        spans = frontmatter_spans(crlf, "commonmark", frozenset({"title"}))
        assert [crlf[s.start : s.end] for s in spans] == ['a "b"']
        assert md(crlf, frontmatter_keys=["title"]) == (
            "---\r\ntitle: a “b”\r\n---\r\n\r\nBody\r\n"
        )


class TestItsOwnTextUnit:
    def test_an_unbalanced_mark_cannot_pair_across_the_block(self) -> None:
        doc = '---\ntitle: He said "hello\n---\n\nworld" she said\n'
        assert md(doc, frontmatter_keys=["title"]) == doc
        # The discriminator: as one unit those two marks do pair, which is what the rule refuses.
        assert polytypo.transform('title: He said "hello\n\nworld" she said\n', locale="en-US") == (
            "title: He said “hello\n\nworld” she said\n"
        )

    @pytest.mark.parametrize(
        "doc",
        [
            DOC,
            '---\ntitle: "x"\n---\n\nBody - one "two" three...\n',
            '---\nsummary: |\n  a - b\n  c - d\n---\n\nBody - e "f"...\n',
            '---\ntitle: a\n---\nAbutting body "x" - y\n',
        ],
    )
    @pytest.mark.parametrize("keys", [[], ["title"], ["title", "slug", "summary", "seo"]])
    def test_cannot_change_a_byte_outside_the_block(self, doc: str, keys: list[str]) -> None:
        # The block's own length can change, so the body is located in each result rather than at
        # one offset taken from the input.
        def body(source: str) -> str:
            return source[source.index("\n---", 3) + len("\n---") :]

        assert body(md(doc, frontmatter_keys=keys)) == body(md(doc))

    @pytest.mark.parametrize("locale", ["en-US", "de-DE", "fr", "ru"])
    def test_idempotent_under_its_own_options(self, locale: str) -> None:
        for doc in (DOC, '---\ntitle: a -- b "c"\nx: keep -- me\n---\n\nBody -- "d"\n'):
            once = md(doc, locale=locale, frontmatter_keys=["title", "summary"])
            assert md(once, locale=locale, frontmatter_keys=["title", "summary"]) == once


class TestValidation:
    @pytest.mark.parametrize("value", ["title", ["title", 7], 7, {"title": True}])
    def test_throws_the_general_option_code_when_not_a_sequence_of_strings(
        self, value: object
    ) -> None:
        assert (
            code_of(
                DOC,
                locale="en-US",
                mode="markdown",
                dialect="commonmark",
                frontmatter_keys=value,
            )
            == "POLYTYPO_INVALID_OPTION"
        )

    def test_is_checked_after_the_dialect(self) -> None:
        assert (
            code_of(DOC, locale="en-US", mode="markdown", frontmatter_keys="bad")
            == "POLYTYPO_INVALID_DIALECT"
        )
        assert (
            code_of(DOC, locale="en-US", mode="markdown", dialect="mdx", frontmatter_keys="bad")
            == "POLYTYPO_INVALID_DIALECT"
        )

    def test_is_ignored_and_unvalidated_in_the_other_modes(self) -> None:
        text = 'title: a "b"\n'
        assert code_of(text, locale="en-US", frontmatter_keys="bad") == "NO THROW"
        assert code_of(text, locale="en-US", mode="html", frontmatter_keys=["t"]) == "NO THROW"
        assert (
            code_of(text, locale="en-US", mode="yaml", keys=["title"], frontmatter_keys="bad")
            == "NO THROW"
        )
        assert polytypo.transform(text, locale="en-US", frontmatter_keys=["title"]) == (
            polytypo.transform(text, locale="en-US")
        )


#: 3.7.3a's own documents: the name, the document, whether the scan finds a block, and whether
#: `frontmatter_keys=["title", "x"]` then converts something inside it. The conformance suite
#: pins most of these, but every locator case there sets no option, so none of them reaches the
#: scan this runtime now locates the block with; the rest are edges no fixture reaches.
LOCATOR_CASES: list[tuple[str, str, bool, bool]] = [
    ("plain", '---\ntitle: a "b"\n---\n\nBody.\n', True, True),
    ("opener-trailing-space", '--- \ntitle: a "b"\n---\n\nBody.\n', True, True),
    ("closer-trailing-space", '---\ntitle: a "b"\n--- \n\nBody.\n', True, True),
    ("opener-trailing-tab", '---\t\ntitle: a "b"\n---\n\nBody.\n', True, True),
    ("closer-trailing-tab", '---\ntitle: a "b"\n---\t\n\nBody.\n', True, True),
    ("dots-closer", '---\ntitle: a "b"\n...\n\nBody.\n', False, False),
    ("after-blank-line", '\n---\ntitle: a "b"\n---\n\nBody.\n', False, False),
    ("opener-with-text", '--- yaml\ntitle: a "b"\n---\n\nBody.\n', False, False),
    ("opener-indented", ' ---\ntitle: a "b"\n---\n\nBody.\n', False, False),
    ("closer-indented", '---\ntitle: a "b"\n ---\n\nBody.\n', False, False),
    ("four-dashes", '----\ntitle: a "b"\n----\n\nBody.\n', False, False),
    ("mixed-delimiters", '---\ntitle: a "b"\n+++\n\nBody.\n', False, False),
    ("empty-block", "---\n---\n\nBody.\n", True, False),
    ("unterminated", '---\ntitle: a "b"\n\nBody.\n', False, False),
    ("only-an-opener", "--- \n", False, False),
    ("closer-at-eof", '---\ntitle: a "b"\n---', True, True),
    ("closer-at-eof-trailing-space", '---\ntitle: a "b"\n--- ', True, True),
    ("crlf", '---\r\ntitle: a "b"\r\n---\r\n\r\nBody.\r\n', True, True),
    ("final-cr-no-newline", '---\r\ntitle: a "b"\r\n---\r', True, True),
    # 3.7.4, spec 1.8.0: the block is found -- step 5's line model sees a lone U+000D -- and its
    # CONTENT is then declined outright, however few lines it has, because 3.8.4's LF-only scan
    # would read the whole block as one line. Measured before the rule existed: marks paired
    # across two mapping lines, `fr` spaced an unlisted line, and a U+000D landed inside a span.
    ("lone-cr-line-endings", '---\rtitle: a "b"\r---\r\rBody.\r', True, False),
    ("lone-cr-two-keys", '---\rtitle: a "b"\rslug: c-d\r---\r\rBody.\r', True, False),
    # A lone U+000D in a document with no block at all reaches the body walk like any other.
    ("lone-cr-no-block", 'Wait for it... he said "hi"\rand then "left".\r', False, False),
    ("byte-order-mark-no-block", '\ufeffWait for it... he said "hi"\n', False, False),
    # 3.7.3a: the mask is one U+0020 per index unit. This runtime indexes code points, so the
    # astral character costs one space; a byte-indexed runtime must spend three.
    (
        "astral-in-the-block",
        '---\ntitle: caf\u00e9 \U0001f600 it\u0027s ok\n---\n\nBody "q"...\n',
        True,
        True,
    ),
    ("byte-order-mark", '\ufeff---\ntitle: a "b"\n---\n\nBody.\n', True, True),
    ("byte-order-mark-trailing-space", '\ufeff--- \ntitle: a "b"\n---\n\nBody.\n', True, True),
    ("toml", '+++\ntitle = "a - b"\n+++\n\nBody.\n', True, False),
    ("toml-trailing-space", '+++ \ntitle = "a - b"\n+++\n\nBody.\n', True, False),
    (
        "masks-the-parser",
        '--- \nx: |\n  ```\n---\n\n```\ncode "q"\n```\n\nBody "q".\n',
        True,
        False,
    ),
]

NAMES = [case[0] for case in LOCATOR_CASES]

#: Measured against tree-sitter-markdown, not assumed. The parser claims a block on an opener
#: indented by one to three spaces, where 3.7.3a step 1 says there is none; the scan claims one
#: when the closing delimiter is the last line and carries no terminator, where the parser does
#: not. Everything else agrees -- including the three shapes step 5's line model added (a final
#: U+000D with no newline, lone-U+000D endings) and the byte-order mark of step 1, which is why
#: those clauses cost this runtime nothing.
KNOWN_DISAGREEMENTS = frozenset(
    {"opener-indented", "closer-at-eof", "closer-at-eof-trailing-space"}
)


class TestBlockExtent:
    """3.7.3a: the block's extent is the scan's, not the parser's."""

    @pytest.mark.parametrize(
        "doc,expected",
        [
            # The FIRST later delimiter line closes, not the last: `b` is body prose and
            # converts although the option never names it. Were the block the whole document,
            # `b` would be an unlisted key and would come back straight.
            (
                '---\na: said "x"\n---\nb: said "y"\n---\n',
                "---\na: said \u201cx\u201d\n---\nb: said \u201cy\u201d\n---\n",
            ),
            # A delimiter of the other kind is not a closer, so there is no block at all.
            ('---\na: said "x"\n+++\n', "---\na: said \u201cx\u201d\n+++\n"),
            # The closing line may be the last line of the document with no terminator at all,
            # which 3.7.3a step 5 admits and tree-sitter's frontmatter support does not.
            ('---\na: said "x"\n---', "---\na: said \u201cx\u201d\n---"),
            # 3.7.3a step 1: one leading U+FEFF is stepped over, and the content offsets are
            # taken from the line after the opener rather than from a fixed distance in.
            ('\ufeff--- \na: said "x"\n---\n', "\ufeff--- \na: said \u201cx\u201d\n---\n"),
        ],
        ids=[
            "first-closer-wins",
            "other-delimiter-is-not-a-closer",
            "closer-at-eof",
            "byte-order-mark-and-a-widened-opener",
        ],
    )
    def test_the_closer_is_the_first_matching_line(self, doc: str, expected: str) -> None:
        assert md(doc, frontmatter_keys=["a"]) == expected

    @pytest.mark.parametrize(
        "doc,has_block,converts",
        [(doc, has_block, converts) for _, doc, has_block, converts in LOCATOR_CASES],
        ids=NAMES,
    )
    def test_the_option_reaches_exactly_the_documents_the_scan_claims(
        self, doc: str, has_block: bool, converts: bool
    ) -> None:
        assert (locate_frontmatter(doc) is not None) == has_block
        assert (md(doc, frontmatter_keys=["title", "x"]) != md(doc)) == converts

    @pytest.mark.parametrize("doc", [doc for _, doc, _, _ in LOCATOR_CASES], ids=NAMES)
    def test_the_two_units_never_share_a_source_position(self, doc: str) -> None:
        """3.7.4: no source position can belong to both units. The body's spans come from
        tree-sitter over the masked document and the block's from the scan, so this is the
        property that would break first if the masking in `markdown_spans` were dropped."""
        block = locate_frontmatter(doc)
        body = markdown_spans(doc, "commonmark")
        inside = frontmatter_spans(doc, "commonmark", frozenset({"title", "x"}))
        if block is None:
            assert inside == []
            return
        assert all(span.start >= block.end for span in body)
        assert all(block.content_start <= s.start and s.end <= block.content_end for s in inside)

    def test_the_mask_keeps_offsets_and_line_terminators(self) -> None:
        doc = "\ufeff--- \nx: |\n  ```\r\n---\t\n\nBody.\n"
        block = locate_frontmatter(doc)
        assert block is not None
        masked = mask_frontmatter(doc, block)
        assert len(masked) == len(doc)
        assert masked[block.end :] == doc[block.end :]
        # 3.7.3a: the leading U+FEFF is masked with the block, although step 1 stepped over it.
        assert block.start == 1
        assert set(masked[: block.end]) <= {" ", "\n", "\r"}
        assert [i for i, ch in enumerate(masked) if ch in "\r\n"] == [
            i for i, ch in enumerate(doc) if ch in "\r\n"
        ]


class TestLoneCarriageReturnContent:
    """3.7.4, spec 1.8.0: a content LINE carrying a U+000D not followed by U+000A yields no spans.

    The witnesses are the ones measured before the rule existed, when the block was found by
    3.7.3a step 5's line model and its content read by 3.8.4's LF-only one. Each is a way the
    earlier "inert" reading was wrong, so each must now come back byte for byte -- and the last
    test is the other half of the rule: per line, so one dirty value does not cost the block."""

    @pytest.mark.parametrize(
        "doc,locale",
        [
            # A quotation opened on one mapping line paired with a mark on the next.
            ('---\rtitle: a "b\rc" d\r---\r\rBody.\r', "en-US"),
            # An unlisted line swallowed into the listed key's plain scalar took fr's spacing.
            ("---\rtitle: hello\rvrai ?\r---\r\rBody.\r", "fr"),
            # The U+000D itself lay inside a span, which 3.8.4 forbids.
            ("---\rtitle: a -- b\rplain-line\r---\r\rBody.\r", "en-US"),
            # And the one-line block, which converted until 1.8.0 made the rule about the
            # character rather than about a line count.
            ('---\rtitle: a "b"\r---\r', "en-US"),
        ],
        ids=[
            "pairs-across-mapping-lines",
            "fr-spaces-an-unlisted-line",
            "terminator-in-a-span",
            "one-line-block",
        ],
    )
    def test_the_block_is_declined_outright(self, doc: str, locale: str) -> None:
        assert frontmatter_spans(doc, "commonmark", frozenset({"title"})) == []
        assert md(doc, locale=locale, frontmatter_keys=["title"]) == md(doc, locale=locale)

    def test_it_costs_the_line_and_not_the_block(self) -> None:
        """The reason the rule is per line: a stray U+000D inside one quoted value is something
        people produce by accident, so it costs that value and the block's other keys convert."""
        doc = '---\ntitle: "a\rb"\nslug: c "d"\n---\n\nBody "q" here.\n'
        assert md(doc, frontmatter_keys=["title", "slug"]) == (
            '---\ntitle: "a\rb"\nslug: c \u201cd\u201d\n---\n\nBody \u201cq\u201d here.\n'
        )
        spans = frontmatter_spans(doc, "commonmark", frozenset({"title", "slug"}))
        assert [doc[s.start : s.end] for s in spans] == ['c "d"']

    def test_a_crlf_block_is_not_declined(self) -> None:
        """Only a U+000D the terminator does not account for. CRLF content is the shape 3.7.4's
        own CRLF case pins, and it must keep converting."""
        crlf = '---\r\ntitle: a "b"\r\nslug: "x"\r\n---\r\n\r\nBody.\r\n'
        assert [
            crlf[s.start : s.end]
            for s in frontmatter_spans(crlf, "commonmark", frozenset({"title"}))
        ] == ['a "b"']


class TestParserAgreement:
    """3.7.3a: "a runtime whose parser also recognises the construct must produce the same extent
    as this scan". tree-sitter-markdown does recognise it, so the agreement is measured here
    rather than assumed, and the shapes where it does not hold are named."""

    @staticmethod
    def parser_extent(doc: str) -> tuple[int, int] | None:
        tree = Parser(Language(tsm.language())).parse(doc.encode("utf-8"))
        offsets = markdown_mode._ByteOffsets(doc)
        for child in tree.root_node.children:
            if child.type in ("minus_metadata", "plus_metadata"):
                return offsets.char_of(child.start_byte), offsets.char_of(child.end_byte)
        return None

    @pytest.mark.parametrize(
        "name,doc", [(name, doc) for name, doc, _, _ in LOCATOR_CASES], ids=NAMES
    )
    def test_the_parser_agrees_with_the_scan_except_where_recorded(
        self, name: str, doc: str
    ) -> None:
        block = locate_frontmatter(doc)
        scanned = None if block is None else (block.start, block.end)
        assert (self.parser_extent(doc) == scanned) == (name not in KNOWN_DISAGREEMENTS)

    @pytest.mark.parametrize("doc", [doc for _, doc, _, _ in LOCATOR_CASES], ids=NAMES)
    def test_the_parser_never_sees_a_frontmatter_node(self, doc: str) -> None:
        """The invariant that lets `_BLOCK_SKIP_TYPES` drop the two metadata types: a located
        block is masked out, and a parser that claims one anyway is overruled by the reparse."""
        block = locate_frontmatter(doc)
        if block is not None:
            assert self.parser_extent(markdown_mode.mask_frontmatter(doc, block)) is None
        elif self.parser_extent(doc) is not None:
            assert self.parser_extent("\n" + doc) is None

    @pytest.mark.parametrize(
        "name,doc",
        [(n, d) for n, d, _, _ in LOCATOR_CASES if n in KNOWN_DISAGREEMENTS],
        ids=[n for n in NAMES if n in KNOWN_DISAGREEMENTS],
    )
    def test_the_scan_wins_where_they_disagree(self, name: str, doc: str) -> None:
        block = locate_frontmatter(doc)
        spans = markdown_spans(doc, "commonmark")
        if block is None:
            # The parser hid the metadata; 3.7.3a says it is prose, so it must be reachable.
            assert any(doc[span.start : span.end].strip().startswith("title") for span in spans)
        else:
            # The parser missed the block; 3.7.3a says it is one, so no body span may enter it.
            assert all(span.start >= block.end for span in spans)

    @pytest.mark.parametrize(
        "doc,expected",
        [
            # The two documents whose output moves with spec 1.8.0, with the option absent.
            ('---\nt: said "x"\n---', '---\nt: said "x"\n---'),
            (' ---\nt: said "x"\n---\n', " ---\nt: said \u201cx\u201d\n---\n"),
        ],
        ids=["closer-at-eof", "opener-indented"],
    )
    def test_the_documents_whose_output_moves(self, doc: str, expected: str) -> None:
        assert md(doc) == expected


class TestParseCount:
    """polytypo/polytypo#59, closed by 3.7.3a: locating the block is a scan, so the option no
    longer costs a second run of the block grammar. Counted rather than asserted from the source
    -- `Parser` is a C type, so the module-level name is what a spy can stand in for."""

    @staticmethod
    def block_parses(monkeypatch: pytest.MonkeyPatch, source: str, **options: Any) -> int:
        calls: list[object] = []
        real = Parser

        def counting_parser(language: Language) -> Parser:
            calls.append(language)
            return real(language)

        monkeypatch.setattr(markdown_mode, "Parser", counting_parser)
        md(source, **options)
        return sum(1 for language in calls if language is markdown_mode._BLOCK_LANGUAGE)

    def test_the_option_costs_no_extra_block_parse(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self.block_parses(monkeypatch, DOC) == 1
        assert self.block_parses(monkeypatch, DOC, frontmatter_keys=["title"]) == 1

    def test_a_document_with_no_block_at_all_parses_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plain = 'Body "quotes" here.\n'
        assert self.block_parses(monkeypatch, plain, frontmatter_keys=["title"]) == 1

    def test_only_a_parser_scan_disagreement_pays_for_a_second_parse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        indented = ' ---\ntitle: a "b"\n---\n\nBody.\n'
        assert self.block_parses(monkeypatch, indented, frontmatter_keys=["title"]) == 2


class TestAnalyze:
    def test_reports_both_units_in_document_offsets_in_order(self) -> None:
        changes = polytypo.analyze(
            DOC,
            locale="en-US",
            mode="markdown",
            dialect="commonmark",
            frontmatter_keys=["title"],
        )
        starts = [c.start for c in changes]
        assert len(changes) > 1
        assert starts == sorted(starts)
        assert starts[0] < DOC.index("\n---", 3)
        assert max(c.end for c in changes) <= len(DOC)
