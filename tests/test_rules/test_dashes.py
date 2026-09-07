"""spec/rules/dashes.md guard-level cases not already exercised by conformance fixtures."""

from __future__ import annotations

import polytypo


def test_double_hyphen_promotes_to_em_dash_in_en_us() -> None:
    assert polytypo.transform("a--b", locale="en-US") == "a—b"


def test_spaced_hyphen_promotes_to_em_dash_in_en_us() -> None:
    assert polytypo.transform("a - b", locale="en-US") == "a—b"


def test_p4_roman_numeral_veto_preserves_a_genuine_range() -> None:
    # dashes.md P4: a tight dash between two maximal ROMAN runs is preserved, not converted.
    assert polytypo.transform("IV-V", locale="en-US") == "IV-V"
    assert polytypo.transform("XX-XXI", locale="en-US") == "XX-XXI"


def test_iso_date_is_left_alone() -> None:
    assert polytypo.transform("2020-01-01", locale="en-US") == "2020-01-01"


def test_digit_flanked_dash_is_never_dashes_territory() -> None:
    # ranges' territory exclusively, unconditionally -- with `ranges` off (the default), a
    # digit-flanked dash is left untouched by `dashes` rather than reinterpreted.
    assert polytypo.transform("pages 5-10", locale="en-US") == "pages 5-10"
