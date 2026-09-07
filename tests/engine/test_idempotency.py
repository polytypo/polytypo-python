"""transform(transform(x)) == transform(x) is a release blocker, not a bug report (PLAN.md 3.4,
mirrors polytypo-js's tests/engine/idempotency.test.ts). Property-based over a biased alphabet
(uniform random Unicode almost never produces the adjacent-quote-mark shapes that actually break
a pipeline), plus bounded exhaustive sweeps, which a defect at this size cannot hide from."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import polytypo
from polytypo._engine.locale import _registry  # noqa: SLF001 -- test-only introspection

VENDOR_ROOT = Path(__file__).resolve().parents[2] / "vendor" / "polytypo-spec"
LOCALES = sorted(_registry()["locales"])

# The characters every rule reads: quote marks, strokes, spacing, digits, brackets, stops.
# "km" is a two-character unit in the JS reference's fast-check sweep -- a multi-char "unit"
# fast-check supports and hypothesis's `text(alphabet=...)` does not (exactly one code point per
# element), so it is drawn here as two single-character elements instead.
HOT_CHARS = [
    '"',
    "'",
    "“",
    "”",
    "‘",
    "’",
    "„",
    "‚",
    "«",
    "»",
    "‹",
    "›",
    "-",
    "‐",
    "‑",
    "–",
    "—",
    " ",
    " ",
    " ",
    "\n",
    ".",
    ",",
    ":",
    ";",
    "!",
    "?",
    "…",
    "(",
    ")",
    "[",
    "]",
    "0",
    "1",
    "9",
    "a",
    "B",
    "x",
    "é",
    "и",
    "k",
    "m",
    "%",
    "§",
    "№",
    "σ",
    "·",
]
_hot_text = st.lists(st.sampled_from(HOT_CHARS), max_size=24).map("".join)


@given(locale=st.sampled_from(LOCALES), text=_hot_text)
@settings(max_examples=2000, suppress_health_check=[HealthCheck.too_slow])
def test_idempotent_over_hot_alphabet(locale: str, text: str) -> None:
    once = polytypo.transform(text, locale=locale)
    twice = polytypo.transform(once, locale=locale)
    assert twice == once


@given(locale=st.sampled_from(LOCALES), text=st.text(max_size=100))
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_idempotent_over_arbitrary_unicode(locale: str, text: str) -> None:
    once = polytypo.transform(text, locale=locale)
    twice = polytypo.transform(once, locale=locale)
    assert twice == once


def _rule_ids() -> list[str]:
    order = json.loads((VENDOR_ROOT / "rules" / "order.json").read_text("utf-8"))
    return [r["id"] for r in sorted(order["rules"], key=lambda r: r["order"])]


@given(locale=st.sampled_from(LOCALES), text=st.text(max_size=100))
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_all_rules_disabled_is_a_no_op(locale: str, text: str) -> None:
    all_off = {rule_id: False for rule_id in _rule_ids()}
    assert polytypo.transform(text, locale=locale, rules=all_off) == text


def _bounded_strings(alphabet: list[str], max_length: int):
    frontier = [""]
    yield ""
    for _ in range(max_length):
        nxt = []
        for prefix in frontier:
            for ch in alphabet:
                candidate = prefix + ch
                nxt.append(candidate)
                yield candidate
        frontier = nxt


def test_bounded_exhaustive_sweep_every_locale() -> None:
    """Both the input characters and the ones the rules produce: a pass over its own output is
    what idempotency actually asserts."""
    alphabet = ['"', "'", "-", " ", ".", "1", "a", "«", "–", "”"]
    broken: list[str] = []
    for locale in LOCALES:
        for text in _bounded_strings(alphabet, 4):
            once = polytypo.transform(text, locale=locale)
            if polytypo.transform(once, locale=locale) != once:
                broken.append(f"{locale}: {text!r}")
                if len(broken) >= 10:
                    break
    assert broken == []


def test_mixed_kind_straight_marks_are_idempotent() -> None:
    """A straight mark of one kind stranded inside a span quoted with the other kind
    (`"a 'b" c'`) is the shape that broke quotes' first repair attempt; this discriminates."""
    alphabet = ['"', "'", "a", " ", "."]
    broken: list[str] = []
    for locale in LOCALES:
        for text in _bounded_strings(alphabet, 6):
            once = polytypo.transform(text, locale=locale)
            if polytypo.transform(once, locale=locale) != once:
                broken.append(f"{locale}: {text!r}")
                if len(broken) >= 10:
                    break
    assert broken == []


def test_idempotent_around_html_line_boundary_marker() -> None:
    """modes.md 3.2's -2 LINE_MARKER must be a BREAK member for every rule; this is exactly the
    class of regression the marker/BREAK fixes in this port guard against."""
    alphabet = [" ", '"', "-", ".", "a", "1"]
    broken: list[str] = []
    for locale in LOCALES:
        for left in _bounded_strings(alphabet, 2):
            for right in _bounded_strings(alphabet, 2):
                text = f"{left}<!--\n-->{right}"
                once = polytypo.transform(text, locale=locale, mode="html")
                if polytypo.transform(once, locale=locale, mode="html") != once:
                    broken.append(f"{locale}: {text!r}")
                    if len(broken) >= 10:
                        break
    assert broken == []


def test_idempotent_around_markdown_line_boundary_marker() -> None:
    alphabet = [" ", '"', "-", ".", "a", "1"]
    broken: list[str] = []
    for locale in LOCALES:
        for left in _bounded_strings(alphabet, 2):
            for right in _bounded_strings(alphabet, 2):
                text = f"{left}\n\n{right}"
                kwargs = {"locale": locale, "mode": "markdown", "dialect": "commonmark"}
                once = polytypo.transform(text, **kwargs)
                twice = polytypo.transform(once, **kwargs)
                if twice != once:
                    broken.append(f"{locale}: {text!r}")
                    if len(broken) >= 10:
                        break
    assert broken == []


def test_line_boundary_classified_as_break_matching_text_mode() -> None:
    """modes.md 7.4: on the same characters a mode must agree with `text`."""
    for locale in LOCALES:
        text_out = polytypo.transform("a  \n  b", locale=locale)
        html_out = polytypo.transform("a  <!--\n-->  b", locale=locale, mode="html")
        assert html_out == text_out.replace("\n", "<!--\n-->")
