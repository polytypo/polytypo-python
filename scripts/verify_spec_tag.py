#!/usr/bin/env python3
"""Two-tag release contract, existence-only variant (docs/ROADMAP.md M5,
docs/REPOSITORY_SPLIT_AND_SPEC_SYNC.md section 4.4, canonical repo).

An operator creates and pushes canonical spec tag `spec-v<VERSION>` (VERSION from
vendor/polytypo-spec/VERSION) to `polytypo/polytypo` before pushing this repo's own release tag
`v<pyproject version>` (only the latter triggers .github/workflows/release.yml). This script
proves that tag exists in the canonical repository -- existence only, not commit-SHA equality.

polytypo-js's own release gate additionally proves both tags resolve to the exact same commit,
which was possible while polytypo-js and polytypo/polytypo shared a git history (pre-split). This
repository was never part of that history -- it is a from-spec port, not a `git filter-repo`
extraction -- so its own commits share no ancestry with polytypo/polytypo's, and no commit SHA
in this repository could ever legitimately equal one in the canonical repository. Existence of
the canonical tag is the strongest claim this repository's own commit history can support; SHA
equality across genuinely unrelated repositories would be a category error, not a stronger check.

Reads the GitHub REST API unauthenticated (polytypo/polytypo is public), never a local git
operation against the canonical repo (it is not this checkout). Exits non-zero with a GitHub
Actions `::error::` annotation on any failure.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

CANONICAL_REPO = "polytypo/polytypo"
STRICT_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def parse_strict_spec_version(raw: str) -> str:
    version = raw.strip()
    if not version:
        raise ValueError("vendor/polytypo-spec/VERSION is empty (after trimming whitespace).")
    if not STRICT_SEMVER.match(version):
        raise ValueError(
            f'vendor/polytypo-spec/VERSION content "{version}" is not a strict MAJOR.MINOR.PATCH '
            "release version -- pre-release suffixes, build-metadata suffixes, leading zeros, "
            "and any other form are rejected by this project's spec-tag policy."
        )
    return version


def derive_spec_tag_name(spec_version: str) -> str:
    return f"spec-v{spec_version}"


def canonical_tag_exists(tag_name: str, canonical_repo: str = CANONICAL_REPO) -> bool:
    url = f"https://api.github.com/repos/{canonical_repo}/git/refs/tags/{tag_name}"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            json.loads(response.read())
            return True
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise RuntimeError(
            f"GitHub API returned {error.code} resolving tag {tag_name!r} in {canonical_repo}."
        ) from error


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    spec_version_raw = (root / "vendor" / "polytypo-spec" / "VERSION").read_text("utf-8")

    try:
        spec_version = parse_strict_spec_version(spec_version_raw)
    except ValueError as error:
        print(f"::error::{error}")
        return 1

    tag_name = derive_spec_tag_name(spec_version)
    print(f"vendor/polytypo-spec/VERSION: {spec_version}")
    print(f"expected canonical spec tag:  {tag_name}")

    try:
        exists = canonical_tag_exists(tag_name)
    except RuntimeError as error:
        print(f"::error::{error}")
        return 1

    if not exists:
        print(
            f"::error::Tag {tag_name!r} does not exist in {CANONICAL_REPO}. It must be created "
            f"and pushed by an operator to {CANONICAL_REPO} before this repository's release tag."
        )
        return 1

    print(f"ok: canonical spec tag {tag_name!r} exists in {CANONICAL_REPO}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
