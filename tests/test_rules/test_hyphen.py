"""spec/rules/hyphen.md guard-level cases not already exercised by conformance fixtures."""

from __future__ import annotations

import polytypo


def test_russian_iz_za_gets_non_breaking_hyphen() -> None:
    assert polytypo.transform("из-за", locale="ru") == "из‑за"


def test_russian_kto_to_gets_non_breaking_hyphen() -> None:
    assert polytypo.transform("кто-то", locale="ru") == "кто‑то"


def test_russian_po_russki_is_not_a_listed_form() -> None:
    assert polytypo.transform("по-русски", locale="ru") == "по-русски"
