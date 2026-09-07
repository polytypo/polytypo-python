# Vendored spec subset

This directory is a manually-synced copy of the subset of `polytypo/polytypo`'s canonical `spec/`
that this repository's build and test suite read: `locales/`, `fixtures/`, `rules/order.json`,
`rules/dashes.md`, `schema/`, `VERSION`, `UNICODE`. It is **not** the canonical spec — the rest of
the normative prose (`spec/rules/*.md` beyond `dashes.md`) and `validate-spec.mjs` live only in
`polytypo/polytypo`. `schema/*.json` is vendored so this repository's own tests can validate the
vendored locale/fixture files structurally (via Python's `jsonschema` package) without
re-implementing `validate-spec.mjs`'s rules by hand.

Editing a file here does not change the spec; it only drifts this copy from canonical. When
canonical's `spec/` changes, re-copy the affected files here. How this vendoring will work
long-term (submodule, per-ecosystem spec package, or something else) is an open decision tracked
in `polytypo/polytypo`'s `docs/ROADMAP.md`; this is the interim, manually-synced form — the same
status `polytypo-js`'s own vendored `spec/` copy has.
