"""spec/rules/spaces.md guard-level cases not already exercised by conformance fixtures
(mirrors the spirit of polytypo-js's tests/rules/spaces.test.ts, at reduced scope)."""

from __future__ import annotations

import polytypo


def test_collapses_run_of_spaces() -> None:
    assert polytypo.transform("a    b", locale="en-US") == "a b"


def test_strips_space_before_punctuation() -> None:
    assert polytypo.transform("Wait , no", locale="en-US") == "Wait, no"


def test_lone_dot_guard_keeps_space_before_dot_run_but_not_before_a_single_stop() -> None:
    # spaces.md 3.4: a run of dots ("...") is a different token from a terminal full stop, and
    # only a genuine single stop has its preceding space stripped.
    assert polytypo.transform("Wait ... more", locale="en-US", rules={"ellipsis": False}) == (
        "Wait ... more"
    )
    assert polytypo.transform("Wait . more", locale="en-US") == "Wait. more"


def test_emoticon_eye_guard_keeps_space_before_face() -> None:
    assert polytypo.transform("a :)", locale="en-US") == "a :)"
    assert polytypo.transform("a :-)", locale="en-US") == "a :-)"


def test_emoticon_mouth_guard_keeps_space_after_face() -> None:
    for eye, nose, mouth in [(":", "", "("), (";", "-", ")")]:
        text = f"a {eye}{nose}{mouth} b"
        out = polytypo.transform(text, locale="en-US")
        assert out.endswith(f"{mouth} b"), out


def test_empty_bracket_guard_collapses_but_does_not_delete() -> None:
    # spaces.md 3.3: "- [ ] item" (a GFM task-list checkbox) must not become "- [] item".
    assert polytypo.transform("[  ]", locale="en-US") == "[ ]"


def test_open_bracket_strips_trailing_space() -> None:
    assert polytypo.transform("(  a)", locale="en-US") == "(a)"
