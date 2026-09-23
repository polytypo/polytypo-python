#!/usr/bin/env python3
"""Copies the runtime-needed subset of vendor/polytypo-spec/ into src/polytypo/_data/, so it
ships as installed package data (read via importlib.resources) instead of the package needing
vendor/ present at runtime (ARCHITECTURE.md section 3.8: no runtime filesystem reads outside the
installed package). vendor/polytypo-spec/ stays the vendored source-of-truth checkout, read
directly by tests; this script's output is what actually ships. Regenerate after re-syncing
vendor/polytypo-spec/ from canonical:

    python3 scripts/gen_data.py
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "polytypo-spec"
DATA = ROOT / "src" / "polytypo" / "_data"


def _init_package(directory: Path) -> None:
    """Marks `directory` as a regular (non-namespace) package, so
    importlib.resources.files("polytypo._data...") resolves unambiguously regardless of how the
    package was installed (wheel, editable install)."""
    (directory / "__init__.py").write_text("")


def copy_locales() -> int:
    dest = DATA / "locales"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    _init_package(dest)
    files = sorted((VENDOR / "locales").glob("*.json"))
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        # `sources` is dropped from the SHIPPED copy. It is mandatory in the canonical spec
        # (locale.schema.json makes it required with minItems: 1, and validate-spec.mjs enforces
        # it), it is kept byte-for-byte in vendor/polytypo-spec/, and it is rendered on the
        # project's Locales page -- but no rule reads it, and it is 94% of the locale payload by
        # raw bytes: 193 KB of 206 KB, against 13 KB of everything the engine actually consults.
        # registry.json carries no `sources` and is unaffected by the pop().
        #
        # This is a projection applied when generating package data, not a change to what is
        # vendored -- the vendoring mechanism is an open decision in the canonical CLAUDE.md and
        # is deliberately not touched here.
        data.pop("sources", None)
        (dest / f.name).write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    return len(files)


def copy_rule_order() -> None:
    dest = DATA / "rules"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    _init_package(dest)
    shutil.copy2(VENDOR / "rules" / "order.json", dest / "order.json")


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    _init_package(DATA)
    n_locales = copy_locales()
    copy_rule_order()
    print(f"  copied {n_locales} locale data file(s) to {(DATA / 'locales').relative_to(ROOT)}")
    print(f"  copied rules/order.json to {(DATA / 'rules').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
