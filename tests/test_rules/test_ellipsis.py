"""spec/rules/ellipsis.md guard-level cases not already exercised by conformance fixtures."""

from __future__ import annotations

import polytypo


def test_three_dots_become_ellipsis() -> None:
    assert polytypo.transform("Wait...", locale="en-US") == "Wait…"


def test_more_than_three_dots_still_collapse_to_ellipsis() -> None:
    assert polytypo.transform("a....b", locale="en-US") == "a…b"


def test_relative_path_is_not_an_ellipsis() -> None:
    # spec 4 "../", "./..": a lone dot beside a solidus is a path, not an ellipsis.
    assert polytypo.transform("See ../docs", locale="en-US") == "See ../docs"
