#!/usr/bin/env python3
"""Copies the runtime-needed subset of vendor/polytypo-spec/ into src/polytypo/_data/, so it
ships as installed package data (read via importlib.resources) instead of the package needing
vendor/ present at runtime (ARCHITECTURE.md section 3.8: no runtime filesystem reads outside the
installed package). vendor/polytypo-spec/ stays the vendored source-of-truth checkout, read
directly by tests; this script's output is what actually ships. Regenerate after re-syncing
vendor/polytypo-spec/ from canonical:

    python3 scripts/gen_data.py
"""

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
        shutil.copy2(f, dest / f.name)
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
