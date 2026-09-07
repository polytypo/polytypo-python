"""spec/rules/symbols.md guard-level cases not already exercised by conformance fixtures."""

from __future__ import annotations

import polytypo


def test_copyright() -> None:
    assert polytypo.transform("(c) 2024", locale="en-US") == "© 2024"


def test_registered() -> None:
    assert polytypo.transform("(r) Brand", locale="en-US") == "® Brand"


def test_trademark() -> None:
    assert polytypo.transform("trademark(tm)", locale="en-US") == "trademark™"


def test_multiplication_sign_between_digits() -> None:
    assert polytypo.transform("5 x 5", locale="en-US") == "5 × 5"


def test_lone_x_between_letters_is_not_multiplication() -> None:
    assert polytypo.transform("a x b", locale="en-US") == "a x b"
