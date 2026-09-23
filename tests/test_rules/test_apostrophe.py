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


def test_case_3a_elision_before_opening_quotation_glyph() -> None:
    # apostrophe.md 3.3 case 3a (spec 1.2.0).
    assert polytypo.transform("l'“idea”", locale="en-US") == "l’“idea”"


def test_case_3a_excludes_brackets() -> None:
    assert polytypo.transform("f'(x) = 2", locale="en-US") == "f'(x) = 2"


def test_case_2a_possessive_after_closing_bracket() -> None:
    # apostrophe.md 3.3 case 2a (spec 1.5.0): the closing delimiters case 3 has always
    # accepted on the mark's right are now accepted on its left too.
    assert (
        polytypo.transform("The pipeline (order 90)'s own output", locale="en-US")
        == "The pipeline (order 90)’s own output"
    )
    assert polytypo.transform("{user}'s account", locale="en-US") == "{user}’s account"
    assert polytypo.transform("the footnote [3]'s author", locale="en-US") == (
        "the footnote [3]’s author"
    )


def test_case_2a_possessive_after_closing_quotation_glyph() -> None:
    # The asymmetry case 2a removes: U+00AB is an OPENISH member and reached case 4 before
    # 1.5.0, while U+00BB and U+203A sat in CLOSEISH, which no left-hand test read.
    assert polytypo.transform("»Wort«'s", locale="en-GB") == "»Wort«’s"
    assert polytypo.transform("«Wort»'s", locale="en-GB") == "«Wort»’s"
    assert polytypo.transform("‹Wort›'s", locale="en-GB") == "‹Wort›’s"
    assert polytypo.transform("“Hamlet”'s", locale="en-US") == "“Hamlet”’s"
    # U+2019 is both this rule's only emission and a CLOSEDELIM member.
    assert polytypo.transform("A ‘quoted’'s meaning", locale="en-GB") == "A ‘quoted’’s meaning"


def test_case_2a_declines_sentence_punctuation() -> None:
    for left in [",", ".", ";", ":", "!", "?", "…"]:
        assert polytypo.transform(f"said{left}'yes", locale="en-GB") == f"said{left}'yes"


def test_case_2a_declines_every_symbol() -> None:
    # apostrophe.md 7 item 8: the declined half of canonical issue #28.
    for left in ["%", "°", "‰", "²", "³", "¹", "⁴"]:
        assert polytypo.transform(f"10{left}'u", locale="en-GB") == f"10{left}'u"


def test_case_2a_leaves_a_prime_on_a_function_name_alone() -> None:
    # It is case 2a's ALNUM right-test that does this, not the case 1 prime guard, which
    # reads DIGIT on the left only.
    assert polytypo.transform("f²'(x) = 4", locale="en-US") == "f²'(x) = 4"
