"""``polytypo.yaml`` -- YAML-only entry point, and the lightest of the four: ``yaml`` mode uses no
parser at all (spec/rules/modes.md 3.8.1), so this module's graph excludes ``html.parser``-based
span extraction and tree-sitter for the same reason ``polytypo.text``'s does -- it has nothing to
import.

``mode`` and ``dialect`` are absent from this entry's ``transform``; ``keys`` goes the other way.
It is optional on the aggregate entry because the other three modes ignore it, and **required**
here, where the mode is fixed and the option always applies."""

from __future__ import annotations

from collections.abc import Sequence

from polytypo._engine.mode_pipelines import analyze_yaml_pipeline, run_yaml_pipeline
from polytypo._engine.origin import Change
from polytypo.errors import PolytypoError

__all__ = ["Change", "PolytypoError", "analyze", "transform"]


def transform(
    input: str,
    *,
    locale: str,
    keys: Sequence[str],
    rules: dict[str, bool] | None = None,
    narrow_nbsp: str | None = None,
) -> str:
    """`keys` names the mapping keys whose scalar values are processable (modes.md 3.8.2). It has
    no default: YAML is a data format with islands of prose in it, and nothing in its syntax
    separates `description:` from `run:`. An empty sequence is legal and processes nothing."""
    return run_yaml_pipeline(input, locale=locale, keys=keys, rules=rules, narrow_nbsp=narrow_nbsp)


def analyze(
    input: str,
    *,
    locale: str,
    keys: Sequence[str],
    rules: dict[str, bool] | None = None,
    narrow_nbsp: str | None = None,
) -> list[Change]:
    """The same pipeline as this entry's `transform`, reporting instead of applying
    (spec/rules/analyze.md). Offsets are code-point offsets into `input`, not into a span."""
    return analyze_yaml_pipeline(
        input, locale=locale, keys=keys, rules=rules, narrow_nbsp=narrow_nbsp
    )
