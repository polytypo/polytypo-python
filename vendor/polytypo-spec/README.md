# Vendored spec subset

This directory is a manually-synced copy of the subset of `polytypo/polytypo`'s canonical `spec/`
that this repository's build and test suite read: `locales/`, `fixtures/`, `rules/order.json`,
`rules/dashes.md`, `schema/`, `VERSION`, `UNICODE`. It is **not** the canonical spec — the rest of
the normative prose (`spec/rules/*.md` beyond `dashes.md`) and `validate-spec.mjs` live only in
`polytypo/polytypo`. `schema/*.json` is vendored so this repository's own tests can validate the
vendored locale/fixture files structurally (via Python's `jsonschema` package) without
re-implementing `validate-spec.mjs`'s rules by hand.

Editing a file here does not change the spec; it only drifts this copy from canonical. When
canonical's `spec/` changes, re-copy the affected files here.

CI checks that it was done. `scripts/check-vendored-spec.sh` compares every file in this directory
against canonical `polytypo/polytypo` at tag `spec-v` + this directory's own `VERSION`, and fails
on any difference. Five details. The files this repository authors itself are listed in
`.not-canonical` and skipped — and a listed path that canonical *does* have is an error, so that
list cannot be used to keep a forked copy of a canonical file. A `locales/*.json` file is compared
in full when it carries its `sources` array, and against canonical minus that array when it does
not, which is the shipped form three of the five runtimes vendor; the script reads which case it
is off the file rather than being told. A file here with no canonical counterpart is a failure, so
a canonical rename cannot pass unnoticed. Completeness is checked from canonical's side rather
than this one: every file canonical has at that tag must be here unless `.not-vendored` names it,
so a vendored file that was deleted, or a canonical file that arrived later and was never copied,
fails naming itself, and an entry canonical does not have at that tag, or one that is also present
here, fails too. Here that list names `CONFORMANCE.md` and the twelve rule documents this
repository does not carry. And the version itself is checked: a tree faithful to the tag it claims
while canonical has tagged a newer one is a warning in CI and, with `--require-current`, a refusal
in the release job, because a package must not be published claiming a spec version canonical has
moved past.

Before that check existed, this half of the tree went stale unnoticed in four of the five
ports at once: the data half is proved by the test suite, and nothing at all read the prose.
See `polytypo/polytypo` issue #56. How this vendoring will work
long-term (submodule, per-ecosystem spec package, or something else) is an open decision tracked
in `polytypo/polytypo`'s `docs/ROADMAP.md`; this is the interim, manually-synced form — the same
status `polytypo-js`'s own vendored `spec/` copy has.

## `locales/*.json` here keep their `sources`, and the shipped copy does not

These files are a build input, not a shipped artifact, so the citations cost nothing here and are
worth having next to the data they justify. The generated/installed copy drops them: no rule reads
the citations, and they are 94% of the locale payload by raw bytes (193 KB of 206 KB, against 13 KB
of everything the engine actually consults). See the generator for exactly where that happens.
