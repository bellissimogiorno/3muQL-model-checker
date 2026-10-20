# Writing a literate theory

A theory is an ordinary UTF-8 Markdown document. Put executable declarations
inside fenced `muql` blocks and explain them in the surrounding prose. All
`muql` blocks in a document contribute to the same theory. Other code blocks
are ignored. Formulas accept Unicode symbols, plain ASCII, or a mixture of
both. The examples use Unicode for readability; every symbol has an ASCII
spelling. The [notation guide](notation.md) gives a complete copyable table.

```muql
theory "A first quorum experiment"
points alice bob carol
values red blue
stages 2
time finite
quorums {alice,bob} {alice,carol} {bob,carol}

predicate vote/1
let Supported(v): ∃ꟴ□(T(vote(v)))

axiom CorrectVotes: ∀v. TF(vote(v))
property SupportedSomewhere: ∀v.
    Supported(v) ⇀ ∃ꟴ◇(T(vote(v)))
```

Save this as `first.md`, then run `python -m muql check first.md` from the
project root. A property is checked at **every stage, every point, and every
nonempty quorum**, including contexts whose point is outside the current
quorum. Axioms impose that same global requirement. Satisfaction means `t` or
`b`; use `T(...)` when you need exactly `t`.

`check` results concern the declared finite scope; `search` results concern
the selected finite bounds. Neither proves the corresponding statement for
arbitrary networks or natural-number time. See
[semantics.md](semantics.md) for the precise mathematical interpretation.

## Declarations

| Declaration | Meaning |
| --- | --- |
| `theory "Readable title"` | Optional display name; defaults to the filename stem. |
| `points alice bob carol` | Required for `check`: nonempty, distinct point names. |
| `values red blue undef` | Required for `check`: nonempty, distinct finite value domain. `undef` has no built-in behavior. |
| `stages 3` | Required for `check`: positive number of stages, numbered `0`, `1`, `2`. |
| `time finite` | Default: the last stage has no successor. |
| `time stutter` | The last stage has itself as a future successor. |
| `quorums {alice,bob} {bob,carol}` | Required for `check`: nonempty generators for the finite semitopology. |
| `predicate vote/1` | Declare a predicate and its value-argument arity. |
| `axiom Correct: ∀v. TF(vote(v))` | Globally constrain every allowed valuation. |
| `property Goal: ∃v. vote(v)` | Ask whether a formula is designated in every allowed valuation and context. |
| `let Seen(v): once(vote(v))` | A reusable formula abbreviation with value parameters. |

For `search`, the frame declarations are optional: predicates, axioms, and
properties suffice. Declared values are retained as a minimum distinct domain;
otherwise fresh names supply a nonempty domain. `time` still chooses the finite
or stutter convention. Search replaces any declared points, stages, and quorums
with candidate frames within its bounds. `list` can display such a template;
the Python loader accepts it with `for_search=True`. See the
[search guide](search.md) for a complete example and generated replay files.

Start each declaration on its own line. A formula can continue on following
lines, preferably indented. A blank line does not terminate a formula. Start
the next declaration to terminate it. `#` and `//` begin comments outside
quoted strings.

Point and value lists accept whitespace or commas. Quote names containing
spaces or punctuation; quote such values when using them in formulas too.
Predicate, macro, and variable names use ASCII letters, digits, and underscores
and cannot begin with a digit. Predicate and macro names cannot be reserved
words. Axiom and property labels start with an ASCII letter or underscore;
subsequent characters may also include digits, `!`, `?`, and `-`. Thus the
paper-style labels `PaxWrite?`, `PaxWrite!`, and `PaxDecide-not-L!` can be used
directly, without quotes:

```muql
axiom PaxWrite?: T(vote(red))
axiom PaxWrite!: TF(vote(red))
```

The direction marks are part of the label; their meaning comes from the
formula you supply. Inside a formula, `!` still means negation. Axiom and
property labels share one namespace; predicate and macro names share another.
Names are case-sensitive. Existing `_back`/`_forward` spellings remain valid.
In a shell, single-quote labels and replacements to protect punctuation from
history expansion and wildcard matching:

```sh
python -m muql check rules.md --drop 'PaxWrite?'
python -m muql check rules.md --replace 'PaxWrite!=T(vote(red))'
```

