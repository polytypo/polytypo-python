"""The conformance runner (docs/ARCHITECTURE.md section 6, canonical repo). Every case in
vendor/polytypo-spec/fixtures/ is driven through the public `polytypo.transform`, and every
non-throwing case is also an idempotency case. Nothing here knows about individual locales or
rules: fixtures are discovered at test time (mirrors polytypo-js's
tests/conformance/runner.test.ts).

`dialect: "mdx"` cases are skipped, not asserted against: this runtime has no MDX/JSX parser and
always raises POLYTYPO_INVALID_DIALECT for that dialect (an accepted, narrower conformance claim
-- see spec/CONFORMANCE.md and README's "supported dialects" note), so asserting the fixture's own
expected output/throws against Python's actual behaviour would either fail spuriously or assert
the wrong code was intentional. spec/rules/modes.md permits a runtime not to support every
dialect, as long as it fails loudly rather than silently mishandling one it claims to support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import polytypo
from polytypo.errors import PolytypoError

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "vendor" / "polytypo-spec" / "fixtures"
RESOLUTION_FILE = FIXTURES_DIR / "locale-resolution.json"


def _escape_non_ascii(text: str) -> str:
    """A diff full of invisible U+00A0 and U+202F is unreviewable (ARCHITECTURE.md 6.1)."""
    return "".join(ch if ord(ch) < 0x80 else f"\\u{ord(ch):04x}" for ch in text)


def _discover_fixture_files() -> list[dict[str, Any]]:
    files = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        if path.name == "locale-resolution.json":
            continue
        data = json.loads(path.read_text("utf-8"))
        files.append({"name": path.name, "locale": data["locale"], "cases": data["cases"]})
    return files


def _case_id(file_name: str, case: dict[str, Any]) -> str:
    return f"{file_name}::{case['id']}"


def _iter_cases():
    for file in _discover_fixture_files():
        for case in file["cases"]:
            yield file["name"], file["locale"], case


CASES = list(_iter_cases())


@pytest.mark.parametrize("file_name,locale,case", CASES, ids=[_case_id(f, c) for f, _, c in CASES])
def test_fixture_case(file_name: str, locale: str, case: dict[str, Any]) -> None:
    if case.get("dialect") == "mdx":
        pytest.skip("mdx dialect is not supported by this runtime (POLYTYPO_INVALID_DIALECT)")

    kwargs: dict[str, Any] = {"locale": locale, "mode": case["mode"]}
    if case.get("dialect") is not None:
        kwargs["dialect"] = case["dialect"]
    if case.get("rules") is not None:
        kwargs["rules"] = case["rules"]

    if "throws" in case:
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.transform(case["in"], **kwargs)
        assert excinfo.value.code == case["throws"]
        return

    expected = case["out"]
    got = polytypo.transform(case["in"], **kwargs)
    assert _escape_non_ascii(got) == _escape_non_ascii(expected)

    # Free coverage, and the most common port bug (ARCHITECTURE.md 6.1).
    twice = polytypo.transform(expected, **kwargs)
    assert _escape_non_ascii(twice) == _escape_non_ascii(expected)


def _load_resolution_cases() -> list[dict[str, Any]]:
    if not RESOLUTION_FILE.exists():
        return []
    return json.loads(RESOLUTION_FILE.read_text("utf-8"))["cases"]


RESOLUTION_CASES = _load_resolution_cases()
PROBES = [
    'He said "so" -- and left...',
    "Pages 1999-2005, see  p. 7 .",
    "Really?.. 50 % (c) 2026",
]


@pytest.mark.parametrize("case", RESOLUTION_CASES, ids=[c["id"] for c in RESOLUTION_CASES])
def test_locale_resolution(case: dict[str, Any]) -> None:
    if "throws" in case:
        with pytest.raises(PolytypoError) as excinfo:
            polytypo.transform("plain text", locale=case["tag"])
        assert excinfo.value.code == case["throws"]
        return

    resolved = case["resolves"]
    for probe in PROBES:
        via_tag = polytypo.transform(probe, locale=case["tag"])
        via_canonical = polytypo.transform(probe, locale=resolved)
        assert _escape_non_ascii(via_tag) == _escape_non_ascii(via_canonical)


def test_conformance_suite_is_not_empty() -> None:
    assert len(CASES) > 0
    assert len(RESOLUTION_CASES) > 0
