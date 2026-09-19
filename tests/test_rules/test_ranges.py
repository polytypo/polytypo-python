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


WJ = "⁠"
EN = "–"
EM = "—"


def _t_de(text: str) -> str:
    return polytypo.transform(text, locale="de-DE", rules={"ranges": True})


class TestClosedUpSymbols:
    """ranges.md 3.2a (spec 1.3.0): a symbol repeated closed up on both members."""

    def test_admits_a_repeated_prefix(self) -> None:
        assert _t("$15-$20") == f"$15{WJ}{EN}{WJ}$20"
        assert _t_de("€15-€20") == f"€15{WJ}{EN}{WJ}€20"

    def test_admits_a_repeated_suffix(self) -> None:
        # The mirror case: the walk moves the LEFT flank and matches the outer symbol after Rrun.
        assert _t("35%-50%") == f"35%{WJ}{EN}{WJ}50%"
        assert _t("15°-20°") == f"15°{WJ}{EN}{WJ}20°"
        assert polytypo.transform("35%-50%", locale="ru", rules={"ranges": True}) == (
            f"35%{WJ}{EM}{WJ}50%"
        )

    def test_requires_the_same_code_point(self) -> None:
        # A currency conversion, not a range; and two half-written shapes.
        assert _t("$15-€20") == "$15-€20"
        assert _t("15-$20") == "15-$20"
        assert _t("15%-20") == "15%-20"

    def test_leaves_the_elided_forms_alone(self) -> None:
        assert _t("$15-20") == f"$15{WJ}{EN}{WJ}20"
        assert _t("15-20%") == f"15{WJ}{EN}{WJ}20%"

    def test_consumes_at_most_one_code_point_per_side(self) -> None:
        assert _t("US$15-US$20") == "US$15-US$20"
        assert _t("15°C-20°C") == "15°C-20°C"

    def test_block_membership_is_by_bounds_not_by_category(self) -> None:
        # U+20B9 and U+20B4 are block members no other test names; U+058F and U+FFE5 are
        # currency signs in Unicode's own classification, deliberately outside CLOSED-SYMBOL.
        assert _t("₹15-₹20") == f"₹15{WJ}{EN}{WJ}₹20"
        assert _t("₴100-₴200") == f"₴100{WJ}{EN}{WJ}₴200"
        assert _t("֏15-֏20") == "֏15-֏20"
        assert _t("￥15-￥20") == "￥15-￥20"

    def test_decides_both_flanks_simultaneously(self) -> None:
        assert _t("%15%-%20%") == f"%15%{WJ}{EN}{WJ}%20%"

    def test_takes_the_spaced_token_away_from_dashes(self) -> None:
        # Through spec 1.2.0 `dashes` converted this with DEFAULT options.
        assert polytypo.transform("$15 - $20", locale="en-US") == "$15 - $20"
        assert _t("$15 - $20") == f"$15{WJ}{EN}{WJ}$20"
        # Only a MATCHED symbol moves a token between rules.
        assert polytypo.transform("$15 - €20", locale="en-US") == "$15—€20"


class TestClosedUpSymbolsAndT1:
    """dashes.md 3.2 step 8 (spec 1.3.0). Widening a range member widens what a `dashes` edit
    elsewhere can disturb; each witness drifted on the second pass before T1's reach became
    CLOSED-SYMBOL-transparent, and each is inert in its all-digit shape."""

    WITNESSES = ["a—$15-$20", "35%-50%—b", "a--15% - 20%", "$1 - $1--a"]

    def test_every_witness_is_a_fixed_point(self) -> None:
        for locale in ("de-DE", "ru", "en-GB", "fi"):
            for text in self.WITNESSES:
                once = polytypo.transform(text, locale=locale, rules={"ranges": True})
                assert polytypo.transform(once, locale=locale, rules={"ranges": True}) == once

    def test_composes_both_positions_on_one_side(self) -> None:
        for text in ("a--$15% - $20%", "$15% - $20%--a", "a--$15% - $20%--b"):
            once = _t_de(text)
            assert _t_de(once) == once

    def test_symbol_shape_matches_its_all_digit_analogue(self) -> None:
        assert _t_de("a—15-20") == "a—15-20"
        assert _t_de("a—$15-$20") == "a—$15-$20"
        assert _t_de("a--1 - 1") == "a--1 - 1"
        assert _t_de("a--$1 - $1") == "a--$1 - $1"

    def test_tight_parenthetical_locale_is_untouched(self) -> None:
        # T1 only applies when the chosen form is spaced — the boundary of the cost, and the
        # reason the repair is T1 and not the unconditional cluster guard.
        assert polytypo.transform("price--$50--drop", locale="en-US") == "price—$50—drop"
        assert polytypo.transform("Anstieg--50%--war", locale="de-DE") == "Anstieg--50%--war"
        assert polytypo.transform("Anstieg--50--war", locale="de-DE") == "Anstieg--50--war"

    def test_right_branch_reads_effective_neighbours(self) -> None:
        # dashes.md 3.2 step 8 disagreed with 3.2b in its own text through spec 1.2.0; no
        # implementation ever did. The space ends the cluster, so step 7 does not cover this.
        assert _t_de(f"a--15{WJ} - 20") == f"a--15{WJ} - 20"
        assert _t_de(f"a--$15{WJ}-{WJ}$20") == f"a--$15{WJ}-{WJ}$20"

    def test_converts_a_hyphen_between_an_existing_joiner_pair(self) -> None:
        assert _t(f"$15{WJ}-{WJ}$20") == f"$15{WJ}{EN}{WJ}$20"
