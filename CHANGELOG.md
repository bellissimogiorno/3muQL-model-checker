# Release notes

## 0.7.5 — 2026-10-20

- Rename 61 axiom declarations across ten bundled theory files to use `?` for
  backward rules and `!` for forward rules, including Bracha's `BrReady!!`.
  Voting, Bracha, Crusader, all four Simple variants, Paxos and Simpler Paxos
  use the convention. Keep descriptive stems for negated/half-output rules
  and the existential Bracha delivery variation; document their correspondence.
- Update demonstrations, replacements/removals, mapping/proof guides, tests,
  reports and generated browser/reader assets. The original audited semantic
  hashes remain the baseline after reversing only the explicit label mapping.
  Formula syntax trees, scopes, property names and expected outcomes are unchanged.
- Reuse the loader's rule-label and declaration grammar in the offline reader
  generator. Check that the shipped reader matches regenerated theory content.
- Refresh all four distributions and the handover. See
  [release validation](docs/validation.md).

## 0.7.4 — 2026-10-20

- Axiom and property labels accept `!`, `?`, and hyphens after the initial
  letter or underscore: `PaxWrite?`, `PaxWrite!`, and `PaxDecide-not-L!`.
  Predicates, macros, variables and formula operators retain their grammar.
- Symbolic labels survive rule removal/replacement, property selection,
  browser drafts, JSON reports, theory exports and independent witness replay.
  Browser download filenames use portable substitutions and distinct indices.
- Highlight complete rule labels in the editor. Keep the bundled theories'
  existing `_back`/`_forward` labels so existing selections remain compatible.
  Added end-to-end Python and Node regressions; refreshed distributions and
  handover. See [release validation](docs/validation.md).

## 0.7.3 — 2026-10-19

- Audited the supplied handover, semantics, engine and delivery paths; reran
  the suites and independent semantic oracles against original and revised code.
- Moved complete countermodel handling and independent replay to `muql/witness.py`,
  retaining existing public imports and JSON formats.
- Cached compiler-local free recurrence names and avoided repeated syntax-key
  hashing on cache hits. Concrete evaluation remains independent.
- Added binding-sensitive compiler regressions, a reproducible 138-record
  before/after comparison and an isolated compilation benchmark.
- Preserved language, theories, solver behavior, browser source and user flows.
  Refreshed all four distributions and the handover. The [audit](docs/audit.md)
  and [validation](docs/validation.md) state the evidence and remaining limits,
  including unavailable real-browser and native-PySAT execution.