Theory exports, reports and witnesses retain the exact labels. Download
filenames substitute `_` for punctuation such as `?` and use numbered prefixes
to distinguish labels that otherwise produce the same filename.

The frame contains the empty set and the whole point set, and closes the
declared generators under **unions**. The empty set is not a current quorum.
The implementation does not add arbitrary supersets or intersections. Thus
`points a b c` with `quorums {a}` has nonempty opens `{a}` and `{a,b,c}`, but
neither `{a,b}` nor `{a,c}`. This matters for quorum-sensitive nested formulas.

Declarations can appear in any order. Duplicate frame declarations, duplicate
names, undeclared points in quorums, empty sets, unknown
predicates, wrong arities, unbound value variables, and binder shadowing are
errors. Missing frame fields are errors for `check` and `replay`; search
templates may omit them. If `quorums` is declared, `points` must also be declared
so those names can be validated. The diagnostic gives a filename, line, and column. Source positions
for name-resolution errors identify the start of the formula declaration.

## Values and predicates

`vote(red)` applies a unary predicate to a declared value. `vote(v)` uses a
bound variable, as in `∀v. vote(v)`. `P` and `P()` both denote a declared
nullary predicate. Predicate arguments are value terms, not formulas.

Bare values and quoted strings resolve in the declared `values` domain.
`red = blue` (also `red == blue`) and `red ≠ blue` (ASCII `red != blue`) are
crisp value equality and inequality.
There are no functions, arithmetic expressions, implicit variables, or
quantifiers over points in this syntax. Point and quorum variation is
expressed through modalities.

## Connectives

The truth constants are `t`, `b`, and `f`: true, broken, and false.

| Unicode | ASCII | Meaning |
| --- | --- | --- |
| `¬P` | `!P` or `not P` | Negation. |
| `P ∧ Q` | `P & Q`, `P && Q`, `P and Q` | Lattice conjunction. |
| `P ∨ Q` | `P \| Q`, `P \|\| Q`, `P or Q` | Lattice disjunction. |
| `P ⊕ Q` | `P xor Q` or `P ^ Q` | `(P ∧ ¬Q) ∨ (¬P ∧ Q)`. |
| `P → Q` | `P -> Q` | Weak implication: `¬P ∨ Q`. |
| `P ⇀ Q` | `P -\ Q` | Strong implication: `¬P ∨ T(Q)`. |
| `P ≡ Q` | `P <=> Q` | Crisp equality of truth values; `t` exactly when both values agree. |
| `P ≤ Q` | `P <= Q` | Crisp assertion of the order `f < b < t`. |

