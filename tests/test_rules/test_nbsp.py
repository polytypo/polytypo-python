"""spec/rules/nbsp.md guard-level cases not already exercised by conformance fixtures. `fr` is
used throughout since its locale data exercises every sub-rule (N1-N10)."""

from __future__ import annotations

import polytypo

NBSP = " "
NNBSP = " "


def test_n2_narrow_nbsp_before_question_mark() -> None:
    assert polytypo.transform("Vraiment ?", locale="fr") == f"Vraiment{NNBSP}?"


def test_n1_nbsp_before_colon() -> None:
    assert polytypo.transform("Il a dit : bonjour", locale="fr") == f"Il a dit{NBSP}: bonjour"


def test_n7_initial_binding() -> None:
    assert polytypo.transform("M. Dupont", locale="fr") == f"M.{NBSP}Dupont"


def test_n5_before_units() -> None:
    assert polytypo.transform("5 km", locale="fr") == f"5{NBSP}km"


def test_n3_after_short_words_does_not_fire_mid_abbreviation() -> None:
    assert polytypo.transform("p. 12", locale="fr") == "p. 12"
