"""spec/rules/nbsp.md 3.1a -- `narrow_nbsp` moves NARROW-TARGET, it does not post-process."""

from __future__ import annotations

import pytest

import polytypo
from polytypo.errors import PolytypoError

NBSP = " "
NNBSP = " "


def _fr(text: str, **kwargs: object) -> str:
    return polytypo.transform(text, locale="fr", **kwargs)  # type: ignore[arg-type]


class TestWhatItChanges:
    def test_writes_nbsp_where_n2_would_write_nnbsp(self) -> None:
        text = "Un délai ? Vraiment ! Et puis ; voilà."
        assert _fr(text) == f"Un délai{NNBSP}? Vraiment{NNBSP}! Et puis{NNBSP}; voilà."
        assert _fr(text, narrow_nbsp="nbsp") == (
            f"Un délai{NBSP}? Vraiment{NBSP}! Et puis{NBSP}; voilà."
        )

    def test_normalises_an_authored_narrow_space_at_a_claimed_index(self) -> None:
        assert _fr(f"Oui{NNBSP}?", narrow_nbsp="nbsp") == f"Oui{NBSP}?"
        assert _fr(f"Oui{NNBSP}?") == f"Oui{NNBSP}?"

    def test_leaves_an_authored_narrow_space_alone_elsewhere(self) -> None:
        assert _fr(f"mot{NNBSP}mot", narrow_nbsp="nbsp") == f"mot{NNBSP}mot"


class TestWhatItDoesNotChange:
    def test_claims_the_same_indices_under_the_same_guards(self) -> None:
        assert _fr("12:30 et http://x ; oui", narrow_nbsp="nbsp") == f"12:30 et http://x{NBSP}; oui"

    def test_leaves_a_sub_rule_whose_target_was_already_nbsp(self) -> None:
        # N1 (the colon) and N8 (fr's primary pair, innerSpace "nbsp") do not move.
        assert _fr("Il a dit : « oui » ; puis ?", narrow_nbsp="nbsp") == (
            f"Il a dit{NBSP}: «{NBSP}oui{NBSP}»{NBSP}; puis{NBSP}?"
        )

    @pytest.mark.parametrize("locale", ["en-US", "de-DE", "ru"])
    def test_is_a_no_op_where_nothing_emits_a_narrow_space(self, locale: str) -> None:
        text = "She said “hi” — really..."
        assert polytypo.transform(text, locale=locale, narrow_nbsp="nbsp") == (
            polytypo.transform(text, locale=locale)
        )


class TestIdempotency:
    def test_is_a_fixed_point_under_the_option(self) -> None:
        for text in ["Un délai ? Vraiment !", f"Oui{NNBSP}?", "Il a dit : « oui » ;"]:
            once = _fr(text, narrow_nbsp="nbsp")
            assert _fr(once, narrow_nbsp="nbsp") == once

    def test_post_processing_the_default_output_is_not(self) -> None:
        # This is why the option moves the target instead: a caller's replace is stable only as
        # long as it always runs. Feed it back through the default pipeline and N2 undoes it.
        post_processed = _fr("Un délai ?").replace(NNBSP, NBSP)
        assert post_processed == f"Un délai{NBSP}?"
        assert _fr(post_processed) == f"Un délai{NNBSP}?"


class TestValidation:
    def test_raises_invalid_option_for_an_unknown_value(self) -> None:
        with pytest.raises(PolytypoError) as excinfo:
            _fr("x", narrow_nbsp="wide")
        assert excinfo.value.code == "POLYTYPO_INVALID_OPTION"

    def test_is_checked_after_mode_and_before_rules_and_locale(self) -> None:
        def code_of(**kwargs: object) -> str:
            try:
                polytypo.transform("x", **kwargs)  # type: ignore[arg-type]
            except PolytypoError as error:
                return error.code
            return "NO THROW"

        assert code_of(locale="fr", mode="asciidoc", narrow_nbsp="wide") == "POLYTYPO_INVALID_MODE"
        assert (
            code_of(locale="fr", narrow_nbsp="wide", rules={"nope": True})
            == "POLYTYPO_INVALID_OPTION"
        )
        assert code_of(locale="xx", narrow_nbsp="wide") == "POLYTYPO_INVALID_OPTION"

    def test_raises_even_when_nbsp_is_disabled(self) -> None:
        # The check belongs to the call, not to the rule.
        with pytest.raises(PolytypoError) as excinfo:
            _fr("x", narrow_nbsp="wide", rules={"nbsp": False})
        assert excinfo.value.code == "POLYTYPO_INVALID_OPTION"

    def test_accepts_the_explicit_default(self) -> None:
        assert _fr("Un délai ?", narrow_nbsp="narrow") == f"Un délai{NNBSP}?"


def test_reaches_the_submodule_entries() -> None:
    from polytypo.html import transform as transform_html
    from polytypo.text import transform as transform_text

    assert transform_text("Un délai ?", locale="fr", narrow_nbsp="nbsp") == f"Un délai{NBSP}?"
    assert transform_html("<p>Un délai ?</p>", locale="fr", narrow_nbsp="nbsp") == (
        f"<p>Un délai{NBSP}?</p>"
    )
