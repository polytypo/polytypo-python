"""modes.md 3.9: ``protect``. The fixtures (tests/conformance) pin the behaviour; this file covers
what a fixture cannot express -- validation order across modes, the moved-range idempotency
property over a sweep, analyze's range obligation, and code-point offsets."""

from __future__ import annotations

import random
from typing import Any

import pytest

import polytypo
import polytypo.html
import polytypo.markdown
import polytypo.text
import polytypo.yaml
from polytypo._engine.codepoints import to_codepoints
from polytypo._engine.locale import get_locale_data, resolve
from polytypo._engine.pipeline import resolve_rule_plan
from polytypo._engine.protect import resolve_protect, run_protected_mapped
from polytypo.errors import PolytypoError

INVALID = "POLYTYPO_INVALID_OPTION"


def _code(**kwargs: Any) -> str:
    with pytest.raises(PolytypoError) as excinfo:
        polytypo.transform("a -- b", **kwargs)
    return excinfo.value.code


class TestAbsentAndEmptyAreTheSameCall:
    def test_none_and_empty_list_equal_no_option(self) -> None:
        text = 'He said "hi" -- and left...'
        plain = polytypo.transform(text, locale="en-US")
        assert polytypo.transform(text, locale="en-US", protect=None) == plain
        assert polytypo.transform(text, locale="en-US", protect=[]) == plain
        assert polytypo.transform(text, locale="en-US", protect=()) == plain
        assert polytypo.text.transform(text, locale="en-US", protect=[]) == plain

    def test_empty_list_is_accepted_in_every_mode(self) -> None:
        for kwargs in (
            {"mode": "html"},
            {"mode": "markdown", "dialect": "commonmark"},
            {"mode": "yaml", "keys": ["a"]},
        ):
            assert polytypo.transform("a -- b", locale="en-US", protect=[], **kwargs) == (
                polytypo.transform("a -- b", locale="en-US", **kwargs)
            )

    def test_empty_list_analyze_equals_no_option(self) -> None:
        text = "Wait... really?"
        assert polytypo.analyze(text, locale="en-US", protect=[]) == polytypo.analyze(
            text, locale="en-US"
        )


class TestRefusals:
    @pytest.mark.parametrize(
        "protect",
        [
            {"start": 0, "end": 1},
            "ab",
            b"ab",
            5,
            [(0, 1), (0, 1)],
            [(2, 4), (3, 5)],
            [(3, 4), (0, 1)],
            [(2, 2)],
            [(3, 2)],
            [(-1, 2)],
            [(0, 7)],
            [(0, 1.5)],
            [(0.0, 1)],
            [(True, 3)],
            [(0, True)],
            [("0", "1")],
            [(0,)],
            [(0, 1, 2)],
            ["ab"],
            [None],
            [{"start": 0, "end": 1}],
            iter([(0, 1)]),
        ],
    )
    def test_malformed_values_raise_invalid_option(self, protect: Any) -> None:
        assert _code(locale="en-US", protect=protect) == INVALID
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.analyze("a -- b", locale="en-US", protect=protect)
        assert excinfo.value.code == INVALID

    def test_bound_is_code_points_not_utf16_units_or_bytes(self) -> None:
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.transform("\U0001f600", locale="en-US", protect=[(0, 2)])
        assert excinfo.value.code == INVALID
        assert polytypo.transform("\U0001f600", locale="en-US", protect=[(0, 1)]) == "\U0001f600"

    def test_list_of_lists_is_accepted(self) -> None:
        assert polytypo.transform("${x} - Rules", locale="en-US", protect=[[0, 4]]) == "${x}—Rules"

    def test_touching_ranges_are_allowed(self) -> None:
        assert resolve_protect([(0, 2), (2, 4)], 6) == [(0, 4)]

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"mode": "html"},
            {"mode": "markdown", "dialect": "commonmark"},
            {"mode": "yaml", "keys": ["a"]},
        ],
    )
    def test_non_empty_protect_is_refused_outside_text(self, kwargs: dict[str, Any]) -> None:
        assert _code(locale="en-US", protect=[(0, 1)], **kwargs) == INVALID
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.analyze("a -- b", locale="en-US", protect=[(0, 1)], **kwargs)
        assert excinfo.value.code == INVALID

    def test_other_entry_points_do_not_take_protect(self) -> None:
        with pytest.raises(TypeError):
            polytypo.html.transform("a", locale="en-US", protect=[(0, 1)])  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            polytypo.markdown.transform(  # type: ignore[call-arg]
                "a", locale="en-US", dialect="commonmark", protect=[(0, 1)]
            )
        with pytest.raises(TypeError):
            polytypo.yaml.transform("a", locale="en-US", keys=[], protect=[(0, 1)])  # type: ignore[call-arg]


