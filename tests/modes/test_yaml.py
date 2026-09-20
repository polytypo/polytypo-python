"""spec/rules/modes.md 3.8 -- the `yaml` mode's span selection, its required `keys` option, and
the accepted misses of section 7.11. Mirrors polytypo-js's tests/modes/yaml.test.ts: the scan is
specified rather than delegated (3.8.1), so a test here is one of the few things standing between
five hand-written scanners and five different answers."""

from __future__ import annotations

import pytest

import polytypo
from polytypo._modes.yaml import yaml_spans
from polytypo.errors import PolytypoError

PROSE_KEYS = ["description", "summary", "title", "a", "b", "c", "k", "n", "inner", "use"]


def yaml(source: str, locale: str = "en-US", keys: list[str] | None = None) -> str:
    return polytypo.transform(
        source, locale=locale, mode="yaml", keys=PROSE_KEYS if keys is None else keys
    )


def span_text(source: str, keys: list[str] | None = None) -> list[str]:
    chosen = frozenset(PROSE_KEYS if keys is None else keys)
    return [source[s.start : s.end] for s in yaml_spans(source, chosen)]


class TestKeysOption:
    """modes.md 3.8.2."""

    def test_is_required_with_no_default(self) -> None:
        def code_of(**kwargs: object) -> str:
            try:
                polytypo.transform("a: one two\n", **kwargs)  # type: ignore[arg-type]
            except PolytypoError as error:
                return error.code
            return "NO THROW"

        assert code_of(locale="en-US", mode="yaml") == "POLYTYPO_INVALID_OPTION"
        assert code_of(locale="en-US", mode="yaml", keys="description") == "POLYTYPO_INVALID_OPTION"
        assert code_of(locale="en-US", mode="yaml", keys=["ok", 7]) == "POLYTYPO_INVALID_OPTION"

    def test_empty_list_is_legal_and_processes_nothing(self) -> None:
        assert yaml("description: one...two\n", keys=[]) == "description: one...two\n"

    def test_processes_a_listed_key_and_leaves_an_unlisted_one(self) -> None:
        source = "description: one...two\nrun: three...four\n"
        assert yaml(source, keys=["description"]) == "description: one…two\nrun: three...four\n"

    def test_matches_at_any_depth(self) -> None:
        source = "description: one...\nnested:\n  description: two...\n"
        assert (
            yaml(source, keys=["description"])
            == "description: one…\nnested:\n  description: two…\n"
        )

    def test_matches_code_point_for_code_point_with_no_case_folding(self) -> None:
        assert span_text("Description: one two\n", keys=["description"]) == []
        assert span_text("Description: one two\n", keys=["Description"]) == ["one two"]

    def test_ignores_trailing_spaces_before_the_colon(self) -> None:
        assert span_text("description  : one two\n", keys=["description"]) == ["one two"]

    def test_never_matches_a_key_carrying_a_declining_character(self) -> None:
        assert span_text('"description": one two\n', keys=["description"]) == []
        assert span_text("a!b: one two\n", keys=["a!b"]) == []

    def test_a_colon_not_followed_by_a_space_is_an_ordinary_key_character(self) -> None:
        assert span_text("a:b: one two\n", keys=["a:b"]) == ["one two"]
        assert span_text("a:b: one two\n", keys=["a"]) == []

    def test_is_ignored_in_the_other_three_modes(self) -> None:
        assert polytypo.transform("a...b", locale="en-US", keys=["a"]) == "a…b"


class TestWhatIsProcessable:
    """modes.md 3.8.4."""

    def test_the_three_scalar_forms(self) -> None:
        source = 'a: one two\nb: "three four"\nc: |\n  five six\n'
        assert span_text(source) == ["one two", "three four", "five six"]

    def test_a_key_is_never_processed(self) -> None:
        assert yaml("a...b: one...two\n", keys=["a...b"]) == "a...b: one…two\n"

    def test_block_sequence_entries_are_consumed_and_nest(self) -> None:
        assert span_text("- a: one two\n- - b: three four\n") == ["one two", "three four"]

    def test_comments_directives_and_both_document_marker_forms(self) -> None:
        assert span_text("%YAML 1.2\n---\n# a comment\na: one two\n...\n") == ["one two"]
        assert span_text("--- a: one two\n") == []

    def test_a_nested_node_is_scanned_but_a_continuation_is_not(self) -> None:
        assert span_text("a:\n  b: one two\n") == ["one two"]
        assert span_text("a: inline value\n  b: one two\n") == []


