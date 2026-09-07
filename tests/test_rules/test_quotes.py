"""spec/rules/quotes.md guard-level cases not already exercised by conformance fixtures."""

from __future__ import annotations

import polytypo


def test_straight_double_quotes_pair_and_convert() -> None:
    assert polytypo.transform('"a" and "b"', locale="en-US") == "“a” and “b”"


def test_rock_n_roll_apostrophes_are_not_mistaken_for_quotation_marks() -> None:
    # quotes.md's listed-elision veto: 'n' here is an elision idiom (apostrophe's territory),
    # not a pair of single quotation marks.
    assert polytypo.transform("rock 'n' roll", locale="en-US") == "rock ’n’ roll"


def test_unbalanced_mark_is_left_alone() -> None:
    out = polytypo.transform('He said "hello', locale="en-US")
    assert out == 'He said "hello'