class TestValidationOrder:
    """mode -> narrow_nbsp -> rules -> locale -> dialect -> keys / frontmatter_keys -> protect."""

    bad = [(3, 2)]

    def test_mode_first(self) -> None:
        assert _code(locale="xx", mode="nope", protect=self.bad) == "POLYTYPO_INVALID_MODE"

    def test_narrow_nbsp_before_rules(self) -> None:
        assert (
            _code(locale="en-US", narrow_nbsp="x", rules={"nope": True}, protect=self.bad)
            == INVALID
        )

    def test_unknown_rule_beats_protect(self) -> None:
        assert (
            _code(locale="en-US", rules={"nope": True}, protect=self.bad) == "POLYTYPO_UNKNOWN_RULE"
        )

    def test_unknown_locale_beats_protect(self) -> None:
        assert _code(locale="xx", protect=self.bad) == "POLYTYPO_UNKNOWN_LOCALE"

    def test_unknown_rule_beats_unknown_locale_beats_protect(self) -> None:
        assert _code(locale="xx", rules={"nope": True}, protect=self.bad) == "POLYTYPO_UNKNOWN_RULE"

    def test_invalid_dialect_beats_non_empty_protect_in_markdown(self) -> None:
        assert (
            _code(locale="en-US", mode="markdown", dialect="nope", protect=[(0, 1)])
            == "POLYTYPO_INVALID_DIALECT"
        )
        assert (
            _code(locale="en-US", mode="markdown", protect=[(0, 1)]) == "POLYTYPO_INVALID_DIALECT"
        )

    def test_frontmatter_keys_beat_protect_in_markdown(self) -> None:
        assert (
            _code(
                locale="en-US",
                mode="markdown",
                dialect="commonmark",
                frontmatter_keys="title",
                protect=[(0, 1)],
            )
            == INVALID
        )

    def test_keys_beat_protect_in_yaml(self) -> None:
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.transform("a: b", locale="en-US", mode="yaml", protect=[(0, 1)])
        assert excinfo.value.code == INVALID
        assert "keys" in str(excinfo.value)

    def test_analyze_has_the_same_order(self) -> None:
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.analyze("a", locale="en-US", rules={"nope": True}, protect=self.bad)
        assert excinfo.value.code == "POLYTYPO_UNKNOWN_RULE"
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.analyze("a", locale="en-US", mode="markdown", protect=[(0, 1)])
        assert excinfo.value.code == "POLYTYPO_INVALID_DIALECT"


class TestCodePointOffsets:
    def test_astral_before_and_inside_a_hole(self) -> None:
        text = "\U0001f600 -- \U0001f600${x} -- \U0001f600"
        out = polytypo.transform(text, locale="en-US", protect=[(5, 10)])
        assert out == "\U0001f600—\U0001f600${x}—\U0001f600"

    def test_protected_run_is_returned_byte_for_byte(self) -> None:
        text = 'a -- "${\U0001f600  ...  x}" -- b'
        start = text.index("${")
        end = text.index("}") + 1
        out = polytypo.transform(text, locale="en-US", protect=[(start, end)])
        assert "${\U0001f600  ...  x}" in out

    def test_whole_input_protected(self) -> None:
        assert polytypo.transform("a -- b", locale="en-US", protect=[(0, 6)]) == "a -- b"
        assert polytypo.analyze("a -- b", locale="en-US", protect=[(0, 6)]) == []

    def test_analyze_offsets_are_code_points_of_the_input(self) -> None:
        text = "\U0001f600${x}...\U0001f600"
        changes = polytypo.analyze(text, locale="en-US", protect=[(1, 5)])
        assert [(c.rule_id, c.start, c.end, c.before) for c in changes] == [
            ("ellipsis", 5, 8, "...")
        ]


