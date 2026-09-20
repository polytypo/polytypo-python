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
