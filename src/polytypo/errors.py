"""The shared error taxonomy (docs/ARCHITECTURE.md section 4.6, canonical repo). One exception
class is enough: the stable machine-readable ``code`` is the contract, not the exception type or
the message text (English, informative, never parsed by calling code)."""

from __future__ import annotations

POLYTYPO_UNKNOWN_LOCALE = "POLYTYPO_UNKNOWN_LOCALE"
POLYTYPO_INVALID_MODE = "POLYTYPO_INVALID_MODE"
POLYTYPO_INVALID_DIALECT = "POLYTYPO_INVALID_DIALECT"
POLYTYPO_UNKNOWN_RULE = "POLYTYPO_UNKNOWN_RULE"
POLYTYPO_MALFORMED_LOCALE_DATA = "POLYTYPO_MALFORMED_LOCALE_DATA"
POLYTYPO_RULE_CONTRACT = "POLYTYPO_RULE_CONTRACT"
POLYTYPO_MALFORMED_INPUT = "POLYTYPO_MALFORMED_INPUT"


class PolytypoError(Exception):
    """Carries a stable ``code`` from the seven above. No other exception type from this package
    or its dependencies is ever allowed to escape :func:`polytypo.transform`."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