class TestAnalyzeEndOffsets:
    def test_end_does_not_run_across_a_skipped_element(self) -> None:
        changes = polytypo.analyze("<p>x--<code>cc</code>y</p>", locale="en-US", mode="html")
        assert [(c.rule_id, c.start, c.end, c.before) for c in changes] == [("dashes", 4, 6, "--")]

    def test_end_does_not_run_across_a_protected_run(self) -> None:
        text = "x--${a}y"
        changes = polytypo.analyze(text, locale="en-US", protect=[(3, 7)])
        assert [(c.start, c.end) for c in changes] == [(1, 3)]

    def test_transform_output_is_unchanged_by_the_fix(self) -> None:
        assert (
            polytypo.transform("<p>x--<code>cc</code>y</p>", locale="en-US", mode="html")
            == "<p>x—<code>cc</code>y</p>"
        )


HOLES = ["${x}", "{n}", "<b>", "{a, plural, one {#}}", "'{b}'", "${\n}", "{ }"]
TOKENS = [
    "a", "word", "Ab", "5", "12", " ", " ", " ", "  ", "-", "--", "---", "...", ".", ",", "!", "?",
    ":", ";", '"', "'", "(", ")", "\n", "–", "—", "'s", "n't", "km", "%", "\U0001f600",
    "é", "«", "»", "„", "“", "”",
]  # fmt: skip
LOCALES = [
    "en-US", "en-GB", "de-DE", "fr", "ru", "fi", "pl", "tr", "es", "it", "nl", "cs", "sv", "el",
    "uk", "hu", "bg", "hr",
]  # fmt: skip
PER_LOCALE = 150


def _build(rng: random.Random) -> tuple[str, list[tuple[int, int]]]:
    text = ""
    length = 0
    holes: list[tuple[int, int]] = []
    for _ in range(rng.randint(3, 10)):
        if rng.random() < 0.2:
            hole = rng.choice(HOLES)
            holes.append((length, length + len(hole)))
            text += hole
            length += len(hole)
        else:
            token = rng.choice(TOKENS)
            text += token
            length += len(token)
    return text, holes


@pytest.mark.parametrize("locale", LOCALES)
def test_sweep_moved_ranges_idempotent_and_analyze_obligations(locale: str) -> None:
    rng = random.Random(f"protect-{locale}")
    plan = resolve_rule_plan(None)
    locale_data = get_locale_data(resolve(locale))
    ctx: Any = {"mode": "text", "dialect": None, "locale": locale, "narrow_target": 0x202F}
    for _ in range(PER_LOCALE):
        text, holes = _build(rng)
        if not holes:
            continue
        merged = resolve_protect(holes, len(to_codepoints(text)))
        out, moved = run_protected_mapped(text, merged, plan, locale_data, ctx)
        assert polytypo.transform(text, locale=locale, protect=holes) == out
        assert [out[h.start : h.end] for h in moved] == [text[h.start : h.end] for h in merged]
        again = polytypo.transform(out, locale=locale, protect=[tuple(h) for h in moved])
        assert again == out, (locale, text, out, again)

        changes = polytypo.analyze(text, locale=locale, protect=holes)
        assert (changes == []) == (out == text), (locale, text)
        for change in changes:
            assert 0 <= change.start <= change.end <= len(text)
            for hole in merged:
                if change.start == change.end:
                    assert not hole.start < change.start < hole.end, (locale, text, change)
                else:
                    assert not (change.start < hole.end and change.end > hole.start), (
                        locale,
                        text,
                        change,
                        hole,
                    )


def test_html_analyze_never_reports_a_range_over_a_skipped_region() -> None:
    rng = random.Random("html-ranges")
    skipped = ["<code>cc</code>", "<br>", "<b>", "</b>", "<!-- c -->", "<script>s()</script>"]
    for locale in ("en-US", "de-DE", "fr", "ru"):
        for _ in range(100):
            parts: list[str] = []
            regions: list[tuple[int, int]] = []
            length = 0
            for _ in range(rng.randint(3, 9)):
                if rng.random() < 0.3:
                    piece = rng.choice(skipped)
                    regions.append((length, length + len(piece)))
                else:
                    piece = rng.choice(TOKENS)
                parts.append(piece)
                length += len(piece)
            text = "".join(parts)
            for change in polytypo.analyze(text, locale=locale, mode="html"):
                assert 0 <= change.start <= change.end <= len(text)
                if change.start == change.end:
                    continue
                for start, end in regions:
                    assert not (change.start < end and change.end > start), (
                        locale,
                        text,
                        change,
                    )
