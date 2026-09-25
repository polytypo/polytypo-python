"""modes.md 3.8.2: ``yaml`` mode's ``keys`` option, resolved once at the call boundary.

It has **no default**, for the reason ``dialect`` has none. YAML is a data format with islands of
prose in it, and nothing in its syntax marks them -- ``description`` holds a sentence and ``run``
holds a shell script, spelled identically -- so a default would be a guess about the schema above
the document. An **empty list is legal**: "process nothing" is a choice a caller may make, not an
error.

Checked after ``locale``, last of the option checks, alongside ``dialect`` (ARCHITECTURE.md
section 7). The two never both apply, since each belongs to a different mode."""

from __future__ import annotations

from collections.abc import Sequence

from polytypo.errors import POLYTYPO_INVALID_OPTION, PolytypoError


def resolve_yaml_keys(value: object) -> frozenset[str]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise PolytypoError(
            POLYTYPO_INVALID_OPTION,
            '"keys" is required when mode is "yaml" and must be a sequence of strings '
            f"(modes.md 3.8.2). Received {'nothing' if value is None else repr(value)}.",
        )
    for key in value:
        if not isinstance(key, str):
            raise PolytypoError(
                POLYTYPO_INVALID_OPTION,
                f'"keys" must contain only strings; received {key!r}.',
            )
    return frozenset(value)


def resolve_frontmatter_keys(value: object) -> frozenset[str] | None:
    """modes.md 3.7.4: ``markdown`` mode's ``frontmatter_keys`` (spec 1.7.0).

    Optional, unlike ``keys`` -- absent means the frontmatter block is skipped whole, which is
    every pre-1.7.0 document's behaviour -- and an empty sequence is legal, exactly as it is for
    ``keys``. Checked after ``dialect`` and before the parse, which is what decides that a
    document failing to parse in its dialect still reports the option error rather than
    POLYTYPO_MALFORMED_INPUT. A separate function from ``resolve_yaml_keys`` because the two
    differ exactly where sharing one would bite: this option has no requiredness."""
    if value is None:
        return None
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise PolytypoError(
            POLYTYPO_INVALID_OPTION,
            '"frontmatter_keys" must be a sequence of strings when given '
            f"(modes.md 3.7.4). Received {value!r}.",
        )
    for key in value:
        if not isinstance(key, str):
            raise PolytypoError(
                POLYTYPO_INVALID_OPTION,
                f'"frontmatter_keys" must contain only strings; received {key!r}.',
            )
    return frozenset(value)
