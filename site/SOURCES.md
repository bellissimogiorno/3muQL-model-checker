# Source provenance

This package was vibe-coded following prompts by Murdoch J. Gabbay.

The package implements mathematical definitions in Unicode and ASCII and adds
explicit finite scopes, an engine, examples, and tests. The original papers
are not redistributed inside this release.

## Paxos paper

Murdoch J. Gabbay and Luca Zanolini, *A declarative approach to specifying Paxos
using three-valued modal fixpoint logic*. The authoritative source for this
release is the user-supplied 74-page PDF dated 10 October 2026 in its PDF creation
metadata, supplied as `paxos(20261010-183141).pdf`.

SHA-256:

```text
ab5759a7c0982e72ae94939a053b420da66e97e766a3245853c72a6aa85f3664
```

The source defines 3muQL in Figures 3 and 5, derived operators in Figure 6,
four Simple theories in Section 6.1, full Declarative Paxos in Figure 11,
and Simpler Declarative Paxos in Figure 12. Theorem and page references throughout
the examples refer to this exact attachment. 

Both Paxos examples express `Agreement` with a conjunctive premise: a true
decision now or earlier and a true decision now must agree on their value.
The protocol axioms are those of Figures 11 and 12.
[The agreement proof](docs/spax-agreement.md) establishes the Simpler Paxos
property for natural-number time independently of the finite checker.

## Companion paper

Murdoch J. Gabbay, *Declarative distributed algorithms as axiomatic theories in
three-valued modal logic over semitopologies*,
[arXiv:2512.21137v3](https://arxiv.org/pdf/2512.21137v3), 13 May 2026, 41 pages.
Retrieved 10 October 2026. The version is pinned because future revisions may
change the formulas or the discussion.

Voting is Figure 3; Bracha's axioms and properties are Figures 10 and 11;
Crusader's axioms and properties are Figures 13 and 14. The executable weakening
experiment corresponds to Section 4.3. The paper's arXiv page identifies its
license as CC BY 4.0. The mathematical definitions and claims are attributed to
the original author; our finite-scoping choices and findings are described
separately.

## Coverage and attribution

All **nine explicitly axiomatized protocol theories** are represented: the four
Simple variants, TyPax, TySPax, Voting, Bracha, and Crusader. References to other
protocols such as Heterogeneous Paxos motivate the papers but do not supply
complete axiom sets in these two sources; no invented versions are included.

[The Paxos mapping](docs/paxos-mapping.md) and
[the companion mapping](docs/companion-mapping.md) preserve axiom labels and
explain every representational choice. Original mathematical statements are
not presented as discoveries of this package. Our original code and explanatory
documentation are MIT licensed; the source papers retain their own authorship
and rights. This is an independent implementation and makes no claim of author
endorsement or equivalence to the papers' Lean developments.