The strong implication symbol is the right harpoon `⇀`, with ASCII spelling
`-\`. These are its only accepted spellings. `=>` is rejected because it
clashes with another implication in the paper. To migrate older package
inputs, replace each `=>` strong-implication operator with `-\` or `⇀`;
leave `<=>` unchanged. Generated ASCII formulas use `-\`.

`≡` / `<=>` is literal truth-value equality, not an abbreviation for two
implications. `≤` / `<=` is a package convenience for testing the lattice order;
it is not the paper's optional three-valued internal order connective.

Both implications allow a broken antecedent to make the implication
designated. To state a classical implication about designated antecedents,
write `TB(P) ⇀ Q` or `TB(P) → Q`, according to whether the conclusion must
be true or merely designated. To require a correct, two-valued predicate,
write `TF(P)`.

## Truth tests

Each truth test returns only `t` or `f`.

| Syntax | Returns `t` when its argument is |
| --- | --- |
| `T(P)` | `t` |
| `F(P)` | `f` |
| `B(P)` | `b` |
| `TB(P)` | `t` or `b` |
| `TF(P)` | `t` or `f` |
| `FB(P)` | `f` or `b` |

## Value binders

| Unicode | ASCII | Meaning |
| --- | --- | --- |
| `∀v. P(v)` | `forall v. P(v)` | Meet over the finite value domain. |
| `∃v. P(v)` | `exists v. P(v)` | Join over the finite value domain. |
| `∃⁰¹v. P(v)` | `affine v. P(v)` | The paper's weak-implication definition of at-most-one existence. |
| `∃¹v. P(v)` | `unique v. P(v)` | `(∃v. P(v)) ∧ (∃⁰¹v. P(v))`, with independent scopes. |

`∃⁰¹` and `∃¹` are three-valued formulas. In particular,
`∃¹v. P(v)` may be designated even when several values give `b` and no
value gives `t`. Use `∃¹v. T(P(v))` to require precisely one actually
true instance. The [basics example](../examples/basics.md) makes this
distinction visible in countermodels.

Binders extend as far right as possible. Write `(∃v. P(v)) ∧ Q` when
`Q` is outside the binder. Nested binders must use distinct names and cannot
reuse a declared value or predicate name.

A space after a symbolic binder is optional: `∀v. P(v)` and `∀ v. P(v)`
are equivalent. Use a space before a bound name beginning with `Q`, since
the accepted plain-Q spellings `∀Q` and `∃Q` name quorum modalities.
`∃1` and `∃!` are accepted aliases for `∃¹`; `∃01` is an
alias for `∃⁰¹`.

## Points and quorums

Evaluation retains a current point and a current nonempty open set `O`.

| Unicode | ASCII | Operation |
| --- | --- | --- |
| `◇(P)` | `diamond(P)` or `somewhere(P)` | Join over points in the current `O`, keeping `O`. |
| `□(P)` | `box(P)` or `everywhere(P)` | Meet over points in the current `O`, keeping `O`. |
| `∃ꟴ(P)` | `existsQ(P)` | Join over all nonempty opens, keeping the current point. |
| `∀ꟴ(P)` | `forallQ(P)` | Meet over all nonempty opens, keeping the current point. |
| `∃ꟴ◇(P)` | `someQuorumSomePoint(P)` | `existsQ(diamond(P))` |
| `∀ꟴ□(P)` | `everyQuorumEveryPoint(P)` | `forallQ(box(P))` |
| `∃ꟴ□(P)` | `quorum(P)` or `someQuorumEveryPoint(P)` | `existsQ(box(P))` |
| `∀ꟴ◇(P)` | `contra(P)` or `everyQuorumSomePoint(P)` | `forallQ(diamond(P))` |

Unicode output uses superscript capital Q (`ꟴ`, U+A7F4). Plain-Q spellings such
as `∃Q□(P)` and `∀Q◇(P)` remain accepted and have exactly the same meaning.

`somewhere` and `everywhere` are aliases for the current-quorum modalities
`diamond` and `box`. To quantify over quorums as well, use the compounds
`someQuorumSomePoint` and `everyQuorumEveryPoint` respectively.

`⋄` is also accepted for `◇`. Symbolic modalities allow prefix notation,
such as `□P`; parentheses in `□(P ∧ Q)` make the intended scope clear.
Named modalities require parentheses: write `box(P)`, not `box P`.

`twined(n)` accepts a positive integer. It requires a nonempty intersection
for every selection of `n` nonempty opens, allowing repetition.

The chosen open remains visible inside the body. In particular,
`∀ꟴ□(□(P))` must preserve this scope; interpreting every nested
operator solely as a quantifier over all points would be incorrect. Explore
[semitopology.md](../examples/semitopology.md) for examples.

## Time

All temporal operators preserve the current point and quorum except for
`ultimately`, which includes `everyQuorumEveryPoint` explicitly.

| Syntax | Meaning |
| --- | --- |
| `yesterday(P)` | Previous stage; `f` at stage zero. |
| `tomorrow(P)` | Next stage; `f` at the end in finite mode, current value there in stutter mode. |
| `once(P)` | Join over strictly earlier stages; `f` at stage zero. |
| `historically(P)` | Meet over strictly earlier stages; `t` at stage zero. |
| `past(P)` | Join over earlier stages **and the current stage**. |
| `sometime(P)` | Join over reachable strictly future stages. |
| `forever(P)` | Meet over reachable strictly future stages. |
| `infinitely(P)` | `forever(sometime(P))`. |
| `ultimately(P)` | `sometime(everyQuorumEveryPoint(forever(P)))`. |

In finite mode, the empty future join is `f` and the empty future meet is
`t`. In stutter mode, the final stage is reachable from itself, so future
operators include it. This finite temporal-frame convention does not
unroll past operators along an infinite repeated suffix. Boundary artifacts
are real: a finite-mode liveness axiom may make a theory inconsistent.
Neither mode proves an unbounded liveness theorem.

`latest v = red. P(v)` asks whether `red` satisfies `P` with value exactly `t`
at the latest strictly earlier stage where **some** value satisfied `P`
with value `t`. It is `f` if no such stage exists. The term after `=` is the
value to test, not a fallback value. The result is crisp. Several values
can satisfy this formula if they were all true at that latest stage;
functional behavior requires an appropriate uniqueness axiom.

## Fixed-point binders

`μX. P ∨ yesterday(X)` (ASCII `mu X. P | yesterday(X)`) binds a
formula-valued variable. Its denotation is
the meet of all pre-fixed points of the body on the finite context lattice.
For a monotone body, this is its least fixed point. The parser also accepts
nonmonotone bodies, matching the paper's more general definition; their
meet need not itself be a fixed point.

`νX. P ∧ tomorrow(X)` (ASCII `nu X. P & tomorrow(X)`) is the package's dual
convenience: the join of all
post-fixed points, and the greatest fixed point for a monotone body.
Fixed-point variables take no arguments and only exist inside their binder.
Use uppercase names such as `X` by convention; uppercase is not required.
Both Greek `μ` and the visually similar micro sign `µ` are accepted for `mu`;
displayed formulas use Greek `μ`.

Monotone cases use finite iteration. Nonmonotone cases use exact finite
enumeration with an explicit resource limit. An exceeded limit produces
`unknown`, never a successful proof. See
[fixedpoints.md](../examples/fixedpoints.md) for both cases.

## Precedence, macros, and reserved words

Unicode symbols and their ASCII spellings have identical precedence. From
tightest to loosest:

| Level | Unicode | ASCII |
| --- | --- | --- |
| 1 · tightest | Value `=`, `≠` | Value `=`, `==`, `!=` |
| 2 | Prefix `¬`, symbolic modalities | Prefix `!`, `not` |
| 3 | `∧` | `&`, `&&`, `and` |
| 4 | `⊕` | `xor`, `^` |
| 5 | `∨` | `\|`, `\|\|`, `or` |
| 6 | `→`, `⇀` | `->`, `-\` |
| 7 | `≤` | `<=` |
| 8 · loosest | `≡` | `<=>` |

Implications associate right; other binary operators associate left. Modal
calls use parentheses; symbolic modalities may also be used as prefixes.
Binders extend over the full following formula. Parenthesize mixed
implications for readability. In particular, `P ⇀ Q ⇀ R` means
`P ⇀ (Q ⇀ R)`, which is different from `(P ∧ Q) ⇀ R` in this logic.

Macros take only value terms: `let Supported(v): ∃ꟴ□(T(vote(v)))` can be
called as `Supported(red)` or `Supported(v)` under a quantifier. A nullary
macro can be called as `Supported` or `Supported()`. Forward references are
allowed, recursive macros are rejected, and local binders are renamed to
avoid variable capture. Even unused macros are checked for errors.

Every argument is checked before expansion, including arguments that the macro
does not use. Macro parameters obey the same no-shadowing rules as other value
binders. Generated local names avoid all declared names and macro parameters.
Expansion, substitution, and renaming together have a limit of 100,000 visited
nodes per expansion. Exceeding that input limit, or the parser's nesting limit,
produces a source diagnostic and CLI exit `2`; no theory has been checked.
This front-end limit is separate from the search budgets that produce `unknown`.

The following words are reserved in formula syntax and cannot name a
predicate, macro, or binder:

```text
t b f not and or xor
theory points values stages time quorums predicate axiom property let
T F B TB TF FB
forall exists affine unique mu nu latest twined
diamond box somewhere everywhere existsQ forallQ quorum contra
someQuorumSomePoint everyQuorumEveryPoint someQuorumEveryPoint everyQuorumSomePoint
yesterday tomorrow once historically past sometime forever infinitely ultimately
```

Quoted values can contain reserved words. Bare names remain case-sensitive:
`True` is a possible declared predicate name; `t` is a truth constant.
