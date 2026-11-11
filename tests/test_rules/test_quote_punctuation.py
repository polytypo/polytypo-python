"""spec/rules/quote-punctuation.md edge cases not already exercised by conformance fixtures: the
rule is default off, acts in en-US only, and declines wherever C1-C4 fail."""

from __future__ import annotations

import copy

import pytest

import polytypo
import polytypo.html
import polytypo.text
from polytypo._engine.locale import _registry  # noqa: SLF001 -- test-only introspection
from polytypo.errors import PolytypoError

ON = {"quote-punctuation": True}


def on(text: str, locale: str = "en-US") -> str:
    return polytypo.transform(text, locale=locale, rules=ON)


def test_off_by_default() -> None:
    assert polytypo.transform('She said "hello", then left.', locale="en-US") == (
        "She said “hello”, then left."
    )


def test_comma_and_stop_move_inside() -> None:
    assert on('She said "hello", then left.') == "She said “hello,” then left."
    assert on('He called it "done". Then he left.') == "He called it “done.” Then he left."


def test_end_of_text_and_line_break_end_the_clause() -> None:
    assert on('Call it "ready".') == "Call it “ready.”"
    assert on('Call it "ready".\nNext') == "Call it “ready.”\nNext"


def test_already_inside_is_untouched() -> None:
    assert on("She said “hello,” then left.") == "She said “hello,” then left."


def test_declines_after_digit_terminal_ellipsis_and_nested_quote() -> None:
    assert on('Route "66".') == "Route “66”."
    assert on('"Stop!".') == "“Stop!”."
    assert on('It said "wait…".') == "It said “wait…”."
    assert on('Use "e.g.", then') == "Use “e.g.”, then"
    assert on("\"He said 'hi'\".") == "“He said ‘hi’”."


def test_declines_when_anything_but_space_or_end_follows() -> None:
    assert on('"file".txt') == "“file”.txt"
    assert on('He said ("hi".)') == "He said (“hi”.)"
    assert on('He said "wait"...') == "He said “wait”…"
    assert on("“a”,”b”") == "“a”,”b”"


def test_other_punctuation_is_never_moved() -> None:
    assert on('Say "a"; say "b": say "c"?') == "Say “a”; say “b”: say “c”?"


def test_start_of_text_has_no_letter_on_the_left() -> None:
    assert on("”, then") == "”, then"


def test_secondary_close_is_not_the_scan_glyph() -> None:
    assert on("Check the dogs’, bowls and cats.") == "Check the dogs’, bowls and cats."


def test_unpaired_closing_mark_moves_too() -> None:
    assert on("Broken pair”, then") == "Broken pair,” then"


def test_two_edits_in_one_text() -> None:
    assert on('The "first", the "second".') == "The “first,” the “second.”"


def test_en_gb_is_a_no_op() -> None:
    assert on('She said "hello", then left.', "en-GB") == "She said ‘hello’, then left."


@pytest.mark.parametrize("locale", sorted(_registry()["locales"]))
def test_every_locale_but_en_us_is_unchanged_by_enabling(locale: str) -> None:
    if locale == "en-US":
        return
    text = 'She said "hello", then left. He called it "done". Then "stop".'
    assert on(text, locale) == polytypo.transform(text, locale=locale)


def test_html_span_boundary_blocks_the_move() -> None:
    kwargs = {"locale": "en-US", "rules": ON}
    assert polytypo.html.transform('<p>She said <em>"hello"</em>, then left.</p>', **kwargs) == (
        "<p>She said <em>“hello”</em>, then left.</p>"
    )
    assert polytypo.html.transform('<p>She said "hello", then left.</p>', **kwargs) == (
        "<p>She said “hello,” then left.</p>"
    )
    assert polytypo.html.transform('<p>Say "hi".</p><p>Next.</p>', **kwargs) == (
        "<p>Say “hi”.</p><p>Next.</p>"
    )


def test_protected_run_blocks_the_move() -> None:
    text = 'Set "file".${ext} now'
    start = text.index("${")
    out = polytypo.text.transform(
        text, locale="en-US", rules=ON, protect=[(start, start + len("${ext}"))]
    )
    assert out == "Set “file”.${ext} now"


def test_analyze_reports_one_change_per_edit_only_when_enabled() -> None:
    text = 'The "first", the "second".'
    assert "quote-punctuation" not in [c.rule_id for c in polytypo.analyze(text, locale="en-US")]
    changes = [
        c
        for c in polytypo.analyze(text, locale="en-US", rules=ON)
        if c.rule_id == "quote-punctuation"
    ]
    assert len(changes) == 2


def _malformed(monkeypatch: pytest.MonkeyPatch, mutate: object) -> None:
    from polytypo._engine import locale as locale_module

    real = locale_module._locale_data_raw  # noqa: SLF001
    data = copy.deepcopy(real("en-US"))
    mutate(data["quotes"])  # type: ignore[operator]
    monkeypatch.setattr(locale_module, "_locale_data_raw", lambda _id: data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda q: q.pop("punctuationPlacement"),
        lambda q: q.__setitem__("punctuationPlacement", "outside"),
        lambda q: q.__setitem__("punctuationPlacement", True),
        lambda q: q.__setitem__("punctuationPlacement", None),
        lambda q: q.__setitem__("punctuationPlacement", ["inside"]),
    ],
)
def test_malformed_punctuation_placement_raises(
    monkeypatch: pytest.MonkeyPatch, mutate: object
) -> None:
    _malformed(monkeypatch, mutate)
    with pytest.raises(PolytypoError) as excinfo:
        polytypo.transform("x", locale="en-US")
    assert excinfo.value.code == "POLYTYPO_MALFORMED_LOCALE_DATA"


def test_astral_letter_before_the_closing_mark_is_not_a_letter_or_is_by_category() -> None:
    # U+1F600 (So) is not a letter: C3 fails, nothing moves. U+1D400 (Lu) is: the stop moves.
    assert on('\U0001f600 "\U0001f600".') == "\U0001f600 “\U0001f600”."
    assert on('x "\U0001d400".') == "x “\U0001d400.”"
