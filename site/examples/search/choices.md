# Correct choices need not be unique

Every choice is two-valued. Does that force at most one chosen value?
This theory supplies no frame: automatic search chooses the participants,
value domain, time stages, quorums, and atomic valuation.

```muql
theory "Correct choices need not be unique"
predicate chosen/1

axiom Correct: ∀v. TF(chosen(v))
property AtMostOne: ∃⁰¹v. chosen(v)
```

Run from the package root:

```sh
python -m muql search examples/search/choices.md --max-points 1 --max-values 2 --max-stages 1
```

Search finds one participant choosing two distinct values with truth value
`t`. The command exits with code `1` because this is a counterexample.
Add `--countermodels witnesses` to save its valuation and a concrete theory
that can be replayed directly. Run `python demo.py --search-only` to include
this example in the guided search tour.
