"""spec/rules/nbsp.md guard-level cases not already exercised by conformance fixtures. `fr` is
used throughout since its locale data exercises every sub-rule (N1-N10)."""

from __future__ import annotations

import polytypo
import polytypo.html

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


def test_n1_right_context_accepts_span_boundary_marker() -> None:
    # nbsp.md 3.3 step 2 (spec 1.2.0): the inline marker is in nbsp's CLOSEISH.
    out = polytypo.html.transform("<strong>gel :</strong> il", locale="fr")
    assert out == f"<strong>gel{NBSP}:</strong> il"


def test_n2_character_reference_guard_numeric() -> None:
    # nbsp.md 3.3 step 4 (spec 1.3.0): the ";" closes "&#160;", so N2 emits nothing. The colon
    # takes nothing either -- step 1's run guard sees a mark to its left.
    assert polytypo.transform("Bonjour&#160;: oui", locale="fr") == "Bonjour&#160;: oui"


def test_n2_character_reference_guard_named() -> None:
    assert polytypo.transform("Tom &amp; Jerry", locale="fr") == "Tom &amp; Jerry"


def test_n2_character_reference_guard_tests_shape_not_the_entity_table() -> None:
    assert polytypo.transform("a &notaname; b", locale="fr") == "a &notaname; b"


def test_n2_ordinary_semicolon_still_binds() -> None:
    assert polytypo.transform("Oui ; non", locale="fr") == f"Oui{NNBSP}; non"


def test_n2_semicolon_after_digit_run_without_ampersand_binds() -> None:
    assert polytypo.transform("Section 4; suite", locale="fr") == f"Section 4{NNBSP}; suite"
