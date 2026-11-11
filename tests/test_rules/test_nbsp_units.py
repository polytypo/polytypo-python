"""spec/rules/nbsp.md 3.7 (spec 1.22.0): N5 inserts for `spacedUnits` and deletes for
`closedUnits`. Every such edit changes what a later pass sees, so the property worth proving is
the fixed point."""

from __future__ import annotations

import itertools

import pytest

import polytypo

NBSP = " "
NNBSP = " "
LOCALES = ["de-DE", "en-US", "en-GB", "ru", "el", "nl", "fr-CA", "hu", "cs", "sr"]


def t(text: str, locale: str) -> str:
    return polytypo.transform(text, locale=locale, mode="text")


def test_inserts_for_spaced_units_and_deletes_for_closed_units() -> None:
    assert t("Es sind 20km", "de-DE") == f"Es sind 20{NBSP}km"
    assert t("Rose 5 %", "en-US") == "Rose 5%"
    assert t(f"Rose 5{NBSP}%", "ru") == "Rose 5%"


def test_before_units_stay_conversion_only() -> None:
    assert t("14 % nebo 20%", "cs") == f"14{NBSP}% nebo 20%"


def test_spaced_unit_keeps_authored_narrow_space() -> None:
    assert t(f"20{NNBSP}km", "de-DE") == f"20{NNBSP}km"


def test_closed_unit_deletes_narrow_space() -> None:
    assert t(f"5{NNBSP}%", "en-US") == "5%"


@pytest.mark.parametrize("text", ["15cm-Norm", "foto-5kg.png", "/5km", "x_5kg", "H2km", "A4kg"])
def test_guards_leave_identifiers_and_compounds(text: str) -> None:
    assert t(text, "de-DE") == text


def test_modulo_guard_for_closed_units() -> None:
    assert t("10 % 3", "en-US") == "10 % 3"


def test_dash_adjacency_guard_for_closed_symbols() -> None:
    # G-R: a closed-up symbol beside a dash decides how ranges/dashes read the token.
    out = t("15 % - 20 %", "en-US")
    assert t(out, "en-US") == out


ATOMS = ["5", "0", " ", NBSP, "%", "km", "°C", "kg", "-", ".", ",", "a", "_", "(", "–", "×"]


@pytest.mark.parametrize("locale", LOCALES)
def test_every_short_string_is_a_fixed_point(locale: str) -> None:
    for depth in range(1, 4):
        for combo in itertools.product(ATOMS, repeat=depth):
            text = "".join(combo)
            once = t(text, locale)
            assert t(once, locale) == once, (locale, text, once)


def test_multiplication_operand_guard() -> None:
    assert t("2 x 3kg", "de-DE") == "2 x 3kg"
    assert t("2 х 3км", "ru") == "2 х 3км"


MUL_ATOMS = ["2", "3", " ", NBSP, NNBSP, "x", "х", "kg", "км", "%"]


@pytest.mark.parametrize("locale", ["de-DE", "en-US", "ru", "cs", "fr-CA"])
def test_multiplication_chains_are_fixed_points(locale: str) -> None:
    for depth in range(1, 6):
        for combo in itertools.product(MUL_ATOMS, repeat=depth):
            text = "".join(combo)
            once = t(text, locale)
            assert t(once, locale) == once, (locale, text, once)
