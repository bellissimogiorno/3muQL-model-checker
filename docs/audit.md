# Correctness and design

3μQL Explorer uses one Python engine for the command line and browser worker.
Its tests cover the executable semantics, protocol theories, finite search,
independent countermodel replay, interface state and release packaging. See
[validation](validation.md) for the checks executed on the supplied release.

## Contracts to preserve

| Area | Contract |
| --- | --- |
| Literate theories | Execute only `muql` fences; preserve comments, quoted values, source positions, macros and separate rule-label/formula-identifier grammar. |
| Truth values | Order `f < b < t`; designate `b` and `t`. A counterexample makes its property `f` while every retained axiom is designated. |
| Quorums | Take union closure with the full space; exclude the empty current quorum. The current point may lie outside its quorum. |
| Quantifiers | Apply the documented three-valued affine/unique rules. Latest observations use strictly earlier stages and ignore `b`. |
| Time | Finite time has no final successor. Stutter time gives the last stage a self-successor; it does not model arbitrary natural-time histories. |
| Recurrences | Keep monotonicity checks conservative, iteration bounds explicit and general fixed-point evaluation exact within its documented limit. |
| SAT and search | Establish consistency before validity, enumerate bounded frames with explicit budgets and preserve `unknown` when work is incomplete. |
| Replay | Decode complete atomic valuations and verify them through the separate concrete evaluator before returning a witness. |
| Browser state | Match choices to their exact source, filter stale worker messages, preserve drafts and attach evidence to the run that produced it. |
| Model views | Label the visible coverage and retain complete replayable data in exports. |
| Generated readers | Share the loader's declaration/label grammar; verify that the shipped reader matches regenerated theory content. |
| Distribution | Keep source/site/package bytes consistent and exercise installation outside the source tree. |

## Module boundaries

`muql/checker.py` owns checking phases, deadlines and reports.
`muql/witness.py` owns witness decoding and independent replay.
`muql/compile.py` performs Boolean compilation and caches structural
free-reference analysis within one compiler. Binding-dependent results must
not enter caches that assume closed formulas. The concrete evaluator retains
its own truth routines.

`muql/theory.py` validates theories and label names; `muql/syntax.py` parses
formula expressions. `muql/web.py` validates browser requests and prepares
portable downloads. Browser controllers render metadata as text and keep
source, choices, running work and saved evidence distinct.

The CLI and browser export complete witnesses in JSON. Use that documented
format for saved countermodels; Python object serialization is not a storage
contract.

## Interpretation

These are executable finite checks and design contracts, not formal verification
or a certification of source-paper transcription. The original source PDFs are
not included. A successful fixed-frame check or completed bounded search does
not establish a theorem for arbitrary networks or natural-number time.
