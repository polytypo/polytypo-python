"""spec/rules/analyze.md -- the contract is A1...A5; the decomposition is observation.

Mirrors polytypo-js's tests/engine/analyze.test.ts case for case, including the two that are
cheap to get wrong (analyze.md section 6): A3 over the whole vendored corpus, and document
offsets under the mode adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import polytypo
from polytypo.errors import PolytypoError

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "vendor" / "polytypo-spec" / "fixtures"

ORDER = [
    "spaces",
    "ellipsis",
    "ranges",
    "dashes",
    "hyphen",
    "quotes",
    "apostrophe",
    "symbols",
    "nbsp",
]


class TestA1AcceptsAndRejectsWhatTransformDoes:
    def test_unknown_locale(self) -> None:
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.analyze("x", locale="xx")
        assert excinfo.value.code == "POLYTYPO_UNKNOWN_LOCALE"

    def test_unknown_rule_wins_over_unknown_locale(self) -> None:
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.analyze("x", locale="xx", rules={"nope": True})
        assert excinfo.value.code == "POLYTYPO_UNKNOWN_RULE"

    def test_unknown_mode(self) -> None:
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.analyze("x", locale="en-US", mode="asciidoc")
        assert excinfo.value.code == "POLYTYPO_INVALID_MODE"

    def test_markdown_requires_a_dialect(self) -> None:
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.analyze("x", locale="en-US", mode="markdown")
        assert excinfo.value.code == "POLYTYPO_INVALID_DIALECT"


class TestA2Pure:
    def test_same_list_for_the_same_arguments(self) -> None:
        once = polytypo.analyze('She said "hi" -- really...', locale="en-US")
        twice = polytypo.analyze('She said "hi" -- really...', locale="en-US")
        assert twice == once

    def test_does_not_change_what_transform_returns(self) -> None:
        text = 'She said "hi" -- really...'
        before = polytypo.transform(text, locale="en-US")
        polytypo.analyze(text, locale="en-US")
        assert polytypo.transform(text, locale="en-US") == before


class TestA3EmptyExactlyWhenTransformChangesNothing:
    def test_empty_for_text_that_needs_nothing(self) -> None:
        assert polytypo.analyze("Nothing to do here.", locale="en-US") == []

    def test_non_empty_for_text_that_needs_something(self) -> None:
        assert len(polytypo.analyze("Wait...", locale="en-US")) > 0

    def test_agrees_with_transform_on_every_canonical_fixture(self) -> None:
        """analyze.md section 6: the whole canonical corpus, the cheap strong version of A3."""
        offenders: list[str] = []
        for path in sorted(FIXTURES_DIR.glob("*.json")):
            if path.name == "locale-resolution.json":
                continue
            data: dict[str, Any] = json.loads(path.read_text("utf-8"))
            for case in data["cases"]:
                if "throws" in case or case.get("dialect") == "mdx":
                    continue
                kwargs: dict[str, Any] = {"locale": data["locale"], "mode": case["mode"]}
                if case.get("dialect") is not None:
                    kwargs["dialect"] = case["dialect"]
                if case.get("keys") is not None:
                    kwargs["keys"] = case["keys"]
                if case.get("rules") is not None:
                    kwargs["rules"] = case["rules"]
                changed = polytypo.transform(case["in"], **kwargs) != case["in"]
                reported = len(polytypo.analyze(case["in"], **kwargs)) > 0
                if changed != reported:
                    offenders.append(f"{data['locale']}/{case['id']}")
        assert offenders == []


class TestA4OnlyRulesEnabledForTheCall:
    def test_never_reports_a_rule_the_caller_disabled(self) -> None:
        ids = [
            c.rule_id
            for c in polytypo.analyze('She said "hi"...', locale="en-US", rules={"quotes": False})
        ]
        assert "quotes" not in ids
        assert "ellipsis" in ids

    def test_never_reports_ranges_unless_turned_on(self) -> None:
        text = "chapters 3-5"
        assert "ranges" not in [c.rule_id for c in polytypo.analyze(text, locale="en-US")]
        turned_on = polytypo.analyze(text, locale="en-US", rules={"ranges": True})
        assert "ranges" in [c.rule_id for c in turned_on]


class TestA5OffsetsAreCodePointsInsideTheInput:
    def test_stays_within_bounds_with_astral_characters(self) -> None:
        text = 'A \U0001f600 says "hi" and waits...'
        for change in polytypo.analyze(text, locale="en-US"):
            assert 0 <= change.start <= change.end <= len(text)

    def test_reports_code_point_offsets(self) -> None:
        """The emoji is one code point here and two UTF-16 units in the JS runtime; both report
        6, which is what makes the offsets portable rather than string-representation-specific."""
        text = '\U0001f600 and "this"'
        first = polytypo.analyze(text, locale="en-US")[0]
        assert first.rule_id == "quotes"
        assert first.start == 6

    def test_html_mode_reports_document_offsets(self) -> None:
        """analyze.md section 6: the mistake that passes every text-mode test."""
        text = '<p class="x">Wait...</p>'
        first = polytypo.analyze(text, locale="en-US", mode="html")[0]
        assert first.rule_id == "ellipsis"
        assert first.start == text.index("...")
        assert first.before == "..."
        assert first.after == "…"

    def test_html_mode_reports_document_offsets_in_a_later_span(self) -> None:
        """Three spans, a non-ASCII character before the change, and the change in the third
        span: the two markers are the only code points in the joined array with no origin, so a
        doubled or dropped one shifts this offset and nothing in a one- or two-span document
        would notice, and `café` puts the UTF-8 byte offset one ahead of the code-point one, so
        a byte offset leaking out of a span adapter cannot pass either."""
        text = "<p>café</p><p>two</p><p>Wait... three</p>"
        first = polytypo.analyze(text, locale="en-US", mode="html")[0]
        assert first.rule_id == "ellipsis"
        assert first.start == text.index("...")
        assert len(text[: text.index("...")].encode("utf-8")) == first.start + 1

    def test_markdown_mode_reports_document_offsets(self) -> None:
        text = "# Title\n\nWait... here\n"
        first = polytypo.analyze(text, locale="en-US", mode="markdown", dialect="commonmark")[0]
        assert first.start == text.index("...")


class TestPipelineOrderAndOverlap:
    def test_reports_rules_in_spec_order(self) -> None:
        ids = [c.rule_id for c in polytypo.analyze('She said "hi" -- wait...', locale="en-US")]
        assert ids == sorted(ids, key=ORDER.index)

    def test_reports_both_rules_when_they_touch_the_same_original_range(self) -> None:
        """The French case analyze.md section 5 is written around: two rules, one original index.
        `spaces` removes the space at 3-4 and `nbsp` inserts at 4-4, in front of the colon the
        caller wrote at 4 -- the second change's position is the colon's, not the deleted
        space's."""
        changes = polytypo.analyze("Oui : non", locale="fr")
        assert [c.rule_id for c in changes] == ["spaces", "nbsp"]
        assert (changes[0].before, changes[0].after) == (" ", "")
        assert (changes[0].start, changes[0].end) == (3, 4)
        assert changes[1].after == " "
        assert (changes[1].start, changes[1].end) == (4, 4)