@pytest.mark.parametrize(
    "name,source",
    [
        ("a multi-line quoted scalar", 'a: "hello\n  b: some prose "word" here"\n'),
        ("a multi-line flow mapping", "a: {\n  b: hello world,\n  c: x\n}\n"),
        ("a multi-line flow sequence", "a: [\n  one two...,\n  three\n]\n"),
        ("a multi-line plain scalar", "a: one two...\n  b: three four...\n"),
    ],
)
def test_continuation_lines_are_consumed_never_rescanned(name: str, source: str) -> None:
    """modes.md 3.8.4 step 7. Without it a span can hold a quoted scalar's own closing delimiter,
    and `quotes` can then leave the scalar unterminated."""
    assert span_text(source) == [], name
    assert yaml(source) == source, name


@pytest.mark.parametrize(
    "name,source",
    [
        ("a bare sequence item", "- Some prose here...\n"),
        ("a flow sequence", "a: [one two..., three]\n"),
        ("a flow mapping", "a: {b: one two...}\n"),
        ("an anchor", "a: &anchor one two...\n"),
        ("an alias", "a: *anchor\n"),
        ("a tag", "a: !!str one two...\n"),
        ("a double-quoted scalar with an escape", 'a: "one \\"two\\"... three"\n'),
        ("a single-quoted scalar with an escaped quote", "a: 'it''s one two...'\n"),
        ("a tab anywhere on the line", "a:\tone two...\n"),
        ("a compact nested sequence", "a: - one two...\n"),
        ("a compact nested mapping", "a: one two .:\n"),
        ("an unterminated quoted scalar", 'a: "one two...\n'),
        ("a value that is only a comment", "a: # one two...\n"),
    ],
)
def test_skip_by_default(name: str, source: str) -> None:
    """modes.md 3.8.3: a construct the scan does not recognise yields no spans, byte for byte."""
    assert span_text(source) == [], name
    assert yaml(source) == source, name


def test_a_file_that_is_not_yaml_comes_back_unchanged_and_never_throws() -> None:
    source = "{{ not yaml at all ... }}\n\t\tmixed\tindentation\n"
    assert yaml(source) == source


class TestBlockScalars:
    """modes.md 3.8.5."""

    @pytest.mark.parametrize("header", ["|", "|-", "|+", ">", ">-", ">+"])
    def test_every_chomping_indicator_gives_identical_spans_and_trailing_bytes(
        self, header: str
    ) -> None:
        source = f"a: {header}\n  one two...\n\n\nz: 1\n"
        assert span_text(source) == ["one two..."], header
        assert yaml(source) == f"a: {header}\n  one two…\n\n\nz: 1\n", header

    def test_a_trailing_comment_on_the_header(self) -> None:
        assert span_text("a: | # note\n  one two\n") == ["one two"]

    def test_indentation_is_outside_the_span_and_extra_indentation_inside_it(self) -> None:
        assert span_text("a: |\n  one two\n    three four\n") == ["one two", "  three four"]

    def test_leading_spaces_of_a_content_line_are_never_collapsed(self) -> None:
        assert yaml("a: |\n  one two\n    three  four\n") == "a: |\n  one two\n    three four\n"

    def test_an_explicit_indentation_indicator(self) -> None:
        assert span_text("a: |2\n   one two\n") == [" one two"]

    @pytest.mark.parametrize(
        "name,source",
        [
            ("an explicit indicator disagreeing with the block", "a: |4\n  one two\n"),
            ("a tab on a content line", "a: |\n  one two\n  three\tfour\n"),
            ("a later line dedented inside the block", "a: |\n    deep one two\n  shallow three\n"),
            ("an unrecognised header", "a: |x\n  one two\n"),
        ],
    )
    def test_the_whole_block_bails(self, name: str, source: str) -> None:
        assert span_text(source) == [], name
        assert yaml(source) == source, name

    def test_the_block_ends_at_the_first_line_indented_no_more_than_the_key(self) -> None:
        assert span_text("a: |\n  one two\nb: three four\n") == ["one two", "three four"]

    def test_quotes_pair_across_block_scalar_lines(self) -> None:
        assert yaml('a: |\n  He said "hi"\n  and left\n') == "a: |\n  He said “hi”\n  and left\n"

    def test_crlf_yields_the_same_spans_as_lf_and_keeps_its_carriage_returns(self) -> None:
        assert span_text("a: |\r\n  one two...\r\n") == ["one two..."]
        assert yaml("a: |\r\n  one two...\r\n") == "a: |\r\n  one two…\r\n"


