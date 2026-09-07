"""spec/rules/ranges.md guard-level cases. `ranges` is opt-in (default off), so every case here
passes `rules={"ranges": True}` explicitly."""

from __future__ import annotations

import polytypo


def _t(text: str) -> str:
    return polytypo.transform(text, locale="en-US", rules={"ranges": True})


def test_off_by_default() -> None:
    assert polytypo.transform("pages 5-10", locale="en-US") == "pages 5-10"


def test_digit_flanked_dash_promotes_to_range() -> None:
    assert _t("pages 5-10") == "pages 5⁠–⁠10"


def test_g2_no_chain_declines_a_second_adjacent_dash() -> None:
    # ranges.md G2: an ISO date, ISBN or phone number always trips this.
    assert _t("ISBN 1-2-3") == "ISBN 1-2-3"


def test_g4_directional_one_two_digit_form() -> None:
    assert _t("chapter 9-15") == "chapter 9⁠–⁠15"


def test_g5_declines_a_decreasing_pair() -> None:
    assert _t("a 100-1") == "a 100-1"
