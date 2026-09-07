#!/usr/bin/env python3
"""Rejects a release unless the pushed tag exactly matches `v<pyproject.toml version>`, and
separately and unconditionally rejects the version "0.0.0" -- pyproject.toml's version is
deliberately left there until an operator explicitly chooses the first real public version
(mirrors polytypo-js's scripts/verify-release-tag.mjs)."""

from __future__ import annotations

import sys
from pathlib import Path

import tomllib


def main() -> int:
    if len(sys.argv) != 2:
        print("::error::usage: python scripts/verify_release_tag.py <pushed-tag>")
        return 1

    pushed_tag = sys.argv[1]
    root = Path(__file__).resolve().parent.parent
    pyproject = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))
    version = pyproject["project"]["version"]

    if version == "0.0.0":
        print(
            "::error::pyproject.toml version is still the 0.0.0 placeholder. An operator must "
            "choose the first real public version before this tag can trigger a release."
        )
        return 1

    expected_tag = f"v{version}"
    if pushed_tag != expected_tag:
        print(
            f"::error::pushed tag {pushed_tag!r} does not match pyproject.toml version "
            f"{version!r} (expected {expected_tag!r})."
        )
        return 1

    print(f"ok: tag {pushed_tag!r} matches pyproject.toml version {version!r}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
