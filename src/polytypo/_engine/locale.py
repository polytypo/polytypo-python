"""Locale resolution (spec/rules/locale-resolution.md) and locale data loading. Resolution is
specified centrally and index-based -- no regex, no host locale, no platform locale-negotiation
library (ARCHITECTURE.md sections 4.1, 4.4, 4.7). Data is embedded in the installed package
(section 3.1/3.8) via importlib.resources, read once and cached at module scope -- resolution
itself stays a pure function of (locale, registry), never mutated after import (section 7's "no
module-level mutable state" is about *rule* state; the registry/locale data are immutable spec
data, loaded once, same as the JS reference implementation's generated locales module)."""

from __future__ import annotations

import json
from functools import cache, lru_cache
from importlib import resources
from typing import Any

from polytypo.errors import POLYTYPO_MALFORMED_LOCALE_DATA, POLYTYPO_UNKNOWN_LOCALE, PolytypoError

_DATA_PACKAGE = "polytypo._data.locales"


@lru_cache(maxsize=1)
def _registry() -> dict[str, Any]:
    text = resources.files(_DATA_PACKAGE).joinpath("registry.json").read_text("utf-8")
    result: dict[str, Any] = json.loads(text)
    return result


@cache
def _locale_data_raw(locale_id: str) -> dict[str, Any]:
    text = resources.files(_DATA_PACKAGE).joinpath(f"{locale_id}.json").read_text("utf-8")
    result: dict[str, Any] = json.loads(text)
    return result


def _canonicalize(tag: str) -> list[str]:
    """spec/rules/locale-resolution.md 3.2 -- ASCII-only, host-independent. Returns the
    canonicalized tag as a list of single characters (index-addressable, like the spec's `c[]`)."""
    c = list(tag.replace("_", "-"))
    m = len(c)
    if m >= 2:
        for j in (0, 1):
            if "A" <= c[j] <= "Z":
                c[j] = chr(ord(c[j]) + 32)
    if m == 5 and c[2] == "-":
        for j in (3, 4):
            if "a" <= c[j] <= "z":
                c[j] = chr(ord(c[j]) - 32)
    return c


def _is_valid_shape(c: list[str]) -> bool:
    """spec/rules/locale-resolution.md 3.3 -- tested by index, not by pattern."""
    m = len(c)
    if m == 2:
        return "a" <= c[0] <= "z" and "a" <= c[1] <= "z"
    if m == 5:
        return (
            "a" <= c[0] <= "z"
            and "a" <= c[1] <= "z"
            and c[2] == "-"
            and "A" <= c[3] <= "Z"
            and "A" <= c[4] <= "Z"
        )
    return False


def resolve(tag: object) -> str:
    """Returns the canonical locale id, or raises POLYTYPO_UNKNOWN_LOCALE /
    POLYTYPO_MALFORMED_LOCALE_DATA. Mirrors locale-resolution.md's algorithm exactly, including
    the "tagAbsent" cases (missing, None, or non-string tag)."""
    if not isinstance(tag, str) or len(tag) == 0:
        raise PolytypoError(
            POLYTYPO_UNKNOWN_LOCALE, "locale is required and must be a non-empty string"
        )

    c = _canonicalize(tag)
    if not _is_valid_shape(c):
        raise PolytypoError(POLYTYPO_UNKNOWN_LOCALE, f"malformed locale tag: {tag!r}")

    canonical = "".join(c)
    registry = _registry()
    locales: list[str] = registry["locales"]
    aliases: dict[str, str] = registry["aliases"]

    if canonical in locales:
        return canonical
    if canonical in aliases:
        return _resolve_alias(canonical, aliases, locales)

    if len(c) == 5:
        base = "".join(c[0:2])
        if base in locales:
            return base
        if base in aliases:
            return _resolve_alias(base, aliases, locales)

    raise PolytypoError(
        POLYTYPO_UNKNOWN_LOCALE, f"unknown locale: {tag!r} (resolved to {canonical!r})"
    )


def _resolve_alias(tag: str, aliases: dict[str, str], locales: list[str]) -> str:
    target = aliases[tag]
    if target not in locales:
        raise PolytypoError(
            POLYTYPO_MALFORMED_LOCALE_DATA,
            f"registry alias {tag!r} -> {target!r} does not name a real locale",
        )
    return target


def get_locale_data(locale_id: str) -> dict[str, Any]:
    """The already-resolved locale's data, as parsed JSON matching locale.schema.json's shape."""
    return _locale_data_raw(locale_id)