class TestQuotedAndPlainScalars:
    """modes.md 3.8.6."""

    def test_no_colon_test_applies_to_a_quoted_scalar(self) -> None:
        assert span_text('a: "Chapter 1: the beginning"\n') == ["Chapter 1: the beginning"]

    def test_a_trailing_comment_is_stripped_before_the_colon_test(self) -> None:
        assert span_text("a: some prose # note: here\n") == ["some prose"]

    def test_a_plain_scalar_splits_at_a_colon_and_at_a_hash(self) -> None:
        assert span_text("a: one:two three\n") == ["one", "two three"]
        assert span_text("a: one#two three\n") == ["one", "two three"]

    def test_the_split_declines_a_growing_replacement_against_a_colon_or_hash(self) -> None:
        # Without the split a -spaced locale emits `a: – b`, which reparses as a nested mapping,
        # and `a – #b`, where everything from the hash becomes a comment.
        assert yaml("k: a:--b\n", "de-DE") == "k: a:--b\n"
        assert yaml("k: a--#b\n", "de-DE") == "k: a--#b\n"

    def test_a_contraction_at_the_same_position_still_applies(self) -> None:
        # 2 -> 1 cannot emit U+0020, and U+0020 is the whole of what the split protects.
        assert yaml("k: a--#b\n", "en-US") == "k: a—#b\n"
        assert yaml("k: a:--b\n", "en-US") == "k: a:—b\n"

    def test_three_dashes_are_declined_by_the_character_clause(self) -> None:
        # modes.md 3.4: `---` -> ` – ` is 3 -> 3, so the length clause misses it entirely.
        assert yaml("k: a:---b\n", "de-DE") == "k: a:---b\n"
        assert yaml("k: a---#b\n", "de-DE") == "k: a---#b\n"


class TestSpanPartitionStability:
    """modes.md 5 item 2."""

    def test_a_span_is_not_lost_because_a_rule_changed_what_is_inside_it(self) -> None:
        source = "a: ${{ steps.pin.outputs.sha }}\n"
        once = yaml(source)
        assert len(yaml_spans(once, frozenset(PROSE_KEYS))) == len(
            yaml_spans(source, frozenset(PROSE_KEYS))
        )
        assert yaml(once) == once


class TestRoundTrip:
    """modes.md 4."""

    def test_a_document_needing_no_changes_comes_back_byte_for_byte(self) -> None:
        source = "a: one two\nb: 'it''s'\nc: [x, y]\n#comment\n"
        assert yaml(source) == source

    def test_quoting_indentation_and_non_ascii_survive_an_edit(self) -> None:
        assert yaml('a: "Une note... précise"\n', "fr") == 'a: "Une note… précise"\n'

    def test_it_is_idempotent_on_a_document_it_does_change(self) -> None:
        source = 'a: The "book"... and more\nb: |\n  He said -- loudly\n'
        once = yaml(source)
        assert once != source
        assert yaml(once) == once
