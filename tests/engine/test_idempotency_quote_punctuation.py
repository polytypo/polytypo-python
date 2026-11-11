"""`quote-punctuation` is off by default, so tests/engine/test_idempotency.py never runs it. These
repeat the release-blocking invariant with the rule enabled (spec/rules/quote-punctuation.md 5):
transform(transform(x)) == transform(x), the second call given the same options. Mirrors
polytypo-js's tests/engine/idempotency-quote-punctuation.test.ts."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import polytypo
from polytypo._engine.locale import _registry  # noqa: SLF001 -- test-only introspection

LOCALES = sorted(_registry()["locales"])
ON = {"quote-punctuation": True}

ALPHABET = [
    '"', "'", "“", "”", "‘", "’", "«", "»", "a", "B", "1", ",", ".", ";", "!", "…", " ", " ",
    "\n", "(", ")", "-", "—",
]  # fmt: skip
_hot_text = st.lists(st.sampled_from(ALPHABET), max_size=24).map("".join)


def _is_idempotent(text: str, locale: str) -> bool:
    once = polytypo.transform(text, locale=locale, rules=ON)
    return polytypo.transform(once, locale=locale, rules=ON) == once


@given(locale=st.sampled_from(LOCALES), text=_hot_text)
@settings(max_examples=5000, suppress_health_check=[HealthCheck.too_slow])
def test_idempotent_over_hot_alphabet_every_locale(locale: str, text: str) -> None:
    assert _is_idempotent(text, locale)


@given(locale=st.sampled_from(LOCALES), text=st.text(max_size=100))
@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
def test_idempotent_over_arbitrary_unicode_every_locale(locale: str, text: str) -> None:
    assert _is_idempotent(text, locale)


def test_exhaustive_sweep_en_us_over_the_rules_own_alphabet() -> None:
    # en-US is the only locale that declares "inside"; every other locale is a no-op for this
    # rule and is covered by the sampled properties above.
    sweep = ['"', "”", "“", "’", "a", "1", ",", ".", " "]
    broken: list[str] = []
    moved = 0
    frontier = [""]
    for _ in range(6):
        nxt = []
        for prefix in frontier:
            for ch in sweep:
                text = prefix + ch
                nxt.append(text)
                once = polytypo.transform(text, locale="en-US", rules=ON)
                if once != polytypo.transform(text, locale="en-US"):
                    moved += 1
                if polytypo.transform(once, locale="en-US", rules=ON) != once and len(broken) < 10:
                    broken.append(repr(text))
        frontier = nxt
    assert broken == []
    assert moved > 1000, "a sweep that never fires proves nothing"
