"""spec/rules/modes.md 3.7.2. The parser's own error type must never escape: only the code is
contractual (ARCHITECTURE.md 4.6), a message and a source position are useful and are not part of
it. Reachable in exactly one place normatively (`dialect: "mdx"`, unsupported by this runtime),
but the wrapper is applied to every parser anyway -- the guarantee is that no parser type
escapes, not that a particular parser is trusted (mirrors polytypo-js's parse-error.ts)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from polytypo.errors import POLYTYPO_MALFORMED_INPUT, PolytypoError

T = TypeVar("T")


def wrap_parser_errors(what: str, run: Callable[[], T]) -> T:
    try:
        return run()
    except PolytypoError:
        raise
    except Exception as error:
        raise PolytypoError(
            POLYTYPO_MALFORMED_INPUT, f"Input does not parse as {what}: {error}"
        ) from error
