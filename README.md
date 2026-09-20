<p align="center">
  <img src="https://raw.githubusercontent.com/polytypo/polytypo/main/brand/logo/polytypo-lockup-stacked.svg" alt="polytypo" width="260">
</p>

<h1 align="center">polytypo</h1>

<p align="center">
  <a href="https://pypi.org/project/polytypo/"><img src="https://img.shields.io/pypi/v/polytypo.svg" alt="PyPI version"></a>
  <a href="https://github.com/polytypo/polytypo-python/actions/workflows/ci.yml"><img src="https://github.com/polytypo/polytypo-python/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/polytypo/"><img src="https://img.shields.io/pypi/dm/polytypo.svg" alt="PyPI downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/polytypo.svg" alt="License: MIT"></a>
</p>

<p align="center">
  Locale-correct quotes, dashes, ellipses, apostrophes, symbols and no-break spaces —<br>
  one portable spec, designed for byte-identical output across runtimes.
</p>

<p align="center">
  <strong>Try it live, no install: <a href="https://polytypo.dev/">polytypo.dev</a></strong>
</p>

This is the Python implementation. The full spec — all locales, all rules, worked examples in
each — lives in [polytypo/polytypo](https://github.com/polytypo/polytypo). This runtime supports
the `text`, `html` and `yaml` modes fully, and `markdown` for the `commonmark` dialect only —
`mdx` raises `POLYTYPO_INVALID_DIALECT` (no MDX/JSX parser is available for Python; see
[Supported dialects](#supported-dialects)).

## Install

```sh
pip install polytypo
```

## Usage

```python
from polytypo import transform

transform("She said, \"it's fine\" -- but I wasn't sure...", locale="en-US")
# She said, “it’s fine”—but I wasn’t sure…
```

Same input, one locale changed — quotes, dash spacing and all follow the target locale, not a
single hardcoded style:

```python
transform('Sie sagte: "Alles gut" -- aber ich war mir nicht sicher...', locale="de-DE")
# Sie sagte: „Alles gut“ – aber ich war mir nicht sicher…
```

HTML and Markdown are first-class modes, not an afterthought — tags, attributes and fenced code
are left alone; only text content is touched:

```python
from polytypo.html import transform

transform('<a title="test... wait">Wait... she said "go on."</a>', locale="en-US")
# <a title="test... wait">Wait… she said “go on.”</a>
```

`polytypo.text`, `polytypo.html`, `polytypo.markdown` and `polytypo.yaml` each exclude the
parser dependency the other modes don't need (importing `polytypo.text` never imports
`html.parser`-based span extraction or tree-sitter; `polytypo.yaml` needs no parser at all). The
aggregate `polytypo` module supports every mode via a `mode` keyword, defaulting to `"text"`.
`locale` has no default anywhere and must always be passed explicitly — there is no silent
fallback to English.

```python
import polytypo

polytypo.transform("...", locale="fr", mode="markdown", dialect="commonmark")
```

`yaml` mode is the one that asks something of you, and it asks for a reason. YAML is a data
format with prose in some of it, so you name the keys whose values are prose; there is no default
and no guess:

```python
from polytypo.yaml import transform

transform("summary: Rates -- all of them...\nrun: git diff -- a--b\n",
          locale="en-US", keys=["summary"])
# summary: Rates—all of them…
# run: git diff -- a--b
```

Nothing in YAML's syntax separates a sentence from a shell script: `description` holds one and
`run` holds the other, spelled identically. Quoting, indentation, anchors and a block scalar's
chomping indicator are never decoded and rewritten — the file is located, not re-emitted — so the
trailing newlines of a `|+` block come back exactly as you wrote them. An empty `keys` list is
legal and processes nothing.

`analyze()` runs the same pipeline and reports what it would do instead of doing it — one record
per edit, each with the rule that made it and code-point offsets into the input you passed (into
the **document**, in `html`, `markdown` and `yaml` mode, not into a span):

```python
import polytypo

polytypo.analyze('Wait... "really"?', locale="en-US")
# [Change(rule_id='ellipsis', start=4, end=7, before='...', after='…'),
#  Change(rule_id='quotes', start=8, end=9, before='"', after='“'), …]
```

It is a report, not a patch. The list is empty exactly when `transform` would return the input
unchanged, and every `rule_id` is a rule that was enabled for that call — but two rules may touch
the same original range (French `spaces` deletes the space before `:` and `nbsp` puts a no-break
one back), so replaying the list is not guaranteed to reproduce the output. Call `transform` for
the text. Full contract: `spec/rules/analyze.md`.

## Supported dialects

`markdown` mode requires a `dialect` keyword, exactly as the spec requires (no default,
detection is forbidden). This runtime supports `dialect="commonmark"` (CommonMark plus GFM —
tables, strikethrough, task lists, autolink literals). `dialect="mdx"` is a real dialect the spec
names, but this runtime has no MDX/JSX parser for it and raises `POLYTYPO_INVALID_DIALECT`
immediately rather than silently mishandling it — a narrower, honest conformance claim, not a
port defect.

## Licence

MIT. See [LICENSE](LICENSE).
