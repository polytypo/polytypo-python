"""modes.md 3.7.4 -- ``markdown`` mode's optional ``frontmatter_keys`` (spec 1.7.0).

The conformance fixtures cover what the option converts. This file covers what a fixture cannot
express (3.7.4: the option throw, the ignored-elsewhere rule, the validation order) and the claim
the section asks a port to test directly: the option cannot change a byte outside the frontmatter
block, because that block is a text unit of its own.
"""

from __future__ import annotations

from typing import Any

import pytest

import polytypo
from polytypo._modes.markdown import frontmatter_spans
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
