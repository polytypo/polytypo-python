"""spec/rules/modes.md 3.4 -- the edge-growth rule's character clause (spec 1.3.0).

Its normative sentence has always been "an edit is discarded if it would place code points at an
extremity of its span that were not there before". The formalisation `r > d` is not that rule: it
misses `r == d`. `dashes` P3 admits a run of two OR THREE, so `---` -> U+0020 en-dash U+0020 is
3 -> 3 and lands U+0020 on both extremities while the length test sees nothing. In `html` and
`markdown`, both shipped at v1.0.0, that produced an element beginning and ending with a space it
never held, and a de-flanked emphasis delimiter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import polytypo

_LOCALES_DIR = Path(__file__).resolve().parents[2] / "vendor" / "polytypo-spec" / "locales"


def _spaced_locales() -> list[str]:
    """Read from the locale data rather than named here: a hardcoded list rots silently as
    locales are added, and it would also admit `el`, whose `dash.parenthetical` is "none"."""
    out: list[str] = []
    for path in sorted(_LOCALES_DIR.glob("*.json")):
        if path.name == "registry.json":
            continue
        data = json.loads(path.read_text("utf-8"))
        if str(data.get("dash", {}).get("parenthetical", "none")).endswith("-spaced"):
            out.append(path.stem)
    return out


@pytest.mark.parametrize("locale", _spaced_locales())
def test_three_dashes_at_a_span_edge_are_declined(locale: str) -> None:
    assert polytypo.transform("a<em>---</em>b", locale=locale, mode="html") == "a<em>---</em>b"


def test_the_same_edit_interior_to_a_span_still_applies() -> None:
    assert polytypo.transform("<p>a---b</p>", locale="de-DE", mode="html") == "<p>a – b</p>"


def test_an_em_tight_locale_still_converts_at_the_edge() -> None:
    # It emits no U+0020 at all, so the character clause does not fire.
    assert polytypo.transform("a<em>---</em>b", locale="en-US", mode="html") == "a<em>—</em>b"


def test_a_spaced_edit_that_replaces_a_space_with_a_space_still_applies() -> None:
    assert (
        polytypo.transform("a<em>x --- y</em>b", locale="de-DE", mode="html") == "a<em>x – y</em>b"
    )


def test_two_dashes_at_an_edge_are_still_declined_by_the_length_clause() -> None:
    assert polytypo.transform("a<em>--</em>b", locale="de-DE", mode="html") == "a<em>--</em>b"
