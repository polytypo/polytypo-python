"""Builds the real sdist+wheel, installs the wheel into a scratch venv, and exercises the
published package exactly as an end user would -- source-tree imports (via `PYTHONPATH=src` in
every other test file) cannot catch a packaging defect like a missing `py.typed` marker or a
file excluded from the wheel (mirrors the intent of polytypo-js's tests/packaging/, adapted to
pip/venv since Python has no dual ESM/CJS or source-map concerns to check).

Slow (builds a wheel and creates a venv): run explicitly, e.g. `pytest tests/packaging -q`."""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def installed_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    build_dir = tmp_path_factory.mktemp("build")
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(build_dir), str(REPO_ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(build_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, found {wheels}"

    venv_dir = tmp_path_factory.mktemp("venv")
    venv.create(venv_dir, with_pip=True)
    venv_python = venv_dir / "bin" / "python"
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet", str(wheels[0])],
        check=True,
        capture_output=True,
        text=True,
    )
    return venv_python


def _run(venv_python: Path, code: str, tmp_path: Path) -> str:
    script = tmp_path / "smoke.py"
    script.write_text(code, encoding="utf-8")
    result = subprocess.run(
        [str(venv_python), str(script)], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def test_wheel_builds_and_installs(installed_wheel: Path) -> None:
    assert installed_wheel.exists()


def test_all_four_import_paths_work(installed_wheel: Path, tmp_path: Path) -> None:
    code = "import polytypo, polytypo.text, polytypo.html, polytypo.markdown\nprint('ok')\n"
    output = _run(installed_wheel, code, tmp_path)
    assert output == "ok"


def test_py_typed_marker_is_shipped(installed_wheel: Path, tmp_path: Path) -> None:
    code = "import importlib.resources as r\nprint((r.files('polytypo') / 'py.typed').is_file())\n"
    output = _run(installed_wheel, code, tmp_path)
    assert output == "True"


def test_real_transform_call_per_mode(installed_wheel: Path, tmp_path: Path) -> None:
    code = (
        "import polytypo.text\n"
        "import polytypo.html\n"
        "import polytypo.markdown\n"
        "\n"
        "print(polytypo.text.transform('She said, \"it is fine\"', locale='en-US'))\n"
        "print(polytypo.html.transform(\"<p>rock 'n' roll</p>\", locale='en-US'))\n"
        "print(polytypo.markdown.transform('Il a dit \"bonjour\"', locale='fr', "
        "dialect='commonmark'))\n"
    )
    output = _run(installed_wheel, code, tmp_path)
    lines = output.splitlines()
    assert lines[0] == "She said, “it is fine”"
    assert lines[1] == "<p>rock ’n’ roll</p>"
    assert lines[2] == "Il a dit «\xa0bonjour\xa0»"
