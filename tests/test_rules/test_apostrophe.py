"""spec/rules/apostrophe.md guard-level cases not already exercised by conformance fixtures."""

from __future__ import annotations

import polytypo


def test_medial_contraction() -> None:
    assert polytypo.transform("don't", locale="en-US") == "don’t"


def test_leading_elision() -> None:
    assert polytypo.transform("'90s", locale="en-US") == "’90s"


def test_trailing_possessive() -> None:
    assert polytypo.transform("the dogs' bowls", locale="en-US") == "the dogs’ bowls"


def test_prime_guard_leaves_feet_and_inches_alone() -> None:
    assert polytypo.transform("6' 2\"", locale="en-US") == "6' 2\""


def test_case_5_nothing_inferable_is_left_alone() -> None:
    assert polytypo.transform("a ' b", locale="en-US") == "a ' b"
